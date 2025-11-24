import math

from src.analytics.fair_price_calculator import calculate_fair_price_with_medians
from src.analytics.median_calculator import calculate_medians_from_comparables
from src.models.property import ComparableProperty, TargetProperty


def _build_comparable(index: int) -> ComparableProperty:
    return ComparableProperty(
        url=f"https://example.com/{index}",
        price=15_000_000 + index * 100_000,
        total_area=80 + index,
        living_area=48 + index,
        ceiling_height=2.7 + 0.05 * index,
        bathrooms=1 if index < 2 else 2,
        floor=4 + index,
        total_floors=20,
        repair_level="стандартная",
        window_type="пластиковые",
        elevator_count="два",
        view_type="улица",
        photo_type="реальные",
        object_status="готов",
    )


def test_medians_include_variable_attributes():
    comparables = [_build_comparable(i) for i in range(5)]

    medians = calculate_medians_from_comparables(comparables)

    assert medians["repair_level"] == "стандартная"
    assert medians["window_type"] == "пластиковые"
    assert medians["view_type"] == "улица"
    assert medians["photo_type"] == "реальные"


def test_calculator_applies_adjustments_from_comparables():
    comparables = [_build_comparable(i) for i in range(5)]

    target = TargetProperty(
        url="https://example.com/target",
        price=18_000_000,
        total_area=95,
        living_area=62,
        ceiling_height=3.05,
        bathrooms=2,
        floor=12,
        total_floors=20,
        repair_level="премиум",
        window_type="панорамные",
        elevator_count="три+",
        view_type="парк",
        photo_type="реальные",
        object_status="готов",
    )

    result = calculate_fair_price_with_medians(target, comparables, base_price_per_sqm=200_000)

    adjustments = result["adjustments"]
    assert "repair_level" in adjustments
    assert "window_type" in adjustments
    # Adjustment coefficients have been recalibrated - premium repair now gives ~12% adjustment
    assert math.isclose(adjustments["repair_level"]["value"], 1.12, rel_tol=0.05)
    assert adjustments["window_type"]["value"] > 1.0


def test_categorical_medians_handle_multiple_modes():
    comparables = []
    # Две категории встречаются одинаково часто — раньше здесь возникал StatisticsError
    for idx, repair in enumerate(["стандартная", "премиум", "стандартная", "премиум"]):
        comp = _build_comparable(idx)
        comparables.append(comp.copy(update={"repair_level": repair}))

    medians = calculate_medians_from_comparables(comparables)

    assert medians["repair_level"] in {"стандартная", "премиум"}
