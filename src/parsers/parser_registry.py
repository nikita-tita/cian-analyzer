"""
Реестр парсеров недвижимости

Система автоматического выбора парсера на основе URL объявления.
Реализует паттерн Factory + Registry для удобного управления парсерами.

Использование:
    >>> registry = ParserRegistry()
    >>> parser = registry.get_parser('https://www.cian.ru/sale/flat/123/')
    >>> data = parser.parse_detail_page(url)
"""

import re
import logging
from typing import Optional, Type, Dict, List
from urllib.parse import urlparse

from .base_real_estate_parser import BaseRealEstateParser

logger = logging.getLogger(__name__)


class ParserRegistry:
    """
    Реестр парсеров для автоматического выбора по URL

    Принципы работы:
    1. Регистрация парсеров через декоратор @register_parser
    2. Автоопределение источника по URL (домен)
    3. Ленивая инициализация парсеров (создаются только при первом использовании)
    4. Поддержка fallback парсеров
    """

    def __init__(self, cache=None, delay: float = 2.0):
        """
        Args:
            cache: Объект кэша для передачи парсерам
            delay: Задержка между запросами (секунды)
        """
        self.cache = cache
        self.delay = delay
        self._parsers: Dict[str, Type[BaseRealEstateParser]] = {}
        self._parser_instances: Dict[str, BaseRealEstateParser] = {}
        self._url_patterns: Dict[str, List[str]] = {}  # source_name -> [patterns]

    def register(
        self,
        source_name: str,
        parser_class: Type[BaseRealEstateParser],
        url_patterns: List[str]
    ):
        r"""
        Регистрация парсера в реестре

        Args:
            source_name: Уникальное имя источника (например, 'cian', 'domclick')
            parser_class: Класс парсера (наследник BaseRealEstateParser)
            url_patterns: Список регулярных выражений для определения URL
                         Например: [r'cian\.ru', r'www\.cian\.ru']
        """
        if not issubclass(parser_class, BaseRealEstateParser):
            raise ValueError(f"Parser class must inherit from BaseRealEstateParser")

        self._parsers[source_name] = parser_class
        self._url_patterns[source_name] = url_patterns

        logger.info(f"✓ Зарегистрирован парсер: {source_name} (паттерны: {url_patterns})")

    def detect_source(self, url: str) -> Optional[str]:
        """
        Определить источник по URL

        Args:
            url: URL объявления

        Returns:
            Имя источника или None, если не найдено
        """
        # Нормализуем URL
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        # Проверяем все зарегистрированные паттерны
        for source_name, patterns in self._url_patterns.items():
            for pattern in patterns:
                if re.search(pattern, domain, re.IGNORECASE):
                    logger.debug(f"URL {url} → источник: {source_name}")
                    return source_name

        logger.warning(f"Не удалось определить источник для URL: {url}")
        return None

    def get_parser(self, url: Optional[str] = None, source_name: Optional[str] = None) -> Optional[BaseRealEstateParser]:
        """
        Получить парсер для URL или источника

        Args:
            url: URL объявления (автоопределение источника)
            source_name: Явное указание источника (приоритет перед url)

        Returns:
            Экземпляр парсера или None

        Examples:
            >>> parser = registry.get_parser(url='https://cian.ru/...')
            >>> parser = registry.get_parser(source_name='cian')
        """
        # Определяем источник
        if not source_name and url:
            source_name = self.detect_source(url)

        if not source_name:
            logger.error("Не удалось определить источник парсера")
            return None

        # Проверяем, зарегистрирован ли парсер
        if source_name not in self._parsers:
            logger.error(f"Парсер для источника '{source_name}' не зарегистрирован")
            return None

        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Для ЦИАН определяем регион из URL
        region = None
        if source_name == 'cian' and url:
            # Импортируем функцию определения региона из централизованного модуля
            from src.config.regions import detect_region_from_url
            region = detect_region_from_url(url)
            logger.info(f"✓ Регион определен из URL: {region or 'не определен'}")

        # Формируем ключ кэша с учетом региона
        # Для ЦИАН: 'cian_msk' или 'cian_spb'
        # Для других парсеров: source_name
        cache_key = f"{source_name}_{region}" if region else source_name

        # Ленивая инициализация: создаем экземпляр только при первом запросе
        if cache_key not in self._parser_instances:
            parser_class = self._parsers[source_name]

            # Для ЦИАН передаем регион при создании
            if source_name == 'cian' and region:
                parser_instance = parser_class(delay=self.delay, cache=self.cache, region=region)
                logger.info(f"✓ Создан экземпляр парсера: {cache_key} (регион: {region})")
            else:
                parser_instance = parser_class(delay=self.delay, cache=self.cache)
                logger.info(f"✓ Создан экземпляр парсера: {cache_key}")

            self._parser_instances[cache_key] = parser_instance

        return self._parser_instances[cache_key]

    def get_all_sources(self) -> List[str]:
        """
        Получить список всех зарегистрированных источников

        Returns:
            Список имен источников
        """
        return list(self._parsers.keys())

    def get_parser_info(self, source_name: str) -> Optional[Dict]:
        """
        Получить информацию о парсере

        Args:
            source_name: Имя источника

        Returns:
            Словарь с информацией или None
        """
        parser = self.get_parser(source_name=source_name)
        if not parser:
            return None

        capabilities = parser.get_capabilities()
        return {
            'source': source_name,
            'url_patterns': self._url_patterns.get(source_name, []),
            'capabilities': capabilities.__dict__,
            'stats': parser.get_stats()
        }

    def get_all_parsers_info(self) -> Dict[str, Dict]:
        """
        Получить информацию о всех парсерах

        Returns:
            Словарь {source_name: info}
        """
        return {
            source: self.get_parser_info(source)
            for source in self.get_all_sources()
        }


# === ГЛОБАЛЬНЫЙ РЕЕСТР ===
# Создаем единственный экземпляр реестра для всего приложения
_global_registry: Optional[ParserRegistry] = None


def get_global_registry(cache=None, delay: float = 2.0) -> ParserRegistry:
    """
    Получить глобальный реестр парсеров (Singleton)

    Args:
        cache: Объект кэша (используется только при первом создании)
        delay: Задержка между запросами

    Returns:
        Глобальный экземпляр ParserRegistry
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = ParserRegistry(cache=cache, delay=delay)
        logger.info("✓ Создан глобальный реестр парсеров")
    return _global_registry


def register_parser(source_name: str, url_patterns: List[str]):
    r"""
    Декоратор для автоматической регистрации парсера в глобальном реестре

    Args:
        source_name: Имя источника
        url_patterns: Паттерны URL

    Example:
        @register_parser('cian', [r'cian\.ru'])
        class CianParser(BaseRealEstateParser):
            ...
    """
    def decorator(parser_class: Type[BaseRealEstateParser]):
        registry = get_global_registry()
        registry.register(source_name, parser_class, url_patterns)
        return parser_class
    return decorator
