"""
Прогноз времени продажи недвижимости

Реалистичный прогноз срока продажи на основе:
- Индекса привлекательности
- Адекватности цены
- Характеристик рынка
- Исторических данных
"""

import logging
import math
from typing import Dict, List

logger = logging.getLogger(__name__)


def forecast_time_to_sell(
    current_price: float,
    fair_price: float,
    attractiveness_index: float,
    market_stats: Dict = None
) -> Dict:
    """
    Прогноз времени продажи при текущей цене

    Args:
        current_price: Текущая цена объекта
        fair_price: Справедливая цена
        attractiveness_index: Индекс привлекательности (0-100)
        market_stats: Рыночная статистика

    Returns:
        Словарь с прогнозом времени и вероятностями
    """

    if not current_price or not fair_price or current_price <= 0 or fair_price <= 0:
        return {}

    # Расчет переоценки
    overpricing_percent = ((current_price / fair_price) - 1) * 100

    # Базовое время продажи (месяцы) на основе индекса привлекательности
    # Индекс 100 -> 1 месяц, индекс 50 -> 6 месяцев, индекс 0 -> 24+ месяца
    base_time = _calculate_base_time_from_attractiveness(attractiveness_index)

    # Корректировка на переоценку
    # Каждые 5% переоценки увеличивают время продажи на 30-50%
    overpricing_factor = 1 + (max(0, overpricing_percent) / 5) * 0.4

    # Итоговое ожидаемое время
    expected_time_months = base_time * overpricing_factor

    # Диапазон времени (мин-макс)
    min_time_months = max(1, expected_time_months * 0.6)
    max_time_months = expected_time_months * 1.5

    # Медиана (50% вероятности)
    median_time_months = expected_time_months

    # Расчет вероятностей продажи по месяцам
    probabilities = _calculate_monthly_probabilities(
        expected_time_months,
        overpricing_percent,
        attractiveness_index
    )

    # Кумулятивные вероятности
    cumulative_probabilities = _calculate_cumulative_probabilities(probabilities)

    result = {
        'expected_time_months': round(expected_time_months, 1),
        'min_time_months': round(min_time_months, 1),
        'max_time_months': round(max_time_months, 1),
        'median_time_months': round(median_time_months, 1),

        'time_range_description': f"{min_time_months:.0f}-{max_time_months:.0f} месяцев",
        'median_description': f"{median_time_months:.0f} месяцев (наиболее вероятно)",

        'monthly_probabilities': probabilities[:12],  # Первые 12 месяцев
        'cumulative_probabilities': cumulative_probabilities[:12],

        'probability_milestones': {
            '1_month': cumulative_probabilities[0] if len(cumulative_probabilities) > 0 else 0,
            '3_months': cumulative_probabilities[2] if len(cumulative_probabilities) > 2 else 0,
            '6_months': cumulative_probabilities[5] if len(cumulative_probabilities) > 5 else 0,
            '12_months': cumulative_probabilities[11] if len(cumulative_probabilities) > 11 else 0,
        },

        'interpretation': _interpret_forecast(
            expected_time_months,
            overpricing_percent,
            attractiveness_index
        )
    }

    logger.info(
        f"Прогноз времени продажи: {expected_time_months:.1f} мес "
        f"(вероятность 6 мес: {result['probability_milestones']['6_months']:.0%})"
    )

    return result


def forecast_at_different_prices(
    fair_price: float,
    attractiveness_index: float,
    price_points: List[float] = None
) -> List[Dict]:
    """
    Прогноз времени продажи при разных ценах

    Args:
        fair_price: Справедливая цена
        attractiveness_index: Индекс привлекательности
        price_points: Список цен для анализа (если None, используются автоматические)

    Returns:
        Список прогнозов для каждой цены
    """

    if price_points is None:
        # Автоматические точки: от -10% до +20% от справедливой цены
        price_points = [
            fair_price * (1 + p / 100)
            for p in [-10, -7, -5, -3, 0, 3, 5, 7, 10, 15, 20]
        ]

    forecasts = []

    for price in price_points:
        discount_percent = ((price / fair_price) - 1) * 100

        forecast = forecast_time_to_sell(
            current_price=price,
            fair_price=fair_price,
            attractiveness_index=attractiveness_index
        )

        forecasts.append({
            'price': price,
            'discount_percent': round(discount_percent, 1),
            'expected_time_months': forecast.get('expected_time_months', 0),
            'probability_6_months': forecast.get('probability_milestones', {}).get('6_months', 0),
            'probability_12_months': forecast.get('probability_milestones', {}).get('12_months', 0),
        })

    return forecasts


def _calculate_base_time_from_attractiveness(attractiveness_index: float) -> float:
    """
    Расчет базового времени продажи из индекса привлекательности

    Args:
        attractiveness_index: Индекс 0-100

    Returns:
        Базовое время в месяцах
    """

    # Логарифмическая модель:
    # Индекс 100 -> 1 месяц
    # Индекс 85 -> 2 месяца
    # Индекс 70 -> 3 месяца
    # Индекс 55 -> 5 месяцев
    # Индекс 40 -> 8 месяцев
    # Индекс 25 -> 14 месяцев
    # Индекс 10 -> 24 месяца

    if attractiveness_index >= 85:
        return 1.0 + (100 - attractiveness_index) / 15
    elif attractiveness_index >= 70:
        return 2.0 + (85 - attractiveness_index) / 15
    elif attractiveness_index >= 55:
        return 3.0 + (70 - attractiveness_index) / 7.5
    elif attractiveness_index >= 40:
        return 5.0 + (55 - attractiveness_index) / 5
    elif attractiveness_index >= 25:
        return 8.0 + (40 - attractiveness_index) / 2.5
    else:
        return 14.0 + (25 - max(attractiveness_index, 10)) / 1.5


def _calculate_monthly_probabilities(
    expected_time_months: float,
    overpricing_percent: float,
    attractiveness_index: float
) -> List[float]:
    """
    Расчет месячной вероятности продажи

    Используется геометрическое распределение с корректировкой
    на переоценку и привлекательность

    Args:
        expected_time_months: Ожидаемое время продажи
        overpricing_percent: Процент переоценки
        attractiveness_index: Индекс привлекательности

    Returns:
        Список вероятностей для каждого месяца
    """

    # Параметр геометрического распределения
    # p = 1 / expected_time (средняя вероятность продажи в месяц)
    if expected_time_months <= 0:
        expected_time_months = 1

    monthly_probability_base = 1 / expected_time_months

    # Корректировка на динамику:
    # - Первые месяцы - выше вероятность (новое объявление)
    # - С течением времени - снижается (объект "залежался")

    probabilities = []

    for month in range(1, 25):  # 24 месяца
        # Базовая вероятность с учетом "старения" объявления
        freshness_factor = math.exp(-0.05 * (month - 1))  # Экспоненциальное затухание

        # Эффект новизны: первые 2-3 месяца повышенный интерес
        if month <= 2:
            newness_boost = 1.4
        elif month <= 4:
            newness_boost = 1.2
        else:
            newness_boost = 1.0

        # Месячная вероятность (что продастся в этом месяце, если еще не продано)
        monthly_prob = monthly_probability_base * freshness_factor * newness_boost

        # Ограничиваем разумными пределами
        monthly_prob = min(monthly_prob, 0.85)  # Максимум 85% в месяц

        probabilities.append(round(monthly_prob, 4))

    return probabilities


def _calculate_cumulative_probabilities(monthly_probabilities: List[float]) -> List[float]:
    """
    Расчет кумулятивной вероятности продажи

    P(продано к месяцу N) = 1 - П(1 - p_i) для i от 1 до N

    Args:
        monthly_probabilities: Список месячных вероятностей

    Returns:
        Список кумулятивных вероятностей
    """

    cumulative = []
    prob_not_sold = 1.0

    for monthly_prob in monthly_probabilities:
        # Вероятность НЕ продать в этом месяце
        prob_not_sold *= (1 - monthly_prob)

        # Кумулятивная вероятность продать к этому месяцу
        cumulative_prob = 1 - prob_not_sold

        cumulative.append(round(cumulative_prob, 4))

    return cumulative


def _interpret_forecast(
    expected_time_months: float,
    overpricing_percent: float,
    attractiveness_index: float
) -> Dict:
    """
    Интерпретация прогноза времени продажи

    Args:
        expected_time_months: Ожидаемое время продажи
        overpricing_percent: Процент переоценки
        attractiveness_index: Индекс привлекательности

    Returns:
        Словарь с интерпретацией
    """

    interpretation = {}

    # Общая оценка
    if expected_time_months <= 2:
        interpretation['overall'] = "✅ Отлично! Быстрая продажа очень вероятна."
    elif expected_time_months <= 4:
        interpretation['overall'] = "✅ Хорошо. Продажа в разумные сроки."
    elif expected_time_months <= 6:
        interpretation['overall'] = "⚠️ Средний срок. Требуется терпение и/или корректировки."
    elif expected_time_months <= 12:
        interpretation['overall'] = "⚠️ Долго. Рекомендуется пересмотреть цену и улучшить презентацию."
    else:
        interpretation['overall'] = "🔴 Очень долго. Необходимы срочные изменения в стратегии продажи."

    # Фактор цены
    if overpricing_percent > 15:
        interpretation['price_factor'] = (
            f"🔴 Сильная переоценка ({overpricing_percent:.1f}%) - "
            f"основной фактор длительной продажи"
        )
    elif overpricing_percent > 10:
        interpretation['price_factor'] = (
            f"⚠️ Переоценка ({overpricing_percent:.1f}%) значительно замедляет продажу"
        )
    elif overpricing_percent > 5:
        interpretation['price_factor'] = (
            f"Небольшая переоценка ({overpricing_percent:.1f}%) немного увеличивает срок"
        )
    elif overpricing_percent > -5:
        interpretation['price_factor'] = "✅ Цена адекватна рынку"
    else:
        interpretation['price_factor'] = (
            f"💰 Цена ниже рынка ({abs(overpricing_percent):.1f}%) - "
            f"способствует быстрой продаже"
        )

    # Фактор привлекательности
    if attractiveness_index >= 85:
        interpretation['attractiveness_factor'] = (
            "🌟 Высокая привлекательность объекта ускоряет продажу"
        )
    elif attractiveness_index >= 70:
        interpretation['attractiveness_factor'] = (
            "✅ Хорошая привлекательность объекта"
        )
    elif attractiveness_index >= 55:
        interpretation['attractiveness_factor'] = (
            "⚠️ Средняя привлекательность - есть потенциал для улучшения"
        )
    else:
        interpretation['attractiveness_factor'] = (
            "🔴 Низкая привлекательность замедляет продажу"
        )

    # Рекомендации
    recommendations = []

    if overpricing_percent > 10:
        recommendations.append("Снизить цену до справедливой или ниже")

    if attractiveness_index < 70:
        recommendations.append("Улучшить презентацию (фото, описание)")

    if attractiveness_index < 55:
        recommendations.append("Рассмотреть улучшения характеристик объекта")

    if expected_time_months > 6 and overpricing_percent < 5:
        recommendations.append("Возможно, рынок слабый - рассмотреть альтернативные стратегии")

    interpretation['recommendations'] = recommendations

    return interpretation


def generate_time_comparison_table(forecasts: List[Dict]) -> str:
    """
    Генерация таблицы сравнения времени продажи при разных ценах

    Args:
        forecasts: Список прогнозов от forecast_at_different_prices

    Returns:
        Markdown-таблица
    """

    lines = []
    lines.append("| Цена | Отклонение | Время продажи | Вероятность (6 мес) | Вероятность (12 мес) |")
    lines.append("|------|------------|---------------|---------------------|----------------------|")

    for f in forecasts:
        price_str = f"{f['price']/1_000_000:.2f}M"
        discount_str = f"{f['discount_percent']:+.1f}%"
        time_str = f"{f['expected_time_months']:.1f} мес"
        prob_6_str = f"{f['probability_6_months']:.0%}"
        prob_12_str = f"{f['probability_12_months']:.0%}"

        # Выделяем справедливую цену
        if abs(f['discount_percent']) < 1:
            price_str = f"**{price_str}**"
            time_str = f"**{time_str}**"

        lines.append(f"| {price_str} | {discount_str} | {time_str} | {prob_6_str} | {prob_12_str} |")

    return "\n".join(lines)
