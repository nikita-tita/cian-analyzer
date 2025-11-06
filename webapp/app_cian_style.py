"""
Flask веб-приложение с интерфейсом в стиле Cian
С полными данными по ВСЕМ похожим объявлениям
"""

from flask import Flask, render_template, request, jsonify, send_file
import sys
import os
import io
import zipfile
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.cian_parser_breadcrumbs import CianParserBreadcrumbs
from src.watermark_remover import WatermarkRemover
from src.iopaint_client import IOPaintClient
from src.markdown_exporter import save_results_as_markdown
from src.txt_exporter import save_results_as_txt
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Хранилище последнего результата парсинга для скачивания
last_parse_result = None


@app.route('/')
def index():
    """Главная страница с Cian-style интерфейсом"""
    return render_template('index_cian_style.html')


@app.route('/parse', methods=['POST'])
def parse():
    """API endpoint для парсинга"""
    try:
        data = request.get_json()
        url = data.get('url', '').strip()

        if not url:
            return jsonify({
                'success': False,
                'error': 'URL не указан'
            }), 400

        if 'cian.ru' not in url:
            return jsonify({
                'success': False,
                'error': 'Это не ссылка на Cian.ru'
            }), 400

        logger.info(f"🔍 Парсинг URL: {url}")
        logger.info(f"⚡ Режим: ПОЛНЫЕ данные для ВСЕХ похожих объявлений")

        # Парсим с полными данными для ВСЕХ похожих
        with CianParserBreadcrumbs(headless=True) as parser:
            result = parser.parse_detail_page_full(url, get_full_similar=True)

        # Считаем статистику
        similar_count = len(result.get('similar_listings', []))
        full_data_count = sum(
            1 for s in result.get('similar_listings', [])
            if s.get('characteristics') and len(s['characteristics']) > 5
        )

        logger.info(f"✅ Готово!")
        logger.info(f"   📊 Основное: {len(result.get('characteristics', {}))} характеристик")
        logger.info(f"   🏘️ Похожих: {similar_count}")
        logger.info(f"   ✅ С полными данными: {full_data_count}/{similar_count}")

        # Сохраняем результат для возможности скачивания
        global last_parse_result
        last_parse_result = result

        return jsonify({
            'success': True,
            'data': result,
            'stats': {
                'characteristics': len(result.get('characteristics', {})),
                'similar_total': similar_count,
                'similar_full': full_data_count,
                'images': len(result.get('images', []))
            }
        })

    except Exception as e:
        logger.error(f"❌ Ошибка при парсинге: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/download_photos', methods=['POST'])
def download_photos():
    """Скачать архив с очищенными фото"""
    global last_parse_result

    if not last_parse_result:
        return jsonify({
            'success': False,
            'error': 'Сначала выполните парсинг объявления'
        }), 400

    try:
        data = request.get_json()
        remove_watermarks = data.get('remove_watermarks', True)

        logger.info(f"📦 Создание архива с фото...")
        logger.info(f"   🧹 Удаление водяных знаков: {'Да' if remove_watermarks else 'Нет'}")

        # Собираем все URL фотографий
        all_photos = []

        # Основное объявление
        main_title = last_parse_result.get('title', 'Основное объявление')
        for i, img_url in enumerate(last_parse_result.get('images', [])[:12]):  # Первые 12 фото
            all_photos.append({
                'url': img_url,
                'folder': '00_Основное_объявление',
                'filename': f'photo_{i+1:02d}.jpg'
            })

        # Похожие объявления
        for idx, listing in enumerate(last_parse_result.get('similar_listings', []), 1):
            listing_title = listing.get('title', f'Объявление {idx}')[:50]  # Ограничиваем длину
            # Убираем спецсимволы из имени папки
            safe_title = "".join(c for c in listing_title if c.isalnum() or c in (' ', '_', '-')).strip()
            folder_name = f'{idx:02d}_{safe_title}'

            for i, img_url in enumerate(listing.get('images', [])[:12]):  # Первые 12 фото каждого
                all_photos.append({
                    'url': img_url,
                    'folder': folder_name,
                    'filename': f'photo_{i+1:02d}.jpg'
                })

        logger.info(f"   📊 Всего фотографий: {len(all_photos)}")

        # Создаем ZIP архив в памяти
        memory_file = io.BytesIO()

        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Обрабатываем фото
            if remove_watermarks:
                logger.info("   🧹 Удаляем водяные знаки...")

                # Пробуем использовать IOPaint (если доступен)
                iopaint_client = IOPaintClient()
                use_iopaint = iopaint_client.check_availability()

                if use_iopaint:
                    logger.info("   ✅ Используем IOPaint (AI-модель LaMa)")
                    remover = iopaint_client
                else:
                    logger.info("   ⚠️ IOPaint недоступен, используем OpenCV")
                    logger.info("   💡 Для лучшего качества запустите: iopaint start --model=lama --port=8080")
                    remover = WatermarkRemover(method='telea')

                for idx, photo_info in enumerate(all_photos, 1):
                    logger.info(f"      [{idx}/{len(all_photos)}] {photo_info['folder']}/{photo_info['filename']}")

                    try:
                        # Обрабатываем фото
                        if use_iopaint:
                            cleaned_img = remover.process_url(
                                url=photo_info['url'],
                                coverage_percent=25  # IOPaint параметр
                            )
                        else:
                            cleaned_img = remover.process_url(
                                url=photo_info['url'],
                                auto_detect_positions=['bottom-right', 'top-right', 'bottom-left']
                            )

                        if cleaned_img:
                            # Сохраняем в архив
                            img_bytes = io.BytesIO()
                            cleaned_img.save(img_bytes, format='JPEG', quality=95)
                            img_bytes.seek(0)

                            zip_path = f"{photo_info['folder']}/{photo_info['filename']}"
                            zf.writestr(zip_path, img_bytes.read())
                    except Exception as e:
                        logger.error(f"      ❌ Ошибка обработки {photo_info['url']}: {e}")
            else:
                # Просто скачиваем без обработки
                import requests
                logger.info("   📥 Скачиваем фото без обработки...")

                for idx, photo_info in enumerate(all_photos, 1):
                    logger.info(f"      [{idx}/{len(all_photos)}] {photo_info['folder']}/{photo_info['filename']}")

                    try:
                        response = requests.get(photo_info['url'], timeout=10)
                        if response.status_code == 200:
                            zip_path = f"{photo_info['folder']}/{photo_info['filename']}"
                            zf.writestr(zip_path, response.content)
                    except Exception as e:
                        logger.error(f"      ❌ Ошибка загрузки {photo_info['url']}: {e}")

        memory_file.seek(0)

        # Генерируем имя файла
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'cian_photos_{timestamp}.zip'

        logger.info(f"✅ Архив создан: {filename}")

        return send_file(
            memory_file,
            mimetype='application/zip',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        logger.error(f"❌ Ошибка создания архива: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/download_markdown', methods=['GET'])
def download_markdown():
    """Скачать результаты в формате Markdown со ВСЕМИ похожими объявлениями"""
    global last_parse_result

    if not last_parse_result:
        return jsonify({
            'success': False,
            'error': 'Сначала выполните парсинг объявления'
        }), 400

    try:
        logger.info("📝 Создание Markdown файла со ВСЕМИ объявлениями...")

        # Создаем временный файл Markdown
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        temp_filename = f'cian_full_analysis_{timestamp}.md'
        temp_path = os.path.join('/tmp', temp_filename)

        # ВАЖНО: Собираем ВСЕ объявления для анализа рынка
        # 1. Основное объявление
        results = [last_parse_result.copy()]

        # 2. Все похожие объявления как отдельные записи
        similar_listings = last_parse_result.get('similar_listings', [])
        logger.info(f"   📊 Основное объявление: 1")
        logger.info(f"   🏘️ Похожих объявлений: {len(similar_listings)}")
        logger.info(f"   📝 Всего для экспорта: {1 + len(similar_listings)}")

        # Добавляем все похожие как отдельные объявления для детального анализа
        for idx, similar in enumerate(similar_listings, 1):
            # Копируем данные похожего объявления
            similar_copy = similar.copy()

            # Добавляем пометку что это похожее объявление
            similar_copy['_source'] = 'Похожее объявление'
            similar_copy['_original_listing'] = last_parse_result.get('title', 'Основное объявление')

            # Убираем вложенные similar_listings чтобы не дублировать
            if 'similar_listings' in similar_copy:
                del similar_copy['similar_listings']

            results.append(similar_copy)
            logger.info(f"      [{idx}/{len(similar_listings)}] {similar_copy.get('title', 'Без названия')[:60]}...")

        # Экспортируем ВСЕ объявления в Markdown
        save_results_as_markdown(results, temp_path)

        logger.info(f"✅ Markdown создан: {temp_filename}")
        logger.info(f"   📄 Размер файла: {os.path.getsize(temp_path) / 1024:.1f} KB")
        logger.info(f"   📊 Объявлений в файле: {len(results)}")

        # Отправляем файл
        return send_file(
            temp_path,
            mimetype='text/markdown',
            as_attachment=True,
            download_name=temp_filename
        )

    except Exception as e:
        logger.error(f"❌ Ошибка создания Markdown: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/download_txt', methods=['GET'])
def download_txt():
    """Скачать результаты в формате TXT со ВСЕМИ похожими объявлениями"""
    global last_parse_result

    if not last_parse_result:
        return jsonify({
            'success': False,
            'error': 'Сначала выполните парсинг объявления'
        }), 400

    try:
        logger.info("📄 Создание TXT файла со ВСЕМИ объявлениями...")

        # Создаем временный файл TXT
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        temp_filename = f'cian_full_analysis_{timestamp}.txt'
        temp_path = os.path.join('/tmp', temp_filename)

        # ВАЖНО: Собираем ВСЕ объявления для анализа рынка
        # 1. Основное объявление
        results = [last_parse_result.copy()]

        # 2. Все похожие объявления как отдельные записи
        similar_listings = last_parse_result.get('similar_listings', [])
        logger.info(f"   📊 Основное объявление: 1")
        logger.info(f"   🏘️ Похожих объявлений: {len(similar_listings)}")
        logger.info(f"   📝 Всего для экспорта: {1 + len(similar_listings)}")

        # Добавляем все похожие как отдельные объявления для детального анализа
        for idx, similar in enumerate(similar_listings, 1):
            # Копируем данные похожего объявления
            similar_copy = similar.copy()

            # Добавляем пометку что это похожее объявление
            similar_copy['_source'] = 'Похожее объявление'
            similar_copy['_original_listing'] = last_parse_result.get('title', 'Основное объявление')

            # Убираем вложенные similar_listings чтобы не дублировать
            if 'similar_listings' in similar_copy:
                del similar_copy['similar_listings']

            results.append(similar_copy)
            logger.info(f"      [{idx}/{len(similar_listings)}] {similar_copy.get('title', 'Без названия')[:60]}...")

        # Экспортируем ВСЕ объявления в TXT
        save_results_as_txt(results, temp_path)

        logger.info(f"✅ TXT создан: {temp_filename}")
        logger.info(f"   📄 Размер файла: {os.path.getsize(temp_path) / 1024:.1f} KB")
        logger.info(f"   📊 Объявлений в файле: {len(results)}")

        # Отправляем файл
        return send_file(
            temp_path,
            mimetype='text/plain',
            as_attachment=True,
            download_name=temp_filename
        )

    except Exception as e:
        logger.error(f"❌ Ошибка создания TXT: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/health')
def health():
    """Проверка здоровья сервиса"""
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    print("=" * 80)
    print("🚀 Cian Parser - Cian Style Interface")
    print("=" * 80)
    print("\n✨ Возможности:")
    print("  • Интерфейс в стиле Cian.ru")
    print("  • Карточки объявлений с фото")
    print("  • ПОЛНЫЕ данные для ВСЕХ похожих объявлений")
    print("  • Автоматический анализ рынка")
    print("  • Интерактивное раскрытие характеристик")
    print("  • Экспорт в Markdown и TXT")
    print("\n⚠️  ВНИМАНИЕ:")
    print("  Парсинг ВСЕХ похожих с полными данными занимает ~1-2 минуты")
    print("  (10 объявлений × ~6-10 секунд на каждое)")
    print("\nСервер запущен на: http://127.0.0.1:5002")
    print("\nОткройте в браузере и вставьте ссылку на объявление Cian.ru\n")

    app.run(debug=True, host='127.0.0.1', port=5002)
