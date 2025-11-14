"""
Unit tests for data_validator.py - data quality validation system
"""

import pytest
from datetime import datetime
from src.analytics.data_validator import (
    # Constants
    MIN_PRICE_PER_SQM,
    MAX_PRICE_PER_SQM,
    MIN_TOTAL_AREA,
    MAX_TOTAL_AREA,
    MIN_TOTAL_PRICE,
    EXCLUDED_STATUSES,
    ALLOWED_STATUSES,
    # Functions
    validate_comparable,
    filter_valid_comparables,
    get_validation_summary,
    check_minimum_comparables,
    validate_target_property,
)
from src.models.property import ComparableProperty, TargetProperty


class TestValidationConstants:
    """Tests for validation constants"""

    def test_price_per_sqm_ranges(self):
        """Test price per sqm ranges are reasonable"""
        assert MIN_PRICE_PER_SQM == 30_000
        assert MAX_PRICE_PER_SQM == 2_000_000
        assert MIN_PRICE_PER_SQM < MAX_PRICE_PER_SQM

    def test_area_ranges(self):
        """Test area ranges are reasonable"""
        assert MIN_TOTAL_AREA == 15
        assert MAX_TOTAL_AREA == 1000
        assert MIN_TOTAL_AREA < MAX_TOTAL_AREA

    def test_min_total_price(self):
        """Test minimum total price"""
        assert MIN_TOTAL_PRICE == 1_000_000

    def test_excluded_statuses(self):
        """Test excluded statuses set"""
        assert isinstance(EXCLUDED_STATUSES, set)
        assert 'проект' in EXCLUDED_STATUSES
        assert 'котлован' in EXCLUDED_STATUSES
        assert 'снесен' in EXCLUDED_STATUSES

    def test_allowed_statuses(self):
        """Test allowed statuses set"""
        assert isinstance(ALLOWED_STATUSES, set)
        assert 'готов' in ALLOWED_STATUSES
        assert 'отделка' in ALLOWED_STATUSES
        assert 'строительство' in ALLOWED_STATUSES


class TestValidateComparable:
    """Tests for validate_comparable() function"""

    def _create_valid_comparable(self):
        """Helper to create a valid comparable"""
        return ComparableProperty(
            url='https://test.com/property/1',
            price=10_000_000,
            total_area=60,
            price_per_sqm=166_667,
            rooms=2,
            floor=5,
            total_floors=10,
            object_status='готов'
        )

    def test_valid_comparable(self):
        """Test validation of a fully valid comparable"""
        comp = self._create_valid_comparable()
        is_valid, details = validate_comparable(comp)

        assert is_valid is True
        assert details['is_valid'] is True
        assert len(details['failures']) == 0
        assert details['completeness'] > 0

    def test_missing_price(self):
        """Test detection of missing price"""
        comp = self._create_valid_comparable()
        comp.price = None

        is_valid, details = validate_comparable(comp)

        assert is_valid is False
        assert 'Отсутствует цена' in details['failures']
        assert details['checks']['has_price'] is False

    def test_very_low_price(self):
        """Test detection of very low price (below MIN_TOTAL_PRICE)"""
        comp = ComparableProperty(
            url='https://test.com/property/1',
            price=500_000,  # Below MIN_TOTAL_PRICE but valid for Pydantic
            total_area=60,
            price_per_sqm=8_333,  # Will be below MIN_PRICE_PER_SQM
            rooms=2,
            floor=5,
            total_floors=10,
            object_status='готов'
        )

        is_valid, details = validate_comparable(comp)

        assert is_valid is False  # Fails due to low price/sqm and total price

    def test_missing_area(self):
        """Test detection of missing area"""
        comp = self._create_valid_comparable()
        comp.total_area = None

        is_valid, details = validate_comparable(comp)

        assert is_valid is False
        assert 'Отсутствует площадь' in details['failures']
        assert details['checks']['has_area'] is False

    def test_very_small_area(self):
        """Test detection of very small area (below MIN_TOTAL_AREA)"""
        comp = ComparableProperty(
            url='https://test.com/property/1',
            price=2_000_000,
            total_area=10,  # Below MIN_TOTAL_AREA (15) but valid for Pydantic
            price_per_sqm=200_000,
            rooms=1,
            floor=5,
            total_floors=10,
            object_status='готов'
        )

        is_valid, details = validate_comparable(comp)

        assert is_valid is False  # Fails due to area below MIN_TOTAL_AREA
        assert any('Площадь вне пределов' in f for f in details['failures'])

    def test_price_per_sqm_calculated(self):
        """Test that price_per_sqm is automatically calculated"""
        comp = ComparableProperty(
            url='https://test.com/property/1',
            price=10_000_000,
            total_area=60,
            # price_per_sqm will be automatically calculated
            rooms=2,
            floor=5,
            total_floors=10,
            object_status='готов'
        )

        is_valid, details = validate_comparable(comp)

        # Should be valid since price_per_sqm is calculated automatically
        assert details['checks']['has_price_per_sqm'] is True
        assert comp.price_per_sqm is not None
        assert comp.price_per_sqm > 0

    def test_price_per_sqm_too_low(self):
        """Test detection of unreasonably low price/sqm"""
        comp = self._create_valid_comparable()
        comp.price_per_sqm = 20_000  # Below MIN_PRICE_PER_SQM

        is_valid, details = validate_comparable(comp)

        assert is_valid is False
        assert any('вне пределов' in f for f in details['failures'])
        assert details['checks']['price_per_sqm_reasonable'] is False

    def test_price_per_sqm_too_high(self):
        """Test detection of unreasonably high price/sqm"""
        comp = self._create_valid_comparable()
        comp.price_per_sqm = 3_000_000  # Above MAX_PRICE_PER_SQM

        is_valid, details = validate_comparable(comp)

        assert is_valid is False
        assert any('вне пределов' in f for f in details['failures'])
        assert details['checks']['price_per_sqm_reasonable'] is False

    def test_area_too_small(self):
        """Test detection of unreasonably small area"""
        comp = self._create_valid_comparable()
        comp.total_area = 10  # Below MIN_TOTAL_AREA
        comp.price_per_sqm = comp.price / comp.total_area

        is_valid, details = validate_comparable(comp)

        assert is_valid is False
        assert any('Площадь вне пределов' in f for f in details['failures'])
        assert details['checks']['area_reasonable'] is False

    def test_area_too_large(self):
        """Test detection of unreasonably large area"""
        comp = self._create_valid_comparable()
        comp.total_area = 1500  # Above MAX_TOTAL_AREA
        comp.price_per_sqm = comp.price / comp.total_area

        is_valid, details = validate_comparable(comp)

        assert is_valid is False
        assert any('Площадь вне пределов' in f for f in details['failures'])
        assert details['checks']['area_reasonable'] is False

    def test_total_price_too_low(self):
        """Test detection of unreasonably low total price"""
        comp = self._create_valid_comparable()
        comp.price = 500_000  # Below MIN_TOTAL_PRICE
        comp.price_per_sqm = comp.price / comp.total_area

        is_valid, details = validate_comparable(comp)

        assert is_valid is False
        assert any('Цена слишком низкая' in f for f in details['failures'])
        assert details['checks']['total_price_reasonable'] is False

    def test_excluded_status(self):
        """Test detection of excluded object status"""
        comp = self._create_valid_comparable()
        comp.object_status = 'проект'  # In EXCLUDED_STATUSES

        is_valid, details = validate_comparable(comp)

        assert is_valid is False
        assert any('Недопустимый статус' in f for f in details['failures'])
        assert details['checks']['not_excluded_status'] is False

    def test_allowed_status_ready(self):
        """Test allowed status 'готов'"""
        comp = self._create_valid_comparable()
        comp.object_status = 'готов'

        is_valid, details = validate_comparable(comp)

        assert is_valid is True
        assert details['checks']['is_allowed_status'] is True

    def test_allowed_status_construction(self):
        """Test allowed status 'строительство'"""
        comp = self._create_valid_comparable()
        comp.object_status = 'строительство'

        is_valid, details = validate_comparable(comp)

        assert is_valid is True
        assert details['checks']['is_allowed_status'] is True

    def test_missing_status_allowed(self):
        """Test that missing status is allowed"""
        comp = self._create_valid_comparable()
        comp.object_status = None

        is_valid, details = validate_comparable(comp)

        assert is_valid is True  # Missing status doesn't fail validation
        assert details['checks']['not_excluded_status'] is True

    def test_completeness_all_fields(self):
        """Test completeness score with all optional fields"""
        comp = self._create_valid_comparable()
        comp.floor = 5
        comp.total_floors = 10
        comp.build_year = 2020

        is_valid, details = validate_comparable(comp)

        assert details['completeness'] == 100.0
        assert details['checks']['has_floor'] is True
        assert details['checks']['has_total_floors'] is True
        assert details['checks']['has_build_year'] is True

    def test_completeness_no_optional_fields(self):
        """Test completeness score with no optional fields"""
        comp = ComparableProperty(
            url='https://test.com/property/1',
            price=10_000_000,
            total_area=60,
            price_per_sqm=166_667,
            rooms=2,
            object_status='готов'
        )

        is_valid, details = validate_comparable(comp)

        assert details['completeness'] == 0.0

    def test_build_year_reasonable(self):
        """Test build year validation"""
        current_year = datetime.now().year

        # Valid year (recent)
        comp1 = self._create_valid_comparable()
        comp1.build_year = current_year - 5
        is_valid, details = validate_comparable(comp1)
        assert details['checks']['has_build_year'] is True

        # Future year (within +5 years allowed)
        comp2 = self._create_valid_comparable()
        comp2.build_year = current_year + 3
        is_valid, details = validate_comparable(comp2)
        assert details['checks']['has_build_year'] is True

        # Old but valid year (Pydantic allows >= 1800)
        comp3 = self._create_valid_comparable()
        comp3.build_year = 1900
        is_valid, details = validate_comparable(comp3)
        assert details['checks']['has_build_year'] is True

        # Future year beyond allowed range
        # (data_validator allows current_year + 5, but Pydantic may limit to 2030)
        comp4 = self._create_valid_comparable()
        # Use a year that's beyond validator's range but within Pydantic's limits
        test_year = min(current_year + 10, 2029)
        if test_year <= current_year + 5:
            # If we can't test beyond range, just verify current implementation
            comp4.build_year = current_year + 4
            is_valid, details = validate_comparable(comp4)
            assert details['checks']['has_build_year'] is True
        else:
            comp4.build_year = test_year
            is_valid, details = validate_comparable(comp4)
            assert details['checks']['has_build_year'] is False


class TestFilterValidComparables:
    """Tests for filter_valid_comparables() function"""

    def _create_valid_comparable(self, index=1):
        """Helper to create a valid comparable"""
        return ComparableProperty(
            url=f'https://test.com/property/{index}',
            price=10_000_000,
            total_area=60,
            price_per_sqm=166_667,
            rooms=2,
            floor=5,
            total_floors=10,
            object_status='готов'
        )

    def test_all_valid_comparables(self):
        """Test filtering with all valid comparables"""
        comparables = [self._create_valid_comparable(i) for i in range(5)]

        valid, excluded = filter_valid_comparables(comparables, verbose=False)

        assert len(valid) == 5
        assert len(excluded) == 0

    def test_all_invalid_comparables(self):
        """Test filtering with all invalid comparables"""
        comparables = []
        for i in range(3):
            comp = self._create_valid_comparable(i)
            comp.price = None  # Make invalid
            comparables.append(comp)

        valid, excluded = filter_valid_comparables(comparables, verbose=False)

        assert len(valid) == 0
        assert len(excluded) == 3

    def test_mixed_valid_invalid(self):
        """Test filtering with mixed valid/invalid"""
        comparables = []

        # 3 valid
        for i in range(3):
            comparables.append(self._create_valid_comparable(i))

        # 2 invalid
        for i in range(3, 5):
            comp = self._create_valid_comparable(i)
            comp.total_area = None  # Make invalid
            comparables.append(comp)

        valid, excluded = filter_valid_comparables(comparables, verbose=False)

        assert len(valid) == 3
        assert len(excluded) == 2

    def test_excluded_reports_structure(self):
        """Test structure of excluded reports"""
        comp = self._create_valid_comparable()
        comp.price = None  # Make invalid

        valid, excluded = filter_valid_comparables([comp], verbose=False)

        assert len(excluded) == 1
        report = excluded[0]
        assert 'is_valid' in report
        assert 'checks' in report
        assert 'failures' in report
        assert 'completeness' in report
        assert report['is_valid'] is False

    def test_empty_list(self):
        """Test filtering empty list"""
        valid, excluded = filter_valid_comparables([], verbose=False)

        assert len(valid) == 0
        assert len(excluded) == 0


class TestGetValidationSummary:
    """Tests for get_validation_summary() function"""

    def _create_valid_comparable(self, index=1):
        """Helper to create a valid comparable"""
        return ComparableProperty(
            url=f'https://test.com/property/{index}',
            price=10_000_000,
            total_area=60,
            price_per_sqm=166_667,
            rooms=2,
            floor=5,
            total_floors=10,
            object_status='готов'
        )

    def test_summary_all_valid(self):
        """Test summary with all valid comparables"""
        comparables = [self._create_valid_comparable(i) for i in range(5)]

        summary = get_validation_summary(comparables)

        assert summary['total'] == 5
        assert summary['valid'] == 5
        assert summary['invalid'] == 0
        assert summary['valid_percentage'] == 100.0
        assert len(summary['issues']) == 0

    def test_summary_all_invalid(self):
        """Test summary with all invalid comparables"""
        comparables = []
        for i in range(3):
            comp = self._create_valid_comparable(i)
            comp.price = None  # Make invalid
            comparables.append(comp)

        summary = get_validation_summary(comparables)

        assert summary['total'] == 3
        assert summary['valid'] == 0
        assert summary['invalid'] == 3
        assert summary['valid_percentage'] == 0.0
        assert len(summary['issues']) > 0

    def test_summary_mixed(self):
        """Test summary with mixed valid/invalid"""
        comparables = []

        # 7 valid
        for i in range(7):
            comparables.append(self._create_valid_comparable(i))

        # 3 invalid
        for i in range(7, 10):
            comp = self._create_valid_comparable(i)
            comp.total_area = None  # Make invalid
            comparables.append(comp)

        summary = get_validation_summary(comparables)

        assert summary['total'] == 10
        assert summary['valid'] == 7
        assert summary['invalid'] == 3
        assert summary['valid_percentage'] == 70.0

    def test_summary_empty_list(self):
        """Test summary with empty list"""
        summary = get_validation_summary([])

        assert summary['total'] == 0
        assert summary['valid'] == 0
        assert summary['invalid'] == 0
        assert summary['valid_percentage'] == 0.0
        assert summary['avg_completeness'] == 0.0
        assert len(summary['issues']) == 0

    def test_summary_avg_completeness(self):
        """Test average completeness calculation"""
        comparables = []

        # One with all fields
        comp1 = self._create_valid_comparable(1)
        comp1.floor = 5
        comp1.total_floors = 10
        comp1.build_year = 2020
        comparables.append(comp1)

        # One with no optional fields
        comp2 = ComparableProperty(
            url='https://test.com/property/2',
            price=10_000_000,
            total_area=60,
            price_per_sqm=166_667,
            rooms=2,
            object_status='готов'
        )
        comparables.append(comp2)

        summary = get_validation_summary(comparables)

        # Average of 100% and 0% = 50%
        assert summary['avg_completeness'] == 50.0

    def test_summary_issues_aggregation(self):
        """Test that issues are properly aggregated"""
        comparables = []

        # 2 with missing price
        for i in range(2):
            comp = self._create_valid_comparable(i)
            comp.price = None
            comparables.append(comp)

        # 1 with missing area
        comp = self._create_valid_comparable(3)
        comp.total_area = None
        comparables.append(comp)

        summary = get_validation_summary(comparables)

        assert summary['invalid'] == 3
        assert 'Отсутствует цена' in summary['issues']
        assert 'Отсутствует площадь' in summary['issues']
        assert summary['issues']['Отсутствует цена'] == 2
        assert summary['issues']['Отсутствует площадь'] == 1


class TestCheckMinimumComparables:
    """Tests for check_minimum_comparables() function"""

    def _create_comparable(self, index=1):
        """Helper to create a comparable"""
        return ComparableProperty(
            url=f'https://test.com/property/{index}',
            price=10_000_000,
            total_area=60,
            price_per_sqm=166_667,
            rooms=2,
            floor=5,
            total_floors=10
        )

    def test_sufficient_comparables(self):
        """Test with sufficient comparables"""
        comparables = [self._create_comparable(i) for i in range(10)]

        result = check_minimum_comparables(comparables, minimum=5, raise_error=False)
        assert result is True

    def test_insufficient_comparables_no_error(self):
        """Test with insufficient comparables, no error raised"""
        comparables = [self._create_comparable(i) for i in range(3)]

        result = check_minimum_comparables(comparables, minimum=5, raise_error=False)
        assert result is False

    def test_insufficient_comparables_with_error(self):
        """Test with insufficient comparables, error raised"""
        comparables = [self._create_comparable(i) for i in range(3)]

        with pytest.raises(ValueError) as excinfo:
            check_minimum_comparables(comparables, minimum=5, raise_error=True)

        assert 'Недостаточно аналогов' in str(excinfo.value)
        assert '3 < 5' in str(excinfo.value)

    def test_exact_minimum(self):
        """Test with exact minimum count"""
        comparables = [self._create_comparable(i) for i in range(5)]

        result = check_minimum_comparables(comparables, minimum=5, raise_error=False)
        assert result is True

    def test_empty_list(self):
        """Test with empty list"""
        with pytest.raises(ValueError):
            check_minimum_comparables([], minimum=1, raise_error=True)


class TestValidateTargetProperty:
    """Tests for validate_target_property() function"""

    def test_valid_target_property(self):
        """Test validation of a valid target property"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10
        )

        is_valid, issues = validate_target_property(target)

        assert is_valid is True
        assert len(issues) == 0

    def test_missing_area(self):
        """Test detection of missing area in target"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            rooms=2,
            floor=5,
            total_floors=10
        )
        target.total_area = None

        is_valid, issues = validate_target_property(target)

        assert is_valid is False
        assert any('площадь' in issue.lower() for issue in issues)

    def test_very_small_area(self):
        """Test detection of very small area in target (unusual but valid for Pydantic)"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=2_000_000,
            total_area=1,  # Very small but valid for Pydantic (>0)
            rooms=1,
            floor=5,
            total_floors=10
        )

        is_valid, issues = validate_target_property(target)

        # Should be valid from validate_target_property perspective
        # (it only checks total_area > 0, which is satisfied)
        assert is_valid is True

    def test_missing_floor_warning(self):
        """Test warning for missing floor (non-critical)"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            total_floors=10
        )
        target.floor = None

        is_valid, issues = validate_target_property(target)

        # Should still be valid but with warning
        assert is_valid is True
        assert any('этаж' in issue.lower() for issue in issues)

    def test_missing_total_floors_warning(self):
        """Test warning for missing total_floors (non-critical)"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5
        )
        target.total_floors = None

        is_valid, issues = validate_target_property(target)

        # Should still be valid but with warning
        assert is_valid is True
        assert any('этажей' in issue.lower() for issue in issues)
