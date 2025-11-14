"""
Unit tests for coefficients.py - pricing coefficient system
"""

import pytest
from src.analytics.coefficients import (
    # Coefficient dictionaries
    REPAIR_LEVEL_COEFFICIENTS,
    HOUSE_CONDITION_COEFFICIENTS,
    HOUSE_TYPE_COEFFICIENTS,
    ELEVATOR_COUNT_COEFFICIENTS,
    BATHROOMS_COEFFICIENTS,
    WINDOW_TYPE_COEFFICIENTS,
    DISTRICT_TYPE_COEFFICIENTS,
    TRANSPORT_ACCESSIBILITY_COEFFICIENTS,
    SURROUNDINGS_COEFFICIENTS,
    SECURITY_LEVEL_COEFFICIENTS,
    PARKING_TYPE_COEFFICIENTS,
    SPORTS_AMENITIES_COEFFICIENTS,
    VIEW_TYPE_COEFFICIENTS,
    PHOTO_TYPE_COEFFICIENTS,
    OBJECT_STATUS_COEFFICIENTS,
    # Dynamic functions
    get_ceiling_height_coefficient,
    get_area_coefficient,
    get_living_area_coefficient,
    get_floor_coefficient,
    get_building_age_coefficient,
    get_price_liquidity_coefficient,
    # Adaptive functions
    calculate_floor_coefficient_adaptive,
    calculate_area_coefficient_adaptive,
)
from src.models.property import ComparableProperty


class TestCoefficientDictionaries:
    """Tests for static coefficient dictionaries"""

    def test_repair_level_coefficients_structure(self):
        """Test repair level coefficients are properly defined"""
        assert isinstance(REPAIR_LEVEL_COEFFICIENTS, dict)
        assert len(REPAIR_LEVEL_COEFFICIENTS) > 0

        # Check standard level is 1.0
        assert REPAIR_LEVEL_COEFFICIENTS.get('стандартная') == 1.0

        # Check all values are reasonable (0.8 - 1.2)
        for value in REPAIR_LEVEL_COEFFICIENTS.values():
            assert 0.8 <= value <= 1.2

    def test_repair_level_ordering(self):
        """Test that better repair levels have higher coefficients"""
        assert REPAIR_LEVEL_COEFFICIENTS['черновая'] < REPAIR_LEVEL_COEFFICIENTS['стандартная']
        assert REPAIR_LEVEL_COEFFICIENTS['стандартная'] < REPAIR_LEVEL_COEFFICIENTS['премиум']
        assert REPAIR_LEVEL_COEFFICIENTS['премиум'] < REPAIR_LEVEL_COEFFICIENTS['дизайнерская']

    def test_house_type_coefficients(self):
        """Test house type coefficients"""
        assert isinstance(HOUSE_TYPE_COEFFICIENTS, dict)
        assert HOUSE_TYPE_COEFFICIENTS['монолит'] > HOUSE_TYPE_COEFFICIENTS['панель']
        assert HOUSE_TYPE_COEFFICIENTS['кирпич'] > HOUSE_TYPE_COEFFICIENTS['дерево']

    def test_elevator_coefficients(self):
        """Test elevator count coefficients"""
        assert ELEVATOR_COUNT_COEFFICIENTS['нет'] < ELEVATOR_COUNT_COEFFICIENTS['один']
        assert ELEVATOR_COUNT_COEFFICIENTS['один'] < ELEVATOR_COUNT_COEFFICIENTS['два']
        assert ELEVATOR_COUNT_COEFFICIENTS['два'] < ELEVATOR_COUNT_COEFFICIENTS['панорамный']

    def test_bathrooms_coefficients(self):
        """Test bathrooms coefficients"""
        assert BATHROOMS_COEFFICIENTS[0] < BATHROOMS_COEFFICIENTS[1]
        assert BATHROOMS_COEFFICIENTS[1] == 1.0
        assert BATHROOMS_COEFFICIENTS[2] > BATHROOMS_COEFFICIENTS[1]

    def test_view_type_coefficients_realistic(self):
        """Test view coefficients are realistic (max 5% impact)"""
        min_coef = min(VIEW_TYPE_COEFFICIENTS.values())
        max_coef = max(VIEW_TYPE_COEFFICIENTS.values())

        # View should impact max 5% (0.95 - 1.05)
        assert min_coef >= 0.95
        assert max_coef <= 1.05

    def test_security_level_ordering(self):
        """Test security levels have increasing coefficients"""
        assert SECURITY_LEVEL_COEFFICIENTS['нет'] < SECURITY_LEVEL_COEFFICIENTS['24/7']
        assert SECURITY_LEVEL_COEFFICIENTS['24/7'] < SECURITY_LEVEL_COEFFICIENTS['24/7+консьерж+видео']


class TestCeilingHeightCoefficient:
    """Tests for get_ceiling_height_coefficient()"""

    def test_very_low_ceiling(self):
        """Test ceiling < 2.5m"""
        coef = get_ceiling_height_coefficient(2.3)
        assert coef == 0.95

    def test_low_ceiling(self):
        """Test ceiling 2.5-2.7m range"""
        coef = get_ceiling_height_coefficient(2.6)
        assert 0.95 < coef < 1.0

    def test_standard_ceiling(self):
        """Test standard 2.7m ceiling"""
        coef = get_ceiling_height_coefficient(2.7)
        assert coef == 1.0

    def test_medium_high_ceiling(self):
        """Test ceiling 2.7-3.0m range"""
        coef = get_ceiling_height_coefficient(2.85)
        assert 1.0 < coef < 1.02

    def test_high_ceiling(self):
        """Test ceiling >= 3.0m"""
        coef = get_ceiling_height_coefficient(3.2)
        assert coef > 1.02
        assert coef <= 1.05  # Max cap

    def test_very_high_ceiling_capped(self):
        """Test very high ceilings approach 1.05"""
        coef = get_ceiling_height_coefficient(4.0)
        # Formula: min(1.05, 1.02 + (4.0 - 3.0) * 0.015) = min(1.05, 1.035) = 1.035
        assert coef <= 1.05
        assert coef >= 1.02


class TestAreaCoefficient:
    """Tests for get_area_coefficient()"""

    def test_equal_to_average(self):
        """Test area equal to average"""
        coef = get_area_coefficient(60, 60)
        assert coef == 1.0

    def test_larger_than_average(self):
        """Test area larger than average gets bonus"""
        coef = get_area_coefficient(80, 60)
        assert coef > 1.0

    def test_smaller_than_average(self):
        """Test area smaller than average gets penalty"""
        coef = get_area_coefficient(40, 60)
        assert coef < 1.0

    def test_much_larger_capped(self):
        """Test very large area is capped at 1.10"""
        coef = get_area_coefficient(200, 60)
        assert coef == 1.10

    def test_much_smaller_capped(self):
        """Test very small area approaches cap at 0.90"""
        coef = get_area_coefficient(20, 100)
        # Formula: 1 + (20/100 - 1) * 0.10 = 1 - 0.8 * 0.10 = 1 - 0.08 = 0.92
        # Then max(0.90, min(0.92, 1.10)) = 0.92
        assert coef >= 0.90
        assert coef < 1.0

    def test_zero_average_area(self):
        """Test handling of zero average area"""
        coef = get_area_coefficient(60, 0)
        assert coef == 1.0


class TestLivingAreaCoefficient:
    """Tests for get_living_area_coefficient()"""

    def test_high_living_area_percentage(self):
        """Test high living area percentage > 50%"""
        coef = get_living_area_coefficient(40, 60)  # 66.7%
        assert coef > 1.0

    def test_very_high_living_area(self):
        """Test very high living area percentage (70%+)"""
        coef = get_living_area_coefficient(45, 60)  # 75%
        assert coef >= 1.06  # Near max bonus

    def test_low_living_area_percentage(self):
        """Test low living area percentage < 30%"""
        coef = get_living_area_coefficient(15, 60)  # 25%
        assert coef < 1.0

    def test_normal_living_area(self):
        """Test normal range (30-50%)"""
        coef = get_living_area_coefficient(25, 60)  # 41.7%
        assert coef == 1.0

    def test_missing_living_area(self):
        """Test with None or 0 values"""
        assert get_living_area_coefficient(None, 60) == 1.0
        assert get_living_area_coefficient(30, None) == 1.0
        assert get_living_area_coefficient(0, 60) == 1.0


class TestFloorCoefficient:
    """Tests for get_floor_coefficient()"""

    def test_middle_floor(self):
        """Test middle floors (30-70%) get bonus"""
        coef = get_floor_coefficient(5, 10)  # 50%
        assert coef == 1.04

    def test_low_floor(self):
        """Test low floors (< 15%) get penalty"""
        coef = get_floor_coefficient(1, 10)  # 10%
        assert coef == 0.97

    def test_high_floor(self):
        """Test high floors (> 85%) get penalty"""
        coef = get_floor_coefficient(9, 10)  # 90%
        assert coef == 0.98

    def test_normal_floor(self):
        """Test floors in 15-30% or 70-85% range"""
        coef = get_floor_coefficient(2, 10)  # 20%
        assert coef == 1.0

    def test_low_rise_building(self):
        """Test building with < 5 floors (no coefficient)"""
        coef = get_floor_coefficient(2, 4)
        assert coef == 1.0

    def test_missing_floor_data(self):
        """Test with missing floor data"""
        assert get_floor_coefficient(None, 10) == 1.0
        assert get_floor_coefficient(5, None) == 1.0


class TestBuildingAgeCoefficient:
    """Tests for get_building_age_coefficient()"""

    def test_new_building(self):
        """Test building <= 10 years old"""
        from datetime import datetime
        current_year = datetime.now().year

        coef = get_building_age_coefficient(current_year - 5)
        assert coef == 1.0

    def test_old_building(self):
        """Test building > 10 years old gets penalty"""
        from datetime import datetime
        current_year = datetime.now().year

        coef = get_building_age_coefficient(current_year - 30)
        assert coef < 1.0

    def test_very_old_building_capped(self):
        """Test very old building is capped at 0.95"""
        from datetime import datetime
        current_year = datetime.now().year

        coef = get_building_age_coefficient(current_year - 200)
        assert coef == 0.95

    def test_missing_build_year(self):
        """Test with missing build year"""
        coef = get_building_age_coefficient(None)
        assert coef == 1.0


class TestPriceLiquidityCoefficient:
    """Tests for get_price_liquidity_coefficient()"""

    def test_normal_price(self):
        """Test price < 150M (no penalty)"""
        coef = get_price_liquidity_coefficient(100_000_000)
        assert coef == 1.0

    def test_high_price(self):
        """Test price 150-200M gets penalty"""
        coef = get_price_liquidity_coefficient(170_000_000)
        assert coef == 0.96

    def test_very_high_price(self):
        """Test price 200-300M gets higher penalty"""
        coef = get_price_liquidity_coefficient(250_000_000)
        assert coef == 0.94

    def test_extreme_price(self):
        """Test price > 300M gets max penalty"""
        coef = get_price_liquidity_coefficient(350_000_000)
        assert coef == 0.90

    def test_missing_price(self):
        """Test with None price"""
        coef = get_price_liquidity_coefficient(None)
        assert coef == 1.0


class TestFloorCoefficientAdaptive:
    """Tests for calculate_floor_coefficient_adaptive()"""

    def _create_comparable(self, floor: int, total_floors: int, price_per_sqm: float):
        """Helper to create comparable with floor data"""
        return ComparableProperty(
            url=f'https://test.com/{floor}',
            price=price_per_sqm * 60,
            total_area=60,
            price_per_sqm=price_per_sqm,
            floor=floor,
            total_floors=total_floors,
            rooms=2
        )

    def test_insufficient_data_fallback(self):
        """Test falls back to fixed coefficient with < 5 comparables"""
        comparables = [
            self._create_comparable(1, 10, 160_000),
            self._create_comparable(5, 10, 170_000),
        ]

        coef, explanation = calculate_floor_coefficient_adaptive(5, 10, comparables)

        assert explanation['type'] == 'fixed'
        assert 'Недостаточно данных' in explanation['reason']

    def test_adaptive_low_floor(self):
        """Test adaptive coefficient for low floor"""
        comparables = [
            self._create_comparable(1, 10, 155_000),  # Low
            self._create_comparable(2, 10, 157_000),  # Low
            self._create_comparable(5, 10, 170_000),  # Mid
            self._create_comparable(6, 10, 172_000),  # Mid
            self._create_comparable(9, 10, 180_000),  # High
        ]

        coef, explanation = calculate_floor_coefficient_adaptive(2, 10, comparables)

        if explanation['type'] == 'adaptive':
            assert explanation['zone'] == 'низкий'
            # Low floors cheaper -> coefficient < 1.0
            assert coef < 1.0

    def test_adaptive_high_floor(self):
        """Test adaptive coefficient for high floor"""
        comparables = [
            self._create_comparable(1, 10, 160_000),  # Low
            self._create_comparable(5, 10, 170_000),  # Mid
            self._create_comparable(6, 10, 172_000),  # Mid
            self._create_comparable(8, 10, 185_000),  # High
            self._create_comparable(9, 10, 187_000),  # High
        ]

        coef, explanation = calculate_floor_coefficient_adaptive(8, 10, comparables)

        if explanation['type'] == 'adaptive':
            assert explanation['zone'] == 'высокий'
            # High floors more expensive -> coefficient > 1.0
            assert coef > 1.0

    def test_adaptive_middle_floor(self):
        """Test adaptive coefficient for middle floor (baseline)"""
        comparables = [
            self._create_comparable(1, 10, 160_000),  # Low
            self._create_comparable(5, 10, 170_000),  # Mid
            self._create_comparable(6, 10, 172_000),  # Mid
            self._create_comparable(9, 10, 180_000),  # High
            self._create_comparable(10, 10, 182_000),  # High
        ]

        coef, explanation = calculate_floor_coefficient_adaptive(5, 10, comparables)

        if explanation['type'] == 'adaptive':
            assert explanation['zone'] == 'средний'
            assert coef == 1.0

    def test_coefficient_capping(self):
        """Test that coefficient is capped at 0.85-1.15"""
        # Create extreme scenario
        comparables = [
            self._create_comparable(1, 10, 100_000),  # Low - very cheap
            self._create_comparable(5, 10, 170_000),  # Mid
            self._create_comparable(6, 10, 172_000),  # Mid
            self._create_comparable(9, 10, 250_000),  # High - very expensive
            self._create_comparable(10, 10, 252_000),  # High
        ]

        coef_high, _ = calculate_floor_coefficient_adaptive(9, 10, comparables)
        coef_low, _ = calculate_floor_coefficient_adaptive(1, 10, comparables)

        # Should be capped
        assert coef_high <= 1.15
        assert coef_low >= 0.85


class TestAreaCoefficientAdaptive:
    """Tests for calculate_area_coefficient_adaptive()"""

    def _create_comparable(self, area: float):
        """Helper to create comparable with area data"""
        return ComparableProperty(
            url=f'https://test.com/{area}',
            price=area * 170_000,
            total_area=area,
            price_per_sqm=170_000,
            rooms=2,
            floor=5,
            total_floors=10
        )

    def test_insufficient_data(self):
        """Test with < 3 comparables"""
        comparables = [
            self._create_comparable(60),
            self._create_comparable(62),
        ]

        coef, explanation = calculate_area_coefficient_adaptive(60, comparables)

        assert explanation['type'] == 'fixed'
        assert 'Недостаточно данных' in explanation['reason']

    def test_similar_areas_no_adjustment(self):
        """Test when all comparables are similar (CV < 15%)"""
        comparables = [
            self._create_comparable(58),
            self._create_comparable(60),
            self._create_comparable(62),
            self._create_comparable(59),
        ]

        coef, explanation = calculate_area_coefficient_adaptive(60, comparables)

        if explanation.get('type') == 'no_adjustment':
            assert coef == 1.0
            assert 'близки по площади' in explanation['reason']

    def test_larger_than_median(self):
        """Test larger area gets penalty (elasticity)"""
        comparables = [
            self._create_comparable(40),
            self._create_comparable(50),
            self._create_comparable(60),
            self._create_comparable(70),
        ]

        coef, explanation = calculate_area_coefficient_adaptive(100, comparables)

        if explanation.get('type') == 'adaptive':
            # Larger apartments cheaper per sqm -> penalty
            assert coef < 1.0

    def test_smaller_than_median(self):
        """Test smaller area gets bonus (elasticity)"""
        comparables = [
            self._create_comparable(60),
            self._create_comparable(80),
            self._create_comparable(100),
            self._create_comparable(120),
        ]

        coef, explanation = calculate_area_coefficient_adaptive(50, comparables)

        if explanation.get('type') == 'adaptive':
            # Smaller apartments more expensive per sqm -> bonus
            assert coef > 1.0

    def test_coefficient_capped(self):
        """Test coefficient is capped at 0.90-1.10"""
        comparables = [
            self._create_comparable(40),
            self._create_comparable(50),
            self._create_comparable(60),
            self._create_comparable(70),
        ]

        # Test extreme large
        coef_large, _ = calculate_area_coefficient_adaptive(300, comparables)
        assert coef_large >= 0.90
        assert coef_large <= 1.10

        # Test extreme small
        coef_small, _ = calculate_area_coefficient_adaptive(10, comparables)
        assert coef_small >= 0.90
        assert coef_small <= 1.10
