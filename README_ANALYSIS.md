# CIAN Analyzer - Codebase Documentation Index

This directory contains comprehensive analysis of the CIAN Analyzer codebase.

## Documentation Files

### 1. **EXECUTIVE_SUMMARY.md** (11KB) - START HERE
High-level overview of the entire application:
- Architecture and technology stack
- 3-step wizard flow explanation
- Potential performance/hanging issues
- Security features
- Quick answers to all 6 analysis questions
- Recommended next steps for debugging

**Best for:** Getting quick understanding of the entire system

### 2. **CODEBASE_ANALYSIS.md** (19KB) - DETAILED REFERENCE
Complete technical analysis covering all 6 requested areas:
1. **Wizard Steps Implementation** - Where steps 1, 2, 3 logic lives
   - Frontend files and line numbers
   - Backend endpoints and line numbers
   - Data flow and missing fields logic
   
2. **API/Server Connection Calls** - How frontend and backend communicate
   - Complete endpoint list (20+ routes)
   - HTTP methods and parameters
   - Error handling patterns
   
3. **Logging Infrastructure** - Where and how logging works
   - Configuration location
   - All logging locations by module
   - Debug logging points with emoji markers
   
4. **Testing Infrastructure** - Testing setup
   - Test framework (pytest)
   - Test files location
   - How to run tests
   
5. **Backend Structure** - Application architecture
   - Flask-based monolithic app
   - Directory structure
   - Core modules and their functions
   
6. **Error Handling Mechanisms** - Where errors are caught and handled
   - Backend validation (URL, input, timeouts)
   - API error responses
   - Frontend error translation system

**Best for:** Deep technical understanding, debugging issues

### 3. **QUICK_REFERENCE.md** (6.7KB) - DAILY LOOKUP
Fast reference guide for common tasks:
- Step 2 and 3 logic quick locations
- Critical files and line ranges
- API endpoints cheat sheet
- Testing quick start
- Environment variables
- Security features overview
- Performance notes
- Production checklist

**Best for:** Quick lookups while working on the code

### 4. **FILE_PATHS_REFERENCE.txt** (9.2KB) - COPY-PASTE PATHS
All absolute file paths with line numbers:
- Step 1, 2, 3 implementations
- Core module locations
- Entry points
- Templates
- Security implementations
- Testing files
- Configuration files
- API endpoint mappings

**Best for:** Finding exact file locations, copy-pasting into editors

---

## Quick Navigation

### If you need to understand...

**The 3-step wizard flow:**
→ Read EXECUTIVE_SUMMARY.md section "1. WIZARD FLOW (3 STEPS)"

**Where step 2 logic is:**
→ Check QUICK_REFERENCE.md "Step 2: Find Comparables" or
→ FILE_PATHS_REFERENCE.txt "STEP 2 LOGIC"

**Where step 3 logic is:**
→ Check QUICK_REFERENCE.md "Step 3: Run Analysis" or
→ FILE_PATHS_REFERENCE.txt "STEP 3 LOGIC"

**Why step 2 might hang:**
→ EXECUTIVE_SUMMARY.md "Potential Issues" section

**Why step 3 might hang:**
→ EXECUTIVE_SUMMARY.md "Potential Issues" section

**How logging works:**
→ CODEBASE_ANALYSIS.md section "3. LOGGING INFRASTRUCTURE"

**How to run tests:**
→ CODEBASE_ANALYSIS.md section "4. TESTING INFRASTRUCTURE" or
→ QUICK_REFERENCE.md "TESTING" section

**All API endpoints:**
→ QUICK_REFERENCE.md "API ENDPOINTS CHEAT SHEET" or
→ FILE_PATHS_REFERENCE.txt "API ENDPOINTS MAPPING"

**Error handling:**
→ CODEBASE_ANALYSIS.md section "6. ERROR HANDLING MECHANISMS"

**Security features:**
→ QUICK_REFERENCE.md "SECURITY FEATURES" or
→ EXECUTIVE_SUMMARY.md "Security Features"

---

## Key Files (Most Important)

| File | Lines | Purpose |
|------|-------|---------|
| /home/user/cian-analyzer/app_new.py | 1,520 | Main Flask app with all API endpoints |
| /home/user/cian-analyzer/static/js/wizard.js | 1,583 | Frontend wizard UI |
| /home/user/cian-analyzer/src/analytics/analyzer.py | 1,090 | Analysis calculations |
| /home/user/cian-analyzer/src/models/property.py | 474 | Data validation models |
| /home/user/cian-analyzer/static/js/error-messages.js | 259 | Error message system |
| /home/user/cian-analyzer/src/utils/session_storage.py | 263 | Session management |
| /home/user/cian-analyzer/templates/wizard.html | ~50KB | HTML template |

---

## Architecture Summary

```
FRONTEND (Browser)
  ↓ fetch() API calls
  
BACKEND (Flask app_new.py)
  ├─ Route handlers (20+ endpoints)
  ├─ Input validation (Pydantic)
  ├─ Business logic
  │   ├─ Parser (src/parsers/)
  │   ├─ Analyzer (src/analytics/)
  │   └─ Session storage (src/utils/)
  └─ Caching (src/cache/)
  
EXTERNAL
  ├─ CIAN.ru (scraping)
  └─ Redis (optional)
```

---

## Debug Markers in Code

Look for these emoji markers to find debug logging quickly:

- **🔍** - Search/filter operations (Step 2)
- **🚀** - Parallel operations
- **✓** - Success/completion markers
- **🔧** - Analysis operations (Step 3)

Example locations:
- Step 2: `/home/user/cian-analyzer/app_new.py` lines 852, 857, 874
- Step 3: `/home/user/cian-analyzer/app_new.py` lines 1118-1184

---

## Getting Started

1. **First time?** Start with **EXECUTIVE_SUMMARY.md**
2. **Need details?** Read **CODEBASE_ANALYSIS.md**
3. **Quick lookup?** Use **QUICK_REFERENCE.md**
4. **Need exact paths?** Check **FILE_PATHS_REFERENCE.txt**

---

## Document Statistics

| Document | Size | Words | Focus |
|----------|------|-------|-------|
| EXECUTIVE_SUMMARY.md | 11KB | ~2,000 | Overview & answers |
| CODEBASE_ANALYSIS.md | 19KB | ~3,500 | Technical deep-dive |
| QUICK_REFERENCE.md | 6.7KB | ~1,200 | Fast lookups |
| FILE_PATHS_REFERENCE.txt | 9.2KB | ~1,500 | Absolute paths |
| **Total** | **46KB** | **~8,200** | **Complete reference** |

---

## How to Use This Analysis

### For Debugging Issues
1. Check EXECUTIVE_SUMMARY.md "Potential Issues"
2. Find the relevant section in CODEBASE_ANALYSIS.md
3. Use QUICK_REFERENCE.md for line numbers
4. Open the file with FILE_PATHS_REFERENCE.txt

### For Understanding Architecture
1. Read EXECUTIVE_SUMMARY.md first
2. Check directory structure in CODEBASE_ANALYSIS.md
3. Review code flow diagrams in CODEBASE_ANALYSIS.md

### For Adding New Features
1. Understand the current flow (EXECUTIVE_SUMMARY.md)
2. Find where similar logic exists (QUICK_REFERENCE.md)
3. Check tests for patterns (CODEBASE_ANALYSIS.md section 4)
4. Review error handling (CODEBASE_ANALYSIS.md section 6)

### For Production Deployment
1. Check QUICK_REFERENCE.md "PRODUCTION CHECKLIST"
2. Review security in EXECUTIVE_SUMMARY.md
3. Set up monitoring via `/health` endpoint

---

## Important Notes

### Step 2 Issues
Step 2 (finding comparables) can hang due to:
- Parallel URL parsing timeout (60s per URL)
- CIAN rate limiting
- Browser pool exhaustion

Check: `/home/user/cian-analyzer/app_new.py` lines 854-874

### Step 3 Issues
Step 3 (analysis) can hang due to:
- Large dataset processing (20+ comparables)
- Statistical calculations
- Recommendations engine (currently disabled)

Check: `/home/user/cian-analyzer/app_new.py` lines 1051-1198

### Performance
- Step 1: 10-20 seconds (parsing)
- Step 2: 15-30+ seconds (depends on CIAN)
- Step 3: 3-10 seconds (depends on data size)

---

## Related Commands

```bash
# Run the Flask app
python app_new.py

# Run all tests
pytest /home/user/cian-analyzer/tests

# Run with coverage
pytest --cov=src tests/

# Check health
curl http://localhost:5002/health

# Check metrics
curl http://localhost:5002/metrics

# View logs (if running with logging)
grep "🔍\|🚀\|✓\|🔧" <logfile>
```

---

## Questions?

- **Architecture:** See CODEBASE_ANALYSIS.md section 5
- **API endpoints:** See QUICK_REFERENCE.md "API ENDPOINTS CHEAT SHEET"
- **Testing:** See CODEBASE_ANALYSIS.md section 4
- **Security:** See EXECUTIVE_SUMMARY.md "Security Features"
- **Performance:** See QUICK_REFERENCE.md "PERFORMANCE NOTES"

---

Generated: November 10, 2025
Total Analysis Time: Complete codebase review
Lines Analyzed: ~13,000 LOC
