"""
Модуль парсеров недвижимости

Автоматическая регистрация всех парсеров при импорте.
"""

# Импортируем исключения из единого места
from ..exceptions import (
    ParsingError,
    SourceNotSupportedError,
    PageNotFoundError,
    ParsingTimeoutError,
    RateLimitedError
)

# Импортируем базовые классы (всегда доступны)
from .base_real_estate_parser import BaseRealEstateParser, ParserCapabilities
from .parser_registry import ParserRegistry, get_global_registry, register_parser
from .field_mapper import FieldMapper, get_field_mapper

# Список успешно импортированных парсеров
__all__ = [
    # Исключения
    'ParsingError',
    'SourceNotSupportedError',
    'PageNotFoundError',
    'ParsingTimeoutError',
    'RateLimitedError',

    # Базовые классы
    'BaseRealEstateParser',
    'ParserCapabilities',

    # Регистрация
    'ParserRegistry',
    'get_global_registry',
    'register_parser',

    # Маппинг
    'FieldMapper',
    'get_field_mapper',
]

# Пытаемся импортировать CianParser (требует Playwright)
try:
    from .cian_parser_adapter import CianParser
    __all__.append('CianParser')
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"CianParser недоступен: {e}")
    CianParser = None

# Пытаемся импортировать MultiSourceSearchStrategy
try:
    from .multi_source_search import (
        MultiSourceSearchStrategy,
        SearchConfig,
        search_across_sources
    )
    __all__.extend(['MultiSourceSearchStrategy', 'SearchConfig', 'search_across_sources'])
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"MultiSourceSearchStrategy недоступна: {e}")
    MultiSourceSearchStrategy = None
    SearchConfig = None
    search_across_sources = None
