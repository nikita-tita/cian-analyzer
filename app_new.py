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
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from src.parsers.playwright_parser import PlaywrightParser, detect_region_from_url
    Parser = PlaywrightParser
    logger.info("Using PlaywrightParser")
except Exception as e:
    logger.warning(f"Playwright not available, using SimpleParser: {e}")
    from src.parsers.simple_parser import SimpleParser
    Parser = SimpleParser
    # Fallback для detect_region
    def detect_region_from_url(url):
        return 'spb'

from src.analytics.analyzer import RealEstateAnalyzer
from src.models.property import (
    TargetProperty,
    ComparableProperty,
    AnalysisRequest
)
from src.utils.session_storage import get_session_storage
from src.cache import init_cache, get_cache

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Инициализация Redis кэша
# В продакшене параметры берутся из env переменных
property_cache = init_cache(
    host=os.getenv('REDIS_HOST', 'localhost'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    db=int(os.getenv('REDIS_DB', 0)),
    password=os.getenv('REDIS_PASSWORD'),
    namespace=os.getenv('REDIS_NAMESPACE', 'housler'),
    enabled=os.getenv('REDIS_ENABLED', 'false').lower() == 'true'
)

# Хранилище сессий с поддержкой Redis
session_storage = get_session_storage()

# Rate limiting configuration
# Используем Redis для распределенного rate limiting (если доступен)
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    storage_uri=f"redis://{os.getenv('REDIS_HOST', 'localhost')}:{os.getenv('REDIS_PORT', 6379)}/{os.getenv('REDIS_DB', 0)}" if os.getenv('REDIS_ENABLED', 'false').lower() == 'true' else 'memory://',
    default_limits=["200 per day", "50 per hour"],
    storage_options={"socket_connect_timeout": 30},
    strategy="fixed-window"
)

logger.info(f"Rate limiting initialized: {limiter.storage_uri[:20]}...")


@app.route('/')
def index():
    """Landing page - Agency website"""
    return render_template('index.html')


@app.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint для мониторинга

    Проверяет:
    - Доступность приложения
    - Состояние Redis кэша
    - Состояние session storage
    - Версию приложения

    Returns:
        200 OK если все в порядке
        503 Service Unavailable если есть критичные проблемы
    """
    health_status = {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '2.0.0',  # Версия после улучшений
        'components': {}
    }

    all_healthy = True

    # Проверка кэша
    try:
        cache_health = property_cache.health_check()
        cache_stats = property_cache.get_stats()
        health_status['components']['redis_cache'] = {
            'status': 'healthy' if cache_health else 'degraded',
            'available': cache_health,
            'stats': cache_stats
        }
        if not cache_health and property_cache.enabled:
            # Если кэш должен быть включен, но недоступен - warning, но не critical
            health_status['components']['redis_cache']['status'] = 'degraded'
            health_status['status'] = 'degraded'
    except Exception as e:
        health_status['components']['redis_cache'] = {
            'status': 'unhealthy',
            'error': str(e)
        }
        # Кэш - не критичный компонент
        if health_status['status'] != 'unhealthy':
            health_status['status'] = 'degraded'

    # Проверка session storage
    try:
        # Пробуем записать и прочитать тестовую сессию
        test_session_id = '_health_check_test'
        session_storage.set(test_session_id, {'test': True})
        test_data = session_storage.get(test_session_id)
        session_storage.delete(test_session_id)

        health_status['components']['session_storage'] = {
            'status': 'healthy',
            'type': type(session_storage).__name__
        }
    except Exception as e:
        health_status['components']['session_storage'] = {
            'status': 'unhealthy',
            'error': str(e)
        }
        all_healthy = False
        health_status['status'] = 'unhealthy'

    # Проверка парсера
    try:
        # Просто проверяем, что класс доступен
        parser_name = Parser.__name__
        health_status['components']['parser'] = {
            'status': 'healthy',
            'type': parser_name
        }
    except Exception as e:
        health_status['components']['parser'] = {
            'status': 'unhealthy',
            'error': str(e)
        }
        all_healthy = False
        health_status['status'] = 'unhealthy'

    # Определяем HTTP статус
    if health_status['status'] == 'healthy':
        http_status = 200
    elif health_status['status'] == 'degraded':
        http_status = 200  # Degraded, но работает
    else:
        http_status = 503  # Service Unavailable

    return jsonify(health_status), http_status


@app.route('/metrics', methods=['GET'])
def metrics():
    """
    Prometheus-compatible metrics endpoint

    Returns:
        Метрики в формате Prometheus
    """
    lines = []

    # Базовые метрики
    lines.append('# HELP housler_up Application is running')
    lines.append('# TYPE housler_up gauge')
    lines.append('housler_up 1')

    # Кэш метрики
    try:
        cache_stats = property_cache.get_stats()
        if cache_stats.get('available'):
            lines.append('# HELP housler_cache_hit_rate Cache hit rate percentage')
            lines.append('# TYPE housler_cache_hit_rate gauge')
            lines.append(f"housler_cache_hit_rate {cache_stats.get('hit_rate', 0)}")

            lines.append('# HELP housler_cache_keys_total Total number of cached keys')
            lines.append('# TYPE housler_cache_keys_total gauge')
            lines.append(f"housler_cache_keys_total {cache_stats.get('total_keys', 0)}")
    except:
        pass

    return '\n'.join(lines) + '\n', 200, {'Content-Type': 'text/plain'}


@app.route('/calculator')
def calculator():
    """Property calculator - main analysis tool"""
    return render_template('wizard.html')


@app.route('/api/parse', methods=['POST'])
@limiter.limit("10 per minute")  # Expensive operation - парсинг
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

        # Автоопределение региона
        region = detect_region_from_url(url)
        logger.info(f"Парсинг URL: {url} (регион: {region})")

        # Парсинг через доступный парсер с кэшем и регионом
        with Parser(headless=True, delay=1.0, cache=property_cache, region=region) as parser:
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


@app.route('/api/create-manual', methods=['POST'])
@limiter.limit("10 per minute")
def create_manual():
    """
    API: Создание объекта вручную без парсинга (Экран 1)

    Body:
        {
            "address": "Санкт-Петербург, улица Ленина, 10",
            "price_raw": 15000000,
            "total_area": 75.5,
            "rooms": "2",
            "floor": "5/10",
            "living_area": 55.0,
            "kitchen_area": 12.0,
            "repair_level": "стандартная",
            "view_type": "улица"
        }

    Returns:
        {
            "status": "success",
            "data": {...},
            "session_id": "uuid",
            "missing_fields": []
        }
    """
    try:
        data = request.json

        # Валидация обязательных полей
        required = ['address', 'price_raw', 'total_area', 'rooms']
        missing = [f for f in required if not data.get(f)]
        if missing:
            return jsonify({
                'status': 'error',
                'message': f'Отсутствуют обязательные поля: {", ".join(missing)}'
            }), 400

        # Создаем объект недвижимости
        property_data = {
            'address': data['address'],
            'price_raw': float(data['price_raw']),
            'price': f"{int(data['price_raw']):,} ₽".replace(',', ' '),
            'total_area': float(data['total_area']),
            'area': f"{data['total_area']} м²",
            'rooms': data['rooms'],
            'floor': data.get('floor', ''),
            'living_area': float(data.get('living_area')) if data.get('living_area') else None,
            'kitchen_area': float(data.get('kitchen_area')) if data.get('kitchen_area') else None,
            'repair_level': data.get('repair_level', 'стандартная'),
            'view_type': data.get('view_type', 'улица'),
            'manual_input': True,
            'title': data.get('title', f"{data['rooms']}-комн. квартира, {data['total_area']} м²"),
            'url': None,  # Нет URL при ручном вводе
            'metro': [],
            'residential_complex': None,
            'characteristics': {}
        }

        # Пытаемся определить регион из адреса
        address_lower = data['address'].lower()
        if 'санкт-петербург' in address_lower or 'спб' in address_lower:
            region = 'spb'
        elif 'москва' in address_lower or 'мск' in address_lower:
            region = 'msk'
        else:
            region = 'spb'  # По умолчанию

        property_data['region'] = region

        logger.info(f"Создание объекта вручную: {property_data['address']} (регион: {region})")

        # Определяем недостающие поля (для ручного ввода их меньше)
        missing_fields = _identify_missing_fields(property_data)

        # Создаем сессию
        session_id = str(uuid.uuid4())
        session_storage.set(session_id, {
            'target_property': property_data,
            'comparables': [],
            'created_at': datetime.now().isoformat(),
            'step': 1
        })

        return jsonify({
            'status': 'success',
            'data': property_data,
            'session_id': session_id,
            'missing_fields': missing_fields
        })

    except Exception as e:
        logger.error(f"Ошибка создания вручную: {e}", exc_info=True)
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
@limiter.limit("15 per minute")  # Expensive - поиск и парсинг аналогов
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

        # Определяем регион из URL целевого объекта
        target_url = target.get('url', '')
        region = detect_region_from_url(target_url)
        logger.info(f"Поиск похожих объектов для сессии {session_id} (тип: {search_type}, регион: {region})")

        # Поиск аналогов с кэшем и регионом
        with Parser(headless=True, delay=1.0, cache=property_cache, region=region) as parser:
            if search_type == 'building':
                # Поиск в том же ЖК
                similar = parser.search_similar_in_building(target, limit=limit)
                residential_complex = target.get('residential_complex', 'Неизвестно')
            else:
                # Широкий поиск по городу
                similar = parser.search_similar(target, limit=limit)
                residential_complex = None

        # Если найдено много аналогов с URL, парсим их параллельно
        urls_to_parse = [c.get('url') for c in similar if c.get('url') and not c.get('price_raw')]

        if urls_to_parse:
            try:
                from src.parsers.async_parser import parse_multiple_urls_parallel
                logger.info(f"🚀 Parallel parsing {len(urls_to_parse)} URLs...")

                detailed_results = parse_multiple_urls_parallel(
                    urls=urls_to_parse,
                    headless=True,
                    cache=property_cache,
                    region=region,
                    max_concurrent=5
                )

                # Обновляем данные аналогов детальной информацией
                url_to_details = {d['url']: d for d in detailed_results}
                for comparable in similar:
                    url = comparable.get('url')
                    if url in url_to_details:
                        comparable.update(url_to_details[url])

                logger.info(f"✓ Enhanced {len(detailed_results)} comparables with detailed data")

            except Exception as e:
                logger.warning(f"Parallel parsing failed, using basic data: {e}")

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

        # Определяем регион
        region = detect_region_from_url(url)
        logger.info(f"Добавление аналога: {url} (регион: {region})")

        # Парсим аналог с кэшем и регионом
        with Parser(headless=True, delay=1.0, cache=property_cache, region=region) as parser:
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
@limiter.limit("20 per minute")  # Анализ - менее expensive
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
            # Импортируем утилиты нормализации
            from src.models.property import normalize_property_data, validate_property_consistency

            # Нормализуем целевой объект
            normalized_target = normalize_property_data(session_data['target_property'])
            target_property = TargetProperty(**normalized_target)

            # Проверяем консистентность
            warnings = validate_property_consistency(target_property)
            if warnings:
                logger.warning(f"Предупреждения валидации: {warnings}")

            # Нормализуем аналоги
            comparables = [
                ComparableProperty(**normalize_property_data(c))
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
        try:
            result = analyzer.analyze(request_model)
        except ValueError as ve:
            # Специфичные ошибки валидации (например, мало аналогов)
            logger.warning(f"Ошибка валидации анализа: {ve}")
            return jsonify({
                'status': 'error',
                'error_type': 'validation_error',
                'message': str(ve)
            }), 422

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
            'error_type': 'internal_error',
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


@app.route('/api/cache/stats', methods=['GET'])
def cache_stats():
    """
    API: Статистика кэша

    Returns:
        {
            "status": "success",
            "stats": {
                "status": "active|disabled",
                "hit_rate": 85.5,
                "total_keys": 123,
                ...
            }
        }
    """
    try:
        stats = property_cache.get_stats()
        return jsonify({
            'status': 'success',
            'stats': stats
        })
    except Exception as e:
        logger.error(f"Ошибка получения статистики кэша: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/cache/clear', methods=['POST'])
def cache_clear():
    """
    API: Очистка кэша (для админов)

    Body:
        {
            "pattern": "*"  # optional, default: все
        }

    Returns:
        {
            "status": "success",
            "deleted": 42
        }
    """
    try:
        pattern = request.json.get('pattern', '*') if request.json else '*'
        deleted = property_cache.clear_all(pattern)

        return jsonify({
            'status': 'success',
            'deleted': deleted,
            'pattern': pattern
        })
    except Exception as e:
        logger.error(f"Ошибка очистки кэша: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


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
            'options': ['дом', 'улица', 'парк', 'вода', 'город', 'закат', 'премиум'],
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
