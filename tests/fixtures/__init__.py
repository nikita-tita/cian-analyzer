"""Test fixtures for unit tests"""

from .sample_data import (
    get_overpriced_analysis,
    get_fair_priced_analysis,
    get_underpriced_analysis,
    get_needs_improvement_analysis,
    get_clean_comparables,
    get_comparables_with_outliers,
    get_small_sample,
    get_high_variance_comparables,
)

__all__ = [
    'get_overpriced_analysis',
    'get_fair_priced_analysis',
    'get_underpriced_analysis',
    'get_needs_improvement_analysis',
    'get_clean_comparables',
    'get_comparables_with_outliers',
    'get_small_sample',
    'get_high_variance_comparables',
]
