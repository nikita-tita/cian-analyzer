"""
Pydantic модели для валидации данных
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator, HttpUrl
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


class ComparableProperty(PropertyBase):
    """Аналог для сравнения"""
    price_per_sqm: Optional[float] = None
    has_design: bool = False
    distance_km: Optional[float] = None  # Расстояние от целевого объекта
    similarity_score: Optional[float] = Field(None, ge=0, le=1)  # Оценка схожести
    excluded: bool = False  # Исключен из анализа

    @validator('price_per_sqm', always=True)
    def calculate_price_per_sqm(cls, v, values):
        if v is None and values.get('price') and values.get('total_area'):
            return values['price'] / values['total_area']
        return v

    class Config:
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

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
