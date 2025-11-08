"""
Модуль кэширования для парсера недвижимости
"""

from .redis_cache import PropertyCache, get_cache, init_cache

__all__ = ['PropertyCache', 'get_cache', 'init_cache']
