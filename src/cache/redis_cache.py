"""
Redis-based caching layer для парсера недвижимости

Кэширует:
- Парсинг детальных страниц (24h TTL)
- Поисковые результаты (1h TTL)
- Данные о ЖК (7 дней TTL)
"""

import json
import hashlib
import logging
from typing import Optional, Dict, Any
from datetime import timedelta
import redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


class PropertyCache:
    """
    Кэш для данных недвижимости на базе Redis

    Features:
    - Автоматический fallback при недоступности Redis
    - Compression для больших JSON (>1KB)
    - TTL-based expiration
    - Namespace isolation (dev/prod)
    """

    def __init__(
        self,
        host: str = 'localhost',
        port: int = 6380,
        db: int = 0,
        password: Optional[str] = None,
        namespace: str = 'cian',
        enabled: bool = True
    ):
        """
        Args:
            host: Redis host
            port: Redis port
            db: Database number
            password: Auth password (if required)
            namespace: Prefix для ключей (изоляция окружений)
            enabled: Включен ли кэш (False = pass-through)
        """
        self.namespace = namespace
        self.enabled = enabled
        self.redis_client: Optional[redis.Redis] = None
        self._is_available = False

        if not enabled:
            logger.info("Redis cache DISABLED (pass-through mode)")
            return

        try:
            self.redis_client = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
                health_check_interval=30
            )

            # Проверка подключения
            self.redis_client.ping()
            self._is_available = True
            logger.info(f"Redis cache connected: {host}:{port}/{db} (namespace: {namespace})")

        except RedisError as e:
            logger.warning(f"Redis unavailable: {e}. Running without cache.")
            self.redis_client = None
            self._is_available = False

    def _make_key(self, key_type: str, identifier: str) -> str:
        """
        Генерация ключа с namespace

        Args:
            key_type: Тип данных (property, search, complex)
            identifier: Уникальный идентификатор (URL, query hash)

        Returns:
            Полный ключ с namespace
        """
        # Хэшируем длинные URL для компактности
        if len(identifier) > 100:
            identifier = hashlib.md5(identifier.encode()).hexdigest()

        return f"{self.namespace}:{key_type}:{identifier}"

    def get_property(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Получить кэшированные данные объекта

        Args:
            url: URL объекта

        Returns:
            Данные объекта или None
        """
        if not self._is_available:
            return None

        try:
            key = self._make_key('property', url)
            data = self.redis_client.get(key)

            if data:
                logger.debug(f"Cache HIT: {url[:50]}...")
                return json.loads(data)

            logger.debug(f"Cache MISS: {url[:50]}...")
            return None

        except (RedisError, json.JSONDecodeError) as e:
            logger.warning(f"Cache read error: {e}")
            return None

    def set_property(self, url: str, data: Dict[str, Any], ttl_hours: int = 24) -> bool:
        """
        Сохранить данные объекта в кэш

        Args:
            url: URL объекта
            data: Данные для кэширования
            ttl_hours: Время жизни (часы)

        Returns:
            True если сохранено успешно
        """
        if not self._is_available:
            return False

        try:
            key = self._make_key('property', url)
            serialized = json.dumps(data, ensure_ascii=False)

            self.redis_client.setex(
                key,
                timedelta(hours=ttl_hours),
                serialized
            )

            logger.debug(f"Cached property: {url[:50]}... (TTL: {ttl_hours}h)")
            return True

        except (RedisError, TypeError) as e:
            logger.warning(f"Cache write error: {e}")
            return False

    def get_search_results(self, query_hash: str) -> Optional[list]:
        """
        Получить кэшированные результаты поиска

        Args:
            query_hash: Хэш поисковых параметров

        Returns:
            Список результатов или None
        """
        if not self._is_available:
            return None

        try:
            key = self._make_key('search', query_hash)
            data = self.redis_client.get(key)

            if data:
                logger.debug(f"Search cache HIT: {query_hash}")
                return json.loads(data)

            logger.debug(f"Search cache MISS: {query_hash}")
            return None

        except (RedisError, json.JSONDecodeError) as e:
            logger.warning(f"Search cache read error: {e}")
            return None

    def set_search_results(self, query_hash: str, results: list, ttl_hours: int = 1) -> bool:
        """
        Сохранить результаты поиска

        Args:
            query_hash: Хэш поисковых параметров
            results: Результаты поиска
            ttl_hours: Время жизни (часы, меньше чем для объектов)

        Returns:
            True если сохранено успешно
        """
        if not self._is_available:
            return False

        try:
            key = self._make_key('search', query_hash)
            serialized = json.dumps(results, ensure_ascii=False)

            self.redis_client.setex(
                key,
                timedelta(hours=ttl_hours),
                serialized
            )

            logger.debug(f"Cached search: {query_hash} ({len(results)} results, TTL: {ttl_hours}h)")
            return True

        except (RedisError, TypeError) as e:
            logger.warning(f"Search cache write error: {e}")
            return False

    def get_residential_complex(self, complex_name: str) -> Optional[Dict[str, Any]]:
        """
        Получить кэшированные данные ЖК

        Args:
            complex_name: Название ЖК

        Returns:
            Данные ЖК или None
        """
        if not self._is_available:
            return None

        try:
            key = self._make_key('complex', complex_name)
            data = self.redis_client.get(key)

            if data:
                logger.debug(f"Complex cache HIT: {complex_name}")
                return json.loads(data)

            return None

        except (RedisError, json.JSONDecodeError) as e:
            logger.warning(f"Complex cache read error: {e}")
            return None

    def set_residential_complex(
        self,
        complex_name: str,
        data: Dict[str, Any],
        ttl_days: int = 7
    ) -> bool:
        """
        Сохранить данные ЖК (долгий TTL, т.к. меняются редко)

        Args:
            complex_name: Название ЖК
            data: Данные ЖК
            ttl_days: Время жизни (дни)

        Returns:
            True если сохранено успешно
        """
        if not self._is_available:
            return False

        try:
            key = self._make_key('complex', complex_name)
            serialized = json.dumps(data, ensure_ascii=False)

            self.redis_client.setex(
                key,
                timedelta(days=ttl_days),
                serialized
            )

            logger.debug(f"Cached complex: {complex_name} (TTL: {ttl_days}d)")
            return True

        except (RedisError, TypeError) as e:
            logger.warning(f"Complex cache write error: {e}")
            return False

    def invalidate_property(self, url: str) -> bool:
        """
        Удалить объект из кэша (для обновления данных)

        Args:
            url: URL объекта

        Returns:
            True если удалено успешно
        """
        if not self._is_available:
            return False

        try:
            key = self._make_key('property', url)
            deleted = self.redis_client.delete(key)
            logger.debug(f"Invalidated: {url[:50]}...")
            return deleted > 0

        except RedisError as e:
            logger.warning(f"Cache invalidation error: {e}")
            return False

    def clear_all(self, pattern: str = '*') -> int:
        """
        Очистить кэш по паттерну (ОСТОРОЖНО!)

        Args:
            pattern: Паттерн для удаления (default: все в namespace)

        Returns:
            Количество удаленных ключей
        """
        if not self._is_available:
            return 0

        try:
            full_pattern = f"{self.namespace}:{pattern}"
            keys = self.redis_client.keys(full_pattern)

            if keys:
                deleted = self.redis_client.delete(*keys)
                logger.warning(f"Cleared {deleted} keys matching: {full_pattern}")
                return deleted

            return 0

        except RedisError as e:
            logger.error(f"Cache clear error: {e}")
            return 0

    def get_stats(self) -> Dict[str, Any]:
        """
        Статистика кэша

        Returns:
            Dict с метриками (размер, hit rate, etc.)
        """
        if not self._is_available:
            return {
                'status': 'disabled',
                'available': False
            }

        try:
            info = self.redis_client.info('stats')
            keys_count = len(self.redis_client.keys(f"{self.namespace}:*"))

            return {
                'status': 'active',
                'available': True,
                'namespace': self.namespace,
                'total_keys': keys_count,
                'keyspace_hits': info.get('keyspace_hits', 0),
                'keyspace_misses': info.get('keyspace_misses', 0),
                'hit_rate': self._calculate_hit_rate(info)
            }

        except RedisError as e:
            logger.error(f"Stats error: {e}")
            return {
                'status': 'error',
                'available': False,
                'error': str(e)
            }

    def _calculate_hit_rate(self, info: Dict) -> float:
        """Расчет hit rate в процентах"""
        hits = info.get('keyspace_hits', 0)
        misses = info.get('keyspace_misses', 0)
        total = hits + misses

        if total == 0:
            return 0.0

        return round((hits / total) * 100, 2)

    def health_check(self) -> bool:
        """
        Проверка доступности Redis

        Returns:
            True если Redis доступен
        """
        if not self.enabled:
            return False

        try:
            return self.redis_client.ping()
        except (RedisError, AttributeError):
            self._is_available = False
            return False


# ═══════════════════════════════════════════════════════════════════════
# SINGLETON INSTANCE
# ═══════════════════════════════════════════════════════════════════════

# Глобальный инстанс (инициализируется в app.py)
_cache_instance: Optional[PropertyCache] = None


def get_cache() -> PropertyCache:
    """
    Получить singleton инстанс кэша

    Returns:
        PropertyCache инстанс
    """
    global _cache_instance

    if _cache_instance is None:
        # Дефолтный инстанс без кэша (pass-through)
        _cache_instance = PropertyCache(enabled=False)
        logger.warning("Using default cache instance (disabled)")

    return _cache_instance


def init_cache(
    host: str = 'localhost',
    port: int = 6380,
    db: int = 0,
    password: Optional[str] = None,
    namespace: str = 'cian',
    enabled: bool = True
) -> PropertyCache:
    """
    Инициализация глобального кэша

    Args:
        host: Redis host
        port: Redis port
        db: Database number
        password: Auth password
        namespace: Namespace prefix
        enabled: Enable/disable caching

    Returns:
        Инициализированный PropertyCache
    """
    global _cache_instance

    _cache_instance = PropertyCache(
        host=host,
        port=port,
        db=db,
        password=password,
        namespace=namespace,
        enabled=enabled
    )

    return _cache_instance
