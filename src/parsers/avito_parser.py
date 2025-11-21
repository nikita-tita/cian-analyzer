"""
Парсер для Avito.ru (Авито Недвижимость)

Особенности Авито:
- Очень сильная защита (DataDome)
- React SPA приложение
- Мобильное API доступно
- Требует обход капчи

Стратегия парсинга:
1. Мобильное API (через curl_cffi с Android User-Agent)
2. Nodriver (обход DataDome)
3. Proxy rotation + Nodriver (последняя попытка)
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
    from .strategies.curl_cffi_strategy import CurlCffiStrategy
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False

try:
    from .strategies.nodriver_strategy import NodriverStrategy
    NODRIVER_AVAILABLE = True
except ImportError:
    NODRIVER_AVAILABLE = False


@register_parser('avito', [r'avito\.ru', r'www\.avito\.ru'])
class AvitoParser(BaseRealEstateParser):
    """
    Парсер для Avito.ru с поддержкой множественных стратегий

    Использует:
    - Мобильное API через curl_cffi (быстро, эффективно)
    - Nodriver для обхода DataDome
    - Proxy rotation (опционально)
    """

    def __init__(
        self,
        delay: float = 2.0,
        cache=None,
        region: str = 'spb',
        use_mobile_api: bool = True
    ):
        """
        Args:
            delay: Задержка между запросами
            cache: Объект кэша
            region: Регион ('spb', 'msk')
            use_mobile_api: Использовать мобильное API (рекомендуется)
        """
        super().__init__(delay, cache)
        self.region = region
        self.use_mobile_api = use_mobile_api

        self.base_url = "https://www.avito.ru"
        self.mobile_api_base = "https://m.avito.ru/api"

        # Маппинг регионов
        self.region_codes = {
            'spb': 'sankt-peterburg',
            'msk': 'moskva',
        }
        self.region_slug = self.region_codes.get(region, 'sankt-peterburg')

        # Стратегии (ленивая инициализация)
        self.curl_cffi: Optional[CurlCffiStrategy] = None
        self.nodriver: Optional[NodriverStrategy] = None

        # Маппер полей
        self.field_mapper = get_field_mapper('avito')

        logger.info(f"✓ Инициализирован AvitoParser (регион: {region}, mobile_api: {use_mobile_api})")

    def _init_curl_cffi(self):
        """Ленивая инициализация curl_cffi"""
        if not CURL_CFFI_AVAILABLE:
            logger.warning("curl_cffi недоступен")
            return

        if not self.curl_cffi:
            # Используем Android User-Agent для мобильного API
            self.curl_cffi = CurlCffiStrategy(
                impersonate='chrome110',  # Имитируем Chrome
                timeout=30
            )
            logger.info("✓ curl_cffi инициализирован для Avito")

    def _init_nodriver(self):
        """Ленивая инициализация Nodriver"""
        if not NODRIVER_AVAILABLE:
            logger.warning("Nodriver недоступен")
            return

        if not self.nodriver:
            self.nodriver = NodriverStrategy(
                headless=False,  # Для Avito лучше работает не-headless
                timeout=30
            )
            logger.info("✓ Nodriver инициализирован для Avito")

    # ===== ОСНОВНЫЕ МЕТОДЫ ПАРСИНГА =====

    def _get_page_content(self, url: str) -> Optional[str]:
        """
        Получить HTML контент страницы

        Args:
            url: URL страницы

        Returns:
            HTML контент или None
        """
        if self.use_mobile_api:
            # Пытаемся через мобильное API
            offer_id = self._extract_offer_id(url)
            if offer_id:
                mobile_html = self._get_via_mobile_api(offer_id)
                if mobile_html:
                    return mobile_html

        # Fallback на Nodriver
        return self._get_via_nodriver(url)

    def _get_via_mobile_api(self, offer_id: str) -> Optional[str]:
        """
        Получить данные через мобильное API

        Args:
            offer_id: ID объявления

        Returns:
            "HTML" (JSON данные преобразованные в HTML-подобную структуру)
        """
        self._init_curl_cffi()

        if not self.curl_cffi:
            return None

        # Мобильный API endpoint
        api_url = f"{self.mobile_api_base}/1/items/{offer_id}"

        logger.info(f"🔄 Запрос к мобильному API Avito: {api_url}")

        # Заголовки для мобильного API
        headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Mobile Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'ru-RU,ru;q=0.9',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': f'https://m.avito.ru/{self.region_slug}/kvartiry/{offer_id}',
        }

        try:
            data = self.curl_cffi.fetch_api(api_url, headers=headers)

            if data:
                logger.info(f"✓ Мобильное API Avito успешно: {offer_id}")
                # Сохраняем JSON в специальном формате для парсинга
                return json.dumps(data)
            else:
                logger.warning(f"⚠️ Мобильное API не вернуло данные")
                return None

        except Exception as e:
            logger.error(f"❌ Ошибка мобильного API Avito: {e}")
            return None

    def _get_via_nodriver(self, url: str) -> Optional[str]:
        """
        Получить страницу через Nodriver (обход DataDome)

        Args:
            url: URL страницы

        Returns:
            HTML контент или None
        """
        self._init_nodriver()

        if not self.nodriver:
            logger.error("Nodriver недоступен для Avito")
            return None

        try:
            logger.info(f"🔄 Загрузка через Nodriver (обход DataDome): {url}")

            html = self.nodriver.fetch_content(
                url,
                wait_for_selector='[data-marker="item-view"]',
                additional_wait=3  # Дополнительное ожидание для Avito
            )

            return html

        except Exception as e:
            logger.error(f"❌ Ошибка Nodriver: {e}")
            return None

    def _parse_single_property(self, url: str, html: str) -> Dict:
        """
        Парсинг одного объявления

        Args:
            url: URL объявления
            html: HTML контент (или JSON строка от мобильного API)

        Returns:
            Словарь с данными (нормализованный формат)
        """
        data = {'url': url, 'source': 'avito'}

        # Проверяем, это JSON от мобильного API или HTML
        if html and html.strip().startswith('{'):
            # Это JSON от мобильного API
            try:
                json_data = json.loads(html)
                logger.info("📱 Парсим данные мобильного API Avito")
                data.update(self._parse_from_mobile_api(json_data))
                return data
            except json.JSONDecodeError:
                logger.warning("⚠️ Не удалось распарсить JSON, пробуем как HTML")

        # Обычный HTML парсинг
        soup = BeautifulSoup(html, 'lxml')

        # Пытаемся извлечь из window.__initialData__ или JSON-LD
        initial_data = self._extract_initial_data(html)
        if initial_data:
            data.update(self._parse_from_initial_data(initial_data))

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
        # Паттерны URL Авито:
        # https://www.avito.ru/sankt-peterburg/kvartiry/2-k._kvartira_56m_44et._1234567890
        # https://m.avito.ru/sankt-peterburg/kvartiry/1234567890

        patterns = [
            r'/kvartiry/[^/]*_(\d{10,})$',  # Desktop URL
            r'/kvartiry/(\d{10,})$',        # Mobile URL
            r'_(\d{10,})$',                 # Fallback
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        logger.warning(f"Не удалось извлечь ID из URL: {url}")
        return None

    def _parse_from_mobile_api(self, api_data: Dict) -> Dict:
        """
        Парсинг данных мобильного API

        Args:
            api_data: JSON данные из API

        Returns:
            Нормализованные данные
        """
        # Используем маппер полей
        return self.field_mapper.transform(api_data)

    def _extract_initial_data(self, html: str) -> Optional[Dict]:
        """
        Извлечь данные из window.__initialData__

        Args:
            html: HTML контент

        Returns:
            Данные или None
        """
        pattern = r'window\.__initialData__\s*=\s*"([^"]+)"'

        try:
            match = re.search(pattern, html)
            if match:
                # Данные закодированы в JSON строке
                json_str = match.group(1)
                # Декодируем escape-последовательности
                json_str = json_str.encode().decode('unicode_escape')
                data = json.loads(json_str)
                logger.info("✓ Извлечены данные из window.__initialData__")
                return data
        except Exception as e:
            logger.debug(f"Ошибка извлечения __initialData__: {e}")

        return None

    def _parse_from_initial_data(self, data: Dict) -> Dict:
        """Парсинг из __initialData__"""
        result = {}

        # Структура данных Avito сложная, пытаемся найти нужные поля
        # Примерная структура: data.item (объявление)
        item = data.get('item', {})

        if item:
            result.update(self.field_mapper.transform(item))

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

        if json_ld.get('@type') in ['Product', 'RealEstateListing']:
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
        title_elem = soup.find('h1', {'data-marker': 'item-view/title'}) or soup.find('h1')
        if title_elem:
            data['title'] = title_elem.get_text(strip=True)

        # Цена
        price_elem = soup.find('[data-marker="item-view/item-price"]')
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            data['price'] = self._extract_number(price_text)

        # Описание
        desc_elem = soup.find('[data-marker="item-view/item-description"]')
        if desc_elem:
            data['description'] = desc_elem.get_text(strip=True)

        # Характеристики
        params = soup.find_all('li', class_='params-paramsList__item')
        characteristics = {}
        for param in params:
            try:
                key = param.get_text(separator='|', strip=True).split('|')[0].strip()
                value = param.get_text(separator='|', strip=True).split('|')[1].strip() if '|' in param.get_text(separator='|') else ''
                if key and value:
                    characteristics[key] = value
            except:
                pass

        data['characteristics'] = characteristics

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
        Поиск аналогов на Avito

        Args:
            target_property: Целевой объект
            limit: Лимит результатов
            strategy: Стратегия поиска

        Returns:
            Список аналогов
        """
        logger.info(f"🔍 Поиск аналогов на Авито (стратегия: {strategy})")

        # Формируем параметры поиска
        search_params = self._build_search_params(target_property, strategy)

        # Выполняем поиск
        try:
            results = self._search_via_url(search_params, limit)
            logger.info(f"✓ Найдено {len(results)} аналогов на Авито")
            return results
        except Exception as e:
            logger.error(f"❌ Ошибка поиска на Авито: {e}")
            return []

    def _build_search_params(self, target: Dict, strategy: str) -> Dict:
        """
        Построить параметры поиска для URL Авито

        Args:
            target: Целевой объект
            strategy: Стратегия поиска

        Returns:
            Параметры для URL
        """
        params = {}

        # Базовые параметры
        price = target.get('price')
        area = target.get('total_area')
        rooms = target.get('rooms')

        if price:
            # ±30% от цены
            price_min = int(price * 0.7)
            price_max = int(price * 1.3)
            params['pmin'] = price_min
            params['pmax'] = price_max

        if area:
            # ±20% от площади
            area_min = int(area * 0.8)
            area_max = int(area * 1.2)
            params['smin'] = area_min
            params['smax'] = area_max

        if rooms and rooms != 'студия':
            # Количество комнат
            params['rooms'] = rooms

        # Стратегия поиска
        if strategy == 'same_building' or strategy == 'same_area':
            # Авито не поддерживает поиск по ЖК напрямую
            # Используем адрес или район
            address = target.get('address', '')
            if address:
                # Извлекаем район из адреса
                # Например: "Санкт-Петербург, Невский район"
                parts = [p.strip() for p in address.split(',')]
                if len(parts) >= 2:
                    params['q'] = parts[1]  # Район

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
        base_search_url = f"https://www.avito.ru/{self.region_slug}/kvartiry/prodam"

        # Добавляем параметры
        if params:
            param_str = '&'.join([f"{k}={v}" for k, v in params.items()])
            search_url = f"{base_search_url}?{param_str}"
        else:
            search_url = base_search_url

        logger.info(f"🔍 Поиск Авито: {search_url}")

        # Пытаемся получить страницу поиска
        html = self._get_search_page(search_url)

        if not html:
            logger.warning("Не удалось получить страницу поиска Авито")
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
        # Используем Nodriver для обхода DataDome
        return self._get_via_nodriver(url)

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
        # Авито использует data-marker для карточек
        cards = soup.find_all(attrs={'data-marker': 'item'})

        if not cards:
            # Альтернативный поиск по классам
            cards = soup.find_all('div', class_=re.compile(r'item.*card|iva-item', re.I))

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
        data = {'source': 'avito'}

        # URL
        link = card.find('a', attrs={'data-marker': 'item-title'})
        if not link:
            link = card.find('a', href=re.compile(r'/kvartiry/'))

        if link and link.get('href'):
            url = link['href']
            if not url.startswith('http'):
                url = f"https://www.avito.ru{url}"
            data['url'] = url
        else:
            return None

        # Заголовок
        title_elem = card.find(attrs={'data-marker': 'item-title'})
        if not title_elem:
            title_elem = card.find('h3') or card.find('h2')

        if title_elem:
            data['title'] = title_elem.get_text(strip=True)

        # Цена
        price_elem = card.find(attrs={'data-marker': 'item-price'})
        if not price_elem:
            price_elem = card.find('span', class_=re.compile(r'price', re.I))

        if price_elem:
            price_text = price_elem.get_text(strip=True)
            data['price'] = self._extract_number(price_text)

        # Характеристики (площадь, комнаты и т.д.)
        params_elem = card.find(attrs={'data-marker': 'item-specific-params'})
        if not params_elem:
            params_elem = card.find('div', class_=re.compile(r'params', re.I))

        if params_elem:
            params_text = params_elem.get_text(strip=True)

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
        address_elem = card.find(attrs={'data-marker': 'item-address'})
        if not address_elem:
            address_elem = card.find('div', class_=re.compile(r'address|geo', re.I))

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
            supports_residential_complex=False,  # Авито не поддерживает поиск по ЖК
            supports_regions=['msk', 'spb'],
            supports_async=False,
            has_api=True,  # Мобильное API
            requires_browser=True  # Nodriver для обхода DataDome
        )

    def get_source_name(self) -> str:
        """Название источника"""
        return 'avito'
