"""
Адаптер для существующих парсеров Циана к новому интерфейсу

Этот модуль оборачивает существующие парсеры (PlaywrightParser, AsyncPlaywrightParser)
и адаптирует их к новому интерфейсу BaseRealEstateParser.

Паттерн: Adapter (Wrapper)
"""

import logging
from typing import Optional, Dict, List, Literal

from .base_real_estate_parser import BaseRealEstateParser, ParserCapabilities
from .playwright_parser import PlaywrightParser as LegacyPlaywrightParser
from .parser_registry import register_parser
from .field_mapper import get_field_mapper

logger = logging.getLogger(__name__)


@register_parser('cian', [r'cian\.ru', r'www\.cian\.ru'])
class CianParser(BaseRealEstateParser):
    """
    Адаптер для парсера Циана к новому интерфейсу

    Использует существующий PlaywrightParser под капотом,
    но предоставляет унифицированный интерфейс BaseRealEstateParser
    """

    def __init__(self, delay: float = 2.0, cache=None, region: str = 'spb'):
        """
        Args:
            delay: Задержка между запросами
            cache: Объект кэша
            region: Регион ('spb', 'msk')
        """
        super().__init__(delay, cache)
        self.region = region

        # Создаем экземпляр старого парсера
        self._legacy_parser = LegacyPlaywrightParser(
            delay=delay,
            cache=cache,
            region=region
        )

        # Маппер полей (хотя для Циана он почти не нужен)
        self.field_mapper = get_field_mapper('cian')

        logger.info(f"✓ Инициализирован CianParser (регион: {region})")

    def _get_page_content(self, url: str) -> Optional[str]:
        """
        Получить контент страницы (делегируем старому парсеру)

        Args:
            url: URL страницы

        Returns:
            HTML контент
        """
        return self._legacy_parser._get_page_content(url)

    def _parse_single_property(self, url: str, html: str) -> Dict:
        """
        Парсинг одного объявления

        Используем существующую логику parse_detail_page,
        но возвращаем данные напрямую

        Args:
            url: URL объявления
            html: HTML контент (игнорируется, т.к. старый парсер сам получает)

        Returns:
            Данные объявления
        """
        # Старый парсер имеет метод parse_detail_page, который делает всю работу
        # Но он также получает контент сам, поэтому мы просто вызываем его напрямую
        # (игнорируя переданный html, т.к. старый парсер работает через кэш)

        # Обходной путь: используем внутренние методы старого парсера
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, 'lxml')

        data = {
            'url': url,
            'source': 'cian',
            'title': None,
            'price': None,
            'price_raw': None,
            'currency': None,
            'description': None,
            'address': None,
            'residential_complex': None,
            'residential_complex_url': None,
            'metro': [],
            'characteristics': {},
            'images': [],
            'seller': {},
        }

        # JSON-LD данные (приоритет)
        json_ld = self._legacy_parser._extract_json_ld(soup)
        if json_ld:
            logger.info("✓ Используем JSON-LD данные")
            data['title'] = json_ld.get('name')

            offers = json_ld.get('offers', {})
            if offers:
                data['price_raw'] = offers.get('price')
                data['currency'] = offers.get('priceCurrency')
                if data['price_raw']:
                    data['price'] = data['price_raw']

        # Дополняем из HTML
        data = self._legacy_parser._extract_basic_info(soup, data)
        data['characteristics'] = self._legacy_parser._extract_characteristics(soup)
        data['images'] = self._legacy_parser._extract_images(soup)
        data['seller'] = self._legacy_parser._extract_seller_info(soup)

        # Извлекаем ключевые поля из characteristics в корень
        self._legacy_parser._promote_key_fields(data)

        # Извлекаем премиум-характеристики
        self._legacy_parser._extract_premium_features(soup, data)

        return data

    def _search_similar_impl(
        self,
        target_property: Dict,
        limit: int = 20,
        strategy: Literal['same_building', 'same_area', 'citywide'] = 'citywide'
    ) -> List[Dict]:
        """
        Поиск аналогов через старый парсер

        Args:
            target_property: Целевой объект
            limit: Лимит результатов
            strategy: Стратегия поиска

        Returns:
            Список аналогов
        """
        logger.info(f"Поиск аналогов на Циане (стратегия: {strategy})")

        # Преобразуем strategy в вызов соответствующего метода старого парсера
        if strategy == 'same_building':
            # Используем search_similar_in_building
            results = self._legacy_parser.search_similar_in_building(
                target_property,
                limit=limit
            )
        else:
            # Используем search_similar (citywide или same_area)
            results = self._legacy_parser.search_similar(
                target_property,
                limit=limit
            )

        # Добавляем source к каждому результату
        for result in results:
            result['source'] = 'cian'

        return results

    def get_capabilities(self) -> ParserCapabilities:
        """Возможности парсера Циана"""
        return ParserCapabilities(
            supports_search=True,
            supports_residential_complex=True,
            supports_regions=['spb', 'msk'],
            supports_async=True,  # AsyncPlaywrightParser есть
            has_api=False,
            requires_browser=True
        )

    def get_source_name(self) -> str:
        """Название источника"""
        return 'cian'

    def get_stats(self) -> Dict:
        """Получить статистику (объединяем с legacy parser)"""
        base_stats = super().get_stats()
        legacy_stats = self._legacy_parser.get_stats()

        # Объединяем статистику
        return {
            **base_stats,
            'legacy_stats': legacy_stats
        }

    def __del__(self):
        """Деструктор - закрываем браузер старого парсера"""
        if hasattr(self, '_legacy_parser'):
            # Закрываем браузер в legacy parser
            if hasattr(self._legacy_parser, 'close_browser'):
                self._legacy_parser.close_browser()
