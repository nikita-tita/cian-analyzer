"""
Unit tests for fair_price_calculator.py - fair price calculation system
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.analytics.fair_price_calculator import (
    calculate_fair_price_with_medians,
    _fallback_calculation,
)
from src.models.property import TargetProperty, ComparableProperty


class TestCalculateFairPriceWithMedians:
    """Tests for calculate_fair_price_with_medians() function"""

    def _create_target(self):
        """Helper to create a target property"""
        return TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10,
            repair_level='стандартная',
            ceiling_height=2.7,
            bathrooms=1,
            window_type='пластиковые',
            view_type='дом',
            photo_type='реальные',
            object_status='готов',
            build_year=2020
        )

    def _create_comparables(self, count=10):
        """Helper to create comparables list"""
        comparables = []
        for i in range(count):
            comp = ComparableProperty(
                url=f'https://test.com/comp/{i}',
                price=10_000_000 + (i * 100_000),
                total_area=60 + (i % 5),
                price_per_sqm=165_000 + (i * 1000),
                rooms=2,
                floor=3 + (i % 7),
                total_floors=10,
                repair_level='стандартная',
                ceiling_height=2.7,
                bathrooms=1,
                window_type='пластиковые',
                view_type='дом',
                photo_type='реальные',
                object_status='готов',
                build_year=2018 + (i % 3)
            )
            comparables.append(comp)
        return comparables

    @patch('src.analytics.fair_price_calculator.calculate_medians_from_comparables')
    @patch('src.analytics.fair_price_calculator.compare_target_with_medians')
    @patch('src.analytics.fair_price_calculator._apply_repair_adjustment_additive')
    @patch('src.analytics.fair_price_calculator._apply_apartment_features_adjustments_additive')
    @patch('src.analytics.fair_price_calculator._apply_position_adjustments_additive')
    @patch('src.analytics.fair_price_calculator._apply_view_adjustments_additive')
    @patch('src.analytics.fair_price_calculator._apply_risk_adjustments_additive')
    @patch('src.analytics.statistical_analysis.calculate_data_quality')
    @patch('src.analytics.fair_price_calculator.calculate_confidence')
    @patch('src.analytics.fair_price_calculator.generate_detailed_report')
    @patch('src.analytics.fair_price_calculator.generate_summary_report')
    def test_basic_calculation_median(
        self, mock_summary, mock_detailed, mock_confidence,
        mock_quality, mock_risk, mock_view, mock_position,
        mock_apartment, mock_repair, mock_compare, mock_medians
    ):
        """Test basic fair price calculation with median method"""
        target = self._create_target()
        comparables = self._create_comparables()
        base_price = 170_000

        # Mock medians calculation
        mock_medians.return_value = {
            'repair_level': 'стандартная',
            'ceiling_height': 2.7,
            'total_area': 60,
            'floor': 5
        }

        # Mock comparison
        mock_compare.return_value = {
            'repair_level': {'equals_median': True},
            'ceiling_height': {'equals_median': True}
        }

        # Mock adjustment functions to return unchanged estimates
        mock_repair.return_value = ([170_000], {})
        mock_apartment.return_value = ([170_000, 172_000], {'area': {'value': 1.0}})
        mock_position.return_value = ([170_000, 172_000, 171_000], {'floor': {'value': 1.0}})
        mock_view.return_value = ([170_000, 172_000, 171_000, 169_000], {'view': {'value': 1.0}})
        mock_risk.return_value = ([170_000, 172_000, 171_000, 169_000, 170_500], {'status': {'value': 1.0}})

        # Mock quality and confidence
        mock_quality.return_value = {'quality': 'high', 'cv': 0.1, 'quality_score': 85}
        mock_confidence.return_value = {'confidence_score': 80, 'level': 'high'}
        mock_detailed.return_value = "Detailed report"
        mock_summary.return_value = "Summary report"

        result = calculate_fair_price_with_medians(target, comparables, base_price, method='median')

        # Verify structure
        assert isinstance(result, dict)
        assert 'fair_price_per_sqm' in result
        assert 'fair_price_total' in result
        assert 'price_diff_percent' in result
        assert 'is_overpriced' in result
        assert 'is_underpriced' in result
        assert 'is_fair' in result
        assert 'confidence' in result
        assert 'data_quality' in result

    @patch('src.analytics.fair_price_calculator.calculate_medians_from_comparables')
    @patch('src.analytics.fair_price_calculator.compare_target_with_medians')
    @patch('src.analytics.fair_price_calculator._apply_repair_adjustment_additive')
    @patch('src.analytics.fair_price_calculator._apply_apartment_features_adjustments_additive')
    @patch('src.analytics.fair_price_calculator._apply_position_adjustments_additive')
    @patch('src.analytics.fair_price_calculator._apply_view_adjustments_additive')
    @patch('src.analytics.fair_price_calculator._apply_risk_adjustments_additive')
    @patch('src.analytics.statistical_analysis.calculate_data_quality')
    @patch('src.analytics.fair_price_calculator.calculate_confidence')
    @patch('src.analytics.fair_price_calculator.generate_detailed_report')
    @patch('src.analytics.fair_price_calculator.generate_summary_report')
    def test_basic_calculation_mean(
        self, mock_summary, mock_detailed, mock_confidence,
        mock_quality, mock_risk, mock_view, mock_position,
        mock_apartment, mock_repair, mock_compare, mock_medians
    ):
        """Test basic fair price calculation with mean method"""
        target = self._create_target()
        comparables = self._create_comparables()
        base_price = 170_000

        # Setup mocks
        mock_medians.return_value = {'repair_level': 'стандартная'}
        mock_compare.return_value = {'repair_level': {'equals_median': True}}
        mock_repair.return_value = ([170_000, 172_000], {})
        mock_apartment.return_value = ([170_000, 172_000], {})
        mock_position.return_value = ([170_000, 172_000], {})
        mock_view.return_value = ([170_000, 172_000], {})
        mock_risk.return_value = ([170_000, 172_000], {})
        mock_quality.return_value = {'quality': 'medium', 'cv': 0.15}
        mock_confidence.return_value = {'confidence_score': 75}
        mock_detailed.return_value = "Report"
        mock_summary.return_value = "Summary"

        result = calculate_fair_price_with_medians(target, comparables, base_price, method='mean')

        assert result['method'] == 'mean'
        # Mean of [170000, 172000] = 171000
        assert result['fair_price_per_sqm'] == 171_000

    @patch('src.analytics.fair_price_calculator.calculate_medians_from_comparables')
    def test_fallback_when_no_medians(self, mock_medians):
        """Test fallback calculation when medians cannot be calculated"""
        target = self._create_target()
        comparables = self._create_comparables()
        base_price = 170_000

        # Mock medians to return empty
        mock_medians.return_value = {}

        result = calculate_fair_price_with_medians(target, comparables, base_price)

        # Should use fallback
        assert result['method'] == 'median_fallback'
        assert 'fair_price_per_sqm' in result
        assert 'fair_price_total' in result

    @patch('src.analytics.fair_price_calculator.calculate_medians_from_comparables')
    @patch('src.analytics.fair_price_calculator.compare_target_with_medians')
    @patch('src.analytics.fair_price_calculator._apply_repair_adjustment_additive')
    @patch('src.analytics.fair_price_calculator._apply_apartment_features_adjustments_additive')
    @patch('src.analytics.fair_price_calculator._apply_position_adjustments_additive')
    @patch('src.analytics.fair_price_calculator._apply_view_adjustments_additive')
    @patch('src.analytics.fair_price_calculator._apply_risk_adjustments_additive')
    @patch('src.analytics.statistical_analysis.calculate_data_quality')
    @patch('src.analytics.fair_price_calculator.calculate_confidence')
    @patch('src.analytics.fair_price_calculator.generate_detailed_report')
    @patch('src.analytics.fair_price_calculator.generate_summary_report')
    def test_no_price_estimates(
        self, mock_summary, mock_detailed, mock_confidence,
        mock_quality, mock_risk, mock_view, mock_position,
        mock_apartment, mock_repair, mock_compare, mock_medians
    ):
        """Test when no price estimates are generated"""
        target = self._create_target()
        comparables = self._create_comparables()
        base_price = 170_000

        # Setup mocks with no adjustments
        mock_medians.return_value = {'repair_level': 'стандартная'}
        mock_compare.return_value = {}
        mock_repair.return_value = ([], {})  # No estimates
        mock_apartment.return_value = ([], {})
        mock_position.return_value = ([], {})
        mock_view.return_value = ([], {})
        mock_risk.return_value = ([], {})
        mock_quality.return_value = {'quality': 'low', 'cv': 0.2}
        mock_confidence.return_value = {'confidence_score': 50}
        mock_detailed.return_value = "Report"
        mock_summary.return_value = "Summary"

        result = calculate_fair_price_with_medians(target, comparables, base_price)

        # Should use base price when no estimates
        assert result['fair_price_per_sqm'] == base_price

    @patch('src.analytics.fair_price_calculator.calculate_medians_from_comparables')
    @patch('src.analytics.fair_price_calculator.compare_target_with_medians')
    @patch('src.analytics.fair_price_calculator._apply_repair_adjustment_additive')
    @patch('src.analytics.fair_price_calculator._apply_apartment_features_adjustments_additive')
    @patch('src.analytics.fair_price_calculator._apply_position_adjustments_additive')
    @patch('src.analytics.fair_price_calculator._apply_view_adjustments_additive')
    @patch('src.analytics.fair_price_calculator._apply_risk_adjustments_additive')
    @patch('src.analytics.statistical_analysis.calculate_data_quality')
    @patch('src.analytics.fair_price_calculator.calculate_confidence')
    @patch('src.analytics.fair_price_calculator.generate_detailed_report')
    @patch('src.analytics.fair_price_calculator.generate_summary_report')
    def test_overpriced_detection(
        self, mock_summary, mock_detailed, mock_confidence,
        mock_quality, mock_risk, mock_view, mock_position,
        mock_apartment, mock_repair, mock_compare, mock_medians
    ):
        """Test detection of overpriced property"""
        target = self._create_target()
        target.price = 15_000_000  # Much higher than fair
        comparables = self._create_comparables()
        base_price = 170_000  # Fair price will be ~170k * 60 = 10.2M

        # Setup mocks
        mock_medians.return_value = {'repair_level': 'стандартная'}
        mock_compare.return_value = {}
        mock_repair.return_value = ([170_000], {})
        mock_apartment.return_value = ([170_000], {})
        mock_position.return_value = ([170_000], {})
        mock_view.return_value = ([170_000], {})
        mock_risk.return_value = ([170_000], {})
        mock_quality.return_value = {'quality': 'medium', 'cv': 0.15}
        mock_confidence.return_value = {'confidence_score': 70}
        mock_detailed.return_value = "Report"
        mock_summary.return_value = "Summary"

        result = calculate_fair_price_with_medians(target, comparables, base_price)

        assert result['is_overpriced'] is True
        assert result['price_diff_percent'] > 5

    @patch('src.analytics.fair_price_calculator.calculate_medians_from_comparables')
    @patch('src.analytics.fair_price_calculator.compare_target_with_medians')
    @patch('src.analytics.fair_price_calculator._apply_repair_adjustment_additive')
    @patch('src.analytics.fair_price_calculator._apply_apartment_features_adjustments_additive')
    @patch('src.analytics.fair_price_calculator._apply_position_adjustments_additive')
    @patch('src.analytics.fair_price_calculator._apply_view_adjustments_additive')
    @patch('src.analytics.fair_price_calculator._apply_risk_adjustments_additive')
    @patch('src.analytics.statistical_analysis.calculate_data_quality')
    @patch('src.analytics.fair_price_calculator.calculate_confidence')
    @patch('src.analytics.fair_price_calculator.generate_detailed_report')
    @patch('src.analytics.fair_price_calculator.generate_summary_report')
    def test_underpriced_detection(
        self, mock_summary, mock_detailed, mock_confidence,
        mock_quality, mock_risk, mock_view, mock_position,
        mock_apartment, mock_repair, mock_compare, mock_medians
    ):
        """Test detection of underpriced property"""
        target = self._create_target()
        target.price = 7_000_000  # Much lower than fair
        comparables = self._create_comparables()
        base_price = 170_000

        # Setup mocks
        mock_medians.return_value = {'repair_level': 'стандартная'}
        mock_compare.return_value = {}
        mock_repair.return_value = ([170_000], {})
        mock_apartment.return_value = ([170_000], {})
        mock_position.return_value = ([170_000], {})
        mock_view.return_value = ([170_000], {})
        mock_risk.return_value = ([170_000], {})
        mock_quality.return_value = {'quality': 'medium', 'cv': 0.15}
        mock_confidence.return_value = {'confidence_score': 70}
        mock_detailed.return_value = "Report"
        mock_summary.return_value = "Summary"

        result = calculate_fair_price_with_medians(target, comparables, base_price)

        assert result['is_underpriced'] is True
        assert result['price_diff_percent'] < -5

    @patch('src.analytics.fair_price_calculator.calculate_medians_from_comparables')
    @patch('src.analytics.fair_price_calculator.compare_target_with_medians')
    @patch('src.analytics.fair_price_calculator._apply_repair_adjustment_additive')
    @patch('src.analytics.fair_price_calculator._apply_apartment_features_adjustments_additive')
    @patch('src.analytics.fair_price_calculator._apply_position_adjustments_additive')
    @patch('src.analytics.fair_price_calculator._apply_view_adjustments_additive')
    @patch('src.analytics.fair_price_calculator._apply_risk_adjustments_additive')
    @patch('src.analytics.statistical_analysis.calculate_data_quality')
    @patch('src.analytics.fair_price_calculator.calculate_confidence')
    @patch('src.analytics.fair_price_calculator.generate_detailed_report')
    @patch('src.analytics.fair_price_calculator.generate_summary_report')
    def test_fair_price_detection(
        self, mock_summary, mock_detailed, mock_confidence,
        mock_quality, mock_risk, mock_view, mock_position,
        mock_apartment, mock_repair, mock_compare, mock_medians
    ):
        """Test detection of fairly priced property"""
        target = self._create_target()
        target.price = 10_200_000  # Close to fair
        comparables = self._create_comparables()
        base_price = 170_000

        # Setup mocks
        mock_medians.return_value = {'repair_level': 'стандартная'}
        mock_compare.return_value = {}
        mock_repair.return_value = ([170_000], {})
        mock_apartment.return_value = ([170_000], {})
        mock_position.return_value = ([170_000], {})
        mock_view.return_value = ([170_000], {})
        mock_risk.return_value = ([170_000], {})
        mock_quality.return_value = {'quality': 'high', 'cv': 0.1}
        mock_confidence.return_value = {'confidence_score': 85}
        mock_detailed.return_value = "Report"
        mock_summary.return_value = "Summary"

        result = calculate_fair_price_with_medians(target, comparables, base_price)

        assert result['is_fair'] is True
        assert -5 <= result['price_diff_percent'] <= 5


class TestFallbackCalculation:
    """Tests for _fallback_calculation() function"""

    def _create_target(self):
        """Helper to create a target property"""
        return TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10,
            repair_level='премиум'
        )

    def test_fallback_basic(self):
        """Test basic fallback calculation"""
        target = self._create_target()
        base_price = 170_000

        result = _fallback_calculation(target, base_price, 'median')

        assert isinstance(result, dict)
        assert 'base_price_per_sqm' in result
        assert 'fair_price_per_sqm' in result
        assert 'fair_price_total' in result
        assert 'method' in result
        assert result['method'] == 'median_fallback'

    def test_fallback_with_repair_coefficient(self):
        """Test fallback applies repair coefficient"""
        target = self._create_target()
        target.repair_level = 'премиум'  # Should have coefficient > 1.0
        base_price = 170_000

        result = _fallback_calculation(target, base_price, 'median')

        # Premium repair should increase price
        assert result['fair_price_per_sqm'] > base_price
        assert 'repair_level' in result['adjustments']

    def test_fallback_without_repair_level(self):
        """Test fallback without repair level"""
        target = self._create_target()
        target.repair_level = None
        base_price = 170_000

        result = _fallback_calculation(target, base_price, 'median')

        # Should use base price without adjustment
        assert result['fair_price_per_sqm'] == base_price
        assert 'repair_level' not in result['adjustments']

    def test_fallback_overpriced(self):
        """Test fallback detects overpriced"""
        target = self._create_target()
        target.price = 15_000_000
        base_price = 170_000

        result = _fallback_calculation(target, base_price, 'mean')

        assert result['is_overpriced'] is True

    def test_fallback_underpriced(self):
        """Test fallback detects underpriced"""
        target = self._create_target()
        target.price = 7_000_000
        base_price = 170_000

        result = _fallback_calculation(target, base_price, 'mean')

        assert result['is_underpriced'] is True

    def test_fallback_fair_price(self):
        """Test fallback detects fair price"""
        target = self._create_target()
        target.price = 11_400_000  # Close to 170k * 1.12 (премиум) * 60
        base_price = 170_000

        result = _fallback_calculation(target, base_price, 'median')

        # Should be within ±5%
        assert -5 <= result['price_diff_percent'] <= 5 or result['is_fair']

    def test_fallback_total_price_calculation(self):
        """Test fallback calculates total price correctly"""
        target = self._create_target()
        target.total_area = 80
        base_price = 150_000

        result = _fallback_calculation(target, base_price, 'median')

        expected_per_sqm = base_price * result['final_multiplier']
        expected_total = expected_per_sqm * 80

        assert result['fair_price_total'] == expected_total

    def test_fallback_minimal_area(self):
        """Test fallback with minimal area"""
        target = self._create_target()
        target.total_area = 1  # Minimal valid area (Pydantic requires >0)
        base_price = 170_000

        result = _fallback_calculation(target, base_price, 'median')

        # Fair price should be minimal
        assert result['fair_price_total'] > 0
        assert result['fair_price_total'] < 500_000  # Should be very small

    def test_fallback_none_price(self):
        """Test fallback with None price"""
        target = self._create_target()
        target.price = None
        base_price = 170_000

        result = _fallback_calculation(target, base_price, 'median')

        assert result['current_price'] == 0
        assert result['price_diff_amount'] < 0  # Negative diff since current is 0
