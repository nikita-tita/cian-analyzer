"""
Правильный расчет справедливой цены с учетом медиан

КЛЮЧЕВАЯ ЛОГИКА:
1. Находим медианы по ПЕРЕМЕННЫМ параметрам
2. Применяем коэффициенты ТОЛЬКО за ОТЛИЧИЯ от медианы
3. Если целевой = медиане → коэфф = 1.0 (БЕЗ изменений)
4. Фиксированные параметры НЕ учитываются (уже в ценах аналогов)
"""

import logging
from typing import Dict, List
from datetime import datetime

from ..models.property import TargetProperty, ComparableProperty
from .median_calculator import (
    calculate_medians_from_comparables,
    compare_target_with_medians
)
from .confidence_calculator import (
    calculate_confidence,
    generate_detailed_report,
    generate_summary_report
)
from .coefficients import (
    REPAIR_LEVEL_COEFFICIENTS,
    VIEW_TYPE_COEFFICIENTS,
    WINDOW_TYPE_COEFFICIENTS,
    ELEVATOR_COUNT_COEFFICIENTS,
    PHOTO_TYPE_COEFFICIENTS,
    OBJECT_STATUS_COEFFICIENTS,
    get_ceiling_height_coefficient,
    get_area_coefficient,
    get_living_area_coefficient,
    get_floor_coefficient,
    get_building_age_coefficient,
    get_price_liquidity_coefficient,
    # Адаптивные коэффициенты (Фаза 3)
    calculate_floor_coefficient_adaptive,
    calculate_area_coefficient_adaptive
)

logger = logging.getLogger(__name__)


def calculate_fair_price_with_medians(
    target: TargetProperty,
    comparables: List[ComparableProperty],
    base_price_per_sqm: float,
    method: str = 'median'
) -> Dict:
    """
    Правильный расчет справедливой цены

    Args:
        target: Целевой объект
        comparables: Список аналогов
        base_price_per_sqm: Базовая цена за м² (медиана из аналогов)
        method: Метод расчета ('median' или 'mean')

    Returns:
        Результат с полным расчетом
    """
    # ШАГ 1: Рассчитываем медианы по переменным параметрам
    medians = calculate_medians_from_comparables(comparables)

    if not medians:
        logger.warning("Не удалось рассчитать медианы - используем упрощенную схему")
        # Fallback на старую логику
        return _fallback_calculation(target, base_price_per_sqm, method)

    # ШАГ 2: Сравниваем целевой с медианами
    comparison = compare_target_with_medians(target, medians)

    # ШАГ 3: Применяем коэффициенты ТОЛЬКО за отличия
    adjustments = {}
    multiplier = 1.0

    # === КЛАСТЕР 1: ОТДЕЛКА ===
    multiplier, adjustments = _apply_repair_adjustment(
        target, medians, comparison, multiplier, adjustments
    )

    # === КЛАСТЕР 2: ХАРАКТЕРИСТИКИ КВАРТИРЫ ===
    multiplier, adjustments = _apply_apartment_features_adjustments(
        target, medians, comparison, multiplier, adjustments, comparables
    )

    # === КЛАСТЕР 3: РАСПОЛОЖЕНИЕ В ДОМЕ ===
    multiplier, adjustments = _apply_position_adjustments(
        target, medians, comparison, multiplier, adjustments, comparables
    )

    # === КЛАСТЕР 4: ИНДИВИДУАЛЬНЫЕ ПАРАМЕТРЫ ===
    multiplier, adjustments = _apply_individual_adjustments(
        target, medians, comparison, multiplier, adjustments
    )

    # === КЛАСТЕР 5: ВИД И ЭСТЕТИКА ===
    multiplier, adjustments = _apply_view_adjustments(
        target, medians, comparison, multiplier, adjustments
    )

    # === КЛАСТЕР 6: РИСКИ ===
    multiplier, adjustments = _apply_risk_adjustments(
        target, medians, comparison, multiplier, adjustments
    )

    # ШАГ 4: Ограничение multiplier (от 0.7 до 1.4)
    if multiplier < 0.7:
        logger.warning(f"Multiplier слишком низкий: {multiplier:.3f}, ограничен до 0.7")
        adjustments['multiplier_limit'] = {
            'value': 0.7 / multiplier,
            'description': f'Ограничение слишком низкого multiplier ({multiplier:.3f} → 0.7)',
            'reason': 'Защита от чрезмерного штрафа'
        }
        multiplier = 0.7
    elif multiplier > 1.4:
        logger.warning(f"Multiplier слишком высокий: {multiplier:.3f}, ограничен до 1.4")
        adjustments['multiplier_limit'] = {
            'value': 1.4 / multiplier,
            'description': f'Ограничение слишком высокого multiplier ({multiplier:.3f} → 1.4)',
            'reason': 'Защита от чрезмерной премии'
        }
        multiplier = 1.4

    # ШАГ 5: Финальный расчет
    fair_price_per_sqm = base_price_per_sqm * multiplier
    fair_price_total = fair_price_per_sqm * (target.total_area or 0)

    current_price = target.price or 0
    price_diff_amount = current_price - fair_price_total
    price_diff_percent = (price_diff_amount / fair_price_total * 100) if fair_price_total > 0 else 0

    # Статусы оценки
    is_overpriced = price_diff_percent > 5
    is_underpriced = price_diff_percent < -5
    is_fair = -5 <= price_diff_percent <= 5

    # === РАСЧЕТ УВЕРЕННОСТИ И ГЕНЕРАЦИЯ ОТЧЕТА (ФАЗА 4) ===
    # Для расчета уверенности нужна информация о качестве данных
    # Используем упрощенный расчет если data_quality недоступен
    try:
        from .statistical_analysis import calculate_data_quality
        data_quality = calculate_data_quality(comparables)
    except (ImportError, Exception) as e:
        logger.warning(f"Не удалось рассчитать качество данных: {e}")
        data_quality = {'quality': 'unknown', 'cv': 0.15, 'quality_score': 70}

    # Рассчитываем уверенность
    confidence = calculate_confidence(
        comparables=comparables,
        data_quality=data_quality,
        adjustments=adjustments,
        final_multiplier=multiplier
    )

    # Генерируем отчеты
    detailed_report = generate_detailed_report(
        target=target,
        comparables=comparables,
        fair_price_result={
            'base_price_per_sqm': base_price_per_sqm,
            'final_multiplier': multiplier,
            'fair_price_per_sqm': fair_price_per_sqm,
            'fair_price_total': fair_price_total,
            'current_price': current_price,
            'adjustments': adjustments,
            'data_quality': data_quality
        },
        confidence=confidence
    )

    summary_report = generate_summary_report(
        fair_price_result={
            'fair_price_total': fair_price_total,
            'current_price': current_price
        },
        confidence=confidence
    )

    # Логируем краткий отчет
    logger.info("")
    logger.info("=" * 70)
    logger.info(summary_report)
    logger.info("=" * 70)
    logger.info("")

    return {
        'base_price_per_sqm': base_price_per_sqm,
        'medians': medians,
        'comparison': comparison,
        'adjustments': adjustments,
        'final_multiplier': multiplier,
        'fair_price_per_sqm': fair_price_per_sqm,
        'fair_price_total': fair_price_total,
        'current_price': current_price,
        'price_diff_amount': price_diff_amount,
        'price_diff_percent': price_diff_percent,
        'is_overpriced': is_overpriced,
        'is_underpriced': is_underpriced,
        'is_fair': is_fair,
        'overpricing_amount': price_diff_amount,
        'overpricing_percent': price_diff_percent,
        'method': method,
        # НОВЫЕ ПОЛЯ (Фаза 4)
        'confidence': confidence,
        'data_quality': data_quality,
        'detailed_report': detailed_report,
        'summary_report': summary_report
    }


# ═══════════════════════════════════════════════════════════════════════════
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ ПРИМЕНЕНИЯ КОРРЕКТИРОВОК
# ═══════════════════════════════════════════════════════════════════════════

def _apply_repair_adjustment(target, medians, comparison, multiplier, adjustments):
    """Применить корректировку за отделку"""
    if 'repair_level' in comparison and not comparison['repair_level']['equals_median']:
        target_repair = target.repair_level
        median_repair = medians['repair_level']

        if target_repair in REPAIR_LEVEL_COEFFICIENTS:
            target_coef = REPAIR_LEVEL_COEFFICIENTS[target_repair]
            median_coef = REPAIR_LEVEL_COEFFICIENTS.get(median_repair, 1.0)

            # Коэффициент = отношение целевого к медиане
            coef = target_coef / median_coef

            adjustments['repair_level'] = {
                'value': coef,
                'description': f'Отделка: {target_repair} vs {median_repair} (медиана)',
                'target_value': target_repair,
                'median_value': median_repair,
                'type': 'variable'
            }
            multiplier *= coef

    return multiplier, adjustments


def _apply_apartment_features_adjustments(target, medians, comparison, multiplier, adjustments, comparables):
    """Применить корректировки за характеристики квартиры"""

    # Высота потолков
    if 'ceiling_height' in comparison and not comparison['ceiling_height']['equals_median']:
        target_height = target.ceiling_height
        median_height = medians['ceiling_height']

        target_coef = get_ceiling_height_coefficient(target_height)
        median_coef = get_ceiling_height_coefficient(median_height)

        coef = target_coef / median_coef

        adjustments['ceiling_height'] = {
            'value': coef,
            'description': f'Высота потолков: {target_height}м vs {median_height:.1f}м (медиана)',
            'target_value': target_height,
            'median_value': median_height,
            'type': 'variable'
        }
        multiplier *= coef

    # Ванные комнаты
    if 'bathrooms' in comparison and not comparison['bathrooms']['equals_median']:
        target_bathrooms = target.bathrooms
        median_bathrooms = int(medians['bathrooms'])

        # Упрощенная логика: +5% за каждую дополнительную ванную
        diff = target_bathrooms - median_bathrooms
        coef = 1 + (diff * 0.05)
        coef = max(0.90, min(coef, 1.15))  # Ограничение от -10% до +15%

        adjustments['bathrooms'] = {
            'value': coef,
            'description': f'Ванные комнаты: {target_bathrooms} vs {median_bathrooms} (медиана)',
            'target_value': target_bathrooms,
            'median_value': median_bathrooms,
            'type': 'variable'
        }
        multiplier *= coef

    # Тип окон
    if 'window_type' in comparison and not comparison['window_type']['equals_median']:
        target_windows = target.window_type
        median_windows = medians['window_type']

        if target_windows in WINDOW_TYPE_COEFFICIENTS:
            target_coef = WINDOW_TYPE_COEFFICIENTS[target_windows]
            median_coef = WINDOW_TYPE_COEFFICIENTS.get(median_windows, 1.0)

            coef = target_coef / median_coef

            adjustments['window_type'] = {
                'value': coef,
                'description': f'Окна: {target_windows} vs {median_windows} (медиана)',
                'target_value': target_windows,
                'median_value': median_windows,
                'type': 'variable'
            }
            multiplier *= coef

    # Лифты
    if 'elevator_count' in comparison and not comparison['elevator_count']['equals_median']:
        target_elevator = target.elevator_count
        median_elevator = medians['elevator_count']

        if target_elevator in ELEVATOR_COUNT_COEFFICIENTS:
            target_coef = ELEVATOR_COUNT_COEFFICIENTS[target_elevator]
            median_coef = ELEVATOR_COUNT_COEFFICIENTS.get(median_elevator, 1.0)

            coef = target_coef / median_coef

            adjustments['elevator_count'] = {
                'value': coef,
                'description': f'Лифты: {target_elevator} vs {median_elevator} (медиана)',
                'target_value': target_elevator,
                'median_value': median_elevator,
                'type': 'variable'
            }
            multiplier *= coef

    # Жилая площадь (процент)
    if 'living_area_percent' in comparison and not comparison['living_area_percent']['equals_median']:
        target_percent = comparison['living_area_percent']['target_value']
        median_percent = comparison['living_area_percent']['median_value']

        target_coef = get_living_area_coefficient(target.living_area, target.total_area)
        # Для медианы рассчитываем коэффициент
        median_living_area = target.total_area * (median_percent / 100)
        median_coef = get_living_area_coefficient(median_living_area, target.total_area)

        coef = target_coef / median_coef

        adjustments['living_area_percent'] = {
            'value': coef,
            'description': f'Жилая площадь: {target_percent:.1f}% vs {median_percent:.1f}% (медиана)',
            'target_value': target_percent,
            'median_value': median_percent,
            'type': 'variable'
        }
        multiplier *= coef

    # Площадь квартиры - АДАПТИВНЫЙ РАСЧЕТ
    if 'total_area' in comparison and not comparison['total_area']['equals_median']:
        target_area = target.total_area

        # АДАПТИВНЫЙ РАСЧЕТ (учитывает разброс площадей в выборке)
        coef, explanation = calculate_area_coefficient_adaptive(target_area, comparables)

        # Логируем использование адаптивного коэффициента
        if explanation['type'] == 'adaptive':
            logger.info(f"✨ Адаптивный коэффициент площади: {coef:.3f}")
            logger.info(f"   Целевая: {target_area:.1f} м², медиана: {explanation['median_area']:.1f} м²")
        elif explanation['type'] == 'no_adjustment':
            logger.debug(f"ℹ️ Коэффициент площади не применяется: {explanation['reason']}")
        else:
            logger.debug(f"⚠️ Фиксированный коэффициент площади: {coef:.3f} ({explanation['reason']})")

        adjustments['total_area'] = {
            'value': coef,
            'description': f'Площадь: {target_area:.1f}м²',
            'target_value': target_area,
            'median_value': explanation.get('median_area', medians.get('total_area')),
            'type': explanation['type'],  # 'adaptive', 'no_adjustment', или 'fixed'
            'explanation': explanation
        }
        multiplier *= coef

    return multiplier, adjustments


def _apply_position_adjustments(target, medians, comparison, multiplier, adjustments, comparables):
    """
    Применить корректировки за расположение в доме

    ФАЗА 3: Используем АДАПТИВНЫЙ коэффициент этажа
    """

    # Этаж - АДАПТИВНЫЙ РАСЧЕТ
    if 'floor' in comparison and not comparison['floor']['equals_median']:
        target_floor = target.floor

        # Используем total_floors целевого объекта
        if target.total_floors:
            # АДАПТИВНЫЙ РАСЧЕТ (рассчитывается из данных конкретного дома)
            coef, explanation = calculate_floor_coefficient_adaptive(
                target_floor,
                target.total_floors,
                comparables
            )

            # Логируем использование адаптивного коэффициента
            if explanation['type'] == 'adaptive':
                logger.info(f"✨ Адаптивный коэффициент этажа: {coef:.3f} ({explanation['zone']})")
                logger.info(f"   Данные: низкие={explanation['data_points']['low']}, "
                           f"средние={explanation['data_points']['mid']}, "
                           f"высокие={explanation['data_points']['high']}")
            else:
                logger.debug(f"⚠️ Фиксированный коэффициент этажа: {coef:.3f} ({explanation['reason']})")

            adjustments['floor'] = {
                'value': coef,
                'description': f'Этаж: {target_floor}/{target.total_floors} ({explanation["zone"]})',
                'target_value': target_floor,
                'median_value': medians.get('floor'),
                'type': explanation['type'],  # 'adaptive' или 'fixed'
                'explanation': explanation
            }
            multiplier *= coef

    # УДАЛЕНО: Расстояние до метро (сравнение в одной области)

    return multiplier, adjustments


def _apply_individual_adjustments(target, medians, comparison, multiplier, adjustments):
    """Применить индивидуальные корректировки"""

    # УДАЛЕНО: Количество парковочных мест (не имеет смысла без контекста)
    # Парковка уже учтена в FIXED параметрах (parking_type)

    return multiplier, adjustments


def _apply_view_adjustments(target, medians, comparison, multiplier, adjustments):
    """Применить корректировки за вид и эстетику"""

    # Вид из окна (максимум 5% влияния)
    if 'view_type' in comparison and not comparison['view_type']['equals_median']:
        target_view = target.view_type
        median_view = medians['view_type']

        if target_view in VIEW_TYPE_COEFFICIENTS:
            target_coef = VIEW_TYPE_COEFFICIENTS[target_view]
            median_coef = VIEW_TYPE_COEFFICIENTS.get(median_view, 1.0)

            coef = target_coef / median_coef

            adjustments['view_type'] = {
                'value': coef,
                'description': f'Вид: {target_view} vs {median_view} (медиана)',
                'target_value': target_view,
                'median_value': median_view,
                'type': 'variable'
            }
            multiplier *= coef

    # УДАЛЕНО: Уровень шума (сравнение в одной области)
    # УДАЛЕНО: Людность (не учитывается)

    return multiplier, adjustments


def _apply_risk_adjustments(target, medians, comparison, multiplier, adjustments):
    """Применить корректировки за риски"""

    # Тип фотографий
    if 'photo_type' in comparison and not comparison['photo_type']['equals_median']:
        target_photo = target.photo_type
        median_photo = medians['photo_type']

        if target_photo in PHOTO_TYPE_COEFFICIENTS:
            target_coef = PHOTO_TYPE_COEFFICIENTS[target_photo]
            median_coef = PHOTO_TYPE_COEFFICIENTS.get(median_photo, 1.0)

            coef = target_coef / median_coef

            adjustments['photo_type'] = {
                'value': coef,
                'description': f'Фото: {target_photo} vs {median_photo} (медиана)',
                'target_value': target_photo,
                'median_value': median_photo,
                'type': 'variable'
            }
            multiplier *= coef

    # Статус объекта
    if 'object_status' in comparison and not comparison['object_status']['equals_median']:
        target_status = target.object_status
        median_status = medians['object_status']

        if target_status in OBJECT_STATUS_COEFFICIENTS:
            target_coef = OBJECT_STATUS_COEFFICIENTS[target_status]
            median_coef = OBJECT_STATUS_COEFFICIENTS.get(median_status, 1.0)

            coef = target_coef / median_coef

            adjustments['object_status'] = {
                'value': coef,
                'description': f'Статус: {target_status} vs {median_status} (медиана)',
                'target_value': target_status,
                'median_value': median_status,
                'type': 'variable'
            }
            multiplier *= coef

    # Возраст дома
    if 'build_year' in comparison and not comparison['build_year']['equals_median']:
        target_year = target.build_year
        median_year = int(medians['build_year'])

        target_coef = get_building_age_coefficient(target_year)
        median_coef = get_building_age_coefficient(median_year)

        coef = target_coef / median_coef

        current_year = datetime.now().year
        target_age = current_year - target_year
        median_age = current_year - median_year

        adjustments['build_year'] = {
            'value': coef,
            'description': f'Возраст: {target_age} лет ({target_year}) vs {median_age} лет ({median_year}) (медиана)',
            'target_value': target_year,
            'median_value': median_year,
            'type': 'variable'
        }
        multiplier *= coef

    # Ликвидность (очень высокая цена)
    if target.price:
        coef = get_price_liquidity_coefficient(target.price)
        if coef < 1.0:
            adjustments['liquidity'] = {
                'value': coef,
                'description': f'Ликвидность: цена {target.price:,.0f} ₽ (высокая - низкая ликвидность)',
                'target_value': target.price,
                'median_value': None,
                'type': 'variable'
            }
            multiplier *= coef

    return multiplier, adjustments


def _fallback_calculation(target, base_price_per_sqm, method):
    """
    Упрощенный расчет без медиан (fallback)
    Используется, если не удалось рассчитать медианы
    """
    logger.warning("Используется упрощенный расчет без медиан")

    adjustments = {}
    multiplier = 1.0

    # Простые коэффициенты без сравнения с медианой
    if target.repair_level and target.repair_level in REPAIR_LEVEL_COEFFICIENTS:
        coef = REPAIR_LEVEL_COEFFICIENTS[target.repair_level]
        adjustments['repair_level'] = {
            'value': coef,
            'description': f'Отделка: {target.repair_level}',
            'type': 'simple'
        }
        multiplier *= coef

    fair_price_per_sqm = base_price_per_sqm * multiplier
    fair_price_total = fair_price_per_sqm * (target.total_area or 0)

    current_price = target.price or 0
    price_diff_amount = current_price - fair_price_total
    price_diff_percent = (price_diff_amount / fair_price_total * 100) if fair_price_total > 0 else 0

    return {
        'base_price_per_sqm': base_price_per_sqm,
        'adjustments': adjustments,
        'final_multiplier': multiplier,
        'fair_price_per_sqm': fair_price_per_sqm,
        'fair_price_total': fair_price_total,
        'current_price': current_price,
        'price_diff_amount': price_diff_amount,
        'price_diff_percent': price_diff_percent,
        'is_overpriced': price_diff_percent > 5,
        'is_underpriced': price_diff_percent < -5,
        'is_fair': -5 <= price_diff_percent <= 5,
        'method': method + '_fallback'
    }
