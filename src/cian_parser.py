"""
Cian.ru Parser - парсер объявлений о недвижимости
"""

import requests
import time
import json
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from fake_useragent import UserAgent
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CianParser:
    """Парсер для cian.ru"""

    def __init__(self, delay: float = 2.0):
        """
        Инициализация парсера

        Args:
            delay: Задержка между запросами в секундах
        """
        self.delay = delay
        self.ua = UserAgent()
        self.session = requests.Session()
        self.base_url = "https://www.cian.ru"

    def _get_headers(self) -> Dict[str, str]:
        """Получить заголовки для запроса"""
        return {
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

    def _make_request(self, url: str) -> Optional[str]:
        """
        Выполнить HTTP запрос

        Args:
            url: URL для запроса

        Returns:
            HTML контент или None при ошибке
        """
        try:
            response = self.session.get(url, headers=self._get_headers(), timeout=30)
            response.raise_for_status()
            time.sleep(self.delay)
            return response.text
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при запросе {url}: {e}")
            return None

    def parse_listing_card(self, card: BeautifulSoup) -> Dict:
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
            'address': None,
            'metro': None,
            'area': None,
            'floor': None,
            'rooms': None,
            'url': None,
            'image_url': None,
        }

        try:
            # Заголовок
            title_elem = card.find('span', {'data-mark': 'OfferTitle'})
            if title_elem:
                data['title'] = title_elem.get_text(strip=True)

            # Цена
            price_elem = card.find('span', {'data-mark': 'MainPrice'})
            if price_elem:
                data['price'] = price_elem.get_text(strip=True)

            # Адрес
            address_elem = card.find('a', {'data-name': 'GeoLabel'})
            if address_elem:
                data['address'] = address_elem.get_text(strip=True)

            # Метро
            metro_elem = card.find('a', {'data-name': 'UndergroundLabel'})
            if metro_elem:
                data['metro'] = metro_elem.get_text(strip=True)

            # Площадь и другие характеристики
            characteristics = card.find_all('span', {'data-mark': 'OfferCharacteristics'})
            for char in characteristics:
                text = char.get_text(strip=True)
                if 'м²' in text:
                    data['area'] = text
                elif 'этаж' in text.lower():
                    data['floor'] = text

            # Ссылка на объявление
            link_elem = card.find('a', {'data-mark': 'OfferTitle'})
            if link_elem and link_elem.get('href'):
                data['url'] = self.base_url + link_elem['href'] if not link_elem['href'].startswith('http') else link_elem['href']

            # Изображение
            img_elem = card.find('img', {'data-mark': 'OfferPreviewImage'})
            if img_elem:
                data['image_url'] = img_elem.get('src') or img_elem.get('data-src')

        except Exception as e:
            logger.error(f"Ошибка при парсинге карточки: {e}")

        return data

    def parse_search_page(self, url: str) -> List[Dict]:
        """
        Парсинг страницы с результатами поиска

        Args:
            url: URL страницы поиска

        Returns:
            Список словарей с данными объявлений
        """
        logger.info(f"Парсинг страницы: {url}")

        html = self._make_request(url)
        if not html:
            return []

        soup = BeautifulSoup(html, 'lxml')

        # Поиск карточек объявлений
        cards = soup.find_all('article', {'data-name': 'CardComponent'})

        if not cards:
            # Альтернативный способ поиска карточек
            cards = soup.find_all('div', class_=lambda x: x and 'offer-card' in x.lower())

        logger.info(f"Найдено {len(cards)} объявлений")

        listings = []
        for card in cards:
            listing_data = self.parse_listing_card(card)
            if listing_data.get('title'):  # Добавляем только если есть заголовок
                listings.append(listing_data)

        return listings

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
        except Exception as e:
            logger.debug(f"Не удалось извлечь JSON-LD: {e}")
        return None

    def parse_detail_page(self, url: str) -> Dict:
        """
        Парсинг детальной страницы объявления

        Args:
            url: URL объявления

        Returns:
            Словарь с детальными данными объявления
        """
        logger.info(f"Парсинг детальной страницы: {url}")

        html = self._make_request(url)
        if not html:
            return {}

        soup = BeautifulSoup(html, 'lxml')

        data = {
            'url': url,
            'title': None,
            'price': None,
            'price_raw': None,
            'currency': None,
            'description': None,
            'address': None,
            'metro': [],
            'characteristics': {},
            'images': [],
            'seller': {},
            'area': None,
            'floor': None,
            'rooms': None,
        }

        try:
            # Сначала пробуем извлечь JSON-LD данные (самый надежный способ)
            json_ld = self._extract_json_ld(soup)
            if json_ld:
                logger.info("✓ Используем JSON-LD данные")

                # Основная информация из JSON-LD
                data['title'] = json_ld.get('name')

                # Цена из offers
                offers = json_ld.get('offers', {})
                if offers:
                    data['price_raw'] = offers.get('price')
                    data['currency'] = offers.get('priceCurrency')
                    if data['price_raw']:
                        # Форматируем цену для отображения
                        price_formatted = f"{data['price_raw']:,}".replace(',', ' ')
                        data['price'] = f"{price_formatted} ₽"

            # Дополняем данными из HTML (описание, характеристики и т.д.)

            # Заголовок (если не было в JSON-LD)
            if not data['title']:
                title_elem = soup.find('h1', {'data-mark': 'OfferTitle'})
                if not title_elem:
                    title_elem = soup.find('h1')
                if title_elem:
                    data['title'] = title_elem.get_text(strip=True)

            # Описание
            desc_elem = soup.find('div', {'data-name': 'Description'})
            if desc_elem:
                # Ищем параграф с описанием
                p_elem = desc_elem.find('p')
                if p_elem:
                    data['description'] = p_elem.get_text(strip=True)
                else:
                    data['description'] = desc_elem.get_text(strip=True)

            # Адрес
            address_elem = soup.find('a', {'data-name': 'GeoLabel'})
            if address_elem:
                data['address'] = address_elem.get_text(strip=True)

            # Метро
            metro_elems = soup.find_all('a', {'data-name': 'UndergroundLabel'})
            if metro_elems:
                data['metro'] = [metro.get_text(strip=True) for metro in metro_elems]

            # Характеристики из списков
            # Ищем все списки с характеристиками
            char_lists = soup.find_all('ul', class_=lambda x: x and 'item' in x.lower())
            for ul in char_lists:
                items = ul.find_all('li')
                for item in items:
                    text = item.get_text(strip=True)
                    # Парсим характеристики вида "Ключ: Значение"
                    if ':' in text:
                        parts = text.split(':', 1)
                        if len(parts) == 2:
                            data['characteristics'][parts[0].strip()] = parts[1].strip()
                    # Или добавляем как есть
                    elif text and len(text) < 100:
                        # Определяем тип характеристики
                        if 'м²' in text or 'кв.м' in text:
                            data['area'] = text
                        elif 'этаж' in text.lower():
                            data['floor'] = text
                        elif 'комн' in text.lower():
                            data['rooms'] = text

            # Дополнительные характеристики из таблиц
            char_items = soup.find_all('div', {'data-name': 'OfferFactItem'})
            for item in char_items:
                label = item.find('span', {'data-mark': 'OfferFactLabel'})
                value = item.find('span', {'data-mark': 'OfferFactValue'})
                if label and value:
                    data['characteristics'][label.get_text(strip=True)] = value.get_text(strip=True)

            # Изображения
            img_gallery = soup.find('div', {'data-name': 'GalleryPreviews'})
            if img_gallery:
                images = img_gallery.find_all('img')
                data['images'] = [img.get('src') or img.get('data-src') for img in images if img.get('src') or img.get('data-src')]

            # Альтернативный способ поиска изображений
            if not data['images']:
                all_images = soup.find_all('img', src=lambda x: x and 'cdn-p.cian.site' in x)
                data['images'] = [img.get('src') for img in all_images[:10]]  # Берем первые 10

            # Информация о продавце
            seller_name = soup.find('div', {'data-name': 'OfferAuthorName'})
            if seller_name:
                data['seller']['name'] = seller_name.get_text(strip=True)

            seller_type = soup.find('div', {'data-name': 'OfferAuthorType'})
            if seller_type:
                data['seller']['type'] = seller_type.get_text(strip=True)

        except Exception as e:
            logger.error(f"Ошибка при парсинге детальной страницы: {e}")

        return data

    def search_similar(self, target_property: Dict, limit: int = 20) -> List[Dict]:
        """
        Автоматический поиск похожих квартир для анализа

        Args:
            target_property: Целевой объект с полями:
                - price: цена
                - area: площадь
                - rooms: количество комнат
                - address: адрес (опционально)
            limit: максимальное количество результатов

        Returns:
            Список похожих объявлений
        """
        logger.info("Начинаем поиск похожих квартир...")

        # Формируем критерии поиска (±40% площадь, ±50% цена)
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
            'region': '2',  # Санкт-Петербург
        }

        # Добавляем комнаты (диапазон ±1)
        rooms_min = max(1, target_rooms - 1)
        rooms_max = target_rooms + 1
        for i in range(rooms_min, rooms_max + 1):
            search_params[f'room{i}'] = '1'

        # Формируем URL
        url = f"{self.base_url}/cat.php?" + '&'.join([f"{k}={v}" for k, v in search_params.items()])

        logger.info(f"URL поиска: {url}")

        # Парсим результаты
        results = self.parse_search_page(url)

        # Ограничиваем количество
        limited_results = results[:limit] if len(results) > limit else results

        logger.info(f"Найдено {len(limited_results)} похожих объявлений")

        return limited_results

    def search(self, query_params: Dict) -> List[Dict]:
        """
        Поиск объявлений по произвольным параметрам

        Args:
            query_params: Параметры поиска

        Returns:
            Список объявлений
        """
        # Формирование URL для поиска
        url = f"{self.base_url}/cat.php?" + '&'.join([f"{k}={v}" for k, v in query_params.items()])

        return self.parse_search_page(url)

    def save_to_json(self, data: List[Dict], filename: str):
        """
        Сохранить данные в JSON файл

        Args:
            data: Данные для сохранения
            filename: Имя файла
        """
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Данные сохранены в {filename}")
        except Exception as e:
            logger.error(f"Ошибка при сохранении в файл: {e}")
