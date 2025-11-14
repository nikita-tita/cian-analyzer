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

        # Вычисляем material_quality на основе количества фотографий
        if 'material_quality' not in result and 'images' in result:
            images = result['images']
            if isinstance(images, list):
                photo_count = len(images)
                if photo_count == 0:
                    result['material_quality'] = 'только_планировка'
                elif photo_count < 5:
                    result['material_quality'] = 'только_планировка'
                elif photo_count < 10:
                    result['material_quality'] = 'качественные_фото'
                else:
                    result['material_quality'] = 'качественные_фото_видео'

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

    # Санузлы
    def parse_bathrooms(bathrooms_data):
        """Парсинг количества санузлов"""
        if isinstance(bathrooms_data, dict):
            # Может быть {count: 2} или {total: 2}
            count = bathrooms_data.get('count') or bathrooms_data.get('total') or bathrooms_data.get('value')
            return int(count) if count else None
        try:
            return int(bathrooms_data) if bathrooms_data else None
        except (ValueError, TypeError):
            return None

    mapper.add_mapping('bathroomsCount', 'bathrooms', transformer=parse_bathrooms)
    mapper.add_mapping('bathrooms', 'bathrooms', transformer=parse_bathrooms)
    mapper.add_mapping('wcCount', 'bathrooms', transformer=parse_bathrooms)

    # Тип окон
    def parse_window_type(windows_data):
        """Парсинг типа окон"""
        if not windows_data:
            return 'пластиковые'  # дефолтное значение
        windows_str = str(windows_data).lower()
        if 'дерев' in windows_str:
            return 'деревянные'
        elif 'алюм' in windows_str:
            return 'алюм'
        elif 'панорам' in windows_str:
            return 'панорамные'
        elif 'евро' in windows_str:
            return 'евро'
        elif 'пластик' in windows_str or 'пвх' in windows_str:
            return 'пластиковые'
        return 'пластиковые'

    mapper.add_mapping('windowType', 'window_type', transformer=parse_window_type)
    mapper.add_mapping('windows', 'window_type', transformer=parse_window_type)

    # Лифты
    def parse_elevators(elevator_data):
        """Парсинг количества лифтов"""
        if isinstance(elevator_data, dict):
            count = elevator_data.get('count') or elevator_data.get('total') or elevator_data.get('value')
            if count is None:
                return 'нет'
            count = int(count)
        else:
            try:
                count = int(elevator_data) if elevator_data else 0
            except (ValueError, TypeError):
                return 'нет'

        if count == 0:
            return 'нет'
        elif count == 1:
            return 'один'
        elif count == 2:
            return 'два'
        else:
            return 'три+'

    mapper.add_mapping('building.elevators', 'elevator_count', transformer=parse_elevators)
    mapper.add_mapping('elevatorCount', 'elevator_count', transformer=parse_elevators)
    mapper.add_mapping('elevatorsCount', 'elevator_count', transformer=parse_elevators)

    # Уровень отделки
    def parse_finish_type(finish_data):
        """Парсинг уровня отделки"""
        if not finish_data:
            return 'стандартная'  # дефолтное значение
        finish_str = str(finish_data).lower()

        if 'черн' in finish_str or 'без отдел' in finish_str:
            return 'черновая'
        elif 'премиум' in finish_str or 'элит' in finish_str:
            return 'премиум'
        elif 'люкс' in finish_str:
            return 'люкс'
        elif 'улучш' in finish_str or 'дизайн' in finish_str:
            return 'улучшенная'
        elif 'стандарт' in finish_str or 'обычн' in finish_str:
            return 'стандартная'
        elif 'евро' in finish_str:
            return 'улучшенная'

        return 'стандартная'

    mapper.add_mapping('decoration', 'repair_level', transformer=parse_finish_type)
    mapper.add_mapping('repairType', 'repair_level', transformer=parse_finish_type)
    mapper.add_mapping('finishType', 'repair_level', transformer=parse_finish_type)

    # Вид из окна
    def parse_view(view_data):
        """Парсинг вида из окна"""
        if not view_data:
            return 'улица'  # дефолтное значение
        view_str = str(view_data).lower()

        if 'вод' in view_str or 'рек' in view_str or 'озер' in view_str or 'мор' in view_str:
            return 'вода'
        elif 'парк' in view_str or 'сквер' in view_str or 'лес' in view_str:
            return 'парк'
        elif 'город' in view_str or 'панорам' in view_str:
            return 'город'
        elif 'двор' in view_str or 'дом' in view_str:
            return 'дом'
        elif 'закат' in view_str:
            return 'закат'
        elif 'премиум' in view_str:
            return 'премиум'
        else:
            return 'улица'

    mapper.add_mapping('view', 'view_type', transformer=parse_view)
    mapper.add_mapping('viewType', 'view_type', transformer=parse_view)
    mapper.add_mapping('windowView', 'view_type', transformer=parse_view)

    # Качество материалов (фото/видео)
    def parse_material_quality(photos_data):
        """Парсинг качества материалов на основе фотографий"""
        # Эта функция будет вызвана с массивом photos
        if not photos_data or not isinstance(photos_data, list):
            return 'только_планировка'

        photo_count = len(photos_data)

        if photo_count == 0:
            return 'только_планировка'
        elif photo_count < 5:
            return 'только_планировка'
        elif photo_count < 10:
            return 'качественные_фото'
        else:
            return 'качественные_фото_видео'

    # Не используем маппинг для material_quality, так как он будет вычисляться отдельно

    # Статус собственности
    def parse_ownership(ownership_data):
        """Парсинг статуса собственности"""
        if not ownership_data:
            return '1_собственник_без_обременений'  # дефолтное значение

        ownership_str = str(ownership_data).lower()

        if 'ипотек' in ownership_str or 'рассрочк' in ownership_str:
            return 'ипотека_рассрочка'
        elif 'обремен' in ownership_str:
            return 'есть_обременения'
        elif 'несколько' in ownership_str or '2' in ownership_str or '3' in ownership_str:
            return '1+_собственников_без_обременений'
        else:
            return '1_собственник_без_обременений'

    mapper.add_mapping('ownershipType', 'ownership_status', transformer=parse_ownership)
    mapper.add_mapping('ownership', 'ownership_status', transformer=parse_ownership)
    mapper.add_mapping('seller.type', 'ownership_status', transformer=parse_ownership)

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
