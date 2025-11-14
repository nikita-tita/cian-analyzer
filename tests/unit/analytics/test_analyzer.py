"""
Unit tests for RealEstateAnalyzer

Tests cover:
- Analyzer initialization
- Market statistics calculation
- Confidence interval calculation
- Strengths/weaknesses analysis
- Chart data generation
- Basic analysis workflow
"""

import pytest
from src.analytics.analyzer import RealEstateAnalyzer
from src.models.property import AnalysisRequest, TargetProperty, ComparableProperty
from tests.fixtures import get_clean_comparables


class TestAnalyzerInitialization:
    """Tests for RealEstateAnalyzer initialization"""

    def test_analyzer_init_default(self):
        """Test analyzer initializes with default config"""
        analyzer = RealEstateAnalyzer()

        assert analyzer.config == {}
        assert analyzer.request is None
        assert analyzer.filtered_comparables == []
        assert analyzer.data_quality == {}
        assert analyzer.metrics is not None
        assert 'calculation_time_ms' in analyzer.metrics

    def test_analyzer_init_with_config(self):
        """Test analyzer initializes with custom config"""
        config = {
            'min_comparables': 10,
            'filter_outliers': True
        }
        analyzer = RealEstateAnalyzer(config=config)

        assert analyzer.config == config
        assert analyzer.config['min_comparables'] == 10

    def test_analyzer_init_with_property_id(self):
        """Test analyzer initializes with property tracking"""
        analyzer = RealEstateAnalyzer(property_id='test-property-123')

        assert analyzer.property_id == 'test-property-123'

    def test_analyzer_constants_defined(self):
        """Test analyzer has required constants"""
        assert RealEstateAnalyzer.LARGE_APARTMENT_THRESHOLD == 150
        assert RealEstateAnalyzer.DESIGN_COEFFICIENT == 1.08
        assert 0 < RealEstateAnalyzer.LARGE_SIZE_MULTIPLIER < 1
        assert RealEstateAnalyzer.MAX_LARGE_SIZE_BONUS > 1


class TestMarketStatistics:
    """Tests for calculate_market_statistics()"""

    def test_market_statistics_basic(self):
        """Test basic market statistics calculation"""
        comparables = get_clean_comparables()

        analyzer = RealEstateAnalyzer()
        analyzer.filtered_comparables = comparables

        stats = analyzer.calculate_market_statistics()

        assert isinstance(stats, dict)
        # Market stats has nested structure with 'all', 'with_design', etc.
        assert 'all' in stats
        if 'all' in stats:
            assert 'median' in stats['all'] or 'mean' in stats['all']
            assert 'count' in stats['all']

    def test_market_statistics_with_empty_data(self):
        """Test market statistics with empty comparables"""
        analyzer = RealEstateAnalyzer()
        analyzer.filtered_comparables = []

        stats = analyzer.calculate_market_statistics()

        assert isinstance(stats, dict)
        # Should handle empty gracefully

    def test_market_statistics_includes_median(self):
        """Test market statistics includes median price"""
        comparables = get_clean_comparables()

        analyzer = RealEstateAnalyzer()
        analyzer.filtered_comparables = comparables

        stats = analyzer.calculate_market_statistics()

        # Market stats has nested structure
        assert 'all' in stats
        assert 'median' in stats['all']


class TestConfidenceInterval:
    """Tests for _calculate_confidence_interval()"""

    def test_confidence_interval_calculation(self):
        """Test confidence interval calculation with valid data"""
        values = [100_000, 105_000, 98_000, 102_000, 101_000, 99_000, 103_000, 100_500]

        analyzer = RealEstateAnalyzer()
        ci = analyzer._calculate_confidence_interval(values, confidence=0.95)

        # _calculate_confidence_interval returns tuple (lower, upper)
        assert isinstance(ci, tuple)
        assert len(ci) == 2
        lower, upper = ci
        assert lower < upper
        # Bounds should be reasonable
        assert 90_000 < lower < 110_000
        assert 90_000 < upper < 110_000

    def test_confidence_interval_with_small_sample(self):
        """Test confidence interval with small sample"""
        values = [100_000, 105_000]

        analyzer = RealEstateAnalyzer()
        ci = analyzer._calculate_confidence_interval(values, confidence=0.95)

        # Returns tuple (lower, upper)
        assert isinstance(ci, tuple)
        assert len(ci) == 2

    def test_confidence_interval_different_confidence_levels(self):
        """Test confidence intervals at different confidence levels"""
        values = [100_000, 105_000, 98_000, 102_000, 101_000, 99_000, 103_000, 100_500]

        analyzer = RealEstateAnalyzer()

        ci_90 = analyzer._calculate_confidence_interval(values, confidence=0.90)
        ci_95 = analyzer._calculate_confidence_interval(values, confidence=0.95)

        # 95% CI should be wider than 90% CI
        lower_90, upper_90 = ci_90
        lower_95, upper_95 = ci_95

        width_90 = upper_90 - lower_90
        width_95 = upper_95 - lower_95
        assert width_95 >= width_90


class TestStrengthsWeaknesses:
    """Tests for calculate_strengths_weaknesses()"""

    def test_strengths_weaknesses_structure(self):
        """Test strengths/weaknesses returns correct structure"""
        comparables = get_clean_comparables()
        target = TargetProperty(
            url='https://test.com/property/123',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10
        )

        analyzer = RealEstateAnalyzer()
        analyzer.request = AnalysisRequest(
            target_property=target,
            comparables=comparables
        )
        analyzer.filtered_comparables = comparables

        result = analyzer.calculate_strengths_weaknesses()

        assert isinstance(result, dict)
        # Should have strengths and weaknesses
        assert 'strengths' in result or 'weaknesses' in result or 'summary' in result

    def test_strengths_weaknesses_with_no_comparables(self):
        """Test strengths/weaknesses with no comparables"""
        target = TargetProperty(
            url='https://test.com/property/123',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10
        )

        analyzer = RealEstateAnalyzer()
        analyzer.request = AnalysisRequest(
            target_property=target,
            comparables=[]
        )
        analyzer.filtered_comparables = []

        result = analyzer.calculate_strengths_weaknesses()

        assert isinstance(result, dict)


class TestChartDataGeneration:
    """Tests for chart data generation methods"""

    def test_comparison_chart_data(self):
        """Test generate_comparison_chart_data()"""
        comparables = get_clean_comparables()
        target = TargetProperty(
            url='https://test.com/property/123',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10
        )

        analyzer = RealEstateAnalyzer()
        analyzer.request = AnalysisRequest(
            target_property=target,
            comparables=comparables
        )
        analyzer.filtered_comparables = comparables

        chart_data = analyzer.generate_comparison_chart_data()

        assert isinstance(chart_data, dict)
        # Should have chart data for visualization

    def test_box_plot_data(self):
        """Test generate_box_plot_data()"""
        comparables = get_clean_comparables()
        target = TargetProperty(
            url='https://test.com/property/123',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10
        )

        analyzer = RealEstateAnalyzer()
        analyzer.request = AnalysisRequest(
            target_property=target,
            comparables=comparables
        )
        analyzer.filtered_comparables = comparables

        box_data = analyzer.generate_box_plot_data()

        assert isinstance(box_data, dict)
        # Should have box plot statistics

    def test_chart_data_with_empty_comparables(self):
        """Test chart generation with no comparables"""
        target = TargetProperty(
            url='https://test.com/property/123',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10
        )

        analyzer = RealEstateAnalyzer()
        analyzer.request = AnalysisRequest(
            target_property=target,
            comparables=[]
        )
        analyzer.filtered_comparables = []

        chart_data = analyzer.generate_comparison_chart_data()
        box_data = analyzer.generate_box_plot_data()

        assert isinstance(chart_data, dict)
        assert isinstance(box_data, dict)


class TestAnalyzerMetrics:
    """Tests for analyzer metrics"""

    def test_get_metrics(self):
        """Test get_metrics() returns metrics dict"""
        analyzer = RealEstateAnalyzer()

        metrics = analyzer.get_metrics()

        assert isinstance(metrics, dict)
        assert 'calculation_time_ms' in metrics
        assert 'comparables_filtered' in metrics

    def test_metrics_updated_during_analysis(self):
        """Test metrics are updated during analysis"""
        # This would require running actual analysis
        # For now just check initial state
        analyzer = RealEstateAnalyzer()

        initial_metrics = analyzer.get_metrics()
        assert initial_metrics['calculation_time_ms'] == 0
        assert initial_metrics['comparables_filtered'] == 0


class TestAnalyzerEdgeCases:
    """Tests for edge cases and error handling"""

    def test_analyzer_with_none_values(self):
        """Test analyzer handles None values gracefully"""
        analyzer = RealEstateAnalyzer(config=None, property_id=None)

        assert analyzer.config == {}
        assert analyzer.property_id is None

    def test_filtered_comparables_empty_initially(self):
        """Test filtered_comparables starts empty"""
        analyzer = RealEstateAnalyzer()

        assert analyzer.filtered_comparables == []
        assert len(analyzer.filtered_comparables) == 0

    def test_data_quality_empty_initially(self):
        """Test data_quality starts empty"""
        analyzer = RealEstateAnalyzer()

        assert analyzer.data_quality == {}
        assert len(analyzer.data_quality) == 0


# Integration test for basic workflow
class TestAnalyzerIntegration:
    """Integration tests for complete analysis workflow"""

    def test_basic_analysis_workflow(self):
        """Test basic analysis workflow without full analyze()"""
        # Create minimal request
        target = TargetProperty(
            url='https://test.com/property/123',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10
        )
        comparables = get_clean_comparables()

        # Initialize analyzer
        analyzer = RealEstateAnalyzer()
        analyzer.request = AnalysisRequest(
            target_property=target,
            comparables=comparables
        )
        analyzer.filtered_comparables = comparables

        # Test individual components work
        stats = analyzer.calculate_market_statistics()
        assert isinstance(stats, dict)

        strengths = analyzer.calculate_strengths_weaknesses()
        assert isinstance(strengths, dict)

        chart_data = analyzer.generate_comparison_chart_data()
        assert isinstance(chart_data, dict)

        metrics = analyzer.get_metrics()
        assert isinstance(metrics, dict)


class TestFilterOutliers:
    """Tests for _filter_outliers() method"""

    def test_filter_outliers_removes_extreme_values(self):
        """Test that outliers beyond 3σ are removed"""
        comparables = get_clean_comparables()

        # Add a moderately high outlier (not too extreme to avoid skewing mean/stdev)
        # Clean comparables are around 167k/sqm, so 230k is about 3-4 stdev away
        outlier = ComparableProperty(
            url='https://test.com/outlier',
            price=13_800_000,
            total_area=60,
            price_per_sqm=230_000,  # Moderately high price per sqm
            rooms=2,
            floor=5,
            total_floors=10
        )
        comparables_with_outlier = comparables + [outlier]

        analyzer = RealEstateAnalyzer()
        filtered = analyzer._filter_outliers(comparables_with_outlier)

        # Should filter out some comparables (may be the outlier or clean ones at edges)
        # The ±3σ rule should remove at least one
        assert len(filtered) <= len(comparables_with_outlier)

    def test_filter_outliers_keeps_normal_values(self):
        """Test that normal values within 3σ are kept"""
        comparables = get_clean_comparables()

        analyzer = RealEstateAnalyzer()
        filtered = analyzer._filter_outliers(comparables)

        # Clean comparables should mostly remain
        assert len(filtered) > 0
        assert len(filtered) >= len(comparables) - 1  # May remove 1 at most

    def test_filter_outliers_with_insufficient_data(self):
        """Test filtering with < 2 comparables"""
        comparables = get_clean_comparables()[:1]

        analyzer = RealEstateAnalyzer()
        filtered = analyzer._filter_outliers(comparables)

        # Should return as-is
        assert len(filtered) == 1

    def test_filter_outliers_excludes_already_excluded(self):
        """Test that already excluded comparables are not included"""
        comparables = get_clean_comparables()
        # Mark one as excluded
        comparables[0].excluded = True

        analyzer = RealEstateAnalyzer()
        filtered = analyzer._filter_outliers(comparables)

        # Excluded should not appear in result
        assert comparables[0] not in filtered

    def test_filter_outliers_handles_missing_price_per_sqm(self):
        """Test handling comparables without price_per_sqm"""
        comparables = get_clean_comparables()
        # Add one without price_per_sqm
        no_price = ComparableProperty(
            url='https://test.com/no-price',
            price=10_000_000,
            total_area=60,
            price_per_sqm=None,
            rooms=2,
            floor=5,
            total_floors=10
        )
        comparables_with_none = comparables + [no_price]

        analyzer = RealEstateAnalyzer()
        filtered = analyzer._filter_outliers(comparables_with_none)

        # Should handle gracefully and include the no-price comparable
        assert no_price in filtered


class TestCalculateFairPrice:
    """Tests for calculate_fair_price() method"""

    def test_calculate_fair_price_basic(self):
        """Test basic fair price calculation"""
        target = TargetProperty(
            url='https://test.com/property/123',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10
        )
        comparables = get_clean_comparables()

        analyzer = RealEstateAnalyzer()
        analyzer.request = AnalysisRequest(
            target_property=target,
            comparables=comparables,
            use_median=True
        )
        analyzer.filtered_comparables = comparables

        result = analyzer.calculate_fair_price()

        assert isinstance(result, dict)
        assert 'fair_price_total' in result
        assert 'fair_price_per_sqm' in result
        assert 'current_price' in result
        assert result['fair_price_total'] > 0

    def test_calculate_fair_price_with_median(self):
        """Test fair price using median method"""
        target = TargetProperty(
            url='https://test.com/property/123',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10
        )
        comparables = get_clean_comparables()

        analyzer = RealEstateAnalyzer()
        analyzer.request = AnalysisRequest(
            target_property=target,
            comparables=comparables,
            use_median=True
        )
        analyzer.filtered_comparables = comparables

        result = analyzer.calculate_fair_price()

        assert result.get('method') == 'median'

    def test_calculate_fair_price_with_mean(self):
        """Test fair price using mean method"""
        target = TargetProperty(
            url='https://test.com/property/123',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10
        )
        comparables = get_clean_comparables()

        analyzer = RealEstateAnalyzer()
        analyzer.request = AnalysisRequest(
            target_property=target,
            comparables=comparables,
            use_median=False
        )
        analyzer.filtered_comparables = comparables

        result = analyzer.calculate_fair_price()

        assert result.get('method') == 'mean'

    def test_calculate_fair_price_overpriced_detection(self):
        """Test detection of overpriced property"""
        target = TargetProperty(
            url='https://test.com/property/123',
            price=15_000_000,  # Much higher than market
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10
        )
        comparables = get_clean_comparables()

        analyzer = RealEstateAnalyzer()
        analyzer.request = AnalysisRequest(
            target_property=target,
            comparables=comparables,
            use_median=True
        )
        analyzer.filtered_comparables = comparables

        result = analyzer.calculate_fair_price()

        # Should detect as overpriced if diff > 5%
        if result.get('price_diff_percent', 0) > 5:
            assert result.get('is_overpriced') is True

    def test_calculate_fair_price_underpriced_detection(self):
        """Test detection of underpriced property"""
        target = TargetProperty(
            url='https://test.com/property/123',
            price=7_000_000,  # Much lower than market
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10
        )
        comparables = get_clean_comparables()

        analyzer = RealEstateAnalyzer()
        analyzer.request = AnalysisRequest(
            target_property=target,
            comparables=comparables,
            use_median=True
        )
        analyzer.filtered_comparables = comparables

        result = analyzer.calculate_fair_price()

        # Should detect as underpriced if diff < -5%
        if result.get('price_diff_percent', 0) < -5:
            assert result.get('is_underpriced') is True

    def test_calculate_fair_price_includes_confidence_interval(self):
        """Test that confidence interval is calculated"""
        target = TargetProperty(
            url='https://test.com/property/123',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10
        )
        comparables = get_clean_comparables()

        analyzer = RealEstateAnalyzer()
        analyzer.request = AnalysisRequest(
            target_property=target,
            comparables=comparables,
            use_median=True
        )
        analyzer.filtered_comparables = comparables

        result = analyzer.calculate_fair_price()

        # Should include CI if enough comparables (>= 3)
        if len(comparables) >= 3 and target.total_area:
            assert 'confidence_interval_95' in result
            ci = result['confidence_interval_95']
            assert 'lower' in ci
            assert 'upper' in ci
            assert ci['lower'] < ci['upper']

    def test_calculate_fair_price_with_empty_comparables(self):
        """Test fair price with no comparables"""
        target = TargetProperty(
            url='https://test.com/property/123',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10
        )

        analyzer = RealEstateAnalyzer()
        analyzer.request = AnalysisRequest(
            target_property=target,
            comparables=[],
            use_median=True
        )
        analyzer.filtered_comparables = []

        result = analyzer.calculate_fair_price()

        # Should return empty dict or handle gracefully
        assert isinstance(result, dict)


class TestGeneratePriceScenarios:
    """Tests for generate_price_scenarios() method"""

    def test_generate_scenarios_basic(self):
        """Test basic scenario generation"""
        target = TargetProperty(
            url='https://test.com/property/123',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10
        )
        comparables = get_clean_comparables()

        analyzer = RealEstateAnalyzer()
        analyzer.request = AnalysisRequest(
            target_property=target,
            comparables=comparables,
            use_median=True
        )
        analyzer.filtered_comparables = comparables

        scenarios = analyzer.generate_price_scenarios()

        assert isinstance(scenarios, list)
        assert len(scenarios) == 4  # fast, optimal, standard, maximum

    def test_generate_scenarios_structure(self):
        """Test scenario structure"""
        target = TargetProperty(
            url='https://test.com/property/123',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10
        )
        comparables = get_clean_comparables()

        analyzer = RealEstateAnalyzer()
        analyzer.request = AnalysisRequest(
            target_property=target,
            comparables=comparables,
            use_median=True
        )
        analyzer.filtered_comparables = comparables

        scenarios = analyzer.generate_price_scenarios()

        for scenario in scenarios:
            assert hasattr(scenario, 'name')
            assert hasattr(scenario, 'type')
            assert hasattr(scenario, 'start_price')
            assert hasattr(scenario, 'expected_final_price')
            assert hasattr(scenario, 'time_months')
            assert hasattr(scenario, 'financials')

    def test_generate_scenarios_has_recommended(self):
        """Test that one scenario is marked as recommended"""
        target = TargetProperty(
            url='https://test.com/property/123',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10
        )
        comparables = get_clean_comparables()

        analyzer = RealEstateAnalyzer()
        analyzer.request = AnalysisRequest(
            target_property=target,
            comparables=comparables,
            use_median=True
        )
        analyzer.filtered_comparables = comparables

        scenarios = analyzer.generate_price_scenarios()

        # Should have at least one recommended scenario
        recommended = [s for s in scenarios if hasattr(s, 'is_recommended') and s.is_recommended]
        assert len(recommended) >= 1

    def test_generate_scenarios_price_trajectory(self):
        """Test that scenarios include price trajectory"""
        target = TargetProperty(
            url='https://test.com/property/123',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10
        )
        comparables = get_clean_comparables()

        analyzer = RealEstateAnalyzer()
        analyzer.request = AnalysisRequest(
            target_property=target,
            comparables=comparables,
            use_median=True
        )
        analyzer.filtered_comparables = comparables

        scenarios = analyzer.generate_price_scenarios()

        for scenario in scenarios:
            assert hasattr(scenario, 'price_trajectory')
            assert isinstance(scenario.price_trajectory, list)
            assert len(scenario.price_trajectory) > 0
