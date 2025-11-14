"""
Unit tests for price_range.py - price range calculation and sensitivity analysis
"""

import pytest
from src.analytics.price_range import (
    calculate_price_range,
    _generate_interpretation,
    _generate_visual_range,
    calculate_price_sensitivity,
)


class TestCalculatePriceRange:
    """Tests for calculate_price_range() function"""

    def test_basic_calculation_with_ci(self):
        """Test basic price range calculation with confidence interval"""
        fair_price = 10_000_000
        confidence_interval = {
            'lower': 9_500_000,
            'upper': 10_500_000,
            'margin': 500_000
        }

        result = calculate_price_range(fair_price, confidence_interval)

        # Check all price points are present
        assert 'min_price' in result
        assert 'fair_price' in result
        assert 'recommended_listing' in result
        assert 'max_price' in result
        assert 'min_acceptable_price' in result

        # Check fair price is preserved
        assert result['fair_price'] == fair_price

        # Check ordering: min < fair < recommended < max
        assert result['min_price'] < result['fair_price']
        assert result['fair_price'] <= result['recommended_listing']
        assert result['recommended_listing'] <= result['max_price']

    def test_calculation_without_ci(self):
        """Test price range calculation without confidence interval"""
        fair_price = 10_000_000

        result = calculate_price_range(fair_price)

        # Should use default ±5% from fair price
        # ci_lower = 9.5M, ci_upper = 10.5M
        # min_price = ci_lower * 0.97 = 9.215M
        # max_price = ci_upper * 1.03 = 10.815M

        assert result['min_price'] == pytest.approx(9_500_000 * 0.97, rel=0.01)
        assert result['max_price'] == pytest.approx(10_500_000 * 1.03, rel=0.01)

    def test_listing_premium_normal_price(self):
        """Test listing premium for normal price (overpricing <= 0%)"""
        fair_price = 10_000_000

        result = calculate_price_range(fair_price, overpricing_percent=0)

        # Should apply 5% premium for negotiation
        assert result['recommended_listing'] == fair_price * 1.05
        assert result['recommended_listing_percent'] == pytest.approx(5.0, rel=0.01)

    def test_listing_premium_slight_overpricing(self):
        """Test listing premium for slight overpricing (0% < overpricing <= 5%)"""
        fair_price = 10_000_000

        result = calculate_price_range(fair_price, overpricing_percent=3.0)

        # Should apply 3% premium
        assert result['recommended_listing'] == fair_price * 1.03
        assert result['recommended_listing_percent'] == pytest.approx(3.0, rel=0.01)

    def test_listing_premium_high_overpricing(self):
        """Test listing premium for high overpricing (>5%)"""
        fair_price = 10_000_000

        result = calculate_price_range(fair_price, overpricing_percent=8.0)

        # Should apply no premium
        assert result['recommended_listing'] == fair_price
        assert result['recommended_listing_percent'] == 0.0

    def test_min_acceptable_price_calculation(self):
        """Test min acceptable price calculation"""
        fair_price = 10_000_000

        result = calculate_price_range(fair_price, overpricing_percent=0)

        # min_acceptable = recommended_listing * 0.95
        expected = result['recommended_listing'] * 0.95
        assert result['min_acceptable_price'] == expected

    def test_min_acceptable_not_below_min_price(self):
        """Test that min acceptable price is never below min price"""
        fair_price = 10_000_000
        # Create scenario where min_acceptable might be too low
        confidence_interval = {
            'lower': 8_000_000,  # Very low CI
            'upper': 12_000_000,
            'margin': 2_000_000
        }

        result = calculate_price_range(
            fair_price,
            confidence_interval,
            overpricing_percent=10  # No premium on listing
        )

        # min_acceptable should not be below min_price
        assert result['min_acceptable_price'] >= result['min_price']

    def test_price_range_spread_calculation(self):
        """Test price range spread calculation"""
        fair_price = 10_000_000
        confidence_interval = {
            'lower': 9_500_000,
            'upper': 10_500_000,
            'margin': 500_000
        }

        result = calculate_price_range(fair_price, confidence_interval)

        expected_spread = result['max_price'] - result['min_price']
        assert result['price_range_spread'] == expected_spread

        expected_percent = (expected_spread / fair_price) * 100
        assert result['price_range_spread_percent'] == pytest.approx(expected_percent, rel=0.01)

    def test_negotiation_room_calculation(self):
        """Test negotiation room calculation"""
        fair_price = 10_000_000

        result = calculate_price_range(fair_price, overpricing_percent=0)

        expected_room = result['recommended_listing'] - result['min_acceptable_price']
        assert result['negotiation_room'] == expected_room

        expected_percent = (expected_room / result['recommended_listing']) * 100
        assert result['negotiation_room_percent'] == pytest.approx(expected_percent, rel=0.01)

    def test_zero_fair_price(self):
        """Test with zero fair price"""
        result = calculate_price_range(0)

        assert result == {}

    def test_negative_fair_price(self):
        """Test with negative fair price"""
        result = calculate_price_range(-1000)

        assert result == {}

    def test_includes_interpretation(self):
        """Test that result includes interpretation"""
        fair_price = 10_000_000

        result = calculate_price_range(fair_price, overpricing_percent=5)

        assert 'interpretation' in result
        assert isinstance(result['interpretation'], dict)

    def test_includes_visual_range(self):
        """Test that result includes visual range"""
        fair_price = 10_000_000

        result = calculate_price_range(fair_price)

        assert 'visual_range' in result
        assert isinstance(result['visual_range'], str)

    def test_percent_calculations_with_zero_protection(self):
        """Test that percent calculations handle zero division"""
        fair_price = 10_000_000

        result = calculate_price_range(fair_price)

        # All percent fields should be numbers, not inf/nan
        assert isinstance(result['min_price_percent'], (int, float))
        assert isinstance(result['recommended_listing_percent'], (int, float))
        assert isinstance(result['max_price_percent'], (int, float))
        assert not (result['min_price_percent'] == float('inf'))
        assert not (result['max_price_percent'] == float('inf'))

    def test_descriptions_present(self):
        """Test that all price descriptions are present"""
        fair_price = 10_000_000

        result = calculate_price_range(fair_price)

        assert 'min_price_description' in result
        assert 'fair_price_description' in result
        assert 'recommended_listing_description' in result
        assert 'max_price_description' in result
        assert 'min_acceptable_description' in result

        # Check they're not empty
        assert len(result['min_price_description']) > 0
        assert len(result['fair_price_description']) > 0


class TestGenerateInterpretation:
    """Tests for _generate_interpretation() function"""

    def test_critical_overpricing_strategy(self):
        """Test interpretation for critical overpricing (>15%)"""
        price_range = self._create_basic_price_range()

        interpretation = _generate_interpretation(price_range, 20.0)

        assert '🔴 КРИТИЧНО' in interpretation['pricing_strategy']
        assert 'сильно переоценен' in interpretation['pricing_strategy'].lower()

    def test_moderate_overpricing_strategy(self):
        """Test interpretation for moderate overpricing (10-15%)"""
        price_range = self._create_basic_price_range()

        interpretation = _generate_interpretation(price_range, 12.0)

        assert '⚠️' in interpretation['pricing_strategy']
        assert 'переоценен' in interpretation['pricing_strategy'].lower()

    def test_slight_overpricing_strategy(self):
        """Test interpretation for slight overpricing (5-10%)"""
        price_range = self._create_basic_price_range()

        interpretation = _generate_interpretation(price_range, 7.0)

        assert '💡 Небольшая переоценка' in interpretation['pricing_strategy']

    def test_fair_price_strategy(self):
        """Test interpretation for fair price (-5% to 5%)"""
        price_range = self._create_basic_price_range()

        interpretation = _generate_interpretation(price_range, 2.0)

        assert '✅ Цена близка к рынку' in interpretation['pricing_strategy']

    def test_underpriced_strategy(self):
        """Test interpretation for underpriced (<-5%)"""
        price_range = self._create_basic_price_range()

        interpretation = _generate_interpretation(price_range, -10.0)

        assert '💰 Объект недооценен' in interpretation['pricing_strategy']

    def test_timeline_critical_overpricing(self):
        """Test timeline for critical overpricing (>15%)"""
        price_range = self._create_basic_price_range()

        interpretation = _generate_interpretation(price_range, 20.0)

        assert '12+ месяцев' in interpretation['expected_timeline']
        assert '2-4 месяца при справедливой' in interpretation['expected_timeline']

    def test_timeline_moderate_overpricing(self):
        """Test timeline for moderate overpricing (10-15%)"""
        price_range = self._create_basic_price_range()

        interpretation = _generate_interpretation(price_range, 12.0)

        assert '6-12 месяцев' in interpretation['expected_timeline']

    def test_timeline_slight_overpricing(self):
        """Test timeline for slight overpricing (5-10%)"""
        price_range = self._create_basic_price_range()

        interpretation = _generate_interpretation(price_range, 7.0)

        assert '4-6 месяцев' in interpretation['expected_timeline']

    def test_timeline_fair_price(self):
        """Test timeline for fair price (-5% to 5%)"""
        price_range = self._create_basic_price_range()

        interpretation = _generate_interpretation(price_range, 2.0)

        assert '2-4 месяца' in interpretation['expected_timeline']

    def test_timeline_underpriced(self):
        """Test timeline for underpriced (<-5%)"""
        price_range = self._create_basic_price_range()

        interpretation = _generate_interpretation(price_range, -10.0)

        assert '1-2 месяца' in interpretation['expected_timeline']

    def test_negotiation_advice(self):
        """Test negotiation advice generation"""
        price_range = self._create_basic_price_range()

        interpretation = _generate_interpretation(price_range, 5.0)

        assert 'negotiation_advice' in interpretation
        assert 'Заложите' in interpretation['negotiation_advice']
        assert 'на торг' in interpretation['negotiation_advice']
        assert 'Не опускайтесь ниже' in interpretation['negotiation_advice']

    def test_risk_high_uncertainty(self):
        """Test risk assessment for high uncertainty (spread >20%)"""
        price_range = {
            'fair_price': 10_000_000,
            'min_price': 8_000_000,
            'max_price': 12_500_000,
            'recommended_listing': 10_500_000,
            'min_acceptable_price': 9_975_000,
            'negotiation_room': 525_000,
            'negotiation_room_percent': 5.0,
            'price_range_spread': 4_500_000,
            'price_range_spread_percent': 45.0  # >20%
        }

        interpretation = _generate_interpretation(price_range, 0)

        assert '⚠️ Высокая неопределенность' in interpretation['risk_assessment']
        assert 'больше аналогов' in interpretation['risk_assessment'].lower()

    def test_risk_moderate_uncertainty(self):
        """Test risk assessment for moderate uncertainty (15-20%)"""
        price_range = {
            'fair_price': 10_000_000,
            'min_price': 9_100_000,
            'max_price': 10_800_000,
            'recommended_listing': 10_500_000,
            'min_acceptable_price': 9_975_000,
            'negotiation_room': 525_000,
            'negotiation_room_percent': 5.0,
            'price_range_spread': 1_700_000,
            'price_range_spread_percent': 17.0  # 15-20%
        }

        interpretation = _generate_interpretation(price_range, 0)

        assert 'Умеренная неопределенность' in interpretation['risk_assessment']

    def test_risk_low_uncertainty(self):
        """Test risk assessment for low uncertainty (<15%)"""
        price_range = {
            'fair_price': 10_000_000,
            'min_price': 9_500_000,
            'max_price': 10_500_000,
            'recommended_listing': 10_500_000,
            'min_acceptable_price': 9_975_000,
            'negotiation_room': 525_000,
            'negotiation_room_percent': 5.0,
            'price_range_spread': 1_000_000,
            'price_range_spread_percent': 10.0  # <15%
        }

        interpretation = _generate_interpretation(price_range, 0)

        assert '✅ Низкая неопределенность' in interpretation['risk_assessment']
        assert 'очень надежна' in interpretation['risk_assessment'].lower()

    def test_interpretation_structure(self):
        """Test that interpretation has all required fields"""
        price_range = self._create_basic_price_range()

        interpretation = _generate_interpretation(price_range, 5.0)

        assert 'pricing_strategy' in interpretation
        assert 'expected_timeline' in interpretation
        assert 'negotiation_advice' in interpretation
        assert 'risk_assessment' in interpretation

    def _create_basic_price_range(self):
        """Helper to create basic price range dict"""
        return {
            'fair_price': 10_000_000,
            'min_price': 9_215_000,
            'max_price': 10_815_000,
            'recommended_listing': 10_500_000,
            'min_acceptable_price': 9_975_000,
            'negotiation_room': 525_000,
            'negotiation_room_percent': 5.0,
            'price_range_spread': 1_600_000,
            'price_range_spread_percent': 16.0
        }


class TestGenerateVisualRange:
    """Tests for _generate_visual_range() function"""

    def test_visual_range_basic(self):
        """Test basic visual range generation"""
        price_range = {
            'min_price': 9_000_000,
            'fair_price': 10_000_000,
            'max_price': 11_000_000,
            'recommended_listing': 10_500_000
        }

        visual = _generate_visual_range(price_range)

        assert isinstance(visual, str)
        assert len(visual) > 0

    def test_visual_range_contains_prices(self):
        """Test that visual range contains price information"""
        price_range = {
            'min_price': 9_000_000,
            'fair_price': 10_000_000,
            'max_price': 11_000_000,
            'recommended_listing': 10_500_000
        }

        visual = _generate_visual_range(price_range)

        # Should contain million markers
        assert '9.0M' in visual or '9.00M' in visual
        assert '10.0M' in visual or '10.00M' in visual
        assert '11.0M' in visual or '11.00M' in visual
        assert '10.5M' in visual or '10.50M' in visual

    def test_visual_range_contains_labels(self):
        """Test that visual range contains labels"""
        price_range = {
            'min_price': 9_000_000,
            'fair_price': 10_000_000,
            'max_price': 11_000_000,
            'recommended_listing': 10_500_000
        }

        visual = _generate_visual_range(price_range)

        assert 'MIN' in visual
        assert 'FAIR' in visual
        assert 'REC' in visual


class TestCalculatePriceSensitivity:
    """Tests for calculate_price_sensitivity() function"""

    def test_basic_sensitivity_calculation(self):
        """Test basic price sensitivity calculation"""
        fair_price = 10_000_000

        sensitivity = calculate_price_sensitivity(fair_price)

        assert isinstance(sensitivity, list)
        assert len(sensitivity) == 10  # 10 price points

    def test_sensitivity_price_points(self):
        """Test that sensitivity includes expected price points"""
        fair_price = 10_000_000

        sensitivity = calculate_price_sensitivity(fair_price)

        discount_percents = [point['discount_percent'] for point in sensitivity]

        # Should include points from -10% to +15%
        assert -10 in discount_percents
        assert 0 in discount_percents
        assert 15 in discount_percents

    def test_sensitivity_structure(self):
        """Test that each sensitivity point has correct structure"""
        fair_price = 10_000_000

        sensitivity = calculate_price_sensitivity(fair_price)

        for point in sensitivity:
            assert 'price' in point
            assert 'discount_percent' in point
            assert 'probability' in point
            assert 'expected_time_months' in point

    def test_discount_increases_probability(self):
        """Test that discounting increases probability"""
        fair_price = 10_000_000

        sensitivity = calculate_price_sensitivity(fair_price, base_probability=0.75)

        # Find fair price point (0% discount)
        fair_point = next(p for p in sensitivity if p['discount_percent'] == 0)

        # Find discounted point (-5%)
        discount_point = next(p for p in sensitivity if p['discount_percent'] == -5)

        assert discount_point['probability'] > fair_point['probability']

    def test_overpricing_decreases_probability(self):
        """Test that overpricing decreases probability"""
        fair_price = 10_000_000

        sensitivity = calculate_price_sensitivity(fair_price, base_probability=0.75)

        # Find fair price point (0% discount)
        fair_point = next(p for p in sensitivity if p['discount_percent'] == 0)

        # Find overpriced point (+10%)
        overpriced_point = next(p for p in sensitivity if p['discount_percent'] == 10)

        assert overpriced_point['probability'] < fair_point['probability']

    def test_discount_decreases_time(self):
        """Test that discounting decreases expected time"""
        fair_price = 10_000_000

        sensitivity = calculate_price_sensitivity(fair_price, time_months=6)

        # Find fair price point (0% discount)
        fair_point = next(p for p in sensitivity if p['discount_percent'] == 0)

        # Find discounted point (-5%)
        discount_point = next(p for p in sensitivity if p['discount_percent'] == -5)

        assert discount_point['expected_time_months'] < fair_point['expected_time_months']

    def test_overpricing_increases_time(self):
        """Test that overpricing increases expected time"""
        fair_price = 10_000_000

        sensitivity = calculate_price_sensitivity(fair_price, time_months=6)

        # Find fair price point (0% discount)
        fair_point = next(p for p in sensitivity if p['discount_percent'] == 0)

        # Find overpriced point (+10%)
        overpriced_point = next(p for p in sensitivity if p['discount_percent'] == 10)

        assert overpriced_point['expected_time_months'] > fair_point['expected_time_months']

    def test_probability_capped_at_95(self):
        """Test that probability never exceeds 0.95"""
        fair_price = 10_000_000

        sensitivity = calculate_price_sensitivity(fair_price, base_probability=0.75)

        for point in sensitivity:
            assert point['probability'] <= 0.95

    def test_probability_minimum_10(self):
        """Test that probability never goes below 0.10"""
        fair_price = 10_000_000

        sensitivity = calculate_price_sensitivity(fair_price, base_probability=0.75)

        for point in sensitivity:
            assert point['probability'] >= 0.10

    def test_custom_base_probability(self):
        """Test with custom base probability"""
        fair_price = 10_000_000

        sensitivity = calculate_price_sensitivity(fair_price, base_probability=0.60)

        # Find fair price point
        fair_point = next(p for p in sensitivity if p['discount_percent'] == 0)

        # Should be close to base probability
        assert fair_point['probability'] == 0.60

    def test_custom_time_months(self):
        """Test with custom time period"""
        fair_price = 10_000_000

        sensitivity = calculate_price_sensitivity(fair_price, time_months=12)

        # Find fair price point
        fair_point = next(p for p in sensitivity if p['discount_percent'] == 0)

        # Time should be based on 12 months
        assert fair_point['expected_time_months'] == 12.0

    def test_price_calculation_accuracy(self):
        """Test that prices are calculated correctly"""
        fair_price = 10_000_000

        sensitivity = calculate_price_sensitivity(fair_price)

        # Check -10% discount
        discount_point = next(p for p in sensitivity if p['discount_percent'] == -10)
        assert discount_point['price'] == fair_price * 0.90

        # Check +15% overpricing
        overpriced_point = next(p for p in sensitivity if p['discount_percent'] == 15)
        assert overpriced_point['price'] == fair_price * 1.15

    def test_values_are_rounded(self):
        """Test that probability and time are rounded"""
        fair_price = 10_000_000

        sensitivity = calculate_price_sensitivity(fair_price)

        for point in sensitivity:
            # Probability should be rounded to 2 decimals
            prob_str = str(point['probability'])
            if '.' in prob_str:
                decimals = len(prob_str.split('.')[1])
                assert decimals <= 2

            # Time should be rounded to 1 decimal
            time_str = str(point['expected_time_months'])
            if '.' in time_str:
                decimals = len(time_str.split('.')[1])
                assert decimals <= 1
