"""Оценка ликвидности объекта и адаптация сценариев продажи."""

from __future__ import annotations

import math
import statistics
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - только для аннотаций
    from ..models.property import ComparableProperty, TargetProperty

SEGMENT_THRESHOLDS = (
    ("mass", 160_000),
    ("comfort", 260_000),
    ("business", 400_000),
    ("premium", math.inf),
)

SEGMENT_LABELS = {
    "mass": "массовый сегмент",
    "comfort": "комфорт",
    "business": "бизнес-класс",
    "premium": "премиум",
    "unknown": "неопределённый сегмент",
}

SEASONALITY_FACTORS = {
    1: (0.88, 1.18, "Январь и праздники традиционно замедляют рынок"),
    2: (0.94, 1.1, "Февраль ещё инерционный, сделки закрываются медленнее"),
    3: (1.02, 0.95, "Весна оживляет спрос"),
    4: (1.05, 0.9, "Апрель — пик активности после зимы"),
    5: (1.08, 0.85, "Май активно закрываются сделки перед летом"),
    6: (0.95, 1.05, "Июнь умеренный: часть покупателей уезжает"),
    7: (0.9, 1.12, "Июль отпускной, меньше просмотров"),
    8: (0.92, 1.08, "Август — вялый, многие отдыхают"),
    9: (1.07, 0.88, "Сентябрь — деловой сезон"),
    10: (1.04, 0.92, "Октябрь стабилен по спросу"),
    11: (1.0, 0.96, "Ноябрь ровный месяц"),
    12: (0.93, 1.1, "Декабрь: внимание переключается на праздники"),
}


def build_liquidity_profile(
    target: "TargetProperty", comparables: Sequence["ComparableProperty"],
) -> Dict[str, Any]:
    """Формирует профиль ликвидности на основе объекта и аналогов."""

    if target is None:
        return _default_profile()

    usable_comps = [c for c in comparables if not getattr(c, "excluded", False)]
    comp_ppsm = [c.price_per_sqm for c in usable_comps if c.price_per_sqm]
    median_ppsm = statistics.median(comp_ppsm) if comp_ppsm else None

    target_ppsm = _resolve_price_per_sqm(target)
    price_ratio = _safe_ratio(target_ppsm, median_ppsm)

    segment = _detect_segment(target_ppsm)
    notes: List[str] = []

    liquidity_score = 1.0

    dom_samples = _collect_dom_samples(usable_comps)
    dom_distribution = _distribution_stats(dom_samples)
    empirical_curve = _build_empirical_curve(dom_samples) if len(dom_samples) >= 3 else []

    discount_samples = _collect_discount_samples(usable_comps)
    discount_distribution = _distribution_stats(discount_samples)

    # Размер и комнатность
    size_factor, size_note = _size_factor(target.total_area)
    liquidity_score *= size_factor
    if size_note:
        notes.append(size_note)

    rooms_factor, rooms_note = _rooms_factor(target.rooms)
    liquidity_score *= rooms_factor
    if rooms_note:
        notes.append(rooms_note)

    # Локация
    location_factor, location_note = _location_factor(getattr(target, "district_type", None))
    liquidity_score *= location_factor
    if location_note:
        notes.append(location_note)

    # Статус строительства
    status_factor, status_note = _status_factor(getattr(target, "object_status", None))
    liquidity_score *= status_factor
    if status_note:
        notes.append(status_note)

    # Обилие аналогов
    comps_factor, comps_note = _comparables_factor(len(usable_comps))
    liquidity_score *= comps_factor
    if comps_note:
        notes.append(comps_note)

    # Переоценка
    price_factor, price_note = _price_factor(price_ratio)
    liquidity_score *= price_factor
    if price_note:
        notes.append(price_note)

    liquidity_score = _clamp(liquidity_score, 0.55, 1.45)

    probability_multiplier = _clamp(liquidity_score, 0.6, 1.4)
    time_multiplier = _clamp(1.0 / liquidity_score, 0.65, 1.6)

    pricing_bias = _pricing_bias(price_ratio)
    pressure_multiplier = _price_pressure_multiplier(price_ratio)

    base_dom = {
        "mass": 3,
        "comfort": 4,
        "business": 6,
        "premium": 8,
    }.get(segment, 4)

    if dom_distribution:
        dom_factor_prob, dom_factor_time, dom_note = _dom_factors(dom_distribution['median'], base_dom)
        probability_multiplier *= dom_factor_prob
        time_multiplier *= dom_factor_time
        if dom_note:
            notes.append(dom_note)

    seasonality = _seasonality_adjustment()
    probability_multiplier *= seasonality['probability_multiplier']
    time_multiplier *= seasonality['time_multiplier']
    if seasonality['note']:
        notes.append(seasonality['note'])

    expected_dom = max(1, round(base_dom * time_multiplier))
    if dom_distribution:
        expected_dom = max(1, round(dom_distribution['median']))

    profile = {
        "segment": segment,
        "segment_label": SEGMENT_LABELS.get(segment, SEGMENT_LABELS["unknown"]),
        "target_price_per_sqm": target_ppsm,
        "median_price_per_sqm": median_ppsm,
        "price_ratio": round(price_ratio, 2) if price_ratio else None,
        "liquidity_score": round(liquidity_score, 2),
        "probability_multiplier": round(probability_multiplier, 2),
        "time_multiplier": round(time_multiplier, 2),
        "pricing_bias": round(pricing_bias, 3),
        "price_pressure_multiplier": round(pressure_multiplier, 2),
        "expected_dom_months": expected_dom,
        "comparables_used": len(usable_comps),
        "notes": notes,
        "generated_at": "auto",
        "dom_distribution": dom_distribution,
        "dom_samples_collected": len(dom_samples),
        "discount_distribution": discount_distribution,
        "seasonality": seasonality,
        "empirical_monthly_curve": empirical_curve,
    }

    return profile


def _default_profile() -> Dict[str, Any]:
    return {
        "segment": "unknown",
        "segment_label": SEGMENT_LABELS["unknown"],
        "target_price_per_sqm": None,
        "median_price_per_sqm": None,
        "price_ratio": None,
        "liquidity_score": 1.0,
        "probability_multiplier": 1.0,
        "time_multiplier": 1.0,
        "pricing_bias": 1.0,
        "price_pressure_multiplier": 1.0,
        "expected_dom_months": 4,
        "comparables_used": 0,
        "notes": [],
        "generated_at": "auto",
        "dom_distribution": {},
        "dom_samples_collected": 0,
        "discount_distribution": {},
        "seasonality": _seasonality_adjustment(),
        "empirical_monthly_curve": [],
    }


def _resolve_price_per_sqm(target: "TargetProperty") -> Optional[float]:
    if target.price_per_sqm:
        return target.price_per_sqm
    if target.price and target.total_area:
        try:
            return target.price / target.total_area
        except ZeroDivisionError:  # pragma: no cover - защитный случай
            return None
    return None


def _safe_ratio(value: Optional[float], baseline: Optional[float]) -> Optional[float]:
    if not value or not baseline:
        return None
    try:
        return value / baseline if baseline else None
    except ZeroDivisionError:  # pragma: no cover - защитный случай
        return None


def _detect_segment(price_per_sqm: Optional[float]) -> str:
    if not price_per_sqm:
        return "unknown"
    for segment, threshold in SEGMENT_THRESHOLDS:
        if price_per_sqm <= threshold:
            return segment
    return "unknown"


def _size_factor(area: Optional[float]) -> Tuple[float, Optional[str]]:
    if not area:
        return 1.0, None
    if area < 40:
        return 1.12, "Компактная площадь ускоряет продажу"
    if area < 70:
        return 1.05, None
    if area < 120:
        return 1.0, None
    if area < 180:
        return 0.9, "Большая площадь требует более долгой экспозиции"
    return 0.8, "Очень большая площадь — нишевый спрос"


def _rooms_factor(rooms: Optional[int]) -> Tuple[float, Optional[str]]:
    if rooms is None:
        return 1.0, None
    if rooms <= 1:
        return 1.06, None
    if rooms == 2:
        return 1.02, None
    if rooms == 3:
        return 0.98, None
    if rooms >= 4:
        return 0.9, "4+ комнат продаются медленнее"
    return 1.0, None


def _location_factor(district_type: Optional[str]) -> Tuple[float, Optional[str]]:
    if not district_type:
        return 1.0, None
    mapping = {
        "center": (1.05, "Центр повышает ликвидность"),
        "near_center": (1.02, None),
        "residential": (1.0, None),
        "transitional": (0.95, "Пограничный район — средний спрос"),
        "remote": (0.88, "Удалённый район снижает скорость продаж"),
    }
    return mapping.get(district_type, (1.0, None))


def _status_factor(status: Optional[str]) -> Tuple[float, Optional[str]]:
    if not status:
        return 1.0, None
    status = status.lower()
    if "готов" in status or "отделка" in status:
        return 1.02, None
    if "стро" in status:
        return 0.9, "Стройка продаётся дольше"
    if "котл" in status or "проект" in status:
        return 0.82, "Ранние стадии строительства резко снижают ликвидность"
    return 1.0, None


def _comparables_factor(count: int) -> Tuple[float, Optional[str]]:
    if count >= 25:
        return 1.08, "Много аналогов — спрос подтверждён рынком"
    if count >= 15:
        return 1.04, None
    if count >= 8:
        return 1.0, None
    if count >= 5:
        return 0.95, "Мало аналогов — нишевый продукт"
    if count >= 3:
        return 0.9, "Слишком мало аналогов — высокая неопределённость"
    return 0.85, "Недостаточно аналогов для уверенного прогноза"


def _price_factor(price_ratio: Optional[float]) -> Tuple[float, Optional[str]]:
    if price_ratio is None:
        return 1.0, None
    if price_ratio > 1.12:
        return 0.82, "Цена заметно выше аналогов — спрос ограничен"
    if price_ratio > 1.05:
        return 0.9, "Цена выше рынка — продажа затянется"
    if price_ratio < 0.9:
        return 1.08, "Цена заметно ниже рынка — выше шанс быстрой сделки"
    if price_ratio < 0.95:
        return 1.04, None
    return 1.0, None


def _pricing_bias(price_ratio: Optional[float]) -> float:
    if price_ratio is None:
        return 1.0
    if price_ratio > 1.15:
        return 0.96
    if price_ratio > 1.08:
        return 0.985
    if price_ratio < 0.88:
        return 1.04
    if price_ratio < 0.95:
        return 1.015
    return 1.0


def _price_pressure_multiplier(price_ratio: Optional[float]) -> float:
    if price_ratio is None:
        return 1.0
    if price_ratio > 1.15:
        return 1.35
    if price_ratio > 1.08:
        return 1.15
    if price_ratio < 0.9:
        return 0.85
    if price_ratio < 0.95:
        return 0.92
    return 1.0


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


def _collect_dom_samples(comparables: Sequence["ComparableProperty"]) -> List[float]:
    samples: List[float] = []
    candidate_fields = (
        "days_on_market",
        "dom",
        "exposure_days",
        "listing_age_days",
        "time_to_sell_months",
    )
    for comp in comparables:
        months_value = None
        for field in candidate_fields:
            raw = getattr(comp, field, None)
            if raw is None:
                raw = _get_from_characteristics(comp, field)
            if raw is None:
                continue
            try:
                numeric = float(raw)
            except (TypeError, ValueError):
                continue
            if numeric <= 0:
                continue
            months_value = numeric / 30 if numeric > 24 else numeric
            break

        if months_value is None:
            continue

        samples.append(_clamp(months_value, 0.25, 36.0))
    return samples


def _collect_discount_samples(comparables: Sequence["ComparableProperty"]) -> List[float]:
    samples: List[float] = []
    candidate_fields = (
        "closing_discount_percent",
        "discount_percent",
        "bargain_percent",
        "negotiation_discount",
    )
    for comp in comparables:
        for field in candidate_fields:
            raw = getattr(comp, field, None)
            if raw is None:
                raw = _get_from_characteristics(comp, field)
            if raw is None:
                continue
            try:
                numeric = float(raw)
            except (TypeError, ValueError):
                continue
            samples.append(numeric)
            break
    return samples


def _distribution_stats(values: Sequence[float]) -> Dict[str, float]:
    if not values:
        return {}
    ordered = sorted(values)
    stats = {
        'median': round(statistics.median(ordered), 2)
    }
    if len(ordered) >= 3:
        try:
            quartiles = statistics.quantiles(ordered, n=4)
            stats['p25'] = round(quartiles[0], 2)
            stats['p75'] = round(quartiles[2], 2)
        except (statistics.StatisticsError, ValueError):
            pass
    return stats


def _build_empirical_curve(samples: Sequence[float], horizon: int = 14) -> List[float]:
    if not samples:
        return []
    ordered = sorted(samples)
    total = len(ordered)
    curve: List[float] = []
    idx = 0
    prev_cum = 0.0
    for month in range(1, horizon + 1):
        while idx < total and ordered[idx] <= month:
            idx += 1
        cum = idx / total
        monthly_prob = max(0.0, cum - prev_cum)
        curve.append(min(0.95, monthly_prob if monthly_prob > 0 else 0.02))
        prev_cum = cum
    return curve


def _dom_factors(median_dom: float, base_dom: float) -> Tuple[float, float, Optional[str]]:
    if not median_dom or base_dom <= 0:
        return 1.0, 1.0, None
    ratio = median_dom / base_dom
    prob = _clamp(1 / ratio, 0.65, 1.35)
    time = _clamp(ratio, 0.7, 1.5)
    if ratio > 1.1:
        note = f"Рынок закрывает сделки в среднем за {median_dom:.1f} мес — медленнее нормы"
    elif ratio < 0.9:
        note = f"Сделки закрываются быстрее рынка (~{median_dom:.1f} мес)"
    else:
        note = None
    return prob, time, note


def _seasonality_adjustment() -> Dict[str, Any]:
    month = datetime.utcnow().month
    probability, time, note = SEASONALITY_FACTORS.get(month, (1.0, 1.0, None))
    return {
        'month': month,
        'probability_multiplier': probability,
        'time_multiplier': time,
        'note': note,
    }


def _get_from_characteristics(obj: Any, field: str) -> Optional[Any]:
    characteristics = getattr(obj, 'characteristics', None)
    if isinstance(characteristics, dict):
        return characteristics.get(field)
    return None


__all__ = ["build_liquidity_profile"]
