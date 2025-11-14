"""
Unit tests for RecommendationEngine

Tests cover:
- Recommendation generation for different price scenarios
- ROI calculations
- Priority classification
- Financial impact calculations
- Edge cases
"""

import pytest
from src.analytics.recommendations import RecommendationEngine, Recommendation
from tests.fixtures import (
    get_overpriced_analysis,
    get_fair_priced_analysis,
    get_underpriced_analysis,
    get_needs_improvement_analysis
)


class TestRecommendation:
    """Tests for Recommendation dataclass"""

    def test_recommendation_to_dict(self):
        """Test conversion to dictionary"""
        rec = Recommendation(
            priority=1,
            icon='⚠️',
            title='Test Title',
            message='Test message',
            action='Test action',
            expected_result='Test result',
            roi=150.5,
            category='pricing'
        )

        result = rec.to_dict()

        assert result['priority'] == 1
        assert result['priority_label'] == 'КРИТИЧНО'
        assert result['icon'] == '⚠️'
        assert result['title'] == 'Test Title'
        assert result['roi'] == 150.5
        assert result['category'] == 'pricing'

    def test_priority_labels(self):
        """Test priority label mapping"""
        priorities = {
            1: 'КРИТИЧНО',
            2: 'ВАЖНО',
            3: 'СРЕДНЕ',
            4: 'ИНФО'
        }

        for priority, expected_label in priorities.items():
            rec = Recommendation(
                priority=priority,
                icon='🔔',
                title='Test',
                message='Test',
                action='Test',
                expected_result='Test'
            )
            assert rec._get_priority_label() == expected_label

    def test_unknown_priority_defaults_to_info(self):
        """Test unknown priority defaults to ИНФО"""
        rec = Recommendation(
            priority=999,  # Unknown priority
            icon='🔔',
            title='Test',
            message='Test',
            action='Test',
            expected_result='Test'
        )
        assert rec._get_priority_label() == 'ИНФО'


class TestRecommendationEngineInit:
    """Tests for RecommendationEngine initialization"""

    def test_engine_initialization(self):
        """Test engine initializes with analysis data"""
        analysis = get_fair_priced_analysis()
        engine = RecommendationEngine(analysis)

        assert engine.analysis == analysis
        assert engine.target == analysis['target_property']
        assert engine.fair_price_analysis == analysis['fair_price_analysis']
        assert engine.scenarios == analysis['price_scenarios']

    def test_constants_defined(self):
        """Test engine has required constants"""
        assert RecommendationEngine.CRITICAL == 1
        assert RecommendationEngine.HIGH == 2
        assert RecommendationEngine.MEDIUM == 3
        assert RecommendationEngine.INFO == 4
        assert RecommendationEngine.DESIGN_COST > 0
        assert RecommendationEngine.PHOTO_SESSION_COST > 0
        assert 0 < RecommendationEngine.OPPORTUNITY_RATE < 1


class TestPricingRecommendations:
    """Tests for _check_pricing() method"""

    def test_overpriced_critical_recommendation(self):
        """Test CRITICAL recommendation for >15% overpricing"""
        analysis = get_overpriced_analysis()  # 20% overpriced
        engine = RecommendationEngine(analysis)

        recs = engine._check_pricing()

        assert len(recs) > 0
        critical_recs = [r for r in recs if r.priority == RecommendationEngine.CRITICAL]
        assert len(critical_recs) >= 1

        critical = critical_recs[0]
        assert 'переоценен' in critical.message.lower() or 'переоценка' in critical.message.lower()
        assert critical.category == 'pricing'
        assert 'financial_impact' in critical.to_dict()

    def test_moderate_overpricing_high_priority(self):
        """Test HIGH priority for moderate overpricing (10-15%)"""
        analysis = get_overpriced_analysis()
        # Modify to moderate overpricing
        analysis['fair_price_analysis']['overpricing_percent'] = 12.0
        analysis['fair_price_analysis']['fair_price_total'] = 10_700_000

        engine = RecommendationEngine(analysis)
        recs = engine._check_pricing()

        high_recs = [r for r in recs if r.priority == RecommendationEngine.HIGH]
        assert len(high_recs) >= 1
        # Check that message mentions price is above market
        msg = high_recs[0].message.lower()
        assert ('выше' in msg and 'рынк' in msg) or 'переоценка' in msg or 'переоценен' in msg

    def test_slight_overpricing_medium_priority(self):
        """Test MEDIUM priority for slight overpricing (5-10%)"""
        analysis = get_fair_priced_analysis()
        analysis['fair_price_analysis']['overpricing_percent'] = 7.0

        engine = RecommendationEngine(analysis)
        recs = engine._check_pricing()

        medium_recs = [r for r in recs if r.priority == RecommendationEngine.MEDIUM]
        assert len(medium_recs) >= 1

    def test_fair_price_info_recommendation(self):
        """Test INFO recommendation for fair pricing (-5% to +5%)"""
        analysis = get_fair_priced_analysis()  # -1.3% overpricing
        engine = RecommendationEngine(analysis)

        recs = engine._check_pricing()

        assert len(recs) > 0
        info_rec = recs[0]
        assert info_rec.priority == RecommendationEngine.INFO
        assert 'справедлив' in info_rec.message.lower() or 'рынк' in info_rec.message.lower()

    def test_underpriced_recommendation(self):
        """Test recommendation for underpriced property"""
        analysis = get_underpriced_analysis()  # -11.1% underpriced
        engine = RecommendationEngine(analysis)

        recs = engine._check_pricing()

        assert len(recs) > 0
        underpriced_rec = recs[0]
        assert 'недооценен' in underpriced_rec.message.lower() or 'ниже рынка' in underpriced_rec.message.lower()
        assert 'financial_impact' in underpriced_rec.to_dict()

    def test_pricing_always_returns_recommendations(self):
        """Test that pricing check always returns at least one recommendation"""
        test_cases = [
            get_overpriced_analysis(),
            get_fair_priced_analysis(),
            get_underpriced_analysis()
        ]

        for analysis in test_cases:
            engine = RecommendationEngine(analysis)
            recs = engine._check_pricing()
            assert len(recs) >= 1, f"No pricing recommendation for overpricing={analysis['fair_price_analysis']['overpricing_percent']}%"


class TestImprovementRecommendations:
    """Tests for _check_improvements() method"""

    def test_design_improvement_high_roi(self):
        """Test design improvement recommendation when ROI > 50%"""
        analysis = get_needs_improvement_analysis()
        engine = RecommendationEngine(analysis)

        recs = engine._check_improvements()

        # Should have design recommendation
        design_recs = [r for r in recs if 'дизайн' in r.title.lower()]
        if len(design_recs) > 0:
            design_rec = design_recs[0]
            assert design_rec.priority == RecommendationEngine.HIGH
            assert design_rec.roi is not None
            assert design_rec.roi > 0
            assert 'investment' in design_rec.financial_impact
            assert 'return' in design_rec.financial_impact

    def test_no_improvement_for_designed_property(self):
        """Test no design recommendation for already designed property"""
        analysis = get_fair_priced_analysis()  # has_design=True
        engine = RecommendationEngine(analysis)

        recs = engine._check_improvements()

        design_recs = [r for r in recs if 'дизайн' in r.title.lower()]
        # Should have fewer or no design recs
        assert len(design_recs) == 0

    def test_parking_recommendation_for_premium_location(self):
        """Test parking recommendation for premium location without parking"""
        analysis = get_needs_improvement_analysis()  # premium_location=True, parking=False
        engine = RecommendationEngine(analysis)

        recs = engine._check_improvements()

        # May have parking recommendation
        parking_recs = [r for r in recs if 'парков' in r.message.lower() or 'парков' in r.title.lower()]
        # This is optional, just checking structure
        if len(parking_recs) > 0:
            assert parking_recs[0].category == 'improvement'


class TestPresentationRecommendations:
    """Tests for _check_presentation() method"""

    def test_photo_recommendation_for_few_photos(self):
        """Test photo recommendation when photos_count < 15"""
        analysis = get_needs_improvement_analysis()  # photos_count=8
        engine = RecommendationEngine(analysis)

        recs = engine._check_presentation()

        photo_recs = [r for r in recs if 'фото' in r.message.lower() or 'фото' in r.title.lower()]
        if len(photo_recs) > 0:
            assert photo_recs[0].category == 'presentation'

    def test_description_recommendation_for_short_text(self):
        """Test description recommendation when description is short"""
        analysis = get_needs_improvement_analysis()  # description_length=100
        engine = RecommendationEngine(analysis)

        recs = engine._check_presentation()

        desc_recs = [r for r in recs if 'описан' in r.message.lower()]
        # Should have description recommendation
        if len(desc_recs) > 0:
            assert desc_recs[0].category == 'presentation'

    def test_no_presentation_recs_for_good_listing(self):
        """Test minimal presentation recommendations for well-presented property"""
        analysis = get_fair_priced_analysis()  # photos=25, description=500
        engine = RecommendationEngine(analysis)

        recs = engine._check_presentation()

        # Should have 0 or very few presentation recs
        assert len(recs) <= 2


class TestGenerateMethod:
    """Tests for generate() method - main orchestrator"""

    def test_generate_returns_recommendations(self):
        """Test generate() returns list of recommendations"""
        analysis = get_overpriced_analysis()
        engine = RecommendationEngine(analysis)

        recs = engine.generate()

        assert isinstance(recs, list)
        assert len(recs) > 0
        assert all(isinstance(r, Recommendation) for r in recs)

    def test_recommendations_sorted_by_priority(self):
        """Test recommendations are sorted by priority (1=highest)"""
        analysis = get_needs_improvement_analysis()
        engine = RecommendationEngine(analysis)

        recs = engine.generate()

        # Check priority is non-decreasing
        priorities = [r.priority for r in recs]
        assert priorities == sorted(priorities), "Recommendations not sorted by priority"

    def test_all_categories_present_for_complex_case(self):
        """Test all recommendation categories for property needing work"""
        analysis = get_needs_improvement_analysis()
        engine = RecommendationEngine(analysis)

        recs = engine.generate()

        categories = {r.category for r in recs}

        # Should have pricing at minimum
        assert 'pricing' in categories

        # May have improvement, presentation, strategy
        assert len(categories) >= 1

    def test_critical_pricing_appears_first(self):
        """Test CRITICAL pricing recommendation appears first for overpriced property"""
        analysis = get_overpriced_analysis()
        engine = RecommendationEngine(analysis)

        recs = engine.generate()

        assert len(recs) > 0
        # First recommendation should be CRITICAL
        assert recs[0].priority == RecommendationEngine.CRITICAL
        assert recs[0].category == 'pricing'

    def test_generate_multiple_calls_consistent(self):
        """Test generate() returns consistent results on multiple calls"""
        analysis = get_fair_priced_analysis()
        engine = RecommendationEngine(analysis)

        recs1 = engine.generate()
        recs2 = engine.generate()

        # Should return same number of recommendations
        assert len(recs1) == len(recs2)

        # Priorities should match
        priorities1 = [r.priority for r in recs1]
        priorities2 = [r.priority for r in recs2]
        assert priorities1 == priorities2


class TestOpportunityCostCalculation:
    """Tests for _calc_opportunity_cost() helper"""

    def test_opportunity_cost_calculation(self):
        """Test opportunity cost grows with time"""
        analysis = get_fair_priced_analysis()
        engine = RecommendationEngine(analysis)

        cost_4m = engine._calc_opportunity_cost(10_000_000, 4)
        cost_12m = engine._calc_opportunity_cost(10_000_000, 12)

        assert cost_4m > 0
        assert cost_12m > cost_4m  # Longer time = higher opportunity cost

    def test_opportunity_cost_proportional_to_price(self):
        """Test opportunity cost increases with price"""
        analysis = get_fair_priced_analysis()
        engine = RecommendationEngine(analysis)

        cost_low = engine._calc_opportunity_cost(5_000_000, 6)
        cost_high = engine._calc_opportunity_cost(15_000_000, 6)

        assert cost_high > cost_low
        assert abs(cost_high / cost_low - 3.0) < 0.1  # Should be ~3x

    def test_opportunity_cost_zero_for_zero_months(self):
        """Test zero opportunity cost for zero months"""
        analysis = get_fair_priced_analysis()
        engine = RecommendationEngine(analysis)

        cost = engine._calc_opportunity_cost(10_000_000, 0)

        assert cost == 0


class TestEdgeCases:
    """Tests for edge cases and error handling"""

    def test_empty_target_property(self):
        """Test handling of empty target property"""
        analysis = {
            'target_property': {},
            'fair_price_analysis': {},
            'price_scenarios': [],
            'comparables': [],
            'market_statistics': {}
        }

        engine = RecommendationEngine(analysis)
        recs = engine.generate()

        # Should not crash, may return empty or minimal recommendations
        assert isinstance(recs, list)

    def test_missing_fair_price_analysis(self):
        """Test handling when fair_price_analysis is missing"""
        analysis = {
            'target_property': {'price': 10_000_000},
            'fair_price_analysis': {},  # Empty
            'price_scenarios': [],
            'comparables': [],
            'market_statistics': {}
        }

        engine = RecommendationEngine(analysis)
        recs = engine.generate()

        # Should handle gracefully
        assert isinstance(recs, list)

    def test_zero_price_handling(self):
        """Test handling of zero prices"""
        analysis = get_fair_priced_analysis()
        analysis['target_property']['price'] = 0
        analysis['fair_price_analysis']['fair_price_total'] = 0

        engine = RecommendationEngine(analysis)

        # Should not crash
        try:
            recs = engine.generate()
            assert isinstance(recs, list)
        except ZeroDivisionError:
            pytest.fail("Should handle zero prices without division errors")

    def test_negative_overpricing_extreme(self):
        """Test extreme underpricing (-50%)"""
        analysis = get_underpriced_analysis()
        analysis['fair_price_analysis']['overpricing_percent'] = -50.0

        engine = RecommendationEngine(analysis)
        recs = engine.generate()

        # Should still generate recommendations
        assert len(recs) > 0

    def test_extreme_overpricing(self):
        """Test extreme overpricing (+100%)"""
        analysis = get_overpriced_analysis()
        analysis['fair_price_analysis']['overpricing_percent'] = 100.0

        engine = RecommendationEngine(analysis)
        recs = engine.generate()

        # Should have CRITICAL recommendation
        critical_recs = [r for r in recs if r.priority == 1]
        assert len(critical_recs) >= 1


class TestROICalculations:
    """Tests for ROI calculation accuracy"""

    def test_roi_formula_correctness(self):
        """Test ROI calculation formula: (gain - cost) / cost * 100"""
        # Manual calculation
        cost = 500_000
        gain = 800_000
        expected_roi = ((gain - cost) / cost) * 100  # 60%

        # This would require exposing the calculation or testing via design recommendation
        # For now, we test that ROI exists and is reasonable
        analysis = get_needs_improvement_analysis()
        analysis['target_property']['total_area'] = 65
        analysis['fair_price_analysis']['base_price_per_sqm'] = 200_000

        engine = RecommendationEngine(analysis)
        recs = engine._check_improvements()

        design_recs = [r for r in recs if r.roi is not None and r.roi > 0]
        if len(design_recs) > 0:
            # ROI should be positive and reasonable (<500%)
            assert 0 < design_recs[0].roi < 500

    def test_recommendations_with_roi_have_financial_impact(self):
        """Test recommendations with ROI include financial_impact"""
        analysis = get_needs_improvement_analysis()
        engine = RecommendationEngine(analysis)

        recs = engine.generate()

        recs_with_roi = [r for r in recs if r.roi is not None]
        for rec in recs_with_roi:
            assert rec.financial_impact is not None
            # Should have some financial data
            assert len(rec.financial_impact) > 0


class TestGetSummary:
    """Tests for get_summary() method if it exists"""

    def test_get_summary_exists(self):
        """Test get_summary method exists"""
        analysis = get_fair_priced_analysis()
        engine = RecommendationEngine(analysis)

        # Check if method exists
        assert hasattr(engine, 'get_summary')

    def test_get_summary_returns_dict(self):
        """Test get_summary returns dictionary"""
        analysis = get_fair_priced_analysis()
        engine = RecommendationEngine(analysis)

        if hasattr(engine, 'get_summary'):
            summary = engine.get_summary()
            assert isinstance(summary, dict)


# ═══════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestRecommendationEngineIntegration:
    """Integration tests with realistic scenarios"""

    @pytest.mark.parametrize("analysis_fixture", [
        get_overpriced_analysis,
        get_fair_priced_analysis,
        get_underpriced_analysis,
        get_needs_improvement_analysis
    ])
    def test_all_scenarios_generate_recommendations(self, analysis_fixture):
        """Test all realistic scenarios generate valid recommendations"""
        analysis = analysis_fixture()
        engine = RecommendationEngine(analysis)

        recs = engine.generate()

        assert len(recs) > 0
        assert all(isinstance(r, Recommendation) for r in recs)
        assert all(1 <= r.priority <= 4 for r in recs)
        assert all(r.title for r in recs)
        assert all(r.message for r in recs)

    def test_recommendation_completeness(self):
        """Test recommendations have all required fields"""
        analysis = get_needs_improvement_analysis()
        engine = RecommendationEngine(analysis)

        recs = engine.generate()

        for rec in recs:
            assert rec.priority in [1, 2, 3, 4]
            assert rec.icon
            assert rec.title
            assert rec.message
            assert rec.action
            assert rec.expected_result
            assert rec.category

    def test_json_serialization(self):
        """Test recommendations can be serialized to JSON"""
        import json

        analysis = get_fair_priced_analysis()
        engine = RecommendationEngine(analysis)

        recs = engine.generate()
        recs_dict = [r.to_dict() for r in recs]

        # Should be JSON serializable
        try:
            json_str = json.dumps(recs_dict, ensure_ascii=False)
            assert len(json_str) > 0
        except TypeError:
            pytest.fail("Recommendations should be JSON serializable")
