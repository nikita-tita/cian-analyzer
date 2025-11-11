"""
Расчет уверенности в результате анализа

Метрики уверенности (0-100%):
- Количество аналогов (больше = лучше)
- Качество данных (CV < 20% = хорошо)
- Количество адаптивных коэффициентов (больше = лучше)
- Величина множителя (близко к 1.0 = хорошо)

Использование:
    from .confidence_calculator import calculate_confidence, generate_detailed_report

    confidence = calculate_confidence(comparables, data_quality, adjustments)
    report = generate_detailed_report(target, comparables, fair_price_result, confidence)
"""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# РАСЧЕТ УВЕРЕННОСТИ
# ═══════════════════════════════════════════════════════════════════════════

def calculate_confidence(
    comparables: List,
    data_quality: Dict[str, Any],
    adjustments: Dict[str, Any],
    final_multiplier: float = 1.0
) -> Dict[str, Any]:
    """
    Рассчитывает уверенность в результате расчета (0-100%)

    Факторы уверенности:
    1. Количество аналогов (5+ = хорошо, 15+ = отлично)
    2. Качество данных (CV < 10% = отлично, < 20% = хорошо)
    3. Адаптивные коэффициенты (больше = лучше)
    4. Величина множителя (1.0 ± 0.2 = нормально)

    Args:
        comparables: Список аналогов
        data_quality: Результаты статистического анализа
        adjustments: Применённые корректировки
        final_multiplier: Итоговый множитель

    Returns:
        Dict с метриками уверенности:
            - confidence_score: оценка 0-100
            - level: уровень ('очень высокая', 'высокая', 'средняя', 'низкая', 'очень низкая')
            - reasons: список факторов влияющих на уверенность
            - details: детальная статистика

    Example:
        >>> confidence = calculate_confidence(comps, quality, adjs)
        >>> if confidence['confidence_score'] < 50:
        >>>     logger.warning("Низкая уверенность в расчете!")
    """
    confidence = 100.0
    reasons = []
    details = {}

    # ===== ФАКТОР 1: КОЛИЧЕСТВО АНАЛОГОВ =====
    count = len(comparables)
    details['comparables_count'] = count

    if count < 5:
        penalty = 30
        confidence -= penalty
        reasons.append(f"Мало аналогов ({count}) [-{penalty}%]")
    elif count < 10:
        penalty = 15
        confidence -= penalty
        reasons.append(f"Недостаточно аналогов ({count}) [-{penalty}%]")
    elif count >= 15:
        bonus = 5
        confidence += bonus
        reasons.append(f"Много аналогов ({count}) [+{bonus}%]")
    else:
        reasons.append(f"Достаточно аналогов ({count})")

    # ===== ФАКТОР 2: КАЧЕСТВО ДАННЫХ (CV) =====
    cv = data_quality.get('cv', 0)
    quality_level = data_quality.get('quality', 'unknown')
    details['cv'] = cv
    details['quality'] = quality_level

    if cv > 0.30:
        penalty = 25
        confidence -= penalty
        reasons.append(f"Высокий разброс данных (CV={cv:.1%}) [-{penalty}%]")
    elif cv > 0.20:
        penalty = 10
        confidence -= penalty
        reasons.append(f"Средний разброс данных (CV={cv:.1%}) [-{penalty}%]")
    elif cv < 0.10:
        bonus = 10
        confidence += bonus
        reasons.append(f"Низкий разброс данных (CV={cv:.1%}) [+{bonus}%]")
    else:
        reasons.append(f"Приемлемый разброс данных (CV={cv:.1%})")

    # ===== ФАКТОР 3: АДАПТИВНЫЕ КОЭФФИЦИЕНТЫ =====
    adaptive_count = sum(
        1 for adj in adjustments.values()
        if isinstance(adj, dict) and adj.get('type') == 'adaptive'
    )
    details['adaptive_coefficients'] = adaptive_count

    if adaptive_count >= 2:
        bonus = 5
        confidence += bonus
        reasons.append(f"Много адаптивных коэффициентов ({adaptive_count}) [+{bonus}%]")
    elif adaptive_count == 1:
        reasons.append(f"Использован 1 адаптивный коэффициент")
    else:
        penalty = 5
        confidence -= penalty
        reasons.append(f"Нет адаптивных коэффициентов [-{penalty}%]")

    # ===== ФАКТОР 4: ВЕЛИЧИНА МНОЖИТЕЛЯ =====
    details['final_multiplier'] = final_multiplier
    multiplier_deviation = abs(final_multiplier - 1.0)

    if multiplier_deviation > 0.30:
        penalty = 15
        confidence -= penalty
        reasons.append(f"Большое отклонение от медианы (×{final_multiplier:.2f}) [-{penalty}%]")
    elif multiplier_deviation > 0.20:
        penalty = 10
        confidence -= penalty
        reasons.append(f"Заметное отклонение от медианы (×{final_multiplier:.2f}) [-{penalty}%]")
    else:
        reasons.append(f"Множитель близок к медиане (×{final_multiplier:.2f})")

    # ===== ИТОГОВАЯ ОЦЕНКА =====
    # Ограничиваем 0-100
    confidence = max(0, min(confidence, 100))
    confidence_score = round(confidence)

    # Уровень уверенности
    level = _get_confidence_level(confidence_score)

    # Рекомендация
    if confidence_score >= 70:
        recommendation = "Результат надежен, можно использовать для принятия решений"
    elif confidence_score >= 50:
        recommendation = "Результат приемлем, но рекомендуется дополнительная проверка"
    else:
        recommendation = "Низкая надежность - рекомендуется собрать больше данных"

    return {
        'confidence_score': confidence_score,
        'level': level,
        'reasons': reasons,
        'details': details,
        'recommendation': recommendation
    }


def _get_confidence_level(score: float) -> str:
    """Уровень уверенности по оценке"""
    if score >= 85:
        return 'очень высокая'
    elif score >= 70:
        return 'высокая'
    elif score >= 50:
        return 'средняя'
    elif score >= 30:
        return 'низкая'
    else:
        return 'очень низкая'


# ═══════════════════════════════════════════════════════════════════════════
# ГЕНЕРАЦИЯ ДЕТАЛЬНОГО ОТЧЕТА
# ═══════════════════════════════════════════════════════════════════════════

def generate_detailed_report(
    target,
    comparables: List,
    fair_price_result: Dict[str, Any],
    confidence: Dict[str, Any]
) -> str:
    """
    Генерирует читаемый детальный отчет о расчете справедливой цены

    Args:
        target: Целевой объект
        comparables: Список аналогов
        fair_price_result: Результат расчета справедливой цены
        confidence: Результат расчета уверенности

    Returns:
        Форматированный текстовый отчет

    Example:
        >>> report = generate_detailed_report(target, comps, result, conf)
        >>> print(report)
    """
    lines = []

    # Заголовок
    lines.append("═" * 70)
    lines.append("ДЕТАЛЬНЫЙ РАСЧЕТ СПРАВЕДЛИВОЙ ЦЕНЫ")
    lines.append("═" * 70)
    lines.append("")

    # ===== РАЗДЕЛ 1: ДАННЫЕ ПО АНАЛОГАМ =====
    lines.append("📊 ДАННЫЕ ПО АНАЛОГАМ")
    lines.append(f"  Найдено: {len(comparables)} объявлений")

    data_quality = fair_price_result.get('data_quality', {})
    if data_quality:
        lines.append(f"  Разброс (CV): {data_quality.get('cv', 0):.1%} ({data_quality.get('quality', 'N/A')})")
        lines.append(f"  Качество данных: {data_quality.get('quality_score', 0)}/100")
    lines.append("")

    # ===== РАЗДЕЛ 2: БАЗОВАЯ ЦЕНА =====
    base_price = fair_price_result.get('base_price_per_sqm', 0)
    lines.append("💰 БАЗОВАЯ ЦЕНА (МЕДИАНА АНАЛОГОВ)")
    lines.append(f"  Медиана цены/м²: {base_price:,.0f} ₽")
    lines.append("")

    # ===== РАЗДЕЛ 3: ПРИМЕНЁННЫЕ КОЭФФИЦИЕНТЫ =====
    lines.append("📈 ПРИМЕНЁННЫЕ КОЭФФИЦИЕНТЫ")
    lines.append("")

    adjustments = fair_price_result.get('adjustments', {})

    # Группируем коэффициенты
    adaptive_adjs = []
    fixed_adjs = []
    other_adjs = []

    for key, adj in adjustments.items():
        if not isinstance(adj, dict):
            continue

        adj_type = adj.get('type', 'unknown')

        if adj_type == 'adaptive':
            adaptive_adjs.append((key, adj))
        elif adj_type == 'fixed':
            fixed_adjs.append((key, adj))
        else:
            other_adjs.append((key, adj))

    # Адаптивные (подсвечиваем)
    if adaptive_adjs:
        lines.append("  ✨ АДАПТИВНЫЕ (рассчитаны из данных):")
        for key, adj in adaptive_adjs:
            coef = adj.get('value', 1.0)
            desc = adj.get('description', key)
            change_pct = (coef - 1.0) * 100
            sign = '+' if change_pct > 0 else ''

            lines.append(f"    • {desc}: {sign}{change_pct:.1f}% (×{coef:.3f})")

            # Детали адаптивного расчета
            explanation = adj.get('explanation', {})
            if 'zone_description' in explanation:
                lines.append(f"      └─ {explanation['zone_description']}")
        lines.append("")

    # Фиксированные
    if fixed_adjs or other_adjs:
        all_fixed = fixed_adjs + other_adjs
        lines.append("  📋 СТАНДАРТНЫЕ:")
        for key, adj in all_fixed:
            coef = adj.get('value', 1.0)
            desc = adj.get('description', key)
            change_pct = (coef - 1.0) * 100
            sign = '+' if change_pct > 0 else ''

            lines.append(f"    • {desc}: {sign}{change_pct:.1f}% (×{coef:.3f})")
        lines.append("")

    # ===== РАЗДЕЛ 4: ИТОГОВЫЙ РАСЧЕТ =====
    multiplier = fair_price_result.get('final_multiplier', 1.0)
    fair_price_per_sqm = fair_price_result.get('fair_price_per_sqm', 0)
    fair_price_total = fair_price_result.get('fair_price_total', 0)
    current_price = fair_price_result.get('current_price', 0)

    lines.append("🎯 ИТОГОВЫЙ РАСЧЕТ")
    lines.append(f"  Итоговый множитель: ×{multiplier:.3f}")
    lines.append(f"  Справедливая цена/м²: {fair_price_per_sqm:,.0f} ₽")
    lines.append(f"  Справедливая цена: {fair_price_total:,.0f} ₽")

    if current_price > 0:
        price_diff = current_price - fair_price_total
        price_diff_pct = (price_diff / fair_price_total * 100) if fair_price_total > 0 else 0

        lines.append("")
        lines.append(f"  Текущая цена: {current_price:,.0f} ₽")

        if price_diff_pct > 5:
            lines.append(f"  ⚠️ ПЕРЕОЦЕНКА: +{price_diff:,.0f} ₽ ({price_diff_pct:+.1f}%)")
        elif price_diff_pct < -5:
            lines.append(f"  ✅ НЕДООЦЕНКА: {price_diff:,.0f} ₽ ({price_diff_pct:+.1f}%)")
        else:
            lines.append(f"  ✅ СПРАВЕДЛИВАЯ ЦЕНА ({price_diff_pct:+.1f}%)")

    lines.append("")

    # ===== РАЗДЕЛ 5: УВЕРЕННОСТЬ В РАСЧЕТЕ =====
    conf_score = confidence.get('confidence_score', 0)
    conf_level = confidence.get('level', 'N/A')
    recommendation = confidence.get('recommendation', '')

    lines.append("✅ УВЕРЕННОСТЬ В РАСЧЕТЕ")
    lines.append(f"  Оценка: {conf_score}/100 ({conf_level})")
    lines.append(f"  Рекомендация: {recommendation}")
    lines.append("")

    lines.append("  Факторы уверенности:")
    for reason in confidence.get('reasons', []):
        lines.append(f"    • {reason}")

    lines.append("")
    lines.append("═" * 70)

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# КРАТКИЙ ОТЧЕТ
# ═══════════════════════════════════════════════════════════════════════════

def generate_summary_report(
    fair_price_result: Dict[str, Any],
    confidence: Dict[str, Any]
) -> str:
    """
    Генерирует краткий отчет (для быстрого просмотра)

    Args:
        fair_price_result: Результат расчета
        confidence: Уверенность

    Returns:
        Краткий форматированный отчет
    """
    fair_price = fair_price_result.get('fair_price_total', 0)
    current_price = fair_price_result.get('current_price', 0)
    conf_score = confidence.get('confidence_score', 0)
    conf_level = confidence.get('level', 'N/A')

    price_diff = current_price - fair_price
    price_diff_pct = (price_diff / fair_price * 100) if fair_price > 0 else 0

    lines = [
        f"Справедливая цена: {fair_price:,.0f} ₽",
        f"Текущая цена: {current_price:,.0f} ₽",
        f"Разница: {price_diff:+,.0f} ₽ ({price_diff_pct:+.1f}%)",
        f"Уверенность: {conf_score}/100 ({conf_level})"
    ]

    return " | ".join(lines)
