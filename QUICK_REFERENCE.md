# Quick Reference Guide - Key File Locations

## STEP 2 & 3 LOGIC (Main Issue Areas)

### Step 2: Find Comparables
**Frontend:**
- `/home/user/cian-analyzer/static/js/wizard.js` **lines 386-558** (screen2 object)
- Main function: `screen2.findSimilar()` (lines 394-422)

**Backend:**
- `/home/user/cian-analyzer/app_new.py` **lines 796-900** (`/api/find-similar` endpoint)
- Parallel parsing: `app_new.py` **lines 854-874**
- Parser import: `src/parsers/async_parser.py`

**What might be hanging:**
1. Parallel parsing taking too long
2. CIAN search query hanging
3. URL parsing timeout

**Debug logging markers in code:**
- Line 852: `🔍 DEBUG: {len(similar)} comparables found`
- Line 857: `🚀 Parallel parsing {len(urls_to_parse)} URLs...`
- Line 874: `✓ Enhanced {len(detailed_results)} comparables`

---

### Step 3: Run Analysis
**Frontend:**
- `/home/user/cian-analyzer/static/js/wizard.js` **lines 561-845** (screen3 object)
- Main function: `screen3.runAnalysis()` (lines 620-649)

**Backend:**
- `/home/user/cian-analyzer/app_new.py` **lines 1051-1198** (`/api/analyze` endpoint)
- **Lines 1118-1184** contain heavy debug logging with 🔧 markers

**Analysis Pipeline:**
1. Validate data (Pydantic) - lines 1084-1115
2. Filter outliers - calls `analyzer._filter_outliers()` (line 122)
3. Calculate statistics - line 157
4. Calculate fair price - line 158
5. Generate scenarios - line 159
6. Return results - lines 1187-1190

**What might be hanging:**
1. Recommendations engine (line 201 - DISABLED temporarily)
2. Large dataset processing
3. Statistical calculations with scipy

**Debug logging markers:**
- Line 1118: `🔧 DEBUG: Создаю analyzer...`
- Line 1121: `🔧 DEBUG: Запускаю analyzer.analyze()...`
- Line 1143: `🔧 DEBUG: Конвертирую result в dict...`

---

## CRITICAL FILES

### API Entry Point
`/home/user/cian-analyzer/app_new.py` - **1,520 lines**
- Lines 44-54: Secret key setup
- Lines 64-93: Redis cache + browser pool init
- Lines 99-120: Rate limiting key generation
- Lines 386-388: Index route
- Lines 564-1424: All API endpoints

### Wizard Frontend
`/home/user/cian-analyzer/static/js/wizard.js` - **1,583 lines**
- Lines 7-13: Global state
- Lines 16-54: Utils (showLoading, showToast, etc.)
- Lines 57-91: Navigation logic
- Lines 94-383: Screen 1 (Parsing)
- Lines 386-558: Screen 2 (Comparables)
- Lines 561-845: Screen 3 (Analysis)
- Lines 847-906: Floating buttons + init

### Analytics Engine
`/home/user/cian-analyzer/src/analytics/analyzer.py` - **1,090 lines**
- Lines 43-85: RealEstateAnalyzer class init
- Lines 87-232: Main analyze() method
- Lines 234-285: _filter_outliers() method
- Lines 287-297: _calculate_confidence_interval()

### Data Models
`/home/user/cian-analyzer/src/models/property.py` - **474 lines**
- Lines 10-68: PropertyBase (Pydantic model)
- Lines 70-180: TargetProperty with clusters
- Lines 182+: ComparableProperty, AnalysisRequest, AnalysisResult

### Error Messages
`/home/user/cian-analyzer/static/js/error-messages.js` - **259 lines**
- Lines 6-106: ERROR_MESSAGES dictionary
- Lines 113-156: translateTechnicalError()
- Lines 164-180: getErrorMessage()

### Session Storage
`/home/user/cian-analyzer/src/utils/session_storage.py` - **263 lines**
- Lines 32-85: SessionStorage class + Redis init
- Lines 125-160: set() method (with TTL)
- Lines 165-200: get() method (checks TTL)
- Lines 235-251: get_stats() method

### Logging Configuration
`/home/user/cian-analyzer/app_new.py` - **lines 9-17**
```python
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
```

---

## API ENDPOINTS CHEAT SHEET

| Endpoint | Method | File:Line | Step |
|----------|--------|-----------|------|
| /health | GET | app:391 | Monitor |
| /metrics | GET | app:524 | Monitor |
| /api/csrf-token | GET | app:509 | Security |
| /api/parse | POST | app:564 | 1 |
| /api/create-manual | POST | app:640 | 1 |
| /api/update-target | POST | app:748 | 1→2 |
| /api/find-similar | POST | app:796 | 2 |
| /api/add-comparable | POST | app:903 | 2 |
| /api/exclude-comparable | POST | app:969 | 2 |
| /api/include-comparable | POST | app:1010 | 2 |
| /api/analyze | POST | app:1051 | 3 |
| /api/export-report/<id> | GET | app:1284 | 3 |
| /api/cache/stats | GET | app:1221 | Monitor |
| /api/cache/clear | POST | app:1251 | Admin |

---

## TESTING

**Test Framework:** pytest
**Test Location:** `/home/user/cian-analyzer/tests/`

**Run All Tests:**
```bash
pytest /home/user/cian-analyzer/tests
```

**Test Files:**
- `test_api.py` - API endpoints
- `test_e2e_full_flow.py` - Full wizard flow
- `test_session_storage.py` - Session management
- `test_security.py` - Security features
- `test_new_analytics.py` - Analysis calculations
- `conftest.py` - Test fixtures

---

## ENVIRONMENT VARIABLES

Key vars for configuration:
- `FLASK_ENV` - 'development' or 'production'
- `SECRET_KEY` - CSRF protection (CRITICAL)
- `REDIS_ENABLED` - true/false for caching
- `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB` - Redis config
- `MAX_BROWSERS` - Browser pool size (default: 3)

---

## SECURITY FEATURES

1. **CSRF Protection** - app_new.py:56-62
2. **URL Validation** - app_new.py:149-206 (SSRF protection)
3. **Input Sanitization** - app_new.py:208-231
4. **Rate Limiting** - app_new.py:122-131
5. **Security Headers** - app_new.py:341-382
6. **Timeout Protection** - app_new.py:297-334 (60s limit per operation)

---

## LOGGING TIPS

To see debug logs during development:
```python
# In app_new.py or any module:
import logging
logger = logging.getLogger(__name__)
logger.info("Your message here")  # Will appear in console
logger.debug("Detailed info")     # Need to set level=DEBUG to see
logger.warning("Something concerning")
logger.error("Error occurred", exc_info=True)  # Include traceback
```

**Recent debug additions** (with emoji markers for easy finding):
- 🔍 - Search/filter operations
- 🚀 - Parallel operations
- ✓ - Success/completion
- 🔧 - Analysis operations

---

## PERFORMANCE NOTES

**Slow Areas:**
1. Step 2 finding similar properties (15s+ typical)
2. Step 3 analysis with 20+ comparables (varies)
3. Parallel parsing if CIAN rate-limited

**Optimization Tips:**
1. Cache comparable results (24h TTL)
2. Reduce max_concurrent from 2 to 1 if rate-limited
3. Use Redis for session storage (not memory)
4. Monitor with /metrics endpoint

---

## PRODUCTION CHECKLIST

- [ ] Set SECRET_KEY environment variable
- [ ] Enable Redis for session storage
- [ ] Configure REDIS_ENABLED=true
- [ ] Set FLASK_ENV=production
- [ ] Run behind Gunicorn (gthread workers)
- [ ] Set up security headers (already done in code)
- [ ] Enable rate limiting (already enabled)
- [ ] Configure log aggregation
- [ ] Set up monitoring with /health endpoint

