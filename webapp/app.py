"""
Flask веб-приложение для парсинга Cian.ru
Вставляете ссылку - получаете Markdown с информацией
"""

from flask import Flask, render_template, request, jsonify
import sys
import os

# Добавляем путь к парсеру
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.cian_parser_enhanced import CianParserEnhanced
import logging

app = Flask(__name__)
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
def index():
    """Главная страница"""
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
        with CianParserPlaywright(headless=True, delay=1.0) as parser:
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


if __name__ == '__main__':
    print("=" * 80)
    print("🚀 Cian Parser Web App")
    print("=" * 80)
    print("\nСервер запущен на: http://127.0.0.1:5000")
    print("\nОткройте в браузере и вставьте ссылку на объявление Cian.ru\n")

    app.run(debug=True, host='127.0.0.1', port=5000)
