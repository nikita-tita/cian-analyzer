# Unit Tests

Unit tests for individual modules and functions.

## Structure

```
unit/
├── analytics/
│   ├── test_recommendations.py      - RecommendationEngine tests (66.5% coverage)
│   └── test_statistical_analysis.py - Statistical functions tests (65.3% coverage)
└── parsers/
    └── (future parser tests)
```

## Running Tests

```bash
# Run all unit tests
pytest tests/unit/ -v

# Run with coverage
pytest tests/unit/ --cov=src --cov-report=html

# Run specific module tests
pytest tests/unit/analytics/test_recommendations.py -v
pytest tests/unit/analytics/test_statistical_analysis.py -v
```

## Test Results

**Total tests created:** 83
**Passing:** 52 (62.6%)
**Failing:** 31 (37.4%) - due to API mismatches, will be fixed

### Coverage Achieved

- **recommendations.py:** 66.50% (151 statements, 42 missed)
- **statistical_analysis.py:** 65.34% (128 statements, 40 missed)

## Test Fixtures

Reusable test data located in `tests/fixtures/sample_data.py`:

- `get_overpriced_analysis()` - Property 20% over market
- `get_fair_priced_analysis()` - Fair market price
- `get_underpriced_analysis()` - 11% below market
- `get_needs_improvement_analysis()` - Needs design, photos
- `get_clean_comparables()` - Normal distribution, no outliers
- `get_comparables_with_outliers()` - Includes 2 statistical outliers
- `get_small_sample()` - Small dataset (< 5 items)
- `get_high_variance_comparables()` - High CV dataset

## Test Coverage by Category

### recommendations.py

✅ **Well tested:**
- Recommendation dataclass (to_dict, priority labels)
- Engine initialization
- Pricing recommendations (critical, high, medium, info)
- Improvement recommendations (ROI calculations)
- Presentation recommendations
- Opportunity cost calculations

⚠️ **Partially tested:**
- Strategy recommendations (API mismatch with fixtures)
- Edge cases (some fail on API issues)

❌ **Not tested:**
- Integration with actual analysis results
- Adjustment context analysis

### statistical_analysis.py

✅ **Well tested:**
- IQR outlier detection (clean data, outliers, edge cases)
- Data quality calculation
- Distribution statistics (mean, median, std, quartiles)
- Statistical accuracy (vs. Python stdlib)
- Coefficient of variation
- Edge cases (small samples, identical values)

⚠️ **Partially tested:**
- Data sufficiency checks (function signature mismatch)
- Segment analysis (function doesn't exist or different API)

## Next Steps

1. **Fix API mismatches** - Update fixtures for `price_scenarios` structure
2. **Complete recommendations coverage** - Test strategy and adjustments
3. **Add parser tests** - `async_parser.py`, `adaptive_selectors.py`
4. **Increase to 80%+** - Add missing edge cases
5. **Add property-based tests** - Use `hypothesis` for statistical functions

## Known Issues

1. `price_scenarios` in fixtures should have `financials` attribute (currently dict)
2. `check_data_sufficiency` and `analyze_by_segments` function signatures differ from expected
3. Some CV assertions use different units (0.17 vs 17%)
4. Pydantic validation prevents negative price testing (by design, good!)
