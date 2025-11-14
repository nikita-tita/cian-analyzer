"""Расчёт доверительных интервалов цены на основе аналогов."""

from __future__ import annotations

import math
import statistics
from typing import Any, Dict, List, Sequence, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - только для типизации
    from ..models.property import TargetProperty, ComparableProperty

Z_SCORE_80 = 1.281  # 80% доверительный интервал
Z_SCORE_95 = 1.960  # 95% доверительный интервал


def calculate_price_confidence(
    target: "TargetProperty", comparables: Sequence["ComparableProperty"]
) -> Dict[str, Any]:
    """Строит доверительные интервалы цены продажи.

    Интервалы рассчитываются по цене за квадратный метр (mean ± z * SE)
    и затем переводятся в абсолютную стоимость, учитывая площадь объекта.
    Если данных недостаточно, функция возвращает пояснение и безопасные значения.
    """

    base_result: Dict[str, Any] = {
        "sample_size": 0,
        "mean_price": None,
        "median_price": None,
        "ci80": {},
        "ci95": {},
        "coefficient_of_variation": None,
        "volatility_bucket": "unknown",
        "note": "Недостаточно данных для расчёта доверительного интервала.",
        "inputs": {
            "mean_price_per_sqm": None,
            "median_price_per_sqm": None,
            "stdev_price_per_sqm": None,
        },
    }

    if not target or not comparables:
        base_result["note"] = "Нет объекта или аналогов для расчёта."
        return base_result

    area = getattr(target, "total_area", None)
    if not area or area <= 0:
        base_result["note"] = "Неизвестна площадь объекта — нечего умножать на кв.метр."
        return base_result

    usable_prices: List[float] = [c.price_per_sqm for c in comparables if c.price_per_sqm]
    sample_size = len(usable_prices)
    base_result["sample_size"] = sample_size

    if sample_size == 0:
        base_result["note"] = "Ни один аналог не содержит цены за м² — интервал не построен."
        return base_result

    mean_ppsm = statistics.mean(usable_prices)
    median_ppsm = statistics.median(usable_prices)
    base_result["inputs"]["mean_price_per_sqm"] = mean_ppsm
    base_result["inputs"]["median_price_per_sqm"] = median_ppsm

    convert = lambda price_per_sqm: max(0.0, price_per_sqm * area)

    mean_price = convert(mean_ppsm)
    median_price = convert(median_ppsm)
    base_result["mean_price"] = mean_price
    base_result["median_price"] = median_price

    if sample_size == 1:
        base_result["inputs"]["stdev_price_per_sqm"] = 0.0
        base_result["ci80"] = {"lower": mean_price, "upper": mean_price, "width_percent": 0.0}
        base_result["ci95"] = base_result["ci80"]
        base_result["coefficient_of_variation"] = 0.0
        base_result["volatility_bucket"] = "single_point"
        base_result["note"] = (
            "Есть только один аналог с ценой за кв.м — доверительный интервал "
            "совпадает с оценкой. Добавьте больше данных для репрезентативности."
        )
        return base_result

    stdev_ppsm = statistics.stdev(usable_prices)
    base_result["inputs"]["stdev_price_per_sqm"] = stdev_ppsm
    se_ppsm = stdev_ppsm / math.sqrt(sample_size)

    cv = (stdev_ppsm / mean_ppsm) if mean_ppsm else None
    base_result["coefficient_of_variation"] = round(cv, 3) if cv is not None else None

    bucket, bucket_note = _volatility_bucket(cv)
    base_result["volatility_bucket"] = bucket

    def interval(z_score: float) -> Dict[str, Any]:
        lower_ppsm = max(0.0, mean_ppsm - z_score * se_ppsm)
        upper_ppsm = max(0.0, mean_ppsm + z_score * se_ppsm)
        lower = convert(lower_ppsm)
        upper = convert(upper_ppsm)
        width_percent = ((upper - lower) / mean_price * 100.0) if mean_price else None
        return {
            "lower": round(lower),
            "upper": round(upper),
            "width_percent": round(width_percent, 1) if width_percent is not None else None,
        }

    base_result["ci80"] = interval(Z_SCORE_80)
    base_result["ci95"] = interval(Z_SCORE_95)

    note_parts = [
        f"Использовано {sample_size} аналогов (медиана {median_ppsm:,.0f} ₽/м²).",
    ]
    if bucket_note:
        note_parts.append(bucket_note)
    if sample_size < 5:
        note_parts.append("Мало наблюдений — интервал расширен и требует осторожности.")

    base_result["note"] = " ".join(note_parts)
    return base_result


def _volatility_bucket(cv: float | None) -> tuple[str, str]:
    if cv is None:
        return "unknown", "Не удалось оценить разброс цен."
    if cv < 0.08:
        return "very_stable", f"Разброс цен минимальный (CV {cv:.1%}) — рынок однородный."
    if cv < 0.15:
        return "stable", f"Разброс умеренный (CV {cv:.1%}) — данные надёжные."
    if cv < 0.25:
        return "volatile", f"Разброс повышенный (CV {cv:.1%}) — рынок разнородный."
    return "highly_volatile", f"Разброс высокий (CV {cv:.1%}) — результат следует интерпретировать осторожно."


__all__ = ["calculate_price_confidence"]
