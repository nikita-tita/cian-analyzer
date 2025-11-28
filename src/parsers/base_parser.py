"""
Базовый класс парсера с общей логикой
"""

import json
import time
import logging
import re
from typing import Optional, Dict, List
from abc import ABC, abstractmethod
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ParsingError(Exception):
    """Ошибка парсинга"""


class BaseCianParser(ABC):
    """
    Базовый класс для всех парсеров Cian

    Содержит общую логику:
    - Извлечение JSON-LD
    - Обработка ошибок
    - Retry механизм
    - Логирование
    - Redis кэширование
    """

    def __init__(self, delay: float = 2.0, cache=None):
        """
        Args:
            delay: Задержка между запросами в секундах
            cache: PropertyCache instance (опционально)
        """
        self.delay = delay
        self.base_url = "https://www.cian.ru"
        self.cache = cache
        self.stats = {
            'requests': 0,
            'errors': 0,
            'retries': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }

    @abstractmethod
    def _get_page_content(self, url: str) -> Optional[str]:
        """
        Получить HTML контент страницы

        Должен быть реализован в подклассах
        """

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.RequestException, TimeoutError)),
        before_sleep=lambda retry_state: logger.warning(
            f"Retry {retry_state.attempt_number}/3 after {retry_state.outcome.exception()}"
        )
    )
    def _make_request_with_retry(self, url: str, **kwargs) -> requests.Response:
        """
        HTTP запрос с автоматическими повторами

        Args:
            url: URL для запроса
            **kwargs: Дополнительные параметры для requests

        Returns:
            Response объект

        Raises:
            requests.RequestException: После 3 неудачных попыток
        """
        self.stats['requests'] += 1
        response = requests.get(url, timeout=30, **kwargs)
        response.raise_for_status()
        time.sleep(self.delay)
        return response

    def _extract_json_ld(self, soup: BeautifulSoup) -> Optional[Dict]:
        """
        Извлечь структурированные данные JSON-LD

        Args:
            soup: BeautifulSoup объект страницы

        Returns:
            Словарь с данными или None
        """
        try:
            json_ld_script = soup.find('script', type='application/ld+json')
            if json_ld_script and json_ld_script.string:
                return json.loads(json_ld_script.string)
        except (json.JSONDecodeError, AttributeError) as e:
            logger.debug(f"Не удалось извлечь JSON-LD: {e}")
        return None

    def _extract_basic_info(self, soup: BeautifulSoup, data: Dict) -> Dict:
        """
        Извлечь базовую информацию из HTML

        Args:
            soup: BeautifulSoup объект
            data: Словарь для заполнения

        Returns:
            Обновленный словарь с данными
        """
        # Заголовок
        if not data.get('title'):
            title_elem = soup.find('h1', {'data-mark': 'OfferTitle'}) or soup.find('h1')
            if title_elem:
                data['title'] = title_elem.get_text(strip=True)

        # Адрес
        if not data.get('address'):
            # Метод 1: GeoLabel (старый формат)
            address_elem = soup.find('a', {'data-name': 'GeoLabel'})
            if address_elem:
                data['address'] = address_elem.get_text(strip=True)

            # Метод 2: AddressItem (новый формат) - может быть в теге <a>
            if not data.get('address'):
                address_item = soup.find('a', {'data-name': 'AddressItem'})
                if address_item:
                    data['address'] = address_item.get_text(strip=True)

            # Метод 3: Из breadcrumbs в OfferBreadcrumbs
            if not data.get('address'):
                breadcrumbs_div = soup.find('div', {'data-name': 'OfferBreadcrumbs'})
                if breadcrumbs_div:
                    # Собираем все ссылки с /geo/ кроме первой (города)
                    geo_links = breadcrumbs_div.find_all('a', href=lambda h: h and '/geo/' in h)
                    if geo_links:
                        address_parts = []
                        for link in geo_links:
                            text = link.get_text(strip=True)
                            # Пропускаем город и общие категории
                            if text not in ['Санкт-Петербург', 'Москва', 'Продажа', 'Купить'] and 'комнат' not in text.lower():
                                address_parts.append(text)
                        if address_parts:
                            data['address'] = ', '.join(address_parts)

            # НОВОЕ: Извлечение street_url из breadcrumbs для точного поиска аналогов
            # URL вида: /kupit-1-komnatnuyu-kvartiru-moskva-proizvodstvennaya-ulica-021905
            # Поддерживаемые типы: ulica, prospekt, pereulok, bulvar, shosse, naberezhnaya, ploshad, proezd, alleya
            if not data.get('street_url'):
                breadcrumbs_div = soup.find('div', {'data-name': 'OfferBreadcrumbs'})
                if breadcrumbs_div:
                    street_types = ['-ulica-', '-prospekt-', '-pereulok-', '-bulvar-', '-shosse-',
                                    '-naberezhnaya-', '-ploshad-', '-proezd-', '-alleya-', '-tupik-']
                    for link in breadcrumbs_div.find_all('a', href=True):
                        href = link.get('href', '')
                        # Ищем ссылку с улицей (содержит тип улицы и geo-id)
                        has_street_type = any(st in href for st in street_types)
                        has_geo_id = re.search(r'-\d{5,}$', href)
                        if has_street_type and has_geo_id:
                            street_url = href if href.startswith('http') else f"https://www.cian.ru{href}"
                            data['street_url'] = street_url
                            logger.info(f"✓ Найден street_url из breadcrumbs: {street_url[:80]}...")
                            break

        # ЖК (Жилой комплекс)
        if not data.get('residential_complex'):
            # Пробуем разные варианты извлечения ЖК

            # Метод 1: Из ссылок на ЖК (самый надежный!)
            # Ищем ссылки типа: https://zhk-название.cian.ru/ или /zhiloy-kompleks-название/
            zhk_links = soup.find_all('a', href=True)
            for link in zhk_links:
                href = link.get('href')
                text = link.get_text(strip=True)

                # Проверяем разные паттерны ссылок на ЖК
                if 'zhk-' in href and '.cian.ru' in href:
                    # Например: https://zhk-moiseenko-10.cian.ru/
                    data['residential_complex'] = text.replace('ЖК ', '').replace('«', '').replace('»', '').strip()
                    data['residential_complex_url'] = href
                    logger.info(f"✓ Найден ЖК по ссылке: {text} → {href[:50]}")
                    break
                elif '/zhiloy-kompleks-' in href or '/kupit-kvartiru-zhiloy-kompleks-' in href:
                    # Например: /kupit-kvartiru-zhiloy-kompleks-moiseenko-10-5094487/
                    data['residential_complex'] = text.replace('ЖК ', '').replace('«', '').replace('»', '').strip()
                    data['residential_complex_url'] = href if href.startswith('http') else f"https://www.cian.ru{href}"
                    logger.info(f"✓ Найден ЖК по ссылке: {text} → {href[:50]}")
                    break

            # Метод 2: Из breadcrumbs
            if not data.get('residential_complex'):
                breadcrumbs = soup.find('div', {'data-name': 'Breadcrumbs'}) or soup.find('nav', class_='breadcrumbs')
                if breadcrumbs:
                    links = breadcrumbs.find_all('a')
                    for link in links:
                        text = link.get_text(strip=True)
                        href = link.get('href', '')
                        # ЖК обычно имеют ссылки вида /zhk-название/
                        if '/zhk-' in href or 'ЖК' in text:
                            data['residential_complex'] = text.replace('ЖК ', '').replace('«', '').replace('»', '').strip()
                            break

            # Метод 3: Из адреса (если есть "ЖК")
            if not data.get('residential_complex') and data.get('address'):
                # Ищем паттерн "ЖК Название"
                match = re.search(r'ЖК\s+([А-Яа-яёЁ\s\-\d]+?)(?:,|$)', data['address'])
                if match:
                    data['residential_complex'] = match.group(1).strip()

            # Метод 4: Из заголовка
            if not data.get('residential_complex') and data.get('title'):
                match = re.search(r'ЖК\s+([А-Яа-яёЁ\s\-\d]+?)(?:,|в|—|$)', data['title'])
                if match:
                    data['residential_complex'] = match.group(1).strip()

            # Метод 5: Из характеристик (если уже извлечены)
            chars = data.get('characteristics', {})
            if not data.get('residential_complex') and chars:
                for key in ['Жилой комплекс', 'ЖК', 'Название ЖК']:
                    if key in chars:
                        data['residential_complex'] = chars[key]
                        break

        # Метро
        if not data.get('metro'):
            # Метод 1: UndergroundLabel (старый формат)
            metro_elems = soup.find_all('a', {'data-name': 'UndergroundLabel'})
            if metro_elems:
                data['metro'] = [metro.get_text(strip=True) for metro in metro_elems]

            # Метод 2: UndergroundItem (новый формат)
            if not data.get('metro') or len(data['metro']) == 0:
                metro_items = soup.find_all('div', {'data-name': 'UndergroundItem'})
                if metro_items:
                    metro_list = []
                    for item in metro_items:
                        # Ищем название станции внутри
                        text = item.get_text(strip=True)
                        # Убираем время в пути (например "5 мин." или "10 мин. пешком")
                        # Удаляем паттерны вроде "5 мин", "10 мин. пешком"
                        text = re.sub(r'\d+\s*мин\.?\s*(пешком)?', '', text).strip()
                        if text and text not in metro_list:
                            metro_list.append(text)
                    if metro_list:
                        data['metro'] = metro_list

            # Метод 3: Из breadcrumbs (новейший формат)
            if not data.get('metro') or len(data['metro']) == 0:
                breadcrumbs_div = soup.find('div', {'data-name': 'OfferBreadcrumbs'})
                if breadcrumbs_div:
                    # Ищем ссылки с текстом "метро"
                    links = breadcrumbs_div.find_all('a')
                    metro_list = []
                    for link in links:
                        text = link.get_text(strip=True)
                        # Если в тексте есть "метро", извлекаем название станции
                        if 'метро' in text.lower():
                            # Убираем слово "метро" и очищаем
                            station = text.replace('метро', '').replace('м.', '').strip()
                            if station and station not in metro_list:
                                metro_list.append(station)
                    if metro_list:
                        data['metro'] = metro_list

        # Описание
        if not data.get('description'):
            desc_elem = soup.find('div', {'data-name': 'Description'})
            if desc_elem:
                p_elem = desc_elem.find('p')
                if p_elem:
                    data['description'] = p_elem.get_text(strip=True)
                else:
                    data['description'] = desc_elem.get_text(strip=True)

        return data

    def _extract_characteristics(self, soup: BeautifulSoup) -> Dict[str, str]:
        """
        Извлечь характеристики из HTML

        Args:
            soup: BeautifulSoup объект

        Returns:
            Словарь с характеристиками
        """
        characteristics = {}

        # Метод 1: OfferSummaryInfoItem (основной для новых страниц)
        summary_items = soup.find_all('div', {'data-name': 'OfferSummaryInfoItem'})
        for item in summary_items:
            # Ищем пары label-value внутри item
            spans = item.find_all('span')
            paragraphs = item.find_all('p')

            # Пробуем извлечь из spans
            if len(spans) >= 2:
                label = spans[0].get_text(strip=True)
                value = spans[1].get_text(strip=True)
                if label and value:
                    characteristics[label] = value
            # Или из paragraphs
            elif len(paragraphs) >= 2:
                label = paragraphs[0].get_text(strip=True)
                value = paragraphs[1].get_text(strip=True)
                if label and value:
                    characteristics[label] = value

        # Метод 2: ObjectFactoidsItem (для ключевых полей: площадь, этаж, год)
        factoid_items = soup.find_all('div', {'data-name': 'ObjectFactoidsItem'})
        for item in factoid_items:
            # Ищем label и value - они находятся в разных span'ах
            spans = item.find_all('span')
            if len(spans) >= 2:
                # Первый span - метка (серый текст), второй - значение (жирный)
                label = spans[0].get_text(strip=True)
                value = spans[1].get_text(strip=True)
                if label and value:
                    characteristics[label] = value

        # Метод 3: OfferFactItem (старый формат)
        char_items = soup.find_all('div', {'data-name': 'OfferFactItem'})
        for item in char_items:
            # Разбиваем текст на label и value
            children = list(item.find_all(['span', 'p']))
            if len(children) >= 2:
                label = children[0].get_text(strip=True)
                value = children[1].get_text(strip=True)
                if label and value:
                    characteristics[label] = value

        # Метод 4: Из списков характеристик
        char_lists = soup.find_all('ul', class_=lambda x: x and 'item' in str(x).lower())
        for ul in char_lists:
            items = ul.find_all('li')
            for item in items:
                text = item.get_text(strip=True)
                if ':' in text and len(text) < 200:
                    parts = text.split(':', 1)
                    if len(parts) == 2:
                        key, value = parts[0].strip(), parts[1].strip()
                        if key and value:
                            characteristics[key] = value

        return characteristics

    def _extract_images(self, soup: BeautifulSoup, max_images: int = 30) -> List[str]:
        """
        Извлечь изображения

        Args:
            soup: BeautifulSoup объект
            max_images: Максимальное количество изображений

        Returns:
            Список URL изображений
        """
        images = []

        # Метод 1: Из галереи
        img_gallery = soup.find('div', {'data-name': 'GalleryPreviews'})
        if img_gallery:
            img_elems = img_gallery.find_all('img')
            images = [
                img.get('src') or img.get('data-src')
                for img in img_elems
                if img.get('src') or img.get('data-src')
            ]

        # Метод 2: Все изображения CDN
        if not images:
            all_images = soup.find_all('img', src=lambda x: x and 'cdn-p.cian.site' in x)
            images = [img.get('src') for img in all_images]

        return images[:max_images]

    def _extract_seller_info(self, soup: BeautifulSoup) -> Dict[str, str]:
        """
        Извлечь информацию о продавце

        Args:
            soup: BeautifulSoup объект

        Returns:
            Словарь с информацией о продавце
        """
        seller = {}

        seller_name = soup.find('div', {'data-name': 'OfferAuthorName'})
        if seller_name:
            seller['name'] = seller_name.get_text(strip=True)

        seller_type = soup.find('div', {'data-name': 'OfferAuthorType'})
        if seller_type:
            seller['type'] = seller_type.get_text(strip=True)

        return seller

    def _promote_key_fields(self, data: Dict) -> None:
        """
        Извлекает ключевые поля из characteristics в корень данных
        для удобства работы с API

        Args:
            data: Словарь с данными объявления (модифицируется in-place)
        """

        characteristics = data.get('characteristics', {})
        if not characteristics:
            return

        # Маппинг: ключ в characteristics -> ключ в корне данных
        mappings = {
            # Площадь (ИСПРАВЛЕНО: total_area вместо area для совместимости с Pydantic)
            'Общая площадь': ('total_area', lambda x: float(re.sub(r'[^\d,.]', '', x).replace(',', '.')) if x else None),
            'Площадь': ('total_area', lambda x: float(re.sub(r'[^\d,.]', '', x).replace(',', '.')) if x else None),
            'Общая, м²': ('total_area', lambda x: float(re.sub(r'[^\d,.]', '', x).replace(',', '.')) if x else None),
            # Жилая площадь - РАСШИРЕНО: больше вариантов ключей
            'Жилая площадь': ('living_area', lambda x: float(re.sub(r'[^\d,.]', '', x).replace(',', '.')) if x else None),
            'Жилая': ('living_area', lambda x: float(re.sub(r'[^\d,.]', '', x).replace(',', '.')) if x else None),
            'Жилая, м²': ('living_area', lambda x: float(re.sub(r'[^\d,.]', '', x).replace(',', '.')) if x else None),
            # Площадь кухни
            'Площадь кухни': ('kitchen_area', lambda x: float(re.sub(r'[^\d,.]', '', x).replace(',', '.')) if x else None),
            'Кухня': ('kitchen_area', lambda x: float(re.sub(r'[^\d,.]', '', x).replace(',', '.')) if x else None),
            'Кухня, м²': ('kitchen_area', lambda x: float(re.sub(r'[^\d,.]', '', x).replace(',', '.')) if x else None),
            # Этаж (извлекает floor из формата "5 из 10")
            'Этаж': ('floor', lambda x: int(x.split()[0]) if x and 'из' in x else (int(x) if x.isdigit() else None)),
            # Год постройки
            'Год постройки': ('build_year', lambda x: int(re.sub(r'[^\d]', '', x)) if x else None),
            'Построен': ('build_year', lambda x: int(re.sub(r'[^\d]', '', x)) if x else None),
        }

        for char_key, (data_key, transform_func) in mappings.items():
            if char_key in characteristics and not data.get(data_key):
                try:
                    value = characteristics[char_key]
                    data[data_key] = transform_func(value) if transform_func else value
                except Exception:
                    pass

        # Извлекаем общее количество этажей из характеристики "Этаж"
        if 'Этаж' in characteristics and not data.get('floor_total'):
            try:
                floor_value = characteristics['Этаж']
                if floor_value and 'из' in floor_value:
                    data['floor_total'] = int(floor_value.split()[-1])
            except Exception:
                pass

        # Извлекаем количество комнат из заголовка
        if not data.get('rooms') and data.get('title'):
            title = data['title']
            # Паттерны: "1-комн.", "2-комн.", "3-комн.", "студия"
            if 'студи' in title.lower():
                data['rooms'] = 'студия'
            else:
                match = re.search(r'(\d+)-комн', title)
                if match:
                    data['rooms'] = int(match.group(1))

    def _extract_premium_features(self, soup: BeautifulSoup, data: Dict) -> None:
        """
        Извлекает премиум-характеристики объекта из HTML и описания

        Args:
            soup: BeautifulSoup объект страницы
            data: Словарь с данными (модифицируется in-place)
        """

        # Получаем полный текст страницы для анализа
        page_text = soup.get_text(separator=' ', strip=True).lower()

        # Получаем описание объекта
        description = data.get('description', '').lower() if data.get('description') else ''

        # Объединяем для поиска
        full_text = f"{page_text} {description}"

        # === ДИЗАЙНЕРСКАЯ ОТДЕЛКА ===
        # Ключевые слова: дизайнерский ремонт, дизайнерская отделка, авторский дизайн
        design_keywords = [
            'дизайнерск',
            'авторск',
            'индивидуальн',
            'эксклюзивн',
            'премиальн',
        ]
        data['дизайнерская отделка'] = any(kw in full_text for kw in design_keywords)

        # === ПАНОРАМНЫЕ ВИДЫ ===
        # Ключевые слова: панорамные окна, панорамный вид, вид на воду, вид на парк
        view_keywords = [
            'панорам',
            'вид на воду',
            'вид на реку',
            'вид на залив',
            'вид на парк',
            'вид на лес',
            'с видом на',
        ]
        data['панорамные виды'] = any(kw in full_text for kw in view_keywords)

        # === ПРЕМИУМ ЛОКАЦИЯ ===
        # Определяем по названию района / адресу
        premium_locations = [
            'петровск',  # Петровский остров
            'крестовск',  # Крестовский остров
            'васильевск',  # Васильевский остров (центральная часть)
            'каменноостров',  # Каменноостровский
            'приморск',  # Приморский район (элитные части)
            'центральный район',
            'адмиралтейск',
        ]

        address = (data.get('address') or '').lower()
        residential_complex = (data.get('residential_complex') or '').lower()

        data['премиум локация'] = any(
            loc in address or loc in residential_complex or loc in full_text
            for loc in premium_locations
        )

        # === ТОЛЬКО РЕНДЕРЫ (НЕТ ФОТО) ===
        # Проверяем упоминания о том, что объект в процессе строительства
        # или есть только визуализации
        renders_keywords = [
            'визуализац',
            'рендер',
            'строит',
            'сдача',
            'планируем',
        ]

        # Также проверяем год постройки - если будущий, то рендеры
        build_year = data.get('build_year')
        from datetime import datetime
        current_year = datetime.now().year

        is_under_construction = build_year and build_year > current_year
        has_render_keywords = any(kw in full_text for kw in renders_keywords)

        data['только рендеры'] = is_under_construction or has_render_keywords

        # === ПАРКОВКА ===
        # Извлекаем из характеристик или текста
        characteristics = data.get('characteristics', {})

        parking_value = None
        for key in characteristics:
            if 'паркинг' in key.lower() or 'парковк' in key.lower():
                val = characteristics[key].lower()
                if 'подземн' in val or 'многоуровнев' in val:
                    parking_value = 'подземная'
                elif 'закрыт' in val or 'охраняем' in val:
                    parking_value = 'закрытая'
                elif 'открыт' in val or 'на улице' in val:
                    parking_value = 'на улице'
                else:
                    parking_value = 'есть'
                break

        # Если не нашли в характеристиках, ищем в тексте
        if not parking_value:
            if 'подземн' in full_text and ('паркинг' in full_text or 'парковк' in full_text):
                parking_value = 'подземная'
            elif 'машиномест' in full_text or 'паркинг' in full_text:
                parking_value = 'есть'

        data['парковка'] = parking_value

        # === ВЫСОТА ПОТОЛКОВ ===
        # Ищем паттерн типа "3.2 м", "высота потолков 3 м", "потолки 3.5м"
        # УЛУЧШЕНО: больше вариантов паттернов
        ceiling_patterns = [
            r'потолк[а-я]*[^\d]{0,20}?(\d+(?:[.,]\d+)?)\s*м',  # "потолки 3.2 м"
            r'высот[а-я]*\s*потолк[а-я]*[^\d]{0,20}?(\d+(?:[.,]\d+)?)\s*м',  # "высота потолков 3 м"
            r'высот[а-я]*[^\d]{0,20}?(\d+(?:[.,]\d+)?)\s*м',  # "высота 3.5 м"
        ]

        for pattern in ceiling_patterns:
            ceiling_match = re.search(pattern, full_text)
            if ceiling_match:
                try:
                    ceiling_height = float(ceiling_match.group(1).replace(',', '.'))
                    if 2.3 <= ceiling_height <= 6.0:  # Расширенный разумный диапазон
                        data['высота потолков'] = ceiling_height
                        logger.debug(f"Найдена высота потолков: {ceiling_height}м (паттерн: {pattern})")
                        break
                except (ValueError, IndexError):
                    continue

        # === ОХРАНА 24/7 ===
        security_keywords = [
            'охран',
            'консьерж',
            'security',
            '24/7',
            'видеонаблюден',
            'контроль доступ',
        ]
        data['охрана 24/7'] = any(kw in full_text for kw in security_keywords)

        # === ТИП ДОМА ===
        # Извлекаем из характеристик или текста
        characteristics = data.get('characteristics', {})

        house_type = None
        for key in characteristics:
            if 'тип дома' in key.lower() or 'здание' in key.lower():
                val = characteristics[key].lower()
                if 'монолит' in val:
                    house_type = 'монолит'
                elif 'кирпич' in val:
                    house_type = 'кирпич'
                elif 'панел' in val:
                    house_type = 'панель'
                break

        # Если не нашли в характеристиках, ищем в тексте
        if not house_type:
            if 'монолит' in full_text:
                house_type = 'монолит'
            elif 'кирпич' in full_text and 'дом' in full_text:
                house_type = 'кирпич'
            elif 'панел' in full_text and 'дом' in full_text:
                house_type = 'панель'

        data['house_type'] = house_type

        # === ВСЕГО ЭТАЖЕЙ ===
        # Извлекаем из поля floor, которое может быть в формате "6/9"
        if not data.get('total_floors'):
            # Ищем в характеристиках
            for key in characteristics:
                if 'этаж' in key.lower():
                    val = characteristics[key]
                    if isinstance(val, str) and '/' in val:
                        try:
                            floor_total = int(val.split('/')[-1])
                            data['total_floors'] = floor_total
                            break
                        except ValueError:
                            pass

        logger.debug("Извлечены премиум-характеристики:")
        logger.debug(f"  Дизайнерская отделка: {data.get('дизайнерская отделка')}")
        logger.debug(f"  Панорамные виды: {data.get('панорамные виды')}")
        logger.debug(f"  Премиум локация: {data.get('премиум локация')}")
        logger.debug(f"  Только рендеры: {data.get('только рендеры')}")
        logger.debug(f"  Парковка: {data.get('парковка')}")
        logger.debug(f"  Высота потолков: {data.get('высота потолков')}")
        logger.debug(f"  Охрана 24/7: {data.get('охрана 24/7')}")
        logger.debug(f"  Тип дома: {data.get('house_type')}")
        logger.debug(f"  Всего этажей: {data.get('total_floors')}")

    def parse_detail_page(self, url: str) -> Dict:
        """
        Парсинг детальной страницы объявления с кэшированием

        Args:
            url: URL объявления

        Returns:
            Словарь с детальными данными
        """
        # Проверяем кэш
        if self.cache:
            cached_data = self.cache.get_property(url)
            if cached_data:
                self.stats['cache_hits'] += 1
                logger.info(f"✅ Cache HIT: {url[:60]}...")
                return cached_data
            else:
                self.stats['cache_misses'] += 1

        logger.info(f"Парсинг детальной страницы: {url}")

        try:
            html = self._get_page_content(url)
            if not html:
                raise ParsingError(f"Не удалось получить контент: {url}")

            soup = BeautifulSoup(html, 'lxml')

            data = {
                'url': url,
                'title': None,
                'price': None,
                'price_raw': None,
                'currency': None,
                'description': None,
                'address': None,
                'residential_complex': None,
                'residential_complex_url': None,  # Ссылка на страницу ЖК
                'metro': [],
                'characteristics': {},
                'images': [],
                'seller': {},
            }

            # JSON-LD данные (приоритет)
            json_ld = self._extract_json_ld(soup)
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
            data = self._extract_basic_info(soup, data)
            data['characteristics'] = self._extract_characteristics(soup)
            data['images'] = self._extract_images(soup)
            data['seller'] = self._extract_seller_info(soup)

            # Извлекаем ключевые поля из characteristics в корень для удобства
            self._promote_key_fields(data)

            # Извлекаем премиум-характеристики
            self._extract_premium_features(soup, data)

            logger.info(f"✓ Успешно спарсен: {data.get('title', 'Без названия')}")

            # Сохраняем в кэш
            if self.cache:
                self.cache.set_property(url, data, ttl_hours=24)
                logger.debug(f"💾 Сохранено в кэш: {url[:60]}...")

            return data

        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Ошибка при парсинге {url}: {e}", exc_info=True)
            raise ParsingError(f"Ошибка парсинга: {e}") from e

    def get_stats(self) -> Dict:
        """Получить статистику работы парсера"""
        return self.stats.copy()

    def reset_stats(self):
        """Сбросить статистику"""
        self.stats = {
            'requests': 0,
            'errors': 0,
            'retries': 0,
            'cache_hits': 0
        }
