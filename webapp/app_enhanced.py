"""
Улучшенное Flask веб-приложение для парсинга Cian.ru
С полными данными + похожие объявления + сравнение
"""

from flask import Flask, render_template, request, jsonify
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.cian_parser_breadcrumbs import CianParserBreadcrumbs as CianParserEnhanced
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def format_to_markdown_enhanced(data):
    """
    Улучшенное форматирование с ВСЕ данными + сравнение

    Args:
        data: Словарь с полными данными

    Returns:
        str: Markdown с максимальной информацией
    """

    if data.get('error'):
        return f"""# ❌ Ошибка при парсинге

**URL:** {data.get('url')}

**Ошибка:** {data.get('error')}

Попробуйте еще раз или проверьте URL.
"""

    md = []

    # Заголовок
    md.append(f"# {data.get('title', 'Объявление')}\n\n")

    # Ссылка
    md.append(f"**🔗 URL:** [{data.get('url')}]({data.get('url')})\n\n")

    md.append("---\n\n")

    # ======== ЦЕНА ========
    md.append("## 💰 Цена и стоимость\n\n")

    if data.get('price'):
        md.append(f"### Основная цена\n")
        md.append(f"**{data['price']}**\n\n")

        if data.get('price_raw'):
            md.append(f"- 💵 Числом: **{data['price_raw']:,}** {data.get('currency', 'RUB')}\n".replace(',', ' '))

        if data.get('price_per_sqm'):
            md.append(f"- 📐 За квадратный метр: **{data['price_per_sqm']}**\n")

        md.append("\n")
    else:
        md.append("*Цена не указана*\n\n")

    # ======== ЛОКАЦИЯ ========
    if data.get('address') or data.get('metro'):
        md.append("## 📍 Локация и транспорт\n\n")

        if data.get('address'):
            md.append(f"### Адрес\n")
            md.append(f"**{data['address'].split(chr(10))[0]}**\n\n")

        if data.get('metro') and len(data['metro']) > 0:
            md.append(f"### 🚇 Ближайшие станции метро\n\n")
            metro_stations = list(dict.fromkeys(data['metro']))
            for i, station in enumerate(metro_stations[:7], 1):
                md.append(f"{i}. {station}\n")
            md.append("\n")

    # ======== ВСЕ ХАРАКТЕРИСТИКИ ========
    chars = data.get('characteristics', {})
    if chars:
        md.append("## 📊 Полные характеристики объекта\n\n")

        # Группируем по категориям
        categories = {
            '🏠 Площадь и планировка': [
                'Общая площадь', 'Жилая площадь', 'Площадь кухни',
                'Количество комнат', 'Комнаты', 'Планировка'
            ],
            '🏢 Здание и этаж': [
                'Этаж', 'Этажей в доме', 'Тип дома', 'Год постройки',
                'Материал стен', 'Высота потолков', 'Лифт'
            ],
            '🛠️ Отделка и состояние': [
                'Отделка', 'Ремонт', 'Состояние', 'Мебель', 'Техника'
            ],
            '🚿 Санузел и удобства': [
                'Санузел', 'Ванная', 'Душ', 'Балкон', 'Лоджия'
            ],
            '🚗 Парковка и инфраструктура': [
                'Парковка', 'Гараж', 'Охрана', 'Консьерж', 'Лифт'
            ],
            '🏞️ Вид и окружение': [
                'Вид из окон', 'Окна', 'Сторона', 'Двор'
            ],
        }

        # Сначала выводим категоризированные
        found_keys = set()
        for category, keywords in categories.items():
            category_chars = {}
            for key, value in chars.items():
                for keyword in keywords:
                    if keyword.lower() in key.lower():
                        category_chars[key] = value
                        found_keys.add(key)
                        break

            if category_chars:
                md.append(f"### {category}\n\n")
                for key, value in category_chars.items():
                    md.append(f"- **{key}:** {value}\n")
                md.append("\n")

        # Остальные характеристики
        other_chars = {k: v for k, v in chars.items() if k not in found_keys}
        if other_chars:
            md.append(f"### 📋 Дополнительная информация\n\n")
            for key, value in list(other_chars.items())[:20]:
                md.append(f"- **{key}:** {value}\n")
            md.append("\n")

        md.append(f"**Всего характеристик:** {len(chars)}\n\n")

    # ======== ОПИСАНИЕ ========
    if data.get('description'):
        md.append("## 📄 Описание объявления\n\n")
        desc = data['description'][:2000]
        md.append(f"{desc}\n\n")
        if len(data['description']) > 2000:
            md.append(f"*... и еще {len(data['description']) - 2000} символов*\n\n")

    # ======== ПОХОЖИЕ ОБЪЯВЛЕНИЯ В ДОМЕ ========
    similar = data.get('similar_listings', [])
    if similar:
        md.append("---\n\n")
        md.append(f"## 🏘️ Похожие объявления в доме ({len(similar)} шт)\n\n")
        md.append("*Найдено через навигацию по breadcrumbs*\n\n")

        for i, listing in enumerate(similar[:10], 1):
            md.append(f"### {i}. {listing.get('title', 'Объявление')}\n\n")

            # Основная информация (всегда есть)
            if listing.get('price'):
                md.append(f"💰 **{listing['price']}**\n\n")

            basic_info = []
            if listing.get('area'):
                basic_info.append(f"📐 Площадь: **{listing['area']}**")
            if listing.get('floor'):
                basic_info.append(f"🏢 Этаж: **{listing['floor']}**")

            if basic_info:
                md.append(" • ".join(basic_info) + "\n\n")

            # ПОЛНЫЕ ХАРАКТЕРИСТИКИ (если есть)
            listing_chars = listing.get('characteristics', {})
            if listing_chars and len(listing_chars) > 0:
                md.append("#### 📊 Полные характеристики:\n\n")

                # Группируем по категориям
                categories = {
                    '🏠 Площадь и планировка': [
                        'Общая площадь', 'Жилая площадь', 'Площадь кухни', 'Высота потолков'
                    ],
                    '🏢 Здание': [
                        'Этаж', 'Тип дома', 'Год постройки', 'Тип жилья', 'Строительная серия'
                    ],
                    '🛠️ Удобства': [
                        'Санузел', 'Балкон', 'Лоджия', 'Ремонт', 'Вид из окон', 'Парковка', 'Лифт', 'Количество лифтов'
                    ],
                }

                # Выводим по категориям
                found_keys = set()
                for category, keywords in categories.items():
                    category_items = []
                    for key, value in listing_chars.items():
                        for keyword in keywords:
                            if keyword.lower() in key.lower():
                                category_items.append(f"  - **{key}:** {value}")
                                found_keys.add(key)
                                break

                    if category_items:
                        md.append(f"**{category}**\n")
                        md.append("\n".join(category_items) + "\n\n")

                # Остальные характеристики
                other_items = [f"  - **{k}:** {v}" for k, v in listing_chars.items() if k not in found_keys]
                if other_items:
                    md.append(f"**📋 Дополнительно:**\n")
                    md.append("\n".join(other_items[:10]) + "\n\n")

                md.append(f"*Всего характеристик: {len(listing_chars)}*\n\n")

            # Ссылка
            if listing.get('url'):
                md.append(f"🔗 [Смотреть объявление на Cian.ru]({listing['url']})\n\n")

            md.append("---\n\n")

        if len(similar) > 10:
            md.append(f"*... и еще {len(similar) - 10} объявлений*\n\n")

    # ======== ИСТОРИЯ ПРОДАЖ ========
    sold = data.get('sold_history', [])
    if sold:
        md.append("---\n\n")
        md.append(f"## 📊 История продаж в доме ({len(sold)} шт)\n\n")

        md.append("### Недавно проданные квартиры\n\n")

        for i, listing in enumerate(sold[:5], 1):
            md.append(f"#### {i}. {listing.get('title', 'Квартира')}\n\n")

            if listing.get('price'):
                md.append(f"- 💰 **Цена продажи:** {listing['price']}\n")

            if listing.get('area'):
                md.append(f"- 📐 **Площадь:** {listing['area']}\n")

            if listing.get('date'):
                md.append(f"- 📅 **Дата продажи:** {listing['date']}\n")

            md.append("\n")

        if len(sold) > 5:
            md.append(f"*... и еще {len(sold) - 5} проданных квартир*\n\n")

    # ======== СРАВНЕНИЕ (если есть похожие) ========
    if similar and len(similar) >= 2:
        md.append("---\n\n")
        md.append("## 📊 Сравнение с объявлениями в доме\n\n")

        # Извлекаем цены для сравнения
        prices = []
        for listing in similar:
            price_text = listing.get('price', '')
            # Парсим цену
            import re
            price_match = re.search(r'(\d+[\s\d]*)', price_text.replace(' ', ''))
            if price_match:
                try:
                    price_val = int(price_match.group(1).replace(' ', ''))
                    prices.append(price_val)
                except:
                    pass

        if prices and data.get('price_raw'):
            avg_price = sum(prices) / len(prices)
            min_price = min(prices)
            max_price = max(prices)
            current_price = data['price_raw']

            md.append("### Анализ цен в доме\n\n")
            md.append(f"- 📈 **Ваша цена:** {current_price:,} ₽\n".replace(',', ' '))
            md.append(f"- 📊 **Средняя цена:** {int(avg_price):,} ₽\n".replace(',', ' '))
            md.append(f"- 📉 **Минимум:** {min_price:,} ₽\n".replace(',', ' '))
            md.append(f"- 📈 **Максимум:** {max_price:,} ₽\n".replace(',', ' '))

            # Оценка
            diff_from_avg = ((current_price - avg_price) / avg_price) * 100

            md.append("\n### Вывод\n\n")
            if abs(diff_from_avg) < 5:
                md.append(f"✅ Цена **в среднем диапазоне** для этого дома\n")
            elif diff_from_avg > 0:
                md.append(f"⚠️ Цена **выше среднего** на {abs(diff_from_avg):.1f}%\n")
            else:
                md.append(f"✅ Цена **ниже среднего** на {abs(diff_from_avg):.1f}% (хорошее предложение!)\n")

            md.append("\n")

    # ======== ИЗОБРАЖЕНИЯ ========
    images = data.get('images', [])
    if images:
        md.append("---\n\n")
        md.append(f"## 📷 Фотографии объекта ({len(images)} шт)\n\n")

        for i, img_url in enumerate(images[:8], 1):
            if img_url.startswith('http'):
                md.append(f"![Фото {i}]({img_url})\n\n")

        if len(images) > 8:
            md.append(f"*... и еще {len(images) - 8} фотографий*\n\n")

    # ======== ПРОДАВЕЦ ========
    seller = data.get('seller', {})
    if seller.get('name'):
        md.append("---\n\n")
        md.append("## 👤 Информация о продавце\n\n")
        md.append(f"**{seller['name']}**\n\n")
        if seller.get('type'):
            md.append(f"- Тип: {seller['type']}\n\n")

    # Футер
    md.append("---\n\n")
    md.append("*Данные получены с помощью Cian Parser Enhanced*\n")
    md.append(f"*Похожих объявлений: {len(similar)} | Проданных: {len(sold)}*\n")

    return ''.join(md)


@app.route('/')
def index():
    """Главная страница"""
    return render_template('index.html')


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

        logger.info(f"Полный парсинг URL: {url}")

        # Парсим с breadcrumbs парсером
        with CianParserEnhanced(headless=True) as parser:
            result = parser.parse_detail_page_full(url, get_full_similar=True)

        # Форматируем в улучшенный Markdown
        markdown = format_to_markdown_enhanced(result)

        return jsonify({
            'success': True,
            'markdown': markdown,
            'data': result,
            'stats': {
                'characteristics': len(result.get('characteristics', {})),
                'similar_listings': len(result.get('similar_listings', [])),
                'sold_history': len(result.get('sold_history', [])),
                'images': len(result.get('images', []))
            }
        })

    except Exception as e:
        logger.error(f"Ошибка при парсинге: {e}")
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
    print("🚀 Cian Parser Enhanced Web App")
    print("=" * 80)
    print("\n✨ Возможности:")
    print("  • ВСЕ характеристики объекта")
    print("  • Похожие объявления в доме")
    print("  • История продаж")
    print("  • Автоматическое сравнение цен")
    print("\nСервер запущен на: http://127.0.0.1:5001")
    print("\nОткройте в браузере и вставьте ссылку на объявление Cian.ru\n")

    app.run(debug=True, host='127.0.0.1', port=5001)
