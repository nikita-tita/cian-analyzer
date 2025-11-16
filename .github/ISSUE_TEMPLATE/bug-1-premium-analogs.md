---
name: 🔴 P0 Bug - Premium segment analog search fails
about: Critical blocker - Premium objects (25M+) return zero analogs
title: '[P0] Premium segment (25M+) returns 0 analogs, blocks Step 3'
labels: bug, critical, P0, blocker
assignees: ''
---

## 🔴 SEVERITY: CRITICAL (P0 - SHOWSTOPPER)

**Priority:** Must fix before production launch
**Affected segments:** Premium (25+ million ₽)
**Impact:** 30-40% of target audience cannot use the system

---

## 📋 Description

For premium segment properties (price 25M+ ₽), the analog search returns **ZERO results**, which completely blocks access to Step 3 (analysis). The system is unusable for high-value properties.

## 🔁 Steps to Reproduce

1. Open calculator: https://housler.ru/calculator
2. Paste URL: `https://spb.cian.ru/sale/flat/321709237/`
3. Click "Загрузить объект" → parsing succeeds ✅
4. Fill required fields:
   - Living area: 67 m²
   - Window type: Пластиковые
   - Elevators: 2
5. Click "Далее" → navigate to Step 2 ✅
6. Click "Автоматически найти похожие объекты"
7. Wait for completion (~20 sec)

## ✅ Expected Result

- Found minimum 5-10 analogs from the same district
- List of analogs displayed on screen
- Ability to proceed to Step 3 for analysis

## ❌ Actual Result

- Message displayed: **"Аналоги не найдены"** (No analogs found)
- Button "К анализу" is disabled/not working
- **Cannot proceed to Step 3**
- **System is completely useless for this property**

## 📊 Test Object Characteristics

- **Type:** 2-room apartment
- **Area:** 96.5 m² (living 67 m²)
- **Price:** 31,200,000 ₽
- **Price/m²:** 323,316 ₽/m²
- **Address:** SPb, Lakhtinsky pr., 85k1
- **Complex:** Lakhta Park
- **Floor:** 20 of 33
- **Year:** 2025

## 🔍 Root Cause Analysis (Hypothesis)

### Possible causes:

1. **Too strict price filters:**
   - Current range: 96.5 m² ± 30% = 67-125 m²
   - Rooms: 2-room ± 1 = 1-3 rooms
   - Price range may be too narrow for premium segment

2. **Regional limitations:**
   - Lakhta district may have few listings
   - Lakhta Park complex is new with limited inventory

3. **Bug in search logic:**
   - System may incorrectly process premium segment
   - CIAN API may return 0 results due to wrong parameters

## 💡 Recommended Fix

```python
# src/parsers/playwright_parser.py

# CURRENT LOGIC (presumed):
def find_analogs(price, area, rooms):
    min_price = price * 0.8  # ±20%
    max_price = price * 1.2

    # For premium 31.2M this gives:
    # min = 24.96M, max = 37.44M
    # TOO NARROW!

# FIXED LOGIC:
def find_analogs(price, area, rooms):
    # Expand range for premium
    if price > 25_000_000:
        price_tolerance = 0.4  # ±40% for premium
    else:
        price_tolerance = 0.3  # ±30% for others

    min_price = price * (1 - price_tolerance)
    max_price = price * (1 + price_tolerance)

    # Fallback: if found < 5 analogs
    if len(analogs) < 5:
        # Expand range even more
        min_price = price * 0.5
        max_price = price * 1.5
        # Retry search

    # Fallback 2: if still < 5
    if len(analogs) < 5:
        # Remove price filter, keep only district
        search_by_region_only()

    return analogs
```

## 📈 Impact Assessment

- ❌ **Complete blockage** of analysis for premium segment (25+ M ₽)
- ❌ Loss of **30-40% of target audience** (agents work primarily with expensive properties)
- ❌ Cannot demo product on real deals
- ❌ **BLOCKER for production launch**

## ✅ Acceptance Criteria

- [ ] Premium object (31.2M) finds minimum 5 analogs
- [ ] Step 3 is unblocked
- [ ] Median calculation works correctly
- [ ] Tested on 10 premium objects (25-50M)
- [ ] Error rate < 5% for premium segment

## 📊 Testing Plan

**Test cases:**
1. Premium 25-30M → min 5 analogs found
2. Premium 30-40M → min 5 analogs found
3. Premium 40-50M → min 5 analogs found
4. Ultra-premium 50M+ → min 3 analogs found (acceptable for rare segment)

**Regression:**
- Ensure economy/middle segments still work
- Median accuracy ±10%
- No performance degradation

## ⏰ Estimated Effort

- **Development:** 4-8 hours
- **Testing:** 4-6 hours
- **Total:** 8-14 hours

## 🔗 Related Issues

- Issue #2: [P0] Analogs hidden from users
- Issue #3: [P1] Restore Housler forecast section

## 📄 Documentation

- Full audit: `docs/FINAL_COMPREHENSIVE_AUDIT_3_ITERATIONS.md`
- Deployment decision: `DEPLOYMENT_DECISION.md`
- Test object URL: https://spb.cian.ru/sale/flat/321709237/

---

**Status:** 🔴 BLOCKER
**Target fix date:** Nov 23, 2025
**Target deployment:** Dec 1-8, 2025 (after UAT)
