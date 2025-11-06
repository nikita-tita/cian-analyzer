"""
Production-ready веб-интерфейс с Redis, PostgreSQL, кэшированием и мониторингом
Улучшенная версия app_new.py с полной интеграцией новых модулей
"""

from flask import Flask, render_template, request, jsonify
import os
import uuid
from typing import Dict, List
from datetime import datetime
import time

# Загрузка переменных окружения
from dotenv import load_dotenv
load_dotenv()

# Настройка логирования
from src.utils.logger import (
    setup_logging,
    get_logger,
    log_execution_time,
    log_api_call,
    get_metrics,
    monitor
)

# Инициализация логирования
setup_logging(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    log_file=os.getenv('LOG_FILE'),
    json_logs=os.getenv('LOG_JSON', 'false').lower() == 'true',
    colored_console=True
)

logger = get_logger(__name__)

# Storage managers
from src.storage.redis_manager import get_session_manager
from src.storage.postgres_manager import get_postgres_manager
from src.storage.cache_manager import get_cache_manager

# Parsers
from src.parsers.playwright_parser import PlaywrightParser
from src.parsers.async_parser import AsyncCianParser

# Analytics
from src.analytics.analyzer import RealEstateAnalyzer
from src.models.property import (
    TargetProperty,
    ComparableProperty,
    AnalysisRequest
)

# Flask app
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', os.urandom(24))

# ==========================================
# Initialize storage managers
# ==========================================
logger.info("🚀 Initializing storage managers...")

# Redis для сессий
try:
    session_manager = get_session_manager(
        host=os.getenv('REDIS_HOST'),
        port=int(os.getenv('REDIS_PORT', 6379)),
        password=os.getenv('REDIS_PASSWORD'),
        ttl=int(os.getenv('REDIS_TTL', 3600)),
        use_fallback=True  # Fallback на in-memory если Redis недоступен
    )
    logger.info("✅ Redis Session Manager initialized")
except Exception as e:
    logger.warning(f"⚠️ Redis initialization failed, using fallback: {e}")
    session_manager = get_session_manager(use_fallback=True)

# PostgreSQL для исторических данных
postgres_manager = None
try:
    postgres_manager = get_postgres_manager(
        host=os.getenv('POSTGRES_HOST'),
        port=int(os.getenv('POSTGRES_PORT', 5432)),
        database=os.getenv('POSTGRES_DB'),
        user=os.getenv('POSTGRES_USER'),
        password=os.getenv('POSTGRES_PASSWORD')
    )
    logger.info("✅ PostgreSQL Manager initialized")
except Exception as e:
    logger.warning(f"⚠️ PostgreSQL initialization failed: {e}")

# Cache Manager
cache_enabled = os.getenv('CACHE_ENABLED', 'true').lower() == 'true'
if cache_enabled:
    cache_manager = get_cache_manager(
        redis_manager=session_manager,
        postgres_manager=postgres_manager,
        use_memory=True,
        memory_max_size=int(os.getenv('CACHE_MEMORY_MAX_SIZE', 100))
    )
    logger.info("✅ Cache Manager initialized")
else:
    cache_manager = None
    logger.info("ℹ️ Caching disabled")

logger.info("✅ All managers initialized successfully")


# ==========================================
# Routes
# ==========================================

@app.route('/')
def index():
    """Главная страница - Экран 1: Парсинг"""
    logger.info("📄 Main page loaded")
    return render_template('wizard.html')


@app.route('/api/parse', methods=['POST'])
@log_api_call()
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
            "missing_fields": ["field1", "field2"],
            "cached": true/false
        }
    """
    try:
        data = request.json
        url = data.get('url')

        if not url:
            return jsonify({'status': 'error', 'message': 'URL обязателен'}), 400

        logger.info(f"🕷️ Parsing URL: {url}")

        # Проверяем кэш
        cached_data = None
        if cache_manager:
            with monitor('cache_lookup'):
                cached_data = cache_manager.get('property', url)

        if cached_data:
            logger.info(f"💾 Using cached data for: {url}")
            parsed_data = cached_data
            from_cache = True
        else:
            # Парсинг через Playwright
            with monitor('parse_property'):
                with PlaywrightParser(headless=True, delay=1.0) as parser:
                    parsed_data = parser.parse_detail_page(url)

            from_cache = False

            # Сохраняем в кэш
            if cache_manager and parsed_data:
                cache_manager.set(
                    'property',
                    url,
                    parsed_data,
                    ttl=3600,
                    save_to_postgres=True if postgres_manager else False,
                    postgres_ttl_hours=24
                )
                logger.info(f"💾 Cached parsed data for: {url}")

        # Определяем недостающие поля
        missing_fields = _identify_missing_fields(parsed_data)

        # Создаем сессию
        session_id = str(uuid.uuid4())
        session_data = {
            'target_property': parsed_data,
            'comparables': [],
            'created_at': datetime.now().isoformat(),
            'step': 1
        }

        # Сохраняем в Redis/fallback
        session_manager.set(session_id, session_data)

        logger.info(f"✅ Session created: {session_id}")

        return jsonify({
            'status': 'success',
            'data': parsed_data,
            'session_id': session_id,
            'missing_fields': missing_fields,
            'cached': from_cache
        })

    except Exception as e:
        logger.error(f"❌ Parse error: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/update-target', methods=['POST'])
@log_api_call()
def update_target():
    """
    API: Обновление целевого объекта (Экран 1 → 2)
    """
    try:
        payload = request.json
        session_id = payload.get('session_id')
        data = payload.get('data')

        if not session_id:
            return jsonify({'status': 'error', 'message': 'session_id обязателен'}), 400

        # Получаем сессию
        session_data = session_manager.get(session_id)
        if not session_data:
            return jsonify({'status': 'error', 'message': 'Сессия не найдена'}), 404

        # Обновляем данные
        session_data['target_property'].update(data)
        session_data['step'] = 2

        # Сохраняем
        session_manager.update(session_id, session_data)

        logger.info(f"✅ Target updated for session: {session_id}")

        return jsonify({
            'status': 'success',
            'message': 'Данные обновлены'
        })

    except Exception as e:
        logger.error(f"❌ Update error: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/find-similar', methods=['POST'])
@log_api_call()
def find_similar():
    """
    API: Поиск аналогов (Экран 2)

    Использует асинхронный парсер для ускорения
    """
    try:
        payload = request.json
        session_id = payload.get('session_id')
        limit = payload.get('limit', 20)
        search_type = payload.get('search_type', 'building')
        use_async = payload.get('use_async', True)  # Флаг для async парсинга

        if not session_id:
            return jsonify({'status': 'error', 'message': 'session_id обязателен'}), 400

        # Получаем сессию
        session_data = session_manager.get(session_id)
        if not session_data:
            return jsonify({'status': 'error', 'message': 'Сессия не найдена'}), 404

        target = session_data['target_property']

        logger.info(f"🔍 Searching comparables (type={search_type}, async={use_async})")

        with monitor('find_similar'):
            if use_async:
                # Асинхронный парсинг (быстрее)
                import asyncio

                async def async_search():
                    async with AsyncCianParser(
                        headless=True,
                        delay=1.0,
                        max_concurrent=int(os.getenv('ASYNC_MAX_CONCURRENT', 5))
                    ) as parser:
                        if search_type == 'building':
                            # TODO: Implement search_similar_in_building_async
                            return await parser.search_similar_async(target, limit=limit)
                        else:
                            return await parser.search_similar_async(target, limit=limit)

                similar = asyncio.run(async_search())
            else:
                # Синхронный парсинг (оригинальный)
                with PlaywrightParser(headless=True, delay=1.0) as parser:
                    if search_type == 'building':
                        similar = parser.search_similar_in_building(target, limit=limit)
                    else:
                        similar = parser.search_similar(target, limit=limit)

        # Сохраняем в сессию
        session_data['comparables'] = similar
        session_manager.update(session_id, session_data)

        logger.info(f"✅ Found {len(similar)} comparables")

        return jsonify({
            'status': 'success',
            'comparables': similar,
            'count': len(similar),
            'search_type': search_type,
            'residential_complex': target.get('residential_complex', 'Неизвестно')
        })

    except Exception as e:
        logger.error(f"❌ Search error: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/add-comparable', methods=['POST'])
@log_api_call()
def add_comparable():
    """
    API: Добавление аналога по URL (Экран 2)
    """
    try:
        payload = request.json
        session_id = payload.get('session_id')
        url = payload.get('url')

        if not session_id or not url:
            return jsonify({'status': 'error', 'message': 'session_id и url обязательны'}), 400

        # Получаем сессию
        session_data = session_manager.get(session_id)
        if not session_data:
            return jsonify({'status': 'error', 'message': 'Сессия не найдена'}), 404

        logger.info(f"🕷️ Adding comparable: {url}")

        # Проверяем кэш
        cached_data = None
        if cache_manager:
            cached_data = cache_manager.get('property', url)

        if cached_data:
            logger.info(f"💾 Using cached comparable: {url}")
            comparable_data = cached_data
        else:
            # Парсим
            with monitor('parse_comparable'):
                with PlaywrightParser(headless=True, delay=1.0) as parser:
                    comparable_data = parser.parse_detail_page(url)

            # Кэшируем
            if cache_manager and comparable_data:
                cache_manager.set('property', url, comparable_data, ttl=3600)

        # Добавляем в список
        session_data['comparables'].append(comparable_data)
        session_manager.update(session_id, session_data)

        logger.info(f"✅ Comparable added")

        return jsonify({
            'status': 'success',
            'comparable': comparable_data
        })

    except Exception as e:
        logger.error(f"❌ Add comparable error: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/exclude-comparable', methods=['POST'])
@log_api_call()
def exclude_comparable():
    """
    API: Исключение аналога из анализа (Экран 2)
    """
    try:
        payload = request.json
        session_id = payload.get('session_id')
        index = payload.get('index')

        if not session_id or index is None:
            return jsonify({'status': 'error', 'message': 'session_id и index обязательны'}), 400

        # Получаем сессию
        session_data = session_manager.get(session_id)
        if not session_data:
            return jsonify({'status': 'error', 'message': 'Сессия не найдена'}), 404

        comparables = session_data['comparables']

        if 0 <= index < len(comparables):
            comparables[index]['excluded'] = True
            session_manager.update(session_id, session_data)
            logger.info(f"✅ Comparable {index} excluded")

        return jsonify({'status': 'success'})

    except Exception as e:
        logger.error(f"❌ Exclude error: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/analyze', methods=['POST'])
@log_api_call()
def analyze():
    """
    API: Полный анализ (Экран 3)

    Сохраняет результаты в PostgreSQL
    """
    start_time = time.time()

    try:
        payload = request.json
        session_id = payload.get('session_id')
        filter_outliers = payload.get('filter_outliers', True)
        use_median = payload.get('use_median', True)

        if not session_id:
            return jsonify({'status': 'error', 'message': 'session_id обязателен'}), 400

        # Получаем сессию
        session_data = session_manager.get(session_id)
        if not session_data:
            return jsonify({'status': 'error', 'message': 'Сессия не найдена'}), 404

        logger.info(f"📊 Starting analysis for session: {session_id}")

        # Валидация и создание моделей
        try:
            with monitor('model_validation'):
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
            logger.error(f"❌ Validation error: {e}", exc_info=True)
            return jsonify({
                'status': 'error',
                'message': f'Ошибка валидации данных: {e}'
            }), 400

        # Анализ
        with monitor('analysis'):
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
        session_manager.update(session_id, session_data)

        # Сохраняем в PostgreSQL
        if postgres_manager:
            try:
                duration = time.time() - start_time
                metadata = {
                    'user_ip': request.remote_addr,
                    'user_agent': request.headers.get('User-Agent'),
                    'duration_seconds': duration
                }

                with monitor('save_to_postgres'):
                    postgres_manager.save_analysis(
                        session_id=session_id,
                        target_property=session_data['target_property'],
                        analysis_result=result_dict,
                        metadata=metadata
                    )

                logger.info(f"💾 Analysis saved to PostgreSQL")

            except Exception as e:
                logger.error(f"⚠️ Failed to save to PostgreSQL: {e}")

        logger.info(f"✅ Analysis completed in {time.time() - start_time:.2f}s")

        return jsonify({
            'status': 'success',
            'analysis': result_dict
        })

    except Exception as e:
        logger.error(f"❌ Analysis error: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/session/<session_id>', methods=['GET'])
@log_api_call()
def get_session(session_id):
    """
    API: Получение данных сессии
    """
    session_data = session_manager.get(session_id)

    if not session_data:
        return jsonify({'status': 'error', 'message': 'Сессия не найдена'}), 404

    return jsonify({
        'status': 'success',
        'data': session_data
    })


@app.route('/api/metrics', methods=['GET'])
def get_metrics_endpoint():
    """
    API: Получение метрик производительности
    """
    try:
        metrics = get_metrics()
        stats = metrics.get_all_stats()

        # Добавляем статистику storage
        storage_stats = {
            'session_manager': session_manager.get_stats() if session_manager else {},
            'postgres_manager': postgres_manager.get_stats() if postgres_manager else {},
            'cache_manager': cache_manager.get_stats() if cache_manager else {}
        }

        return jsonify({
            'status': 'success',
            'performance_metrics': stats,
            'storage_stats': storage_stats
        })

    except Exception as e:
        logger.error(f"❌ Metrics error: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint для мониторинга
    """
    health_status = {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'services': {
            'redis': session_manager._redis_available if session_manager else False,
            'postgres': postgres_manager is not None,
            'cache': cache_manager is not None
        }
    }

    return jsonify(health_status)


# ==========================================
# Helper functions
# ==========================================

def _identify_missing_fields(parsed_data: Dict) -> List[Dict]:
    """
    Определяет недостающие поля для анализа
    (Копия из app_new.py)
    """
    missing = []

    required_fields = [
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

    characteristics_mapping = {
        'ceiling_height': 'Высота потолков',
        'build_year': 'Год постройки',
        'house_type': 'Тип дома',
        'has_elevator': 'Количество лифтов',
    }

    characteristics = parsed_data.get('characteristics', {})

    for field_info in required_fields:
        field = field_info['field']

        if field in parsed_data and parsed_data[field] is not None:
            continue

        char_key = characteristics_mapping.get(field)
        if char_key and char_key in characteristics:
            continue

        missing.append(field_info)

    return missing


# ==========================================
# Startup
# ==========================================

if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("🚀 Starting Cian Analyzer (Production Mode)")
    logger.info("=" * 60)
    logger.info(f"📊 Redis: {'✅ Connected' if session_manager._redis_available else '⚠️ Fallback mode'}")
    logger.info(f"📊 PostgreSQL: {'✅ Connected' if postgres_manager else '❌ Disabled'}")
    logger.info(f"📊 Cache: {'✅ Enabled' if cache_manager else '❌ Disabled'}")
    logger.info("=" * 60)

    app.run(
        debug=os.getenv('FLASK_DEBUG', 'false').lower() == 'true',
        host='0.0.0.0',
        port=5002
    )
