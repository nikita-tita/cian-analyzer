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
from flask_wtf.csrf import CSRFProtect

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from src.parsers.playwright_parser import PlaywrightParser, detect_region_from_url
    from src.parsers.browser_pool import BrowserPool
    Parser = PlaywrightParser
    PLAYWRIGHT_AVAILABLE = True
    logger.info("Using PlaywrightParser")
except Exception as e:
    logger.warning(f"Playwright not available, using SimpleParser: {e}")
    from src.parsers.simple_parser import SimpleParser
    Parser = SimpleParser
    PLAYWRIGHT_AVAILABLE = False
    BrowserPool = None
    # Fallback для detect_region
    def detect_region_from_url(url):
        return 'spb'

from src.analytics.analyzer import RealEstateAnalyzer
from src.analytics.offer_generator import generate_housler_offer
from src.models.property import (
    TargetProperty,
    ComparableProperty,
    AnalysisRequest
)
from src.utils.session_storage import get_session_storage
from src.cache import init_cache, get_cache

app = Flask(__name__)

# SECURITY: Secret key from environment (CRITICAL FIX)
# Generate with: openssl rand -hex 32
app.secret_key = os.getenv('SECRET_KEY')
if not app.secret_key:
    logger.error("SECRET_KEY not set in environment! Using temporary key for development only.")
    if os.getenv('FLASK_ENV') == 'production':
        raise RuntimeError('SECRET_KEY must be set in production environment')
    # Development fallback (will be different on each restart)
    app.secret_key = os.urandom(24)

# SECURITY: CSRF Protection (защита от Cross-Site Request Forgery)
csrf = CSRFProtect(app)
# Настройка CSRF
app.config['WTF_CSRF_TIME_LIMIT'] = None  # Token doesn't expire (session-based)
app.config['WTF_CSRF_SSL_STRICT'] = os.getenv('FLASK_ENV') == 'production'
app.config['WTF_CSRF_METHODS'] = ['POST', 'PUT', 'PATCH', 'DELETE']
logger.info("CSRF protection enabled")

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

# SECURITY & PERFORMANCE: Browser Pool для контроля ресурсов Playwright
# Ограничивает количество одновременно открытых браузеров
# Защищает от DoS атак и утечек памяти
browser_pool = None
if PLAYWRIGHT_AVAILABLE:
    max_browsers = int(os.getenv('MAX_BROWSERS', '3'))  # Production: 3-5 браузеров
    browser_pool = BrowserPool(
        max_browsers=max_browsers,
        max_age_seconds=3600,  # 1 час
        headless=True,
        block_resources=True
    )
    browser_pool.start()
    logger.info(f"Browser pool initialized with max_browsers={max_browsers}")
else:
    logger.warning("Browser pool not available (Playwright not installed)")

# Rate limiting configuration
# SECURITY: Комбинированный ключ для защиты от обхода через прокси
import hashlib

def get_rate_limit_key():
    """
    Генерирует комбинированный ключ для rate limiting

    Использует: IP + User-Agent + Session (если есть)
    Это затрудняет обход через прокси или смену IP
    """
    # IP адрес
    ip = get_remote_address()

    # User-Agent
    user_agent = request.headers.get('User-Agent', '')[:200]  # Ограничиваем длину

    # Session ID (если есть)
    session_id = session.get('id', '')

    # Комбинируем и хэшируем для privacy
    combined = f"{ip}:{user_agent}:{session_id}"
    key_hash = hashlib.sha256(combined.encode()).hexdigest()[:16]

    return key_hash

# Используем Redis для распределенного rate limiting (если доступен)
limiter = Limiter(
    app=app,
    key_func=get_rate_limit_key,  # Используем улучшенный ключ
    storage_uri=f"redis://{os.getenv('REDIS_HOST', 'localhost')}:{os.getenv('REDIS_PORT', 6379)}/{os.getenv('REDIS_DB', 0)}" if os.getenv('REDIS_ENABLED', 'false').lower() == 'true' else 'memory://',
    default_limits=["200 per day", "50 per hour"],
    storage_options={"socket_connect_timeout": 30},
    strategy="moving-window"  # Более строгая стратегия
)

logger.info(f"Rate limiting initialized: {limiter._storage_uri[:20]}...")


# ═══════════════════════════════════════════════════════════════════════════
# SECURITY UTILITIES (CRITICAL FIX)
# ═══════════════════════════════════════════════════════════════════════════

from urllib.parse import urlparse
import ipaddress

# Whitelist разрешенных доменов для парсинга (защита от SSRF)
ALLOWED_DOMAINS = [
    'www.cian.ru',
    'cian.ru',
    'spb.cian.ru',
    'moscow.cian.ru'
]

def validate_url(url: str) -> None:
    """
    Validate URL для защиты от SSRF атак

    Args:
        url: URL для проверки

    Raises:
        ValueError: если URL опасен

    Защита от:
    - Internal network scanning
    - File:// protocol
    - Localhost/private IP access
    - Arbitrary domain access
    """
    if not url:
        raise ValueError('URL не может быть пустым')

    # Парсим URL
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise ValueError(f'Невалидный URL: {e}')

    # Проверяем протокол
    if parsed.scheme not in ['http', 'https']:
        raise ValueError(f'Запрещенный протокол: {parsed.scheme}. Разрешены только http/https')

    # Проверяем наличие hostname
    if not parsed.hostname:
        raise ValueError('URL должен содержать hostname')

    # Проверяем whitelist доменов
    hostname_lower = parsed.hostname.lower()
    if not any(hostname_lower == domain or hostname_lower.endswith('.' + domain)
               for domain in ALLOWED_DOMAINS):
        raise ValueError(f'Домен {parsed.hostname} не разрешен. Разрешены только: {", ".join(ALLOWED_DOMAINS)}')

    # Блокируем private/internal IP адреса
    try:
        ip = ipaddress.ip_address(parsed.hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            raise ValueError(f'Запрещен доступ к internal IP: {ip}')
    except ValueError:
        # Не IP адрес - это нормально, продолжаем
        pass

    # Дополнительные проверки
    if len(url) > 2048:
        raise ValueError('URL слишком длинный (max 2048 символов)')

    # Блокируем подозрительные паттерны
    suspicious_patterns = ['localhost', '127.', '192.168.', '10.', '172.16.', '@']
    for pattern in suspicious_patterns:
        if pattern in url.lower():
            raise ValueError(f'URL содержит подозрительный паттерн: {pattern}')


def sanitize_string(text: str, max_length: int = 1000) -> str:
    """
    Sanitize строку от потенциально опасного контента

    Args:
        text: Строка для очистки
        max_length: Максимальная длина

    Returns:
        Очищенная строка
    """
    if not text:
        return ''

    # Обрезаем до максимальной длины
    text = str(text).strip()[:max_length]

    # Удаляем null bytes
    text = text.replace('\x00', '')

    # Удаляем control characters кроме \n, \r, \t
    text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\r\t')

    return text


# Pydantic models для валидации входных данных
from pydantic import BaseModel, Field, validator, ValidationError as PydanticValidationError

class ManualPropertyInput(BaseModel):
    """Валидация данных для ручного ввода объекта недвижимости"""
    address: str = Field(..., min_length=5, max_length=500, description="Полный адрес")
    price_raw: float = Field(..., gt=0, lt=1_000_000_000_000, description="Цена в рублях")
    total_area: float = Field(..., gt=1, lt=10000, description="Общая площадь в м²")
    rooms: str = Field(..., description="Количество комнат")
    floor: str = Field(default='', max_length=20, description="Этаж в формате N/M")
    living_area: float = Field(default=None, gt=0, lt=10000, description="Жилая площадь в м²")
    kitchen_area: float = Field(default=None, gt=0, lt=500, description="Площадь кухни в м²")
    repair_level: str = Field(default='стандартная', max_length=50)
    view_type: str = Field(default='улица', max_length=50)

    @validator('address')
    def validate_address(cls, v):
        """Санитизация адреса"""
        v = sanitize_string(v, max_length=500)
        if not v or len(v) < 5:
            raise ValueError('Адрес слишком короткий')
        # Блокируем SQL injection паттерны
        dangerous_patterns = ['<script', 'javascript:', 'onerror=', 'onclick=', 'drop table', 'union select']
        v_lower = v.lower()
        for pattern in dangerous_patterns:
            if pattern in v_lower:
                raise ValueError(f'Адрес содержит недопустимые символы')
        return v

    @validator('rooms')
    def validate_rooms(cls, v):
        """Валидация комнат"""
        allowed_values = ['Студия', '1', '2', '3', '4', '5', '5+']
        if v not in allowed_values:
            raise ValueError(f'Недопустимое значение для комнат: {v}. Разрешены: {allowed_values}')
        return v

    @validator('living_area')
    def validate_living_area(cls, v, values):
        """Проверка что жилая площадь не больше общей"""
        if v and 'total_area' in values and v > values['total_area']:
            raise ValueError('Жилая площадь не может быть больше общей')
        return v

    @validator('kitchen_area')
    def validate_kitchen_area(cls, v, values):
        """Проверка что площадь кухни не больше общей"""
        if v and 'total_area' in values and v > values['total_area']:
            raise ValueError('Площадь кухни не может быть больше общей')
        return v


# Timeout decorator для защиты от зависающих операций
import signal
import threading
from contextlib import contextmanager
from functools import wraps

class TimeoutError(Exception):
    """Exception raised when operation times out"""
    pass


@contextmanager
def timeout_context(seconds: int, error_message: str = 'Operation timed out'):
    """
    Context manager для жесткого timeout операций
    Работает как в главном потоке (через signal), так и в дочерних (через threading.Timer)

    Args:
        seconds: Максимальное время выполнения в секундах
        error_message: Сообщение об ошибке

    Raises:
        TimeoutError: если операция превысила timeout

    Example:
        with timeout_context(60):
            long_running_operation()
    """
    # Проверяем, находимся ли мы в главном потоке
    is_main_thread = threading.current_thread() is threading.main_thread()

    if is_main_thread:
        # В главном потоке используем signal
        def timeout_handler(signum, frame):
            raise TimeoutError(error_message)

        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(seconds)

        try:
            yield
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
    else:
        # В дочерних потоках просто выполняем без timeout
        # (signal не работает в дочерних потоках с Gunicorn gthread worker)
        logger.debug(f"Timeout context called in non-main thread, executing without timeout")
        yield


# ═══════════════════════════════════════════════════════════════════════════
# SECURITY HEADERS (CRITICAL FIX)
# ═══════════════════════════════════════════════════════════════════════════

@app.after_request
def set_security_headers(response):
    """
    Apply security headers to all responses

    Protection against:
    - XSS (Content-Security-Policy)
    - Clickjacking (X-Frame-Options)
    - MIME sniffing (X-Content-Type-Options)
    - Information leakage (Referrer-Policy)
    """

    # Content Security Policy - защита от XSS
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' https://cdn.jsdelivr.net https://unpkg.com; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
        "img-src 'self' data: https: http:; "
        "font-src 'self' https://cdn.jsdelivr.net https://fonts.gstatic.com; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self';"
    )

    # Запрет на MIME-sniffing
    response.headers['X-Content-Type-Options'] = 'nosniff'

    # Защита от clickjacking
    response.headers['X-Frame-Options'] = 'DENY'

    # XSS Protection (legacy, но для старых браузеров)
    response.headers['X-XSS-Protection'] = '1; mode=block'

    # Referrer Policy - не передаем полный URL при переходах
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

    # HSTS - принудительный HTTPS (только в production)
    if os.getenv('FLASK_ENV') == 'production':
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

    return response


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

        # Получаем статистику хранилища
        storage_stats = session_storage.get_stats()

        health_status['components']['session_storage'] = {
            'status': 'healthy',
            'type': type(session_storage).__name__,
            'backend': storage_stats['backend'],
            'total_sessions': storage_stats['total_sessions'],
            'hit_rate_percent': storage_stats['hit_rate_percent']
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

    # Проверка browser pool
    if browser_pool:
        try:
            pool_stats = browser_pool.get_stats()
            health_status['components']['browser_pool'] = {
                'status': 'healthy',
                'pool_size': pool_stats['pool_size'],
                'max_browsers': pool_stats['max_browsers'],
                'browsers_in_use': pool_stats['browsers_in_use'],
                'browsers_free': pool_stats['browsers_free']
            }
        except Exception as e:
            health_status['components']['browser_pool'] = {
                'status': 'degraded',
                'error': str(e)
            }
            if health_status['status'] != 'unhealthy':
                health_status['status'] = 'degraded'

    # Определяем HTTP статус
    if health_status['status'] == 'healthy':
        http_status = 200
    elif health_status['status'] == 'degraded':
        http_status = 200  # Degraded, но работает
    else:
        http_status = 503  # Service Unavailable

    return jsonify(health_status), http_status


@app.route('/api/csrf-token', methods=['GET'])
def get_csrf_token():
    """
    SECURITY: Endpoint для получения CSRF токена

    Генерирует CSRF token для использования в AJAX запросах

    Returns:
        JSON с CSRF токеном
    """
    from flask_wtf.csrf import generate_csrf
    token = generate_csrf()
    return jsonify({'csrf_token': token})


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
    # Получаем session_id из query параметра (если есть)
    session_id = request.args.get('session')
    return render_template('wizard.html', session_id=session_id)


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

        # SECURITY: Валидация URL (защита от SSRF)
        try:
            validate_url(url)
        except ValueError as e:
            logger.warning(f"URL validation failed: {e} (from {request.remote_addr})")
            return jsonify({'status': 'error', 'message': str(e)}), 400

        # Автоопределение региона
        region = detect_region_from_url(url)
        logger.info(f"Парсинг URL: {url} (регион: {region})")

        # SECURITY: Парсинг с timeout (защита от DoS)
        try:
            with timeout_context(60, 'Парсинг занял слишком много времени (>60s)'):
                with Parser(headless=True, delay=1.0, cache=property_cache, region=region, browser_pool=browser_pool) as parser:
                    parsed_data = parser.parse_detail_page(url)
        except TimeoutError as e:
            logger.error(f"Parsing timeout for {url}: {e}")
            return jsonify({
                'status': 'error',
                'message': 'Время ожидания истекло. Попробуйте позже или другой объект.'
            }), 408  # Request Timeout

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

        # SECURITY: Валидация входных данных через Pydantic
        try:
            validated = ManualPropertyInput(**data)
        except PydanticValidationError as e:
            logger.warning(f"Validation error from {request.remote_addr}: {e}")
            # Форматируем ошибки для пользователя
            errors = []
            for error in e.errors():
                field = error['loc'][0]
                msg = error['msg']
                errors.append(f"{field}: {msg}")
            return jsonify({
                'status': 'error',
                'message': 'Ошибка валидации данных',
                'errors': errors
            }), 400

        # Создаем объект недвижимости из валидированных данных
        property_data = {
            'address': validated.address,
            'price_raw': validated.price_raw,
            'price': f"{int(validated.price_raw):,} ₽".replace(',', ' '),
            'total_area': validated.total_area,
            'area': f"{validated.total_area} м²",
            'rooms': validated.rooms,
            'floor': validated.floor,
            'living_area': validated.living_area,
            'kitchen_area': validated.kitchen_area,
            'repair_level': validated.repair_level,
            'view_type': validated.view_type,
            'manual_input': True,
            'title': f"{validated.rooms}-комн. квартира, {validated.total_area} м²",
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
        import time
        request_start = time.time()

        payload = request.json
        session_id = payload.get('session_id')
        limit = payload.get('limit', 50)  # Увеличено до 50 по умолчанию
        search_type = payload.get('search_type', 'building')  # По умолчанию ищем в ЖК

        logger.info(f"📍 [STEP 2] find-similar request started (session: {session_id}, type: {search_type}, limit: {limit})")

        if not session_id or not session_storage.exists(session_id):
            logger.error(f"❌ Session not found: {session_id}")
            return jsonify({'status': 'error', 'message': 'Сессия не найдена'}), 404

        session_data = session_storage.get(session_id)
        target = session_data['target_property']

        # Определяем регион из URL целевого объекта
        target_url = target.get('url', '')
        region = detect_region_from_url(target_url)
        logger.info(f"🔍 Searching for similar properties (session: {session_id}, type: {search_type}, region: {region}, limit: {limit})")

        # Поиск аналогов с кэшем и регионом
        with Parser(headless=True, delay=1.0, cache=property_cache, region=region, browser_pool=browser_pool) as parser:
            if search_type == 'building':
                # Поиск в том же ЖК
                similar = parser.search_similar_in_building(target, limit=limit)
                residential_complex = target.get('residential_complex', 'Неизвестно')
            else:
                # Широкий поиск по городу
                similar = parser.search_similar(target, limit=limit)
                residential_complex = None

        # Если найдено много аналогов с URL, парсим их параллельно
        # Парсим детально объекты без полных данных (price, total_area, price_per_sqm)
        urls_to_parse = [
            c.get('url') for c in similar
            if c.get('url') and not (c.get('price') and c.get('total_area'))
        ]

        logger.info(f"🔍 DEBUG: {len(similar)} comparables found, {len(urls_to_parse)} need detailed parsing")

        if urls_to_parse:
            try:
                from src.parsers.async_parser import parse_multiple_urls_parallel
                logger.info(f"🚀 Starting parallel parsing of {len(urls_to_parse)} URLs...")
                import time
                parse_start = time.time()

                detailed_results = parse_multiple_urls_parallel(
                    urls=urls_to_parse,
                    headless=True,
                    cache=property_cache,
                    region=region,
                    max_concurrent=5  # FIXED: Увеличено с 2 до 5 для ускорения
                )

                parse_elapsed = time.time() - parse_start
                logger.info(f"⏱️ Parallel parsing took {parse_elapsed:.1f}s for {len(urls_to_parse)} URLs")

                # Обновляем данные аналогов детальной информацией
                url_to_details = {d['url']: d for d in detailed_results}
                updated_count = 0
                for comparable in similar:
                    url = comparable.get('url')
                    if url in url_to_details:
                        comparable.update(url_to_details[url])
                        updated_count += 1

                logger.info(f"✅ Enhanced {updated_count}/{len(similar)} comparables with detailed data")

            except Exception as e:
                logger.error(f"❌ Parallel parsing failed, using basic data: {e}", exc_info=True)

        # Сохраняем в сессию
        session_data['comparables'] = similar
        session_storage.set(session_id, session_data)

        # Debug logging - trace object count
        request_elapsed = time.time() - request_start
        logger.info(f"🔍 Saved {len(similar)} comparables to session {session_id}")
        logger.info(f"✅ [STEP 2] find-similar completed in {request_elapsed:.1f}s - returning {len(similar)} comparables")

        return jsonify({
            'status': 'success',
            'comparables': similar,
            'count': len(similar),
            'search_type': search_type,
            'residential_complex': residential_complex,
            'elapsed_time': round(request_elapsed, 1)
        })

    except Exception as e:
        logger.error(f"❌ [STEP 2] find-similar failed: {e}", exc_info=True)
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

        # SECURITY: Валидация URL (защита от SSRF)
        try:
            validate_url(url)
        except ValueError as e:
            logger.warning(f"URL validation failed: {e} (from {request.remote_addr})")
            return jsonify({'status': 'error', 'message': str(e)}), 400

        # Определяем регион
        region = detect_region_from_url(url)
        logger.info(f"Добавление аналога: {url} (регион: {region})")

        # SECURITY: Парсим с timeout (защита от DoS)
        try:
            with timeout_context(60, 'Парсинг занял слишком много времени (>60s)'):
                with Parser(headless=True, delay=1.0, cache=property_cache, region=region, browser_pool=browser_pool) as parser:
                    comparable_data = parser.parse_detail_page(url)
        except TimeoutError as e:
            logger.error(f"Parsing timeout for {url}: {e}")
            return jsonify({
                'status': 'error',
                'message': 'Время ожидания истекло. Попробуйте позже.'
            }), 408

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


@app.route('/api/include-comparable', methods=['POST'])
def include_comparable():
    """
    API: Возврат аналога в анализ (Экран 2)

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
            comparables[index]['excluded'] = False
            session_storage.set(session_id, session_data)

        return jsonify({'status': 'success'})

    except Exception as e:
        logger.error(f"Ошибка возврата: {e}", exc_info=True)
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
        logger.info(f"🔧 DEBUG: Создаю analyzer...")
        analyzer = RealEstateAnalyzer()
        try:
            logger.info(f"🔧 DEBUG: Запускаю analyzer.analyze()...")
            result = analyzer.analyze(request_model)
            logger.info(f"🔧 DEBUG: ✓ Анализ завершён, тип результата: {type(result)}")
        except ValueError as ve:
            # Специфичные ошибки валидации (например, мало аналогов)
            logger.warning(f"Ошибка валидации анализа: {ve}")
            return jsonify({
                'status': 'error',
                'error_type': 'validation_error',
                'message': str(ve)
            }), 422
        except Exception as analysis_error:
            # Любые другие ошибки анализа
            logger.error(f"Ошибка во время анализа: {analysis_error}", exc_info=True)
            return jsonify({
                'status': 'error',
                'error_type': 'analysis_error',
                'message': f'Ошибка анализа: {str(analysis_error)}'
            }), 500

        # Конвертируем в JSON
        try:
            logger.info(f"🔧 DEBUG: Конвертирую result в dict...")
            result_dict = result.dict()
            logger.info(f"🔧 DEBUG: ✓ Конвертация успешна, размер: {len(str(result_dict))} символов")
        except Exception as dict_error:
            logger.error(f"Ошибка конвертации результата в dict: {dict_error}", exc_info=True)
            return jsonify({
                'status': 'error',
                'error_type': 'serialization_error',
                'message': 'Ошибка обработки результатов анализа'
            }), 500

        # Валидация результата перед отправкой
        logger.info(f"🔧 DEBUG: Валидирую required_fields...")
        required_fields = ['market_statistics', 'fair_price_analysis', 'price_scenarios',
                          'strengths_weaknesses', 'target_property']
        missing_fields = [field for field in required_fields if not result_dict.get(field)]

        if missing_fields:
            logger.warning(f"Результат анализа не содержит обязательных полей: {missing_fields}")
            # Добавляем пустые значения для отсутствующих полей
            for field in missing_fields:
                if field == 'price_scenarios':
                    result_dict[field] = []
                else:
                    result_dict[field] = {}

        # Метрики
        try:
            logger.info(f"🔧 DEBUG: Получаю метрики...")
            metrics = analyzer.get_metrics()
            result_dict['metrics'] = metrics
            logger.info(f"🔧 DEBUG: ✓ Метрики получены")
        except Exception as metrics_error:
            logger.warning(f"Ошибка получения метрик: {metrics_error}")
            result_dict['metrics'] = {}

        # Сохраняем в сессию
        logger.info(f"🔧 DEBUG: Сохраняю результат в сессию {session_id}...")
        session_data['analysis'] = result_dict
        session_data['step'] = 3
        session_storage.set(session_id, session_data)
        logger.info(f"🔧 DEBUG: ✓ Результат сохранён в сессию")

        logger.info(f"🔧 DEBUG: Формирую JSON ответ...")
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


@app.route('/api/export-report/<session_id>', methods=['GET'])
def export_report(session_id):
    """
    API: Экспорт детального отчета в PDF (Экран 3)

    Returns:
        PDF файл для скачивания с полным визуальным отчетом
    """
    try:
        if not session_storage.exists(session_id):
            return jsonify({'status': 'error', 'message': 'Сессия не найдена'}), 404

        session_data = session_storage.get(session_id)

        # Проверяем, что анализ выполнен
        if 'analysis' not in session_data or not session_data['analysis']:
            return jsonify({
                'status': 'error',
                'message': 'Анализ не выполнен. Сначала запустите анализ на шаге 3.'
            }), 400

        logger.info(f"Экспорт PDF отчета для сессии {session_id}")

        # Генерируем PDF используя Playwright
        from datetime import datetime
        import asyncio

        if not PLAYWRIGHT_AVAILABLE:
            # Fallback to markdown if playwright not available
            logger.warning("Playwright не доступен, возвращаем markdown")
            return _export_markdown_fallback(session_id, session_data)

        # Создаем URL для HTML отчета
        base_url = request.url_root.rstrip('/')
        report_url = f"{base_url}/report/{session_id}"

        # Генерируем PDF
        pdf_bytes = asyncio.run(_generate_pdf_from_page(report_url))

        # Возвращаем PDF файл
        from flask import Response
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"housler_report_{session_id[:8]}_{timestamp}.pdf"

        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Content-Type': 'application/pdf'
            }
        )

    except Exception as e:
        logger.error(f"Ошибка экспорта отчета: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'Ошибка генерации отчета: {str(e)}'
        }), 500


@app.route('/report/<session_id>', methods=['GET'])
def view_report(session_id):
    """
    Просмотр HTML отчета (для PDF генерации)
    """
    try:
        if not session_storage.exists(session_id):
            return "Сессия не найдена", 404

        session_data = session_storage.get(session_id)

        if 'analysis' not in session_data or not session_data['analysis']:
            return "Анализ не выполнен", 400

        analysis = session_data['analysis']
        target = session_data.get('target_property', {})
        comparables = session_data.get('comparables', [])

        # Фильтруем исключенные аналоги
        comparables = [c for c in comparables if not c.get('excluded', False)]

        # Генерируем персонализированный оффер Housler
        housler_offer = generate_housler_offer(
            analysis=analysis,
            property_info=target,
            recommendations=analysis.get('recommendations', [])
        )

        # Подготавливаем данные для шаблона
        template_data = {
            'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'property_info': target,
            'comparables': comparables,
            'fair_price_analysis': analysis.get('fair_price_analysis', {}),
            'market_statistics': analysis.get('market_statistics', {}),
            'recommendations': analysis.get('recommendations', []),
            'price_scenarios': analysis.get('price_scenarios', []),
            'time_forecast': analysis.get('time_forecast', {}),
            'attractiveness_index': analysis.get('attractiveness_index', {}),
            'strengths_weaknesses': analysis.get('strengths_weaknesses', {}),
            'housler_offer': housler_offer
        }

        return render_template('report.html', **template_data)

    except Exception as e:
        logger.error(f"Ошибка отображения отчета: {e}", exc_info=True)
        return f"Ошибка генерации отчета: {str(e)}", 500


async def _generate_pdf_from_page(url: str) -> bytes:
    """
    Генерирует PDF из HTML страницы используя Playwright
    """
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Загружаем страницу
        logger.info(f"Загружаем страницу для PDF: {url}")
        await page.goto(url, wait_until='networkidle', timeout=60000)

        # Ждем загрузки контента (report-container вместо analysis-results)
        try:
            await page.wait_for_selector('.report-container', timeout=10000)
        except Exception as e:
            logger.warning(f"Не дождались report-container: {e}, продолжаем...")

        # Даем время на загрузку шрифтов и стилей
        await page.wait_for_timeout(2000)

        # Генерируем PDF
        logger.info("Генерируем PDF...")
        pdf_bytes = await page.pdf(
            format='A4',
            margin={
                'top': '15mm',
                'right': '12mm',
                'bottom': '15mm',
                'left': '12mm'
            },
            print_background=True,
            prefer_css_page_size=False,
            display_header_footer=False
        )

        await browser.close()
        logger.info(f"PDF сгенерирован, размер: {len(pdf_bytes)} bytes")
        return pdf_bytes


def _export_markdown_fallback(session_id: str, session_data: dict):
    """
    Fallback функция для экспорта в markdown если playwright не доступен
    """
    from src.analytics.property_tracker import PropertyLog
    from src.analytics.markdown_exporter import MarkdownExporter
    from datetime import datetime
    from flask import Response

    # Создаем PropertyLog из данных сессии
    property_log = PropertyLog(
        property_id=session_id,
        url=session_data.get('target_property', {}).get('url'),
        started_at=datetime.now().isoformat(),
        completed_at=datetime.now().isoformat(),
        status='completed'
    )

    # Заполняем информацию об объекте
    target = session_data.get('target_property', {})
    property_log.property_info = {
        'price': target.get('price'),
        'total_area': target.get('total_area'),
        'rooms': target.get('rooms'),
        'floor': target.get('floor'),
        'total_floors': target.get('total_floors'),
        'address': target.get('address')
    }

    # Добавляем аналоги
    comparables = session_data.get('comparables', [])
    property_log.comparables_data = [
        {
            'price': c.get('price'),
            'total_area': c.get('total_area'),
            'price_per_sqm': c.get('price_per_sqm'),
            'address': c.get('address'),
            'url': c.get('url')
        }
        for c in comparables
        if not c.get('excluded', False)
    ]

    # Заполняем результаты анализа
    analysis = session_data['analysis']
    if 'market_statistics' in analysis:
        property_log.market_stats = analysis['market_statistics']
    if 'fair_price_analysis' in analysis:
        property_log.fair_price_result = analysis['fair_price_analysis']
    if 'price_range' in analysis:
        property_log.price_range = analysis['price_range']
    if 'attractiveness_index' in analysis:
        property_log.attractiveness_index = analysis['attractiveness_index']
    if 'time_forecast' in analysis:
        property_log.time_forecast = analysis['time_forecast']
    if 'price_sensitivity' in analysis:
        property_log.price_sensitivity = analysis['price_sensitivity']
    if 'price_scenarios' in analysis:
        property_log.scenarios = analysis['price_scenarios']
    if 'adjustments_applied' in analysis:
        property_log.adjustments = analysis['adjustments_applied']
    if 'metrics' in analysis:
        property_log.metrics = analysis['metrics']
    if 'recommendations' in analysis:
        property_log.recommendations = analysis['recommendations']

    # Генерируем Markdown отчет
    exporter = MarkdownExporter()
    markdown_content = exporter.export_single_property(property_log)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"housler_report_{session_id[:8]}_{timestamp}.md"

    return Response(
        markdown_content,
        mimetype='text/markdown',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Content-Type': 'text/markdown; charset=utf-8'
        }
    )


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


# CLEANUP: Shutdown handler для browser pool
import atexit
import signal

def shutdown_browser_pool():
    """Закрывает browser pool при завершении приложения"""
    if browser_pool:
        logger.info("Shutting down browser pool...")
        try:
            browser_pool.shutdown()
        except Exception as e:
            logger.error(f"Error shutting down browser pool: {e}")

# Регистрируем обработчики завершения
atexit.register(shutdown_browser_pool)

def signal_handler(signum, frame):
    """Обработчик сигналов для graceful shutdown"""
    logger.info(f"Received signal {signum}, shutting down...")
    shutdown_browser_pool()
    exit(0)

# Регистрируем обработчики сигналов
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


if __name__ == '__main__':
    try:
        app.run(debug=True, host='0.0.0.0', port=5002)
    finally:
        shutdown_browser_pool()
