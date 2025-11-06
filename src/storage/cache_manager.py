"""
Cache Manager для кэширования парсированных объектов и результатов анализа
Использует Redis и PostgreSQL для многоуровневого кэширования
"""

import hashlib
import json
import logging
from typing import Dict, Optional, Any, Callable
from functools import wraps
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Менеджер многоуровневого кэширования

    Уровни кэширования:
    1. In-memory (самый быстрый, но ограниченный)
    2. Redis (быстрый, персистентный)
    3. PostgreSQL (медленный, но с долгим TTL и поиском)

    Features:
    - Автоматическое истечение кэша (TTL)
    - Многоуровневое кэширование
    - Cache decorators для функций
    - Поддержка invalidation
    """

    def __init__(
        self,
        redis_manager=None,
        postgres_manager=None,
        use_memory: bool = True,
        memory_max_size: int = 100
    ):
        """
        Инициализация менеджера кэширования

        Args:
            redis_manager: Экземпляр RedisSessionManager (опционально)
            postgres_manager: Экземпляр PostgresManager (опционально)
            use_memory: Использовать in-memory кэш
            memory_max_size: Максимальный размер in-memory кэша
        """
        self.redis_manager = redis_manager
        self.postgres_manager = postgres_manager
        self.use_memory = use_memory
        self.memory_max_size = memory_max_size

        # In-memory cache (LRU-like)
        self._memory_cache: Dict[str, Dict] = {}
        self._memory_access_order: list = []

        logger.info("✅ Cache Manager инициализирован")

    def _evict_memory_cache(self):
        """Освобождение памяти при превышении лимита"""
        while len(self._memory_cache) >= self.memory_max_size:
            # Удаляем самый старый элемент
            if self._memory_access_order:
                oldest_key = self._memory_access_order.pop(0)
                self._memory_cache.pop(oldest_key, None)

    def _update_memory_access(self, key: str):
        """Обновление порядка доступа для LRU"""
        if key in self._memory_access_order:
            self._memory_access_order.remove(key)
        self._memory_access_order.append(key)

    @staticmethod
    def _generate_cache_key(prefix: str, identifier: Any) -> str:
        """
        Генерация ключа кэша

        Args:
            prefix: Префикс (property, analysis, etc.)
            identifier: Идентификатор (URL, dict, etc.)

        Returns:
            Хэшированный ключ
        """
        if isinstance(identifier, dict):
            # Сортируем ключи для консистентности
            identifier_str = json.dumps(identifier, sort_keys=True, ensure_ascii=False)
        else:
            identifier_str = str(identifier)

        # MD5 хэш для короткого ключа
        hash_obj = hashlib.md5(identifier_str.encode('utf-8'))
        hash_key = hash_obj.hexdigest()

        return f"cache:{prefix}:{hash_key}"

    def get(
        self,
        prefix: str,
        identifier: Any,
        check_postgres: bool = True
    ) -> Optional[Dict]:
        """
        Получение данных из кэша (многоуровневое)

        Args:
            prefix: Префикс кэша
            identifier: Идентификатор данных
            check_postgres: Проверять PostgreSQL кэш

        Returns:
            Данные из кэша или None
        """
        cache_key = self._generate_cache_key(prefix, identifier)

        # Level 1: Memory cache
        if self.use_memory and cache_key in self._memory_cache:
            entry = self._memory_cache[cache_key]

            # Проверка истечения
            if entry['expires_at'] and datetime.now() > entry['expires_at']:
                del self._memory_cache[cache_key]
                logger.debug(f"💾 Memory cache expired: {cache_key}")
            else:
                self._update_memory_access(cache_key)
                logger.debug(f"💾 Memory cache HIT: {cache_key}")
                return entry['data']

        # Level 2: Redis cache
        if self.redis_manager:
            data = self.redis_manager.get(cache_key)
            if data:
                logger.debug(f"💾 Redis cache HIT: {cache_key}")

                # Promote to memory cache
                if self.use_memory:
                    self._evict_memory_cache()
                    self._memory_cache[cache_key] = {
                        'data': data,
                        'expires_at': None  # Управляется Redis TTL
                    }
                    self._update_memory_access(cache_key)

                return data

        # Level 3: PostgreSQL cache (для property объектов)
        if check_postgres and self.postgres_manager and prefix == 'property':
            # identifier - это URL объекта
            if isinstance(identifier, str) and identifier.startswith('http'):
                data = self.postgres_manager.get_cached_property(identifier)
                if data:
                    logger.debug(f"💾 PostgreSQL cache HIT: {identifier}")

                    # Promote to Redis and Memory
                    if self.redis_manager:
                        self.redis_manager.set(cache_key, data, ttl=3600)

                    if self.use_memory:
                        self._evict_memory_cache()
                        self._memory_cache[cache_key] = {
                            'data': data,
                            'expires_at': datetime.now() + timedelta(hours=1)
                        }
                        self._update_memory_access(cache_key)

                    return data

        logger.debug(f"💾 Cache MISS: {cache_key}")
        return None

    def set(
        self,
        prefix: str,
        identifier: Any,
        data: Dict,
        ttl: int = 3600,
        save_to_postgres: bool = False,
        postgres_ttl_hours: int = 24
    ) -> bool:
        """
        Сохранение данных в кэш (многоуровневое)

        Args:
            prefix: Префикс кэша
            identifier: Идентификатор данных
            data: Данные для кэширования
            ttl: TTL для Redis в секундах
            save_to_postgres: Сохранять в PostgreSQL
            postgres_ttl_hours: TTL для PostgreSQL в часах

        Returns:
            True если успешно
        """
        cache_key = self._generate_cache_key(prefix, identifier)

        success = True

        # Level 1: Memory cache
        if self.use_memory:
            self._evict_memory_cache()
            self._memory_cache[cache_key] = {
                'data': data,
                'expires_at': datetime.now() + timedelta(seconds=ttl)
            }
            self._update_memory_access(cache_key)
            logger.debug(f"💾 Saved to memory cache: {cache_key}")

        # Level 2: Redis cache
        if self.redis_manager:
            success = self.redis_manager.set(cache_key, data, ttl=ttl)
            if success:
                logger.debug(f"💾 Saved to Redis cache: {cache_key}")
            else:
                logger.warning(f"⚠️ Failed to save to Redis: {cache_key}")

        # Level 3: PostgreSQL cache (для property объектов)
        if save_to_postgres and self.postgres_manager and prefix == 'property':
            if isinstance(identifier, str) and identifier.startswith('http'):
                pg_success = self.postgres_manager.cache_parsed_property(
                    url=identifier,
                    property_data=data,
                    ttl_hours=postgres_ttl_hours
                )
                if pg_success:
                    logger.debug(f"💾 Saved to PostgreSQL cache: {identifier}")
                else:
                    logger.warning(f"⚠️ Failed to save to PostgreSQL: {identifier}")

        return success

    def delete(self, prefix: str, identifier: Any) -> bool:
        """
        Удаление данных из кэша

        Args:
            prefix: Префикс кэша
            identifier: Идентификатор данных

        Returns:
            True если успешно
        """
        cache_key = self._generate_cache_key(prefix, identifier)

        # Delete from all levels
        if self.use_memory:
            self._memory_cache.pop(cache_key, None)
            if cache_key in self._memory_access_order:
                self._memory_access_order.remove(cache_key)

        if self.redis_manager:
            self.redis_manager.delete(cache_key)

        logger.debug(f"🗑️ Deleted from cache: {cache_key}")
        return True

    def invalidate_pattern(self, prefix: str, pattern: str = "*") -> int:
        """
        Инвалидация кэша по паттерну

        Args:
            prefix: Префикс кэша
            pattern: Паттерн для поиска

        Returns:
            Количество удаленных записей
        """
        count = 0

        # Invalidate memory cache
        if self.use_memory:
            keys_to_delete = [
                k for k in self._memory_cache.keys()
                if k.startswith(f"cache:{prefix}:")
            ]
            for key in keys_to_delete:
                self._memory_cache.pop(key, None)
                if key in self._memory_access_order:
                    self._memory_access_order.remove(key)
            count += len(keys_to_delete)

        # Invalidate Redis cache
        if self.redis_manager:
            search_pattern = f"cache:{prefix}:{pattern}"
            redis_keys = self.redis_manager.get_all_keys(search_pattern)
            for key in redis_keys:
                self.redis_manager.delete(key)
            count += len(redis_keys)

        logger.info(f"🗑️ Invalidated {count} cache entries for pattern: {prefix}:{pattern}")
        return count

    def clear_all(self):
        """Очистка всего кэша"""
        if self.use_memory:
            self._memory_cache.clear()
            self._memory_access_order.clear()

        if self.redis_manager:
            # Удаляем только cache:* ключи
            cache_keys = self.redis_manager.get_all_keys("cache:*")
            for key in cache_keys:
                self.redis_manager.delete(key)

        logger.info("🧹 Весь кэш очищен")

    def get_stats(self) -> Dict[str, Any]:
        """
        Получение статистики кэша

        Returns:
            Словарь со статистикой
        """
        stats = {
            'memory_enabled': self.use_memory,
            'redis_enabled': self.redis_manager is not None,
            'postgres_enabled': self.postgres_manager is not None,
        }

        if self.use_memory:
            stats['memory_cache_size'] = len(self._memory_cache)
            stats['memory_max_size'] = self.memory_max_size

        if self.redis_manager:
            redis_stats = self.redis_manager.get_stats()
            stats['redis_stats'] = redis_stats

        if self.postgres_manager:
            pg_stats = self.postgres_manager.get_stats()
            stats['postgres_cached_properties'] = pg_stats.get('cached_properties', 0)

        return stats


def cache(
    prefix: str,
    ttl: int = 3600,
    key_func: Optional[Callable] = None,
    save_to_postgres: bool = False
):
    """
    Декоратор для кэширования результатов функций

    Args:
        prefix: Префикс для ключа кэша
        ttl: Время жизни кэша в секундах
        key_func: Функция для генерации ключа из аргументов (опционально)
        save_to_postgres: Сохранять в PostgreSQL

    Usage:
        @cache('myfunction', ttl=600)
        def my_function(arg1, arg2):
            return expensive_operation(arg1, arg2)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Получаем глобальный cache manager (нужно будет создать)
            from src.storage.cache_manager import _cache_manager
            if _cache_manager is None:
                # Кэш не инициализирован - выполняем функцию без кэширования
                return func(*args, **kwargs)

            # Генерация ключа
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Используем все аргументы как ключ
                cache_key = {
                    'args': args,
                    'kwargs': kwargs
                }

            # Проверяем кэш
            cached_result = _cache_manager.get(prefix, cache_key)
            if cached_result is not None:
                logger.debug(f"💾 Returning cached result for {func.__name__}")
                return cached_result

            # Выполняем функцию
            result = func(*args, **kwargs)

            # Сохраняем в кэш
            _cache_manager.set(
                prefix,
                cache_key,
                result,
                ttl=ttl,
                save_to_postgres=save_to_postgres
            )

            return result

        return wrapper
    return decorator


# Global cache manager instance
_cache_manager: Optional[CacheManager] = None


def get_cache_manager(
    redis_manager=None,
    postgres_manager=None,
    use_memory: bool = True,
    memory_max_size: int = 100
) -> CacheManager:
    """
    Получение singleton instance cache manager

    Args:
        redis_manager: Redis manager instance
        postgres_manager: Postgres manager instance
        use_memory: Use in-memory cache
        memory_max_size: Max in-memory cache size

    Returns:
        CacheManager instance
    """
    global _cache_manager

    if _cache_manager is None:
        _cache_manager = CacheManager(
            redis_manager=redis_manager,
            postgres_manager=postgres_manager,
            use_memory=use_memory,
            memory_max_size=memory_max_size
        )

    return _cache_manager
