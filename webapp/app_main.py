"""
Flask веб-приложение для анализа недвижимости Cian.ru
Лендинг + Калькулятор + Парсер
"""

from flask import Flask, render_template, request, jsonify, send_from_directory
import sys
import os

# Добавляем путь к парсеру
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.parsers.playwright_parser import PlaywrightParser
import logging

app = Flask(__name__,
            static_folder='static',
            static_url_path='/static')
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def format_to_markdown(data):
    """
    Форматирует данные объявления в Markdown

    Args:
        data: Словарь с данными объявления

    Returns:
        str: Отформатированный Markdown текст
    """

    if data.get('error'):
        return f"""# ❌ Ошибка при парсинге

**URL:** {data.get('url')}

**Ошибка:** {data.get('error')}

Попробуйте еще раз или проверьте URL.
"""

    md = []

    # Заголовок
    md.append(f"# {data.get('title', 'Объявление')}\n")

    # Ссылка
    md.append(f"**🔗 Ссылка:** [{data.get('url')}]({data.get('url')})\n")

    # Разделитель
    md.append("---\n")

    # Цена
    md.append("## 💰 Цена\n")
    if data.get('price'):
        md.append(f"**{data['price']}**\n")
        if data.get('price_raw'):
            md.append(f"- Числом: {data['price_raw']:,} {data.get('currency', 'RUB')}\n".replace(',', ' '))
        if data.get('area') and '₽/м²' in data['area']:
            md.append(f"- {data['area']}\n")
    else:
        md.append("*Цена не указана*\n")

    md.append("\n")

    # Локация
    if data.get('address') or data.get('metro'):
        md.append("## 📍 Локация\n")

        if data.get('address'):
            address = data['address'].split('\n')[0]  # Берем первую строку
            md.append(f"**Адрес:** {address}\n\n")

        if data.get('metro') and len(data['metro']) > 0:
            md.append("**🚇 Метро:**\n")
            # Убираем дубликаты
            metro_stations = list(dict.fromkeys(data['metro']))
            for station in metro_stations[:5]:  # Первые 5 станций
                md.append(f"- {station}\n")
            md.append("\n")

    # Характеристики
    if data.get('area') or data.get('floor') or data.get('rooms'):
        md.append("## 📊 Характеристики\n")

        if data.get('area') and '₽/м²' not in data['area']:
            md.append(f"- **Площадь:** {data['area']}\n")
        if data.get('floor'):
            md.append(f"- **Этаж:** {data['floor']}\n")
        if data.get('rooms'):
            md.append(f"- **Комнаты:** {data['rooms']}\n")

        md.append("\n")

    # Дополнительные характеристики
    chars = data.get('characteristics', {})
    if chars:
        md.append("### Дополнительные характеристики\n")
        for key, value in list(chars.items())[:15]:
            md.append(f"- **{key}:** {value}\n")
        md.append("\n")

    # Описание
    if data.get('description'):
        md.append("## 📄 Описание\n")
        desc = data['description'][:1000]  # Первые 1000 символов
        md.append(f"{desc}\n")
        if len(data['description']) > 1000:
            md.append(f"\n*... и еще {len(data['description']) - 1000} символов*\n")
        md.append("\n")

    # Изображения
    images = data.get('images', [])
    if images:
        md.append(f"## 📷 Изображения ({len(images)} шт)\n")

        # Показываем первые 5 изображений
        for i, img_url in enumerate(images[:5], 1):
            if img_url.startswith('http'):
                md.append(f"![Фото {i}]({img_url})\n\n")

        if len(images) > 5:
            md.append(f"*... и еще {len(images) - 5} изображений*\n\n")

    # Продавец
    seller = data.get('seller', {})
    if seller.get('name'):
        md.append("## 👤 Продавец\n")
        md.append(f"**{seller['name']}**\n")
        if seller.get('type'):
            md.append(f"- Тип: {seller['type']}\n")
        md.append("\n")

    # Футер
    md.append("---\n")
    md.append("*Данные получены с помощью Cian Parser*\n")

    return ''.join(md)


@app.route('/')
def landing():
    """Лендинг страница"""
    return render_template('landing.html')


@app.route('/calculator')
def calculator():
    """Калькулятор-визард для анализа недвижимости"""
    return render_template('calculator.html')


@app.route('/parser')
def parser():
    """Простой парсер объявлений"""
    return render_template('index.html')


@app.route('/parse', methods=['POST'])
def parse():
    """
    API endpoint для парсинга объявления

    Принимает JSON с полем 'url'
    Возвращает Markdown с информацией
    """
    try:
        data = request.get_json()
        url = data.get('url', '').strip()

        if not url:
            return jsonify({
                'success': False,
                'error': 'URL не указан'
            }), 400

        # Проверяем, что это Cian URL
        if 'cian.ru' not in url:
            return jsonify({
                'success': False,
                'error': 'Это не ссылка на Cian.ru'
            }), 400

        logger.info(f"Парсинг URL: {url}")

        # Парсим объявление
        with PlaywrightParser(headless=True, delay=1.0) as parser:
            result = parser.parse_detail_page(url)

        # Форматируем в Markdown
        markdown = format_to_markdown(result)

        return jsonify({
            'success': True,
            'markdown': markdown,
            'data': result
        })

    except Exception as e:
        logger.error(f"Ошибка при парсинге: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/health')
def health():
    """Проверка здоровья сервиса"""
    return jsonify({'status': 'ok'})


# API endpoints для калькулятора
@app.route('/api/parse', methods=['POST'])
def api_parse():
    """API для парсинга объявления (для калькулятора)"""
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

        logger.info(f"API парсинг URL: {url}")

        # Парсим объявление
        with PlaywrightParser(headless=True, delay=1.0) as parser:
            result = parser.parse_detail_page(url)

        return jsonify({
            'success': True,
            'data': result
        })

    except Exception as e:
        logger.error(f"Ошибка при парсинге: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    """API для анализа недвижимости"""
    try:
        data = request.get_json()
        # TODO: Реализовать полный анализ с аналогами

        return jsonify({
            'success': True,
            'message': 'Анализ пока в разработке'
        })

    except Exception as e:
        logger.error(f"Ошибка при анализе: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 8080))
    use_ssl = os.environ.get('USE_SSL', 'false').lower() == 'true'

    # Определяем протокол
    protocol = 'https' if use_ssl else 'http'

    print("=" * 80)
    print("🚀 Cian Analyzer - Умный анализ недвижимости")
    print("=" * 80)
    print(f"\n📍 Сервер запущен на: {protocol}://0.0.0.0:{port}")
    print("\n📄 Доступные страницы:")
    print(f"   • {protocol}://0.0.0.0:{port}/          - Лендинг")
    print(f"   • {protocol}://0.0.0.0:{port}/calculator - Калькулятор")
    print(f"   • {protocol}://0.0.0.0:{port}/parser     - Простой парсер")
    print("\n")

    # Настройка SSL
    if use_ssl:
        cert_path = os.path.join(os.path.dirname(__file__), 'cert.pem')
        key_path = os.path.join(os.path.dirname(__file__), 'key.pem')

        if os.path.exists(cert_path) and os.path.exists(key_path):
            print("🔒 HTTPS включен (самоподписанный сертификат)")
            print("   Браузер покажет предупреждение - это нормально для разработки\n")
            app.run(debug=True, host='0.0.0.0', port=port, ssl_context=(cert_path, key_path))
        else:
            print("⚠️  SSL сертификаты не найдены, запускаем без HTTPS\n")
            app.run(debug=True, host='0.0.0.0', port=port)
    else:
        app.run(debug=True, host='0.0.0.0', port=port)
