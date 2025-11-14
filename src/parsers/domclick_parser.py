"""
Парсер для DomClick.ru (Домклик - сервис Сбербанка)

Особенности Домклика:
- React SPA приложение
- Данные часто в window.__INITIAL_STATE__ или JSON endpoints
- Защита от ботов (требуется Playwright)
- API для поиска объявлений
- Интеграция с ипотекой Сбербанка

Стратегия парсинга:
1. Использование внутреннего API Домклика (если доступно)
2. Извлечение данных из window.__INITIAL_STATE__
3. Fallback на HTML парсинг
"""

import json
import logging
import re
from typing import Optional, Dict, List, Literal
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, Page, Browser, TimeoutError as PlaywrightTimeout

from .base_real_estate_parser import BaseRealEstateParser, ParserCapabilities, ParsingError
from .field_mapper import get_field_mapper
from .parser_registry import register_parser

logger = logging.getLogger(__name__)


@register_parser('domclick', [r'domclick\.ru'])
class DomClickParser(BaseRealEstateParser):
    """
    Парсер для DomClick.ru

    Использует:
    - Playwright для обхода защиты
    - Извлечение JSON из window.__INITIAL_STATE__
    - API endpoints где возможно
    """

    def __init__(self, delay: float = 2.0, cache=None, region: str = 'spb'):
        """
        Args:
            delay: Задержка между запросами
            cache: Объект кэша
            region: Регион ('spb', 'msk', и т.д.)
        """
        super().__init__(delay, cache)
        self.region = region
        self.base_url = "https://domclick.ru"
        self.api_base = "https://domclick.ru/api"
        self.browser: Optional[Browser] = None
        self.playwright = None

        # Маппер полей
        self.field_mapper = get_field_mapper('domclick')

    def _init_browser(self):
        """Инициализация браузера"""
        if not self.browser:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-dev-shm-usage'
                ]
            )
            logger.info("✓ Браузер Playwright запущен для DomClick")

    def _close_browser(self):
        """Закрытие браузера"""
        if self.browser:
            self.browser.close()
            self.browser = None
        if self.playwright:
            self.playwright.stop()
            self.playwright = None
            logger.info("✓ Браузер Playwright остановлен")

    def __del__(self):
        """Деструктор - закрываем браузер"""
        self._close_browser()

    def _get_page_content(self, url: str) -> Optional[str]:
        """
        Получить HTML контент страницы через Playwright

        Args:
            url: URL страницы

        Returns:
            HTML контент или None
        """
        self._init_browser()

        try:
            context = self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )

            page = context.new_page()

            # Блокируем ненужные ресурсы
            page.route("**/*.{png,jpg,jpeg,gif,svg,woff,woff2,ttf,ico}", lambda route: route.abort())

            logger.info(f"Загрузка страницы: {url}")
            page.goto(url, wait_until='networkidle', timeout=30000)

            # Ждем загрузки контента
            try:
                page.wait_for_selector('body', timeout=10000)
            except PlaywrightTimeout:
                logger.warning("Timeout ожидания body, продолжаем...")

            html = page.content()
            context.close()

            return html

        except Exception as e:
            logger.error(f"Ошибка получения страницы {url}: {e}")
            return None

    def _extract_initial_state(self, html: str) -> Optional[Dict]:
        """
        Извлечь данные из window.__INITIAL_STATE__

        Многие React SPA хранят данные в глобальной переменной

        Args:
            html: HTML контент

        Returns:
            Словарь с данными или None
        """
        try:
            # Ищем паттерн window.__INITIAL_STATE__ = {...}
            pattern = r'window\.__INITIAL_STATE__\s*=\s*(\{.+?\});'
            match = re.search(pattern, html, re.DOTALL)

            if match:
                json_str = match.group(1)
                data = json.loads(json_str)
                logger.info("✓ Извлечены данные из __INITIAL_STATE__")
                return data

            # Альтернативный паттерн
            pattern2 = r'__NEXT_DATA__\s*=\s*(\{.+?\})</script>'
            match2 = re.search(pattern2, html, re.DOTALL)

            if match2:
                json_str = match2.group(1)
                data = json.loads(json_str)
                logger.info("✓ Извлечены данные из __NEXT_DATA__")
                return data

        except json.JSONDecodeError as e:
            logger.warning(f"Ошибка парсинга JSON из __INITIAL_STATE__: {e}")
        except Exception as e:
            logger.warning(f"Ошибка извлечения __INITIAL_STATE__: {e}")

        return None

    def _parse_single_property(self, url: str, html: str) -> Dict:
        """
        Парсинг одного объявления из HTML

        Args:
            url: URL объявления
            html: HTML контент

        Returns:
            Словарь с данными (в формате Домклика, будет преобразован маппером)
        """
        soup = BeautifulSoup(html, 'lxml')

        data = {
            'url': url,
            'source': 'domclick',
        }

        # Пытаемся извлечь из __INITIAL_STATE__
        initial_state = self._extract_initial_state(html)
        if initial_state:
            # Структура зависит от того, как Домклик хранит данные
            # Обычно это что-то вроде: __INITIAL_STATE__.property или .offer
            data.update(self._parse_from_initial_state(initial_state))
        else:
            # Fallback: парсинг HTML
            logger.info("Извлечение данных из HTML (fallback)")
            data.update(self._parse_from_html(soup))

        # JSON-LD (если есть)
        json_ld = self._extract_json_ld_domclick(soup)
        if json_ld:
            data.update(self._parse_from_json_ld(json_ld))

        return data

    def _parse_from_initial_state(self, state: Dict) -> Dict:
        """
        Парсинг данных из __INITIAL_STATE__

        Args:
            state: Объект __INITIAL_STATE__

        Returns:
            Извлеченные данные
        """
        data = {}

        # Пытаемся найти данные объявления
        # Структура может быть разной, проверяем распространенные варианты
        if 'offer' in state:
            offer = state['offer']
            data.update(self._extract_offer_data(offer))
        elif 'property' in state:
            prop = state['property']
            data.update(self._extract_offer_data(prop))
        elif 'pageProps' in state and 'offer' in state['pageProps']:
            offer = state['pageProps']['offer']
            data.update(self._extract_offer_data(offer))

        return data

    def _extract_offer_data(self, offer: Dict) -> Dict:
        """
        Извлечь данные из объекта offer

        Args:
            offer: Объект с данными объявления

        Returns:
            Словарь с данными
        """
        data = {}

        # Основные поля (примерная структура Домклика)
        field_mappings = {
            'id': 'id',
            'title': 'title',
            'description': 'description',
            'price': 'bargainTerms.price',
            'totalArea': 'totalArea',
            'livingArea': 'livingArea',
            'kitchenArea': 'kitchenArea',
            'roomsCount': 'roomsCount',
            'floor': 'floorNumber',
            'floorsTotal': 'floorsCount',
            'address': 'location.address',
            'residentialComplex': 'building.name',
            'buildYear': 'building.buildYear',
            'houseType': 'building.type',
        }

        for source_key, target_key in field_mappings.items():
            value = self._get_nested_value(offer, source_key)
            if value is not None:
                data[target_key] = value

        # Метро
        if 'location' in offer and 'undergrounds' in offer['location']:
            metro_list = offer['location']['undergrounds']
            if isinstance(metro_list, list):
                data['location.undergrounds'] = metro_list

        # Изображения
        if 'photos' in offer:
            data['photos'] = offer['photos']

        return data

    def _get_nested_value(self, obj: Dict, path: str):
        """
        Получить значение по вложенному пути (например, 'location.address')

        Args:
            obj: Словарь
            path: Путь к значению

        Returns:
            Значение или None
        """
        keys = path.split('.')
        current = obj

        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None

        return current

    def _parse_from_html(self, soup: BeautifulSoup) -> Dict:
        """
        Fallback парсинг из HTML

        Args:
            soup: BeautifulSoup объект

        Returns:
            Извлеченные данные
        """
        data = {}

        # Заголовок
        title_elem = soup.find('h1')
        if title_elem:
            data['title'] = title_elem.get_text(strip=True)

        # Цена
        price_elem = soup.find(class_=re.compile(r'price', re.I))
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            # Убираем все кроме цифр
            price_clean = re.sub(r'[^\d]', '', price_text)
            if price_clean:
                data['bargainTerms.price'] = price_clean

        # Описание
        desc_elem = soup.find(class_=re.compile(r'description', re.I))
        if desc_elem:
            data['description'] = desc_elem.get_text(strip=True)

        logger.info(f"HTML fallback: извлечено {len(data)} полей")

        return data

    def _extract_json_ld_domclick(self, soup: BeautifulSoup) -> Optional[Dict]:
        """
        Извлечь JSON-LD для Домклика

        Args:
            soup: BeautifulSoup объект

        Returns:
            Данные JSON-LD или None
        """
        try:
            json_ld_script = soup.find('script', type='application/ld+json')
            if json_ld_script and json_ld_script.string:
                return json.loads(json_ld_script.string)
        except (json.JSONDecodeError, AttributeError) as e:
            logger.debug(f"JSON-LD не найден: {e}")

        return None

    def _parse_from_json_ld(self, json_ld: Dict) -> Dict:
        """
        Парсинг данных из JSON-LD

        Args:
            json_ld: JSON-LD данные

        Returns:
            Извлеченные данные
        """
        data = {}

        if json_ld.get('@type') == 'Product' or json_ld.get('@type') == 'RealEstateListing':
            data['title'] = json_ld.get('name')
            data['description'] = json_ld.get('description')

            if 'offers' in json_ld:
                offers = json_ld['offers']
                if isinstance(offers, dict):
                    data['bargainTerms.price'] = offers.get('price')
                    data['bargainTerms.currency'] = offers.get('priceCurrency', 'RUB')

        return data

    def _search_similar_impl(
        self,
        target_property: Dict,
        limit: int = 20,
        strategy: Literal['same_building', 'same_area', 'citywide'] = 'citywide'
    ) -> List[Dict]:
        """
        Поиск аналогов на Домклике

        Args:
            target_property: Целевой объект
            limit: Лимит результатов
            strategy: Стратегия поиска

        Returns:
            Список аналогов
        """
        logger.warning("Поиск на Домклике пока не реализован (требуется изучение API)")

        # TODO: Реализовать поиск через API Домклика
        # Примерный endpoint: https://domclick.ru/api/search/v1/offers
        # Параметры: city, rooms, priceMin, priceMax, areaMin, areaMax, и т.д.

        return []

    def get_capabilities(self) -> ParserCapabilities:
        """Возможности парсера Домклика"""
        return ParserCapabilities(
            supports_search=False,  # Пока не реализовано
            supports_residential_complex=False,
            supports_regions=['msk', 'spb'],
            supports_async=False,
            has_api=True,
            requires_browser=True
        )

    def get_source_name(self) -> str:
        """Название источника"""
        return 'domclick'
