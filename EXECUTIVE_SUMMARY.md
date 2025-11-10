# CIAN Analyzer - Executive Summary

## Overview
A **Flask-based real estate analysis web application** with a 3-step wizard interface for analyzing property values using comparable analysis.

**Architecture:** Monolithic Flask backend + Vanilla JavaScript frontend
**Language:** Python (backend) + JavaScript (frontend)  
**Total Code:** ~13,000 LOC
**Framework:** Flask 3.0.0+
**Database:** Redis (caching/sessions, optional with memory fallback)

---

## Key Facts About the Codebase

### 1. WIZARD FLOW (3 STEPS)

The entire application revolves around a 3-step sequential flow:

**STEP 1: Property Parsing (Парсинг)**
- User enters CIAN.ru URL or fills form manually
- Backend parses property details from HTML
- Identifies missing critical fields (repair_level, view_type)
- Creates session and stores target property
- **Files:** `/app_new.py:564-793`, `/static/js/wizard.js:94-383`

**STEP 2: Find Comparables (Аналоги)**
- User finds similar properties (auto or manual)
- Backend searches building or city for comparables
- Parallel parsing enriches data (max 2 concurrent to avoid rate limiting)
- User can exclude/include properties before analysis
- **Files:** `/app_new.py:796-1048`, `/static/js/wizard.js:386-558`
- **Issue:** Can hang on parallel parsing if CIAN rate-limits

**STEP 3: Run Analysis (Анализ)**
- Backend analyzes target vs comparables
- Calculates fair price, market stats, scenarios, strengths/weaknesses
- Generates visualizations and report
- **Files:** `/app_new.py:1051-1198`, `/static/js/wizard.js:561-845`
- **Issue:** Can hang on large comparables sets or recommendation engine

### 2. BACKEND ARCHITECTURE

**Entry Point:** `/home/user/cian-analyzer/app_new.py` (1,520 lines)

**Core Components:**
1. **Flask Web Framework** - HTTP handling, routing, security
2. **Analytics Engine** - Statistical analysis, fair price calculation
3. **Parser** - Web scraping (Playwright/BeautifulSoup)
4. **Session Storage** - Redis or in-memory with TTL
5. **Caching Layer** - Redis with multiple TTLs
6. **Security** - CSRF, URL validation, rate limiting, security headers

**Key Modules:**
- `RealEstateAnalyzer` - Main analysis orchestrator
- `PropertyCache` - Redis-backed caching
- `SessionStorage` - Session management with TTL
- `PlaywrightParser` - Browser automation
- `SimpleParser` - Lightweight fallback

### 3. FRONTEND ARCHITECTURE

**Main File:** `/home/user/cian-analyzer/static/js/wizard.js` (1,583 lines)

**Structure:**
- Global state machine (currentStep, sessionId, targetProperty, etc.)
- Utility functions (UI helpers, number formatting)
- 3 screen objects (screen1, screen2, screen3)
- Navigation controller
- Error handling system

**HTTP Communication:**
- All data mutations: POST requests with JSON bodies
- All reads: GET requests
- CSRF token protection on all POST requests
- Toast notifications for user feedback
- Centralized error translation to Russian

### 4. DATA FLOW

```
User Input (Browser)
  ↓
fetch() POST/GET to /api/...
  ↓
Flask route handler in app_new.py
  ↓
Validation (Pydantic models)
  ↓
Business logic (Parser/Analyzer)
  ↓
Redis cache hit/miss
  ↓
Response JSON
  ↓
Frontend state update + UI render
```

### 5. API ENDPOINTS (20+)

**Health:** `/health`, `/metrics`, `/api/csrf-token`
**Step 1:** `/api/parse`, `/api/create-manual`, `/api/update-target`
**Step 2:** `/api/find-similar`, `/api/add-comparable`, `/api/exclude-comparable`
**Step 3:** `/api/analyze`, `/api/export-report`
**Admin:** `/api/cache/stats`, `/api/cache/clear`

---

## Potential Issues (Based on Debug Logging)

### Step 2 Can Hang Due To:
1. **Parallel URL parsing** (lines 854-874)
   - Max 2 concurrent to avoid rate limiting
   - Each URL has 60s timeout
   - CIAN might be rate-limiting or blocking

2. **Search query** not returning results quickly

3. **Browser pool** exhaustion if Playwright is enabled

### Step 3 Can Hang Due To:
1. **Recommendations engine** (currently DISABLED - line 201)
   - Was causing freezes, temporarily commented out

2. **Statistical calculations** with 20+ comparables
   - Outlier filtering (±3σ rule)
   - Fair price calculations with scipy.stats

3. **Large dataset processing**
   - Confidence interval calculations
   - Chart data generation

4. **Session retrieval** timeout

---

## Security Features

1. **CSRF Protection** - Flask-WTF tokens on all POST requests
2. **URL Validation** - Whitelist check (only CIAN.ru allowed)
3. **SSRF Protection** - IP address blocking (no 127.0.0.1, 192.168.*, etc.)
4. **Input Sanitization** - Pydantic validation + length limits + null byte removal
5. **Rate Limiting** - 200/day, 50/hour per user/IP combination
6. **Security Headers** - CSP, X-Frame-Options, HSTS, etc.
7. **Timeout Protection** - 60s max per operation (signal-based)
8. **Session Expiry** - 1 hour TTL with thread-safe cleanup

---

## Logging Infrastructure

**Configuration:**
```python
# app_new.py lines 9-17
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
```

**Debug Markers (easy to find):**
- 🔍 - Search/filtering operations (Step 2)
- 🚀 - Parallel operations
- ✓ - Success/completion
- 🔧 - Analysis operations (Step 3)

**Key Log Points:**
- `/api/parse` calls: lines 599, 607, 633
- `/api/find-similar`: lines 832, 852, 857, 874, 884-885
- `/api/analyze`: lines 1081, 1118-1184 (many 🔧 markers)

---

## Testing

**Framework:** pytest 7.4.0+
**Location:** `/home/user/cian-analyzer/tests/`
**Test Files:** 8 files covering APIs, E2E flow, security, analytics, sessions

**Run Tests:**
```bash
pytest /home/user/cian-analyzer/tests
pytest --cov=src tests/  # With coverage
```

---

## Critical Files Quick Reference

| Purpose | File | Lines | Type |
|---------|------|-------|------|
| Flask app | app_new.py | 1,520 | Python |
| Frontend wizard | static/js/wizard.js | 1,583 | JavaScript |
| Analytics | src/analytics/analyzer.py | 1,090 | Python |
| Data models | src/models/property.py | 474 | Python |
| Error messages | static/js/error-messages.js | 259 | JavaScript |
| Session storage | src/utils/session_storage.py | 263 | Python |
| Redis cache | src/cache/redis_cache.py | ~200 | Python |
| HTML template | templates/wizard.html | ~50K | HTML |
| Tests | tests/ | 1,500+ | Python |

---

## Performance Characteristics

**Typical Timings:**
- Step 1 (parsing): 10-20 seconds
- Step 2 (find similar): 15-30+ seconds (depends on CIAN)
- Step 3 (analysis): 3-10 seconds (depends on comparables count)

**Bottlenecks:**
1. CIAN response times
2. Parallel parsing concurrency limit (2)
3. Statistical calculations with large datasets
4. Network latency

**Optimization Options:**
1. Increase cache TTL (currently 24h for properties)
2. Reduce parallel parsing max_concurrent
3. Use Redis for session storage (faster than memory)
4. Implement request queuing for Step 3

---

## Production Deployment

**Recommended Setup:**
- Gunicorn with gthread workers (multi-threaded)
- Redis for caching and session storage
- Environment variables for configuration
- HTTPS/SSL termination at reverse proxy
- Monitoring via `/health` and `/metrics` endpoints

**Critical Environment Variables:**
- `SECRET_KEY` - MUST be set for CSRF (generate with `openssl rand -hex 32`)
- `FLASK_ENV` - Set to 'production'
- `REDIS_ENABLED` - Set to 'true' for distributed sessions
- `REDIS_HOST`, `REDIS_PORT` - Redis connection details

---

## Documentation Generated

Three comprehensive documents have been created:

1. **CODEBASE_ANALYSIS.md** (19KB)
   - Detailed breakdown of all 6 requested areas
   - Full file structure and architecture
   - Database flows and diagrams
   - Security implementations

2. **QUICK_REFERENCE.md** (6.7KB)
   - Quick lookup for common tasks
   - API endpoints cheat sheet
   - File location shortcuts
   - Performance notes

3. **FILE_PATHS_REFERENCE.txt** (9.2KB)
   - All absolute file paths with line numbers
   - Easy copy-paste paths for developers
   - Organized by feature and component

---

## Answers to Your 6 Questions

### 1. Where are the "steps" implemented?
- **Step 1:** `app_new.py:564-793`, `static/js/wizard.js:94-383`
- **Step 2:** `app_new.py:796-1048`, `static/js/wizard.js:386-558`
- **Step 3:** `app_new.py:1051-1198`, `static/js/wizard.js:561-845`

### 2. Where are API/server connection calls?
- **Frontend:** All in `static/js/wizard.js` using fetch() API
- **Backend:** All endpoints in `app_new.py` (20+ routes)
- **Parsers:** `src/parsers/` for CIAN scraping

### 3. What is the logging infrastructure?
- **Setup:** `app_new.py:9-17` (basicConfig with INFO level)
- **Locations:** Every module uses `logger = logging.getLogger(__name__)`
- **Markers:** 🔍, 🚀, ✓, 🔧 for debugging

### 4. What testing infrastructure exists?
- **Framework:** pytest with 8 test files
- **Location:** `/home/user/cian-analyzer/tests/`
- **Coverage:** APIs, E2E flow, security, analytics, sessions

### 5. What is the backend structure?
- **Type:** Flask (not Express, not Next.js)
- **Architecture:** Monolithic with modular analytics
- **Core:** Pydantic validation, Redis caching, Playwright parsing

### 6. Where are error handling mechanisms?
- **Backend:** Input validation (`app_new.py:149-231`), timeouts (`app_new.py:286-334`), error responses
- **Frontend:** Error message system (`static/js/error-messages.js`), toast notifications
- **HTTP Status:** Proper 400/403/404/408/422/429/503 codes

---

## Next Steps for Debugging

1. **If Step 2 hangs:** Check CIAN connectivity and parallel parsing logs (look for 🚀 markers)
2. **If Step 3 hangs:** Monitor analysis logs (look for 🔧 markers) and check data size
3. **For performance:** Check `/metrics` endpoint and cache hit rate at `/api/cache/stats`
4. **For errors:** Check browser console AND `/health` endpoint status
5. **For production issues:** Enable detailed logging and monitor with `/health` polling

---

## Key Takeaways

- **Well-architected:** Clear separation between frontend, backend, analytics
- **Secure:** Multiple layers of validation, rate limiting, CSRF protection
- **Testable:** Comprehensive test suite with pytest
- **Debuggable:** Extensive logging with emoji markers for easy navigation
- **Scalable:** Redis support for distributed caching and sessions
- **Maintainable:** Clean code structure with documented functions

