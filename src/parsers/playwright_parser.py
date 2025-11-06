"""
Эффективный Playwright парсер с переиспользованием браузера
"""

import time
import logging
from typing import Optional, List, Dict
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext
from bs4 import BeautifulSoup

from .base_parser import BaseCianParser, ParsingError

logger = logging.getLogger(__name__)


class PlaywrightParser(BaseCianParser):
    """
    Playwright парсер с переиспользованием браузера

    ОПТИМИЗАЦИЯ:
    - Браузер запускается один раз на всю сессию
    - Context переиспользуется
    - Блокируются ненужные ресурсы (картинки, шрифты)
    """

    def __init__(self, headless: bool = True, delay: float = 2.0, block_resources: bool = True):
        """
        Args:
            headless: Запускать браузер в фоновом режиме
            delay: Задержка между запросами
            block_resources: Блокировать картинки/шрифты для ускорения
        """
        super().__init__(delay)
        self.headless = headless
        self.block_resources = block_resources
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None

    def __enter__(self):
        """Context manager вход"""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager выход"""
        self.close()

    def start(self):
        """Запуск браузера (один раз за сессию)"""
        if self.browser:
            logger.warning("Браузер уже запущен")
            return

        logger.info("🚀 Запуск Playwright браузера...")
        self.playwright = sync_playwright().start()

        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-gpu',
                '--disable-software-rasterizer',
            ]
        )

        self.context = self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='ru-RU',
            timezone_id='Europe/Moscow',
        )

        # Скрываем автоматизацию
        self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            window.chrome = { runtime: {} };
        """)

        # Блокируем ненужные ресурсы для ускорения
        if self.block_resources:
            self.context.route(
                "**/*.{png,jpg,jpeg,gif,svg,webp,woff,woff2,ttf,mp4,mp3,pdf}",
                lambda route: route.abort()
            )

        logger.info("✓ Браузер запущен и готов к работе")

    def close(self):
        """Закрытие браузера"""
        if self.context:
            self.context.close()
            self.context = None

        if self.browser:
            self.browser.close()
            self.browser = None

        if self.playwright:
            self.playwright.stop()
            self.playwright = None

        logger.info("Браузер закрыт")

    def _get_page_content(self, url: str) -> Optional[str]:
        """
        Получить HTML контент через Playwright

        Args:
            url: URL для загрузки

        Returns:
            HTML контент или None
        """
        if not self.context:
            raise RuntimeError("Браузер не запущен. Используйте with context или вызовите .start()")

        page: Page = self.context.new_page()

        try:
            logger.info(f"Загрузка страницы: {url}")

            # Загружаем страницу
            page.goto(url, wait_until='domcontentloaded', timeout=30000)

            # Ждем появления контента
            try:
                page.wait_for_selector(
                    'h1, [data-mark="OfferTitle"], script[type="application/ld+json"]',
                    timeout=10000
                )
            except:
                logger.warning("Селекторы не найдены, но продолжаем")

            # Дополнительное ожидание для динамического контента
            time.sleep(1)

            html = page.content()

            logger.info(f"✓ Страница загружена ({len(html)} символов)")
            return html

        except Exception as e:
            logger.error(f"Ошибка при загрузке {url}: {e}", exc_info=True)
            return None

        finally:
            page.close()
            time.sleep(self.delay)

    def parse_search_page(self, url: str) -> List[Dict]:
        """
        Парсинг страницы с результатами поиска

        Args:
            url: URL страницы поиска

        Returns:
            Список словарей с данными объявлений
        """
        logger.info(f"Парсинг страницы поиска: {url}")

        html = self._get_page_content(url)
        if not html:
            return []

        soup = BeautifulSoup(html, 'lxml')

        # Поиск карточек объявлений
        cards = soup.find_all('article', {'data-name': 'CardComponent'})

        if not cards:
            cards = soup.find_all('div', class_=lambda x: x and 'offer-card' in str(x).lower())

        logger.info(f"Найдено {len(cards)} объявлений")

        listings = []
        for card in cards:
            try:
                listing_data = self._parse_listing_card(card)
                if listing_data.get('title'):
                    listings.append(listing_data)
            except Exception as e:
                logger.warning(f"Ошибка при парсинге карточки: {e}")
                continue

        return listings

    def _parse_listing_card(self, card: BeautifulSoup) -> Dict:
        """
        Парсинг карточки объявления из списка

        Args:
            card: BeautifulSoup объект карточки

        Returns:
            Словарь с данными объявления
        """
        data = {
            'title': None,
            'price': None,
            'price_per_sqm': None,  # Цена за кв.м
            'price_raw': None,  # Цена в числовом виде
            'address': None,
            'metro': None,
            'area': None,
            'area_value': None,  # Площадь в числовом виде
            'rooms': None,
            'floor': None,
            'renovation': None,  # Тип ремонта
            'url': None,
            'image_url': None,
        }

        # Заголовок - пробуем несколько вариантов
        title_elem = (
            card.find('span', {'data-mark': 'OfferTitle'}) or
            card.find('h3') or
            card.find('a', {'data-name': 'LinkArea'})
        )
        if title_elem:
            data['title'] = title_elem.get_text(strip=True)

            # Извлекаем количество комнат из заголовка
            import re
            title_lower = data['title'].lower()
            if 'студи' in title_lower:
                data['rooms'] = 'студия'
            else:
                match = re.search(r'(\d+)-комн', data['title'])
                if match:
                    data['rooms'] = match.group(1)

        # Цена - пробуем несколько вариантов
        price_elem = (
            card.find('span', {'data-mark': 'MainPrice'}) or
            card.find('span', class_=lambda x: x and 'price' in str(x).lower())
        )
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            data['price'] = price_text

            # Извлекаем числовое значение цены
            import re
            price_numbers = re.sub(r'[^\d]', '', price_text)
            if price_numbers:
                data['price_raw'] = int(price_numbers)

        # Адрес - собираем ВСЕ GeoLabel (breadcrumbs)
        geo_labels = card.find_all('a', {'data-name': 'GeoLabel'})
        if geo_labels:
            # Собираем все части адреса
            address_parts = [label.get_text(strip=True) for label in geo_labels]
            # Соединяем через запятую, пропуская дубликаты
            unique_parts = []
            for part in address_parts:
                if part not in unique_parts:
                    unique_parts.append(part)
            data['address'] = ', '.join(unique_parts)

        # Если GeoLabel не найдены
        if not data['address']:
            address_elem = (
                card.find('div', {'data-name': 'AddressContainer'}) or
                card.find('div', class_=lambda x: x and 'address' in str(x).lower())
            )
            if address_elem:
                data['address'] = address_elem.get_text(strip=True)

        # Если адрес все еще не найден, пробуем найти любой текст с городом
        if not data['address']:
            # Ищем div/span с текстом, содержащим "Санкт-Петербург" или "Москва"
            for elem in card.find_all(['div', 'span', 'a']):
                text = elem.get_text(strip=True)
                if 'Санкт-Петербург' in text or 'Москва' in text:
                    if len(text) < 200:  # Не берем слишком длинные тексты
                        data['address'] = text
                        break

        # Метро
        metro_elem = card.find('a', {'data-name': 'UndergroundLabel'})
        if metro_elem:
            data['metro'] = metro_elem.get_text(strip=True)

        # Подзаголовок с характеристиками (ПРИОРИТЕТ - здесь содержится площадь!)
        # Формат: "2-комн. квартира, 85 м², 4/9 этаж"
        subtitle_elem = card.find('span', {'data-mark': 'OfferSubtitle'})
        if subtitle_elem:
            subtitle_text = subtitle_elem.get_text(strip=True)
            import re

            # Извлекаем площадь (85 м²)
            area_match = re.search(r'([\d,\.]+)\s*м²', subtitle_text)
            if area_match:
                data['area'] = area_match.group(0)  # "85 м²"
                area_str = area_match.group(1).replace(',', '.')
                try:
                    data['area_value'] = float(area_str)
                except ValueError:
                    pass

            # Извлекаем этаж (4/9 этаж → 4)
            floor_match = re.search(r'(\d+)/\d+\s*этаж', subtitle_text)
            if floor_match:
                try:
                    data['floor'] = int(floor_match.group(1))  # Только номер этажа, не "4/9"
                except ValueError:
                    pass

            # Извлекаем количество комнат (2-комн.)
            if not data['rooms']:  # Если еще не извлекли из заголовка
                if 'студи' in subtitle_text.lower():
                    data['rooms'] = 'студия'
                else:
                    rooms_match = re.search(r'(\d+)-комн', subtitle_text)
                    if rooms_match:
                        data['rooms'] = rooms_match.group(1)

        # Характеристики (FALLBACK - если не нашли в подзаголовке)
        characteristics = card.find_all('span', {'data-mark': 'OfferCharacteristics'})
        for char in characteristics:
            text = char.get_text(strip=True)
            if 'м²' in text and not data['area_value']:
                data['area'] = text
                # Извлекаем числовое значение площади
                import re
                area_match = re.search(r'([\d,\.]+)\s*м²', text)
                if area_match:
                    area_str = area_match.group(1).replace(',', '.')
                    try:
                        data['area_value'] = float(area_str)
                    except ValueError:
                        pass
            elif 'этаж' in text.lower() and not data['floor']:
                data['floor'] = text
            elif 'ремонт' in text.lower() or 'отделк' in text.lower():
                data['renovation'] = text

        # Вычисляем цену за кв.м если есть цена и площадь
        if data['price_raw'] and data['area_value']:
            data['price_per_sqm'] = round(data['price_raw'] / data['area_value'])

        # Ссылка - пробуем несколько вариантов
        link_elem = (
            card.find('a', {'data-mark': 'OfferTitle'}) or
            card.find('a', {'data-name': 'LinkArea'}) or
            card.find('a', href=lambda x: x and '/sale/flat/' in str(x))
        )
        if link_elem and link_elem.get('href'):
            href = link_elem['href']
            data['url'] = self.base_url + href if not href.startswith('http') else href

        # Изображение
        img_elem = card.find('img', {'data-mark': 'OfferPreviewImage'})
        if img_elem:
            data['image_url'] = img_elem.get('src') or img_elem.get('data-src')

        return data

    def search_similar_in_building(self, target_property: Dict, limit: int = 20) -> List[Dict]:
        """
        Поиск похожих квартир в том же ЖК (жилом комплексе)

        Args:
            target_property: Целевой объект с полями residential_complex, residential_complex_url, address
            limit: максимальное количество результатов

        Returns:
            Список похожих объявлений из того же ЖК
        """
        logger.info("🔍 Начинаем поиск похожих квартир в том же ЖК...")

        residential_complex = target_property.get('residential_complex')
        residential_complex_url = target_property.get('residential_complex_url')
        address = target_property.get('address', '')

        # ПРИОРИТЕТ 1: Используем прямую ссылку на страницу ЖК (самый точный метод!)
        if residential_complex_url:
            logger.info(f"✨ Используем прямую ссылку на ЖК: {residential_complex_url}")

            # Если это ссылка на поддомен (zhk-название.cian.ru), ищем кнопку "Все квартиры"
            # Если это ссылка /kupit-kvartiru-zhiloy-kompleks-*, она уже готова для парсинга
            if 'zhk-' in residential_complex_url and '.cian.ru' in residential_complex_url:
                # Загружаем страницу ЖК и ищем ссылку на каталог
                html = self._get_page_content(residential_complex_url)
                if html:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(html, 'lxml')

                    # Ищем ссылку на каталог квартир ЖК
                    catalog_links = soup.find_all('a', href=True)
                    for link in catalog_links:
                        href = link.get('href')
                        text = link.get_text(strip=True).lower()

                        if ('/kupit-kvartiru-zhiloy-kompleks-' in href or
                            ('/cat.php' in href and 'newobject' in href)):
                            residential_complex_url = href if href.startswith('http') else f"https://www.cian.ru{href}"
                            logger.info(f"   Найдена ссылка на каталог: {residential_complex_url[:80]}")
                            break

            # Парсим страницу с объявлениями ЖК
            results = self.parse_search_page(residential_complex_url)

            if results:
                # Маппинг полей для Pydantic моделей
                for result in results:
                    if 'area_value' in result and result['area_value']:
                        result['total_area'] = result['area_value']
                    if 'price_raw' in result and result['price_raw']:
                        result['price'] = result['price_raw']
                    if 'rooms' in result and isinstance(result['rooms'], str) and result['rooms'].isdigit():
                        result['rooms'] = int(result['rooms'])

                logger.info(f"✓ Найдено {len(results)} объявлений через прямую ссылку на ЖК")
                return results[:limit]
            else:
                logger.warning("⚠️ По прямой ссылке ничего не найдено, пробуем текстовый поиск")

        # ПРИОРИТЕТ 2: Текстовый поиск по названию ЖК (fallback)
        if not residential_complex:
            logger.warning("⚠️ Не указан ЖК, используется поиск по адресу")
            # Пробуем извлечь из адреса
            import re
            match = re.search(r'ЖК\s+([А-Яа-яёЁ\s\-\d]+?)(?:,|$)', address)
            if match:
                residential_complex = match.group(1).strip()
            else:
                # Если нет ЖК - используем старый метод
                logger.warning("⚠️ ЖК не найден, используется широкий поиск")
                return self.search_similar(target_property, limit)

        logger.info(f"📍 Текстовый поиск по ЖК: {residential_complex}")

        # Формируем поисковый запрос
        import urllib.parse

        # Вариант 1: Точное название ЖК
        search_query = f"ЖК {residential_complex}"
        encoded_query = urllib.parse.quote(search_query)

        # Строим URL поиска с текстовым запросом
        search_params = {
            'deal_type': 'sale',
            'offer_type': 'flat',
            'engine_version': '2',
            'region': '2',  # Санкт-Петербург
            'text': encoded_query,
        }

        url = f"{self.base_url}/cat.php?" + '&'.join([f"{k}={v}" for k, v in search_params.items()])

        logger.info(f"🔗 URL поиска: {url}")

        # Парсим результаты
        results = self.parse_search_page(url)

        # Фильтруем результаты - оставляем только те, что точно из этого ЖК
        filtered_results = []
        rc_lower = residential_complex.lower()

        # Разбиваем название ЖК на слова для более гибкого поиска
        rc_words = set(rc_lower.split())

        logger.info(f"   Найдено {len(results)} карточек, фильтруем по ЖК '{residential_complex}'")
        logger.info(f"   Ключевые слова ЖК: {rc_words}")

        for i, result in enumerate(results):
            result_title = result.get('title', '').lower()
            result_address = result.get('address', '').lower()

            if i < 5:  # Логируем первые 5 для отладки
                logger.info(f"   Карточка {i+1}:")
                logger.info(f"     Title: {result_title[:100]}")
                logger.info(f"     Address: {result_address[:150]}")

            # Полное совпадение (приоритет)
            if rc_lower in result_title or rc_lower in result_address:
                filtered_results.append(result)
                logger.debug(f"     ✓ Добавлена (полное совпадение)")
                continue

            # Частичное совпадение - проверяем основные слова
            # (минимум 2 слова из названия ЖК должны присутствовать)
            if len(rc_words) >= 2:
                title_words = set(result_title.split())
                address_words = set(result_address.split())

                matching_in_title = len(rc_words & title_words)
                matching_in_address = len(rc_words & address_words)

                if matching_in_title >= 2 or matching_in_address >= 2:
                    filtered_results.append(result)
                    logger.debug(f"     ✓ Добавлена (частичное совпадение: {matching_in_title} в title, {matching_in_address} в address)")
                elif i < 3:
                    logger.debug(f"     ✗ Пропущена (мало совпадений: {matching_in_title} в title, {matching_in_address} в address)")

        # Ограничиваем количество
        limited_results = filtered_results[:limit]

        # Маппинг полей для Pydantic моделей
        # Парсер карточек возвращает 'area_value' и 'price_raw', но модели ожидают 'total_area' и 'price'
        for result in limited_results:
            if 'area_value' in result and result['area_value']:
                result['total_area'] = result['area_value']
            if 'price_raw' in result and result['price_raw']:
                result['price'] = result['price_raw']
            # Конвертируем rooms в int если это строка с цифрой
            if 'rooms' in result and isinstance(result['rooms'], str) and result['rooms'].isdigit():
                result['rooms'] = int(result['rooms'])

        logger.info(f"✓ Найдено {len(limited_results)} похожих объявлений в ЖК {residential_complex}")

        return limited_results

    def search_similar(self, target_property: Dict, limit: int = 20) -> List[Dict]:
        """
        Автоматический поиск похожих квартир (широкий поиск по городу)

        Args:
            target_property: Целевой объект с полями price, total_area, rooms
            limit: максимальное количество результатов

        Returns:
            Список похожих объявлений
        """
        logger.info("🔍 Начинаем поиск похожих квартир...")

        # Формируем критерии поиска
        target_price = target_property.get('price', 100_000_000)
        target_area = target_property.get('total_area', 100)
        target_rooms = target_property.get('rooms', 2)

        # Строим URL поиска
        search_params = {
            'deal_type': 'sale',
            'offer_type': 'flat',
            'engine_version': '2',
            'price_min': int(target_price * 0.5),
            'price_max': int(target_price * 1.5),
            'minArea': int(target_area * 0.6),
            'maxArea': int(target_area * 1.4),
            'region': '2',  # Санкт-Петербург (настраивается)
        }

        # Комнаты (диапазон ±1)
        rooms_min = max(1, target_rooms - 1)
        rooms_max = target_rooms + 1
        for i in range(rooms_min, rooms_max + 1):
            search_params[f'room{i}'] = '1'

        url = f"{self.base_url}/cat.php?" + '&'.join([f"{k}={v}" for k, v in search_params.items()])

        logger.info(f"URL поиска: {url}")

        # Парсим результаты
        results = self.parse_search_page(url)

        # Ограничиваем количество
        limited_results = results[:limit]

        logger.info(f"✓ Найдено {len(limited_results)} похожих объявлений")

        return limited_results
