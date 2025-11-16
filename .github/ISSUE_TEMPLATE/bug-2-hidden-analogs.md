---
name: 🔴 P0 Bug - Analogs found but hidden from user
about: Critical UX issue - System finds analogs but doesn't display them
title: '[P0] Analogs found (13) but not displayed on Step 2 - persists 3 deploys'
labels: bug, critical, P0, blocker, UX
assignees: ''
---

## 🔴 SEVERITY: CRITICAL (P0 - SHOWSTOPPER)

**Priority:** Must fix before production launch
**Affected segments:** All (economy, middle, premium)
**Impact:** Complete loss of product value (automation + transparency)
**Status:** Persists through 3 consecutive deploys! 🚨

---

## 📋 Description

The system **finds** analogs (e.g., 13 items for 7.7M object), **uses** them in calculations (median: 282,028 ₽/m²), but **DOES NOT DISPLAY** the list to the user on Step 2.

This is a **critical trust issue** - users cannot see what data the analysis is based on.

## 🔁 Steps to Reproduce

1. Open calculator: https://housler.ru/calculator
2. Load object: `https://spb.cian.ru/sale/flat/322492072/` (7.7M)
3. Complete Step 1 → proceed to Step 2
4. Click "Автоматически найти похожие объекты"
5. Wait for completion (~20 sec)

**Expected:** List of 13 analog cards with details
**Actual:** Empty form with only "Add manually" option

6. Proceed to Step 3
7. **Observe:** Report shows "Found 13 analogs", "Median: 282,028 ₽/m²"

## 🖼️ Expected vs Actual

### Expected UI:

```
╔════════════════════════════════════════════════╗
║ ✓ Найдено 13 похожих объектов                 ║
╠════════════════════════════════════════════════╣
║ [Карточка 1]                                   ║
║ ул. Софийская, 8к1                            ║
║ 38.5 м² • 8 500 000 ₽ • 220 779 ₽/м²         ║
║ 1-комн • 7/16 этаж                            ║
║ [Подробнее →] [❌ Удалить]                    ║
╟────────────────────────────────────────────────╢
║ [Карточка 2]                                   ║
║ ул. Дунайский пр., 7к5                        ║
║ 35.1 м² • 7 200 000 ₽ • 205 128 ₽/м²         ║
║ ...                                            ║
╟────────────────────────────────────────────────╢
║ ... (еще 11 карточек)                         ║
╟────────────────────────────────────────────────╢
║ [+ Добавить аналог вручную]                   ║
║                                                ║
║ [К анализу с 13 объектами →]                  ║
╚════════════════════════════════════════════════╝
```

### Actual UI:

```
╔════════════════════════════════════════════════╗
║ Добавить аналог вручную                       ║
║ [Форма ввода URL]                             ║
║                                                ║
║ (пусто - ничего не отображается)              ║
╚════════════════════════════════════════════════╝
```

## 🔍 Additional Symptoms

On Step 3, unclear warning is displayed:

```
⚠️ Обнаружено 1 проблем с аналогами.
   Проверьте предупреждения выше.
```

But there are **NO warnings above**! User doesn't understand what the problem is.

## 📊 Impact Assessment

- ❌ **Loss of trust:** Client doesn't understand what the analysis is based on
- ❌ **Cannot verify:** Impossible to check if selection is correct
- ❌ **Risk of errors:** System may include irrelevant objects, user won't know
- ❌ **Value reduction:** Step 2 becomes useless (just 20 sec loading)
- ❌ **Competitive advantage lost:** CIAN also shows analogs (free)

## 🔍 Root Cause (Suspected)

### Hypothesis 1: Frontend doesn't receive API data

```javascript
// Probable issue in wizard.js or similar:
const response = await fetch('/api/find-analogs', {...})
const analogs = await response.json()

// BUG: Data not saved to state
// setAnalogs(analogs) <-- this line missing?
```

### Hypothesis 2: Component doesn't render

```jsx
// In wizard.html / wizard.js missing:
<AnalogsList analogs={analogs} />
```

### Hypothesis 3: Data cleared after loading

```javascript
// Bug: data reset when navigating between steps
setAnalogs([]) // <-- accidental reset
```

## 💡 Recommended Fix

### Backend Check

Verify API returns full data:

```python
# app_new.py or similar
@app.route('/api/find-analogs', methods=['POST'])
def find_analogs():
    analogs = search_analogs(property_data)

    return jsonify({
        'success': True,
        'count': len(analogs),
        'analogs': [
            {
                'id': a.id,
                'address': a.address,
                'area': a.area,
                'price': a.price,
                'price_per_sqm': a.price_per_sqm,
                'rooms': a.rooms,
                'floor': a.floor,
                'url': a.url
            }
            for a in analogs
        ]
    })
```

### Frontend Fix

```javascript
// static/js/wizard.js

async function findAnalogs() {
  showLoader("Ищем похожие объекты...")

  const response = await fetch('/api/find-analogs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ property_data })
  })

  const data = await response.json()

  // FIX: Save analogs to state
  window.analogsList = data.analogs
  sessionStorage.setItem('analogs', JSON.stringify(data.analogs))

  // FIX: Display list
  renderAnalogsList(data.analogs)

  hideLoader()
}

function renderAnalogsList(analogs) {
  const container = document.getElementById('analogs-list')

  if (analogs.length === 0) {
    container.innerHTML = '<p class="alert alert-warning">Аналоги не найдены. Попробуйте расширить критерии поиска.</p>'
    return
  }

  let html = `<h3 class="mb-3">✓ Найдено ${analogs.length} похожих объектов</h3>`
  html += '<div class="analogs-grid">'

  analogs.forEach((analog, index) => {
    html += `
      <div class="analog-card" data-id="${analog.id}">
        <div class="analog-header">
          <h5>${analog.address}</h5>
          <button class="btn btn-sm btn-outline-danger" onclick="removeAnalog(${index})">
            ❌ Удалить
          </button>
        </div>
        <div class="analog-body">
          <p><strong>Площадь:</strong> ${analog.area} м²</p>
          <p><strong>Цена:</strong> ${analog.price.toLocaleString()} ₽</p>
          <p><strong>Цена/м²:</strong> ${analog.price_per_sqm.toLocaleString()} ₽/м²</p>
          <p><strong>Комнат:</strong> ${analog.rooms} • <strong>Этаж:</strong> ${analog.floor}</p>
        </div>
        <div class="analog-footer">
          <a href="${analog.url}" target="_blank" class="btn btn-sm btn-primary">
            Подробнее на ЦИАН →
          </a>
        </div>
      </div>
    `
  })

  html += '</div>'
  html += `
    <div class="mt-4">
      <button class="btn btn-lg btn-success" onclick="proceedToAnalysis()">
        К анализу с ${analogs.length} объектами →
      </button>
    </div>
  `

  container.innerHTML = html
}

function removeAnalog(index) {
  window.analogsList.splice(index, 1)
  sessionStorage.setItem('analogs', JSON.stringify(window.analogsList))
  renderAnalogsList(window.analogsList)
}

function proceedToAnalysis() {
  if (window.analogsList.length < 5) {
    alert('Для анализа нужно минимум 5 аналогов. Добавьте еще или снизьте критерии поиска.')
    return
  }

  // Navigate to Step 3
  window.location.hash = '#step-3'
}
```

### CSS (optional)

```css
.analogs-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1rem;
  margin-top: 1rem;
}

.analog-card {
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 1rem;
  background: #fff;
}

.analog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.analog-body {
  margin: 0.5rem 0;
}

.analog-footer {
  margin-top: 1rem;
}
```

## ✅ Acceptance Criteria

- [ ] After auto-search, list of ALL found analogs is displayed
- [ ] Each analog card shows: address, area, price, price/m², rooms, floor
- [ ] User can click "Подробнее" → opens CIAN URL in new tab
- [ ] User can click "Удалить" → analog removed from list
- [ ] Counter updates in real-time: "К анализу с N объектами"
- [ ] If < 5 analogs, show warning before proceeding
- [ ] Fix unclear message "1 проблема с аналогами" → specific explanation

## 🧪 Testing Plan

**Manual tests:**
1. Economy object → 10-15 analogs found and displayed ✅
2. Middle object → 10-15 analogs found and displayed ✅
3. Premium object → 5+ analogs found and displayed ✅ (after Bug #1 fix)
4. Remove 2 analogs → counter updates to "N-2" ✅
5. Proceed with < 5 analogs → warning shown ✅
6. Proceed with 5+ analogs → Step 3 loads with selected analogs ✅

**Regression:**
- Backend calculations still use correct analogs
- Median accuracy unchanged
- Performance < 2 sec for rendering

## ⏰ Estimated Effort

- **Frontend Development:** 6-8 hours
- **Backend Integration:** 2-4 hours
- **Testing:** 4-6 hours
- **Total:** 12-18 hours

## 🔗 Related Issues

- Issue #1: [P0] Premium segment returns 0 analogs
- Issue #3: [P1] Restore Housler forecast section

## 📄 Documentation

- Full audit: `docs/FINAL_COMPREHENSIVE_AUDIT_3_ITERATIONS.md`
- Manual testing: `docs/HOUSLER_MANUAL_TESTING_REPORT.md`
- Test object URL: https://spb.cian.ru/sale/flat/322492072/

## 📊 Historical Context

**Iteration 1:** Bug present
**Iteration 2:** Bug present
**Iteration 3:** **Bug STILL present** 🚨

This has persisted through **3 consecutive deploys**. It's critical to fix NOW before production launch.

---

**Status:** 🔴 BLOCKER
**Target fix date:** Nov 23, 2025
**Target deployment:** Dec 1-8, 2025 (after UAT)
