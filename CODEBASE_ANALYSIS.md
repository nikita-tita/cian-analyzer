# CIAN Analyzer - Comprehensive Codebase Analysis

## Executive Summary
This is a **Flask-based hybrid Python/JavaScript web application** for real estate property analysis. It implements a 3-step wizard flow (step 1: parsing, step 2: comparables, step 3: analysis) with comprehensive analytics, caching, and security features.

**Total Python Code:** ~9,755 lines
**Backend:** Flask (1,520 LOC in app_new.py)
**Frontend:** Vanilla JavaScript (~2,490 LOC across wizard.js files)
**Analytics:** Pydantic models + statistical analysis (~1,564 LOC)

---

## 1. WIZARD STEPS IMPLEMENTATION (ШАГИ)

### Architecture Overview
The wizard is a **3-screen sequential flow** implemented with:
- **Frontend:** Client-side state machine in JavaScript (browser)
- **Backend:** RESTful API endpoints + session storage (server)
- **Session Storage:** Redis-backed (with in-memory fallback) for persistence

### Step 1: Property Parsing (Парсинг - "Загрузка объекта")
**Location:** Frontend `/static/js/wizard.js` lines 94-383 (screen1 object)
**HTML Template:** `/templates/wizard.html` lines 58-279 (screen-1 div)

**Key Components:**

| Component | File | Lines | Purpose |
|-----------|------|-------|---------|
| Parse Handler | wizard.js | 167-201 | HTTP POST to `/api/parse` |
| Manual Input Form | wizard.js | 115-165 | Form submission to `/api/create-manual` |
| Result Display | wizard.js | 203-271 | Shows parsed property details |
| Missing Fields | wizard.js | 273-317 | Renders form for missing properties |
| Update Target | wizard.js | 319-382 | POST to `/api/update-target` (step 1→2) |

**Backend Logic:**
```
app_new.py lines:
  564-637: @app.route('/api/parse') - Parse CIAN URL
  640-745: @app.route('/api/create-manual') - Manual property creation
  748-793: @app.route('/api/update-target') - Update target properties
```

**Flow:**
1. User enters URL or clicks "Manual Input"
2. Frontend calls `/api/parse` (URL) or `/api/create-manual` (manual)
3. Backend parses property details, identifies missing fields
4. Returns session_id, property data, missing_fields list
5. Frontend renders missing field form (repair_level, view_type)
6. User submits form → `/api/update-target` call
7. State advances to Step 2

**Missing Fields Logic:**
Location: `/app_new.py` lines 1427-1486 (`_identify_missing_fields()`)
- 6 field clusters (20 fields total)
- Only critical fields for comparison: repair_level, view_type
- Checks both root properties and characteristics dict

---

### Step 2: Find Comparables (Аналоги - "Похожие объекты")
**Location:** Frontend `/static/js/wizard.js` lines 386-558 (screen2 object)
**HTML Template:** `/templates/wizard.html` lines 281-315 (screen-2 div)

**Key Components:**

| Component | File | Lines | Purpose |
|-----------|------|-------|---------|
| Find Similar | wizard.js | 394-422 | POST to `/api/find-similar` |
| Add Comparable | wizard.js | 424-460 | POST to `/api/add-comparable` |
| Render Comparables | wizard.js | 462-531 | Display list with exclude/include |
| Exclude Logic | wizard.js | 533-557 | POST to `/api/exclude-comparable` |

**Backend Logic:**
```
app_new.py lines:
  796-900: @app.route('/api/find-similar') - Auto-search similar properties
  903-966: @app.route('/api/add-comparable') - Manually add property
  969-1007: @app.route('/api/exclude-comparable') - Mark as excluded
  1010-1048: @app.route('/api/include-comparable') - Re-include property
```

**Flow:**
1. Frontend calls `/api/find-similar` with session_id
2. Backend uses Parser to search similar properties in building or city
3. Parallel parsing of URLs for detailed data (async_parser.py)
4. Returns list of comparable properties
5. User can exclude/include comparables before analysis
6. Click "K analizu" (To Analysis) button → Step 3

**Search Types:**
- `building`: Search in same residential complex
- `city`: Broader search across city

**Parallel Parsing:**
Location: `/app_new.py` lines 854-874
Uses `parse_multiple_urls_parallel()` from `src/parsers/async_parser.py`
- Max concurrent: 2 (to avoid CIAN rate limiting)
- Enrich comparables with price, area, price_per_sqm

---

### Step 3: Run Analysis (Анализ - "Полный анализ")
**Location:** Frontend `/static/js/wizard.js` lines 561-845 (screen3 object)
**HTML Template:** `/templates/wizard.html` lines 318+ (screen-3 div)

**Key Components:**

| Component | File | Lines | Purpose |
|-----------|------|-------|---------|
| Run Analysis | wizard.js | 620-649 | POST to `/api/analyze` |
| Display Analysis | wizard.js | 651-668 | Render results |
| Summary Display | wizard.js | 670-697 | Show market stats |
| Fair Price | wizard.js | 699-748 | Display pricing analysis |
| Scenarios | wizard.js | 750-780 | Price scenarios |
| Strengths/Weaknesses | wizard.js | 782-813 | Factor analysis |
| Chart Rendering | wizard.js | 815-844 | Chart.js visualization |

**Backend Logic:**
```
app_new.py lines:
  1051-1198: @app.route('/api/analyze') - MAIN ANALYSIS ENDPOINT
```

**Analysis Flow:**
1. Frontend POST to `/api/analyze` with session_id
2. Backend retrieves session (target + comparables)
3. **Data Validation:** Normalize + validate property consistency
4. **Filtering:** Remove outliers (±3σ rule if filter_outliers=true)
5. **Calculation Pipeline:**
   - Market statistics (mean, median, count)
   - Fair price analysis (adjusted for comparables)
   - Price scenarios (3-5 different pricing strategies)
   - Strengths/weaknesses analysis
   - Price range, attractiveness index, time forecast
6. Returns AnalysisResult JSON
7. Frontend renders charts, metrics, recommendations
8. User can download report via `/api/export-report/<session_id>`

**Analysis Components:**
Location: `/src/analytics/analyzer.py` lines 87-232
- Outlier filtering: lines 234-285
- Fair price calculation: line 158
- Market statistics: line 157
- Price scenarios: line 159
- Confidence intervals: lines 287-297

---

## 2. API/SERVER CONNECTION CALLS

### Backend Framework
**Type:** Flask 3.0.0+
**Entry Point:** `/app_new.py` (1,520 lines)
**Alternative Entry:** `/index.py` (wrapper for Vercel)

### API Endpoints Structure

#### Health & Monitoring
```
GET /health           → Health check (all components)
GET /metrics          → Prometheus-compatible metrics
GET /api/csrf-token   → Generate CSRF token
GET /api/session/<id> → Get session data
GET /api/cache/stats  → Cache statistics
POST /api/cache/clear → Clear cache (admin)
```

#### Step 1: Property Input
```
POST /api/parse            → Parse CIAN URL
POST /api/create-manual    → Create property manually
POST /api/update-target    → Update target with missing fields
```

#### Step 2: Comparables
```
POST /api/find-similar         → Auto-search similar
POST /api/add-comparable       → Manually add comparable
POST /api/exclude-comparable   → Exclude from analysis
POST /api/include-comparable   → Re-include in analysis
```

#### Step 3: Analysis & Export
```
POST /api/analyze              → Run full analysis
GET /api/export-report/<id>    → Download Markdown report
```

### HTTP Calls in Frontend
**Main JavaScript Files:**
1. `/static/js/wizard.js` - Modern version with CSRF protection
2. `/wizard.js` - Older version (1,090 lines)

**HTTP Methods:**
- All data mutations use `POST` with JSON bodies
- All reads use `GET`
- CSRF token included in meta tag or fetched via `/api/csrf-token`

**Error Handling:**
Location: `/static/js/error-messages.js` (259 lines)
- Maps technical errors to user-friendly Russian messages
- 20+ predefined error messages
- Functions: `getErrorMessage()`, `validateField()`, `showErrorToast()`

---

## 3. LOGGING INFRASTRUCTURE

### Configuration
**Entry Point:** `app_new.py` lines 9-17
```python
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
```

### Logging Locations

| Module | File | Purpose |
|--------|------|---------|
| **Flask App** | app_new.py | Request logging, API calls, errors |
| **Analytics** | src/analytics/*.py | Analysis calculations, metrics |
| **Parser** | src/parsers/*.py | Web parsing, browser pool |
| **Cache** | src/cache/redis_cache.py | Redis operations |
| **Session** | src/utils/session_storage.py | Session storage ops |
| **Security** | app_new.py | URL validation, CSRF |

### Key Debug Logging Points
- **Step 2 Search:** app_new.py lines 852, 857, 874, 884-885 (emoji markers: 🔍, 🚀, ✓)
- **Analysis:** analyzer.py lines 245-256, 118, 1118-1184 (🔧, 🔍 markers)
- **Session:** session_storage.py lines 79, 114-115, 192

### Debug Logging Examples
```
"🔍 DEBUG: {len(similar)} comparables found, {len(urls_to_parse)} need parsing"
"🚀 Parallel parsing {len(urls_to_parse)} URLs..."
"✓ Enhanced {len(detailed_results)} comparables with detailed data"
"🔧 DEBUG: Создаю analyzer..."
```

---

## 4. TESTING INFRASTRUCTURE

### Test Framework
**Framework:** pytest 7.4.0+
**Location:** `/tests/` directory

### Test Files

| File | Focus | Tests |
|------|-------|-------|
| test_api.py | API endpoints | Health, metrics, CSRF |
| test_e2e_full_flow.py | End-to-end flow | Parse → find similar → analyze |
| test_session_storage.py | Session management | Storage, TTL, LRU eviction |
| test_security.py | Security features | URL validation, SSRF protection |
| test_browser_pool.py | Browser pool | Pool management, limits |
| test_new_analytics.py | Analytics engine | Calculations, filtering |
| test_field_mapping.py | Field mapping | Property validation |
| test_fair_price_calculator.py | Fair price logic | Pricing calculations |
| conftest.py | Fixtures | App fixtures, test data |

### Test Execution
```bash
pytest /home/user/cian-analyzer/tests
pytest --cov=src tests/  # With coverage
```

### Key Test Areas
1. **API Endpoints** - Response codes, JSON structure
2. **Session Persistence** - Redis/memory storage, TTL
3. **Security** - SSRF protection, CSRF tokens, URL validation
4. **Analytics** - Outlier filtering, fair price calculation
5. **E2E Flow** - Full wizard workflow from start to finish

---

## 5. BACKEND STRUCTURE

### Application Type
**Framework:** Flask (not Express, not Next.js)
**Architecture:** Monolithic Flask app with modular analytics

### Directory Structure
```
/home/user/cian-analyzer/
├── app_new.py                 # Main Flask app (1,520 lines)
├── index.py                   # Vercel entry point
├── requirements.txt           # Dependencies
├── pyproject.toml            # Project config
├── wizard.js                 # Legacy wizard
├── templates/
│   ├── wizard.html          # Main wizard template
│   └── index.html           # Landing page
├── static/
│   ├── js/
│   │   ├── wizard.js        # Modern wizard (1,583 lines)
│   │   ├── error-messages.js # Error handling
│   │   └── advice-ticker.js
│   └── css/
├── src/
│   ├── analytics/           # Data analysis modules
│   │   ├── analyzer.py      # Main analyzer (1,090 lines)
│   │   ├── fair_price_calculator.py
│   │   ├── median_calculator.py
│   │   ├── price_range.py
│   │   ├── attractiveness_index.py
│   │   ├── time_forecast.py
│   │   ├── recommendations.py
│   │   ├── coefficients.py
│   │   └── parameter_classifier.py
│   ├── models/
│   │   └── property.py      # Pydantic models (474 lines)
│   ├── parsers/             # Web scraping
│   │   ├── playwright_parser.py
│   │   ├── simple_parser.py
│   │   ├── async_parser.py
│   │   └── browser_pool.py
│   ├── cache/
│   │   └── redis_cache.py   # Redis caching layer
│   ├── utils/
│   │   └── session_storage.py # Session management
│   └── templates/           # HTML templates
├── tests/                   # Pytest test suite
└── docs/                    # Documentation
```

### Core Modules

**Flask App (app_new.py):**
- 1,520 lines
- CSRF protection with Flask-WTF
- Rate limiting with Flask-Limiter
- Security headers (CSP, X-Frame-Options, etc.)
- 20+ route handlers
- Session storage initialization
- Browser pool management

**Analytics Engine (src/analytics/):**
- RealEstateAnalyzer class - main analysis orchestrator
- Fair price calculations with statistical confidence
- Market statistics (mean, median, confidence intervals)
- Price scenarios (3-5 different strategies)
- Outlier filtering (±3σ rule)
- Attractiveness indexing
- Time-to-sell forecasting

**Data Models (src/models/property.py):**
- Pydantic validation for all inputs
- TargetProperty class
- ComparableProperty class
- AnalysisRequest & AnalysisResult classes
- 4 property clusters (20+ fields)

**Parser (src/parsers/):**
- PlaywrightParser - browser automation (Playwright)
- SimpleParser - lightweight fallback (BeautifulSoup)
- BrowserPool - resource management
- AsyncParser - parallel URL parsing
- Region detection from URL

**Caching (src/cache/redis_cache.py):**
- Redis-based caching with fallback
- Multiple TTLs: 24h (properties), 1h (search), 7d (complex data)
- Compression for large JSON
- Namespace isolation (dev/prod)

**Session Storage (src/utils/session_storage.py):**
- Redis or in-memory with TTL
- LRU eviction for memory storage
- Thread-safe access
- Session statistics (hits, misses, evictions)

---

## 6. ERROR HANDLING MECHANISMS

### Backend Error Handling

#### 1. Application-Level Errors
Location: `app_new.py` lines 286-334 (timeout context)

**Timeout Protection:**
```python
@contextmanager
def timeout_context(seconds: int, error_message: str):
    """Protects against hanging operations (e.g., long parsing)"""
    # Uses signal.SIGALRM in main thread
    # Falls back to no-timeout in worker threads (Gunicorn gthread)
```

#### 2. Input Validation Errors
Location: `app_new.py` lines 149-231

**URL Validation (`validate_url()`):**
- Whitelist of allowed domains (SSRF protection)
- Protocol check (http/https only)
- IP address blocking (private/loopback)
- Length limit (2048 chars)
- Suspicious pattern detection

**Data Validation (`ManualPropertyInput`):**
- Pydantic BaseModel with validators
- Field constraints: price (>0, <1 trillion), area, rooms
- Cross-field validation (living_area < total_area)
- String sanitization (max 1000 chars, null bytes removed)

#### 3. API Response Errors
All endpoints return consistent error JSON:
```json
{
  "status": "error",
  "message": "Human-readable error message",
  "error_type": "validation_error|analysis_error|internal_error",
  "errors": ["field-specific errors if applicable"]
}
```

#### 4. Analysis-Specific Errors
Location: `app_new.py` lines 1051-1198

**Insufficient Data:**
```python
if len(self.filtered_comparables) < 3:
    raise ValueError(f"Not enough comparables ({n} found, 3 required)")
```

**Validation Errors:**
```python
except PydanticValidationError:
    # Return 400 Bad Request with field errors
```

**Analysis Failures:**
```python
except ValueError as ve:
    # Return 422 Unprocessable Entity (validation error)
except Exception:
    # Return 500 Internal Server Error
```

#### 5. Parser Errors
Location: Various parsers
- Timeout handling (60s limit per URL)
- Network error recovery
- Fallback to SimpleParser if Playwright unavailable
- Browser pool exhaustion handling

### Frontend Error Handling

**Error Message System:** `/static/js/error-messages.js` (259 lines)
```javascript
// 20+ predefined messages
ERROR_MESSAGES = {
    'network_error': {title, message},
    'parsing_failed': {...},
    'no_comparables': {...},
    'analysis_failed': {...},
    // ... etc
}

// Functions:
getErrorMessage(errorKey) → {title, message}
showErrorToast(errorKey, type) → Display to user
validateField(field, value) → Boolean
```

**Error Handling in Wizard:**
1. Catch all fetch errors
2. Parse response JSON
3. Translate technical errors to user-friendly Russian
4. Show toast notifications with error details
5. Log to browser console

### Logging Error Details
```python
logger.error(f"Error: {e}", exc_info=True)  # Include traceback
logger.warning(f"Non-critical issue: {e}")   # Just message
```

### Security Error Handling
1. **400 Bad Request** - Invalid URL or data
2. **403 Forbidden** - CSRF token missing/invalid
3. **404 Not Found** - Session expired
4. **408 Request Timeout** - Parser timeout
5. **422 Unprocessable Entity** - Validation failed
6. **429 Too Many Requests** - Rate limit exceeded
7. **503 Service Unavailable** - Health check failed

---

## Key Diagrams

### Request Flow (Step 1 → Step 2)
```
Frontend                    Backend                   External
  User                      App                       CIAN
   |                          |                        |
   |-- POST /api/parse ------->|
   |    (url: https://...)      |-- Parse URL -------->|
   |                            |                       |
   |                            |<-- HTML page ---------|
   |                            |
   |                            |-- Validate & Extract--|
   |                            |   Property Data
   |                            |
   |<-- {session, data} --------|
   |
   |-- Complete Missing Fields--|
   |
   |-- POST /api/update-target->|-- Save Session ------|
   |                            |
   |-- Navigate to Step 2 ------|
```

### Analysis Processing (Step 3)
```
POST /api/analyze
  ↓
Normalize Property Data (Pydantic)
  ↓
Filter Outliers (±3σ)
  ↓
Calculate Market Statistics
  ↓
Calculate Fair Price (with adjustments)
  ↓
Generate Price Scenarios (3-5 variants)
  ↓
Analyze Strengths/Weaknesses
  ↓
Calculate Price Range & Sensitivity
  ↓
Forecast Time to Sell
  ↓
Calculate Attractiveness Index
  ↓
Return AnalysisResult JSON
  ↓
Frontend Renders Charts & Metrics
```

---

## File Size Summary

| Category | Count | LOC |
|----------|-------|-----|
| Python Source | ~18 files | ~9,755 |
| JavaScript | 3 files | ~2,490 |
| Templates | 2 files | ~50K+ chars |
| Tests | 8 files | ~1,500 |
| **Total** | **~30** | **~13,000+** |

---

## Critical Configuration Files

| File | Purpose |
|------|---------|
| requirements.txt | Python dependencies (Flask, Pydantic, Playwright, etc.) |
| pyproject.toml | Project metadata |
| .env.example | Environment variables template |
| .pre-commit-config.yaml | Code quality checks |

---

## Dependencies Highlights

**Web Framework:** Flask 3.0.0+
**Validation:** Pydantic 2.5.0+
**Parsing:** BeautifulSoup4 4.12.0+, Playwright 1.40.0+
**Analytics:** NumPy 1.24.0+, SciPy 1.11.0+
**Caching:** Redis 5.0.0+
**Security:** Flask-WTF 1.2.0+, Flask-Limiter 3.5.0+
**Testing:** pytest 7.4.0+

---

## Production Deployment

**Recommended Server:** Gunicorn 21.2.0+
**Worker Type:** gthread (multi-threaded)
**Session Storage:** Redis (distributed)
**Caching:** Redis
**Security Features:**
- CSRF tokens (Flask-WTF)
- Rate limiting (Flask-Limiter)
- Security headers (CSP, HSTS, X-Frame-Options)
- Input validation (Pydantic)
- URL whitelist (SSRF protection)

