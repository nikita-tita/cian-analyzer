"""
Unit tests for median_calculator.py - median calculation and comparison system
"""

import pytest
from src.analytics.median_calculator import (
    calculate_medians_from_comparables,
    compare_target_with_medians,
    get_readable_comparison_summary,
)
from src.models.property import ComparableProperty, TargetProperty


class TestCalculateMediansFromComparables:
    """Tests for calculate_medians_from_comparables() function"""

    def _create_comparables(self, count=5):
        """Helper to create comparables with varied parameters"""
        comparables = []
        for i in range(count):
            comp = ComparableProperty(
                url=f'https://test.com/comp/{i}',
                price=10_000_000 + (i * 100_000),
                total_area=60 + i,
                price_per_sqm=165_000 + (i * 1000),
                living_area=40 + i,
                rooms=2,
                floor=3 + i,
                total_floors=10,
                ceiling_height=2.7 + (i * 0.1),
                bathrooms=1 + (i % 2),
                repair_level='стандартная' if i % 2 == 0 else 'улучшенная',
                window_type='пластиковые',
                elevator_count='один' if i % 2 == 0 else 'два',
                view_type='дом',
                photo_type='реальные',
                object_status='готов',
                build_year=2018 + i
            )
            comparables.append(comp)
        return comparables

    def test_empty_list(self):
        """Test with empty comparables list"""
        medians = calculate_medians_from_comparables([])
        assert medians == {}

    def test_single_comparable(self):
        """Test with single comparable"""
        comparables = self._create_comparables(1)
        medians = calculate_medians_from_comparables(comparables)

        # Single value should be used as median
        assert medians['total_area'] == 60
        assert medians['floor'] == 3
        assert medians['repair_level'] == 'стандартная'

    def test_numeric_medians(self):
        """Test numeric parameter medians"""
        comparables = self._create_comparables(5)
        medians = calculate_medians_from_comparables(comparables)

        # With 5 values (60, 61, 62, 63, 64), median should be 62
        assert medians['total_area'] == 62
        # Floors (3, 4, 5, 6, 7), median should be 5
        assert medians['floor'] == 5

    def test_categorical_mode(self):
        """Test categorical parameter mode calculation"""
        comparables = []
        # Add more 'стандартная' than 'улучшенная'
        for i in range(7):
            comp = ComparableProperty(
                url=f'https://test.com/comp/{i}',
                price=10_000_000,
                total_area=60,
                price_per_sqm=165_000,
                rooms=2,
                floor=5,
                total_floors=10,
                repair_level='стандартная' if i < 5 else 'улучшенная'
            )
            comparables.append(comp)

        medians = calculate_medians_from_comparables(comparables)

        # 'стандартная' appears 5 times, 'улучшенная' 2 times
        assert medians['repair_level'] == 'стандартная'

    def test_categorical_tie_first_value(self):
        """Test categorical tie resolution (picks first encountered)"""
        comparables = []
        # Create a tie: 2x'стандартная', 2x'улучшенная'
        for i in range(4):
            comp = ComparableProperty(
                url=f'https://test.com/comp/{i}',
                price=10_000_000,
                total_area=60,
                price_per_sqm=165_000,
                rooms=2,
                floor=5,
                total_floors=10,
                repair_level='улучшенная' if i < 2 else 'стандартная'
            )
            comparables.append(comp)

        medians = calculate_medians_from_comparables(comparables)

        # Should pick first encountered in tie
        assert medians['repair_level'] in ['улучшенная', 'стандартная']

    def test_price_per_sqm_median(self):
        """Test price per sqm median calculation"""
        comparables = self._create_comparables(5)
        medians = calculate_medians_from_comparables(comparables)

        # Prices: 165k, 166k, 167k, 168k, 169k -> median 167k
        assert medians['price_per_sqm'] == 167_000

    def test_living_area_percent_median(self):
        """Test living area percent calculation"""
        comparables = self._create_comparables(5)
        medians = calculate_medians_from_comparables(comparables)

        # Should calculate percent and get median
        assert 'living_area_percent' in medians
        assert 50 < medians['living_area_percent'] < 80  # Reasonable range

    def test_build_year_median(self):
        """Test build year median"""
        comparables = self._create_comparables(5)
        medians = calculate_medians_from_comparables(comparables)

        # Years: 2018, 2019, 2020, 2021, 2022 -> median 2020
        assert medians['build_year'] == 2020

    def test_missing_optional_parameters(self):
        """Test with missing optional parameters"""
        comparables = [
            ComparableProperty(
                url='https://test.com/comp/1',
                price=10_000_000,
                total_area=60,
                price_per_sqm=165_000,
                rooms=2,
                floor=5,
                total_floors=10
                # No ceiling_height, bathrooms, etc.
            )
        ]

        medians = calculate_medians_from_comparables(comparables)

        # Should have basic parameters
        assert 'total_area' in medians
        assert 'floor' in medians
        # Should not have optional ones
        assert 'ceiling_height' not in medians
        assert 'bathrooms' not in medians

    def test_partial_data_availability(self):
        """Test with some comparables having data, some not"""
        comparables = []
        for i in range(5):
            comp = ComparableProperty(
                url=f'https://test.com/comp/{i}',
                price=10_000_000,
                total_area=60 + i,
                price_per_sqm=165_000,
                rooms=2,
                floor=5,
                total_floors=10
            )
            # Only add ceiling_height for some
            if i >= 2:
                comp.ceiling_height = 2.7 + (i * 0.1)
            comparables.append(comp)

        medians = calculate_medians_from_comparables(comparables)

        # Should calculate median only from available values (3 values)
        assert 'ceiling_height' in medians


class TestCompareTargetWithMedians:
    """Tests for compare_target_with_medians() function"""

    def test_numeric_equals_median(self):
        """Test numeric parameter equal to median"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10
        )

        medians = {
            'total_area': 60,
            'floor': 5
        }

        comparison = compare_target_with_medians(target, medians)

        assert 'total_area' in comparison
        assert comparison['total_area']['equals_median'] is True
        assert comparison['total_area']['direction'] == 'equals'
        assert comparison['floor']['equals_median'] is True

    def test_numeric_above_median(self):
        """Test numeric parameter above median"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=80,  # Above median
            rooms=2,
            floor=5,
            total_floors=10
        )

        medians = {
            'total_area': 60
        }

        comparison = compare_target_with_medians(target, medians)

        assert comparison['total_area']['equals_median'] is False
        assert comparison['total_area']['direction'] == 'above'
        assert comparison['total_area']['difference'] == 20

    def test_numeric_below_median(self):
        """Test numeric parameter below median"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=40,  # Below median
            rooms=2,
            floor=3,  # Below median
            total_floors=10
        )

        medians = {
            'total_area': 60,
            'floor': 5
        }

        comparison = compare_target_with_medians(target, medians)

        assert comparison['total_area']['direction'] == 'below'
        assert comparison['total_area']['difference'] == -20
        assert comparison['floor']['direction'] == 'below'
        assert comparison['floor']['difference'] == -2

    def test_categorical_equals_median(self):
        """Test categorical parameter equal to median"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10,
            repair_level='стандартная'
        )

        medians = {
            'repair_level': 'стандартная'
        }

        comparison = compare_target_with_medians(target, medians)

        assert comparison['repair_level']['equals_median'] is True
        assert comparison['repair_level']['direction'] == 'equals'

    def test_categorical_differs_median(self):
        """Test categorical parameter differs from median"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10,
            repair_level='премиум'
        )

        medians = {
            'repair_level': 'стандартная'
        }

        comparison = compare_target_with_medians(target, medians)

        assert comparison['repair_level']['equals_median'] is False
        assert comparison['repair_level']['direction'] == 'different'

    def test_living_area_percent_comparison(self):
        """Test living area percent comparison"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            living_area=45,  # 75%
            rooms=2,
            floor=5,
            total_floors=10
        )

        medians = {
            'living_area_percent': 60  # Median is 60%
        }

        comparison = compare_target_with_medians(target, medians)

        assert 'living_area_percent' in comparison
        assert comparison['living_area_percent']['target_value'] == 75.0
        assert comparison['living_area_percent']['median_value'] == 60
        assert comparison['living_area_percent']['direction'] == 'above'

    def test_missing_target_parameters(self):
        """Test when target is missing parameters in medians"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10
            # No ceiling_height
        )

        medians = {
            'ceiling_height': 2.7
        }

        comparison = compare_target_with_medians(target, medians)

        # Should not include ceiling_height since target doesn't have it
        assert 'ceiling_height' not in comparison

    def test_missing_median_values(self):
        """Test when medians don't have all target parameters"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10,
            ceiling_height=2.8
        )

        medians = {
            'total_area': 60
            # No ceiling_height in medians
        }

        comparison = compare_target_with_medians(target, medians)

        # Should only compare what's in medians
        assert 'total_area' in comparison
        assert 'ceiling_height' not in comparison

    def test_empty_medians(self):
        """Test with empty medians dict"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10
        )

        comparison = compare_target_with_medians(target, {})

        assert comparison == {}


class TestGetReadableComparisonSummary:
    """Tests for get_readable_comparison_summary() function"""

    def test_basic_summary(self):
        """Test basic readable summary generation"""
        comparison = {
            'total_area': {
                'target_value': 60,
                'median_value': 60,
                'equals_median': True,
                'direction': 'equals'
            },
            'floor': {
                'target_value': 7,
                'median_value': 5,
                'equals_median': False,
                'direction': 'above'
            }
        }

        summary = get_readable_comparison_summary(comparison)

        assert isinstance(summary, str)
        assert 'Сравнение' in summary
        assert 'total_area' in summary
        assert 'floor' in summary
        assert 'МЕДИАНА' in summary  # For total_area
        assert 'выше' in summary  # For floor

    def test_summary_with_below_direction(self):
        """Test summary with below median values"""
        comparison = {
            'total_area': {
                'target_value': 40,
                'median_value': 60,
                'equals_median': False,
                'direction': 'below'
            }
        }

        summary = get_readable_comparison_summary(comparison)

        assert 'ниже' in summary

    def test_summary_with_categorical(self):
        """Test summary with categorical parameters"""
        comparison = {
            'repair_level': {
                'target_value': 'премиум',
                'median_value': 'стандартная',
                'equals_median': False,
                'direction': 'different'
            }
        }

        summary = get_readable_comparison_summary(comparison)

        assert 'repair_level' in summary
        assert 'премиум' in summary
        assert 'стандартная' in summary
        assert 'отличается' in summary

    def test_summary_counts(self):
        """Test that summary includes counts"""
        comparison = {
            'total_area': {
                'target_value': 60,
                'median_value': 60,
                'equals_median': True,
                'direction': 'equals'
            },
            'floor': {
                'target_value': 5,
                'median_value': 5,
                'equals_median': True,
                'direction': 'equals'
            },
            'repair_level': {
                'target_value': 'премиум',
                'median_value': 'стандартная',
                'equals_median': False,
                'direction': 'different'
            }
        }

        summary = get_readable_comparison_summary(comparison)

        # Should show 2 equals, 1 differs
        assert '2 параметров = медиане' in summary
        assert '1 отличаются' in summary

    def test_summary_mentions_coefficients(self):
        """Test that summary mentions coefficients application"""
        comparison = {
            'total_area': {
                'target_value': 60,
                'median_value': 60,
                'equals_median': True,
                'direction': 'equals'
            }
        }

        summary = get_readable_comparison_summary(comparison)

        assert 'Коэффициенты' in summary
        assert 'отличающихся' in summary

    def test_empty_comparison(self):
        """Test summary with empty comparison"""
        summary = get_readable_comparison_summary({})

        assert isinstance(summary, str)
        assert '0 параметров = медиане' in summary
        assert '0 отличаются' in summary
