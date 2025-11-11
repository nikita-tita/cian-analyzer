"""
Валидатор данных для аналогов недвижимости

Проверяет качество данных перед расчетом справедливой цены:
- Наличие обязательных полей
- Разумность значений (цена, площадь)
- Статус объекта (исключаем проекты, котлованы)
- Полнота информации

Использование:
    from .data_validator import validate_comparable, filter_valid_comparables

    valid_comps = filter_valid_comparables(comparables)
"""

import logging
from typing import List, Tuple, Dict, Any
from datetime import datetime

from ..models.property import ComparableProperty

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# КОНСТАНТЫ ДЛЯ ВАЛИДАЦИИ
# ═══════════════════════════════════════════════════════════════════════════

# Разумные границы для цены за м² (руб/м²)
MIN_PRICE_PER_SQM = 30_000      # Минимум (эконом-класс в удаленных районах)
MAX_PRICE_PER_SQM = 2_000_000   # Максимум (элитная недвижимость)

# Разумные границы для площади (м²)
MIN_TOTAL_AREA = 15     # Минимум (студия малая)
MAX_TOTAL_AREA = 1000   # Максимум (пентхаусы, особняки)

# Минимальная цена объекта (руб)
MIN_TOTAL_PRICE = 1_000_000     # 1 млн руб

# Статусы объектов, которые НЕЛЬЗЯ использовать как аналоги
EXCLUDED_STATUSES = {
    'проект',           # Еще в проекте
    'котлован',         # Только начало стройки
    'снесен',           # Уже не существует
    'заморожен',        # Стройка заморожена
}

# Статусы, которые МОЖНО использовать
ALLOWED_STATUSES = {
    'готов',            # Дом сдан
    'отделка',          # Завершается отделка
    'строительство',    # Активная стройка (приемлемо для новостроек)
}


# ═══════════════════════════════════════════════════════════════════════════
# ОСНОВНЫЕ ФУНКЦИИ ВАЛИДАЦИИ
# ═══════════════════════════════════════════════════════════════════════════

def validate_comparable(comparable: ComparableProperty) -> Tuple[bool, Dict[str, Any]]:
    """
    Валидация одного аналога

    Проверяет:
    1. Наличие обязательных полей (цена, площадь)
    2. Разумность значений
    3. Статус объекта
    4. Полноту данных

    Args:
        comparable: Объект аналога для проверки

    Returns:
        Tuple[bool, dict]:
            - bool: True если аналог валиден
            - dict: Детали проверки с причинами исключения

    Example:
        >>> is_valid, details = validate_comparable(comp)
        >>> if not is_valid:
        >>>     logger.warning(f"Исключен: {details['failures']}")
    """
    checks = {}
    failures = []

    # ===== ПРОВЕРКА 1: НАЛИЧИЕ ОБЯЗАТЕЛЬНЫХ ПОЛЕЙ =====

    # Цена
    has_price = comparable.price is not None and comparable.price > 0
    checks['has_price'] = has_price
    if not has_price:
        failures.append('Отсутствует цена')

    # Площадь
    has_area = comparable.total_area is not None and comparable.total_area > 0
    checks['has_area'] = has_area
    if not has_area:
        failures.append('Отсутствует площадь')

    # Цена за м² (вычисляемое поле)
    has_price_per_sqm = comparable.price_per_sqm is not None and comparable.price_per_sqm > 0
    checks['has_price_per_sqm'] = has_price_per_sqm
    if not has_price_per_sqm and has_price and has_area:
        failures.append('Отсутствует цена/м² (некорректный расчет)')

    # ===== ПРОВЕРКА 2: РАЗУМНОСТЬ ЗНАЧЕНИЙ =====

    # Цена за м² в разумных пределах
    if has_price_per_sqm:
        price_reasonable = MIN_PRICE_PER_SQM <= comparable.price_per_sqm <= MAX_PRICE_PER_SQM
        checks['price_per_sqm_reasonable'] = price_reasonable
        if not price_reasonable:
            failures.append(
                f'Цена/м² вне пределов: {comparable.price_per_sqm:,.0f} ₽ '
                f'(допустимо {MIN_PRICE_PER_SQM:,}-{MAX_PRICE_PER_SQM:,})'
            )
    else:
        checks['price_per_sqm_reasonable'] = False

    # Площадь в разумных пределах
    if has_area:
        area_reasonable = MIN_TOTAL_AREA <= comparable.total_area <= MAX_TOTAL_AREA
        checks['area_reasonable'] = area_reasonable
        if not area_reasonable:
            failures.append(
                f'Площадь вне пределов: {comparable.total_area:.1f} м² '
                f'(допустимо {MIN_TOTAL_AREA}-{MAX_TOTAL_AREA})'
            )
    else:
        checks['area_reasonable'] = False

    # Общая цена в разумных пределах
    if has_price:
        total_price_reasonable = comparable.price >= MIN_TOTAL_PRICE
        checks['total_price_reasonable'] = total_price_reasonable
        if not total_price_reasonable:
            failures.append(
                f'Цена слишком низкая: {comparable.price:,.0f} ₽ '
                f'(минимум {MIN_TOTAL_PRICE:,})'
            )
    else:
        checks['total_price_reasonable'] = False

    # ===== ПРОВЕРКА 3: СТАТУС ОБЪЕКТА =====

    # Проверяем, что статус известен
    object_status = getattr(comparable, 'object_status', None)

    if object_status:
        status_lower = object_status.lower()

        # Не должен быть в списке исключенных
        not_excluded_status = status_lower not in EXCLUDED_STATUSES
        checks['not_excluded_status'] = not_excluded_status
        if not not_excluded_status:
            failures.append(f'Недопустимый статус: {object_status}')

        # Должен быть в списке разрешенных (или неизвестен)
        is_allowed_status = status_lower in ALLOWED_STATUSES
        checks['is_allowed_status'] = is_allowed_status
        if not is_allowed_status and not_excluded_status:
            # Неизвестный статус - выдаем предупреждение, но не исключаем
            logger.debug(f'Неизвестный статус объекта: {object_status}')
    else:
        # Статус не указан - допускаем (может быть вторичка)
        checks['not_excluded_status'] = True
        checks['is_allowed_status'] = True

    # ===== ПРОВЕРКА 4: ПОЛНОТА ДАННЫХ (ОПЦИОНАЛЬНО) =====

    # Этаж (желательно, но не критично)
    has_floor = comparable.floor is not None and comparable.floor > 0
    checks['has_floor'] = has_floor

    # Общее количество этажей
    has_total_floors = (
        hasattr(comparable, 'total_floors') and
        comparable.total_floors is not None and
        comparable.total_floors > 0
    )
    checks['has_total_floors'] = has_total_floors

    # Год постройки
    has_build_year = (
        hasattr(comparable, 'build_year') and
        comparable.build_year is not None and
        1800 <= comparable.build_year <= datetime.now().year + 5
    )
    checks['has_build_year'] = has_build_year

    # ===== ИТОГОВАЯ ОЦЕНКА =====

    # Обязательные проверки
    critical_checks = [
        'has_price',
        'has_area',
        'has_price_per_sqm',
        'price_per_sqm_reasonable',
        'area_reasonable',
        'total_price_reasonable',
        'not_excluded_status',
    ]

    is_valid = all(checks.get(check, False) for check in critical_checks)

    # Подсчет полноты данных (0-100%)
    optional_checks = ['has_floor', 'has_total_floors', 'has_build_year']
    completeness = sum(checks.get(check, False) for check in optional_checks) / len(optional_checks) * 100

    return is_valid, {
        'is_valid': is_valid,
        'checks': checks,
        'failures': failures,
        'completeness': round(completeness, 1),
        'url': getattr(comparable, 'url', None),
        'price': comparable.price if has_price else None,
        'total_area': comparable.total_area if has_area else None,
    }


def filter_valid_comparables(
    comparables: List[ComparableProperty],
    verbose: bool = True
) -> Tuple[List[ComparableProperty], List[Dict[str, Any]]]:
    """
    Фильтрация списка аналогов - оставляем только валидные

    Args:
        comparables: Список аналогов для фильтрации
        verbose: Логировать ли детали фильтрации

    Returns:
        Tuple[List, List]:
            - Список валидных аналогов
            - Список отчетов по исключенным (для аналитики)

    Example:
        >>> valid, excluded = filter_valid_comparables(comparables)
        >>> logger.info(f"Валидных: {len(valid)}, исключено: {len(excluded)}")
    """
    valid = []
    excluded_reports = []

    for i, comp in enumerate(comparables):
        is_valid, details = validate_comparable(comp)

        if is_valid:
            valid.append(comp)
            if verbose:
                logger.debug(
                    f"✓ Аналог {i+1}: валиден "
                    f"(полнота данных: {details['completeness']:.0f}%)"
                )
        else:
            excluded_reports.append(details)
            if verbose:
                failures_str = '; '.join(details['failures'])
                logger.info(
                    f"✗ Аналог {i+1}: ИСКЛЮЧЕН - {failures_str}"
                )

    # Итоговая статистика
    total = len(comparables)
    valid_count = len(valid)
    excluded_count = len(excluded_reports)

    if verbose:
        logger.info("")
        logger.info("=" * 60)
        logger.info("ИТОГИ ВАЛИДАЦИИ")
        logger.info("=" * 60)
        logger.info(f"Всего аналогов: {total}")
        logger.info(f"Валидных: {valid_count} ({valid_count/total*100:.1f}%)")
        logger.info(f"Исключено: {excluded_count} ({excluded_count/total*100:.1f}%)")

        if excluded_count > 0:
            logger.info("")
            logger.info("Причины исключения:")

            # Агрегируем причины
            reasons_count = {}
            for report in excluded_reports:
                for failure in report['failures']:
                    reasons_count[failure] = reasons_count.get(failure, 0) + 1

            for reason, count in sorted(reasons_count.items(), key=lambda x: x[1], reverse=True):
                logger.info(f"  • {reason}: {count}")

        logger.info("=" * 60)
        logger.info("")

    return valid, excluded_reports


def get_validation_summary(comparables: List[ComparableProperty]) -> Dict[str, Any]:
    """
    Получить сводку по валидации без фильтрации

    Полезно для аналитики - понять качество данных

    Args:
        comparables: Список аналогов

    Returns:
        Dict с метриками качества данных

    Example:
        >>> summary = get_validation_summary(comparables)
        >>> print(f"Валидность: {summary['valid_percentage']:.1f}%")
    """
    total = len(comparables)

    if total == 0:
        return {
            'total': 0,
            'valid': 0,
            'invalid': 0,
            'valid_percentage': 0.0,
            'avg_completeness': 0.0,
            'issues': {}
        }

    valid_count = 0
    invalid_count = 0
    completeness_scores = []
    all_issues = []

    for comp in comparables:
        is_valid, details = validate_comparable(comp)

        if is_valid:
            valid_count += 1
        else:
            invalid_count += 1
            all_issues.extend(details['failures'])

        completeness_scores.append(details['completeness'])

    # Агрегируем проблемы
    issues_count = {}
    for issue in all_issues:
        issues_count[issue] = issues_count.get(issue, 0) + 1

    return {
        'total': total,
        'valid': valid_count,
        'invalid': invalid_count,
        'valid_percentage': valid_count / total * 100,
        'avg_completeness': sum(completeness_scores) / len(completeness_scores),
        'issues': issues_count
    }


# ═══════════════════════════════════════════════════════════════════════════
# ДОПОЛНИТЕЛЬНЫЕ УТИЛИТЫ
# ═══════════════════════════════════════════════════════════════════════════

def check_minimum_comparables(
    comparables: List[ComparableProperty],
    minimum: int = 5,
    raise_error: bool = True
) -> bool:
    """
    Проверка минимального количества аналогов

    Args:
        comparables: Список аналогов
        minimum: Минимальное требуемое количество
        raise_error: Выбросить ValueError если недостаточно

    Returns:
        True если достаточно аналогов

    Raises:
        ValueError: Если недостаточно и raise_error=True
    """
    count = len(comparables)

    if count < minimum:
        msg = (
            f"Недостаточно аналогов для надежного расчета: {count} < {minimum}. "
            f"Рекомендуется расширить критерии поиска."
        )

        if raise_error:
            raise ValueError(msg)
        else:
            logger.warning(msg)
            return False

    return True


def validate_target_property(target) -> Tuple[bool, List[str]]:
    """
    Валидация целевого объекта (того, для которого считаем цену)

    Args:
        target: TargetProperty объект

    Returns:
        Tuple[bool, List[str]]: (is_valid, list_of_issues)
    """
    issues = []

    # Обязательные поля для расчета
    if not target.total_area or target.total_area <= 0:
        issues.append("Отсутствует площадь целевого объекта")

    # Желательные поля
    if not hasattr(target, 'floor') or not target.floor:
        issues.append("Отсутствует этаж (расчет будет менее точным)")

    if not hasattr(target, 'total_floors') or not target.total_floors:
        issues.append("Отсутствует количество этажей в доме")

    # Критические проблемы
    critical_issues = [iss for iss in issues if "Отсутствует площадь" in iss]

    is_valid = len(critical_issues) == 0

    return is_valid, issues
