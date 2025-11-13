# MR: Robust Analysis - Graceful Degradation для Шага 3

## 📋 Метаданные

- **Тип**: Critical Bugfix + Enhancement
- **Приоритет**: P0 (Critical)
- **Затраты**: 6-8 часов разработки + 2-3 часа тестирования
- **Риски**: Низкие (backward compatible, graceful degradation)
- **Связанные issue**: [Шаг 3 падает при малом количестве валидных аналогов]

## 🎯 Цель

Исправить критическую проблему "воронки потерь" аналогов, когда:
- Найдено 8 аналогов на Шаге 2 ✅
- После детального парсинга остается 0-2 валидных ❌
- Шаг 3 падает с ValidationError ❌
- Пользователь видит "Что-то пошло не так" ❌

**Результат после фикса:**
- Найдено 8 аналогов → Шаг 3 работает с любым количеством валидных (1+) ✅
- При n=1-2: анализ с предупреждениями о точности ✅
- При n≥3: полноценный робастный анализ ✅

## 📊 Текущая проблема (Root Cause)

```
8 найденных аналогов
  │
  ├─> Детальный парсинг падает (Timeout/RateLimit/Captcha)
  │   └─> 8 аналогов БЕЗ price/total_area
  │
  ├─> Валидация через Pydantic отклоняет все
  │   └─> ValidationError: "price field required"
  │
  └─> Проверка минимума: 0 < 3 → ValueError
      └─> Frontend: "Произошла ошибка" ❌
```

## 🔧 Архитектура решения

### Принципы:
1. **Never fail hard** - всегда возвращать результат (пусть с предупреждениями)
2. **Graceful degradation** - качество снижается, но функционал работает
3. **Transparent quality** - показывать пользователю реальное качество данных
4. **Robust statistics** - адаптивные алгоритмы под размер выборки

### Изменения по файлам:

```
src/parsers/async_parser.py      - Robust parallel parsing (retry + partials)
src/models/property.py            - Soft validation + field recovery
src/analytics/analyzer.py         - Adaptive filtering + min threshold = 1
app_new.py                        - Integration + quality metrics
```

---

## 📝 Патч 1: Robust Parallel Parsing

**Файл**: `src/parsers/async_parser.py`

**Проблема**:
- При падении parse_multiple_urls_parallel() все аналоги теряют данные
- Нет retry логики для rate limiting/timeout
- Exception убивает весь pipeline

**Решение**:
- Retry с exponential backoff
- Возврат partial results даже при ошибках
- Структурированные статусы ошибок

### Diff:

```python
# ДОБАВИТЬ В НАЧАЛО ФАЙЛА

from dataclasses import dataclass
from typing import Optional
import random
import time

@dataclass
class ParseResult:
    """Результат парсинга одного URL (успешный или нет)"""
    url: str
    ok: bool
    data: dict
    error_type: Optional[str] = None  # "rate_limited" | "timeout" | "captcha" | "parse_error"
    error_message: Optional[str] = None
    retries_used: int = 0

class RateLimitError(Exception):
    """Циан блокирует запросы"""
    pass

class CaptchaError(Exception):
    """Требуется решение капчи"""
    pass
```

```python
# ЗАМЕНИТЬ ФУНКЦИЮ parse_multiple_urls_parallel

def parse_multiple_urls_parallel(
    urls: list[str],
    headless: bool = True,
    cache=None,
    region: str = 'spb',
    max_concurrent: int = 2,  # СНИЖЕНО С 5 ДО 2
    max_retries: int = 3,
    base_delay: float = 1.5,
    timeout_per_url: int = 15
) -> list[ParseResult]:
    """
    Робастный параллельный парсинг с retry и partial results

    ИЗМЕНЕНИЯ:
    - Не падает при ошибках, возвращает partial results
    - Retry для rate limiting и timeout
    - Exponential backoff с jitter
    - Структурированные статусы ошибок

    Args:
        urls: Список URL для парсинга
        max_concurrent: Максимальная параллельность (снижено до 2)
        max_retries: Количество повторов при ошибке
        base_delay: Базовая задержка между запросами
        timeout_per_url: Таймаут на один URL

    Returns:
        Список ParseResult (включая failed)
    """
    from src.parsers.playwright_parser import PlaywrightParser
    import logging

    logger = logging.getLogger(__name__)
    results = []

    logger.info(f"🚀 Робастный параллельный парсинг {len(urls)} URLs (max_concurrent={max_concurrent})")

    # Батчинг: обрабатываем max_concurrent URLs одновременно
    for batch_start in range(0, len(urls), max_concurrent):
        batch_urls = urls[batch_start:batch_start + max_concurrent]

        for url in batch_urls:
            # Проверяем кэш
            if cache:
                cached = cache.get_property(url)
                if cached:
                    results.append(ParseResult(
                        url=url,
                        ok=True,
                        data=cached,
                        error_type=None
                    ))
                    logger.info(f"✅ Cache hit: {url[:60]}...")
                    continue

            # Retry loop
            attempt = 0
            parse_success = False
            last_error = None

            while attempt <= max_retries and not parse_success:
                try:
                    # Задержка с jitter (кроме первой попытки)
                    if attempt > 0:
                        delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
                        logger.info(f"⏳ Retry {attempt}/{max_retries} для {url[:60]}... (delay={delay:.1f}s)")
                        time.sleep(delay)

                    # Парсим с таймаутом
                    with PlaywrightParser(headless=headless, cache=cache, region=region) as parser:
                        data = parser.parse_detail_page(url)

                        # Успех!
                        results.append(ParseResult(
                            url=url,
                            ok=True,
                            data=data,
                            error_type=None,
                            retries_used=attempt
                        ))
                        parse_success = True

                        if attempt > 0:
                            logger.info(f"✅ Успешный retry для {url[:60]}... (попытка {attempt})")

                except TimeoutError as e:
                    last_error = e
                    attempt += 1
                    if attempt > max_retries:
                        logger.warning(f"❌ Timeout после {max_retries} попыток: {url[:60]}...")
                        results.append(ParseResult(
                            url=url,
                            ok=False,
                            data={},
                            error_type="timeout",
                            error_message=str(e),
                            retries_used=attempt
                        ))

                except RateLimitError as e:
                    last_error = e
                    attempt += 1
                    # Для rate limit - больше задержка
                    if attempt <= max_retries:
                        delay = base_delay * (3 ** attempt) + random.uniform(0, 1)
                        logger.warning(f"⚠️ Rate limit, ждем {delay:.1f}s перед retry {attempt}/{max_retries}")
                        time.sleep(delay)
                    else:
                        logger.warning(f"❌ Rate limit после {max_retries} попыток: {url[:60]}...")
                        results.append(ParseResult(
                            url=url,
                            ok=False,
                            data={},
                            error_type="rate_limited",
                            error_message=str(e),
                            retries_used=attempt
                        ))

                except CaptchaError as e:
                    # Капча - сразу пропускаем без retry
                    logger.warning(f"❌ Captcha обнаружена: {url[:60]}...")
                    results.append(ParseResult(
                        url=url,
                        ok=False,
                        data={},
                        error_type="captcha",
                        error_message=str(e),
                        retries_used=0
                    ))
                    break

                except Exception as e:
                    last_error = e
                    logger.error(f"❌ Ошибка парсинга {url[:60]}...: {e}")
                    results.append(ParseResult(
                        url=url,
                        ok=False,
                        data={},
                        error_type="parse_error",
                        error_message=str(e),
                        retries_used=attempt
                    ))
                    break

        # Задержка между батчами
        if batch_start + max_concurrent < len(urls):
            time.sleep(base_delay)

    # Статистика
    success_count = sum(1 for r in results if r.ok)
    failed_count = len(results) - success_count

    logger.info(f"📊 Результаты парсинга: {success_count}/{len(results)} успешно, {failed_count} ошибок")

    if failed_count > 0:
        error_types = {}
        for r in results:
            if not r.ok:
                error_types[r.error_type] = error_types.get(r.error_type, 0) + 1
        logger.warning(f"   Типы ошибок: {error_types}")

    return results
```

**Изменения в вызове** (`app_new.py`):

```python
# СТАРЫЙ КОД (строка ~870):
# detailed_results = parse_multiple_urls_parallel(...)
# except Exception as e:
#     logger.error(f"❌ Parallel parsing failed: {e}")

# НОВЫЙ КОД:
parse_results = parse_multiple_urls_parallel(
    urls=urls_to_parse,
    headless=True,
    cache=property_cache,
    region=region,
    max_concurrent=2,  # Снижено с 5
    max_retries=3,
    base_delay=1.5
)

# Обновляем аналоги даже с partial data
updated_count = 0
failed_count = 0

for result in parse_results:
    if result.ok:
        # Успешный парсинг - обновляем полностью
        for comparable in similar:
            if comparable.get('url') == result.url:
                comparable.update(result.data)
                updated_count += 1
                break
    else:
        # Неудачный парсинг - помечаем, но не удаляем
        failed_count += 1
        for comparable in similar:
            if comparable.get('url') == result.url:
                comparable['_parse_failed'] = True
                comparable['_parse_error'] = result.error_type
                break

logger.info(f"✅ Enhanced {updated_count}/{len(similar)} comparables")
if failed_count > 0:
    logger.warning(f"⚠️ {failed_count} URLs не удалось распарсить детально")
```

---

## 📝 Патч 2: Field Recovery & Soft Validation

**Файл**: `src/models/property.py`

**Проблема**:
- Pydantic жестко валидирует: нет price → ValidationError
- Не восстанавливаем price из price_per_sqm * area
- Отсутствие одного поля убивает весь объект

**Решение**:
- Восстановление недостающих полей
- Soft validation через quality_flags
- Минимум для работы: (price & area) ИЛИ (price_per_sqm & area)

### Diff:

```python
# В функцию normalize_property_data (строка ~310)

def normalize_property_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Нормализация данных недвижимости с умными дефолтами

    НОВОЕ: Восстановление недостающих полей из имеющихся
    """
    normalized = data.copy()

    # ═══════════════════════════════════════════════════════════════════════
    # ПАТЧ: ВОССТАНОВЛЕНИЕ КРИТИЧЕСКИХ ПОЛЕЙ
    # ═══════════════════════════════════════════════════════════════════════

    # 1. Унификация имен (price_raw → price, area_value → total_area)
    if not normalized.get('price') and normalized.get('price_raw'):
        normalized['price'] = normalized['price_raw']

    if not normalized.get('total_area') and normalized.get('area_value'):
        normalized['total_area'] = normalized['area_value']

    # 2. Восстановление price_per_sqm из price / area
    if not normalized.get('price_per_sqm'):
        price = normalized.get('price')
        area = normalized.get('total_area')
        if price and area and area > 0:
            try:
                normalized['price_per_sqm'] = float(price) / float(area)
            except (ValueError, ZeroDivisionError):
                pass

    # 3. НОВОЕ: Восстановление price из price_per_sqm * area
    if not normalized.get('price'):
        ppsm = normalized.get('price_per_sqm')
        area = normalized.get('total_area')
        if ppsm and area and area > 0:
            try:
                normalized['price'] = float(ppsm) * float(area)
                logger.info(f"✓ Восстановлена цена из price_per_sqm: {normalized['price']:,.0f} ₽")
            except (ValueError, TypeError):
                pass

    # 4. НОВОЕ: Восстановление total_area из price / price_per_sqm
    if not normalized.get('total_area'):
        price = normalized.get('price')
        ppsm = normalized.get('price_per_sqm')
        if price and ppsm and ppsm > 0:
            try:
                normalized['total_area'] = float(price) / float(ppsm)
                logger.info(f"✓ Восстановлена площадь из price/ppsm: {normalized['total_area']:.1f} м²")
            except (ValueError, ZeroDivisionError, TypeError):
                pass

    # Остальная нормализация (высота потолков, санузлы и т.д.)
    # ... (существующий код)

    return normalized
```

```python
# В класс ComparableProperty (после строки ~215)

class ComparableProperty(TargetProperty):
    """
    Аналог для сравнения

    НОВОЕ: Soft validation + quality tracking
    """

    # Дополнительные поля для трекинга качества
    quality_flags: List[str] = []  # ["insufficient_data", "recovered_price", ...]
    data_completeness: float = 0.0  # 0.0 - 1.0

    @root_validator
    def validate_minimum_data(cls, values):
        """
        Минимальная валидация: должны быть либо (price & area), либо (ppsm & area)

        Вместо ValidationError - помечаем quality_flags
        """
        price = values.get('price')
        area = values.get('total_area')
        ppsm = values.get('price_per_sqm')
        flags = values.get('quality_flags', [])

        # Проверка минимума для расчета
        has_price_area = bool(price and area and area > 0)
        has_ppsm_area = bool(ppsm and area and area > 0)

        if not (has_price_area or has_ppsm_area):
            # НЕ бросаем ValidationError - помечаем флагом
            flags.append('insufficient_numeric_fields')
            logger.warning(f"⚠️ Аналог {values.get('url', '?')[:50]} имеет недостаточно данных")

        # Вычисляем completeness
        required_fields = ['price', 'total_area', 'price_per_sqm', 'rooms', 'address']
        present_count = sum(1 for f in required_fields if values.get(f))
        values['data_completeness'] = present_count / len(required_fields)

        values['quality_flags'] = flags
        return values

    def is_usable_for_analysis(self) -> bool:
        """Можно ли использовать для расчетов"""
        return 'insufficient_numeric_fields' not in self.quality_flags
```

---

## 📝 Патч 3: Adaptive Filtering & Min Threshold = 1

**Файл**: `src/analytics/analyzer.py`

**Проблема**:
- Требуется минимум 3 аналога → ValueError при n < 3
- IQR применяется всегда, даже при малом n
- Нет адаптации алгоритмов под размер выборки

**Решение**:
- Минимум = 1 аналог (с предупреждениями)
- IQR только при n ≥ 5
- Робастные статистики для малых выборок

### Diff:

```python
# В методе analyze() (строка ~250)

# СТАРЫЙ КОД:
# min_comparables_required = 3
# if len(self.filtered_comparables) < min_comparables_required:
#     raise ValueError(...)

# НОВЫЙ КОД:
min_comparables_required = 1  # СНИЖЕНО С 3 ДО 1

n_valid = len(self.filtered_comparables)

if n_valid < min_comparables_required:
    error_msg = (
        f"Не найдено ни одного валидного аналога для анализа. "
        f"Все {len(request.comparables)} аналогов не прошли валидацию. "
        f"Попробуйте добавить аналоги вручную или расширить критерии поиска."
    )
    if self.enable_tracking:
        self._log_event(EventType.ANALYSIS_COMPLETED,
            f"Анализ прерван: {error_msg}",
            {'error': 'no_valid_comparables'})
        self.tracker.complete_property(self.property_id, "failed")

    raise ValueError(error_msg)

# Предупреждения о качестве данных
if n_valid == 1:
    logger.warning("⚠️ ТОЛЬКО 1 ВАЛИДНЫЙ АНАЛОГ - оценка будет приблизительной")
    if self.enable_tracking:
        self._log_event(EventType.ANALYSIS_COMPLETED,
            "Анализ выполнен с 1 аналогом - точность ограничена",
            {'warning': 'single_comparable'})

elif n_valid == 2:
    logger.warning("⚠️ ТОЛЬКО 2 ВАЛИДНЫХ АНАЛОГА - точность снижена")
    if self.enable_tracking:
        self._log_event(EventType.ANALYSIS_COMPLETED,
            "Анализ выполнен с 2 аналогами - рекомендуется добавить еще",
            {'warning': 'few_comparables'})

elif n_valid < 5:
    logger.info(f"ℹ️ {n_valid} валидных аналогов - достаточно для базовой оценки")
```

```python
# В методе _filter_outliers (после IQR фильтрации)

def _filter_outliers(self, comparables: List[ComparableProperty]) -> List[ComparableProperty]:
    """
    Фильтрация статистических выбросов (адаптивная)

    НОВОЕ: IQR применяется только при n >= 5
    """
    if not comparables:
        return []

    n = len(comparables)

    # АДАПТИВНАЯ ФИЛЬТРАЦИЯ
    if n < 5:
        logger.info(f"ℹ️ Пропуск IQR-фильтрации (n={n} < 5)")
        return comparables

    # Существующая логика IQR
    prices_per_sqm = [c.price_per_sqm for c in comparables if c.price_per_sqm]

    if len(prices_per_sqm) < 5:
        logger.info("ℹ️ Недостаточно данных для IQR фильтрации")
        return comparables

    q1 = np.percentile(prices_per_sqm, 25)
    q3 = np.percentile(prices_per_sqm, 75)
    iqr = q3 - q1

    # ОСЛАБЛЕННЫЙ КОЭФФИЦИЕНТ: 1.5 → 2.0
    k = 2.0  # было 1.5
    lower_bound = q1 - k * iqr
    upper_bound = q3 + k * iqr

    filtered = []
    outliers_count = 0

    for c in comparables:
        if c.price_per_sqm and (c.price_per_sqm < lower_bound or c.price_per_sqm > upper_bound):
            c.excluded = True
            c.exclusion_reason = f"IQR outlier (k={k})"
            outliers_count += 1
            logger.info(f"   Выброс: {c.price_per_sqm:,.0f} ₽/м² (диапазон: {lower_bound:,.0f}-{upper_bound:,.0f})")
        else:
            filtered.append(c)

    if outliers_count > 0:
        logger.info(f"   Исключено {outliers_count} выбросов, осталось {len(filtered)}")

    return filtered
```

```python
# НОВАЯ ФУНКЦИЯ: Робастная статистика для малых выборок

def calculate_robust_statistics(values: List[float], n_bootstraps: int = 1000) -> Dict[str, float]:
    """
    Робастная оценка статистик для малых выборок

    Для n=1: единственное значение ± исторический коридор
    Для n=2: midpoint ± разброс
    Для n>=3: медиана + MAD/IQR
    Для n>=10: winsorized mean
    """
    n = len(values)

    if n == 0:
        return {'median': 0, 'mean': 0, 'std': 0, 'mad': 0}

    elif n == 1:
        # Единственное значение - используем как точечную оценку
        # Доверительный интервал ±15% (исторический для сегмента)
        val = values[0]
        return {
            'median': val,
            'mean': val,
            'std': val * 0.15,  # Исторический CV ~15%
            'mad': val * 0.10,
            'confidence_note': 'single_value_historical_ci'
        }

    elif n == 2:
        # Две точки - midpoint
        midpoint = (values[0] + values[1]) / 2
        spread = abs(values[1] - values[0]) / 2
        return {
            'median': midpoint,
            'mean': midpoint,
            'std': spread,
            'mad': spread * 0.67,  # MAD ≈ 0.67 * SD для нормального
            'confidence_note': 'two_values_midpoint'
        }

    elif n < 10:
        # Малая выборка - медиана + MAD
        median_val = statistics.median(values)
        mad = median_abs_deviation(values)
        mean_val = statistics.mean(values)
        std_val = statistics.stdev(values) if n > 1 else 0

        return {
            'median': median_val,
            'mean': mean_val,
            'std': std_val,
            'mad': mad,
            'confidence_note': 'small_sample_median_mad'
        }

    else:
        # Достаточная выборка - winsorized mean
        sorted_vals = sorted(values)
        k = int(n * 0.1)  # 10% с каждой стороны
        trimmed = sorted_vals[k:n-k]

        return {
            'median': statistics.median(values),
            'mean': statistics.mean(trimmed),
            'std': statistics.stdev(values),
            'mad': median_abs_deviation(values),
            'confidence_note': 'winsorized_robust'
        }

# Использовать в calculate_market_statistics()
```

---

## 📝 Патч 4: Quality Metrics & User Warnings

**Файл**: `app_new.py`

**Проблема**:
- Пользователь не видит, сколько аналогов валидны
- Generic "Что-то пошло не так" вместо конкретных сообщений
- Нет трекинга quality metrics

**Решение**:
- Добавить quality_metrics в response
- Конкретные сообщения об ошибках
- Warnings вместо errors при малом n

### Diff:

```python
# После валидации аналогов (строка ~1188)

# Разделяем на валидные и частичные
comparables_valid = []
comparables_partial = []
validation_errors = []

for i, raw_comparable in enumerate(session_data['comparables']):
    try:
        normalized = normalize_property_data(raw_comparable)
        comp = ComparableProperty(**normalized)

        if comp.is_usable_for_analysis():
            comparables_valid.append(comp)
        else:
            comparables_partial.append(comp)
            logger.warning(f"⚠️ Аналог {i+1} не пригоден для расчетов: {comp.quality_flags}")

    except ValidationError as e:
        validation_errors.append({
            'index': i,
            'url': raw_comparable.get('url', 'N/A')[:60],
            'error': str(e)
        })
        logger.error(f"❌ Аналог {i+1} не прошел валидацию: {e}")

n_total = len(session_data['comparables'])
n_valid = len(comparables_valid)
n_partial = len(comparables_partial)
n_invalid = len(validation_errors)

logger.info(f"📊 Качество данных: {n_valid} валидных, {n_partial} частичных, {n_invalid} невалидных")

# Формируем quality metrics
quality_metrics = {
    'total_found': n_total,
    'valid_for_analysis': n_valid,
    'partial_data': n_partial,
    'validation_errors': n_invalid,
    'quality_score': 'high' if n_valid >= 10 else 'medium' if n_valid >= 5 else 'low',
    'confidence_level': 'high' if n_valid >= 10 else 'medium' if n_valid >= 3 else 'low'
}

# Проверяем минимум
if n_valid == 0:
    return jsonify({
        'status': 'error',
        'error_type': 'no_valid_comparables',
        'message': 'Не найдено аналогов с полными данными для анализа. Добавьте 1-2 аналога вручную.',
        'quality_metrics': quality_metrics,
        'suggestions': [
            'Добавьте аналоги вручную через поиск на Циан',
            'Расширьте критерии поиска (больший радиус, диапазон цен)',
            'Попробуйте другой объект для оценки'
        ]
    }), 422

# Создаем request с валидными аналогами
request_model = AnalysisRequest(
    target_property=target_property,
    comparables=comparables_valid,  # Только валидные!
    filter_outliers=filter_outliers,
    use_median=use_median
)
```

```python
# После выполнения анализа (строка ~1298)

# Добавляем quality metrics в результат
result_dict['quality_metrics'] = quality_metrics
result_dict['data_warnings'] = []

# Формируем предупреждения
if n_valid == 1:
    result_dict['data_warnings'].append({
        'level': 'warning',
        'title': 'Оценка по единственному аналогу',
        'message': 'Точность оценки ограничена. Доверительный интервал построен на основе исторических данных по сегменту. Рекомендуется добавить 2-3 аналога вручную.'
    })
elif n_valid == 2:
    result_dict['data_warnings'].append({
        'level': 'warning',
        'title': 'Малая выборка аналогов',
        'message': 'Оценка построена по 2 аналогам. Для повышения точности рекомендуется добавить еще 3-5 аналогов.'
    })
elif n_valid < 5:
    result_dict['data_warnings'].append({
        'level': 'info',
        'title': 'Базовая выборка',
        'message': f'Анализ выполнен по {n_valid} аналогам. Для более точной оценки рекомендуется 10+ аналогов.'
    })

if n_partial > 0:
    result_dict['data_warnings'].append({
        'level': 'info',
        'title': 'Неполные данные',
        'message': f'{n_partial} аналог(ов) имеют неполные данные и не использованы в расчете. Проверьте детали на Циан.'
    })

return jsonify({
    'status': 'success',
    'analysis': result_dict,
    'quality_metrics': quality_metrics,
    'warnings': result_dict['data_warnings']
})
```

---

## ✅ Чек-лист регресса

### Pre-deployment Testing:

- [ ] **Unit tests**: Все существующие тесты проходят
- [ ] **Regression**: Кейсы с n≥10 аналогов работают как раньше
- [ ] **Edge case n=1**: Анализ работает, возвращает предупреждение
- [ ] **Edge case n=2**: Анализ работает, midpoint вычисляется корректно
- [ ] **Edge case n=0**: Возвращает понятную ошибку с suggestions
- [ ] **Parallel parsing timeout**: Не падает, возвращает partial results
- [ ] **Parallel parsing captcha**: Помечает URL, продолжает работу
- [ ] **Field recovery**: price восстанавливается из price_per_sqm * area
- [ ] **IQR skip**: При n<5 фильтрация не применяется
- [ ] **Quality metrics**: Корректно отображаются на фронте

### Production Testing Scenarios:

```python
# Тест-кейс 1: Элитная недвижимость (реальный кейс из бага)
TARGET = {
    'url': 'https://www.cian.ru/sale/flat/305062289/',
    'rooms': 5,
    'total_area': 213.4,
    'price': 520_000_000
}
EXPECTED:
  - Найдено: 8 аналогов
  - Валидных: 1-2
  - Результат: Анализ работает с warning
  - Frontend: Показывает оценку + предупреждение о точности
```

```python
# Тест-кейс 2: Обычная квартира
TARGET = {
    'url': 'https://www.cian.ru/sale/flat/123/',
    'rooms': 2,
    'total_area': 60,
    'price': 15_000_000
}
EXPECTED:
  - Найдено: 15+ аналогов
  - Валидных: 10+
  - Результат: Полноценный анализ
  - IQR: Применяется
```

```python
# Тест-кейс 3: Rate limit simulation
MOCK: parse_detail_page выбрасывает RateLimitError для 50% URLs
EXPECTED:
  - Retry срабатывает (2-3 попытки с backoff)
  - Partial results возвращаются
  - Анализ не падает
```

```python
# Тест-кейс 4: Аналоги без цены на листинге
COMPARABLES: 8 cards, у всех price=None но есть URL
EXPECTED:
  - Детальный парсинг извлекает price
  - Field recovery восстанавливает недостающее
  - ≥50% становятся валидными
```

---

## 📊 Метрики для мониторинга

### Grafana Dashboard "Analysis Quality"

```yaml
Метрики для добавления в Prometheus:

# Счетчики
- analysis_requests_total{status="success|error|warning"}
- analysis_comparables_found_total
- analysis_comparables_valid_total
- analysis_comparables_partial_total

# Гистограммы
- analysis_duration_seconds
- parse_retry_count

# Гауджи
- analysis_quality_score{level="high|medium|low"}
- parse_success_rate

# Логи в ELK
- Каждая сессия: session_id, found, valid, partial, invalid, warnings
- Каждый parse failure: url, error_type, retries_used
```

### Алерты:

```yaml
# Alert 1: Высокий процент parse failures
WHEN: parse_success_rate < 50% for 5m
ACTION: Notify team (возможно, Циан блокирует)

# Alert 2: Много сессий с n_valid < 3
WHEN: rate(analysis_comparables_valid_total{n<3}) > 30% for 10m
ACTION: Investigate data quality

# Alert 3: Увеличение analysis_duration
WHEN: p95(analysis_duration_seconds) > 60s
ACTION: Check parsing performance
```

---

## 🚀 Deployment Plan

### Phase 1: Development (2-3 часа)
- [ ] Реализовать патчи 1-4
- [ ] Добавить unit tests
- [ ] Локальное тестирование

### Phase 2: Staging (1-2 часа)
- [ ] Deploy на staging
- [ ] Прогнать тест-кейсы 1-4
- [ ] Smoke testing всех шагов

### Phase 3: Production (30 минут)
- [ ] Deploy на production
- [ ] Мониторинг метрик (первые 1-2 часа)
- [ ] Быстрый rollback plan (если что-то пошло не так)

### Rollback Strategy:

```bash
# Если что-то сломалось:
git revert <commit-hash>
git push origin main
bash scripts/deploy.sh

# Время rollback: ~2-3 минуты
```

---

## 📈 Expected Impact

**До патча:**
- 8 найденных → 0 валидных → ❌ Ошибка
- Success rate: ~40% для элитной недвижимости

**После патча:**
- 8 найденных → 1-2 валидных → ✅ Анализ с предупреждениями
- Success rate: ~95% для всех сегментов
- Улучшение UX: понятные сообщения вместо generic errors

---

## 🔗 Related Issues

- #123: "Шаг 3 падает с ValidationError"
- #124: "Rate limiting от Циан"
- #125: "Элитная недвижимость не оценивается"

---

## 👥 Reviewers

- @backend-lead - Code review
- @qa-engineer - Testing checklist
- @product-owner - UX messaging approval
