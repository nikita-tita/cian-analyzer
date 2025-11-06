"""
Новый улучшенный веб-интерфейс с 3-экранным UX
"""

from flask import Flask, render_template, request, jsonify, session
import os
import uuid
import logging
from typing import Dict, List
from datetime import datetime

from src.parsers.playwright_parser import PlaywrightParser
from redis_session_manager import RedisSessionManager
from src.analytics.analyzer import RealEstateAnalyzer
from src.models.property import (
    TargetProperty,
    ComparableProperty,
    AnalysisRequest
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Хранилище сессий через Redis
session_manager = RedisSessionManager()

# Middleware для логирования всех запросов
@app.before_request
def log_request():
    worker_id = os.getpid()
    logger.info(f"🌐 [{worker_id}] {request.method} {request.path}")
    if request.is_json:
        body = request.get_json(silent=True)
        if body and 'session_id' in body:
            logger.info(f"🔑 [{worker_id}] Session ID в запросе: {body['session_id']}")

@app.after_request
def log_response(response):
    worker_id = os.getpid()
    logger.info(f"✓ [{worker_id}] {request.path} → {response.status_code}")
    return response

# Логируем запуск приложения
worker_id = os.getpid()
logger.info("=" * 60)
logger.info(f"🚀 Cian Analyzer v2.0 - Railway Production [Worker: {worker_id}]")
logger.info("=" * 60)
logger.info(f"📊 Parser: PlaywrightParser (Full-featured)")
logger.info(f"📊 Cache: Redis (Distributed)")
logger.info(f"📊 Redis Connected: {session_manager.is_redis_connected()}")
logger.info(f"📊 Worker ID: {worker_id}")
logger.info("=" * 60)


@app.route('/')
def index():
    """Главная страница - Экран 1: Парсинг"""
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

        # Парсинг через PlaywrightParser (полноценный парсинг)
        with PlaywrightParser(headless=True, delay=1.0) as parser:
            parsed_data = parser.parse_detail_page(url)

        # Определяем недостающие поля для анализа
        missing_fields = _identify_missing_fields(parsed_data)

        # Создаем сессию в Redis
        session_id = str(uuid.uuid4())
        session_data = {
            'target_property': parsed_data,
            'comparables': [],
            'step': 1
        }

        session_manager.create_session(session_id, session_data, ttl=7200)  # 2 часа

        logger.info(f"✅ Сессия создана: {session_id}")
        logger.info(f"📊 Всего активных сессий: {session_manager.get_all_sessions()}")

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

        logger.info(f"📝 Запрос на обновление сессии: {session_id}")
        logger.info(f"📊 Всего сессий: {session_manager.get_all_sessions()}")

        if not session_id:
            logger.error("❌ Session ID не предоставлен")
            return jsonify({'status': 'error', 'message': 'Session ID обязателен'}), 400

        # Получаем сессию из Redis
        session_data = session_manager.get_session(session_id)

        if not session_data:
            logger.error(f"❌ Сессия {session_id} не найдена в Redis")
            return jsonify({
                'status': 'error',
                'message': f'Сессия не найдена. Возможно время сессии истекло. Попробуйте спарсить объект заново.',
                'debug': {
                    'requested_session': session_id,
                    'total_sessions': session_manager.get_all_sessions()
                }
            }), 404

        # Обновляем данные
        session_data['target_property'].update(data)
        session_data['step'] = 2
        session_manager.update_session(session_id, session_data, ttl=7200)

        logger.info(f"✅ Сессия {session_id} обновлена, переход на шаг 2")

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

        logger.info(f"🔍 Запрос на поиск аналогов для сессии: {session_id}")
        logger.info(f"📊 Всего сессий: {session_manager.get_all_sessions()}")

        session_data = session_manager.get_session(session_id)

        if not session_data:
            logger.error(f"❌ Сессия {session_id} не найдена при поиске аналогов")
            return jsonify({
                'status': 'error',
                'message': 'Сессия не найдена. Попробуйте спарсить объект заново.'
            }), 404

        target = session_data['target_property']

        logger.info(f"✅ Поиск похожих объектов для сессии {session_id} (тип: {search_type})")

        # Поиск аналогов
        with PlaywrightParser(headless=True, delay=1.0) as parser:
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
        session_manager.update_session(session_id, session_data, ttl=7200)

        logger.info(f"✅ Найдено {len(similar)} аналогов для сессии {session_id}")

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

        logger.info(f"➕ Запрос на добавление аналога для сессии: {session_id}")

        session_data = session_manager.get_session(session_id)

        if not session_data:
            logger.error(f"❌ Сессия {session_id} не найдена при добавлении аналога")
            return jsonify({
                'status': 'error',
                'message': 'Сессия не найдена. Попробуйте спарсить объект заново.'
            }), 404

        logger.info(f"✅ Добавление аналога: {url}")

        # Парсим аналог
        with PlaywrightParser(headless=True, delay=1.0) as parser:
            comparable_data = parser.parse_detail_page(url)

        # Добавляем в список
        session_data['comparables'].append(comparable_data)
        session_manager.update_session(session_id, session_data, ttl=7200)

        logger.info(f"✅ Аналог добавлен, всего аналогов: {len(session_data['comparables'])}")

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

        if not session_id or session_id not in sessions_storage:
            return jsonify({'status': 'error', 'message': 'Сессия не найдена'}), 404

        comparables = sessions_storage[session_id]['comparables']

        if 0 <= index < len(comparables):
            comparables[index]['excluded'] = True

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

        logger.info(f"📊 Запрос на анализ для сессии: {session_id}")

        session_data = session_manager.get_session(session_id)

        if not session_data:
            logger.error(f"❌ Сессия {session_id} не найдена при анализе")
            return jsonify({
                'status': 'error',
                'message': 'Сессия не найдена. Попробуйте спарсить объект заново.'
            }), 404

        logger.info(f"✅ Начало анализа для сессии {session_id}")

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
        session_manager.update_session(session_id, session_data, ttl=7200)

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
    logger.info(f"🔍 Проверка сессии: {session_id}")
    logger.info(f"📊 Всего сессий: {session_manager.get_all_sessions()}")

    session_data = session_manager.get_session(session_id)

    if not session_data:
        logger.error(f"❌ Сессия {session_id} не найдена")
        return jsonify({
            'status': 'error',
            'message': 'Сессия не найдена',
            'debug': {
                'requested_session': session_id,
                'total_sessions': session_manager.get_all_sessions()
            }
        }), 404

    logger.info(f"✅ Сессия {session_id} найдена")
    return jsonify({
        'status': 'success',
        'data': session_data
    })


@app.route('/api/health', methods=['GET'])
def health():
    """
    API: Проверка здоровья приложения

    Returns:
        {
            "status": "healthy",
            "sessions": 5,
            "parser": "SimpleParser"
        }
    """
    return jsonify({
        'status': 'healthy',
        'sessions': session_manager.get_all_sessions(),
        'parser': 'PlaywrightParser',
        'redis_connected': session_manager.is_redis_connected(),
        'worker_id': os.getpid()
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
        # Только РУЧНЫЕ поля (автопарсящиеся убраны!)
        {
            'field': 'repair_level',
            'label': '🎨 Уровень отделки',
            'type': 'select',
            'options': ['черновая', 'стандартная', 'улучшенная', 'премиум', 'люкс'],
            'description': 'Качество отделки',
            'default': 'стандартная'
        },
        {
            'field': 'district_type',
            'label': '🏙️ Тип района',
            'type': 'select',
            'options': ['center', 'near_center', 'residential', 'transitional', 'remote'],
            'description': 'Расположение относительно центра',
            'default': 'residential'
        },
        {
            'field': 'surroundings',
            'label': '🌳 Окружение',
            'type': 'multiselect',
            'options': ['парки', 'школы', 'торговля', 'офисы', 'промышленность', 'престиж'],
            'description': 'Что есть рядом',
            'default': []
        },
        {
            'field': 'security_level',
            'label': '🔒 Безопасность',
            'type': 'select',
            'options': ['нет', 'дневная', '24/7', '24/7+консьерж', '24/7+консьерж+видео'],
            'description': 'Система охраны',
            'default': 'нет'
        },
        {
            'field': 'parking_spaces',
            'label': '🚙 Машиномест',
            'type': 'number',
            'description': 'Количество мест',
            'default': 0,
            'min': 0,
            'max': 999
        },
        {
            'field': 'sports_amenities',
            'label': '⚽ Спорт',
            'type': 'multiselect',
            'options': ['детская', 'спортплощадка', 'тренажер', 'бассейн', 'полный'],
            'description': 'Спортивные объекты',
            'default': []
        },
        {
            'field': 'view_type',
            'label': '🌅 Вид из окна',
            'type': 'select',
            'options': ['худогов', 'дом', 'улица', 'парк', 'вода', 'город', 'закат', 'премиум'],
            'description': 'Что видно',
            'default': 'улица'
        },
        {
            'field': 'noise_level',
            'label': '🔇 Уровень шума',
            'type': 'select',
            'options': ['очень_тихо', 'тихо', 'нормально', 'шумно', 'очень_шумно'],
            'description': 'Шумность',
            'default': 'нормально'
        },
        {
            'field': 'crowded_level',
            'label': '👥 Людность',
            'type': 'select',
            'options': ['пустынно', 'спокойно', 'нормально', 'оживленно', 'очень_оживленно'],
            'description': 'Насколько людно',
            'default': 'нормально'
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
