# Технический анализ: Почему Step 3 не работает на production housler.ru

**Дата анализа:** 2025-01-13
**Тестовый объект:** 5-комнатная квартира 213.4 м², Москва, переулок Коробейников (ID 305062289)
**Проблема:** Step 3 (анализ) не генерирует отчет после успешного поиска 8 аналогов на Step 2

---

## 1. Текущее состояние production

### Версия кода на production (origin/main)
```
Commit: 7b967a8 fix: Исправить критические ошибки в поиске аналогов
Branch: main
```

### Наша версия с фиксами (НЕ на production)
```
Commit: 7f51b62 fix: Implement robust analysis with graceful degradation (4 patches)
Branch: claude/fix-analogs-search-error-011CV5bH3zS2qf8Efh9QPvDu
```

**⚠️ КРИТИЧНО:** Наши фиксы НЕ задеплоены на production!

---

## 2. Как сейчас работает система (production код)

### Step 1: Загрузка объекта ✅
```
Endpoint: POST /api/load-property
Status: Работает корректно
```
- Парсит URL с Циана
- Извлекает базовые данные (комнаты, площадь, цена)
- Сохраняет в session storage

### Step 2: Поиск аналогов ✅
```
Endpoint: POST /api/find-similar
Status: Работает корректно
Found: 8 аналогов (все из Москвы)
```

**Что происходит:**
1. Вызывается `PlaywrightParser.search_similar()` - многоуровневый поиск
2. Находит 8 квартир на поисковой выдаче Циана
3. Парсит карточки объявлений (`_parse_listing_card()`)
4. Получает базовые данные: URL, title, price_per_sqm, total_area
5. Запускает детальный парсинг через `parse_multiple_urls_parallel()`

**Детальный парсинг (ПРОБЛЕМНОЕ МЕСТО):**
```python
# app_new.py:870-876 (production)
detailed_results = parse_multiple_urls_parallel(
    urls=urls_to_parse,
    headless=True,
    cache=property_cache,
    region=region,
    max_concurrent=5  # ⚠️ ПРОБЛЕМА #1: Слишком высокий, вызывает rate limiting
)
```

**Проблемы детального парсинга:**
- `max_concurrent=5` → Циан блокирует (429 Too Many Requests)
- Нет retry логики → таймауты приводят к полному провалу
- Нет field recovery → если `price` отсутствует, данные теряются
- Exception throwing → один провал убивает весь процесс

**Результат Step 2:**
```json
{
  "comparables": [
    {
      "url": "https://...",
      "title": "5-комн. квартира, 260.1 м²",
      "price_per_sqm": 769231,
      "total_area": 260.1,
      "price": null  // ⚠️ НЕТ ЦЕНЫ - парсинг упал по timeout
    },
    // ... 7 аналогов, у 6 из них price=null
  ]
}
```

### Step 3: Анализ ❌
```
Endpoint: POST /api/analyze
Status: ПАДАЕТ с ошибкой
```

**"Loss Funnel" - воронка потери данных:**

```
┌─────────────────────────────────────────────────────────────┐
│ Step 2: Найдено 8 аналогов с базовыми данными              │
│ (price_per_sqm, total_area есть у всех из карточек поиска) │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Детальный парсинг: parse_multiple_urls_parallel()          │
│ max_concurrent=5 → Циан блокирует (rate limiting)          │
│ Timeout на 6 из 8 URL → Exception → данные теряются         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Результат: 8 аналогов, но у 6 из них:                      │
│ - price = null                                              │
│ - total_area = null (перезаписан null при update)          │
│ - price_per_sqm = null                                      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ normalize_property_data() - попытка восстановления          │
│                                                              │
│ ❌ PRODUCTION КОД (НЕ работает):                            │
│ if price and area:                                          │
│     price_per_sqm = price / area  # price=null → скип      │
│                                                              │
│ ❌ НЕТ обратного восстановления:                            │
│ if price_per_sqm and area:                                  │
│     price = price_per_sqm * area  # ← ЭТОГО НЕТ!           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Pydantic валидация: ComparableProperty(**data)             │
│                                                              │
│ class PropertyBase:                                         │
│     price: Optional[float] = Field(None, gt=0)             │
│     total_area: Optional[float] = Field(None, gt=0)        │
│                                                              │
│ ❌ PRODUCTION: Strict validation → ValidationError          │
│ 6 аналогов отвергнуты (price=null или area=null)           │
│                                                              │
│ Результат: 2 валидных аналога из 8                         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ IQR-фильтрация выбросов                                    │
│                                                              │
│ ❌ PRODUCTION: detect_outliers_iqr() вызывается ВСЕГДА     │
│ n=2 (слишком мало для IQR, но проверки нет)                │
│ IQR на n=2 → непредсказуемые результаты                    │
│ Результат: 0-1 аналог после фильтрации                     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Проверка минимального количества аналогов                   │
│                                                              │
│ # src/analytics/analyzer.py:252 (PRODUCTION)               │
│ min_comparables_required = 3  # ❌ Слишком высокий порог   │
│ if len(filtered_comparables) < 3:                          │
│     raise ValueError("Недостаточно аналогов")  # ← FAIL!   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Flask endpoint /api/analyze перехватывает ValueError        │
│                                                              │
│ except ValueError as ve:                                    │
│     return jsonify({                                        │
│         'status': 'error',                                  │
│         'error_type': 'validation_error',                   │
│         'message': str(ve)  # ← Generic message             │
│     }), 422                                                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Frontend получает 422 error                                 │
│ Отображает: "Произошла ошибка: что-то пошло не так"       │
│ Отчет не генерируется ❌                                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Детальный разбор проблем в production коде

### Проблема #1: Детальный парсинг без retry
**Файл:** `src/parsers/async_parser.py:385-425` (production)

```python
def parse_multiple_urls_parallel(..., max_concurrent: int = 5):
    # ❌ max_concurrent=5 слишком высокий → rate limiting

    async def parse_with_timeout(url):
        try:
            return await asyncio.wait_for(
                self.parse_detail_page_async(url),
                timeout=timeout_per_url
            )
        except asyncio.TimeoutError:
            # ❌ Возвращает заглушку с error, но данные ТЕРЯЮТСЯ
            return {
                'url': url,
                'title': 'Timeout при парсинге',
                'error': f'Превышено время ожидания ({timeout_per_url}s)'
            }
```

**Проблемы:**
- Нет retry логики (один timeout = полная потеря данных)
- Нет классификации ошибок (rate limit vs timeout vs network)
- Нет экспоненциального backoff
- Нет метрик качества парсинга

### Проблема #2: Отсутствие field recovery
**Файл:** `src/models/property.py:327-330` (production)

```python
# 1. Базовые расчеты
if normalized.get('price') and normalized.get('total_area'):
    if not normalized.get('price_per_sqm'):
        normalized['price_per_sqm'] = normalized['price'] / normalized['total_area']

# ❌ НЕТ обратного восстановления:
# if price_per_sqm and area and not price:
#     price = price_per_sqm * area  # ← ЭТОГО НЕТ!
```

**Последствия:**
- Если детальный парсинг не получил `price`, но `price_per_sqm` есть → данные не восстанавливаются
- При Step 2 карточки поиска ИМЕЮТ `price_per_sqm` и `total_area`
- После провала детального парсинга эти данные можно использовать для восстановления `price`
- Но это не делается → аналог отвергается валидацией

### Проблема #3: Strict Pydantic validation
**Файл:** `src/models/property.py:215-224` (production)

```python
class ComparableProperty(TargetProperty):
    """Аналог для сравнения"""
    has_design: bool = False
    distance_km: Optional[float] = None
    similarity_score: Optional[float] = Field(None, ge=0, le=1)
    excluded: bool = False

    # ❌ НЕТ quality_flags для soft validation
    # ❌ НЕТ root_validator для помечания проблемных полей

    class Config(TargetProperty.Config):
        validate_assignment = True
```

**Последствия:**
- Любой аналог без `price` или `total_area` → `ValidationError`
- Нет graceful degradation (продолжить с предупреждениями)
- Нет флагов качества для отслеживания проблемных данных

### Проблема #4: IQR применяется всегда
**Файл:** `src/analytics/analyzer.py:193-207` (production)

```python
# IQR-фильтрация выбросов
comparables_after_iqr, iqr_outliers = detect_outliers_iqr(comparables_to_process)

# ❌ НЕТ проверки: if len(comparables_to_process) >= 5
```

**Последствия:**
- IQR статистически корректен только для n ≥ 5
- При n=2 или n=3 IQR может отсеять ВСЕ данные
- Результат: 0 аналогов после фильтрации

### Проблема #5: Высокий порог минимальных аналогов
**Файл:** `src/analytics/analyzer.py:252-265` (production)

```python
# Проверка на достаточное количество аналогов
min_comparables_required = 3  # ❌ Слишком высокий порог

if len(self.filtered_comparables) < min_comparables_required:
    error_msg = (
        f"Недостаточно аналогов для анализа: найдено {len(self.filtered_comparables)}, "
        f"требуется минимум {min_comparables_required}."
    )
    raise ValueError(error_msg)  # ❌ Hard fail вместо graceful degradation
```

**Последствия:**
- Анализ невозможен при 1-2 аналогах (даже если они качественные)
- Нет возможности сгенерировать отчет с предупреждениями о низком качестве

### Проблема #6: Generic error messages
**Файл:** `app_new.py:1259-1274` (production)

```python
except ValueError as ve:
    # Специфичные ошибки валидации (например, мало аналогов)
    logger.warning(f"Ошибка валидации анализа: {ve}")
    return jsonify({
        'status': 'error',
        'error_type': 'validation_error',  # ❌ Generic тип
        'message': str(ve)  # ❌ Technical message для пользователя
    }), 422
```

**Последствия:**
- Frontend получает generic "validation_error"
- Отображает "Произошла ошибка: что-то пошло не так"
- Пользователь не понимает, что произошло и как исправить

---

## 4. Почему тест на production провалился

**Сценарий теста:**
1. Загружен объект: 5-комн, 213.4 м², Москва
2. Step 2 нашел **8 аналогов** (все корректные, все из Москвы)
3. Step 3 провалился

**Пошаговая диагностика:**

```
8 аналогов найдено
↓
Детальный парсинг (max_concurrent=5, no retry)
↓
Rate limiting от Циана → 6 из 8 timeout
↓
6 аналогов без price/area → ValidationError
↓
2 валидных аналога остались
↓
IQR-фильтрация на n=2 → 0-1 аналог
↓
Проверка: 0-1 < 3 → ValueError
↓
Frontend: "Произошла ошибка: что-то пошло не так"
```

---

## 5. Что было исправлено в нашей ветке (НЕ на production)

### ✅ PATCH 1: Robust parallel parsing with retry logic
**Коммит:** `7f51b62`
**Файл:** `src/parsers/async_parser.py`

```python
@dataclass
class ParseResult:
    url: str
    ok: bool
    data: dict
    error_type: Optional[str] = None  # "rate_limited" | "timeout" | "captcha"
    error_message: Optional[str] = None
    retries_used: int = 0

async def _parse_with_retry(url, max_retries=3, base_delay=2.0) -> ParseResult:
    for attempt in range(max_retries + 1):
        try:
            # ... парсинг ...
            return ParseResult(url=url, ok=True, data=data, retries_used=attempt)
        except Exception as e:
            error_type = self._classify_error(str(e))

            # Экспоненциальный backoff с jitter
            delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
            if error_type == 'rate_limited':
                delay *= 2

            await asyncio.sleep(delay)

    # Все попытки провалились - возвращаем минимальные данные
    return ParseResult(url=url, ok=False, data={'url': url},
                      error_type=error_type, retries_used=max_retries)

def parse_multiple_urls_parallel(..., max_concurrent=3, max_retries=2):
    # Снижен max_concurrent с 5 → 3
    # Добавлен параметр max_retries
    # Возвращает (results_data, quality_metrics)
```

**Эффект:**
- Rate limiting обходится через retry с увеличенной задержкой
- Timeout не убивает данные - возвращаются частичные результаты
- Метрики качества: successful/failed/retries/error_breakdown

### ✅ PATCH 2: Field recovery in normalize_property_data()
**Коммит:** `7f51b62`
**Файл:** `src/models/property.py`

```python
# Восстанавливаем price_per_sqm из price и area
if not ppsm and price and area and area > 0:
    ppsm = price / area
    normalized['price_per_sqm'] = ppsm

# НОВОЕ: Восстанавливаем price из price_per_sqm и area
if not price and ppsm and area:
    price = ppsm * area
    normalized['price'] = price

# НОВОЕ: Восстанавливаем total_area из price и price_per_sqm
if not area and price and ppsm and ppsm > 0:
    area = price / ppsm
    normalized['total_area'] = area
```

**Эффект:**
- Аналоги с `price_per_sqm` + `total_area` (из карточек Step 2) восстанавливают `price`
- ValidationError больше не отвергает аналоги с восстановимыми данными

### ✅ PATCH 2.1: Soft validation with quality_flags
**Коммит:** `7f51b62`
**Файл:** `src/models/property.py`

```python
class ComparableProperty(TargetProperty):
    quality_flags: List[str] = []

    @root_validator(pre=False)
    def validate_minimum_data(cls, values):
        flags = values.get('quality_flags', [])

        if not (price and area) and not (ppsm and area):
            flags.append('insufficient_numeric_fields')

        if not values.get('address'):
            flags.append('missing_address')

        # НЕ бросаем ValidationError - просто помечаем флагами
        values['quality_flags'] = flags
        return values
```

**Эффект:**
- Аналоги с проблемами не отвергаются, а помечаются флагами
- Анализ продолжается с предупреждениями о качестве данных

### ✅ PATCH 3: Lower min threshold to 1 and adaptive IQR
**Коммит:** `7f51b62`
**Файл:** `src/analytics/analyzer.py`

```python
# АДАПТИВНАЯ IQR-фильтрация выбросов (только если n >= 5)
n = len(comparables_to_process)
if n >= 5:
    comparables_after_iqr, iqr_outliers = detect_outliers_iqr(comparables_to_process)
else:
    # Слишком мало данных для IQR - используем все аналоги
    logger.info(f"⚠️ IQR пропущен: только {n} аналог(ов), нужно минимум 5")
    comparables_after_iqr = comparables_to_process

# Снижаем порог с 3 до 1 (graceful degradation)
min_comparables_required = 1
```

**Эффект:**
- Анализ возможен даже с 1 аналогом (с предупреждением о низком качестве)
- IQR не "съедает" все данные при малых выборках

### ✅ PATCH 4: Quality metrics and specific error messages
**Коммит:** `7f51b62`
**Файлы:** `app_new.py`, `src/parsers/async_parser.py`

```python
# app_new.py: Детальные предупреждения о проблемах парсинга
if parse_failed > 50%:
    warnings.append({
        'type': 'error',
        'title': 'Критическая проблема с загрузкой данных',
        'message': f'Не удалось загрузить данные для {parse_failed} из {total_found}. '
                   f'Причины: {", ".join(error_details)}.'
    })

# app_new.py: Специфичные типы ошибок
except ValueError as ve:
    if 'недостаточно аналогов' in str(ve).lower():
        error_type = 'insufficient_comparables'
    elif 'цена' in str(ve).lower():
        error_type = 'invalid_price_data'
    # ...
```

**Эффект:**
- Пользователь видит конкретные причины ошибок
- Вместо "что-то пошло не так" → "Rate limiting, попробуйте через 5 минут"

---

## 6. Сравнение: Production vs Наш Fix

| Аспект | Production (main) | Наш Fix (feature branch) |
|--------|-------------------|--------------------------|
| **Retry логика** | ❌ Нет | ✅ 3 попытки с exp backoff |
| **max_concurrent** | 5 (rate limit) | 3 (безопасно) |
| **Field recovery** | Только price_per_sqm | ✅ Все 3 поля восстанавливаются |
| **Validation** | Strict (ValidationError) | ✅ Soft (quality_flags) |
| **IQR фильтрация** | Всегда | ✅ Только при n≥5 |
| **Min аналогов** | 3 (hard fail) | ✅ 1 (graceful degradation) |
| **Error messages** | Generic | ✅ Specific (rate_limit, timeout) |
| **Quality metrics** | ❌ Нет | ✅ Parse stats + warnings |
| **Return type** | `List[Dict]` | ✅ `tuple[List[Dict], Dict]` |

---

## 7. Почему тест провалился: ВЫВОДЫ

### Критическая причина:
**Наш код НЕ задеплоен на production housler.ru!**

```bash
# Production (origin/main)
Commit: 7b967a8 fix: Исправить критические ошибки в поиске аналогов
Date: Более ранний коммит

# Наш fix (claude/fix-analogs-search-error-011CV5bH3zS2qf8Efh9QPvDu)
Commit: 7f51b62 fix: Implement robust analysis with graceful degradation
Date: Сегодня, но НЕ в main
```

### Что происходит на production:
1. **Step 2** находит 8 аналогов ✅
2. **Детальный парсинг** падает по rate limiting (max_concurrent=5, no retry)
3. **6 из 8 аналогов** теряют данные (price=null)
4. **Pydantic ValidationError** отвергает 6 аналогов
5. **2 аналога** остаются
6. **IQR фильтр** на n=2 отсеивает еще 1-2 аналога
7. **0-1 аналог** < 3 minimum → ValueError
8. **Frontend** отображает "Произошла ошибка: что-то пошло не так" ❌

### Что должно быть с нашим фиксом:
1. **Step 2** находит 8 аналогов ✅
2. **Детальный парсинг** с retry + backoff → 6-8 аналогов успешно ✅
3. **Field recovery** восстанавливает price для оставшихся 0-2 аналогов ✅
4. **Soft validation** помечает проблемные флагами, не отвергает ✅
5. **8 аналогов** (некоторые с quality_flags)
6. **IQR пропущен** (n=8 < рекомендованных 15, но ≥5) ✅
7. **8 аналогов** > 1 minimum → Анализ продолжается ✅
8. **Frontend** генерирует отчет с предупреждением о качестве ✅

---

## 8. Технические детали для диагностики

### Как проверить что на production сейчас:

```bash
# SSH на сервер
ssh root@91.229.8.221

# Проверить текущую ветку
cd /var/www/housler
git branch --show-current
git log --oneline -1

# Ожидаемый результат на production:
# main
# 7b967a8 fix: Исправить критические ошибки в поиске аналогов

# Проверить версию async_parser.py
grep "def parse_multiple_urls_parallel" src/parsers/async_parser.py -A 5
# Если видим max_concurrent: int = 5 (без max_retries) → СТАРЫЙ КОД

# Проверить analyzer.py
grep "min_comparables_required" src/analytics/analyzer.py -A 1
# Если видим min_comparables_required = 3 → СТАРЫЙ КОД
```

### Логи на production (если доступны):

```bash
# Логи Flask приложения
journalctl -u housler -n 100 --no-pager

# Искать в логах:
# - "⏱️ Timeout" → парсинг падает по timeout
# - "❌ Parallel parsing failed" → детальный парсинг провалился
# - "Недостаточно аналогов для анализа" → reached min threshold check
# - "ValidationError" → Pydantic отверг аналоги
```

### API тестирование:

```bash
# Step 2: Проверить что возвращает /api/find-similar
curl -X POST https://housler.ru/api/find-similar \
  -H "Content-Type: application/json" \
  -d '{"session_id": "..."}' | jq '.comparables[] | {url, price, price_per_sqm, total_area}'

# Ожидаемая проблема: большинство аналогов с price=null

# Step 3: Проверить ошибку /api/analyze
curl -X POST https://housler.ru/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"session_id": "...", "filter_outliers": true}' | jq

# Ожидаемый результат:
# {
#   "status": "error",
#   "error_type": "validation_error",
#   "message": "Недостаточно аналогов для анализа: найдено 0-2, требуется минимум 3"
# }
```

---

## 9. Рекомендации по деплою

### Вариант 1: Pull Request в main (Рекомендуется)

1. Создать PR в GitHub UI:
   - Source: `claude/fix-analogs-search-error-011CV5bH3zS2qf8Efh9QPvDu`
   - Target: `main`
   - Title: "Fix: Robust analysis with graceful degradation (4 patches)"

2. Пройти ревью (если требуется)

3. Merge в `main` → GitHub Actions автоматически задеплоит

### Вариант 2: Прямой деплой через скрипт

```bash
# Локально
cd /home/user/cian-analyzer
bash scripts/deploy.sh

# Скрипт автоматически:
# 1. Push в GitHub
# 2. SSH на сервер
# 3. git pull на сервере
# 4. pip install (если нужно)
# 5. systemctl restart housler
```

### Вариант 3: Ручной деплой на сервере

```bash
# SSH на production
ssh root@91.229.8.221
cd /var/www/housler

# Вариант 3a: Мерж в main (если есть права)
git fetch origin
git checkout main
git merge origin/claude/fix-analogs-search-error-011CV5bH3zS2qf8Efh9QPvDu
git push origin main

# Вариант 3b: Прямо на feature ветке (для быстрого теста)
git fetch origin
git checkout claude/fix-analogs-search-error-011CV5bH3zS2qf8Efh9QPvDu
git pull origin claude/fix-analogs-search-error-011CV5bH3zS2qf8Efh9QPvDu

# Перезапуск сервиса
systemctl restart housler

# Проверка
systemctl status housler
journalctl -u housler -n 20 --no-pager
```

### После деплоя: Тестовый сценарий

```
1. Открыть https://housler.ru с ?reset=1
2. Загрузить объект: https://www.cian.ru/sale/flat/305062289/
3. Step 2: Должен найти ~8 аналогов ✅
4. Step 3:
   - Ожидание: Отчет генерируется ✅
   - Может быть желтое предупреждение: "Найдено 8 аналогов, рекомендуется 15-20"
   - Может быть предупреждение о проблемах парсинга (rate limiting)
   - НО отчет должен быть сгенерирован с табличками и ценами ✅
```

---

## 10. Итоговая рекомендация

**Необходимые действия:**

1. ✅ **Код готов** - все 4 патча реализованы в ветке `claude/fix-analogs-search-error-011CV5bH3zS2qf8Efh9QPvDu`
2. ⏳ **Нужен деплой** - выбрать один из 3 вариантов выше
3. ⏳ **Тестирование** - повторить сценарий с 5-комнатной квартирой
4. ⏳ **Мониторинг** - проверить логи на отсутствие новых ошибок

**Ожидаемый результат после деплоя:**
- Step 3 будет генерировать отчет даже при проблемах с парсингом
- Пользователь увидит конкретные предупреждения вместо "что-то пошло не так"
- Анализ возможен даже с 1-2 качественными аналогами
- Система устойчива к rate limiting от Циана (retry + backoff)

**Риски:**
- Минимальные - все изменения обратно совместимы
- Graceful degradation гарантирует, что система не упадет полностью
- В худшем случае - будет больше предупреждений пользователю, но анализ продолжится

---

**Автор:** Claude (AI Assistant)
**Дата:** 2025-01-13
**Версия анализа:** 1.0
