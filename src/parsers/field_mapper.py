"""
Система маппинга полей между разными источниками недвижимости

Каждый источник (Циан, Домклик, Авито) имеет свою структуру данных.
Этот модуль приводит данные к единому стандартному формату.

Стандартный формат (common schema):
{
    'url': str,
    'source': str,  # 'cian', 'domclick', 'avito'
    'title': str,
    'price': float,
    'currency': str,
    'total_area': float,
    'living_area': float,
    'kitchen_area': float,
    'rooms': int or 'студия',
    'floor': int,
    'floor_total': int,
    'address': str,
    'metro': List[str],
    'residential_complex': str,
    'build_year': int,
    'description': str,
    'images': List[str],
    'characteristics': Dict,

    # Премиум характеристики
    'дизайнерская отделка': bool,
    'панорамные виды': bool,
    'премиум локация': bool,
    'только рендеры': bool,
    'парковка': str,
    'высота потолков': float,
    'охрана 24/7': bool,
    'house_type': str,
}
"""

import logging
from typing import Dict, Callable, Any, Optional
import re

logger = logging.getLogger(__name__)


class FieldMapper:
    """
    Маппер полей для преобразования данных из источника в стандартный формат

    Поддерживает:
    - Переименование полей
    - Трансформацию значений
    - Значения по умолчанию
    - Вычисляемые поля
    """

    def __init__(self, source_name: str):
        """
        Args:
            source_name: Имя источника ('cian', 'domclick', и т.д.)
        """
        self.source_name = source_name
        self.mappings = {}
        self.transformers = {}
        self.defaults = {}

    def add_mapping(
        self,
        source_field: str,
        target_field: str,
        transformer: Optional[Callable[[Any], Any]] = None,
        default: Any = None
    ):
        """
        Добавить маппинг поля

        Args:
            source_field: Имя поля в исходных данных
            target_field: Имя поля в стандартном формате
            transformer: Функция преобразования значения
            default: Значение по умолчанию
        """
        self.mappings[source_field] = target_field
        if transformer:
            self.transformers[source_field] = transformer
        if default is not None:
            self.defaults[target_field] = default

    def transform(self, source_data: Dict) -> Dict:
        """
        Преобразовать данные из источника в стандартный формат

        Args:
            source_data: Данные из парсера

        Returns:
            Данные в стандартном формате
        """
        result = {}

        # Применяем маппинги
        for source_field, target_field in self.mappings.items():
            if source_field in source_data:
                value = source_data[source_field]

                # Применяем трансформацию, если есть
                if source_field in self.transformers:
                    try:
                        value = self.transformers[source_field](value)
                    except Exception as e:
                        logger.warning(f"Ошибка трансформации поля {source_field}: {e}")
                        value = None

                if value is not None:
                    result[target_field] = value

        # Добавляем значения по умолчанию для отсутствующих полей
        for target_field, default_value in self.defaults.items():
            if target_field not in result:
                result[target_field] = default_value

        # Копируем поля, которые уже в стандартном формате
        for key, value in source_data.items():
            if key not in self.mappings and key not in result:
                result[key] = value

        # Добавляем метаданные
        result['source'] = self.source_name

        return result


# === ФАБРИКА МАППЕРОВ ===

def create_cian_mapper() -> FieldMapper:
    """
    Создать маппер для Циана

    Циан уже возвращает данные почти в стандартном формате,
    поэтому маппинг минимальный
    """
    mapper = FieldMapper('cian')

    # Циан использует почти те же поля, что и стандарт
    # Просто добавляем алиасы на случай изменений
    mapper.add_mapping('price_raw', 'price', transformer=lambda x: float(x) if x else None)

    return mapper


def create_domclick_mapper() -> FieldMapper:
    """
    Создать маппер для Домклика

    Домклик имеет другую структуру данных, требуется больше преобразований
    """
    mapper = FieldMapper('domclick')

    # Основные поля
    mapper.add_mapping('dealType', 'deal_type', transformer=lambda x: x.lower() if x else 'sale')
    mapper.add_mapping('propertyType', 'property_type', transformer=lambda x: x.lower() if x else 'flat')

    # Цена
    mapper.add_mapping('bargainTerms.price', 'price', transformer=lambda x: float(x) if x else None)
    mapper.add_mapping('bargainTerms.currency', 'currency', default='RUB')

    # Площадь
    def parse_area(area_obj):
        """Парсинг объекта площади Домклика"""
        if isinstance(area_obj, dict):
            return float(area_obj.get('value', 0))
        return float(area_obj) if area_obj else None

    mapper.add_mapping('totalArea', 'total_area', transformer=parse_area)
    mapper.add_mapping('livingArea', 'living_area', transformer=parse_area)
    mapper.add_mapping('kitchenArea', 'kitchen_area', transformer=parse_area)

    # Комнаты
    def parse_rooms(rooms_data):
        """Парсинг комнат из Домклика"""
        if isinstance(rooms_data, dict):
            count = rooms_data.get('count', 0)
            if count == 0:
                return 'студия'
            return int(count)
        return int(rooms_data) if rooms_data else None

    mapper.add_mapping('roomsCount', 'rooms', transformer=parse_rooms)

    # Этаж
    mapper.add_mapping('floorNumber', 'floor', transformer=lambda x: int(x) if x else None)
    mapper.add_mapping('floorsCount', 'floor_total', transformer=lambda x: int(x) if x else None)

    # Адрес
    def parse_address(address_obj):
        """Парсинг адреса Домклика"""
        if isinstance(address_obj, dict):
            parts = []
            for key in ['street', 'house']:
                if key in address_obj and address_obj[key]:
                    parts.append(str(address_obj[key]))
            return ', '.join(parts) if parts else None
        return str(address_obj) if address_obj else None

    mapper.add_mapping('location.address', 'address', transformer=parse_address)

    # Метро
    def parse_metro(metro_data):
        """Парсинг метро из Домклика"""
        if isinstance(metro_data, list):
            return [m.get('name', '') for m in metro_data if isinstance(m, dict)]
        elif isinstance(metro_data, dict):
            return [metro_data.get('name', '')]
        return []

    mapper.add_mapping('location.undergrounds', 'metro', transformer=parse_metro)

    # ЖК
    mapper.add_mapping('building.name', 'residential_complex')

    # Год постройки
    mapper.add_mapping('building.buildYear', 'build_year', transformer=lambda x: int(x) if x else None)

    # Тип дома
    def parse_house_type(building_type):
        """Парсинг типа дома"""
        if not building_type:
            return None
        building_type = str(building_type).lower()
        if 'монолит' in building_type:
            return 'монолит'
        elif 'кирпич' in building_type:
            return 'кирпич'
        elif 'панель' in building_type:
            return 'панель'
        return building_type

    mapper.add_mapping('building.type', 'house_type', transformer=parse_house_type)

    # Высота потолков
    def parse_ceiling_height(height_data):
        """Парсинг высоты потолков"""
        if isinstance(height_data, dict):
            return float(height_data.get('value', 0)) if height_data.get('value') else None
        try:
            return float(height_data) if height_data else None
        except (ValueError, TypeError):
            return None

    mapper.add_mapping('ceilingHeight', 'ceiling_height', transformer=parse_ceiling_height)
    mapper.add_mapping('building.ceilingHeight', 'ceiling_height', transformer=parse_ceiling_height)

    # Описание
    mapper.add_mapping('description', 'description')

    # Изображения
    def parse_images(images_data):
        """Парсинг изображений"""
        if isinstance(images_data, list):
            return [img.get('url', img) if isinstance(img, dict) else img for img in images_data]
        return []

    mapper.add_mapping('photos', 'images', transformer=parse_images)

    return mapper


# === ГЛОБАЛЬНАЯ ФАБРИКА ===

_mappers_cache: Dict[str, FieldMapper] = {}


def get_field_mapper(source_name: str) -> FieldMapper:
    """
    Получить маппер для источника (с кэшированием)

    Args:
        source_name: Имя источника

    Returns:
        FieldMapper для данного источника
    """
    if source_name not in _mappers_cache:
        if source_name == 'cian':
            _mappers_cache[source_name] = create_cian_mapper()
        elif source_name == 'domclick':
            _mappers_cache[source_name] = create_domclick_mapper()
        else:
            logger.warning(f"Неизвестный источник {source_name}, используем базовый маппер")
            _mappers_cache[source_name] = FieldMapper(source_name)

    return _mappers_cache[source_name]


# === УТИЛИТЫ ===

def normalize_price(price_str: str) -> Optional[float]:
    """
    Нормализовать цену из строки

    Args:
        price_str: Строка с ценой (например, "5 000 000 ₽")

    Returns:
        Цена как float или None
    """
    if not price_str:
        return None

    # Убираем всё кроме цифр и точки/запятой
    cleaned = re.sub(r'[^\d,.]', '', str(price_str))
    cleaned = cleaned.replace(',', '.')

    try:
        return float(cleaned)
    except ValueError:
        return None


def normalize_area(area_str: str) -> Optional[float]:
    """
    Нормализовать площадь из строки

    Args:
        area_str: Строка с площадью (например, "45.5 м²")

    Returns:
        Площадь как float или None
    """
    if not area_str:
        return None

    # Убираем единицы измерения и пробелы
    cleaned = re.sub(r'[^\d,.]', '', str(area_str))
    cleaned = cleaned.replace(',', '.')

    try:
        return float(cleaned)
    except ValueError:
        return None


def normalize_rooms(rooms_str: str) -> Optional[int or str]:
    """
    Нормализовать количество комнат

    Args:
        rooms_str: Строка с комнатами

    Returns:
        Количество комнат (int) или 'студия'
    """
    if not rooms_str:
        return None

    rooms_str = str(rooms_str).lower()

    if 'студ' in rooms_str:
        return 'студия'

    # Извлекаем число
    match = re.search(r'(\d+)', rooms_str)
    if match:
        return int(match.group(1))

    return None
