"""
Простой парсер для Vercel (без Playwright)
Использует requests + BeautifulSoup для базового парсинга
"""

import requests
from bs4 import BeautifulSoup
from typing import Dict, Any, Optional, List
import re
import logging

logger = logging.getLogger(__name__)


class SimpleParser:
    """
    Упрощенный парсер для serverless окружения
    Не требует Playwright/браузер
    """

    def __init__(self, headless=True, delay=1.0):
        # Параметры для совместимости с PlaywrightParser
        self.headless = headless
        self.delay = delay
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

    def __enter__(self):
        """Поддержка контекстного менеджера"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Поддержка контекстного менеджера"""

    def parse_detail_page(self, url: str) -> Dict[str, Any]:
        """
        Парсинг страницы объекта (алиас для совместимости с PlaywrightParser)
        """
        return self.parse_property(url)

    def parse_property(self, url: str) -> Dict[str, Any]:
        """
        Парсинг объекта недвижимости

        Примечание: Это упрощенная версия для демо на Vercel.
        Для полноценного парсинга используйте локальную версию с Playwright.
        """
        logger.info(f"SimpleParser: Parsing {url}")

        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # Базовое извлечение данных
            title = soup.find('h1')
            title_text = title.get_text(strip=True) if title else ""

            # Извлекаем основные параметры из title
            rooms = self._extract_rooms(title_text)
            total_area = self._extract_area(title_text)

            # Цена
            price_elem = soup.find(attrs={'data-testid': 'price-amount'}) or soup.find(class_=re.compile('price', re.I))
            price = self._extract_price(price_elem.get_text() if price_elem else "")

            # Адрес
            address_elem = soup.find(attrs={'data-testid': 'address'}) or soup.find(class_=re.compile('address', re.I))
            address = address_elem.get_text(strip=True) if address_elem else ""

            result = {
                'title': title_text,
                'price': price,
                'rooms': rooms,
                'total_area': total_area,
                'address': address,
                'url': url,
                # Значения по умолчанию для обязательных полей
                'living_area': total_area * 0.7 if total_area else 50.0,
                'kitchen_area': total_area * 0.15 if total_area else 10.0,
                'floor': 5,
                'total_floors': 10,
                'build_year': 2015,
                'house_type': 'монолит',
                'repair_level': 'стандартная',
                'has_balcony': True,
                'bathrooms': 1,
                'ceiling_height': 2.7,
                'view_type': 'улица',
                'parking_type': 'подземная',
                'elevator_count': 1,
                'security_level': 'консьерж',
                'distance_to_metro': 10,
                'metro_transport': 'пешком',
                'district_type': 'центр',
                'has_furniture': False,
                'window_type': 'пластик',
                'photo_type': 'профессиональное',
                'object_status': 'стандарт',
                '_parser_type': 'simple',
                '_warning': 'Данные получены упрощенным парсером. Для точных данных используйте локальную версию.'
            }

            logger.info("SimpleParser: Successfully parsed basic data")
            return result

        except Exception as e:
            logger.error(f"SimpleParser: Error parsing {url}: {e}")
            # Возвращаем минимальные данные для демо
            return self._get_demo_data(url)

    def search_similar_in_building(self, target_property: Dict[str, Any], limit: int = 10) -> List[Dict[str, Any]]:
        """
        Поиск похожих объектов в том же ЖК

        Примечание: Упрощенная версия для демо.
        Возвращает тестовые данные.
        """
        logger.warning("SimpleParser: search_similar_in_building returns demo data only")
        return self._generate_demo_comparables(target_property, limit, in_building=True)

    def search_similar(self, target_property: Dict[str, Any], limit: int = 10) -> List[Dict[str, Any]]:
        """
        Поиск похожих объектов в городе

        Примечание: Упрощенная версия для демо.
        Возвращает тестовые данные.
        """
        logger.warning("SimpleParser: search_similar returns demo data only")
        return self._generate_demo_comparables(target_property, limit, in_building=False)

    def parse_comparables(self, search_url: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Парсинг аналогов

        Примечание: Упрощенная версия для демо.
        Возвращает тестовые данные.
        """
        logger.warning("SimpleParser: parse_comparables returns demo data only")
        return self._generate_demo_comparables({}, limit)

    def _generate_demo_comparables(self, target_property: Dict[str, Any], limit: int = 10, in_building: bool = False) -> List[Dict[str, Any]]:
        """Генерация демо-аналогов на основе целевого объекта"""
        # Для демо возвращаем несколько тестовых аналогов
        demo_comparables = []
        base_price = target_property.get('price', 16000000)
        base_area = target_property.get('total_area', 65.0)
        rooms = target_property.get('rooms', 2)

        for i in range(min(limit, 5)):
            # Генерируем похожие по параметрам объекты
            area_diff = (-10 + i * 5) if in_building else (-15 + i * 7)
            total_area = base_area + area_diff
            price_per_sqm = (base_price / base_area) * (0.95 + i * 0.02)
            price = int(total_area * price_per_sqm)

            demo_comparables.append({
                'title': f'{rooms}-комн. квартира, {int(total_area)} м²',
                'price': price,
                'price_per_sqm': int(price_per_sqm),
                'rooms': rooms,
                'total_area': total_area,
                'living_area': total_area * 0.65,
                'kitchen_area': 12.0,
                'floor': 5 + i,
                'total_floors': 17,
                'address': f'{"Тот же ЖК" if in_building else "Похожий район"}, корпус {i+1}',
                'url': f'https://www.cian.ru/sale/flat/demo{i}/',
                'build_year': 2015 + i,
                'house_type': 'монолит',
                'repair_level': 'стандартная' if i % 2 == 0 else 'улучшенная',
                'has_balcony': True,
                'bathrooms': 1,
                'ceiling_height': 2.7,
                'view_type': 'улица',
                'parking_type': 'подземная',
                'elevator_count': 2,
                'security_level': 'консьерж',
                'distance_to_metro': 10 + i * 2,
                'metro_transport': 'пешком',
                'district_type': 'центр',
                'has_furniture': False,
                'window_type': 'пластик',
                'photo_type': 'профессиональное',
                'object_status': 'стандарт',
                '_parser_type': 'simple_demo',
                '_in_same_building': in_building
            })

        return demo_comparables

    def _extract_rooms(self, text: str) -> int:
        """Извлечь количество комнат"""
        if 'студ' in text.lower():
            return 0
        match = re.search(r'(\d+)-комн', text)
        if match:
            return int(match.group(1))
        return 2  # default

    def _extract_area(self, text: str) -> Optional[float]:
        """Извлечь площадь"""
        match = re.search(r'(\d+(?:\.\d+)?)\s*м', text)
        if match:
            return float(match.group(1))
        return None

    def _extract_price(self, text: str) -> Optional[int]:
        """Извлечь цену"""
        # Убираем всё кроме цифр
        digits = re.sub(r'\D', '', text)
        if digits:
            return int(digits)
        return None

    def _get_demo_data(self, url: str) -> Dict[str, Any]:
        """Демо-данные при ошибке парсинга"""
        return {
            'title': '2-комн. квартира, 65 м²',
            'price': 16000000,
            'rooms': 2,
            'total_area': 65.0,
            'living_area': 45.0,
            'kitchen_area': 12.0,
            'floor': 7,
            'total_floors': 17,
            'build_year': 2018,
            'house_type': 'монолит',
            'repair_level': 'стандартная',
            'has_balcony': True,
            'bathrooms': 1,
            'ceiling_height': 2.7,
            'view_type': 'улица',
            'parking_type': 'подземная',
            'elevator_count': 2,
            'security_level': 'консьерж',
            'distance_to_metro': 10,
            'metro_transport': 'пешком',
            'district_type': 'центр',
            'has_furniture': False,
            'window_type': 'пластик',
            'photo_type': 'профессиональное',
            'object_status': 'стандарт',
            'address': 'Демо адрес',
            'url': url,
            '_parser_type': 'demo',
            '_warning': 'Ошибка парсинга. Показаны демо-данные.'
        }
