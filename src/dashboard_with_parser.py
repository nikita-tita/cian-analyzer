"""
Веб-дашборд с интеграцией парсера Cian
Автоматическое заполнение данных из объявления
"""

from flask import Flask, render_template, request, jsonify
from typing import Dict, List, Optional
import statistics
import math
from datetime import datetime
import re

# Импортируем парсер
from cian_parser import CianParser

# Импортируем улучшенный анализатор
import sys
sys.path.append('.')
from web_dashboard import RealEstateAnalyzer

app = Flask(__name__)


class CianDataMapper:
    """
    Маппер данных из парсера Cian в формат дашборда

    Преобразует данные парсинга в структуру для анализатора
    """

    @staticmethod
    def parse_price(price_str: str) -> Optional[float]:
        """
        Парсинг цены из строки

        Examples:
            "195 000 000 ₽" -> 195000000
            "180 млн ₽" -> 180000000
        """
        if not price_str:
            return None

        # Убираем все пробелы и валюту
        clean_price = price_str.replace(' ', '').replace('₽', '').replace(',', '')

        # Проверяем на "млн"
        if 'млн' in clean_price.lower():
            try:
                num = float(clean_price.lower().replace('млн', ''))
                return num * 1_000_000
            except:
                pass

        # Обычное число
        try:
            return float(clean_price)
        except:
            return None

    @staticmethod
    def parse_area(area_str: str) -> Optional[float]:
        """
        Парсинг площади из строки

        Examples:
            "180.4 м²" -> 180.4
            "180,4 м²" -> 180.4
        """
        if not area_str:
            return None

        clean = area_str.replace('м²', '').replace('м', '').replace(',', '.').strip()

        try:
            return float(clean)
        except:
            return None

    @staticmethod
    def parse_floor(floor_str: str) -> tuple:
        """
        Парсинг этажа

        Examples:
            "6/7" -> (6, 7)
            "6 из 7" -> (6, 7)
        """
        if not floor_str:
            return (None, None)

        # Варианты: "6/7", "6 из 7", "6-й этаж из 7"
        match = re.search(r'(\d+)\D+(\d+)', floor_str)
        if match:
            return (int(match.group(1)), int(match.group(2)))

        return (None, None)

    @staticmethod
    def parse_rooms(title: str) -> Optional[int]:
        """
        Определение количества комнат из заголовка

        Examples:
            "3-комн. квартира" -> 3
            "Квартира-студия" -> 0
        """
        if not title:
            return None

        # Студия
        if 'студ' in title.lower():
            return 0

        # N-комн
        match = re.search(r'(\d+)-комн', title)
        if match:
            return int(match.group(1))

        return None

    @staticmethod
    def detect_design_quality(description: str, title: str) -> bool:
        """
        Определение наличия дизайнерского ремонта

        Ключевые слова: дизайн, авторск, премиум, элитн, де-люкс
        """
        text = (description or '') + ' ' + (title or '')
        text = text.lower()

        design_keywords = [
            'дизайн', 'авторск', 'премиум', 'элитн',
            'де-люкс', 'deluxe', 'эксклюзив', 'индивидуальн'
        ]

        return any(keyword in text for keyword in design_keywords)

    @staticmethod
    def detect_panoramic_views(description: str, title: str) -> bool:
        """Определение панорамных видов"""
        text = (description or '') + ' ' + (title or '')
        text = text.lower()

        view_keywords = [
            'панорам', 'вид на воду', 'вид на залив', 'вид на реку',
            'на воду', 'на море', 'на парк', 'прекрасный вид'
        ]

        return any(keyword in text for keyword in view_keywords)

    @staticmethod
    def detect_premium_location(address: str) -> bool:
        """Определение премиум локации"""
        if not address:
            return False

        address_lower = address.lower()

        premium_areas = [
            'петровск', 'крестовск', 'каменный остров',
            'центр', 'невский', 'литейный', 'дворцов',
            'петроградск', 'васильевск'
        ]

        return any(area in address_lower for area in premium_areas)

    @staticmethod
    def parse_metro_distance(metro_info) -> Optional[int]:
        """
        Парсинг расстояния до метро

        Args:
            metro_info: Строка или список станций метро

        Examples:
            "7 мин пешком" -> 7
            "10 минут" -> 10
            ["Площадь Восстания • 7 мин"] -> 7
        """
        if not metro_info:
            return None

        # Если список, берем первую станцию
        if isinstance(metro_info, list):
            if not metro_info:
                return None
            metro_info = metro_info[0]

        # Парсим строку
        if isinstance(metro_info, str):
            match = re.search(r'(\d+)\s*мин', metro_info)
            if match:
                return int(match.group(1))

        return None

    @staticmethod
    def detect_renders(description: str) -> bool:
        """Определение, что на фото только рендеры"""
        if not description:
            return False

        text = description.lower()

        render_keywords = [
            'рендер', 'визуализац', 'проект', 'планируется',
            'будет завершен', 'окончание ремонта', 'сдача'
        ]

        return any(keyword in text for keyword in render_keywords)

    @classmethod
    def map_to_target_property(cls, parsed_data: Dict) -> Dict:
        """
        Преобразование данных парсинга в формат дашборда

        Args:
            parsed_data: Данные из CianParser

        Returns:
            Словарь для RealEstateAnalyzer
        """
        title = parsed_data.get('title', '')
        description = parsed_data.get('description', '')
        address = parsed_data.get('address', '')

        # Парсим основные данные
        price = cls.parse_price(parsed_data.get('price'))
        total_area = cls.parse_area(parsed_data.get('area'))
        rooms = cls.parse_rooms(title)
        current_floor, total_floors = cls.parse_floor(parsed_data.get('floor'))

        # Определяем характеристики
        has_design = cls.detect_design_quality(description, title)
        panoramic_views = cls.detect_panoramic_views(description, title)
        premium_location = cls.detect_premium_location(address)
        renders_only = cls.detect_renders(description)
        metro_distance = cls.parse_metro_distance(parsed_data.get('metro', ''))

        # Формируем объект
        target = {
            'price': price,
            'total_area': total_area,
            'rooms': rooms,
            'floor': parsed_data.get('floor'),
            'current_floor': current_floor,
            'total_floors': total_floors,
            'has_design': has_design,
            'panoramic_views': panoramic_views,
            'premium_location': premium_location,
            'renders_only': renders_only,
            'metro_distance_min': metro_distance,

            # Дополнительная информация
            'title': title,
            'description': description,
            'address': address,
            'url': parsed_data.get('url'),
            'images': parsed_data.get('images', []),

            # Параметры по умолчанию (пользователь может уточнить)
            'living_area': None,  # Нужно уточнить
            'build_year': 2020,   # Нужно уточнить
            'house_type': 'монолит',  # По умолчанию для премиума
            'parking': 'подземная' if premium_location else 'нет',
            'ceiling_height': 3.0 if has_design else 2.7,
            'security_247': premium_location,
            'has_elevator': True if total_floors and total_floors > 5 else False
        }

        # Убираем None значения
        return {k: v for k, v in target.items() if v is not None}


@app.route('/')
def index():
    """Главная страница с интеграцией парсера"""
    return render_template('dashboard_with_parser.html')


@app.route('/api/parse-cian', methods=['POST'])
def parse_cian_url():
    """
    Парсинг объявления Cian по URL

    POST data:
        {
            "url": "https://www.cian.ru/sale/flat/123456/"
        }

    Returns:
        {
            "success": true,
            "target_property": {...},
            "missing_fields": ["living_area", ...]
        }
    """
    data = request.json
    url = data.get('url')

    if not url:
        return jsonify({
            'success': False,
            'error': 'URL не указан'
        }), 400

    try:
        # Инициализируем парсер
        parser = CianParser(delay=1.0)

        # Парсим объявление
        parsed_data = parser.parse_detail_page(url)

        if not parsed_data:
            return jsonify({
                'success': False,
                'error': 'Не удалось спарсить объявление'
            }), 400

        # Преобразуем в формат дашборда
        mapper = CianDataMapper()
        target_property = mapper.map_to_target_property(parsed_data)

        # Определяем недостающие поля
        required_fields = {
            'price': 'Цена',
            'total_area': 'Общая площадь',
            'living_area': 'Жилая площадь',
            'rooms': 'Количество комнат',
            'build_year': 'Год постройки'
        }

        missing_fields = []
        for field, label in required_fields.items():
            if field not in target_property or target_property[field] is None:
                missing_fields.append({
                    'field': field,
                    'label': label
                })

        return jsonify({
            'success': True,
            'target_property': target_property,
            'missing_fields': missing_fields,
            'parsed_data': parsed_data  # Для отладки
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Ошибка парсинга: {str(e)}'
        }), 500


@app.route('/api/analyze-with-parser', methods=['POST'])
def analyze_with_parser():
    """
    Полный анализ с парсингом

    POST data:
        {
            "url": "https://www.cian.ru/...",
            "additional_params": {
                "living_area": 40.2,
                "build_year": 2022
            },
            "comparables": [...]
        }
    """
    data = request.json
    url = data.get('url')
    additional_params = data.get('additional_params', {})
    comparables = data.get('comparables', [])

    # 1. Парсим целевой объект
    parser = CianParser(delay=1.0)
    parsed_data = parser.parse_listing_page(url)

    if not parsed_data:
        return jsonify({
            'success': False,
            'error': 'Не удалось спарсить объявление'
        }), 400

    # 2. Преобразуем в формат дашборда
    mapper = CianDataMapper()
    target_property = mapper.map_to_target_property(parsed_data)

    # 3. Дополняем пользовательскими параметрами
    target_property.update(additional_params)

    # 4. Запускаем анализ
    analyzer = RealEstateAnalyzer()
    analyzer.set_target_property(target_property)

    for comp in comparables:
        analyzer.add_comparable(comp)

    # Выполняем расчеты
    market_stats = analyzer.calculate_market_statistics()
    fair_price = analyzer.calculate_fair_price()
    scenarios = analyzer.generate_price_scenarios()
    strengths_weaknesses = analyzer.calculate_strengths_weaknesses()
    comparison_chart = analyzer.generate_comparison_chart_data()
    box_plot = analyzer.generate_box_plot_data()

    return jsonify({
        'success': True,
        'market_statistics': market_stats,
        'fair_price_analysis': fair_price,
        'price_scenarios': scenarios,
        'strengths_weaknesses': strengths_weaknesses,
        'comparison_chart_data': comparison_chart,
        'box_plot_data': box_plot,
        'target_property': analyzer.target_property,
        'parsed_data': parsed_data,
        'version': 'enhanced_v2.0_with_parser'
    })


@app.route('/api/parse-comparables', methods=['POST'])
def parse_comparables():
    """
    Парсинг аналогов из поиска Cian

    POST data:
        {
            "search_url": "https://www.cian.ru/cat.php?...",
            "limit": 10
        }

    Returns:
        {
            "success": true,
            "comparables": [...]
        }
    """
    data = request.json
    search_url = data.get('search_url')
    limit = data.get('limit', 10)

    try:
        parser = CianParser(delay=1.0)

        # Парсим список
        listings = parser.parse_search_page(search_url)

        if not listings:
            return jsonify({
                'success': False,
                'error': 'Не удалось спарсить аналоги'
            }), 400

        # Преобразуем в формат дашборда
        mapper = CianDataMapper()
        comparables = []

        for listing in listings[:limit]:
            comp = mapper.map_to_target_property(listing)
            # Добавляем price_per_sqm
            if comp.get('price') and comp.get('total_area'):
                comp['price_per_sqm'] = comp['price'] / comp['total_area']
            comparables.append(comp)

        return jsonify({
            'success': True,
            'comparables': comparables,
            'count': len(comparables)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Ошибка парсинга аналогов: {str(e)}'
        }), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5002)  # Порт 5002 для интеграции
