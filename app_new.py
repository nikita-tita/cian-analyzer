"""
Housler - Интеллектуальный анализ недвижимости
Веб-интерфейс с 3-экранным wizard UX
"""

from flask import Flask, render_template, request, jsonify, session
import os
import uuid
import logging
from typing import Dict, List
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from src.parsers.playwright_parser import PlaywrightParser
    Parser = PlaywrightParser
    logger.info("Using PlaywrightParser")
except Exception as e:
    logger.warning(f"Playwright not available, using SimpleParser: {e}")
    from src.parsers.simple_parser import SimpleParser
    Parser = SimpleParser

from src.analytics.analyzer import RealEstateAnalyzer
from src.models.property import (
    TargetProperty,
    ComparableProperty,
    AnalysisRequest
)
from src.utils.session_storage import get_session_storage

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Хранилище сессий с поддержкой Redis
session_storage = get_session_storage()


@app.route('/')
def index():
    """Landing page"""
    return render_template('index.html')


@app.route('/analyze')
def analyze_page():
    """Wizard interface - main analysis tool"""
    return render_template('wizard.html')


@app.route('/api/parse', methods=['POST'])
def parse_url():
    """
    API: Парсинг URL целевого объекта (Экран 1)

    Body:
        {
            "url": "https://www.cian.ru/sale/flat/123/"
        }

    Returns:
        {
            "status": "success",
            "data": {...},
            "session_id": "uuid",
            "missing_fields": ["field1", "field2"]
        }
    """
    try:
        data = request.json
        url = data.get('url')

        if not url:
            return jsonify({'status': 'error', 'message': 'URL обязателен'}), 400

        logger.info(f"Парсинг URL: {url}")

        # Парсинг через доступный парсер
        with Parser(headless=True, delay=1.0) as parser:
            parsed_data = parser.parse_detail_page(url)

        # Определяем недостающие поля для анализа
        missing_fields = _identify_missing_fields(parsed_data)

        # Создаем сессию
        session_id = str(uuid.uuid4())
        session_storage.set(session_id, {
            'target_property': parsed_data,
            'comparables': [],
            'created_at': datetime.now().isoformat(),
            'step': 1
        })

        return jsonify({
            'status': 'success',
            'data': parsed_data,
            'session_id': session_id,
            'missing_fields': missing_fields
        })

    except Exception as e:
        logger.error(f"Ошибка парсинга: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/update-target', methods=['POST'])
def update_target():
    """
    API: Обновление целевого объекта с заполненными полями (Экран 1 → 2)

    Body:
        {
            "session_id": "uuid",
            "data": {
                "has_design": true,
                "ceiling_height": 3.2,
                ...
            }
        }

    Returns:
        {
            "status": "success",
            "message": "Данные обновлены"
        }
    """
    try:
        payload = request.json
        session_id = payload.get('session_id')
        data = payload.get('data')

        if not session_id or not session_storage.exists(session_id):
            return jsonify({'status': 'error', 'message': 'Сессия не найдена'}), 404

        # Обновляем данные
        session_data = session_storage.get(session_id)
        session_data['target_property'].update(data)
        session_data['step'] = 2
        session_storage.set(session_id, session_data)

        return jsonify({
            'status': 'success',
            'message': 'Данные обновлены'
        })

    except Exception as e:
        logger.error(f"Ошибка обновления: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/find-similar', methods=['POST'])
def find_similar():
    """
    API: Автоматический поиск похожих объектов (Экран 2)

    Body:
        {
            "session_id": "uuid",
            "limit": 20,
            "search_type": "building"  // "building" или "city"
        }

    Returns:
        {
            "status": "success",
            "comparables": [...],
            "search_type": "building",
            "residential_complex": "Название ЖК"
        }
    """
    try:
        payload = request.json
        session_id = payload.get('session_id')
        limit = payload.get('limit', 20)
        search_type = payload.get('search_type', 'building')  # По умолчанию ищем в ЖК

        if not session_id or not session_storage.exists(session_id):
            return jsonify({'status': 'error', 'message': 'Сессия не найдена'}), 404

        session_data = session_storage.get(session_id)
        target = session_data['target_property']

        logger.info(f"Поиск похожих объектов для сессии {session_id} (тип: {search_type})")

        # Поиск аналогов
        with Parser(headless=True, delay=1.0) as parser:
            if search_type == 'building':
                # Поиск в том же ЖК
                similar = parser.search_similar_in_building(target, limit=limit)
                residential_complex = target.get('residential_complex', 'Неизвестно')
            else:
                # Широкий поиск по городу
                similar = parser.search_similar(target, limit=limit)
                residential_complex = None

        # Сохраняем в сессию
        session_data['comparables'] = similar
        session_storage.set(session_id, session_data)

        return jsonify({
            'status': 'success',
            'comparables': similar,
            'count': len(similar),
            'search_type': search_type,
            'residential_complex': residential_complex
        })

    except Exception as e:
        logger.error(f"Ошибка поиска: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/add-comparable', methods=['POST'])
def add_comparable():
    """
    API: Добавление аналога по URL (Экран 2)

    Body:
        {
            "session_id": "uuid",
            "url": "https://www.cian.ru/sale/flat/456/"
        }

    Returns:
        {
            "status": "success",
            "comparable": {...}
        }
    """
    try:
        payload = request.json
        session_id = payload.get('session_id')
        url = payload.get('url')

        if not session_id or not session_storage.exists(session_id):
            return jsonify({'status': 'error', 'message': 'Сессия не найдена'}), 404

        logger.info(f"Добавление аналога: {url}")

        # Парсим аналог
        with Parser(headless=True, delay=1.0) as parser:
            comparable_data = parser.parse_detail_page(url)

        # Добавляем в список
        session_data = session_storage.get(session_id)
        session_data['comparables'].append(comparable_data)
        session_storage.set(session_id, session_data)

        return jsonify({
            'status': 'success',
            'comparable': comparable_data
        })

    except Exception as e:
        logger.error(f"Ошибка добавления: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/exclude-comparable', methods=['POST'])
def exclude_comparable():
    """
    API: Исключение аналога из анализа (Экран 2)

    Body:
        {
            "session_id": "uuid",
            "index": 3
        }

    Returns:
        {
            "status": "success"
        }
    """
    try:
        payload = request.json
        session_id = payload.get('session_id')
        index = payload.get('index')

        if not session_id or not session_storage.exists(session_id):
            return jsonify({'status': 'error', 'message': 'Сессия не найдена'}), 404

        session_data = session_storage.get(session_id)
        comparables = session_data['comparables']

        if 0 <= index < len(comparables):
            comparables[index]['excluded'] = True
            session_storage.set(session_id, session_data)

        return jsonify({'status': 'success'})

    except Exception as e:
        logger.error(f"Ошибка исключения: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/analyze', methods=['POST'])
def analyze():
    """
    API: Полный анализ (Экран 3)

    Body:
        {
            "session_id": "uuid",
            "filter_outliers": true,
            "use_median": true
        }

    Returns:
        {
            "status": "success",
            "analysis": {...}
        }
    """
    try:
        payload = request.json
        session_id = payload.get('session_id')
        filter_outliers = payload.get('filter_outliers', True)
        use_median = payload.get('use_median', True)

        if not session_id or not session_storage.exists(session_id):
            return jsonify({'status': 'error', 'message': 'Сессия не найдена'}), 404

        session_data = session_storage.get(session_id)

        logger.info(f"Анализ для сессии {session_id}")

        # Валидация и создание моделей
        try:
            target_property = TargetProperty(**session_data['target_property'])
            comparables = [
                ComparableProperty(**c)
                for c in session_data['comparables']
            ]

            request_model = AnalysisRequest(
                target_property=target_property,
                comparables=comparables,
                filter_outliers=filter_outliers,
                use_median=use_median
            )

        except Exception as e:
            logger.error(f"Ошибка валидации: {e}", exc_info=True)
            return jsonify({
                'status': 'error',
                'message': f'Ошибка валидации данных: {e}'
            }), 400

        # Анализ
        analyzer = RealEstateAnalyzer()
        result = analyzer.analyze(request_model)

        # Конвертируем в JSON
        result_dict = result.dict()

        # Метрики
        metrics = analyzer.get_metrics()
        result_dict['metrics'] = metrics

        # Сохраняем в сессию
        session_data['analysis'] = result_dict
        session_data['step'] = 3
        session_storage.set(session_id, session_data)

        return jsonify({
            'status': 'success',
            'analysis': result_dict
        })

    except Exception as e:
        logger.error(f"Ошибка анализа: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/session/<session_id>', methods=['GET'])
def get_session(session_id):
    """
    API: Получение данных сессии

    Returns:
        {
            "status": "success",
            "data": {...}
        }
    """
    if not session_storage.exists(session_id):
        return jsonify({'status': 'error', 'message': 'Сессия не найдена'}), 404

    return jsonify({
        'status': 'success',
        'data': session_storage.get(session_id)
    })


def _identify_missing_fields(parsed_data: Dict) -> List[Dict]:
    """
    Определяет недостающие поля для анализа

    Returns:
        Список словарей с информацией о недостающих полях
    """
    missing = []

    # ═══════════════════════════════════════════════════════════════════════════
    # НОВАЯ КЛАСТЕРНАЯ СИСТЕМА ПОЛЕЙ (6 кластеров, 20 полей)
    # ═══════════════════════════════════════════════════════════════════════════

    required_fields = [
        # Только важные параметры для сравнения внутри одного дома
        {
            'field': 'repair_level',
            'label': '🎨 Уровень отделки',
            'type': 'select',
            'options': ['черновая', 'стандартная', 'улучшенная', 'премиум', 'люкс'],
            'description': 'Качество отделки (важный фактор цены)',
            'default': 'стандартная'
        },
        {
            'field': 'view_type',
            'label': '🌅 Вид из окна',
            'type': 'select',
            'options': ['худогов', 'дом', 'улица', 'парк', 'вода', 'город', 'закат', 'премиум'],
            'description': 'Что видно из окон (влияет на стоимость)',
            'default': 'улица'
        },
    ]

    # Маппинг полей на характеристики
    characteristics_mapping = {
        'ceiling_height': 'Высота потолков',
        'build_year': 'Год постройки',
        'house_type': 'Тип дома',
        'has_elevator': 'Количество лифтов',
    }

    characteristics = parsed_data.get('characteristics', {})

    for field_info in required_fields:
        field = field_info['field']

        # Проверяем сначала в корне данных
        if field in parsed_data and parsed_data[field] is not None:
            continue

        # Затем проверяем в characteristics
        char_key = characteristics_mapping.get(field)
        if char_key and char_key in characteristics:
            # Поле найдено в characteristics - не добавляем в missing
            continue

        # Поле не найдено - добавляем в missing
        missing.append(field_info)

    return missing


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5002)
