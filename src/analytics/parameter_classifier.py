"""
Классификация параметров на ФИКСИРОВАННЫЕ и ПЕРЕМЕННЫЕ
для правильного сравнительного анализа

ФИКСИРОВАННЫЕ параметры:
  - Используются для ФИЛЬТРАЦИИ аналогов (выбор однородной группы)
  - Коэффициенты за них НЕ применяются
  - Они уже учтены в ценах аналогов

ПЕРЕМЕННЫЕ параметры:
  - ОТЛИЧАЮТСЯ внутри группы аналогов
  - Коэффициенты применяются только за ОТЛИЧИЯ от медианы
  - Если целевой = медиане → коэффициент = 1.0 (нет изменения)
"""

from typing import Set, Dict, Any
from enum import Enum


class ParameterType(Enum):
    """Тип параметра"""
    FIXED = "fixed"  # Фиксированный (для фильтрации)
    VARIABLE = "variable"  # Переменный (для корректировок)


# ═══════════════════════════════════════════════════════════════════════════
# КАТЕГОРИЗАЦИЯ ПАРАМЕТРОВ
# ═══════════════════════════════════════════════════════════════════════════

FIXED_PARAMETERS = {
    # Локация (одинаковая для всех аналогов)
    'district_type',  # район
    'transport_accessibility',  # транспортная доступность

    # Тип дома (одинаковый для всех аналогов)
    'house_type',  # монолит/кирпич/панель

    # Инфраструктура комплекса (одинаковая для всех аналогов)
    'security_level',  # охрана
    'parking_type',  # тип парковки
    'sports_amenities',  # спортивная инфраструктура

    # Состояние дома (если фильтруем по возрасту)
    'house_condition',  # состояние
}

VARIABLE_PARAMETERS = {
    # КЛАСТЕР 1: ОТДЕЛКА (отличается между аналогами)
    'repair_level',  # черновая/стандарт/премиум/люкс

    # КЛАСТЕР 2: ХАРАКТЕРИСТИКИ КВАРТИРЫ (отличаются)
    'ceiling_height',  # высота потолков
    'bathrooms',  # количество ванных
    'window_type',  # тип окон
    'elevator_count',  # количество лифтов
    'living_area',  # жилая площадь (процент)
    'total_area',  # общая площадь

    # КЛАСТЕР 3: РАСПОЛОЖЕНИЕ В ДОМЕ (отличается)
    'floor',  # этаж
    # УДАЛЕНО: 'metro_distance_min' - сравнение в одной области

    # КЛАСТЕР 4: ИНДИВИДУАЛЬНЫЕ ПАРАМЕТРЫ
    # УДАЛЕНО: 'parking_spaces' - не имеет смысла без контекста

    # КЛАСТЕР 5: ВИД (отличается, максимум 5% влияния)
    'view_type',  # вид из окна
    # УДАЛЕНО: 'noise_level' - сравнение в одной области
    # УДАЛЕНО: 'crowded_level' - не учитывается

    # КЛАСТЕР 6: РИСКИ (отличаются)
    'photo_type',  # тип фото
    'object_status',  # статус объекта
    'build_year',  # год постройки (возраст дома)
}


def classify_parameter(param_name: str) -> ParameterType:
    """
    Классифицировать параметр

    Args:
        param_name: Название параметра

    Returns:
        Тип параметра (FIXED или VARIABLE)
    """
    if param_name in FIXED_PARAMETERS:
        return ParameterType.FIXED
    elif param_name in VARIABLE_PARAMETERS:
        return ParameterType.VARIABLE
    else:
        # По умолчанию считаем переменным
        return ParameterType.VARIABLE


def get_fixed_parameters() -> Set[str]:
    """Получить список фиксированных параметров"""
    return FIXED_PARAMETERS.copy()


def get_variable_parameters() -> Set[str]:
    """Получить список переменных параметров"""
    return VARIABLE_PARAMETERS.copy()


def should_apply_coefficient(param_name: str) -> bool:
    """
    Проверить, нужно ли применять коэффициент для данного параметра

    Args:
        param_name: Название параметра

    Returns:
        True если нужно применять коэффициент (переменный параметр)
        False если не нужно (фиксированный параметр)
    """
    return classify_parameter(param_name) == ParameterType.VARIABLE


def explain_parameter_classification() -> Dict[str, Any]:
    """
    Объяснить классификацию параметров (для документации)

    Returns:
        Словарь с объяснениями
    """
    return {
        'fixed': {
            'parameters': list(FIXED_PARAMETERS),
            'description': 'Используются для фильтрации аналогов. Коэффициенты НЕ применяются.',
            'examples': [
                'Если целевой объект в монолитном доме → выбираем только монолитные аналоги',
                'Если целевой объект с охраной → выбираем только аналоги с охраной',
                'Локация одинаковая для всех → не нужен коэффициент за локацию'
            ]
        },
        'variable': {
            'parameters': list(VARIABLE_PARAMETERS),
            'description': 'Отличаются между аналогами. Коэффициенты применяются только за ОТЛИЧИЯ от медианы.',
            'examples': [
                'Ремонт: если целевой = премиум, медиана = стандартная → применяем коэфф +50%',
                'Вид: если целевой = на воду, медиана = на улицу → применяем коэфф +5%',
                'Этаж: если целевой = средний, медиана = низкий → применяем коэфф +4%',
                'Если целевой = медиане → коэфф = 1.0 (без изменений)'
            ]
        }
    }


# ═══════════════════════════════════════════════════════════════════════════
# ГРУППИРОВКА ПАРАМЕТРОВ ДЛЯ УДОБСТВА
# ═══════════════════════════════════════════════════════════════════════════

PARAMETER_GROUPS = {
    'location': {
        'name': 'Локация и инфраструктура',
        'type': ParameterType.FIXED,
        'parameters': ['district_type', 'transport_accessibility']
    },
    'building': {
        'name': 'Характеристики дома',
        'type': ParameterType.FIXED,
        'parameters': ['house_type', 'house_condition']
    },
    'complex_amenities': {
        'name': 'Инфраструктура комплекса',
        'type': ParameterType.FIXED,
        'parameters': ['security_level', 'parking_type', 'sports_amenities']
    },
    'repair': {
        'name': 'Отделка',
        'type': ParameterType.VARIABLE,
        'parameters': ['repair_level']
    },
    'apartment_features': {
        'name': 'Характеристики квартиры',
        'type': ParameterType.VARIABLE,
        'parameters': ['ceiling_height', 'bathrooms', 'window_type', 'elevator_count',
                       'living_area', 'total_area']
    },
    'position': {
        'name': 'Расположение в доме',
        'type': ParameterType.VARIABLE,
        'parameters': ['floor']
    },
    'view': {
        'name': 'Вид из окна',
        'type': ParameterType.VARIABLE,
        'parameters': ['view_type']
    },
    'risks': {
        'name': 'Информация и риски',
        'type': ParameterType.VARIABLE,
        'parameters': ['photo_type', 'object_status', 'build_year']
    }
}


def get_parameter_group(param_name: str) -> str:
    """
    Получить группу параметра

    Args:
        param_name: Название параметра

    Returns:
        Название группы или 'other'
    """
    for group_name, group_info in PARAMETER_GROUPS.items():
        if param_name in group_info['parameters']:
            return group_name
    return 'other'
