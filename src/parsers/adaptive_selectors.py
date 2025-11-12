"""
Адаптивные селекторы для парсинга Cian

Этот модуль предоставляет гибкие методы поиска элементов на странице,
устойчивые к изменениям верстки.

Подходы:
1. Множественные селекторы с приоритетами
2. Поиск по содержимому текста
3. Поиск по частичному совпадению атрибутов
4. Фолбэк на более общие селекторы
"""

import re
import logging
from typing import List, Dict, Any, Optional, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)


class AdaptiveSelector:
    """
    Адаптивный селектор для поиска элементов с множественными стратегиями
    """

    def __init__(self, soup):
        """
        Args:
            soup: BeautifulSoup объект для парсинга
        """
        self.soup = soup
        self.stats = {}  # Статистика успешных селекторов

    def find_element(self, selectors: List[Dict[str, Any]],
                     description: str = "элемент"):
        """
        Найти элемент, пробуя множество селекторов по приоритету

        Args:
            selectors: Список словарей с параметрами поиска
                Формат: [
                    {'tag': 'div', 'attrs': {'data-name': 'Price'}},
                    {'tag': 'span', 'class_': lambda x: 'price' in str(x).lower()},
                    {'tag': 'div', 'text_contains': 'Цена:'}
                ]
            description: Описание элемента для логирования

        Returns:
            Найденный элемент или None
        """
        for i, selector in enumerate(selectors):
            try:
                # Стандартный поиск по тегу и атрибутам
                if 'tag' in selector:
                    tag = selector['tag']
                    attrs = selector.get('attrs', {})
                    class_ = selector.get('class_')

                    # Используем class_ если указан
                    if class_:
                        elem = self.soup.find(tag, class_=class_)
                    else:
                        elem = self.soup.find(tag, attrs)

                    if elem:
                        logger.debug(f"✓ {description}: найден селектором #{i+1}")
                        self._record_success(description, i)
                        return elem

                # Поиск по содержимому текста
                if 'text_contains' in selector:
                    text_pattern = selector['text_contains']
                    tag = selector.get('tag', True)  # True = любой тег

                    elem = self.soup.find(
                        tag,
                        string=lambda s: s and text_pattern.lower() in s.lower()
                    )

                    if elem:
                        logger.debug(f"✓ {description}: найден по тексту '{text_pattern}'")
                        self._record_success(description, i)
                        return elem

                # Поиск по регулярному выражению в атрибуте
                if 'attr_regex' in selector:
                    attr_name = selector['attr_regex']['attr']
                    pattern = selector['attr_regex']['pattern']
                    tag = selector.get('tag', True)

                    elem = self.soup.find(
                        tag,
                        attrs={attr_name: re.compile(pattern, re.IGNORECASE)}
                    )

                    if elem:
                        logger.debug(f"✓ {description}: найден по regex в {attr_name}")
                        self._record_success(description, i)
                        return elem

            except Exception as e:
                logger.debug(f"Селектор #{i+1} для '{description}' не сработал: {e}")
                continue

        logger.debug(f"⚠ {description}: не найден ни одним из {len(selectors)} селекторов")
        return None

    def find_elements(self, selectors: List[Dict[str, Any]],
                      description: str = "элементы"):
        """
        Найти все элементы, пробуя множество селекторов

        Args:
            selectors: Список словарей с параметрами поиска
            description: Описание элементов для логирования

        Returns:
            Список найденных элементов
        """
        for i, selector in enumerate(selectors):
            try:
                # Стандартный поиск
                if 'tag' in selector:
                    tag = selector['tag']
                    attrs = selector.get('attrs', {})
                    class_ = selector.get('class_')

                    if class_:
                        elems = self.soup.find_all(tag, class_=class_)
                    else:
                        elems = self.soup.find_all(tag, attrs)

                    if elems:
                        logger.debug(f"✓ {description}: найдено {len(elems)} элементов селектором #{i+1}")
                        self._record_success(description, i)
                        return elems

                # Поиск по частичному совпадению класса
                if 'class_contains' in selector:
                    pattern = selector['class_contains']
                    tag = selector.get('tag', True)

                    elems = self.soup.find_all(
                        tag,
                        class_=lambda x: x and pattern.lower() in ' '.join(x).lower()
                    )

                    if elems:
                        logger.debug(f"✓ {description}: найдено {len(elems)} по классу содержащему '{pattern}'")
                        self._record_success(description, i)
                        return elems

            except Exception as e:
                logger.debug(f"Селектор #{i+1} для '{description}' не сработал: {e}")
                continue

        logger.debug(f"⚠ {description}: не найдены ни одним из {len(selectors)} селекторов")
        return []

    def extract_text(self, selectors: List[Dict[str, Any]],
                     description: str = "текст") -> Optional[str]:
        """
        Извлечь текст из элемента с множественными стратегиями

        Returns:
            Извлеченный текст или None
        """
        elem = self.find_element(selectors, description)
        if elem:
            return elem.get_text(strip=True)
        return None

    def _record_success(self, element_type: str, selector_index: int):
        """Записать успешный селектор для анализа"""
        key = f"{element_type}:{selector_index}"
        self.stats[key] = self.stats.get(key, 0) + 1

    def get_stats(self) -> Dict[str, int]:
        """Получить статистику успешных селекторов"""
        return self.stats.copy()


# ============================================================================
# ПРЕДОПРЕДЕЛЕННЫЕ СЕЛЕКТОРЫ ДЛЯ КАРТОЧЕК ОБЪЯВЛЕНИЙ
# ============================================================================

CARD_SELECTORS = [
    # Приоритет 1: Официальный data-атрибут
    {'tag': 'article', 'attrs': {'data-name': 'CardComponent'}},

    # Приоритет 2: По классу с "card"
    {'tag': 'article', 'class_contains': 'card'},
    {'tag': 'div', 'class_contains': 'offer-card'},

    # Приоритет 3: По data-mark
    {'tag': 'div', 'attr_regex': {'attr': 'data-mark', 'pattern': r'offer'}},

    # Приоритет 4: Любой article (очень общий)
    {'tag': 'article'},
]

TITLE_SELECTORS = [
    # Карточки в списке
    {'tag': 'span', 'attrs': {'data-mark': 'OfferTitle'}},
    {'tag': 'h3'},
    {'tag': 'a', 'attrs': {'data-name': 'LinkArea'}},
    {'tag': 'div', 'class_contains': 'title'},

    # Детальная страница
    {'tag': 'h1', 'attrs': {'data-mark': 'OfferTitle'}},
    {'tag': 'h1'},
]

PRICE_SELECTORS = [
    {'tag': 'span', 'attrs': {'data-mark': 'MainPrice'}},
    {'tag': 'span', 'class_contains': 'price'},
    {'tag': 'div', 'class_contains': 'price'},
    {'tag': 'span', 'attrs': {'itemprop': 'price'}},
    {'tag': True, 'text_contains': '₽'},
]

ADDRESS_SELECTORS = [
    {'tag': 'a', 'attrs': {'data-name': 'GeoLabel'}},
    {'tag': 'a', 'attrs': {'data-name': 'AddressItem'}},
    {'tag': 'div', 'attrs': {'data-name': 'AddressContainer'}},
    {'tag': 'div', 'class_contains': 'address'},
    {'tag': 'span', 'attrs': {'itemprop': 'address'}},
]

AREA_SELECTORS = [
    # В подзаголовке
    {'tag': 'span', 'attrs': {'data-mark': 'OfferSubtitle'}},
    # В характеристиках
    {'tag': 'span', 'attrs': {'data-mark': 'OfferCharacteristics'}},
    # По тексту
    {'tag': True, 'text_contains': 'м²'},
]

METRO_SELECTORS = [
    {'tag': 'a', 'attrs': {'data-name': 'UndergroundLabel'}},
    {'tag': 'div', 'attrs': {'data-name': 'UndergroundItem'}},
    {'tag': 'span', 'class_contains': 'metro'},
    {'tag': True, 'text_contains': 'метро'},
]


# ============================================================================
# ФУНКЦИИ ИЗВЛЕЧЕНИЯ ДАННЫХ С АДАПТИВНЫМ ПАРСИНГОМ
# ============================================================================

def extract_price_with_fallback(elem) -> Dict[str, Any]:
    """
    Извлечь цену из элемента с множественными стратегиями

    Returns:
        {'price': str, 'price_raw': int} или {'price': None, 'price_raw': None}
    """
    from bs4 import BeautifulSoup

    selector = AdaptiveSelector(elem if isinstance(elem, BeautifulSoup) else BeautifulSoup(str(elem), 'lxml'))

    # Пробуем найти элемент с ценой
    price_elem = selector.find_element(PRICE_SELECTORS, "цена")

    if price_elem:
        price_text = price_elem.get_text(strip=True)

        # Извлекаем числовое значение
        price_numbers = re.sub(r'[^\d]', '', price_text)
        if price_numbers:
            return {
                'price': price_text,
                'price_raw': int(price_numbers)
            }

    return {'price': None, 'price_raw': None}


def extract_area_with_fallback(elem) -> Dict[str, Any]:
    """
    Извлечь площадь из элемента с множественными стратегиями

    Returns:
        {'area': str, 'area_value': float} или {'area': None, 'area_value': None}
    """
    from bs4 import BeautifulSoup

    selector = AdaptiveSelector(elem if isinstance(elem, BeautifulSoup) else BeautifulSoup(str(elem), 'lxml'))

    # Пробуем найти элемент с площадью
    area_elem = selector.find_element(AREA_SELECTORS, "площадь")

    if area_elem:
        area_text = area_elem.get_text(strip=True)

        # Извлекаем числовое значение
        area_match = re.search(r'([\d,\.]+)\s*м²', area_text)
        if area_match:
            area_str = area_match.group(1).replace(',', '.')
            try:
                return {
                    'area': area_match.group(0),
                    'area_value': float(area_str)
                }
            except ValueError:
                pass

    return {'area': None, 'area_value': None}


def extract_rooms_from_text(text: str) -> Optional[str]:
    """
    Извлечь количество комнат из текста с множественными паттернами

    Args:
        text: Текст для анализа

    Returns:
        Количество комнат ('1', '2', 'студия') или None
    """
    if not text:
        return None

    text_lower = text.lower()

    # Студия
    if 'студи' in text_lower:
        return 'студия'

    # N-комнатная
    patterns = [
        r'(\d+)-комн',
        r'(\d+)\s*комн',
        r'(\d+)к',
        r'(\d+)\s*к\.',
    ]

    for pattern in patterns:
        match = re.search(pattern, text_lower)
        if match:
            return match.group(1)

    return None


def extract_floor_from_text(text: str) -> Optional[int]:
    """
    Извлечь этаж из текста с множественными паттернами

    Returns:
        Номер этажа или None
    """
    if not text:
        return None

    # Паттерны: "4/9 этаж", "этаж 4", "4 этаж"
    patterns = [
        r'(\d+)/\d+\s*этаж',
        r'этаж\s*(\d+)',
        r'(\d+)\s*этаж',
    ]

    for pattern in patterns:
        match = re.search(pattern, text.lower())
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                pass

    return None
