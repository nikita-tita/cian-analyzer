"""
Pydantic модели для валидации данных
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator, root_validator
from datetime import datetime


class PropertyBase(BaseModel):
    """Базовая модель недвижимости"""
    url: str
    title: Optional[str] = None
    price: Optional[float] = Field(None, gt=0)
    total_area: Optional[float] = Field(None, gt=0)
    living_area: Optional[float] = Field(None, gt=0)
    kitchen_area: Optional[float] = Field(None, gt=0)
    rooms: Optional[int] = Field(None, ge=0, le=10)  # 0 = студия
    floor: Optional[int] = None
    total_floors: Optional[int] = None
    address: Optional[str] = None
    metro: List[str] = []
    description: Optional[str] = None

    @validator('metro', pre=True)
    def parse_metro(cls, v):
        """Парсинг метро - преобразуем None в пустой список"""
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return v

    @validator('rooms', pre=True)
    def parse_rooms(cls, v):
        """
        Парсинг количества комнат с обработкой "студия"

        Студия = 0 комнат (открытая планировка без выделенных спален)
        """
        if v is None:
            return None
        if isinstance(v, str):
            v_lower = v.lower().strip()
            # Обрабатываем студию
            if 'студ' in v_lower:
                return 0
            # Извлекаем число из строки
            import re
            match = re.search(r'\d+', v)
            if match:
                return int(match.group())
            return None
        return v

    @validator('price', 'total_area', pre=True)
    def parse_numeric(cls, v):
        """Парсинг числовых значений из строк"""
        if isinstance(v, str):
            # Убираем пробелы и запятые
            v = v.replace(' ', '').replace(',', '.')
            # Извлекаем только цифры и точку
            import re
            match = re.search(r'[\d.]+', v)
            if match:
                return float(match.group())
        return v


class TargetProperty(PropertyBase):
    """Целевой объект для анализа"""
    price_per_sqm: Optional[float] = None

    # ═══════════════════════════════════════════════════════════════════════
    # КЛАСТЕР 1: ОТДЕЛКА И СОСТОЯНИЕ
    # ═══════════════════════════════════════════════════════════════════════
    repair_level: Optional[str] = "стандартная"  # черновая | стандартная | улучшенная | премиум | люкс
    house_condition: Optional[str] = "хорошее"  # новостройка | современное | хорошее | требует | ветхое
    build_year: Optional[int] = Field(None, ge=1800, le=2030)

    # ═══════════════════════════════════════════════════════════════════════
    # КЛАСТЕР 2: ХАРАКТЕРИСТИКИ ДОМА
    # ═══════════════════════════════════════════════════════════════════════
    house_type: Optional[str] = None  # монолит | кирпич | панель | дерево | смешанный
    elevator_count: Optional[str] = "один"  # нет | один | два | три+ | панорамный
    ceiling_height: Optional[float] = Field(None, ge=2.0, le=5.0)
    bathrooms: Optional[int] = Field(None, ge=0, le=10)  # количество ванных комнат
    window_type: Optional[str] = "пластиковые"  # деревянные | алюм | пластиковые | евро | панорамные

    # ═══════════════════════════════════════════════════════════════════════
    # КЛАСТЕР 3: ЛОКАЦИЯ И ДОСТУПНОСТЬ
    # ═══════════════════════════════════════════════════════════════════════
    metro_distance_min: Optional[int] = Field(None, ge=0, le=60)
    district_type: Optional[str] = "residential"  # center | near_center | residential | transitional | remote
    transport_accessibility: Optional[str] = "доступно"  # метро_рядом | метро_близко | доступно | транспорт | плохо
    surroundings: List[str] = []  # парки | школы | торговля | офисы | промышленность | престиж

    # ═══════════════════════════════════════════════════════════════════════
    # КЛАСТЕР 4: БЕЗОПАСНОСТЬ И СЕРВИС
    # ═══════════════════════════════════════════════════════════════════════
    security_level: Optional[str] = "нет"  # нет | дневная | 24/7 | 24/7+консьерж | 24/7+консьерж+видео
    parking_type: Optional[str] = "нет"  # нет | открытая | навес | закрытая | подземная | несколько | гараж
    parking_spaces: Optional[int] = Field(None, ge=0)  # количество машиномест (без ограничения)
    sports_amenities: List[str] = []  # детская | спортплощадка | тренажер | бассейн | полный

    # ═══════════════════════════════════════════════════════════════════════
    # КЛАСТЕР 5: ВИД И ЭСТЕТИКА
    # ═══════════════════════════════════════════════════════════════════════
    view_type: Optional[str] = "улица"  # худогов | дом | улица | парк | вода | город | закат | премиум
    noise_level: Optional[str] = "нормально"  # очень_тихо | тихо | нормально | шумно | очень_шумно
    crowded_level: Optional[str] = "нормально"  # пустынно | спокойно | нормально | оживленно | очень_оживленно

    # ═══════════════════════════════════════════════════════════════════════
    # КЛАСТЕР 6: ИНФОРМАЦИЯ И РИСКИ
    # ═══════════════════════════════════════════════════════════════════════
    photo_type: Optional[str] = "реальные"  # реальные | реальные+рендеры | рендеры+видео | только_рендеры | стройка
    object_status: Optional[str] = "готов"  # готов | отделка | строительство | котлован | проект

    # НОВЫЕ ПОЛЯ (2025-01-12)
    material_quality: Optional[str] = "качественные_фото"  # качественные_фото_видео | качественные_фото | только_рендеры | только_планировка
    ownership_status: Optional[str] = "1_собственник_без_обременений"  # 1_собственник_без_обременений | 1+_собственников_без_обременений | ипотека_рассрочка | есть_обременения

    # Дополнительные поля
    images: List[str] = []
    characteristics: Dict[str, Any] = {}
    seller: Dict[str, Any] = {}

    # Обратная совместимость (deprecated, будут удалены)
    has_design: Optional[bool] = None
    panoramic_views: Optional[bool] = None
    premium_location: Optional[bool] = None
    parking: Optional[str] = None
    security_247: Optional[bool] = None
    has_elevator: Optional[bool] = None
    renders_only: Optional[bool] = None

    @validator('price_per_sqm', always=True)
    def calculate_price_per_sqm(cls, v, values):
        """Автоматический расчет цены за м²"""
        if v is None and values.get('price') and values.get('total_area'):
            return values['price'] / values['total_area']
        return v

    @validator('living_area')
    def validate_living_area(cls, v, values):
        """Проверка что жилая площадь не больше общей"""
        if v and values.get('total_area') and v > values['total_area']:
            raise ValueError('Жилая площадь не может быть больше общей')
        return v

    class Config:
        validate_assignment = True
        # Разрешаем дополнительные поля (для русских названий)
        extra = 'allow'

    def __init__(self, **data):
        """Инициализация с маппингом русских названий"""
        # Маппинг русских названий на английские
        russian_to_english = {
            # КЛАСТЕР 1: ОТДЕЛКА И СОСТОЯНИЕ
            'уровень отделки': 'repair_level',
            'состояние дома': 'house_condition',
            'год постройки': 'build_year',

            # КЛАСТЕР 2: ХАРАКТЕРИСТИКИ ДОМА
            'тип дома': 'house_type',
            'количество лифтов': 'elevator_count',
            'высота потолков': 'ceiling_height',
            'ванные комнаты': 'bathrooms',
            'тип окон': 'window_type',

            # КЛАСТЕР 3: ЛОКАЦИЯ И ДОСТУПНОСТЬ
            'расстояние до метро': 'metro_distance_min',
            'тип района': 'district_type',
            'транспортная доступность': 'transport_accessibility',
            'окружение': 'surroundings',

            # КЛАСТЕР 4: БЕЗОПАСНОСТЬ И СЕРВИС
            'уровень безопасности': 'security_level',
            'тип парковки': 'parking_type',
            'машиномест': 'parking_spaces',
            'спортивная инфраструктура': 'sports_amenities',

            # КЛАСТЕР 5: ВИД И ЭСТЕТИКА
            'вид из окна': 'view_type',
            'уровень шума': 'noise_level',
            'людность': 'crowded_level',

            # КЛАСТЕР 6: ИНФОРМАЦИЯ И РИСКИ
            'тип фотографий': 'photo_type',
            'статус объекта': 'object_status',

            # НОВЫЕ ПОЛЯ (2025-01-12)
            'качество материалов': 'material_quality',
            'статус собственности': 'ownership_status',

            # Обратная совместимость (deprecated)
            'дизайнерская отделка': 'has_design',
            'панорамные виды': 'panoramic_views',
            'премиум локация': 'premium_location',
            'только рендеры': 'renders_only',
            'парковка': 'parking',
            'охрана 24/7': 'security_247',
        }

        # Преобразуем русские ключи в английские
        mapped_data = {}
        for key, value in data.items():
            english_key = russian_to_english.get(key, key)
            mapped_data[english_key] = value

        super().__init__(**mapped_data)


class ComparableProperty(TargetProperty):
    """Аналог для сравнения"""
    has_design: bool = False
    distance_km: Optional[float] = None  # Расстояние от целевого объекта
    similarity_score: Optional[float] = Field(None, ge=0, le=1)  # Оценка схожести
    excluded: bool = False  # Исключен из анализа

    # PATCH 2: Флаги качества данных (вместо ValidationError)
    quality_flags: List[str] = []

    @root_validator(pre=False)
    def validate_minimum_data(cls, values):
        """
        PATCH 2: Soft validation - добавляем флаги качества вместо исключений

        Вместо того чтобы выбрасывать ValidationError, помечаем проблемные аналоги
        флагами. Это позволяет продолжить анализ даже с неполными данными.
        """
        flags = values.get('quality_flags', [])
        price = values.get('price')
        area = values.get('total_area')
        ppsm = values.get('price_per_sqm')

        # Проверка минимальных обязательных полей
        has_price_area = bool(price and area)
        has_ppsm_area = bool(ppsm and area)

        if not (has_price_area or has_ppsm_area):
            flags.append('insufficient_numeric_fields')

        # Проверка адреса и локации
        if not values.get('address'):
            flags.append('missing_address')

        # Проверка количества комнат
        if not values.get('rooms'):
            flags.append('missing_rooms')

        # Проверка наличия критичных полей
        if price and price <= 0:
            flags.append('invalid_price')

        if area and area <= 0:
            flags.append('invalid_area')

        values['quality_flags'] = flags
        return values

    class Config(TargetProperty.Config):
        validate_assignment = True


class AnalysisRequest(BaseModel):
    """Запрос на анализ"""
    target_property: TargetProperty
    comparables: List[ComparableProperty] = []

    # Параметры анализа
    filter_outliers: bool = True
    use_median: bool = True

    class Config:
        validate_assignment = True


class PriceScenario(BaseModel):
    """Сценарий продажи"""
    name: str
    type: str
    description: str
    start_price: float
    expected_final_price: float
    time_months: int
    base_probability: float
    reduction_rate: float

    # Расчетные данные
    price_trajectory: List[Dict[str, float]] = []
    monthly_probability: List[float] = []
    cumulative_probability: List[float] = []
    financials: Dict[str, Any] = {}

    # НОВОЕ: Флаг рекомендуемого сценария (автоматически выбирается по максимальному expected_value)
    is_recommended: bool = False
    recommendation_reason: Optional[str] = None


class AnalysisResult(BaseModel):
    """Результат анализа"""
    timestamp: datetime = Field(default_factory=datetime.now)

    target_property: TargetProperty
    comparables: List[ComparableProperty]

    # Рыночная статистика
    market_statistics: Dict[str, Any]

    # Справедливая цена
    fair_price_analysis: Dict[str, Any]

    # Сценарии
    price_scenarios: List[PriceScenario]

    # Сильные и слабые стороны
    strengths_weaknesses: Dict[str, Any]

    # Данные для графиков
    comparison_chart_data: Dict[str, Any]
    box_plot_data: Dict[str, Any]

    # НОВЫЕ МЕТРИКИ
    # Диапазон справедливой цены (min, fair, recommended, max)
    price_range: Dict[str, Any] = {}

    # Индекс привлекательности объекта (0-100)
    attractiveness_index: Dict[str, Any] = {}

    # Прогноз времени продажи
    time_forecast: Dict[str, Any] = {}

    # Анализ чувствительности к цене
    price_sensitivity: List[Dict[str, Any]] = []

    # Рекомендации
    recommendations: List[Dict[str, Any]] = []

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# ═══════════════════════════════════════════════════════════════════════
# УТИЛИТЫ ДЛЯ НОРМАЛИЗАЦИИ И ВАЛИДАЦИИ ДАННЫХ
# ═══════════════════════════════════════════════════════════════════════

def normalize_property_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Нормализация данных недвижимости с умными дефолтами

    Применяет контекстно-зависимые дефолты на основе известных параметров:
    - Высота потолков зависит от года постройки и типа дома
    - Количество санузлов зависит от площади и комнат
    - Характеристики отделки зависят от ЖК и цены

    Args:
        data: Сырые данные объекта

    Returns:
        Нормализованные данные с заполненными пропусками
    """
    normalized = data.copy()

    # 1. PATCH 2: Восстановление недостающих полей (price ↔ price_per_sqm ↔ total_area)
    price = normalized.get('price')
    ppsm = normalized.get('price_per_sqm')
    area = normalized.get('total_area')

    # Приводим к числам если строки
    try:
        price = float(price) if price else None
    except (ValueError, TypeError):
        price = None

    try:
        ppsm = float(ppsm) if ppsm else None
    except (ValueError, TypeError):
        ppsm = None

    try:
        area = float(area) if area else None
    except (ValueError, TypeError):
        area = None

    # Восстанавливаем price_per_sqm из price и area
    if not ppsm and price and area and area > 0:
        ppsm = price / area
        normalized['price_per_sqm'] = ppsm

    # НОВОЕ: Восстанавливаем price из price_per_sqm и area
    if not price and ppsm and area:
        price = ppsm * area
        normalized['price'] = price

    # НОВОЕ: Восстанавливаем total_area из price и price_per_sqm
    if not area and price and ppsm and ppsm > 0:
        area = price / ppsm
        normalized['total_area'] = area

    # 2. Умные дефолты для высоты потолков
    if not normalized.get('ceiling_height'):
        build_year = normalized.get('build_year')
        house_type = (normalized.get('house_type') or '').lower()

        # Современные монолиты
        if build_year and build_year >= 2010:
            if 'монолит' in house_type:
                normalized['ceiling_height'] = 3.0
            elif 'кирпич' in house_type:
                normalized['ceiling_height'] = 2.8
            else:
                normalized['ceiling_height'] = 2.7
        # Старый фонд
        elif build_year and build_year < 1970:
            normalized['ceiling_height'] = 3.2  # Сталинки
        # Хрущевки/брежневки
        elif build_year and 1960 <= build_year < 1990:
            normalized['ceiling_height'] = 2.5
        # Средний дефолт
        else:
            normalized['ceiling_height'] = 2.7

    # 3. Умные дефолты для санузлов
    if not normalized.get('bathrooms'):
        # Безопасное преобразование в числа
        try:
            rooms = int(normalized.get('rooms', 1)) if normalized.get('rooms') else 1
        except (ValueError, TypeError):
            rooms = 1

        try:
            total_area = float(normalized.get('total_area', 0)) if normalized.get('total_area') else 0
        except (ValueError, TypeError):
            total_area = 0

        if total_area > 120 or rooms >= 4:
            normalized['bathrooms'] = 2
        elif total_area > 80 or rooms >= 3:
            normalized['bathrooms'] = 1
        else:
            normalized['bathrooms'] = 1

    # 4. Дефолты для типа отделки
    if not normalized.get('repair_level'):
        # Безопасное преобразование в число
        try:
            price_per_sqm = float(normalized.get('price_per_sqm', 0)) if normalized.get('price_per_sqm') else 0
        except (ValueError, TypeError):
            price_per_sqm = 0

        # Премиум (> 300к/м²)
        if price_per_sqm > 300000:
            normalized['repair_level'] = 'премиум'
        # Улучшенная (200-300к)
        elif price_per_sqm > 200000:
            normalized['repair_level'] = 'улучшенная'
        # Стандартная
        else:
            normalized['repair_level'] = 'стандартная'

    # 5. Дефолты для типа окон
    if not normalized.get('window_type'):
        build_year = normalized.get('build_year')
        if build_year and build_year >= 2010:
            normalized['window_type'] = 'пластиковые'
        elif build_year and build_year < 1960:
            normalized['window_type'] = 'деревянные'
        else:
            normalized['window_type'] = 'пластиковые'

    # 6. Дефолт для количества лифтов
    if not normalized.get('elevator_count'):
        total_floors = normalized.get('total_floors', 0)
        if total_floors >= 16:
            normalized['elevator_count'] = 'два'
        elif total_floors >= 6:
            normalized['elevator_count'] = 'один'
        else:
            normalized['elevator_count'] = 'нет'

    # 7. Дефолт для статуса объекта
    if not normalized.get('object_status'):
        photo_type = normalized.get('photo_type', 'реальные')
        if 'стройка' in photo_type or 'рендер' in photo_type:
            normalized['object_status'] = 'строительство'
        else:
            normalized['object_status'] = 'готов'

    # 8. Дефолт для типа фото
    if not normalized.get('photo_type'):
        object_status = normalized.get('object_status', 'готов')
        if object_status in ['строительство', 'котлован', 'проект']:
            normalized['photo_type'] = 'только_рендеры'
        else:
            normalized['photo_type'] = 'реальные'

    return normalized


def validate_property_consistency(prop: TargetProperty) -> List[str]:
    """
    Проверка консистентности данных объекта

    Returns:
        Список предупреждений (warnings), пустой если все ОК
    """
    warnings = []

    # 1. Проверка площадей
    if prop.living_area and prop.total_area:
        living_percent = (prop.living_area / prop.total_area) * 100
        if living_percent < 40:
            warnings.append(
                f"Низкая доля жилой площади: {living_percent:.1f}% "
                f"({prop.living_area}м² из {prop.total_area}м²)"
            )
        elif living_percent > 95:
            warnings.append(
                f"Подозрительно высокая доля жилой площади: {living_percent:.1f}%"
            )

    # 2. Проверка этажности
    if prop.floor and prop.total_floors:
        if prop.floor > prop.total_floors:
            warnings.append(
                f"Этаж ({prop.floor}) больше общего количества ({prop.total_floors})"
            )

    # 3. Проверка цены
    if prop.price_per_sqm:
        if prop.price_per_sqm < 50000:
            warnings.append(f"Подозрительно низкая цена: {prop.price_per_sqm:,.0f} ₽/м²")
        elif prop.price_per_sqm > 1000000:
            warnings.append(f"Подозрительно высокая цена: {prop.price_per_sqm:,.0f} ₽/м²")

    # 4. Проверка высоты потолков
    if prop.ceiling_height:
        if prop.ceiling_height < 2.3:
            warnings.append(f"Низкие потолки: {prop.ceiling_height}м")
        elif prop.ceiling_height > 4.5:
            warnings.append(f"Подозрительно высокие потолки: {prop.ceiling_height}м")

    # 5. Проверка года постройки
    if prop.build_year:
        current_year = datetime.now().year
        if prop.build_year > current_year + 2:
            warnings.append(
                f"Год постройки в будущем: {prop.build_year} "
                f"(сейчас {current_year})"
            )
        elif prop.build_year < 1800:
            warnings.append(f"Слишком старый год постройки: {prop.build_year}")

    return warnings
