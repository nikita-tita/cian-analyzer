"""
Парсер для Yandex Real Estate (realty.yandex.ru)

Особенности Яндекс Недвижимости:
- GraphQL API
- React SPA приложение
- Средняя защита (Yandex Cloud Shield)
- Хорошо структурированные данные

Стратегия парсинга:
1. GraphQL API (через httpx или curl_cffi)
2. Playwright для поиска и детальных страниц
3. Fallback на HTML парсинг
"""

import json
import logging
import re
import time
from typing import Optional, Dict, List, Literal
from bs4 import BeautifulSoup
from urllib.parse import urljoin, parse_qs, urlparse

from .base_real_estate_parser import BaseRealEstateParser, ParserCapabilities, ParsingError
from .field_mapper import get_field_mapper
from .parser_registry import register_parser

logger = logging.getLogger(__name__)

# Импорт стратегий
try:
    from .strategies.httpx_strategy import HttpxStrategy
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

try:
    from .strategies.curl_cffi_strategy import CurlCffiStrategy
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False

try:
    from .strategies.playwright_stealth_strategy import PlaywrightStealthStrategy
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


@register_parser('yandex', [r'realty\.yandex\.ru', r'yandex\.ru/realty'])
class YandexRealtyParser(BaseRealEstateParser):
    """
    Парсер для Yandex Realty с поддержкой GraphQL API

    Использует:
    - GraphQL API через httpx (быстро, эффективно)
    - Playwright для fallback
    - HTML парсинг для резервного варианта
    """

    def __init__(
        self,
        delay: float = 2.0,
        cache=None,
        region: str = 'spb',
        use_graphql: bool = True
    ):
        """
        Args:
            delay: Задержка между запросами
            cache: Объект кэша
            region: Регион ('spb', 'msk')
            use_graphql: Использовать GraphQL API (рекомендуется)
        """
        super().__init__(delay, cache)
        self.region = region
        self.use_graphql = use_graphql

        self.base_url = "https://realty.yandex.ru"
        self.graphql_url = "https://realty.yandex.ru/graphql"

        # Маппинг регионов в region_id Яндекса
        self.region_codes = {
            'spb': '2',      # Санкт-Петербург
            'msk': '1',      # Москва
        }
        self.region_id = self.region_codes.get(region, '2')

        # Стратегии (ленивая инициализация)
        self.httpx: Optional[HttpxStrategy] = None
        self.curl_cffi: Optional[CurlCffiStrategy] = None
        self.playwright: Optional[PlaywrightStealthStrategy] = None

        # Маппер полей
        self.field_mapper = get_field_mapper('yandex')

        logger.info(f"✓ Инициализирован YandexRealtyParser (регион: {region}, GraphQL: {use_graphql})")

    def _init_httpx(self):
        """Ленивая инициализация httpx"""
        if not HTTPX_AVAILABLE:
            logger.warning("httpx недоступен")
            return

        if not self.httpx:
            self.httpx = HttpxStrategy(
                timeout=30,
                enable_http2=True
            )
            logger.info("✓ httpx инициализирован для Yandex")

    def _init_curl_cffi(self):
        """Ленивая инициализация curl_cffi"""
        if not CURL_CFFI_AVAILABLE:
            logger.warning("curl_cffi недоступен")
            return

        if not self.curl_cffi:
            self.curl_cffi = CurlCffiStrategy(
                impersonate='chrome110',
                timeout=30
            )
            logger.info("✓ curl_cffi инициализирован для Yandex")

    def _init_playwright(self):
        """Ленивая инициализация Playwright"""
        if not PLAYWRIGHT_AVAILABLE:
            logger.warning("Playwright недоступен")
            return

        if not self.playwright:
            self.playwright = PlaywrightStealthStrategy(
                headless=True,
                stealth_mode=True,
                timeout=30000
            )
            logger.info("✓ Playwright инициализирован для Yandex")

    # ===== ОСНОВНЫЕ МЕТОДЫ ПАРСИНГА =====

    def _get_page_content(self, url: str) -> Optional[str]:
        """
        Получить HTML контент страницы

        Args:
            url: URL страницы

        Returns:
            HTML контент или None
        """
        if self.use_graphql:
            # Пытаемся через GraphQL API
            offer_id = self._extract_offer_id(url)
            if offer_id:
                graphql_data = self._fetch_via_graphql(offer_id)
                if graphql_data:
                    # Возвращаем JSON как "HTML"
                    return json.dumps(graphql_data)

        # Fallback на Playwright
        return self._get_via_playwright(url)

    def _fetch_via_graphql(self, offer_id: str) -> Optional[Dict]:
        """
        Получить данные через GraphQL API

        Args:
            offer_id: ID объявления

        Returns:
            JSON данные или None
        """
        # Пытаемся сначала через httpx, потом через curl_cffi
        self._init_httpx()

        if self.httpx:
            result = self._execute_graphql_query(offer_id, self.httpx)
            if result:
                return result

        # Fallback на curl_cffi
        self._init_curl_cffi()

        if self.curl_cffi:
            result = self._execute_graphql_query(offer_id, self.curl_cffi)
            if result:
                return result

        logger.warning("⚠️ GraphQL запросы не сработали")
        return None

    def _execute_graphql_query(self, offer_id: str, strategy) -> Optional[Dict]:
        """
        Выполнить GraphQL запрос через заданную стратегию

        Args:
            offer_id: ID объявления
            strategy: Стратегия (httpx или curl_cffi)

        Returns:
            JSON данные или None
        """
        logger.info(f"🔄 GraphQL запрос Yandex для {offer_id}")

        # GraphQL query для получения объявления
        # Это упрощенная версия, реальный query может отличаться
        query = """
        query GetOffer($offerId: ID!) {
            offer(id: $offerId) {
                id
                title
                description
                price {
                    value
                    currency
                }
                area {
                    value
                    unit
                }
                rooms
                floor
                floorsTotal
                address {
                    fullAddress
                }
                location {
                    latitude
                    longitude
                }
                images {
                    url
                }
                characteristics {
                    key
                    value
                }
            }
        }
        """

        variables = {
            "offerId": offer_id
        }

        payload = {
            "query": query,
            "variables": variables
        }

        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': f'https://realty.yandex.ru/offer/{offer_id}',
        }

        try:
            data = strategy.fetch_api(
                self.graphql_url,
                method='POST',
                json=payload,
                headers=headers
            )

            if data and 'data' in data:
                logger.info(f"✓ GraphQL Yandex успешно: {offer_id}")
                return data.get('data', {}).get('offer')
            else:
                logger.warning(f"⚠️ GraphQL вернул пустые данные")
                return None

        except Exception as e:
            logger.error(f"❌ Ошибка GraphQL Yandex: {e}")
            return None

    def _get_via_playwright(self, url: str) -> Optional[str]:
        """
        Получить страницу через Playwright

        Args:
            url: URL страницы

        Returns:
            HTML контент или None
        """
        self._init_playwright()

        if not self.playwright:
            logger.error("Playwright недоступен для Yandex")
            return None

        try:
            logger.info(f"🔄 Загрузка через Playwright: {url}")

            html = self.playwright.fetch_content(
                url,
                wait_for_selector='[class*="CardContainer"]',
                additional_wait=1000  # ms
            )

            return html

        except Exception as e:
            logger.error(f"❌ Ошибка Playwright: {e}")
            return None

    def _parse_single_property(self, url: str, html: str) -> Dict:
        """
        Парсинг одного объявления

        Args:
            url: URL объявления
            html: HTML контент (или JSON строка от GraphQL)

        Returns:
            Словарь с данными (нормализованный формат)
        """
        data = {'url': url, 'source': 'yandex'}

        # Проверяем, это JSON от GraphQL или HTML
        if html and html.strip().startswith('{'):
            # Это JSON от GraphQL
            try:
                json_data = json.loads(html)
                logger.info("📊 Парсим данные GraphQL Yandex")
                data.update(self._parse_from_graphql(json_data))
                return data
            except json.JSONDecodeError:
                logger.warning("⚠️ Не удалось распарсить JSON, пробуем как HTML")

        # Обычный HTML парсинг
        soup = BeautifulSoup(html, 'lxml')

        # Пытаемся извлечь из window.__INITIAL_STATE__
        initial_state = self._extract_initial_state(html)
        if initial_state:
            data.update(self._parse_from_initial_state(initial_state))

        # JSON-LD
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
        # Паттерны URL Yandex:
        # https://realty.yandex.ru/offer/1234567890/
        # https://realty.yandex.ru/offer/1234567890

        patterns = [
            r'/offer/(\d+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        logger.warning(f"Не удалось извлечь ID из URL: {url}")
        return None

    def _parse_from_graphql(self, graphql_data: Dict) -> Dict:
        """
        Парсинг данных GraphQL

        Args:
            graphql_data: JSON данные из GraphQL

        Returns:
            Нормализованные данные
        """
        # Используем маппер полей
        return self.field_mapper.transform(graphql_data)

    def _extract_initial_state(self, html: str) -> Optional[Dict]:
        """
        Извлечь данные из window.__INITIAL_STATE__

        Args:
            html: HTML контент

        Returns:
            Данные или None
        """
        patterns = [
            r'window\.__INITIAL_STATE__\s*=\s*(\{.+?\});',
            r'window\.INITIAL_STATE\s*=\s*(\{.+?\});',
        ]

        for pattern in patterns:
            try:
                match = re.search(pattern, html, re.DOTALL)
                if match:
                    data = json.loads(match.group(1))
                    logger.info("✓ Извлечены данные из __INITIAL_STATE__")
                    return data
            except Exception as e:
                logger.debug(f"Ошибка извлечения __INITIAL_STATE__: {e}")

        return None

    def _parse_from_initial_state(self, state: Dict) -> Dict:
        """Парсинг из __INITIAL_STATE__"""
        result = {}

        # Структура данных Yandex: state.offer или state.card
        offer = state.get('offer') or state.get('card')

        if offer:
            result.update(self.field_mapper.transform(offer))

        return result

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
        price_elem = soup.find('[class*="Price"]')
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            data['price'] = self._extract_number(price_text)

        # Описание
        desc_elem = soup.find('[class*="Description"]')
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
        Поиск аналогов на Yandex

        Args:
            target_property: Целевой объект
            limit: Лимит результатов
            strategy: Стратегия поиска

        Returns:
            Список аналогов
        """
        logger.info(f"🔍 Поиск аналогов на Яндекс (стратегия: {strategy})")

        # Формируем параметры поиска
        search_params = self._build_search_params(target_property, strategy)

        # Выполняем поиск
        try:
            results = self._search_via_url(search_params, limit)
            logger.info(f"✓ Найдено {len(results)} аналогов на Яндекс")
            return results
        except Exception as e:
            logger.error(f"❌ Ошибка поиска на Яндекс: {e}")
            return []

    def _build_search_params(self, target: Dict, strategy: str) -> Dict:
        """
        Построить параметры поиска для URL Яндекс.Недвижимости

        Args:
            target: Целевой объект
            strategy: Стратегия поиска

        Returns:
            Параметры для URL
        """
        params = {
            'type': 'SELL',
            'category': 'APARTMENT',
            'region': self.region_id,
        }

        # Базовые параметры
        price = target.get('price')
        area = target.get('total_area')
        rooms = target.get('rooms')

        if price:
            # ±30% от цены
            price_min = int(price * 0.7)
            price_max = int(price * 1.3)
            params['priceMin'] = price_min
            params['priceMax'] = price_max

        if area:
            # ±20% от площади
            area_min = int(area * 0.8)
            area_max = int(area * 1.2)
            params['areaMin'] = area_min
            params['areaMax'] = area_max

        if rooms and rooms != 'студия':
            # Количество комнат
            params['roomsTotal'] = rooms
        elif rooms == 'студия':
            params['roomsTotal'] = 'STUDIO'

        # Стратегия поиска
        if strategy == 'same_building':
            # Яндекс может поддерживать поиск по ЖК через ID
            # Но для упрощения используем адрес
            address = target.get('address', '')
            if address:
                parts = [p.strip() for p in address.split(',')]
                if len(parts) >= 2:
                    params['address'] = parts[1]  # Район или улица

        return params

    def _search_via_url(self, params: Dict, limit: int) -> List[Dict]:
        """
        Выполнить поиск через URL с параметрами

        Args:
            params: Параметры поиска
            limit: Лимит результатов

        Returns:
            Список результатов
        """
        # Формируем URL поиска
        region_name = 'sankt-peterburg' if self.region == 'spb' else 'moskva'
        base_search_url = f"https://realty.yandex.ru/{region_name}/kupit/kvartira/"

        # Добавляем параметры
        if params:
            param_str = '&'.join([f"{k}={v}" for k, v in params.items()])
            search_url = f"{base_search_url}?{param_str}"
        else:
            search_url = base_search_url

        logger.info(f"🔍 Поиск Яндекс: {search_url}")

        # Пытаемся получить страницу поиска
        html = self._get_search_page(search_url)

        if not html:
            logger.warning("Не удалось получить страницу поиска Яндекс")
            return []

        # Парсим результаты поиска
        results = self._parse_search_results(html, limit)

        return results

    def _get_search_page(self, url: str) -> Optional[str]:
        """
        Получить страницу поиска

        Args:
            url: URL страницы поиска

        Returns:
            HTML или None
        """
        # Используем Playwright
        return self._get_via_playwright(url)

    def _parse_search_results(self, html: str, limit: int) -> List[Dict]:
        """
        Парсинг результатов поиска из HTML

        Args:
            html: HTML страницы поиска
            limit: Лимит результатов

        Returns:
            Список объявлений
        """
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, 'lxml')
        results = []

        # Ищем карточки объявлений
        # Яндекс использует специфичные классы
        cards = soup.find_all('div', class_=re.compile(r'OffersSerp__list|SeriesCard|OffersSerpItem', re.I))

        if not cards:
            # Альтернативный поиск
            cards = soup.find_all('article') or soup.find_all('div', attrs={'data-testid': re.compile(r'offer', re.I)})

        logger.debug(f"Найдено {len(cards)} карточек на странице поиска")

        for card in cards[:limit]:
            try:
                item = self._parse_search_card(card)
                if item:
                    results.append(item)
            except Exception as e:
                logger.debug(f"Ошибка парсинга карточки: {e}")
                continue

        return results

    def _parse_search_card(self, card) -> Optional[Dict]:
        """
        Парсинг одной карточки из результатов поиска

        Args:
            card: BeautifulSoup элемент карточки

        Returns:
            Данные объявления или None
        """
        data = {'source': 'yandex'}

        # URL
        link = card.find('a', href=re.compile(r'/offer/'))

        if link and link.get('href'):
            url = link['href']
            if not url.startswith('http'):
                url = f"https://realty.yandex.ru{url}"
            data['url'] = url
        else:
            return None

        # Заголовок
        title_elem = card.find('h3') or card.find('h2') or card.find('a', href=re.compile(r'/offer/'))

        if title_elem:
            data['title'] = title_elem.get_text(strip=True)

        # Цена
        price_elem = card.find('span', class_=re.compile(r'price', re.I))

        if price_elem:
            price_text = price_elem.get_text(strip=True)
            data['price'] = self._extract_number(price_text)

        # Характеристики (площадь, комнаты и т.д.)
        # Яндекс группирует характеристики в специальных элементах
        params_container = card.find('div', class_=re.compile(r'param|info|characteristics', re.I))

        if params_container:
            params_text = params_container.get_text(strip=True)

            # Площадь
            area_match = re.search(r'(\d+(?:[.,]\d+)?)\s*м', params_text)
            if area_match:
                data['total_area'] = float(area_match.group(1).replace(',', '.'))

            # Комнаты
            if 'студия' in params_text.lower():
                data['rooms'] = 'студия'
            else:
                rooms_match = re.search(r'(\d+)[- ]?комн', params_text)
                if rooms_match:
                    data['rooms'] = int(rooms_match.group(1))

            # Этаж
            floor_match = re.search(r'(\d+)/(\d+)\s*эт', params_text)
            if floor_match:
                data['floor'] = int(floor_match.group(1))
                data['floor_total'] = int(floor_match.group(2))

        # Адрес
        address_elem = card.find('div', class_=re.compile(r'address|geo|location', re.I))

        if address_elem:
            data['address'] = address_elem.get_text(strip=True)

        # Вычисляем цену за м²
        if data.get('price') and data.get('total_area'):
            data['price_per_sqm'] = round(data['price'] / data['total_area'], 2)

        return data

    # ===== ВОЗМОЖНОСТИ =====

    def get_capabilities(self) -> ParserCapabilities:
        """Возможности парсера"""
        return ParserCapabilities(
            supports_search=True,  # ✅ Реализовано через HTML парсинг
            supports_residential_complex=False,  # Упрощенная поддержка через адрес
            supports_regions=['msk', 'spb'],
            supports_async=True,  # httpx async
            has_api=True,  # GraphQL
            requires_browser=True  # Playwright для поиска
        )

    def get_source_name(self) -> str:
        """Название источника"""
        return 'yandex'
