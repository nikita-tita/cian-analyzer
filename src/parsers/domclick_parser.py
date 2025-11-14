"""
Парсер для DomClick.ru (Домклик - сервис Сбербанка)

Особенности Домклика:
- React SPA приложение
- REST API для поиска и детальных данных
- Защита от ботов (используется BrowserPool)
- Интеграция с ипотекой Сбербанка

Стратегия парсинга:
1. Использование REST API через requests (быстро, эффективно)
2. Fallback на Playwright для обхода защиты
3. Извлечение данных из window.__INITIAL_STATE__ если API недоступен
"""

import json
import logging
import re
import time
import requests
from typing import Optional, Dict, List, Literal
from bs4 import BeautifulSoup
from urllib.parse import urljoin, parse_qs, urlparse

from .base_real_estate_parser import BaseRealEstateParser, ParserCapabilities, ParsingError
from .field_mapper import get_field_mapper
from .parser_registry import register_parser

logger = logging.getLogger(__name__)

# Попытка импортировать Playwright (опционально)
try:
    from .browser_pool import BrowserPool
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("BrowserPool недоступен - Playwright функции отключены")


# Маппинг регионов в коды Домклика
REGION_CODES = {
    'spb': '78000000000',  # Санкт-Петербург
    'msk': '77000000000',  # Москва
}


@register_parser('domclick', [r'domclick\.ru', r'www\.domclick\.ru'])
class DomClickParser(BaseRealEstateParser):
    """
    Парсер для DomClick.ru с поддержкой API

    Использует:
    - REST API Домклика (основной метод)
    - BrowserPool для случаев когда нужен Playwright
    - Кэширование результатов
    """

    def __init__(self, delay: float = 2.0, cache=None, region: str = 'spb', use_api: bool = True):
        """
        Args:
            delay: Задержка между запросами
            cache: Объект кэша
            region: Регион ('spb', 'msk')
            use_api: Использовать API (быстрее) или Playwright
        """
        super().__init__(delay, cache)
        self.region = region
        self.region_code = REGION_CODES.get(region, REGION_CODES['spb'])
        self.use_api = use_api

        self.base_url = "https://domclick.ru"
        self.api_base = "https://domclick.ru/api"

        # BrowserPool (ленивая инициализация)
        self.browser_pool: Optional[BrowserPool] = None

        # HTTP сессия с правильными заголовками
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
            'Referer': 'https://domclick.ru/',
            'Origin': 'https://domclick.ru',
        })

        # Маппер полей
        self.field_mapper = get_field_mapper('domclick')

        logger.info(f"✓ Инициализирован DomClickParser (регион: {region}, API: {use_api})")

    def _init_browser_pool(self):
        """Ленивая инициализация BrowserPool"""
        if not PLAYWRIGHT_AVAILABLE:
            logger.warning("BrowserPool недоступен")
            return

        if not self.browser_pool:
            self.browser_pool = BrowserPool(max_browsers=3)
            self.browser_pool.start()
            logger.info("✓ BrowserPool инициализирован")

    def _close_browser_pool(self):
        """Закрытие BrowserPool"""
        if self.browser_pool:
            self.browser_pool.shutdown()
            self.browser_pool = None

    def __del__(self):
        """Деструктор"""
        self._close_browser_pool()

    # ===== ОСНОВНЫЕ МЕТОДЫ ПАРСИНГА =====

    def _get_page_content(self, url: str) -> Optional[str]:
        """
        Получить HTML контент страницы

        Args:
            url: URL страницы

        Returns:
            HTML контент или None
        """
        if self.use_api:
            # Пытаемся через API
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                time.sleep(self.delay)
                return response.text
            except Exception as e:
                logger.warning(f"API request failed: {e}, falling back to Playwright")

        # Fallback на Playwright
        return self._get_page_with_playwright(url)

    def _get_page_with_playwright(self, url: str) -> Optional[str]:
        """Получить страницу через Playwright"""
        if not PLAYWRIGHT_AVAILABLE:
            logger.error("Playwright недоступен для получения страницы")
            return None

        self._init_browser_pool()

        try:
            browser, context = self.browser_pool.acquire()

            page = context.new_page()

            # Блокируем ненужные ресурсы
            page.route("**/*.{png,jpg,jpeg,gif,svg,woff,woff2,ttf,ico}",
                      lambda route: route.abort())

            logger.info(f"Загрузка через Playwright: {url}")
            page.goto(url, wait_until='networkidle', timeout=30000)

            html = page.content()
            page.close()

            self.browser_pool.release(browser)

            return html

        except Exception as e:
            logger.error(f"Ошибка Playwright: {e}")
            return None

    def _parse_single_property(self, url: str, html: str) -> Dict:
        """
        Парсинг одного объявления

        Args:
            url: URL объявления
            html: HTML контент

        Returns:
            Словарь с данными (нормализованный формат)
        """
        data = {'url': url, 'source': 'domclick'}

        # Пытаемся извлечь ID из URL
        offer_id = self._extract_offer_id(url)

        if offer_id and self.use_api:
            # Используем API для получения данных
            api_data = self._fetch_offer_by_api(offer_id)
            if api_data:
                data.update(api_data)
                return data

        # Fallback: парсинг HTML
        soup = BeautifulSoup(html, 'lxml')

        # Пытаемся извлечь из __INITIAL_STATE__ или __NEXT_DATA__
        initial_state = self._extract_initial_state(html)
        if initial_state:
            data.update(self._parse_from_initial_state(initial_state))

        # Дополняем из JSON-LD
        json_ld = self._extract_json_ld(soup)
        if json_ld:
            data.update(self._parse_from_json_ld(json_ld))

        # Fallback HTML парсинг
        if not data.get('title'):
            data.update(self._parse_from_html(soup))

        return data

    def _extract_offer_id(self, url: str) -> Optional[str]:
        """
        Извлечь ID объявления из URL

        Args:
            url: URL объявления

        Returns:
            ID или None
        """
        # Паттерны URL Домклика:
        # https://domclick.ru/card/sale__flat__12345 (двойное подчеркивание)
        # https://domclick.ru/card/sale_flat_12345 (одинарное подчеркивание)
        # https://domclick.ru/offers/12345
        # https://domclick.ru/card/12345

        patterns = [
            r'/card/sale_+flat_+(\d+)',  # Гибкий паттерн для одного или нескольких подчеркиваний
            r'/card/[^/]*_(\d+)',  # Любой префикс с подчеркиванием
            r'/card/(\d+)',  # Только ID
            r'/offers/(\d+)',
            r'/object/(\d+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        logger.warning(f"Не удалось извлечь ID из URL: {url}")
        return None

    def _fetch_offer_by_api(self, offer_id: str) -> Optional[Dict]:
        """
        Получить данные объявления через API

        Args:
            offer_id: ID объявления

        Returns:
            Данные или None
        """
        # Примерные API endpoints Домклика (могут отличаться)
        api_urls = [
            f"{self.api_base}/v1/offers/{offer_id}",
            f"{self.api_base}/offers/{offer_id}",
            f"{self.base_url}/api/cards/{offer_id}",
        ]

        for api_url in api_urls:
            try:
                logger.debug(f"Пробуем API: {api_url}")
                response = self.session.get(api_url, timeout=10)

                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"✓ Данные получены через API: {api_url}")
                    return self._normalize_api_response(data)

            except Exception as e:
                logger.debug(f"API {api_url} не сработал: {e}")
                continue

        logger.warning(f"Все API endpoints не сработали для {offer_id}")
        return None

    def _normalize_api_response(self, api_data: Dict) -> Dict:
        """
        Нормализация ответа API в наш формат

        Args:
            api_data: Сырые данные из API

        Returns:
            Нормализованные данные
        """
        # Используем маппер полей
        return self.field_mapper.transform(api_data)

    def _extract_initial_state(self, html: str) -> Optional[Dict]:
        """
        Извлечь данные из window.__INITIAL_STATE__ или __NEXT_DATA__

        Args:
            html: HTML контент

        Returns:
            Данные или None
        """
        patterns = [
            (r'window\.__INITIAL_STATE__\s*=\s*(\{.+?\});', '__INITIAL_STATE__'),
            (r'<script id="__NEXT_DATA__"[^>]*>(\{.+?\})</script>', '__NEXT_DATA__'),
            (r'window\.__PRELOADED_STATE__\s*=\s*(\{.+?\});', '__PRELOADED_STATE__'),
        ]

        for pattern, name in patterns:
            try:
                match = re.search(pattern, html, re.DOTALL)
                if match:
                    data = json.loads(match.group(1))
                    logger.info(f"✓ Извлечены данные из {name}")
                    return data
            except (json.JSONDecodeError, AttributeError) as e:
                logger.debug(f"Ошибка извлечения {name}: {e}")

        return None

    def _parse_from_initial_state(self, state: Dict) -> Dict:
        """Парсинг из __INITIAL_STATE__"""
        data = {}

        # Пытаемся найти данные объявления в разных местах структуры
        possible_paths = [
            ('props', 'pageProps', 'offer'),
            ('offer',),
            ('card',),
            ('data', 'offer'),
        ]

        offer = None
        for path in possible_paths:
            current = state
            for key in path:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    current = None
                    break
            if current:
                offer = current
                break

        if offer:
            data.update(self._extract_offer_fields(offer))

        return data

    def _extract_offer_fields(self, offer: Dict) -> Dict:
        """Извлечь поля из объекта offer"""
        return {
            'title': offer.get('title') or offer.get('name'),
            'description': offer.get('description'),
            'price': offer.get('price') or self._get_nested(offer, 'bargainTerms.price'),
            'currency': offer.get('currency', 'RUB'),
            'total_area': offer.get('totalArea') or offer.get('area'),
            'living_area': offer.get('livingArea'),
            'kitchen_area': offer.get('kitchenArea'),
            'rooms': offer.get('roomsCount') or offer.get('rooms'),
            'floor': offer.get('floor') or offer.get('floorNumber'),
            'floor_total': offer.get('floorsTotal') or offer.get('floorsCount'),
            'address': self._get_nested(offer, 'location.address') or offer.get('address'),
            'residential_complex': self._get_nested(offer, 'building.name'),
            'build_year': self._get_nested(offer, 'building.buildYear'),
            'house_type': self._get_nested(offer, 'building.type'),
            'images': offer.get('photos') or offer.get('images') or [],
        }

    def _get_nested(self, obj: Dict, path: str, default=None):
        """Получить вложенное значение по пути"""
        keys = path.split('.')
        current = obj
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current

    def _extract_json_ld(self, soup: BeautifulSoup) -> Optional[Dict]:
        """Извлечь JSON-LD"""
        try:
            json_ld_script = soup.find('script', type='application/ld+json')
            if json_ld_script and json_ld_script.string:
                return json.loads(json_ld_script.string)
        except Exception as e:
            logger.debug(f"JSON-LD не найден: {e}")
        return None

    def _parse_from_json_ld(self, json_ld: Dict) -> Dict:
        """Парсинг из JSON-LD"""
        data = {}

        if json_ld.get('@type') in ['Product', 'RealEstateListing', 'Apartment']:
            data['title'] = json_ld.get('name')
            data['description'] = json_ld.get('description')

            if 'offers' in json_ld:
                offers = json_ld['offers']
                if isinstance(offers, dict):
                    data['price'] = offers.get('price')
                    data['currency'] = offers.get('priceCurrency', 'RUB')

        return data

    def _parse_from_html(self, soup: BeautifulSoup) -> Dict:
        """Fallback HTML парсинг"""
        data = {}

        # Заголовок
        h1 = soup.find('h1')
        if h1:
            data['title'] = h1.get_text(strip=True)

        # Цена
        price_elem = soup.find(class_=re.compile(r'price', re.I))
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            data['price'] = self._extract_number(price_text)

        # Описание
        desc_elem = soup.find(class_=re.compile(r'description', re.I))
        if desc_elem:
            data['description'] = desc_elem.get_text(strip=True)

        return data

    def _extract_number(self, text: str) -> Optional[float]:
        """Извлечь число из текста"""
        if not text:
            return None
        cleaned = re.sub(r'[^\d.]', '', text)
        try:
            return float(cleaned)
        except ValueError:
            return None

    # ===== ПОИСК АНАЛОГОВ =====

    def _search_similar_impl(
        self,
        target_property: Dict,
        limit: int = 20,
        strategy: Literal['same_building', 'same_area', 'citywide'] = 'citywide'
    ) -> List[Dict]:
        """
        Поиск аналогов через API Домклика

        Args:
            target_property: Целевой объект
            limit: Лимит результатов
            strategy: Стратегия поиска

        Returns:
            Список аналогов
        """
        logger.info(f"Поиск аналогов на Домклике (стратегия: {strategy})")

        # Формируем параметры поиска
        search_params = self._build_search_params(target_property, strategy)

        # Выполняем поиск через API
        results = self._search_via_api(search_params, limit)

        logger.info(f"✓ Найдено {len(results)} аналогов на Домклике")
        return results

    def _build_search_params(self, target: Dict, strategy: str) -> Dict:
        """
        Построить параметры поиска для API

        Args:
            target: Целевой объект
            strategy: Стратегия

        Returns:
            Параметры для API
        """
        params = {
            'region': self.region_code,
            'deal_type': 'sale',
            'category': 'flat',
        }

        # Базовые параметры
        price = target.get('price')
        area = target.get('total_area')
        rooms = target.get('rooms')

        if price:
            # ±30% от цены
            price_min = price * 0.7
            price_max = price * 1.3
            params['priceMin'] = int(price_min)
            params['priceMax'] = int(price_max)

        if area:
            # ±20% от площади
            area_min = area * 0.8
            area_max = area * 1.2
            params['areaMin'] = int(area_min)
            params['areaMax'] = int(area_max)

        if rooms and rooms != 'студия':
            params['roomsCount'] = rooms

        # Стратегия same_building
        if strategy == 'same_building' and target.get('residential_complex'):
            params['residentialComplex'] = target['residential_complex']

        # Стратегия same_area
        if strategy == 'same_area' and target.get('metro'):
            metro = target['metro']
            if isinstance(metro, list) and metro:
                params['metro'] = metro[0]

        return params

    def _search_via_api(self, params: Dict, limit: int) -> List[Dict]:
        """
        Выполнить поиск через API

        Args:
            params: Параметры поиска
            limit: Лимит результатов

        Returns:
            Список результатов
        """
        # Примерные API endpoints для поиска
        search_urls = [
            f"{self.api_base}/v1/search/offers",
            f"{self.api_base}/search",
            f"{self.base_url}/api/search/v1/offers",
        ]

        params['limit'] = limit
        params['offset'] = 0

        for search_url in search_urls:
            try:
                logger.debug(f"Поиск через API: {search_url}")
                response = self.session.get(search_url, params=params, timeout=30)

                if response.status_code == 200:
                    data = response.json()
                    results = self._extract_search_results(data)

                    if results:
                        logger.info(f"✓ Поиск успешен через {search_url}")
                        return results[:limit]

            except Exception as e:
                logger.debug(f"API {search_url} не сработал: {e}")
                continue

        logger.warning("Все API endpoints поиска не сработали")
        return []

    def _extract_search_results(self, api_response: Dict) -> List[Dict]:
        """
        Извлечь результаты из ответа API поиска

        Args:
            api_response: Ответ API

        Returns:
            Список результатов
        """
        # Ищем результаты в разных местах структуры
        possible_paths = [
            ('offers',),
            ('results',),
            ('data', 'offers'),
            ('items',),
        ]

        offers = None
        for path in possible_paths:
            current = api_response
            for key in path:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    current = None
                    break
            if current and isinstance(current, list):
                offers = current
                break

        if not offers:
            return []

        # Нормализуем каждый результат
        results = []
        for offer in offers:
            try:
                normalized = self._normalize_api_response(offer)
                normalized['source'] = 'domclick'
                results.append(normalized)
            except Exception as e:
                logger.warning(f"Ошибка нормализации результата: {e}")

        return results

    # ===== ВОЗМОЖНОСТИ =====

    def get_capabilities(self) -> ParserCapabilities:
        """Возможности парсера"""
        return ParserCapabilities(
            supports_search=True,
            supports_residential_complex=True,
            supports_regions=['msk', 'spb'],
            supports_async=False,
            has_api=True,
            requires_browser=not self.use_api  # API не требует браузер
        )

    def get_source_name(self) -> str:
        """Название источника"""
        return 'domclick'
