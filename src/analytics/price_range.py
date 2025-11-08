"""
Расчет диапазона справедливой цены

Вместо одной точечной оценки предоставляет понятный диапазон для принятия решений:
- Минимальная цена (нижняя граница для быстрой продажи)
- Справедливая цена (медианная оценка)
- Рекомендуемая цена листинга (с учетом торга)
- Максимальная цена (верхняя граница без потери ликвидности)
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def calculate_price_range(
    fair_price: float,
    confidence_interval: Optional[Dict] = None,
    overpricing_percent: float = 0,
    market_stats: Optional[Dict] = None
) -> Dict:
    """
    Расчет диапазона цен для принятия решений

    Args:
        fair_price: Справедливая цена (базовая оценка)
        confidence_interval: Доверительный интервал 95% {'lower': float, 'upper': float, 'margin': float}
        overpricing_percent: Текущая переоценка в процентах
        market_stats: Рыночная статистика для контекста

    Returns:
        Словарь с диапазоном цен и рекомендациями
    """

    if not fair_price or fair_price <= 0:
        return {}

    # Получаем границы доверительного интервала
    if confidence_interval and 'lower' in confidence_interval and 'upper' in confidence_interval:
        ci_lower = confidence_interval['lower']
        ci_upper = confidence_interval['upper']
        ci_margin = confidence_interval.get('margin', (ci_upper - ci_lower) / 2)
    else:
        # Если CI не предоставлен, используем ±5% от справедливой цены
        ci_margin = fair_price * 0.05
        ci_lower = fair_price - ci_margin
        ci_upper = fair_price + ci_margin

    # 1. МИНИМАЛЬНАЯ ЦЕНА (для быстрой продажи)
    # Нижняя граница CI минус небольшой буфер (2-3%)
    min_price = ci_lower * 0.97

    # 2. СПРАВЕДЛИВАЯ ЦЕНА (базовая оценка)
    # Уже есть - это fair_price

    # 3. РЕКОМЕНДУЕМАЯ ЦЕНА ЛИСТИНГА
    # Справедливая цена + премия для торга (3-7% в зависимости от рынка)
    # Если объект уже переоценен, не добавляем дополнительную премию
    if overpricing_percent > 5:
        # Объект уже переоценен - листинг = справедливая
        recommended_listing = fair_price
        listing_premium_percent = 0
    elif overpricing_percent > 0:
        # Небольшая переоценка - минимальная премия
        listing_premium_percent = 3
        recommended_listing = fair_price * 1.03
    else:
        # Нормальная цена или недооценка - стандартная премия для торга
        listing_premium_percent = 5
        recommended_listing = fair_price * 1.05

    # 4. МАКСИМАЛЬНАЯ ЦЕНА (верхняя граница без потери ликвидности)
    # Верхняя граница CI плюс небольшой буфер (2-3%)
    max_price = ci_upper * 1.03

    # 5. МИНИМАЛЬНАЯ ЦЕНА ПРОДАЖИ (после торга)
    # Рекомендуемая листинговая минус стандартная скидка (3-5%)
    min_acceptable_price = recommended_listing * 0.95

    # Убеждаемся что минимальная цена продажи не ниже минимальной цены
    if min_acceptable_price < min_price:
        min_acceptable_price = min_price

    # Рассчитываем проценты от справедливой цены
    result = {
        'min_price': min_price,
        'min_price_percent': ((min_price / fair_price - 1) * 100) if fair_price > 0 else 0,
        'min_price_description': 'Минимальная цена для быстрой продажи (1-2 месяца)',

        'fair_price': fair_price,
        'fair_price_description': 'Справедливая рыночная цена',

        'recommended_listing': recommended_listing,
        'recommended_listing_percent': ((recommended_listing / fair_price - 1) * 100) if fair_price > 0 else 0,
        'recommended_listing_description': f'Рекомендуемая цена объявления (+{listing_premium_percent}% для торга)',

        'max_price': max_price,
        'max_price_percent': ((max_price / fair_price - 1) * 100) if fair_price > 0 else 0,
        'max_price_description': 'Максимальная цена без потери ликвидности',

        'min_acceptable_price': min_acceptable_price,
        'min_acceptable_percent': ((min_acceptable_price / fair_price - 1) * 100) if fair_price > 0 else 0,
        'min_acceptable_description': 'Минимальная цена продажи (после торга)',

        'price_range_spread': max_price - min_price,
        'price_range_spread_percent': ((max_price - min_price) / fair_price * 100) if fair_price > 0 else 0,

        'negotiation_room': recommended_listing - min_acceptable_price,
        'negotiation_room_percent': ((recommended_listing - min_acceptable_price) / recommended_listing * 100) if recommended_listing > 0 else 0,
    }

    # Добавляем интерпретацию
    result['interpretation'] = _generate_interpretation(result, overpricing_percent)

    # Добавляем визуальное представление
    result['visual_range'] = _generate_visual_range(result)

    logger.info(
        f"Диапазон цен рассчитан: "
        f"{min_price:,.0f} - {fair_price:,.0f} - {max_price:,.0f} ₽"
    )

    return result


def _generate_interpretation(price_range: Dict, current_overpricing: float) -> Dict:
    """
    Генерация интерпретации диапазона цен

    Args:
        price_range: Словарь с диапазоном цен
        current_overpricing: Текущая переоценка в процентах

    Returns:
        Словарь с интерпретацией и рекомендациями
    """

    fair_price = price_range['fair_price']
    recommended = price_range['recommended_listing']
    min_price = price_range['min_price']
    max_price = price_range['max_price']

    interpretation = {
        'pricing_strategy': '',
        'expected_timeline': '',
        'negotiation_advice': '',
        'risk_assessment': ''
    }

    # Стратегия ценообразования
    if current_overpricing > 15:
        interpretation['pricing_strategy'] = (
            f"🔴 КРИТИЧНО: Объект сильно переоценен ({current_overpricing:.1f}%). "
            f"Рекомендуется немедленно снизить цену до {fair_price:,.0f} ₽ "
            f"или даже {min_price:,.0f} ₽ для быстрой продажи."
        )
    elif current_overpricing > 10:
        interpretation['pricing_strategy'] = (
            f"⚠️ Объект переоценен ({current_overpricing:.1f}%). "
            f"Рекомендуется установить цену {recommended:,.0f} ₽ "
            f"с готовностью к торгу до {fair_price:,.0f} ₽."
        )
    elif current_overpricing > 5:
        interpretation['pricing_strategy'] = (
            f"💡 Небольшая переоценка ({current_overpricing:.1f}%). "
            f"Можно держать текущую цену, но быть готовым к активному торгу."
        )
    elif current_overpricing > -5:
        interpretation['pricing_strategy'] = (
            f"✅ Цена близка к рынку. Рекомендуется листинг {recommended:,.0f} ₽ "
            f"с готовностью продать от {price_range['min_acceptable_price']:,.0f} ₽."
        )
    else:
        interpretation['pricing_strategy'] = (
            f"💰 Объект недооценен ({abs(current_overpricing):.1f}%). "
            f"Можно повысить цену до {recommended:,.0f} ₽ без риска потери покупателей."
        )

    # Ожидаемый срок продажи
    if current_overpricing > 15:
        interpretation['expected_timeline'] = "12+ месяцев при текущей цене, 2-4 месяца при справедливой"
    elif current_overpricing > 10:
        interpretation['expected_timeline'] = "6-12 месяцев при текущей цене, 3-6 месяцев при корректировке"
    elif current_overpricing > 5:
        interpretation['expected_timeline'] = "4-6 месяцев при активном торге"
    elif current_overpricing > -5:
        interpretation['expected_timeline'] = "2-4 месяца при нормальной активности"
    else:
        interpretation['expected_timeline'] = "1-2 месяца (быстрая продажа)"

    # Совет по торгу
    negotiation_room_percent = price_range['negotiation_room_percent']
    interpretation['negotiation_advice'] = (
        f"Заложите {negotiation_room_percent:.1f}% ({price_range['negotiation_room']:,.0f} ₽) "
        f"на торг. Не опускайтесь ниже {price_range['min_acceptable_price']:,.0f} ₽."
    )

    # Оценка рисков
    spread_percent = price_range['price_range_spread_percent']
    if spread_percent > 20:
        interpretation['risk_assessment'] = (
            f"⚠️ Высокая неопределенность (разброс {spread_percent:.1f}%). "
            f"Рекомендуется собрать больше аналогов для точной оценки."
        )
    elif spread_percent > 15:
        interpretation['risk_assessment'] = (
            f"Умеренная неопределенность (разброс {spread_percent:.1f}%). "
            f"Оценка надежна, но возможны колебания."
        )
    else:
        interpretation['risk_assessment'] = (
            f"✅ Низкая неопределенность (разброс {spread_percent:.1f}%). "
            f"Оценка очень надежна."
        )

    return interpretation


def _generate_visual_range(price_range: Dict) -> str:
    """
    Генерация ASCII-визуализации диапазона цен

    Args:
        price_range: Словарь с диапазоном цен

    Returns:
        ASCII-строка с визуализацией
    """

    min_price = price_range['min_price']
    fair_price = price_range['fair_price']
    max_price = price_range['max_price']
    recommended = price_range['recommended_listing']

    # Создаем простую визуализацию
    visual = f"""
    Диапазон цен:

    {min_price/1_000_000:.1f}M ←─────┼─────┼─────→ {max_price/1_000_000:.1f}M
           MIN    FAIR   REC
                  {fair_price/1_000_000:.1f}M  {recommended/1_000_000:.1f}M
    """

    return visual.strip()


def calculate_price_sensitivity(
    fair_price: float,
    base_probability: float = 0.75,
    time_months: int = 6
) -> list:
    """
    Расчет чувствительности вероятности продажи к изменению цены

    Args:
        fair_price: Справедливая цена
        base_probability: Базовая вероятность продажи по справедливой цене
        time_months: Срок для расчета вероятности

    Returns:
        Список точек {price, discount_percent, probability, expected_time}
    """

    # Точки для анализа: от -10% до +15% от справедливой цены
    price_points = [
        -10, -7, -5, -3, 0, 3, 5, 7, 10, 15
    ]

    sensitivity = []

    for discount_percent in price_points:
        price = fair_price * (1 + discount_percent / 100)

        # Эвристическая модель вероятности
        # При справедливой цене (0%) -> базовая вероятность
        # При скидке -> вероятность растет
        # При переоценке -> вероятность падает
        if discount_percent <= 0:
            # Скидка или справедливая цена
            probability = min(0.95, base_probability + abs(discount_percent) * 0.02)
            expected_time = time_months * (1 - abs(discount_percent) * 0.03)
        else:
            # Переоценка
            probability = max(0.10, base_probability - discount_percent * 0.04)
            expected_time = time_months * (1 + discount_percent * 0.15)

        sensitivity.append({
            'price': price,
            'discount_percent': discount_percent,
            'probability': round(probability, 2),
            'expected_time_months': round(expected_time, 1)
        })

    return sensitivity
