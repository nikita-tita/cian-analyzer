"""
Утилиты для адаптивной системы парсинга

Набор helper функций для упрощения работы с парсерами
"""

import logging
from typing import Dict, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def detect_platform(url: str) -> str:
    """
    Определить платформу по URL

    Args:
        url: URL объявления

    Returns:
        Название платформы ('cian', 'domclick', 'avito', 'yandex', 'unknown')

    Examples:
        >>> detect_platform('https://www.cian.ru/sale/flat/12345/')
        'cian'
        >>> detect_platform('https://domclick.ru/card/sale__flat__12345')
        'domclick'
    """
    url_lower = url.lower()

    if 'cian.ru' in url_lower:
        return 'cian'
    elif 'domclick.ru' in url_lower:
        return 'domclick'
    elif 'avito.ru' in url_lower:
        return 'avito'
    elif 'realty.yandex.ru' in url_lower or 'yandex.ru/realty' in url_lower:
        return 'yandex'
    else:
        return 'unknown'


def is_valid_property_url(url: str) -> bool:
    """
    Проверить, является ли URL валидным для парсинга объявления

    Args:
        url: URL для проверки

    Returns:
        True если URL валиден

    Examples:
        >>> is_valid_property_url('https://www.cian.ru/sale/flat/12345/')
        True
        >>> is_valid_property_url('not-a-url')
        False
    """
    try:
        parsed = urlparse(url)
        return all([parsed.scheme, parsed.netloc])
    except:
        return False


def normalize_property_data(data: Dict) -> Dict:
    """
    Нормализовать данные объявления для единообразия

    Args:
        data: Сырые данные объявления

    Returns:
        Нормализованные данные

    Examples:
        >>> data = {'price': '10000000', 'total_area': '50.5'}
        >>> normalized = normalize_property_data(data)
        >>> type(normalized['price'])
        <class 'float'>
    """
    normalized = data.copy()

    # Преобразуем числовые поля
    numeric_fields = ['price', 'total_area', 'living_area', 'kitchen_area', 'ceiling_height']
    for field in numeric_fields:
        if field in normalized and normalized[field] is not None:
            try:
                if isinstance(normalized[field], str):
                    # Убираем пробелы и валютные символы
                    cleaned = normalized[field].replace(' ', '').replace('₽', '').replace(',', '.')
                    normalized[field] = float(cleaned)
                elif not isinstance(normalized[field], (int, float)):
                    normalized[field] = float(normalized[field])
            except (ValueError, TypeError):
                logger.warning(f"Не удалось преобразовать {field}: {normalized[field]}")

    # Преобразуем целочисленные поля
    integer_fields = ['floor', 'floor_total', 'build_year']
    for field in integer_fields:
        if field in normalized and normalized[field] is not None:
            try:
                if not isinstance(normalized[field], int):
                    normalized[field] = int(float(normalized[field]))
            except (ValueError, TypeError):
                logger.warning(f"Не удалось преобразовать {field}: {normalized[field]}")

    # Нормализуем комнаты
    if 'rooms' in normalized:
        rooms = normalized['rooms']
        if isinstance(rooms, str):
            if 'студ' in rooms.lower():
                normalized['rooms'] = 'студия'
            else:
                import re
                match = re.search(r'(\d+)', rooms)
                if match:
                    normalized['rooms'] = int(match.group(1))

    # Нормализуем массивы
    if 'metro' in normalized and isinstance(normalized['metro'], str):
        normalized['metro'] = [normalized['metro']]

    if 'images' in normalized and not isinstance(normalized['images'], list):
        normalized['images'] = []

    return normalized


def merge_property_data(*sources: Dict) -> Dict:
    """
    Объединить данные из нескольких источников (приоритет первому)

    Args:
        *sources: Словари с данными для объединения

    Returns:
        Объединенный словарь

    Examples:
        >>> source1 = {'title': 'Test', 'price': 10000000}
        >>> source2 = {'price': 9000000, 'area': 50}
        >>> merged = merge_property_data(source1, source2)
        >>> merged['price']  # Приоритет у первого источника
        10000000
        >>> merged['area']  # Берется из второго если нет в первом
        50
    """
    result = {}

    for source in sources:
        if not source:
            continue

        for key, value in source.items():
            # Добавляем только если ключа еще нет или значение None/пустое
            if key not in result or result[key] is None or result[key] == '':
                if value is not None and value != '':
                    result[key] = value

    return result


def filter_properties(
    properties: List[Dict],
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    min_area: Optional[float] = None,
    max_area: Optional[float] = None,
    rooms: Optional[int] = None,
    sources: Optional[List[str]] = None
) -> List[Dict]:
    """
    Фильтровать список объявлений по критериям

    Args:
        properties: Список объявлений
        min_price: Минимальная цена
        max_price: Максимальная цена
        min_area: Минимальная площадь
        max_area: Максимальная площадь
        rooms: Количество комнат
        sources: Список источников для фильтрации

    Returns:
        Отфильтрованный список

    Examples:
        >>> props = [
        ...     {'price': 10000000, 'total_area': 50, 'rooms': 2, 'source': 'cian'},
        ...     {'price': 15000000, 'total_area': 70, 'rooms': 3, 'source': 'domclick'},
        ... ]
        >>> filtered = filter_properties(props, max_price=12000000, rooms=2)
        >>> len(filtered)
        1
    """
    filtered = properties

    # Фильтр по цене
    if min_price is not None:
        filtered = [p for p in filtered if p.get('price', 0) >= min_price]

    if max_price is not None:
        filtered = [p for p in filtered if p.get('price', float('inf')) <= max_price]

    # Фильтр по площади
    if min_area is not None:
        filtered = [p for p in filtered if p.get('total_area', 0) >= min_area]

    if max_area is not None:
        filtered = [p for p in filtered if p.get('total_area', float('inf')) <= max_area]

    # Фильтр по комнатам
    if rooms is not None:
        filtered = [p for p in filtered if p.get('rooms') == rooms]

    # Фильтр по источникам
    if sources:
        filtered = [p for p in filtered if p.get('source') in sources]

    return filtered


def deduplicate_properties(properties: List[Dict], key: str = 'url') -> List[Dict]:
    """
    Удалить дубликаты из списка объявлений

    Args:
        properties: Список объявлений
        key: Ключ для определения дубликатов (по умолчанию 'url')

    Returns:
        Список без дубликатов

    Examples:
        >>> props = [
        ...     {'url': 'test.com/1', 'price': 10000000},
        ...     {'url': 'test.com/1', 'price': 10000000},
        ...     {'url': 'test.com/2', 'price': 15000000},
        ... ]
        >>> unique = deduplicate_properties(props)
        >>> len(unique)
        2
    """
    seen = set()
    unique = []

    for prop in properties:
        identifier = prop.get(key)
        if identifier and identifier not in seen:
            seen.add(identifier)
            unique.append(prop)

    return unique


def sort_properties(
    properties: List[Dict],
    by: str = 'price',
    reverse: bool = False
) -> List[Dict]:
    """
    Сортировать объявления по заданному критерию

    Args:
        properties: Список объявлений
        by: Поле для сортировки ('price', 'total_area', 'price_per_sqm')
        reverse: Обратная сортировка (по убыванию)

    Returns:
        Отсортированный список

    Examples:
        >>> props = [
        ...     {'price': 15000000, 'total_area': 70},
        ...     {'price': 10000000, 'total_area': 50},
        ... ]
        >>> sorted_props = sort_properties(props, by='price')
        >>> sorted_props[0]['price']
        10000000
    """
    # Вычисляем price_per_sqm если нужно
    if by == 'price_per_sqm':
        for prop in properties:
            if prop.get('price') and prop.get('total_area'):
                prop['price_per_sqm'] = prop['price'] / prop['total_area']
            else:
                prop['price_per_sqm'] = float('inf') if reverse else 0

    try:
        return sorted(
            properties,
            key=lambda x: x.get(by, 0) or 0,
            reverse=reverse
        )
    except (TypeError, KeyError):
        logger.warning(f"Не удалось отсортировать по {by}, возвращаем исходный список")
        return properties


def calculate_property_score(property_data: Dict, target: Dict) -> float:
    """
    Вычислить score объявления относительно целевого

    Score от 0 до 100, где 100 - идеальное совпадение

    Args:
        property_data: Данные объявления
        target: Целевые параметры

    Returns:
        Score от 0 до 100

    Examples:
        >>> prop = {'price': 10000000, 'total_area': 50, 'rooms': 2}
        >>> target = {'price': 10000000, 'total_area': 50, 'rooms': 2}
        >>> score = calculate_property_score(prop, target)
        >>> score
        100.0
    """
    score = 0.0
    weights = {
        'price': 0.4,
        'total_area': 0.3,
        'rooms': 0.2,
        'floor': 0.1,
    }

    for field, weight in weights.items():
        if field not in target or target[field] is None:
            continue

        if field not in property_data or property_data[field] is None:
            continue

        target_value = target[field]
        actual_value = property_data[field]

        if field in ['price', 'total_area']:
            # Числовые поля - вычисляем отклонение
            if target_value > 0:
                deviation = abs(actual_value - target_value) / target_value
                field_score = max(0, 100 * (1 - deviation))
            else:
                field_score = 0
        else:
            # Категориальные поля - точное совпадение
            field_score = 100 if actual_value == target_value else 0

        score += field_score * weight

    return round(score, 2)


def format_property_summary(property_data: Dict) -> str:
    """
    Форматировать краткую сводку объявления для вывода

    Args:
        property_data: Данные объявления

    Returns:
        Форматированная строка

    Examples:
        >>> prop = {
        ...     'title': 'Test Property',
        ...     'price': 10000000,
        ...     'total_area': 50,
        ...     'rooms': 2,
        ...     'source': 'cian'
        ... }
        >>> summary = format_property_summary(prop)
        >>> 'Test Property' in summary
        True
    """
    title = property_data.get('title', 'Без названия')[:50]
    price = property_data.get('price', 0)
    area = property_data.get('total_area', 0)
    rooms = property_data.get('rooms', 'N/A')
    source = property_data.get('source', 'unknown').upper()

    summary = f"[{source}] {title}"

    if price:
        summary += f" | {price:,.0f} ₽"

    if area:
        summary += f" | {area} м²"

    if rooms:
        summary += f" | {rooms} комн."

    if price and area and area > 0:
        price_per_sqm = price / area
        summary += f" | {price_per_sqm:,.0f} ₽/м²"

    return summary


def validate_property_data(property_data: Dict) -> tuple[bool, List[str]]:
    """
    Валидировать данные объявления

    Args:
        property_data: Данные для валидации

    Returns:
        (is_valid, errors) где errors - список ошибок

    Examples:
        >>> prop = {'title': 'Test', 'price': 10000000, 'total_area': 50}
        >>> is_valid, errors = validate_property_data(prop)
        >>> is_valid
        True
    """
    errors = []

    # Обязательные поля
    required_fields = ['title', 'price', 'total_area']
    for field in required_fields:
        if field not in property_data or property_data[field] is None:
            errors.append(f"Отсутствует обязательное поле: {field}")

    # Валидация цены
    price = property_data.get('price')
    if price is not None:
        if not isinstance(price, (int, float)) or price <= 0:
            errors.append(f"Некорректная цена: {price}")

    # Валидация площади
    area = property_data.get('total_area')
    if area is not None:
        if not isinstance(area, (int, float)) or area <= 0 or area > 1000:
            errors.append(f"Некорректная площадь: {area}")

    # Валидация этажа
    floor = property_data.get('floor')
    floor_total = property_data.get('floor_total')
    if floor is not None and floor_total is not None:
        if floor > floor_total:
            errors.append(f"Этаж {floor} больше общего количества этажей {floor_total}")

    is_valid = len(errors) == 0
    return is_valid, errors
