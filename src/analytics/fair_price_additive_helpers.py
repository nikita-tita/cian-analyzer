"""
Аддитивные helper-функции для расчета справедливой цены

НОВАЯ ЛОГИКА: Каждый фактор дает независимую оценку от базовой медианы
"""

import logging
from typing import List, Dict, Tuple, Any

logger = logging.getLogger(__name__)


# Импорт коэффициентов
from .coefficients import (
    REPAIR_LEVEL_COEFFICIENTS,
    VIEW_TYPE_COEFFICIENTS,
    WINDOW_TYPE_COEFFICIENTS,
    ELEVATOR_COUNT_COEFFICIENTS,
    BATHROOMS_COEFFICIENTS,
    get_ceiling_height_coefficient,
    get_living_area_coefficient,
    # Адаптивные коэффициенты
    calculate_floor_coefficient_adaptive,
    calculate_area_coefficient_adaptive
)


def _apply_repair_adjustment_additive(
    target, medians, comparison, base_price, price_estimates, adjustments
) -> Tuple[List[float], Dict]:
    """Применить корректировку за отделку (аддитивно)"""
    if 'repair_level' in comparison and not comparison['repair_level']['equals_median']:
        target_repair = target.repair_level
        median_repair = medians['repair_level']

        if target_repair in REPAIR_LEVEL_COEFFICIENTS:
            target_coef = REPAIR_LEVEL_COEFFICIENTS[target_repair]
            median_coef = REPAIR_LEVEL_COEFFICIENTS.get(median_repair, 1.0)

            # Коэффициент = отношение целевого к медиане
            coef = target_coef / median_coef

            # Добавляем независимую оценку
            price_estimate = base_price * coef
            price_estimates.append(price_estimate)

            adjustments['repair_level'] = {
                'value': coef,
                'percent': (coef - 1.0) * 100,
                'price_estimate': price_estimate,
                'description': f'Отделка: {target_repair} vs {median_repair} (медиана)',
                'target_value': target_repair,
                'median_value': median_repair,
                'type': 'variable'
            }

            logger.debug(f"  Отделка: {target_repair} → коэфф {coef:.3f} → {price_estimate:,.0f} ₽/м²")

    return price_estimates, adjustments


def _apply_apartment_features_adjustments_additive(
    target, medians, comparison, base_price, price_estimates, adjustments, comparables
) -> Tuple[List[float], Dict]:
    """Применить корректировки за характеристики квартиры (аддитивно)"""

    # 1. Высота потолков
    if 'ceiling_height' in comparison and not comparison['ceiling_height']['equals_median']:
        target_height = target.ceiling_height
        median_height = medians['ceiling_height']

        target_coef = get_ceiling_height_coefficient(target_height)
        median_coef = get_ceiling_height_coefficient(median_height)
        coef = target_coef / median_coef

        price_estimate = base_price * coef
        price_estimates.append(price_estimate)

        adjustments['ceiling_height'] = {
            'value': coef,
            'percent': (coef - 1.0) * 100,
            'price_estimate': price_estimate,
            'description': f'Высота потолков: {target_height}м vs {median_height:.1f}м (медиана)',
            'target_value': target_height,
            'median_value': median_height,
            'type': 'variable'
        }

        logger.debug(f"  Потолки: {target_height}м → коэфф {coef:.3f} → {price_estimate:,.0f} ₽/м²")

    # 2. Ванные комнаты
    if 'bathrooms' in comparison and not comparison['bathrooms']['equals_median']:
        target_bathrooms = target.bathrooms
        median_bathrooms = int(medians['bathrooms'])

        # Раздельный санузел +5%, два санузла +10%, совмещенный -7%
        # Упрощенная логика: +5% за каждую дополнительную ванную (до +10%)
        diff = target_bathrooms - median_bathrooms
        coef = 1 + (diff * 0.05)
        coef = max(0.90, min(coef, 1.10))  # Ограничение ±10%

        price_estimate = base_price * coef
        price_estimates.append(price_estimate)

        adjustments['bathrooms'] = {
            'value': coef,
            'percent': (coef - 1.0) * 100,
            'price_estimate': price_estimate,
            'description': f'Ванные комнаты: {target_bathrooms} vs {median_bathrooms} (медиана)',
            'target_value': target_bathrooms,
            'median_value': median_bathrooms,
            'type': 'variable'
        }

        logger.debug(f"  Санузлы: {target_bathrooms} → коэфф {coef:.3f} → {price_estimate:,.0f} ₽/м²")

    # 3. Тип окон
    if 'window_type' in comparison and not comparison['window_type']['equals_median']:
        target_windows = target.window_type
        median_windows = medians['window_type']

        if target_windows in WINDOW_TYPE_COEFFICIENTS:
            target_coef = WINDOW_TYPE_COEFFICIENTS[target_windows]
            median_coef = WINDOW_TYPE_COEFFICIENTS.get(median_windows, 1.0)
            coef = target_coef / median_coef

            # Ограничение ±10% (по требованию пользователя)
            coef = max(0.90, min(coef, 1.10))

            price_estimate = base_price * coef
            price_estimates.append(price_estimate)

            adjustments['window_type'] = {
                'value': coef,
                'percent': (coef - 1.0) * 100,
                'price_estimate': price_estimate,
                'description': f'Окна: {target_windows} vs {median_windows} (медиана)',
                'target_value': target_windows,
                'median_value': median_windows,
                'type': 'variable'
            }

            logger.debug(f"  Окна: {target_windows} → коэфф {coef:.3f} → {price_estimate:,.0f} ₽/м²")

    # 4. Лифты
    if 'elevator_count' in comparison and not comparison['elevator_count']['equals_median']:
        target_elevator = target.elevator_count
        median_elevator = medians['elevator_count']

        if target_elevator in ELEVATOR_COUNT_COEFFICIENTS:
            target_coef = ELEVATOR_COUNT_COEFFICIENTS[target_elevator]
            median_coef = ELEVATOR_COUNT_COEFFICIENTS.get(median_elevator, 1.0)
            coef = target_coef / median_coef

            price_estimate = base_price * coef
            price_estimates.append(price_estimate)

            adjustments['elevator_count'] = {
                'value': coef,
                'percent': (coef - 1.0) * 100,
                'price_estimate': price_estimate,
                'description': f'Лифты: {target_elevator} vs {median_elevator} (медиана)',
                'target_value': target_elevator,
                'median_value': median_elevator,
                'type': 'variable'
            }

            logger.debug(f"  Лифты: {target_elevator} → коэфф {coef:.3f} → {price_estimate:,.0f} ₽/м²")

    # 5. Жилая площадь (процент)
    if 'living_area_percent' in comparison and not comparison['living_area_percent']['equals_median']:
        target_percent = comparison['living_area_percent']['target_value']
        median_percent = comparison['living_area_percent']['median_value']

        target_coef = get_living_area_coefficient(target.living_area, target.total_area)
        median_living_area = target.total_area * (median_percent / 100)
        median_coef = get_living_area_coefficient(median_living_area, target.total_area)
        coef = target_coef / median_coef

        price_estimate = base_price * coef
        price_estimates.append(price_estimate)

        adjustments['living_area_percent'] = {
            'value': coef,
            'percent': (coef - 1.0) * 100,
            'price_estimate': price_estimate,
            'description': f'Жилая площадь: {target_percent:.1f}% vs {median_percent:.1f}% (медиана)',
            'target_value': target_percent,
            'median_value': median_percent,
            'type': 'variable'
        }

        logger.debug(f"  Жилая площадь: {target_percent:.1f}% → коэфф {coef:.3f} → {price_estimate:,.0f} ₽/м²")

    # 6. Площадь квартиры - АДАПТИВНЫЙ РАСЧЕТ
    if 'total_area' in comparison and not comparison['total_area']['equals_median']:
        target_area = target.total_area

        coef, explanation = calculate_area_coefficient_adaptive(target_area, comparables)

        if explanation['type'] != 'no_adjustment':
            price_estimate = base_price * coef
            price_estimates.append(price_estimate)

            adjustments['total_area'] = {
                'value': coef,
                'percent': (coef - 1.0) * 100,
                'price_estimate': price_estimate,
                'description': f'Площадь: {target_area:.1f}м²',
                'target_value': target_area,
                'median_value': explanation.get('median_area', medians.get('total_area')),
                'type': explanation['type'],
                'explanation': explanation
            }

            if explanation['type'] == 'adaptive':
                logger.info(f"  ✨ Площадь (адаптивно): {target_area:.1f}м² → коэфф {coef:.3f} → {price_estimate:,.0f} ₽/м²")
            else:
                logger.debug(f"  Площадь: {target_area:.1f}м² → коэфф {coef:.3f} → {price_estimate:,.0f} ₽/м²")

    return price_estimates, adjustments


def _apply_position_adjustments_additive(
    target, medians, comparison, base_price, price_estimates, adjustments, comparables
) -> Tuple[List[float], Dict]:
    """Применить корректировки за расположение в доме (аддитивно)"""

    # Этаж - АДАПТИВНЫЙ РАСЧЕТ
    if 'floor' in comparison and not comparison['floor']['equals_median']:
        target_floor = target.floor

        if target.total_floors:
            coef, explanation = calculate_floor_coefficient_adaptive(
                target_floor,
                target.total_floors,
                comparables
            )

            price_estimate = base_price * coef
            price_estimates.append(price_estimate)

            adjustments['floor'] = {
                'value': coef,
                'percent': (coef - 1.0) * 100,
                'price_estimate': price_estimate,
                'description': f'Этаж: {target_floor}/{target.total_floors} ({explanation.get("zone", "средний")})',
                'target_value': target_floor,
                'median_value': medians.get('floor'),
                'type': explanation['type'],
                'explanation': explanation
            }

            if explanation['type'] == 'adaptive':
                logger.info(f"  ✨ Этаж (адаптивно): {target_floor}/{target.total_floors} → коэфф {coef:.3f} → {price_estimate:,.0f} ₽/м²")
            else:
                logger.debug(f"  Этаж: {target_floor}/{target.total_floors} → коэфф {coef:.3f} → {price_estimate:,.0f} ₽/м²")

    return price_estimates, adjustments


def _apply_view_adjustments_additive(
    target, medians, comparison, base_price, price_estimates, adjustments
) -> Tuple[List[float], Dict]:
    """Применить корректировки за вид и эстетику (аддитивно)"""

    # Вид из окна (максимум 5% влияния)
    if 'view_type' in comparison and not comparison['view_type']['equals_median']:
        target_view = target.view_type
        median_view = medians['view_type']

        if target_view in VIEW_TYPE_COEFFICIENTS:
            target_coef = VIEW_TYPE_COEFFICIENTS[target_view]
            median_coef = VIEW_TYPE_COEFFICIENTS.get(median_view, 1.0)
            coef = target_coef / median_coef

            price_estimate = base_price * coef
            price_estimates.append(price_estimate)

            adjustments['view_type'] = {
                'value': coef,
                'percent': (coef - 1.0) * 100,
                'price_estimate': price_estimate,
                'description': f'Вид: {target_view} vs {median_view} (медиана)',
                'target_value': target_view,
                'median_value': median_view,
                'type': 'variable'
            }

            logger.debug(f"  Вид: {target_view} → коэфф {coef:.3f} → {price_estimate:,.0f} ₽/м²")

    return price_estimates, adjustments


def _apply_risk_adjustments_additive(
    target, medians, comparison, base_price, price_estimates, adjustments
) -> Tuple[List[float], Dict]:
    """Применить корректировки за риски и качество материалов (аддитивно)"""

    # НОВОЕ: Качество фото/материалов для ЦЕЛЕВОГО объекта
    # Логика: если продаем по цене люкс-ремонта, но только с рендерами - это минус
    # ~4% в разные стороны
    # ВАЖНО: Применяется ТОЛЬКО если пользователь явно указал!
    if hasattr(target, 'material_quality') and target.material_quality and target.material_quality is not None:
        material_quality = target.material_quality

        MATERIAL_QUALITY_COEFFICIENTS = {
            'качественные_фото_видео': 1.02,  # +2% (доверие покупателей)
            'качественные_фото': 1.00,  # Базовый уровень
            'только_рендеры': 0.98,  # -2% (нет доверия)
            'только_планировка': 0.96,  # -4% (большие риски)
        }

        if material_quality in MATERIAL_QUALITY_COEFFICIENTS:
            coef = MATERIAL_QUALITY_COEFFICIENTS[material_quality]

            price_estimate = base_price * coef
            price_estimates.append(price_estimate)

            adjustments['material_quality'] = {
                'value': coef,
                'percent': (coef - 1.0) * 100,
                'price_estimate': price_estimate,
                'description': f'Качество материалов: {material_quality}',
                'target_value': material_quality,
                'type': 'target_only'
            }

            logger.debug(f"  Качество материалов: {material_quality} → коэфф {coef:.3f} → {price_estimate:,.0f} ₽/м²")

    # НОВОЕ: Статус собственности (вместо статуса объекта)
    # ВАЖНО: Применяется ТОЛЬКО если пользователь явно указал!
    if hasattr(target, 'ownership_status') and target.ownership_status and target.ownership_status is not None:
        ownership_status = target.ownership_status

        OWNERSHIP_STATUS_COEFFICIENTS = {
            '1_собственник_без_обременений': 1.05,  # +5% (быстрая сделка)
            '1+_собственников_без_обременений': 1.01,  # +1% (согласования)
            'ипотека_рассрочка': 0.98,  # -2% (нужно ждать)
            'есть_обременения': 0.93,  # -7% (сложности)
        }

        if ownership_status in OWNERSHIP_STATUS_COEFFICIENTS:
            coef = OWNERSHIP_STATUS_COEFFICIENTS[ownership_status]

            price_estimate = base_price * coef
            price_estimates.append(price_estimate)

            adjustments['ownership_status'] = {
                'value': coef,
                'percent': (coef - 1.0) * 100,
                'price_estimate': price_estimate,
                'description': f'Статус собственности: {ownership_status.replace("_", " ")}',
                'target_value': ownership_status,
                'type': 'target_only'
            }

            logger.debug(f"  Статус собственности: {ownership_status} → коэфф {coef:.3f} → {price_estimate:,.0f} ₽/м²")

    # УДАЛЕНО: build_year (возраст дома) - по требованию пользователя (под вопросом)
    # Причина: есть клевые сталинки и хрущевки, плюс реновация

    return price_estimates, adjustments
