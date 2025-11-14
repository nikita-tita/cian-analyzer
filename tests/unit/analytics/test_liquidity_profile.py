"""
Unit tests for liquidity_profile.py - property liquidity assessment
"""

import pytest
from src.analytics.liquidity_profile import (
    build_liquidity_profile,
    _default_profile,
    _resolve_price_per_sqm,
    _safe_ratio,
    _detect_segment,
    _size_factor,
    _rooms_factor,
    _location_factor,
    _status_factor,
    _comparables_factor,
    _price_factor,
    _pricing_bias,
    _price_pressure_multiplier,
    _clamp,
    SEGMENT_THRESHOLDS,
    SEGMENT_LABELS,
)
from src.models.property import TargetProperty, ComparableProperty


class TestSegmentDetection:
    """Tests for segment detection and thresholds"""

    def test_segment_thresholds_definition(self):
        """Test that segment thresholds are properly defined"""
        assert len(SEGMENT_THRESHOLDS) == 4
        assert SEGMENT_THRESHOLDS[0][0] == "mass"
        assert SEGMENT_THRESHOLDS[1][0] == "comfort"
        assert SEGMENT_THRESHOLDS[2][0] == "business"
        assert SEGMENT_THRESHOLDS[3][0] == "premium"

    def test_segment_labels_definition(self):
        """Test that segment labels are properly defined"""
        assert "mass" in SEGMENT_LABELS
        assert "comfort" in SEGMENT_LABELS
        assert "business" in SEGMENT_LABELS
        assert "premium" in SEGMENT_LABELS
        assert "unknown" in SEGMENT_LABELS

    def test_detect_segment_mass(self):
        """Test mass segment detection (<= 160k)"""
        assert _detect_segment(100_000) == "mass"
        assert _detect_segment(160_000) == "mass"

    def test_detect_segment_comfort(self):
        """Test comfort segment detection (160k-260k)"""
        assert _detect_segment(200_000) == "comfort"
        assert _detect_segment(260_000) == "comfort"

    def test_detect_segment_business(self):
        """Test business segment detection (260k-400k)"""
        assert _detect_segment(300_000) == "business"
        assert _detect_segment(400_000) == "business"

    def test_detect_segment_premium(self):
        """Test premium segment detection (>400k)"""
        assert _detect_segment(500_000) == "premium"
        assert _detect_segment(1_000_000) == "premium"

    def test_detect_segment_none(self):
        """Test unknown segment for None price"""
        assert _detect_segment(None) == "unknown"

    def test_detect_segment_zero(self):
        """Test unknown segment for zero price"""
        assert _detect_segment(0) == "unknown"


class TestUtilityFunctions:
    """Tests for utility functions"""

    def test_clamp_within_bounds(self):
        """Test clamping value within bounds"""
        assert _clamp(0.8, 0.6, 1.0) == 0.8

    def test_clamp_below_minimum(self):
        """Test clamping value below minimum"""
        assert _clamp(0.4, 0.6, 1.0) == 0.6

    def test_clamp_above_maximum(self):
        """Test clamping value above maximum"""
        assert _clamp(1.5, 0.6, 1.0) == 1.0

    def test_clamp_at_boundaries(self):
        """Test clamping at exact boundaries"""
        assert _clamp(0.6, 0.6, 1.0) == 0.6
        assert _clamp(1.0, 0.6, 1.0) == 1.0

    def test_safe_ratio_valid(self):
        """Test safe ratio with valid inputs"""
        assert _safe_ratio(100, 50) == 2.0
        assert _safe_ratio(50, 100) == 0.5

    def test_safe_ratio_none_value(self):
        """Test safe ratio with None value"""
        assert _safe_ratio(None, 100) is None
        assert _safe_ratio(100, None) is None

    def test_safe_ratio_zero_baseline(self):
        """Test safe ratio with zero baseline"""
        assert _safe_ratio(100, 0) is None

    def test_safe_ratio_both_none(self):
        """Test safe ratio with both None"""
        assert _safe_ratio(None, None) is None

    def test_resolve_price_per_sqm_direct(self):
        """Test price per sqm resolution when available"""
        target = TargetProperty(
            url='https://test.com/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10,
            price_per_sqm=170_000
        )
        assert _resolve_price_per_sqm(target) == 170_000

    def test_resolve_price_per_sqm_calculated(self):
        """Test price per sqm calculation from price and area"""
        target = TargetProperty(
            url='https://test.com/1',
            price=10_000_000,
            total_area=50,
            rooms=2,
            floor=5,
            total_floors=10
        )
        result = _resolve_price_per_sqm(target)
        assert result == pytest.approx(200_000, rel=0.01)

    def test_resolve_price_per_sqm_missing_price(self):
        """Test price per sqm when price is missing"""
        target = TargetProperty(
            url='https://test.com/1',
            price=None,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10
        )
        assert _resolve_price_per_sqm(target) is None

    def test_resolve_price_per_sqm_missing_area(self):
        """Test price per sqm when area is missing"""
        target = TargetProperty(
            url='https://test.com/1',
            price=10_000_000,
            total_area=None,
            rooms=2,
            floor=5,
            total_floors=10
        )
        assert _resolve_price_per_sqm(target) is None


class TestSizeFactor:
    """Tests for _size_factor() function"""

    def test_compact_size_very_small(self):
        """Test compact size factor (<40 sqm)"""
        factor, note = _size_factor(35)
        assert factor == 1.12
        assert "Компактная площадь" in note

    def test_small_size(self):
        """Test small size factor (40-70 sqm)"""
        factor, note = _size_factor(50)
        assert factor == 1.05
        assert note is None

    def test_medium_size(self):
        """Test medium size factor (70-120 sqm)"""
        factor, note = _size_factor(90)
        assert factor == 1.0
        assert note is None

    def test_large_size(self):
        """Test large size factor (120-180 sqm)"""
        factor, note = _size_factor(150)
        assert factor == 0.9
        assert "Большая площадь" in note

    def test_very_large_size(self):
        """Test very large size factor (>180 sqm)"""
        factor, note = _size_factor(200)
        assert factor == 0.8
        assert "Очень большая площадь" in note

    def test_none_area(self):
        """Test None area"""
        factor, note = _size_factor(None)
        assert factor == 1.0
        assert note is None


class TestRoomsFactor:
    """Tests for _rooms_factor() function"""

    def test_studio_or_one_room(self):
        """Test 1-room factor"""
        factor, note = _rooms_factor(1)
        assert factor == 1.06
        assert note is None

    def test_two_rooms(self):
        """Test 2-room factor"""
        factor, note = _rooms_factor(2)
        assert factor == 1.02
        assert note is None

    def test_three_rooms(self):
        """Test 3-room factor"""
        factor, note = _rooms_factor(3)
        assert factor == 0.98
        assert note is None

    def test_four_plus_rooms(self):
        """Test 4+ rooms factor"""
        factor, note = _rooms_factor(4)
        assert factor == 0.9
        assert "4+ комнат" in note

        factor5, note5 = _rooms_factor(5)
        assert factor5 == 0.9

    def test_none_rooms(self):
        """Test None rooms"""
        factor, note = _rooms_factor(None)
        assert factor == 1.0
        assert note is None


class TestLocationFactor:
    """Tests for _location_factor() function"""

    def test_center_location(self):
        """Test center location factor"""
        factor, note = _location_factor("center")
        assert factor == 1.05
        assert "Центр повышает" in note

    def test_near_center_location(self):
        """Test near center location factor"""
        factor, note = _location_factor("near_center")
        assert factor == 1.02
        assert note is None

    def test_residential_location(self):
        """Test residential location factor"""
        factor, note = _location_factor("residential")
        assert factor == 1.0
        assert note is None

    def test_transitional_location(self):
        """Test transitional location factor"""
        factor, note = _location_factor("transitional")
        assert factor == 0.95
        assert "Пограничный район" in note

    def test_remote_location(self):
        """Test remote location factor"""
        factor, note = _location_factor("remote")
        assert factor == 0.88
        assert "Удалённый район" in note

    def test_unknown_location(self):
        """Test unknown location"""
        factor, note = _location_factor("unknown_type")
        assert factor == 1.0
        assert note is None

    def test_none_location(self):
        """Test None location"""
        factor, note = _location_factor(None)
        assert factor == 1.0
        assert note is None


class TestStatusFactor:
    """Tests for _status_factor() function"""

    def test_ready_status(self):
        """Test ready status factor"""
        factor, note = _status_factor("готов")
        assert factor == 1.02
        assert note is None

    def test_finishing_status(self):
        """Test finishing status factor"""
        factor, note = _status_factor("отделка")
        assert factor == 1.02
        assert note is None

    def test_construction_status(self):
        """Test construction status factor"""
        factor, note = _status_factor("строительство")
        assert factor == 0.9
        assert "Стройка" in note

    def test_early_stage_status(self):
        """Test early stage status factor"""
        factor1, note1 = _status_factor("котлован")
        assert factor1 == 0.82
        assert "Ранние стадии" in note1

        factor2, note2 = _status_factor("проект")
        assert factor2 == 0.82

    def test_none_status(self):
        """Test None status"""
        factor, note = _status_factor(None)
        assert factor == 1.0
        assert note is None

    def test_case_insensitive(self):
        """Test case insensitive status matching"""
        factor_lower, _ = _status_factor("готов")
        factor_upper, _ = _status_factor("ГОТОВ")
        assert factor_lower == factor_upper


class TestComparablesFactor:
    """Tests for _comparables_factor() function"""

    def test_many_comparables(self):
        """Test many comparables factor (>=25)"""
        factor, note = _comparables_factor(30)
        assert factor == 1.08
        assert "Много аналогов" in note

    def test_good_comparables(self):
        """Test good number of comparables (15-24)"""
        factor, note = _comparables_factor(20)
        assert factor == 1.04
        assert note is None

    def test_adequate_comparables(self):
        """Test adequate comparables (8-14)"""
        factor, note = _comparables_factor(10)
        assert factor == 1.0
        assert note is None

    def test_few_comparables(self):
        """Test few comparables (5-7)"""
        factor, note = _comparables_factor(6)
        assert factor == 0.95
        assert "Мало аналогов" in note

    def test_very_few_comparables(self):
        """Test very few comparables (3-4)"""
        factor, note = _comparables_factor(4)
        assert factor == 0.9
        assert "Слишком мало аналогов" in note

    def test_insufficient_comparables(self):
        """Test insufficient comparables (<3)"""
        factor, note = _comparables_factor(2)
        assert factor == 0.85
        assert "Недостаточно аналогов" in note


class TestPriceFactor:
    """Tests for _price_factor() function"""

    def test_significantly_overpriced(self):
        """Test significantly overpriced factor (>1.12)"""
        factor, note = _price_factor(1.2)
        assert factor == 0.82
        assert "заметно выше" in note.lower()

    def test_overpriced(self):
        """Test overpriced factor (1.05-1.12)"""
        factor, note = _price_factor(1.08)
        assert factor == 0.9
        assert "выше рынка" in note.lower()

    def test_significantly_underpriced(self):
        """Test significantly underpriced factor (<0.9)"""
        factor, note = _price_factor(0.85)
        assert factor == 1.08
        assert "ниже рынка" in note.lower()

    def test_underpriced(self):
        """Test underpriced factor (0.9-0.95)"""
        factor, note = _price_factor(0.92)
        assert factor == 1.04
        assert note is None

    def test_fair_price(self):
        """Test fair price factor (0.95-1.05)"""
        factor, note = _price_factor(1.0)
        assert factor == 1.0
        assert note is None

    def test_none_price_ratio(self):
        """Test None price ratio"""
        factor, note = _price_factor(None)
        assert factor == 1.0
        assert note is None


class TestPricingBias:
    """Tests for _pricing_bias() function"""

    def test_strong_overpricing_bias(self):
        """Test strong overpricing bias (>1.15)"""
        bias = _pricing_bias(1.2)
        assert bias == 0.96

    def test_moderate_overpricing_bias(self):
        """Test moderate overpricing bias (1.08-1.15)"""
        bias = _pricing_bias(1.1)
        assert bias == 0.985

    def test_strong_underpricing_bias(self):
        """Test strong underpricing bias (<0.88)"""
        bias = _pricing_bias(0.85)
        assert bias == 1.04

    def test_moderate_underpricing_bias(self):
        """Test moderate underpricing bias (0.88-0.95)"""
        bias = _pricing_bias(0.9)
        assert bias == 1.015

    def test_neutral_bias(self):
        """Test neutral bias (0.95-1.08)"""
        bias = _pricing_bias(1.0)
        assert bias == 1.0

    def test_none_bias(self):
        """Test None bias"""
        bias = _pricing_bias(None)
        assert bias == 1.0


class TestPricePressureMultiplier:
    """Tests for _price_pressure_multiplier() function"""

    def test_strong_pressure(self):
        """Test strong pressure (>1.15)"""
        multiplier = _price_pressure_multiplier(1.2)
        assert multiplier == 1.35

    def test_moderate_pressure(self):
        """Test moderate pressure (1.08-1.15)"""
        multiplier = _price_pressure_multiplier(1.1)
        assert multiplier == 1.15

    def test_strong_discount_pressure(self):
        """Test strong discount pressure (<0.9)"""
        multiplier = _price_pressure_multiplier(0.85)
        assert multiplier == 0.85

    def test_moderate_discount_pressure(self):
        """Test moderate discount pressure (0.9-0.95)"""
        multiplier = _price_pressure_multiplier(0.92)
        assert multiplier == 0.92

    def test_neutral_pressure(self):
        """Test neutral pressure (0.95-1.08)"""
        multiplier = _price_pressure_multiplier(1.0)
        assert multiplier == 1.0

    def test_none_pressure(self):
        """Test None pressure"""
        multiplier = _price_pressure_multiplier(None)
        assert multiplier == 1.0


class TestDefaultProfile:
    """Tests for _default_profile() function"""

    def test_default_profile_structure(self):
        """Test default profile structure"""
        profile = _default_profile()

        assert profile['segment'] == 'unknown'
        assert profile['segment_label'] == SEGMENT_LABELS['unknown']
        assert profile['target_price_per_sqm'] is None
        assert profile['median_price_per_sqm'] is None
        assert profile['price_ratio'] is None
        assert profile['liquidity_score'] == 1.0
        assert profile['probability_multiplier'] == 1.0
        assert profile['time_multiplier'] == 1.0
        assert profile['pricing_bias'] == 1.0
        assert profile['price_pressure_multiplier'] == 1.0
        assert profile['expected_dom_months'] == 4
        assert profile['comparables_used'] == 0
        assert profile['notes'] == []
        assert 'generated_at' in profile


class TestBuildLiquidityProfile:
    """Tests for build_liquidity_profile() main function"""

    def _create_target(self, **kwargs):
        """Helper to create target property"""
        defaults = {
            'url': 'https://test.com/target/1',
            'price': 10_000_000,
            'total_area': 60,
            'rooms': 2,
            'floor': 5,
            'total_floors': 10,
        }
        defaults.update(kwargs)
        return TargetProperty(**defaults)

    def _create_comparable(self, index=1, price_per_sqm=170_000):
        """Helper to create comparable property"""
        return ComparableProperty(
            url=f'https://test.com/comp/{index}',
            price=10_000_000,
            total_area=60,
            price_per_sqm=price_per_sqm,
            rooms=2,
            floor=5,
            total_floors=10
        )

    def test_none_target(self):
        """Test with None target"""
        profile = build_liquidity_profile(None, [])
        assert profile == _default_profile()

    def test_basic_profile(self):
        """Test basic profile generation"""
        target = self._create_target()
        comparables = [self._create_comparable(i) for i in range(10)]

        profile = build_liquidity_profile(target, comparables)

        assert 'segment' in profile
        assert 'liquidity_score' in profile
        assert 'probability_multiplier' in profile
        assert 'time_multiplier' in profile
        assert 'expected_dom_months' in profile
        assert 'comparables_used' in profile
        assert 'notes' in profile

    def test_segment_detection_mass(self):
        """Test mass segment detection"""
        target = self._create_target(price_per_sqm=150_000)
        comparables = [self._create_comparable(i, 150_000) for i in range(5)]

        profile = build_liquidity_profile(target, comparables)

        assert profile['segment'] == 'mass'
        assert profile['expected_dom_months'] == 3  # base_dom for mass

    def test_segment_detection_comfort(self):
        """Test comfort segment detection"""
        target = self._create_target(price_per_sqm=200_000)
        comparables = [self._create_comparable(i, 200_000) for i in range(5)]

        profile = build_liquidity_profile(target, comparables)

        assert profile['segment'] == 'comfort'

    def test_segment_detection_business(self):
        """Test business segment detection"""
        target = self._create_target(price_per_sqm=300_000)
        comparables = [self._create_comparable(i, 300_000) for i in range(5)]

        profile = build_liquidity_profile(target, comparables)

        assert profile['segment'] == 'business'

    def test_segment_detection_premium(self):
        """Test premium segment detection"""
        target = self._create_target(price_per_sqm=500_000)
        comparables = [self._create_comparable(i, 500_000) for i in range(5)]

        profile = build_liquidity_profile(target, comparables)

        assert profile['segment'] == 'premium'

    def test_price_ratio_calculation(self):
        """Test price ratio calculation"""
        target = self._create_target(price_per_sqm=200_000)
        comparables = [self._create_comparable(i, 170_000) for i in range(5)]

        profile = build_liquidity_profile(target, comparables)

        # 200k / 170k ≈ 1.18
        assert profile['price_ratio'] == pytest.approx(1.18, abs=0.01)

    def test_excluded_comparables(self):
        """Test that excluded comparables are filtered out"""
        target = self._create_target()
        comparables = [self._create_comparable(i) for i in range(10)]
        # Mark some as excluded
        comparables[0].excluded = True
        comparables[1].excluded = True

        profile = build_liquidity_profile(target, comparables)

        assert profile['comparables_used'] == 8  # 10 - 2 excluded

    def test_liquidity_score_clamped(self):
        """Test that liquidity score is clamped to 0.55-1.45"""
        target = self._create_target(total_area=300, rooms=5)  # Large, should decrease score
        comparables = [self._create_comparable(i, 100_000) for i in range(2)]  # Few comparables

        profile = build_liquidity_profile(target, comparables)

        assert 0.55 <= profile['liquidity_score'] <= 1.45

    def test_multipliers_clamped(self):
        """Test that multipliers are clamped"""
        target = self._create_target()
        comparables = [self._create_comparable(i) for i in range(10)]

        profile = build_liquidity_profile(target, comparables)

        # Probability multiplier: 0.6-1.4
        assert 0.6 <= profile['probability_multiplier'] <= 1.4
        # Time multiplier: 0.65-1.6
        assert 0.65 <= profile['time_multiplier'] <= 1.6

    def test_compact_apartment_note(self):
        """Test compact apartment note generation"""
        target = self._create_target(total_area=35)  # <40
        comparables = [self._create_comparable(i) for i in range(5)]

        profile = build_liquidity_profile(target, comparables)

        assert any("Компактная площадь" in note for note in profile['notes'])

    def test_large_apartment_note(self):
        """Test large apartment note generation"""
        target = self._create_target(total_area=150)  # 120-180
        comparables = [self._create_comparable(i) for i in range(5)]

        profile = build_liquidity_profile(target, comparables)

        assert any("Большая площадь" in note for note in profile['notes'])

    def test_many_rooms_note(self):
        """Test many rooms note generation"""
        target = self._create_target(rooms=4)
        comparables = [self._create_comparable(i) for i in range(5)]

        profile = build_liquidity_profile(target, comparables)

        assert any("4+ комнат" in note for note in profile['notes'])

    def test_few_comparables_note(self):
        """Test few comparables note generation"""
        target = self._create_target()
        comparables = [self._create_comparable(i) for i in range(4)]  # <5

        profile = build_liquidity_profile(target, comparables)

        assert any("аналогов" in note.lower() for note in profile['notes'])

    def test_overpriced_note(self):
        """Test overpriced note generation"""
        target = self._create_target(price_per_sqm=200_000)
        comparables = [self._create_comparable(i, 170_000) for i in range(5)]

        profile = build_liquidity_profile(target, comparables)

        # price_ratio = 1.18 > 1.05, should have "выше" note
        assert any("выше" in note.lower() for note in profile['notes'])

    def test_underpriced_note(self):
        """Test underpriced note generation"""
        target = self._create_target(price_per_sqm=150_000)
        comparables = [self._create_comparable(i, 180_000) for i in range(5)]

        profile = build_liquidity_profile(target, comparables)

        # price_ratio = 0.83 < 0.9, should have "ниже" note
        assert any("ниже" in note.lower() for note in profile['notes'])

    def test_median_calculation(self):
        """Test median price per sqm calculation"""
        target = self._create_target()
        comparables = [
            self._create_comparable(1, 160_000),
            self._create_comparable(2, 170_000),
            self._create_comparable(3, 180_000),
            self._create_comparable(4, 190_000),
            self._create_comparable(5, 200_000),
        ]

        profile = build_liquidity_profile(target, comparables)

        assert profile['median_price_per_sqm'] == 180_000

    def test_empty_comparables(self):
        """Test with empty comparables list"""
        target = self._create_target()

        profile = build_liquidity_profile(target, [])

        assert profile['comparables_used'] == 0
        assert profile['median_price_per_sqm'] is None
        assert profile['price_ratio'] is None

    def test_dom_calculation_varies_by_segment(self):
        """Test that DOM varies by segment"""
        comparables = [self._create_comparable(i, 150_000) for i in range(10)]

        # Mass segment
        target_mass = self._create_target(price_per_sqm=150_000)
        profile_mass = build_liquidity_profile(target_mass, comparables)

        # Premium segment
        target_premium = self._create_target(price_per_sqm=500_000)
        comps_premium = [self._create_comparable(i, 500_000) for i in range(10)]
        profile_premium = build_liquidity_profile(target_premium, comps_premium)

        # Premium should have higher base DOM
        assert profile_premium['expected_dom_months'] >= profile_mass['expected_dom_months']
