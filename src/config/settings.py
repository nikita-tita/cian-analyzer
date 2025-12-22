"""
Централизованная конфигурация HOUSLER

Использует переменные окружения с валидацией через Pydantic.
Все настройки в одном месте - никакого хардкода в коде.

Пример использования:
    from src.config import settings

    # Доступ к настройкам
    redis_url = settings.redis_url
    is_prod = settings.is_production

    # Проверка features
    if settings.REDIS_ENABLED:
        init_redis()
"""

import os
from typing import List, Optional
from functools import lru_cache


class Settings:
    """
    Конфигурация приложения

    Все настройки загружаются из переменных окружения.
    Дефолтные значения оптимизированы для development.
    В production переопределяются через .env или Docker environment.
    """

    def __init__(self):
        # ═══════════════════════════════════════════════════════════════════
        # FLASK
        # ═══════════════════════════════════════════════════════════════════
        self.SECRET_KEY: str = os.getenv('SECRET_KEY', '')
        self.FLASK_ENV: str = os.getenv('FLASK_ENV', 'development')
        self.FLASK_DEBUG: bool = os.getenv('FLASK_DEBUG', 'true').lower() == 'true'

        # ═══════════════════════════════════════════════════════════════════
        # REDIS
        # ═══════════════════════════════════════════════════════════════════
        self.REDIS_ENABLED: bool = os.getenv('REDIS_ENABLED', 'false').lower() == 'true'
        self.REDIS_HOST: str = os.getenv('REDIS_HOST', 'localhost')
        self.REDIS_PORT: int = int(os.getenv('REDIS_PORT', '6380'))
        self.REDIS_DB: int = int(os.getenv('REDIS_DB', '0'))
        self.REDIS_PASSWORD: Optional[str] = os.getenv('REDIS_PASSWORD') or None
        self.REDIS_NAMESPACE: str = os.getenv('REDIS_NAMESPACE', 'housler')

        # ═══════════════════════════════════════════════════════════════════
        # GUNICORN
        # ═══════════════════════════════════════════════════════════════════
        self.WORKERS: int = int(os.getenv('WORKERS', '4'))
        self.WORKER_CLASS: str = os.getenv('WORKER_CLASS', 'sync')
        self.TIMEOUT: int = int(os.getenv('TIMEOUT', '300'))
        self.BIND: str = os.getenv('BIND', '0.0.0.0:5000')

        # ═══════════════════════════════════════════════════════════════════
        # LOGGING
        # ═══════════════════════════════════════════════════════════════════
        self.LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')

        # ═══════════════════════════════════════════════════════════════════
        # PARSER
        # ═══════════════════════════════════════════════════════════════════
        self.DEFAULT_REGION: str = os.getenv('DEFAULT_REGION', 'spb')
        self.PARSER_HEADLESS: bool = os.getenv('PARSER_HEADLESS', 'true').lower() == 'true'
        self.PARSER_DELAY: float = float(os.getenv('PARSER_DELAY', '1.0'))
        self.PARSER_TIMEOUT: int = int(os.getenv('PARSER_TIMEOUT', '60'))
        self.MAX_CONCURRENT_PARSING: int = int(os.getenv('MAX_CONCURRENT_PARSING', '5'))
        self.MAX_BROWSERS: int = int(os.getenv('MAX_BROWSERS', '3'))
        self.USE_BROWSER_POOL: bool = os.getenv('USE_BROWSER_POOL', 'false').lower() == 'true'

        # Лимиты для поиска
        self.SEARCH_LIMIT_DEFAULT: int = int(os.getenv('SEARCH_LIMIT_DEFAULT', '50'))
        self.SEARCH_LIMIT_MAX: int = int(os.getenv('SEARCH_LIMIT_MAX', '100'))

        # ═══════════════════════════════════════════════════════════════════
        # RATE LIMITING
        # ═══════════════════════════════════════════════════════════════════
        self.RATELIMIT_DEFAULT: str = os.getenv('RATELIMIT_DEFAULT', '200 per day, 50 per hour')
        self.RATELIMIT_PARSE: str = os.getenv('RATELIMIT_PARSE', '10 per minute')
        self.RATELIMIT_SEARCH: str = os.getenv('RATELIMIT_SEARCH', '15 per minute')
        self.RATELIMIT_ANALYZE: str = os.getenv('RATELIMIT_ANALYZE', '20 per minute')

        # ═══════════════════════════════════════════════════════════════════
        # SECURITY
        # ═══════════════════════════════════════════════════════════════════
        # Разрешённые домены для парсинга (защита от SSRF)
        allowed_domains_str = os.getenv(
            'ALLOWED_PARSING_DOMAINS',
            'www.cian.ru,cian.ru,spb.cian.ru,moscow.cian.ru,www.domclick.ru,domclick.ru'
        )
        self.ALLOWED_PARSING_DOMAINS: List[str] = [
            d.strip() for d in allowed_domains_str.split(',') if d.strip()
        ]

        # Allowed hosts для Flask
        allowed_hosts_str = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1,housler.ru')
        self.ALLOWED_HOSTS: List[str] = [
            h.strip() for h in allowed_hosts_str.split(',') if h.strip()
        ]

        # CORS origins
        cors_origins_str = os.getenv('CORS_ORIGINS', 'http://localhost:3000,https://housler.ru')
        self.CORS_ORIGINS: List[str] = [
            o.strip() for o in cors_origins_str.split(',') if o.strip()
        ]

        # Admin API key
        self.ADMIN_API_KEY: Optional[str] = os.getenv('ADMIN_API_KEY') or None

        # ═══════════════════════════════════════════════════════════════════
        # DUPLICATE DETECTION
        # Коэффициенты для определения дублей из разных источников
        # ═══════════════════════════════════════════════════════════════════
        self.DUPLICATE_STRICT_PRICE_TOLERANCE: float = float(
            os.getenv('DUPLICATE_STRICT_PRICE_TOLERANCE', '0.02')  # ±2%
        )
        self.DUPLICATE_PROBABLE_PRICE_TOLERANCE: float = float(
            os.getenv('DUPLICATE_PROBABLE_PRICE_TOLERANCE', '0.10')  # ±10%
        )
        self.DUPLICATE_POSSIBLE_PRICE_TOLERANCE: float = float(
            os.getenv('DUPLICATE_POSSIBLE_PRICE_TOLERANCE', '0.15')  # ±15%
        )
        self.DUPLICATE_AREA_TOLERANCE: float = float(
            os.getenv('DUPLICATE_AREA_TOLERANCE', '0.5')  # ±0.5 м²
        )
        self.DUPLICATE_POSSIBLE_AREA_TOLERANCE: float = float(
            os.getenv('DUPLICATE_POSSIBLE_AREA_TOLERANCE', '1.0')  # ±1 м²
        )

        # ═══════════════════════════════════════════════════════════════════
        # ANALYSIS
        # ═══════════════════════════════════════════════════════════════════
        self.MIN_COMPARABLES_FOR_ANALYSIS: int = int(
            os.getenv('MIN_COMPARABLES_FOR_ANALYSIS', '3')
        )
        self.RECOMMENDED_COMPARABLES: int = int(
            os.getenv('RECOMMENDED_COMPARABLES', '10')
        )

        # ═══════════════════════════════════════════════════════════════════
        # MONITORING
        # ═══════════════════════════════════════════════════════════════════
        self.PROMETHEUS_ENABLED: bool = os.getenv('PROMETHEUS_ENABLED', 'false').lower() == 'true'
        self.GRAFANA_ENABLED: bool = os.getenv('GRAFANA_ENABLED', 'false').lower() == 'true'

        # ═══════════════════════════════════════════════════════════════════
        # PROXY (Decodo/Smartproxy)
        # ═══════════════════════════════════════════════════════════════════
        self.PROXY_ENABLED: bool = os.getenv('PROXY_ENABLED', 'false').lower() == 'true'
        self.PROXY_HOST: str = os.getenv('PROXY_HOST', 'gate.decodo.com')
        self.PROXY_PORT: int = int(os.getenv('PROXY_PORT', '10001'))
        self.PROXY_USERNAME: Optional[str] = os.getenv('PROXY_USERNAME') or None
        self.PROXY_PASSWORD: Optional[str] = os.getenv('PROXY_PASSWORD') or None
        self.PROXY_TYPE: str = os.getenv('PROXY_TYPE', 'http')  # http, https, socks5
        self.PROXY_LOCATION: str = os.getenv('PROXY_LOCATION', 'RU')

        # ═══════════════════════════════════════════════════════════════════
        # APPLICATION INFO
        # ═══════════════════════════════════════════════════════════════════
        self.APP_NAME: str = 'HOUSLER'
        self.APP_VERSION: str = os.getenv('APP_VERSION', '2.1.0')

    # ═══════════════════════════════════════════════════════════════════════
    # COMPUTED PROPERTIES
    # ═══════════════════════════════════════════════════════════════════════

    @property
    def is_production(self) -> bool:
        """Проверка production окружения"""
        return self.FLASK_ENV == 'production'

    @property
    def is_development(self) -> bool:
        """Проверка development окружения"""
        return self.FLASK_ENV == 'development'

    @property
    def redis_url(self) -> str:
        """URL для подключения к Redis"""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @property
    def rate_limit_storage_uri(self) -> str:
        """URI хранилища для rate limiting"""
        if self.REDIS_ENABLED:
            return self.redis_url
        return 'memory://'

    @property
    def proxy_url(self) -> Optional[str]:
        """
        URL прокси для HTTP клиентов (curl_cffi, httpx)
        Формат: http://user:pass@host:port
        """
        if not self.PROXY_ENABLED or not self.PROXY_USERNAME:
            return None
        return f"{self.PROXY_TYPE}://{self.PROXY_USERNAME}:{self.PROXY_PASSWORD}@{self.PROXY_HOST}:{self.PROXY_PORT}"

    @property
    def proxy_config(self) -> Optional[dict]:
        """
        Конфигурация прокси для Playwright
        Формат: {'server': 'http://host:port', 'username': '...', 'password': '...'}
        """
        if not self.PROXY_ENABLED or not self.PROXY_USERNAME:
            return None
        return {
            'server': f"{self.PROXY_TYPE}://{self.PROXY_HOST}:{self.PROXY_PORT}",
            'username': self.PROXY_USERNAME,
            'password': self.PROXY_PASSWORD,
        }

    def validate(self) -> List[str]:
        """
        Валидация конфигурации

        Returns:
            Список ошибок (пустой если всё OK)
        """
        errors = []

        # Production требует SECRET_KEY
        if self.is_production and not self.SECRET_KEY:
            errors.append('SECRET_KEY must be set in production environment')

        # Проверка допустимых значений
        if self.LOG_LEVEL not in ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'):
            errors.append(f'Invalid LOG_LEVEL: {self.LOG_LEVEL}')

        if self.DEFAULT_REGION not in ('spb', 'msk'):
            errors.append(f'Invalid DEFAULT_REGION: {self.DEFAULT_REGION}')

        if self.MAX_BROWSERS < 1 or self.MAX_BROWSERS > 10:
            errors.append(f'MAX_BROWSERS should be between 1 and 10, got {self.MAX_BROWSERS}')

        return errors


# ═══════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Получить singleton экземпляр настроек

    Кэшируется для performance. Настройки загружаются один раз при старте.
    """
    return Settings()
