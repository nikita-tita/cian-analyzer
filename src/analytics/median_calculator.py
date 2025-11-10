"""
Расчет медиан по переменным параметрам аналогов

Медиана представляет "СРЕДНИЙ" аналог в группе.
Коэффициенты применяются только за отличия целевого от медианы.
"""

import statistics
from collections import Counter
from typing import List, Dict, Any
from ..models.property import ComparableProperty, TargetProperty
from .parameter_classifier import get_variable_parameters


def calculate_medians_from_comparables(
    comparables: List[ComparableProperty]
) -> Dict[str, Any]:
    """
    Рассчитать медианы по всем переменным параметрам аналогов

    Args:
        comparables: Список аналогов

    Returns:
        Словарь с медианами: {parameter_name: median_value}
    """
    if not comparables:
        return {}

    medians = {}
    get_variable_parameters()

    # Числовые параметры
    numeric_params = {
        'total_area': [],
        'living_area': [],
        'ceiling_height': [],
        'bathrooms': [],
        'floor': [],
        'metro_distance_min': [],
        'parking_spaces': [],
    }

    # Категориальные параметры (будем искать моду)
    categorical_params = {
        'repair_level': [],
        'window_type': [],
        'elevator_count': [],
        'view_type': [],
        'noise_level': [],
        'crowded_level': [],
        'photo_type': [],
        'object_status': [],
    }

    # Специальные параметры
    build_years = []
    living_area_percents = []

    # Собираем данные из аналогов
    for comp in comparables:
        # Числовые параметры
        if comp.total_area:
            numeric_params['total_area'].append(comp.total_area)

        if hasattr(comp, 'living_area') and comp.living_area:
            numeric_params['living_area'].append(comp.living_area)

        if hasattr(comp, 'ceiling_height') and comp.ceiling_height:
            numeric_params['ceiling_height'].append(comp.ceiling_height)

        if hasattr(comp, 'bathrooms') and comp.bathrooms is not None:
            numeric_params['bathrooms'].append(comp.bathrooms)

        if comp.floor:
            numeric_params['floor'].append(comp.floor)

        if hasattr(comp, 'metro_distance_min') and comp.metro_distance_min:
            numeric_params['metro_distance_min'].append(comp.metro_distance_min)

        if hasattr(comp, 'parking_spaces') and comp.parking_spaces:
            numeric_params['parking_spaces'].append(comp.parking_spaces)

        # Категориальные параметры
        if hasattr(comp, 'repair_level') and comp.repair_level:
            categorical_params['repair_level'].append(comp.repair_level)

        if hasattr(comp, 'window_type') and comp.window_type:
            categorical_params['window_type'].append(comp.window_type)

        if hasattr(comp, 'elevator_count') and comp.elevator_count:
            categorical_params['elevator_count'].append(comp.elevator_count)

        if hasattr(comp, 'view_type') and comp.view_type:
            categorical_params['view_type'].append(comp.view_type)

        if hasattr(comp, 'noise_level') and comp.noise_level:
            categorical_params['noise_level'].append(comp.noise_level)

        if hasattr(comp, 'crowded_level') and comp.crowded_level:
            categorical_params['crowded_level'].append(comp.crowded_level)

        if hasattr(comp, 'photo_type') and comp.photo_type:
            categorical_params['photo_type'].append(comp.photo_type)

        if hasattr(comp, 'object_status') and comp.object_status:
            categorical_params['object_status'].append(comp.object_status)

        # Специальные расчеты
        if hasattr(comp, 'build_year') and comp.build_year:
            build_years.append(comp.build_year)

        if hasattr(comp, 'living_area') and comp.living_area and comp.total_area:
            living_percent = (comp.living_area / comp.total_area) * 100
            living_area_percents.append(living_percent)

    # Рассчитываем медианы для числовых параметров
    for param_name, values in numeric_params.items():
        if values and len(values) >= 2:
            medians[param_name] = statistics.median(values)
        elif values:
            medians[param_name] = values[0]

    # Рассчитываем моду (наиболее частое значение) для категориальных
    for param_name, values in categorical_params.items():
        if not values:
            continue

        try:
            medians[param_name] = statistics.mode(values)
        except statistics.StatisticsError:
            # Несколько значений с одинаковой частотой — выбираем первое встреченное
            counter = Counter(values)
            max_count = max(counter.values())
            top_candidates = {value for value, count in counter.items() if count == max_count}

            for value in values:
                if value in top_candidates:
                    medians[param_name] = value
                    break
            else:
                # Fallback на первое значение, если список неожиданно пуст
                medians[param_name] = values[0]

    # Специальные медианы
    if build_years and len(build_years) >= 2:
        medians['build_year'] = statistics.median(build_years)
    elif build_years:
        medians['build_year'] = build_years[0]

    if living_area_percents and len(living_area_percents) >= 2:
        medians['living_area_percent'] = statistics.median(living_area_percents)
    elif living_area_percents:
        medians['living_area_percent'] = living_area_percents[0]

    # Добавляем медиану цены за м²
    prices_per_sqm = [c.price_per_sqm for c in comparables if c.price_per_sqm]
    if prices_per_sqm and len(prices_per_sqm) >= 2:
        medians['price_per_sqm'] = statistics.median(prices_per_sqm)
    elif prices_per_sqm:
        medians['price_per_sqm'] = prices_per_sqm[0]

    return medians


def compare_target_with_medians(
    target: TargetProperty,
    medians: Dict[str, Any]
) -> Dict[str, Dict[str, Any]]:
    """
    Сравнить целевой объект с медианами

    Args:
        target: Целевой объект
        medians: Медианы по аналогам

    Returns:
        Словарь с результатами сравнения:
        {
            parameter_name: {
                'target_value': ...,
                'median_value': ...,
                'difference': ...,  # для числовых
                'equals_median': bool,
                'direction': 'above' | 'below' | 'equals'  # для числовых
            }
        }
    """
    comparison = {}

    # Числовые параметры
    numeric_params = [
        'total_area', 'living_area', 'ceiling_height', 'bathrooms',
        'floor', 'metro_distance_min', 'parking_spaces', 'build_year'
    ]

    for param_name in numeric_params:
        if param_name not in medians:
            continue

        target_value = getattr(target, param_name, None)
        if target_value is None:
            continue

        median_value = medians[param_name]

        comparison[param_name] = {
            'target_value': target_value,
            'median_value': median_value,
            'difference': target_value - median_value,
            'equals_median': abs(target_value - median_value) < 0.01,
            'direction': 'equals' if abs(target_value - median_value) < 0.01 else (
                'above' if target_value > median_value else 'below'
            )
        }

    # Категориальные параметры
    categorical_params = [
        'repair_level', 'window_type', 'elevator_count', 'view_type',
        'noise_level', 'crowded_level', 'photo_type', 'object_status'
    ]

    for param_name in categorical_params:
        if param_name not in medians:
            continue

        target_value = getattr(target, param_name, None)
        if target_value is None:
            continue

        median_value = medians[param_name]

        comparison[param_name] = {
            'target_value': target_value,
            'median_value': median_value,
            'equals_median': target_value == median_value,
            'direction': 'equals' if target_value == median_value else 'different'
        }

    # Специальный параметр: процент жилой площади
    if 'living_area_percent' in medians and target.living_area and target.total_area:
        target_living_percent = (target.living_area / target.total_area) * 100
        median_living_percent = medians['living_area_percent']

        comparison['living_area_percent'] = {
            'target_value': target_living_percent,
            'median_value': median_living_percent,
            'difference': target_living_percent - median_living_percent,
            'equals_median': abs(target_living_percent - median_living_percent) < 1.0,
            'direction': 'equals' if abs(target_living_percent - median_living_percent) < 1.0 else (
                'above' if target_living_percent > median_living_percent else 'below'
            )
        }

    return comparison


def get_readable_comparison_summary(comparison: Dict[str, Dict[str, Any]]) -> str:
    """
    Получить читаемое описание сравнения

    Args:
        comparison: Результат сравнения из compare_target_with_medians

    Returns:
        Строка с описанием
    """
    lines = ["Сравнение целевого объекта с медианой аналогов:", ""]

    equals_count = 0
    differs_count = 0

    for param_name, data in comparison.items():
        equals = data['equals_median']

        if equals:
            equals_count += 1
            status = "= МЕДИАНА"
        else:
            differs_count += 1
            if 'direction' in data and data['direction'] in ['above', 'below']:
                direction = "выше" if data['direction'] == 'above' else "ниже"
                status = f"{direction} медианы"
            else:
                status = "отличается"

        target_val = data['target_value']
        median_val = data['median_value']

        lines.append(f"  {param_name}: {target_val} (медиана: {median_val}) → {status}")

    lines.append("")
    lines.append(f"Итого: {equals_count} параметров = медиане, {differs_count} отличаются")
    lines.append("Коэффициенты применяются только для отличающихся параметров!")

    return "\n".join(lines)
