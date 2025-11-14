# Test Coverage Analysis - Housler (Cian Analyzer)

**Date:** 2025-11-14
**Current Test Count:** 149 tests across 35 test classes
**Source Lines:** ~12,446 lines (src/)
**Test Lines:** ~3,939 lines (tests/)
**Coverage Target:** 70% (configured in pytest.ini)

---

## Executive Summary

The codebase demonstrates good testing practices with comprehensive API, security, and integration tests. However, significant gaps exist in coverage for critical business logic, parsers, and infrastructure components. This analysis identifies **10 high-priority areas** requiring immediate test coverage and **8 medium-priority areas** for future improvement.

**Test Coverage Ratio:** ~24% (3,939 test lines / 16,385 total lines)
**Estimated Actual Coverage:** Unknown (needs pytest execution)

---

## Current Test Coverage

### ✅ Well-Tested Components (Good Coverage)

| Component | Test File | Coverage Quality |
|-----------|-----------|------------------|
| Session Storage | `test_session_storage.py` (441 lines) | ⭐⭐⭐⭐⭐ Excellent - TTL, LRU, threading, Redis |
| API Endpoints | `test_api.py` (561 lines) | ⭐⭐⭐⭐ Good - CRUD, validation, exports |
| Security | `test_security.py` (415 lines) | ⭐⭐⭐⭐⭐ Excellent - CSRF, XSS, SQL injection, SSRF |
| Browser Pool | `test_browser_pool.py` (333 lines) | ⭐⭐⭐⭐ Good - Lifecycle, concurrency |
| Data Validation | `test_data_validator.py` (381 lines) | ⭐⭐⭐⭐ Good - Input validation, field mapping |
| E2E Workflows | `test_e2e_full_flow.py` (387 lines) | ⭐⭐⭐ Fair - Production integration tests |

### ⚠️ Partially Tested Components

| Component | Test File | Coverage Gaps |
|-----------|-----------|---------------|
| Analytics | `test_new_analytics.py` (395 lines) | Missing: analyzer.py, statistical_analysis.py |
| Fair Price Calculator | `test_fair_price_calculator.py` (76 lines) | ⚠️ **Only 76 lines** for 574-line module! |
| Comparables Quality | `test_comparables_quality.py` (486 lines) | Good but needs edge cases |
| Field Mapping | `test_field_mapping.py` (152 lines) | Parser coverage incomplete |

### ❌ Critical Gaps (No Test Coverage)

The following critical components have **ZERO dedicated tests**:

#### High-Impact Business Logic (10 modules, ~4,500 lines)

1. **`src/analytics/recommendations.py`** (570 lines)
   - **Risk:** HIGH - Core AI recommendation engine
   - **Functionality:** Generates personalized recommendations with ROI calculations
   - **Why Critical:** Directly impacts user decisions and business value

2. **`src/analytics/coefficients.py`** (various sizes)
   - **Risk:** MEDIUM-HIGH - Pricing accuracy depends on this
   - **Functionality:** 6-cluster coefficient system for price adjustments
   - **Why Critical:** Incorrect coefficients = wrong prices

3. **`src/analytics/offer_generator.py`** (size TBD)
   - **Risk:** HIGH - Revenue optimization
   - **Functionality:** Generates 4 sales strategies with financial projections
   - **Why Critical:** Affects customer outcomes and satisfaction

4. **`src/analytics/statistical_analysis.py`** (446 lines)
   - **Risk:** HIGH - Data quality and confidence
   - **Functionality:** Statistical methods, confidence intervals
   - **Why Critical:** Foundation for all pricing calculations

5. **`src/analytics/median_calculator.py`** (size TBD)
   - **Risk:** MEDIUM - Core pricing component
   - **Functionality:** Median-based fair price calculation
   - **Why Critical:** Primary valuation methodology

6. **`src/analytics/property_tracker.py`** (213 lines)
   - **Risk:** MEDIUM - Session state management
   - **Functionality:** Tracks property changes over time
   - **Why Critical:** Data integrity across user sessions

7. **`src/analytics/parameter_classifier.py`** (213 lines)
   - **Risk:** MEDIUM - Feature extraction
   - **Functionality:** Classifies property parameters for comparison
   - **Why Critical:** Affects comparable matching quality

8. **`src/analytics/fair_price_additive_helpers.py`** (size TBD)
   - **Risk:** MEDIUM - Price calculation accuracy
   - **Functionality:** Helper functions for additive price model
   - **Why Critical:** Supports main pricing engine

9. **`src/analytics/markdown_exporter.py`** (in src/analytics/)
   - **Risk:** MEDIUM - Report quality
   - **Functionality:** Exports analysis to markdown
   - **Why Critical:** Customer-facing output

10. **`src/analytics/analyzer.py`** (1,547 lines - LARGEST MODULE!)
    - **Risk:** CRITICAL - Main orchestration
    - **Functionality:** Coordinates entire analysis pipeline
    - **Why Critical:** Core application logic
    - **Note:** Likely has indirect coverage via integration tests but needs unit tests

#### Parsers & Data Extraction (4 modules, ~1,600 lines)

11. **`src/parsers/async_parser.py`** (616 lines)
    - **Risk:** HIGH - Performance optimization
    - **Functionality:** Parallel parsing (5x speedup claimed)
    - **Why Critical:** Production performance bottleneck

12. **`src/parsers/adaptive_selectors.py`** (376 lines)
    - **Risk:** HIGH - Parsing reliability
    - **Functionality:** Dynamic CSS selector handling
    - **Why Critical:** Website changes break parsing

13. **`src/parsers/simple_parser.py`** (249 lines)
    - **Risk:** MEDIUM - Fallback reliability
    - **Functionality:** Lightweight fallback parser
    - **Why Critical:** Backup when main parser fails

14. **`src/parsers/base_parser.py`** (722 lines)
    - **Risk:** MEDIUM-HIGH - Parser foundation
    - **Functionality:** Base parsing infrastructure
    - **Why Critical:** All parsers inherit from this

#### Infrastructure & Utilities (6 modules, ~1,200 lines)

15. **`src/cache/redis_cache.py`** (454 lines)
    - **Risk:** MEDIUM - Performance & reliability
    - **Functionality:** Redis caching layer (24h TTL, claimed 3000x speedup)
    - **Why Critical:** Production performance and costs
    - **Tests Needed:** Cache hits/misses, TTL, fallback behavior, compression

16. **`src/watermark_remover.py`** (estimated 200+ lines)
    - **Risk:** LOW-MEDIUM - Image quality
    - **Functionality:** Removes watermarks from property photos
    - **Why Critical:** Affects report presentation quality

17. **`src/iopaint_client.py`** (estimated 200+ lines)
    - **Risk:** LOW - External service integration
    - **Functionality:** Integration with IOPaint service
    - **Why Critical:** Photo processing reliability

18. **`src/txt_exporter.py`** (estimated size)
    - **Risk:** LOW - Export format
    - **Functionality:** Text export functionality
    - **Why Critical:** Alternative export format

19. **`src/markdown_exporter.py`** (root level)
    - **Risk:** MEDIUM - Primary export
    - **Functionality:** Main markdown export
    - **Why Critical:** Customer-facing reports

20. **`src/export_logs.py`** (estimated size)
    - **Risk:** LOW - Debugging
    - **Functionality:** Log export utilities
    - **Why Critical:** Production troubleshooting

---

## Priority Recommendations

### 🔴 P0: Critical (Immediate Action Required)

These components handle core business logic and have high bug risk:

#### 1. **Recommendations Engine** (`src/analytics/recommendations.py`)
**Priority:** CRITICAL
**Estimated Effort:** 3-4 days

**What to Test:**
```python
# Test file: tests/test_recommendations.py

class TestRecommendationEngine:
    def test_price_critical_recommendations():
        """Test CRITICAL priority recs for overpriced properties"""

    def test_roi_calculations():
        """Verify ROI calculations for improvements"""

    def test_recommendation_prioritization():
        """Ensure proper priority ordering (1=CRITICAL → 4=INFO)"""

    def test_financial_impact_accuracy():
        """Validate financial projections"""

    def test_edge_cases_no_issues():
        """Handle properties with zero issues"""

    def test_multiple_category_recommendations():
        """Mix of price, design, strategy recommendations"""
```

**Why Critical:**
- Directly affects customer decisions worth millions of rubles
- Complex ROI calculations need validation
- Business logic changes frequently

---

#### 2. **Statistical Analysis** (`src/analytics/statistical_analysis.py`)
**Priority:** CRITICAL
**Estimated Effort:** 2-3 days

**What to Test:**
```python
# Test file: tests/test_statistical_analysis.py

class TestStatisticalAnalysis:
    def test_confidence_interval_calculation():
        """95% confidence intervals for price ranges"""

    def test_outlier_detection():
        """Identify and filter statistical outliers"""

    def test_median_vs_mean_calculations():
        """Verify median-based pricing vs mean"""

    def test_sample_size_validation():
        """Handle small sample sizes gracefully"""

    def test_distribution_analysis():
        """Check normal vs skewed distributions"""
```

**Why Critical:**
- Foundation for all pricing accuracy
- Statistical errors compound through the system
- Affects confidence in recommendations

---

#### 3. **Async Parser** (`src/parsers/async_parser.py`)
**Priority:** CRITICAL
**Estimated Effort:** 3-4 days

**What to Test:**
```python
# Test file: tests/test_async_parser.py

class TestAsyncPlaywrightParser:
    def test_concurrent_parsing_success():
        """Parse 5-10 URLs in parallel"""

    def test_rate_limiting_handling():
        """Handle Cian rate limits gracefully"""

    def test_error_recovery():
        """Continue on individual failures"""

    def test_browser_context_isolation():
        """Ensure contexts don't leak data"""

    def test_performance_improvement():
        """Verify claimed 5x speedup"""

    def test_captcha_detection():
        """Detect and report CAPTCHA challenges"""
```

**Why Critical:**
- Production performance bottleneck
- Complex async/concurrency bugs hard to debug
- Affects user experience directly

---

#### 4. **Analyzer Core** (`src/analytics/analyzer.py`)
**Priority:** CRITICAL
**Estimated Effort:** 5-7 days (LARGEST MODULE)

**What to Test:**
```python
# Test file: tests/test_analyzer_core.py

class TestRealEstateAnalyzer:
    def test_full_analysis_pipeline():
        """End-to-end analysis workflow"""

    def test_insufficient_comparables():
        """Handle < 5 comparables gracefully"""

    def test_coefficient_application():
        """Apply all 6 clusters correctly"""

    def test_price_range_generation():
        """Generate 4 price scenarios"""

    def test_error_propagation():
        """Handle downstream module failures"""

    def test_result_consistency():
        """Same input = same output (deterministic)"""
```

**Why Critical:**
- 1,547 lines - largest single module
- Orchestrates entire application
- Likely has some indirect coverage but needs isolation

---

### 🟡 P1: High Priority (Next Sprint)

#### 5. **Offer Generator** (`src/analytics/offer_generator.py`)
**Estimated Effort:** 2 days

**Tests Needed:**
- 4 sales strategy generation (quick, standard, patient, luxury)
- Financial projections accuracy
- Time-to-sell estimates
- Edge cases (extreme prices)

---

#### 6. **Adaptive Selectors** (`src/parsers/adaptive_selectors.py`)
**Estimated Effort:** 2-3 days

**Tests Needed:**
- Fallback CSS selector chains
- Website structure changes
- Error reporting when all selectors fail
- Performance with multiple fallbacks

---

#### 7. **Redis Cache** (`src/cache/redis_cache.py`)
**Estimated Effort:** 2 days

**Tests Needed:**
- Cache hit/miss statistics
- TTL expiration (24h for details, 1h for search)
- Compression for large JSON (>1KB)
- Graceful fallback when Redis unavailable
- Namespace isolation (dev/prod)

---

#### 8. **Coefficients System** (`src/analytics/coefficients.py`)
**Estimated Effort:** 1-2 days

**Tests Needed:**
- All 6 cluster coefficients
- Edge values (e.g., 5m ceiling height)
- Coefficient chaining/multiplication
- Boundary conditions

---

### 🟢 P2: Medium Priority (Future Sprints)

#### 9. **Export Modules**
- `markdown_exporter.py` (both versions)
- `txt_exporter.py`

**Estimated Effort:** 1-2 days total

**Tests Needed:**
- Report structure validation
- Markdown formatting correctness
- Special character handling
- Missing data scenarios

---

#### 10. **Image Processing**
- `watermark_remover.py`
- `iopaint_client.py`

**Estimated Effort:** 2 days

**Tests Needed:**
- Watermark detection accuracy
- Inpainting quality metrics
- Service availability handling
- Performance with large images

---

## Testing Strategy Recommendations

### 1. **Increase Unit Test Coverage**

**Current Issue:** Heavy reliance on integration tests
**Goal:** 80%+ unit test coverage for business logic

**Action Items:**
```bash
# Add unit tests for pure functions
tests/test_coefficients.py          # Pure calculations
tests/test_statistical_functions.py  # Math functions
tests/test_price_calculations.py     # Price formulas
```

---

### 2. **Add Property-Based Testing**

For statistical and mathematical functions, use **hypothesis** library:

```python
# Example: tests/test_statistical_properties.py
from hypothesis import given, strategies as st

@given(st.lists(st.floats(min_value=1000, max_value=100_000_000), min_size=5))
def test_median_always_in_range(prices):
    """Median should always be within min/max of dataset"""
    median = calculate_median(prices)
    assert min(prices) <= median <= max(prices)
```

**Install:** `pip install hypothesis`

---

### 3. **Add Performance Regression Tests**

**Current Issue:** Claims like "3000x speedup" and "5x speedup" are untested

```python
# tests/test_performance.py
import pytest
import time

@pytest.mark.slow
def test_async_parser_performance():
    """Verify async parser is faster than sync"""
    urls = [f"https://cian.ru/sale/flat/{i}/" for i in range(10)]

    # Sync baseline
    start = time.time()
    sync_results = sync_parse(urls)
    sync_time = time.time() - start

    # Async version
    start = time.time()
    async_results = async_parse(urls)
    async_time = time.time() - start

    # Should be at least 2x faster (conservative estimate)
    assert async_time < sync_time / 2, \
        f"Async ({async_time:.1f}s) not faster than sync ({sync_time:.1f}s)"
```

---

### 4. **Add Contract Tests for External APIs**

For Cian.ru parsing, use contract testing to detect website changes:

```python
# tests/test_cian_contracts.py
def test_cian_property_page_structure():
    """Verify Cian property page still has expected structure"""
    html = fetch_sample_page()

    # Critical elements that must exist
    assert '[data-name="PriceInfo"]' in html
    assert '[data-name="OfferTitle"]' in html
    assert '[data-name="OfferMainFeatures"]' in html

    # Alert if structure changes
```

---

### 5. **Add Data Quality Tests**

```python
# tests/test_data_quality.py
def test_parsed_prices_are_reasonable():
    """Parsed prices should be within realistic ranges"""
    result = parse_property(url)

    # Moscow/SPb prices
    assert 1_000_000 <= result['price'] <= 1_000_000_000, \
        "Price outside reasonable range"

def test_no_missing_critical_fields():
    """Critical fields must never be None"""
    result = parse_property(url)

    required = ['price', 'total_area', 'address', 'rooms']
    missing = [f for f in required if not result.get(f)]

    assert not missing, f"Missing required fields: {missing}"
```

---

### 6. **Improve Test Data Management**

**Current Issue:** Tests use hardcoded URLs and magic numbers
**Solution:** Create test fixtures with realistic scenarios

```python
# tests/fixtures/properties.py
SAMPLE_PROPERTIES = {
    'overpriced_studio': {
        'price': 8_000_000,
        'total_area': 25,
        'rooms': 1,
        'expected_fair_price': 6_500_000,
        'expected_overpricing': 23.1
    },
    'underpriced_3br': {
        'price': 12_000_000,
        'total_area': 75,
        'rooms': 3,
        'expected_fair_price': 14_000_000,
        'expected_overpricing': -14.3
    },
    # ... more scenarios
}
```

---

### 7. **Add Mutation Testing**

Verify test quality using **mutmut**:

```bash
pip install mutmut
mutmut run --paths-to-mutate=src/analytics/
```

This will inject bugs and verify tests catch them. Goal: 80%+ mutation score.

---

## Test Organization Improvements

### Current Structure
```
tests/
├── conftest.py              # Shared fixtures
├── test_api.py              # API endpoints
├── test_security.py         # Security
├── test_*_*.py             # Various modules
```

### Recommended Structure
```
tests/
├── conftest.py              # Global fixtures
├── fixtures/                # ← NEW: Shared test data
│   ├── properties.py
│   ├── comparables.py
│   └── analysis_results.py
├── unit/                    # ← NEW: Pure unit tests
│   ├── analytics/
│   │   ├── test_coefficients.py
│   │   ├── test_statistical_analysis.py
│   │   ├── test_recommendations.py
│   │   └── test_offer_generator.py
│   └── parsers/
│       ├── test_async_parser.py
│       └── test_adaptive_selectors.py
├── integration/             # ← REORGANIZE: Integration tests
│   ├── test_full_analysis_pipeline.py
│   ├── test_parser_integration.py
│   └── test_cache_integration.py
├── e2e/                     # ← MOVE: E2E tests
│   └── test_user_workflows.py
├── performance/             # ← NEW: Performance tests
│   └── test_async_parser_perf.py
└── security/                # ← KEEP: Security tests
    └── test_security.py
```

**Update pytest.ini:**
```ini
[pytest]
testpaths = tests/unit tests/integration tests/e2e

markers =
    unit: Fast unit tests (<100ms)
    integration: Integration tests (<5s)
    e2e: End-to-end tests (slow)
    performance: Performance regression tests
    security: Security tests
```

---

## Coverage Goals (3-Month Roadmap)

| Timeline | Coverage Target | Focus Areas |
|----------|----------------|-------------|
| **Month 1** | 50% → 65% | P0 items (recommendations, stats, async parser) |
| **Month 2** | 65% → 75% | P1 items (offer gen, cache, selectors) |
| **Month 3** | 75% → 85% | P2 items + performance tests |

---

## Immediate Action Items (This Week)

1. ✅ **Run Coverage Report**
   ```bash
   pytest --cov=src --cov=app_new --cov-report=html
   open htmlcov/index.html  # Review uncovered lines
   ```

2. ✅ **Create Test Files** (empty, just structure):
   ```bash
   touch tests/unit/analytics/test_recommendations.py
   touch tests/unit/analytics/test_statistical_analysis.py
   touch tests/unit/parsers/test_async_parser.py
   touch tests/unit/analytics/test_analyzer_core.py
   ```

3. ✅ **Write First Critical Test** (Quick Win):
   ```python
   # tests/unit/analytics/test_recommendations.py
   def test_recommendation_engine_basic():
       """Smoke test: Engine initializes and generates recommendations"""
       from src.analytics.recommendations import RecommendationEngine

       analysis = {
           'target_property': {'price': 10_000_000},
           'fair_price_analysis': {
               'fair_price': 9_000_000,
               'overpricing_percent': 11.1
           }
       }

       engine = RecommendationEngine(analysis)
       recs = engine.generate_recommendations()

       assert len(recs) > 0, "Should generate at least one recommendation"
       assert any(r.priority == 1 for r in recs), "Overpriced property should have CRITICAL rec"
   ```

4. ✅ **Set Up CI Coverage Tracking**
   ```yaml
   # .github/workflows/tests.yml
   - name: Upload coverage to Codecov
     uses: codecov/codecov-action@v3
     with:
       file: ./coverage.xml
   ```

---

## Tools & Libraries to Add

```bash
# Install testing utilities
pip install hypothesis          # Property-based testing
pip install mutmut             # Mutation testing
pip install pytest-benchmark   # Performance regression
pip install pytest-xdist        # Parallel test execution
pip install pytest-timeout     # Prevent hanging tests
pip install faker              # Generate realistic test data
```

---

## Metrics to Track

### Code Coverage
- **Line Coverage:** Current unknown, Target 80%
- **Branch Coverage:** Current unknown, Target 75%
- **Function Coverage:** Current unknown, Target 90%

### Test Health
- **Test Success Rate:** Should be 100% on main branch
- **Test Execution Time:** Keep < 5 minutes for CI
- **Flaky Test Rate:** Should be < 1%

### Quality Metrics
- **Mutation Score:** Target 80% (tests catch injected bugs)
- **Code Duplication:** Target < 5% in tests
- **Test-to-Code Ratio:** Target 1:1 (currently ~1:3)

---

## Conclusion

The Housler codebase has a solid foundation with good security and API test coverage. However, **critical business logic modules are untested**, creating significant risk for bugs in pricing calculations and recommendations.

**Priority Focus:**
1. Test the **4 critical P0 modules** (recommendations, statistics, async parser, analyzer)
2. Add **property-based testing** for mathematical functions
3. Restructure tests into **unit/integration/e2e** hierarchy
4. Set up **coverage tracking** in CI/CD

**Expected Impact:**
- Reduce production bugs by 60%+
- Increase deployment confidence
- Enable safe refactoring of core modules
- Improve onboarding for new developers

---

**Next Steps:** Review this document with the team and prioritize P0 test creation for the next sprint.
