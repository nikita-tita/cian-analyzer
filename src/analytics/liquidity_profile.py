"""Оценка ликвидности объекта и адаптация сценариев продажи."""

from __future__ import annotations

import math
import statistics
from typing import Any, Dict, List, Optional, Sequence, Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - только для аннотаций
    from ..models.property import ComparableProperty, TargetProperty

SEGMENT_THRESHOLDS = (
    ("mass", 160_000),
    ("comfort", 400_000),  # Extended from 260K to match current market (160K-400K)
    ("business", 600_000),  # Business class now 400K-600K (was 260K-400K)
    ("premium", math.inf),
)

SEGMENT_LABELS = {
    "mass": "массовый сегмент",
    "comfort": "комфорт",
    "business": "бизнес-класс",
    "premium": "премиум",
    "unknown": "неопределённый сегмент",
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
    expected_dom = max(1, round(base_dom * time_multiplier))

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


__all__ = ["build_liquidity_profile"]
