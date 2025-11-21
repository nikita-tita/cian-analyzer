"""
Модуль парсеров недвижимости

Автоматическая регистрация всех парсеров при импорте.
"""

# Импортируем базовые классы (всегда доступны)
from .base_real_estate_parser import BaseRealEstateParser, ParserCapabilities, ParsingError
from .parser_registry import ParserRegistry, get_global_registry, register_parser
from .field_mapper import FieldMapper, get_field_mapper

# Список успешно импортированных парсеров
__all__ = [
    # Базовые классы
    'BaseRealEstateParser',
    'ParserCapabilities',
    'ParsingError',

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

# Пытаемся импортировать DomClickParser (требует Playwright для fallback)
try:
    from .domclick_parser import DomClickParser
    __all__.append('DomClickParser')
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"DomClickParser недоступен: {e}")
    DomClickParser = None

# Пытаемся импортировать AvitoParser (требует curl_cffi и nodriver)
try:
    from .avito_parser import AvitoParser
    __all__.append('AvitoParser')
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"AvitoParser недоступен: {e}")
    AvitoParser = None

# Пытаемся импортировать YandexRealtyParser (требует httpx/curl_cffi)
try:
    from .yandex_realty_parser import YandexRealtyParser
    __all__.append('YandexRealtyParser')
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"YandexRealtyParser недоступен: {e}")
    YandexRealtyParser = None

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
