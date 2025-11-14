"""
Базовый интерфейс для всех парсеров недвижимости (абстрактный класс)

Этот модуль определяет единый интерфейс для парсеров разных источников:
- Циан (Cian.ru)
- Домклик (DomClick.ru)
- Авито (Avito.ru) - будущая поддержка
- и другие

Архитектура построена на принципах:
- Strategy Pattern: разные стратегии парсинга для разных сайтов
- Template Method: общая логика в базовом классе
- Dependency Injection: кэш передается извне
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, List, Literal
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ParserCapabilities:
    """
    Возможности конкретного парсера

    Attributes:
        supports_search: Поддерживает ли поиск аналогов
        supports_residential_complex: Поддерживает ли поиск по ЖК
        supports_regions: Список поддерживаемых регионов
        supports_async: Поддерживает ли асинхронный парсинг
        has_api: Есть ли официальное API
        requires_browser: Требуется ли браузер (Playwright)
    """
    supports_search: bool = True
    supports_residential_complex: bool = True
    supports_regions: List[str] = None
    supports_async: bool = False
    has_api: bool = False
    requires_browser: bool = True

    def __post_init__(self):
        if self.supports_regions is None:
            self.supports_regions = ['spb', 'msk']


class BaseRealEstateParser(ABC):
    """
    Абстрактный базовый класс для всех парсеров недвижимости

    Определяет единый интерфейс для:
    - Парсинга детальной страницы объявления
    - Поиска аналогов по различным критериям
    - Извлечения структурированных данных
    - Работы с кэшем

    Подклассы должны реализовать:
    - _get_page_content() - получение HTML/данных страницы
    - _parse_single_property() - парсинг одного объявления
    - _search_similar_impl() - реализация поиска аналогов
    - get_capabilities() - возможности парсера
    """

    def __init__(self, delay: float = 2.0, cache=None):
        """
        Args:
            delay: Задержка между запросами (секунды)
            cache: Объект кэша (PropertyCache или аналог)
        """
        self.delay = delay
        self.cache = cache
        self.stats = {
            'requests': 0,
            'errors': 0,
            'retries': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }

    # === АБСТРАКТНЫЕ МЕТОДЫ (должны быть реализованы в подклассах) ===

    @abstractmethod
    def _get_page_content(self, url: str) -> Optional[str]:
        """
        Получить содержимое страницы

        Args:
            url: URL страницы

        Returns:
            HTML контент или None при ошибке
        """
        pass

    @abstractmethod
    def _parse_single_property(self, url: str, html: str) -> Dict:
        """
        Парсинг одного объявления из HTML

        Args:
            url: URL объявления
            html: HTML контент страницы

        Returns:
            Словарь с данными объявления (стандартизированный формат)
        """
        pass

    @abstractmethod
    def _search_similar_impl(
        self,
        target_property: Dict,
        limit: int = 20,
        strategy: Literal['same_building', 'same_area', 'citywide'] = 'citywide'
    ) -> List[Dict]:
        """
        Реализация поиска аналогов (специфична для каждого сайта)

        Args:
            target_property: Целевой объект (эталон)
            limit: Максимальное количество результатов
            strategy: Стратегия поиска

        Returns:
            Список объявлений-аналогов
        """
        pass

    @abstractmethod
    def get_capabilities(self) -> ParserCapabilities:
        """
        Получить возможности парсера

        Returns:
            ParserCapabilities с информацией о поддерживаемых функциях
        """
        pass

    @abstractmethod
    def get_source_name(self) -> str:
        """
        Получить название источника

        Returns:
            Название (например, 'cian', 'domclick', 'avito')
        """
        pass

    # === ПУБЛИЧНЫЕ МЕТОДЫ (общие для всех парсеров) ===

    def parse_detail_page(self, url: str) -> Dict:
        """
        Парсинг детальной страницы объявления с кэшированием

        Args:
            url: URL объявления

        Returns:
            Словарь с данными объявления

        Raises:
            ParsingError: При ошибке парсинга
        """
        # Проверяем кэш
        if self.cache:
            cached_data = self.cache.get_property(url)
            if cached_data:
                self.stats['cache_hits'] += 1
                logger.info(f"✅ Cache HIT [{self.get_source_name()}]: {url[:60]}...")
                return cached_data
            else:
                self.stats['cache_misses'] += 1

        logger.info(f"Парсинг [{self.get_source_name()}]: {url}")

        try:
            # Получаем контент
            html = self._get_page_content(url)
            if not html:
                raise ParsingError(f"Не удалось получить контент: {url}")

            # Парсим
            data = self._parse_single_property(url, html)

            # Добавляем метаданные
            data['source'] = self.get_source_name()
            data['url'] = url

            logger.info(f"✓ Успешно спарсен [{self.get_source_name()}]: {data.get('title', 'Без названия')[:50]}")

            # Сохраняем в кэш
            if self.cache:
                self.cache.set_property(url, data, ttl_hours=24)
                logger.debug(f"💾 Сохранено в кэш: {url[:60]}...")

            return data

        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Ошибка при парсинге {url}: {e}", exc_info=True)
            raise ParsingError(f"Ошибка парсинга: {e}") from e

    def search_similar(
        self,
        target_property: Dict,
        limit: int = 20,
        strategy: Literal['same_building', 'same_area', 'citywide'] = 'citywide'
    ) -> List[Dict]:
        """
        Поиск аналогов (публичный метод с валидацией)

        Args:
            target_property: Целевой объект
            limit: Максимальное количество результатов
            strategy: Стратегия поиска:
                - 'same_building': В том же ЖК
                - 'same_area': В том же районе/у того же метро
                - 'citywide': По всему городу

        Returns:
            Список объявлений-аналогов
        """
        capabilities = self.get_capabilities()

        if not capabilities.supports_search:
            logger.warning(f"Парсер {self.get_source_name()} не поддерживает поиск")
            return []

        if strategy == 'same_building' and not capabilities.supports_residential_complex:
            logger.warning(f"Парсер {self.get_source_name()} не поддерживает поиск по ЖК, переключаюсь на citywide")
            strategy = 'citywide'

        logger.info(f"Поиск аналогов [{self.get_source_name()}] (стратегия: {strategy}, лимит: {limit})")

        try:
            results = self._search_similar_impl(target_property, limit, strategy)
            logger.info(f"✓ Найдено {len(results)} аналогов [{self.get_source_name()}]")
            return results
        except Exception as e:
            logger.error(f"Ошибка поиска аналогов [{self.get_source_name()}]: {e}")
            return []

    def get_stats(self) -> Dict:
        """Получить статистику работы парсера"""
        return {
            **self.stats,
            'source': self.get_source_name(),
            'capabilities': self.get_capabilities().__dict__
        }

    def reset_stats(self):
        """Сбросить статистику"""
        self.stats = {
            'requests': 0,
            'errors': 0,
            'retries': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }


class ParsingError(Exception):
    """Ошибка парсинга"""
    pass
