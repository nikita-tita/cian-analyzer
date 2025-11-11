"""
Статистический анализ данных аналогов

Функции:
- IQR-фильтрация выбросов (Interquartile Range)
- Расчет коэффициента вариации (CV)
- Оценка качества данных
- Проверка нормальности распределения

Использование:
    from .statistical_analysis import detect_outliers_iqr, calculate_data_quality

    valid, outliers = detect_outliers_iqr(comparables)
    quality = calculate_data_quality(comparables)
"""

import statistics
import logging
from typing import List, Tuple, Dict, Any, Optional
from math import sqrt

from ..models.property import ComparableProperty

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# IQR-ФИЛЬТРАЦИЯ ВЫБРОСОВ
# ═══════════════════════════════════════════════════════════════════════════

def detect_outliers_iqr(
    comparables: List[ComparableProperty],
    field: str = 'price_per_sqm',
    multiplier: float = 1.5
) -> Tuple[List[ComparableProperty], List[Dict[str, Any]]]:
    """
    Фильтрация статистических выбросов методом IQR (Interquartile Range)

    IQR метод:
    - Q1 = 25-й перцентиль
    - Q3 = 75-й перцентиль
    - IQR = Q3 - Q1
    - Нижняя граница = Q1 - multiplier × IQR
    - Верхняя граница = Q3 + multiplier × IQR

    Стандартный multiplier = 1.5 (исключает ~0.7% выбросов при нормальном распределении)

    Args:
        comparables: Список аналогов для фильтрации
        field: Поле для анализа ('price_per_sqm', 'total_area', etc.)
        multiplier: Множитель IQR (обычно 1.5 или 3.0)

    Returns:
        Tuple[List, List]:
            - Список валидных аналогов (без выбросов)
            - Список отчетов по выбросам

    Example:
        >>> valid, outliers = detect_outliers_iqr(comparables)
        >>> logger.info(f"Отфильтровано {len(outliers)} выбросов")
    """
    if len(comparables) < 4:
        # IQR требует минимум 4 значения для квартилей
        logger.debug(f"Слишком мало данных для IQR ({len(comparables)} < 4) - пропускаем фильтрацию")
        return comparables, []

    # Извлекаем значения
    values = []
    value_map = {}  # Сопоставление значение -> аналог

    for comp in comparables:
        value = getattr(comp, field, None)
        if value is not None and value > 0:
            values.append(value)
            # Сохраняем для обратного поиска
            if value not in value_map:
                value_map[value] = []
            value_map[value].append(comp)

    if len(values) < 4:
        logger.debug(f"Недостаточно валидных значений {field} ({len(values)} < 4)")
        return comparables, []

    # Вычисляем квартили
    try:
        quartiles = statistics.quantiles(values, n=4)
        q1 = quartiles[0]  # 25-й перцентиль
        q3 = quartiles[2]  # 75-й перцентиль
        iqr = q3 - q1

        # Границы
        lower_bound = q1 - multiplier * iqr
        upper_bound = q3 + multiplier * iqr

        logger.info(f"IQR статистика для {field}:")
        logger.info(f"  Q1 (25%): {q1:,.0f}")
        logger.info(f"  Q3 (75%): {q3:,.0f}")
        logger.info(f"  IQR: {iqr:,.0f}")
        logger.info(f"  Границы: [{lower_bound:,.0f}, {upper_bound:,.0f}]")

    except statistics.StatisticsError as e:
        logger.warning(f"Не удалось рассчитать квартили: {e}")
        return comparables, []

    # Фильтруем выбросы
    valid = []
    outliers_reports = []

    for comp in comparables:
        value = getattr(comp, field, None)

        if value is None or value <= 0:
            # Нет значения - пропускаем (валидация должна была отфильтровать)
            valid.append(comp)
            continue

        if lower_bound <= value <= upper_bound:
            # В пределах нормы
            valid.append(comp)
        else:
            # Выброс
            outlier_type = 'верхний' if value > upper_bound else 'нижний'
            deviation = ((value - q3) / iqr) if value > upper_bound else ((q1 - value) / iqr)

            outliers_reports.append({
                'comparable': comp,
                'field': field,
                'value': value,
                'type': outlier_type,
                'deviation_iqr': abs(deviation),
                'bounds': (lower_bound, upper_bound),
                'url': getattr(comp, 'url', None)
            })

            logger.debug(
                f"✗ Выброс {outlier_type}: {value:,.0f} "
                f"(отклонение {abs(deviation):.1f} × IQR)"
            )

    logger.info(f"IQR фильтр: {len(comparables)} → {len(valid)} (исключено {len(outliers_reports)})")

    return valid, outliers_reports


# ═══════════════════════════════════════════════════════════════════════════
# ОЦЕНКА КАЧЕСТВА ДАННЫХ
# ═══════════════════════════════════════════════════════════════════════════

def calculate_data_quality(
    comparables: List[ComparableProperty],
    field: str = 'price_per_sqm'
) -> Dict[str, Any]:
    """
    Оценка качества данных по коэффициенту вариации (CV)

    CV = (стандартное отклонение / среднее) × 100%

    Классификация качества:
    - CV < 10%: отличное (очень низкий разброс)
    - CV < 20%: хорошее (низкий разброс)
    - CV < 30%: удовлетворительное (средний разброс)
    - CV >= 30%: плохое (высокий разброс)

    Args:
        comparables: Список аналогов
        field: Поле для анализа

    Returns:
        Dict с метриками качества:
            - cv: коэффициент вариации (0-1)
            - std_dev: стандартное отклонение
            - mean: среднее
            - median: медиана
            - count: количество значений
            - quality: уровень качества (excellent/good/fair/poor)
            - quality_score: оценка 0-100

    Example:
        >>> quality = calculate_data_quality(comparables)
        >>> if quality['quality'] == 'poor':
        >>>     logger.warning("Высокий разброс данных!")
    """
    values = [
        getattr(comp, field, None)
        for comp in comparables
        if getattr(comp, field, None) is not None and getattr(comp, field) > 0
    ]

    if len(values) < 2:
        return {
            'count': len(values),
            'quality': 'insufficient',
            'quality_score': 0,
            'cv': 1.0,
            'std_dev': 0,
            'mean': 0,
            'median': 0,
            'reason': 'Недостаточно данных для оценки (<2)'
        }

    # Статистики
    mean = statistics.mean(values)
    median = statistics.median(values)
    std_dev = statistics.stdev(values) if len(values) > 1 else 0

    # Коэффициент вариации
    cv = std_dev / mean if mean > 0 else 1.0

    # Классификация качества
    if cv < 0.10:
        quality = 'excellent'
        quality_score = 95
        description = 'Очень низкий разброс данных'
    elif cv < 0.20:
        quality = 'good'
        quality_score = 80
        description = 'Низкий разброс данных'
    elif cv < 0.30:
        quality = 'fair'
        quality_score = 60
        description = 'Средний разброс данных'
    else:
        quality = 'poor'
        quality_score = max(0, 40 - int((cv - 0.30) * 100))  # Снижается при увеличении CV
        description = 'Высокий разброс данных - результаты могут быть неточными'

    return {
        'count': len(values),
        'mean': mean,
        'median': median,
        'std_dev': std_dev,
        'cv': cv,
        'cv_percent': cv * 100,
        'quality': quality,
        'quality_score': quality_score,
        'description': description
    }


def calculate_distribution_stats(
    comparables: List[ComparableProperty],
    field: str = 'price_per_sqm'
) -> Dict[str, Any]:
    """
    Расширенная статистика распределения

    Включает:
    - Среднее, медиана, мода
    - Квартили (Q1, Q2, Q3)
    - Минимум, максимум, размах
    - Асимметрия (skewness)
    - Эксцесс (kurtosis)

    Args:
        comparables: Список аналогов
        field: Поле для анализа

    Returns:
        Dict с полной статистикой распределения
    """
    values = [
        getattr(comp, field, None)
        for comp in comparables
        if getattr(comp, field, None) is not None and getattr(comp, field) > 0
    ]

    if len(values) < 2:
        return {'error': 'Недостаточно данных', 'count': len(values)}

    # Базовые статистики
    mean = statistics.mean(values)
    median = statistics.median(values)

    try:
        mode = statistics.mode(values)
    except statistics.StatisticsError:
        mode = None  # Нет явной моды

    # Квантили
    if len(values) >= 4:
        quartiles = statistics.quantiles(values, n=4)
        q1, q2, q3 = quartiles[0], quartiles[1], quartiles[2]
    else:
        q1 = q2 = q3 = median

    # Разброс
    min_val = min(values)
    max_val = max(values)
    range_val = max_val - min_val

    # Стандартное отклонение
    std_dev = statistics.stdev(values) if len(values) > 1 else 0

    # Асимметрия (упрощенная формула)
    if std_dev > 0:
        skewness = sum((x - mean) ** 3 for x in values) / (len(values) * std_dev ** 3)
    else:
        skewness = 0

    # Эксцесс (упрощенная формула)
    if std_dev > 0:
        kurtosis = sum((x - mean) ** 4 for x in values) / (len(values) * std_dev ** 4) - 3
    else:
        kurtosis = 0

    return {
        'count': len(values),
        'mean': mean,
        'median': median,
        'mode': mode,
        'q1': q1,
        'q2': q2,
        'q3': q3,
        'min': min_val,
        'max': max_val,
        'range': range_val,
        'std_dev': std_dev,
        'variance': std_dev ** 2,
        'skewness': skewness,
        'kurtosis': kurtosis
    }


# ═══════════════════════════════════════════════════════════════════════════
# ПРОВЕРКА ДОСТАТОЧНОСТИ ДАННЫХ
# ═══════════════════════════════════════════════════════════════════════════

def check_data_sufficiency(
    comparables: List[ComparableProperty],
    minimum_count: int = 5,
    maximum_cv: float = 0.30
) -> Tuple[bool, str]:
    """
    Проверка достаточности данных для надежного расчета

    Проверяет:
    1. Количество аналогов >= minimum_count
    2. Коэффициент вариации <= maximum_cv
    3. Отсутствие критических выбросов

    Args:
        comparables: Список аналогов
        minimum_count: Минимальное требуемое количество
        maximum_cv: Максимально допустимый CV

    Returns:
        Tuple[bool, str]: (достаточно ли данных, причина если нет)

    Example:
        >>> is_sufficient, reason = check_data_sufficiency(comparables)
        >>> if not is_sufficient:
        >>>     logger.warning(f"Данных недостаточно: {reason}")
    """
    # Проверка 1: Количество
    if len(comparables) < minimum_count:
        return False, (
            f"Недостаточно аналогов: {len(comparables)} < {minimum_count}. "
            f"Рекомендуется собрать больше данных."
        )

    # Проверка 2: Качество (CV)
    quality = calculate_data_quality(comparables)

    if quality['quality'] == 'insufficient':
        return False, "Недостаточно валидных значений для оценки качества"

    if quality['cv'] > maximum_cv:
        return False, (
            f"Слишком высокий разброс данных: CV={quality['cv']:.1%} > {maximum_cv:.0%}. "
            f"Данные слишком разнородны для надежного расчета."
        )

    # Проверка 3: Выбросы (не должно быть > 20% выбросов)
    valid, outliers = detect_outliers_iqr(comparables)

    outliers_percent = len(outliers) / len(comparables) if len(comparables) > 0 else 0

    if outliers_percent > 0.20:
        return False, (
            f"Слишком много выбросов: {len(outliers)} из {len(comparables)} "
            f"({outliers_percent:.0%}). Данные нестабильны."
        )

    # Все проверки пройдены
    return True, "OK"


# ═══════════════════════════════════════════════════════════════════════════
# АНАЛИЗ ПО СЕГМЕНТАМ
# ═══════════════════════════════════════════════════════════════════════════

def analyze_by_segments(
    comparables: List[ComparableProperty],
    segment_field: str,
    value_field: str = 'price_per_sqm'
) -> Dict[Any, Dict[str, Any]]:
    """
    Анализ данных по сегментам (группировка)

    Например:
    - По количеству комнат
    - По этажам (низкие/средние/высокие)
    - По годам постройки

    Args:
        comparables: Список аналогов
        segment_field: Поле для группировки ('rooms', 'floor', etc.)
        value_field: Поле для анализа значений

    Returns:
        Dict[сегмент, статистика] - статистика по каждому сегменту

    Example:
        >>> segments = analyze_by_segments(comparables, 'rooms')
        >>> for rooms, stats in segments.items():
        >>>     print(f"{rooms}-комн: {stats['median']:,.0f} ₽/м²")
    """
    # Группируем по сегментам
    segments = {}

    for comp in comparables:
        segment = getattr(comp, segment_field, None)

        if segment is None:
            continue

        if segment not in segments:
            segments[segment] = []

        segments[segment].append(comp)

    # Считаем статистику по каждому сегменту
    results = {}

    for segment, segment_comps in segments.items():
        quality = calculate_data_quality(segment_comps, field=value_field)
        results[segment] = {
            'count': len(segment_comps),
            'median': quality.get('median', 0),
            'mean': quality.get('mean', 0),
            'std_dev': quality.get('std_dev', 0),
            'cv': quality.get('cv', 0),
            'quality': quality.get('quality', 'unknown')
        }

    return results
