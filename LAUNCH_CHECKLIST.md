# ✅ LAUNCH CHECKLIST - Dashboard v2.0

**Pre-launch verification checklist**

---

## 📋 BEFORE YOU START

### 1. System Requirements

```bash
# Check Python version (need 3.8+)
python3 --version
# ✅ Should show: Python 3.8.x or higher

# Check pip
pip --version
# ✅ Should show pip version
```

### 2. Dependencies

```bash
# Install required packages
pip install flask pydantic beautifulsoup4

# Verify installation
python3 -c "import flask; print(f'Flask: {flask.__version__}')"
python3 -c "import pydantic; print(f'Pydantic: {pydantic.__version__}')"
python3 -c "import bs4; print(f'BeautifulSoup: {bs4.__version__}')"

# ✅ All should print without errors
```

---

## 🚀 LAUNCH

### Step 1: Navigate to project

```bash
cd /Users/fatbookpro/Desktop/cian
pwd
# ✅ Should show: /Users/fatbookpro/Desktop/cian
```

### Step 2: Check files exist

```bash
# Check backend
ls -la src/web_dashboard_unified.py
ls -la src/analytics/recommendations.py

# Check frontend
ls -la src/templates/dashboard_unified.html
ls -la src/static/js/glossary.js
ls -la src/static/css/unified-dashboard.css

# ✅ All should exist
```

### Step 3: Launch server

**Option A: Quick script**
```bash
bash QUICK_RUN.sh
```

**Option B: Manual**
```bash
cd src
python3 web_dashboard_unified.py
```

**Expected output:**
```
 * Serving Flask app 'web_dashboard_unified'
 * Debug mode: off
WARNING: This is a development server.
 * Running on http://127.0.0.1:5001
Press CTRL+C to quit
```

✅ Server is running!

---

## 🧪 VERIFICATION

### Test 1: Health Check

**In a new terminal:**
```bash
curl http://localhost:5001/health
```

**Expected response:**
```json
{
  "status": "healthy",
  "version": "2.0",
  "timestamp": "2025-11-05T..."
}
```

✅ **PASS:** Backend is healthy

❌ **FAIL:** Check if server is running, check port 5001

---

### Test 2: Homepage Loads

**In browser:**
```
http://localhost:5001
```

**Should see:**
- ✅ Header: "🏠 Анализ Недвижимости v2.0"
- ✅ Status indicator: "● Система работает" (green)
- ✅ Form: "📋 Данные объекта"
- ✅ Input fields for price, area, etc.
- ✅ "🔍 Анализировать" button

**Check browser console (F12):**
- ✅ No JavaScript errors
- ✅ All resources loaded (no 404s)

---

### Test 3: Interactive Tooltips

**On homepage:**

1. Find any term with ℹ️ icon (e.g., "Цена за м² ℹ️")
2. Hover over the ℹ️
3. Should see tooltip appear with:
   - ✅ Title
   - ✅ Simple explanation
   - ✅ Example
   - ✅ "Почему важно"

**Check:**
- ✅ Tooltip appears smoothly
- ✅ Tooltip is readable
- ✅ Tooltip disappears when mouse moves away

---

### Test 4: Form Submission

**Fill in the form:**
```
Цена за м²: 200000
Площадь: 50
Жилая площадь: 30
Этаж: 5
Этажей в доме: 10
Комнат: 2

☑ Дизайнерский ремонт
☑ Панорамные виды
☐ Парковка
☑ Рядом с метро

Количество аналогов: 10
☑ Фильтровать выбросы
☑ Использовать медиану
```

**Click "🔍 Анализировать"**

**Should see:**
1. ✅ Loading spinner appears
2. ✅ After 1-2 seconds, results appear
3. ✅ Page scrolls to results automatically

---

### Test 5: Recommendations Panel

**After analysis completes:**

**Should see:**
- ✅ Section "🎯 Персонализированные рекомендации"
- ✅ At least 1 recommendation card
- ✅ Priority badge (КРИТИЧНО/ВАЖНО/СРЕДНЕ/ИНФО)
- ✅ Title and description
- ✅ Action items

**Check for:**
- ✅ Color coding by priority (red/yellow/green/blue)
- ✅ ROI badge on some recommendations (if applicable)
- ✅ Readable text

---

### Test 6: Waterfall Chart

**After analysis completes:**

**Should see:**
- ✅ Section "📊 Формирование справедливой цены"
- ✅ Chart.js bar chart
- ✅ Multiple bars (base, adjustments, total)
- ✅ Colors: blue (base/total), green (positive), red (negative)

**Interact:**
1. Hover over a bar
2. ✅ Tooltip should appear showing:
   - Label (e.g., "Дизайн +8%")
   - Value (e.g., "+14,400 ₽/м²")

---

### Test 7: Price Analysis

**After analysis completes:**

**Should see:**
- ✅ Section "💰 Анализ цены"
- ✅ 4 cards:
  1. Текущая цена
  2. Справедливая цена (highlighted)
  3. Отклонение
  4. Рекомендация

**Check:**
- ✅ Prices formatted with commas (e.g., "200,000 ₽/м²")
- ✅ Deviation shows percentage (e.g., "+15.3%")
- ✅ Recommendation shows status (e.g., "✅ Справедливая цена")

---

### Test 8: Market Statistics

**After analysis completes:**

**Should see:**
- ✅ Section "📈 Рыночная статистика"
- ✅ 6 stat cards:
  1. Медиана рынка
  2. Минимум
  3. Максимум
  4. Разброс (σ)
  5. Аналогов
  6. После фильтрации

**Check:**
- ✅ All values are numbers
- ✅ Icons displayed correctly
- ✅ Readable layout

---

### Test 9: Selling Scenarios

**After analysis completes:**

**Should see:**
- ✅ Section "🎲 Сценарии продажи"
- ✅ 4 scenario cards:
  - 🚀 AGGRESSIVE
  - ⚖️ MODERATE
  - 🛡️ CONSERVATIVE
  - 🎯 OPTIMAL

**Each card should show:**
- ✅ Success probability (e.g., "78%")
- ✅ Recommended price
- ✅ Expected time
- ✅ Net revenue
- ✅ Reasoning text

---

### Test 10: Responsive Design

**Resize browser window:**

1. **Desktop (1200px+)**
   - ✅ 3-column grid for stats
   - ✅ Side-by-side forms

2. **Tablet (768-1199px)**
   - ✅ 2-column grid
   - ✅ Readable layout

3. **Mobile (<768px)**
   - ✅ Single column
   - ✅ Stacked elements
   - ✅ Touch-friendly buttons
   - ✅ No horizontal scrolling

**On actual mobile device or DevTools mobile emulation:**
- ✅ Tooltips work on tap
- ✅ Form inputs are usable
- ✅ Charts are readable

---

## 🎯 COMPREHENSIVE TEST SUITE

### Automated Tests

**In a new terminal (while server is running):**

```bash
cd /Users/fatbookpro/Desktop/cian
python3 test_unified_dashboard.py
```

**Expected output:**
```
╔════════════════════════════════════════════════════════════╗
║   Unified Real Estate Dashboard v2.0 - Test Suite         ║
╚════════════════════════════════════════════════════════════╝

============================================================
TEST 1: Health Check
============================================================

✓ Status: healthy
✓ Version: 2.0
✓ Timestamp: 2025-11-05T...

============================================================
TEST 2: Homepage
============================================================

✓ Chart.js loaded
✓ Glossary.js loaded
✓ CSS loaded
✓ Form present
✓ Waterfall chart
✓ Recommendations

[... more tests ...]

============================================================
TEST SUMMARY
============================================================

  PASS - Health Check
  PASS - Homepage
  PASS - Analysis API
  PASS - Recommendations
  PASS - Waterfall Chart
  PASS - Selling Scenarios

Results: 6/6 tests passed

🎉 ALL TESTS PASSED! Dashboard is ready to use.
```

✅ **All tests should PASS**

---

## ✅ FINAL CHECKLIST

**Before considering launch complete:**

- [ ] Python 3.8+ installed
- [ ] Dependencies installed (flask, pydantic, beautifulsoup4)
- [ ] Server starts without errors
- [ ] Health check returns 200 OK
- [ ] Homepage loads completely
- [ ] No JavaScript errors in console
- [ ] Tooltips appear on hover
- [ ] Form submits successfully
- [ ] Recommendations appear
- [ ] Waterfall chart renders
- [ ] All 4 price analysis cards show
- [ ] Market statistics display
- [ ] 4 selling scenarios appear
- [ ] Automated tests pass (6/6)
- [ ] Responsive on mobile
- [ ] No console warnings

**If all checked:**
# ✅ SYSTEM IS READY FOR USE!

---

## 🐛 TROUBLESHOOTING

### Issue: Port 5001 already in use

```bash
# Find process using port 5001
lsof -i :5001

# Kill it
kill -9 <PID>

# Or use different port
PORT=8080 python3 src/web_dashboard_unified.py
```

### Issue: Module not found

```bash
# Make sure you're in correct directory
pwd
# Should be: /Users/fatbookpro/Desktop/cian

# Reinstall dependencies
pip install --upgrade flask pydantic beautifulsoup4
```

### Issue: Chart not showing

**Check:**
1. Browser console for errors (F12)
2. Network tab - is Chart.js CDN loading?
3. If CDN blocked, download Chart.js locally:
   ```bash
   cd src/static/js
   curl -O https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js
   ```
4. Update HTML to use local file instead of CDN

### Issue: Tooltips not working

**Check:**
1. Is glossary.js loaded? (Network tab)
2. Browser console errors?
3. Try different browser
4. Clear browser cache (Cmd+Shift+R / Ctrl+Shift+F5)

### Issue: Recommendations not appearing

**Check:**
1. Backend logs for errors
2. API response in Network tab
3. Try with different test data
4. Check `recommendations.py` file exists

---

## 📊 SUCCESS CRITERIA

**System is considered ready when:**

✅ **Functional:**
- All API endpoints respond
- UI loads without errors
- All components render
- Interactive features work

✅ **Performance:**
- Page loads in < 2 seconds
- Analysis completes in < 3 seconds
- No memory leaks
- No console errors

✅ **User Experience:**
- Tooltips are helpful
- Recommendations are actionable
- Visualizations are clear
- Mobile-friendly

✅ **Quality:**
- All automated tests pass
- No JavaScript errors
- No broken links
- Clean console

---

## 🚀 YOU'RE DONE!

**If everything above checks out:**

```
✅ Backend: Working
✅ Frontend: Working
✅ API: Working
✅ Tests: Passing
✅ UX: Smooth

🎉 DASHBOARD v2.0 IS LIVE!
```

**Next steps:**
1. Read [VISUAL_GUIDE.md](VISUAL_GUIDE.md) to understand the UI
2. Read [IMPLEMENTATION_COMPLETE.md](IMPLEMENTATION_COMPLETE.md) for features
3. Share with users!
4. Gather feedback
5. Plan next improvements (see Roadmap in SESSION_FINAL_SUMMARY.md)

---

**Need help?**
- Check [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)
- Review [SESSION_FINAL_SUMMARY.md](SESSION_FINAL_SUMMARY.md)
- Re-run tests: `python3 test_unified_dashboard.py`

**Happy analyzing!** 🏠📊💰
