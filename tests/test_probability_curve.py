import pytest

from src.analytics.analyzer import RealEstateAnalyzer


def _make_analyzer(profile):
    analyzer = RealEstateAnalyzer.__new__(RealEstateAnalyzer)
    analyzer.market_profile = profile
    return analyzer


def _extract_median_month(analyzer, curve):
    cumulative = analyzer._calculate_cumulative_probability(curve)
    if not cumulative:
        return None
    final = cumulative[-1]
    if final <= 0:
        return None
    threshold = final / 2
    for idx, value in enumerate(cumulative, start=1):
        if value >= threshold:
            return idx
    return len(curve)


def test_probability_curve_fast_segment():
    profile = {
        'expected_dom_months': 3,
        'probability_multiplier': 1.2,
        'pricing_bias': 1.0,
        'time_multiplier': 0.8,
        'price_pressure_multiplier': 1.0
    }
    analyzer = _make_analyzer(profile)

    curve = analyzer._calculate_monthly_probability(
        'fast',
        fair_price=10_000_000,
        start_price=10_200_000,
        base_probability=80
    )

    assert len(curve) == 14
    assert all(0 <= value <= 0.95 for value in curve)

    cumulative = analyzer._calculate_cumulative_probability(curve)
    assert pytest.approx(cumulative[-1], rel=1e-3) == min(0.98, 0.80)

    median_month = _extract_median_month(analyzer, curve)
    assert median_month is not None
    assert median_month <= 3  # быстрый сегмент должен успевать до DOM


def test_probability_curve_slow_segment():
    fast_profile = {
        'expected_dom_months': 3,
        'probability_multiplier': 1.1,
        'pricing_bias': 1.0,
        'time_multiplier': 0.9,
        'price_pressure_multiplier': 1.0
    }
    slow_profile = {
        'expected_dom_months': 9,
        'probability_multiplier': 0.7,
        'pricing_bias': 1.0,
        'time_multiplier': 1.3,
        'price_pressure_multiplier': 1.0
    }

    fast_analyzer = _make_analyzer(fast_profile)
    slow_analyzer = _make_analyzer(slow_profile)

    fast_curve = fast_analyzer._calculate_monthly_probability(
        'optimal',
        fair_price=12_000_000,
        start_price=12_600_000,
        base_probability=75
    )
    slow_curve = slow_analyzer._calculate_monthly_probability(
        'maximum',
        fair_price=15_000_000,
        start_price=16_500_000,
        base_probability=35
    )

    fast_median = _extract_median_month(fast_analyzer, fast_curve)
    slow_median = _extract_median_month(slow_analyzer, slow_curve)

    assert fast_median is not None and slow_median is not None
    assert slow_median > fast_median  # медленный сегмент сдвигается вправо

    slow_cumulative = slow_analyzer._calculate_cumulative_probability(slow_curve)
    assert pytest.approx(slow_cumulative[-1], rel=1e-3) == min(0.98, 0.35)
    assert slow_curve[0] < fast_curve[0]  # стартовая вероятность медленнее
