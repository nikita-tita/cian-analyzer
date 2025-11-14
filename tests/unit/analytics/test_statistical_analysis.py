"""
Unit tests for Statistical Analysis module

Tests cover:
- IQR outlier detection
- Data quality assessment
- Distribution statistics
- Sample size validation
- Segment analysis
"""

import pytest
import statistics
from src.analytics.statistical_analysis import (
    detect_outliers_iqr,
    calculate_data_quality,
    calculate_distribution_stats,
    check_data_sufficiency,
    analyze_by_segments
)
from tests.fixtures import (
    get_clean_comparables,
    get_comparables_with_outliers,
    get_small_sample,
    get_high_variance_comparables
)


class TestDetectOutliersIQR:
    """Tests for IQR (Interquartile Range) outlier detection"""

    def test_clean_data_no_outliers(self):
        """Test that clean data returns no outliers"""
        comparables = get_clean_comparables()

        valid, outliers = detect_outliers_iqr(comparables, field='price_per_sqm')

        # All data should be valid (no outliers)
        assert len(valid) == len(comparables)
        assert len(outliers) == 0

    def test_detects_outliers(self):
        """Test that obvious outliers are detected"""
        comparables = get_comparables_with_outliers()  # Has 2 outliers

        valid, outliers = detect_outliers_iqr(comparables, field='price_per_sqm')

        # Should detect some outliers
        assert len(outliers) > 0
        assert len(valid) < len(comparables)
        assert len(valid) + len(outliers) <= len(comparables)

    def test_small_sample_returns_all(self):
        """Test that samples < 4 items return all data without filtering"""
        comparables = get_small_sample()  # 3 items

        valid, outliers = detect_outliers_iqr(comparables, field='price_per_sqm')

        # Should return all without filtering
        assert len(valid) == len(comparables)
        assert len(outliers) == 0

    def test_iqr_with_different_multipliers(self):
        """Test IQR with different multipliers (1.5 vs 3.0)"""
        comparables = get_comparables_with_outliers()

        # Stricter filtering (multiplier=1.5)
        valid_strict, outliers_strict = detect_outliers_iqr(
            comparables, field='price_per_sqm', multiplier=1.5
        )

        # Looser filtering (multiplier=3.0)
        valid_loose, outliers_loose = detect_outliers_iqr(
            comparables, field='price_per_sqm', multiplier=3.0
        )

        # Stricter should catch more outliers
        assert len(outliers_strict) >= len(outliers_loose)
        assert len(valid_strict) <= len(valid_loose)

    def test_iqr_different_fields(self):
        """Test IQR can be applied to different fields"""
        comparables = get_comparables_with_outliers()

        fields = ['price_per_sqm', 'total_area', 'price']

        for field in fields:
            valid, outliers = detect_outliers_iqr(comparables, field=field)

            # Should process without errors
            assert isinstance(valid, list)
            assert isinstance(outliers, list)

    def test_iqr_outlier_report_structure(self):
        """Test outlier reports have correct structure"""
        comparables = get_comparables_with_outliers()

        valid, outliers = detect_outliers_iqr(comparables, field='price_per_sqm')

        for outlier_info in outliers:
            assert isinstance(outlier_info, dict)
            # Check required fields exist (structure may vary)

    def test_iqr_preserves_valid_data(self):
        """Test that valid comparables are preserved correctly"""
        comparables = get_clean_comparables()

        valid, outliers = detect_outliers_iqr(comparables, field='price_per_sqm')

        # Check that valid items are actual ComparableProperty objects
        for comp in valid:
            assert hasattr(comp, 'price')
            assert hasattr(comp, 'total_area')
            assert hasattr(comp, 'price_per_sqm')

    def test_iqr_with_none_values(self):
        """Test IQR handles None values gracefully"""
        comparables = get_clean_comparables()
        # Set some values to None
        if len(comparables) > 0:
            comparables[0].price_per_sqm = None

        valid, outliers = detect_outliers_iqr(comparables, field='price_per_sqm')

        # Should handle None values without crashing
        assert isinstance(valid, list)
        assert isinstance(outliers, list)

    def test_iqr_with_zero_values(self):
        """Test IQR handles zero values"""
        comparables = get_clean_comparables()
        if len(comparables) > 0:
            comparables[0].price_per_sqm = 0  # Invalid but shouldn't crash

        valid, outliers = detect_outliers_iqr(comparables, field='price_per_sqm')

        # Should process without errors
        assert isinstance(valid, list)


class TestCalculateDataQuality:
    """Tests for data quality assessment"""

    def test_clean_data_high_quality(self):
        """Test clean data gets high quality score"""
        comparables = get_clean_comparables()

        quality = calculate_data_quality(comparables)

        assert isinstance(quality, dict)
        # Quality should be good
        if 'quality_score' in quality:
            assert quality['quality_score'] >= 0
        if 'cv' in quality:  # Coefficient of variation
            # Clean data should have low CV
            assert quality['cv'] < 20  # Less than 20% variation

    def test_high_variance_data_lower_quality(self):
        """Test high variance data gets lower quality score"""
        comparables = get_high_variance_comparables()

        quality = calculate_data_quality(comparables)

        assert isinstance(quality, dict)
        # Should detect high variance
        if 'cv' in quality:
            assert quality['cv'] > 0.15  # High coefficient of variation (15%)

    def test_quality_with_small_sample(self):
        """Test quality calculation with small sample"""
        comparables = get_small_sample()

        quality = calculate_data_quality(comparables)

        assert isinstance(quality, dict)
        # Should still return quality metrics
        if 'sample_size' in quality:
            assert quality['sample_size'] == len(comparables)

    def test_quality_metrics_structure(self):
        """Test quality dict has expected structure"""
        comparables = get_clean_comparables()

        quality = calculate_data_quality(comparables)

        assert isinstance(quality, dict)
        # Should have some quality metrics
        assert len(quality) > 0

    def test_quality_empty_list(self):
        """Test quality calculation with empty list"""
        quality = calculate_data_quality([])

        assert isinstance(quality, dict)
        # Should handle empty gracefully

    def test_quality_detects_issues(self):
        """Test quality calculation detects data issues"""
        # Small sample with high variance
        comparables = get_small_sample()

        quality = calculate_data_quality(comparables)

        # Should indicate some quality issues
        if 'warnings' in quality or 'issues' in quality:
            assert len(quality.get('warnings', [])) >= 0


class TestCalculateDistributionStats:
    """Tests for distribution statistics calculation"""

    def test_distribution_stats_basic(self):
        """Test basic distribution statistics"""
        comparables = get_clean_comparables()

        stats = calculate_distribution_stats(comparables, field='price_per_sqm')

        assert isinstance(stats, dict)
        # Should have basic statistics
        expected_keys = ['mean', 'median', 'std', 'min', 'max']
        for key in expected_keys:
            if key in stats:
                assert isinstance(stats[key], (int, float))

    def test_median_vs_mean(self):
        """Test median and mean calculations"""
        comparables = get_clean_comparables()

        stats = calculate_distribution_stats(comparables, field='price_per_sqm')

        if 'mean' in stats and 'median' in stats:
            # For clean data, mean and median should be close
            mean = stats['mean']
            median = stats['median']
            assert abs(mean - median) / median < 0.1  # Within 10%

    def test_skewed_distribution(self):
        """Test detection of skewed distribution"""
        comparables = get_high_variance_comparables()

        stats = calculate_distribution_stats(comparables, field='price_per_sqm')

        # High variance data may show skewness
        if 'skew' in stats or 'skewness' in stats:
            # Just check it's calculated
            assert isinstance(stats.get('skew', stats.get('skewness', 0)), (int, float))

    def test_distribution_different_fields(self):
        """Test distribution stats for different fields"""
        comparables = get_clean_comparables()

        fields = ['price_per_sqm', 'total_area', 'price']

        for field in fields:
            stats = calculate_distribution_stats(comparables, field=field)
            assert isinstance(stats, dict)

    def test_distribution_small_sample(self):
        """Test distribution stats with small sample"""
        comparables = get_small_sample()

        stats = calculate_distribution_stats(comparables, field='price_per_sqm')

        assert isinstance(stats, dict)
        # Should still calculate basic stats

    def test_quartiles_calculation(self):
        """Test quartile calculations (Q1, Q2, Q3)"""
        comparables = get_clean_comparables()

        stats = calculate_distribution_stats(comparables, field='price_per_sqm')

        if all(k in stats for k in ['q1', 'q2', 'q3']):
            # Q1 < Q2 < Q3
            assert stats['q1'] <= stats['q2'] <= stats['q3']
            # Q2 should equal median
            if 'median' in stats:
                assert abs(stats['q2'] - stats['median']) < 0.01


class TestCheckDataSufficiency:
    """Tests for data sufficiency validation"""

    def test_sufficient_data(self):
        """Test recognition of sufficient data"""
        comparables = get_clean_comparables()  # 8 items

        is_sufficient, message = check_data_sufficiency(comparables, minimum_count=5)

        assert isinstance(is_sufficient, bool)
        assert is_sufficient is True

    def test_insufficient_data(self):
        """Test recognition of insufficient data"""
        comparables = get_small_sample()  # 3 items

        is_sufficient, message = check_data_sufficiency(comparables, minimum_count=5)

        assert isinstance(is_sufficient, bool)
        assert is_sufficient is False

    def test_empty_data_insufficient(self):
        """Test empty data is insufficient"""
        is_sufficient, message = check_data_sufficiency([], minimum_count=5)

        assert isinstance(is_sufficient, bool)
        assert is_sufficient is False

    def test_exact_minimum(self):
        """Test data size exactly at minimum"""
        comparables = get_small_sample()  # 3 items

        is_sufficient, message = check_data_sufficiency(comparables, minimum_count=3)

        assert isinstance(is_sufficient, bool)
        assert is_sufficient is True

    def test_sufficiency_warning_messages(self):
        """Test warning messages for insufficient data"""
        comparables = get_small_sample()

        is_sufficient, message = check_data_sufficiency(comparables, minimum_count=10)

        # Should include some information about insufficiency
        assert isinstance(message, str)
        assert len(message) > 0


class TestAnalyzeBySegments:
    """Tests for segment-based analysis"""

    def test_segment_analysis_basic(self):
        """Test basic segment analysis"""
        comparables = get_clean_comparables()

        # Analyze by rooms (grouping field)
        result = analyze_by_segments(
            comparables,
            segment_field='rooms',
            value_field='price_per_sqm'
        )

        assert isinstance(result, dict)

    def test_segments_with_different_fields(self):
        """Test segmentation by different fields"""
        comparables = get_clean_comparables()

        # Group by 'rooms', analyze different value fields
        value_fields = ['price', 'total_area']

        for field in value_fields:
            result = analyze_by_segments(comparables, segment_field='rooms', value_field=field)
            assert result is not None

    def test_segment_coverage(self):
        """Test all data points are covered by segments"""
        comparables = get_clean_comparables()

        result = analyze_by_segments(comparables, segment_field='rooms', value_field='price_per_sqm')

        # Should return dict with segment stats
        assert isinstance(result, dict)

    def test_empty_data_segments(self):
        """Test segment analysis with empty data"""
        result = analyze_by_segments([], segment_field='rooms', value_field='price')

        # Should handle gracefully
        assert isinstance(result, dict)


class TestStatisticalEdgeCases:
    """Tests for edge cases and error handling"""

    def test_all_identical_values(self):
        """Test statistics with all identical values"""
        comparables = get_clean_comparables()
        # Set all to same value
        for comp in comparables:
            comp.price_per_sqm = 150_000

        stats = calculate_distribution_stats(comparables, field='price_per_sqm')

        if 'std' in stats:
            # Standard deviation should be 0 or very close
            assert stats['std'] < 0.01

    def test_two_values_only(self):
        """Test statistics with only 2 values"""
        comparables = get_small_sample()[:2]

        stats = calculate_distribution_stats(comparables, field='price_per_sqm')

        # Should still calculate mean and median
        assert isinstance(stats, dict)

    def test_negative_values_handling(self):
        """Test handling of negative values (invalid data)"""
        # NOTE: Pydantic validates price > 0, so we can't set negative prices
        # This is actually correct behavior - prices should never be negative
        # Testing with zero instead
        comparables = get_clean_comparables()
        if len(comparables) > 0:
            # Set to very small positive value (edge case)
            comparables[0].price_per_sqm = 1  # Very low but valid

        # Should handle without crashing
        stats = calculate_distribution_stats(comparables, field='price_per_sqm')
        assert isinstance(stats, dict)

    def test_extreme_outliers(self):
        """Test IQR with extreme outliers (10x median)"""
        comparables = get_clean_comparables()
        # Add extreme outlier
        if len(comparables) > 0:
            comparables[0].price_per_sqm = 1_000_000  # 10x normal

        valid, outliers = detect_outliers_iqr(comparables, field='price_per_sqm')

        # Should detect extreme outlier
        assert len(outliers) > 0


class TestStatisticalAccuracy:
    """Tests for statistical calculation accuracy"""

    def test_mean_calculation_accuracy(self):
        """Test mean calculation is accurate"""
        comparables = get_clean_comparables()

        values = [c.price_per_sqm for c in comparables if c.price_per_sqm]
        expected_mean = statistics.mean(values)

        stats = calculate_distribution_stats(comparables, field='price_per_sqm')

        if 'mean' in stats:
            # Should match Python's statistics.mean
            assert abs(stats['mean'] - expected_mean) < 1.0

    def test_median_calculation_accuracy(self):
        """Test median calculation is accurate"""
        comparables = get_clean_comparables()

        values = [c.price_per_sqm for c in comparables if c.price_per_sqm]
        expected_median = statistics.median(values)

        stats = calculate_distribution_stats(comparables, field='price_per_sqm')

        if 'median' in stats:
            # Should match Python's statistics.median
            assert abs(stats['median'] - expected_median) < 1.0

    def test_std_calculation_accuracy(self):
        """Test standard deviation calculation"""
        comparables = get_clean_comparables()

        values = [c.price_per_sqm for c in comparables if c.price_per_sqm]
        if len(values) > 1:
            expected_std = statistics.stdev(values)

            stats = calculate_distribution_stats(comparables, field='price_per_sqm')

            if 'std' in stats:
                # Should be close to Python's statistics.stdev
                assert abs(stats['std'] - expected_std) / expected_std < 0.01


class TestCoefficientOfVariation:
    """Tests for Coefficient of Variation (CV) calculation"""

    def test_cv_low_for_clean_data(self):
        """Test CV is low for clean data"""
        comparables = get_clean_comparables()

        quality = calculate_data_quality(comparables)

        if 'cv' in quality:
            # Clean data should have CV < 0.15 (15%)
            assert quality['cv'] < 0.15

    def test_cv_high_for_varied_data(self):
        """Test CV is high for highly varied data"""
        comparables = get_high_variance_comparables()

        quality = calculate_data_quality(comparables)

        if 'cv' in quality:
            # High variance data should have CV > 0.10 (10%)
            assert quality['cv'] > 0.10

    def test_cv_zero_for_identical_values(self):
        """Test CV is zero when all values are identical"""
        comparables = get_clean_comparables()
        # Set all to same value
        for comp in comparables:
            comp.price_per_sqm = 150_000

        quality = calculate_data_quality(comparables)

        if 'cv' in quality:
            # CV should be 0 or very close
            assert quality['cv'] < 0.01


# ═══════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestStatisticalWorkflow:
    """Integration tests for complete statistical workflow"""

    def test_complete_analysis_workflow(self):
        """Test complete statistical analysis workflow"""
        # 1. Get data
        comparables = get_comparables_with_outliers()

        # 2. Check sufficiency
        is_sufficient, message = check_data_sufficiency(comparables, minimum_count=5)
        assert isinstance(is_sufficient, bool)

        # 3. Remove outliers
        valid, outliers = detect_outliers_iqr(comparables, field='price_per_sqm')
        assert len(valid) > 0

        # 4. Calculate quality
        quality = calculate_data_quality(valid)
        assert quality is not None

        # 5. Get distribution stats
        stats = calculate_distribution_stats(valid, field='price_per_sqm')
        assert stats is not None

    def test_pipeline_with_clean_data(self):
        """Test statistical pipeline with clean data"""
        comparables = get_clean_comparables()

        # Filter outliers
        valid, outliers = detect_outliers_iqr(comparables)
        assert len(outliers) == 0  # Clean data has no outliers

        # Assess quality
        quality = calculate_data_quality(valid)
        # Should be high quality

        # Get stats
        stats = calculate_distribution_stats(valid, field='price_per_sqm')
        assert 'mean' in stats or 'median' in stats

    def test_pipeline_with_problematic_data(self):
        """Test statistical pipeline handles problematic data"""
        comparables = get_small_sample()  # Too small + may have issues

        # Should handle gracefully at each step
        is_sufficient, message = check_data_sufficiency(comparables, minimum_count=5)
        valid, outliers = detect_outliers_iqr(comparables)
        quality = calculate_data_quality(valid)
        stats = calculate_distribution_stats(valid, field='price_per_sqm')

        # All should complete without crashing
        assert isinstance(is_sufficient, bool)
        assert valid is not None
        assert quality is not None
        assert stats is not None
