# Housler API Documentation v2.0

## Оглавление
1. [Инфраструктура](#инфраструктура)
2. [Основные эндпоинты](#основные-эндпоинты)
3. [Административные эндпоинты](#административные-эндпоинты)
4. [Примеры использования](#примеры-использования)

---

## Инфраструктура

### Health Check
Проверка состояния сервиса.

```http
GET /health
```

**Response** (200 OK):
```json
{
  "status": "healthy|degraded|unhealthy",
  "timestamp": "2025-11-08T15:30:00",
  "version": "2.0.0",
  "components": {
    "redis_cache": {
      "status": "healthy",
      "available": true,
      "stats": {
        "hit_rate": 78.5,
        "total_keys": 142
      }
    },
    "session_storage": {
      "status": "healthy",
      "type": "InMemorySessionStorage"
    },
    "parser": {
      "status": "healthy",
      "type": "PlaywrightParser"
    }
  }
}
```

**Статусы:**
- `200` - Healthy или Degraded (работает, но есть minor проблемы)
- `503` - Unhealthy (critical failure)

### Metrics (Prometheus)
Метрики для мониторинга.

```http
GET /metrics
```

**Response** (200 OK):
```
# HELP housler_up Application is running
# TYPE housler_up gauge
housler_up 1

# HELP housler_cache_hit_rate Cache hit rate percentage
# TYPE housler_cache_hit_rate gauge
housler_cache_hit_rate 78.5

# HELP housler_cache_keys_total Total number of cached keys
# TYPE housler_cache_keys_total gauge
housler_cache_keys_total 142
```

---

## Основные эндпоинты

### 1. Парсинг целевого объекта

```http
POST /api/parse
Content-Type: application/json
```

**Request:**
```json
{
  "url": "https://www.cian.ru/sale/flat/123456/"
}
```

**Response** (200 OK):
```json
{
  "status": "success",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "data": {
    "url": "https://www.cian.ru/sale/flat/123456/",
    "title": "3-комн. квартира, 85 м²",
    "price": 12500000,
    "price_per_sqm": 147058.82,
    "total_area": 85,
    "rooms": 3,
    "floor": 7,
    "total_floors": 12,
    "residential_complex": "ЖК Невские Паруса",
    "repair_level": "улучшенная",
    "ceiling_height": 3.0,
    "metro_distance_min": 5
  },
  "missing_fields": [
    {
      "field": "view_type",
      "label": "🌅 Вид из окна",
      "type": "select",
      "options": ["дом", "улица", "парк", "вода", "город"]
    }
  ]
}
```

**Автоопределение региона:**
- URL содержит `moskva` → регион Москва
- URL содержит `sankt-peterburg` → регион Санкт-Петербург
- По умолчанию → Санкт-Петербург

---

### 2. Поиск аналогов

```http
POST /api/search-similar
Content-Type: application/json
```

**Request:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "search_type": "building",  // "building" или "city"
  "limit": 10
}
```

**Response** (200 OK):
```json
{
  "status": "success",
  "comparables": [
    {
      "url": "https://www.cian.ru/sale/flat/234567/",
      "title": "3-комн. квартира, 82 м²",
      "price": 11800000,
      "price_per_sqm": 143902.44,
      "total_area": 82,
      "rooms": 3,
      "floor": 5
    }
  ],
  "count": 10,
  "search_type": "building",
  "residential_complex": "ЖК Невские Паруса"
}
```

**Типы поиска:**
- `building` - Поиск в том же ЖК (приоритет)
- `city` - Широкий поиск по городу

**Параллельный парсинг:**
Если найдены URL без детальной информации, автоматически запускается параллельный парсинг (5 потоков):
- До: 10 объектов × 5с = 50с
- После: 10 объектов / 5 потоков = ~10с (5x ускорение)

---

### 3. Анализ

```http
POST /api/analyze
Content-Type: application/json
```

**Request:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "filter_outliers": true,
  "use_median": true
}
```

**Response** (200 OK):
```json
{
  "status": "success",
  "analysis": {
    "timestamp": "2025-11-08T15:30:00",
    "market_statistics": {
      "all": {
        "mean": 145000,
        "median": 143500,
        "min": 130000,
        "max": 160000,
        "stdev": 8500,
        "count": 10,
        "confidence_interval_95": {
          "lower": 140200,
          "upper": 146800,
          "margin": 3300
        }
      }
    },
    "fair_price_analysis": {
      "base_price_per_sqm": 143500,
      "final_multiplier": 1.028,
      "fair_price_total": 12750000,
      "current_price": 12500000,
      "price_diff_percent": -1.96,
      "is_overpriced": false,
      "is_underpriced": true,
      "confidence_interval_95": {
        "lower": 12100000,
        "upper": 13400000,
        "margin": 650000,
        "margin_percent": 5.1,
        "description": "12,750,000 ± 650,000 ₽ (95% доверия)"
      },
      "medians": {
        "ceiling_height": 2.85,
        "floor": 6,
        "view_type": "улица"
      },
      "adjustments": {
        "ceiling_height": {
          "description": "Высота потолков выше медианы (3.0 vs 2.85)",
          "value": 1.015
        }
      }
    },
    "price_scenarios": [
      {
        "name": "Быстрая продажа",
        "type": "fast",
        "start_price": 13005000,
        "expected_final_price": 12800000,
        "time_months": 2,
        "base_probability": 0.85
      },
      {
        "name": "Оптимальная",
        "type": "optimal",
        "start_price": 13515000,
        "expected_final_price": 13000000,
        "time_months": 4,
        "base_probability": 0.75
      }
    ],
    "strengths_weaknesses": {
      "strengths": [
        {"factor": "Высокие потолки (3.0м)", "premium": "+1.5%"}
      ],
      "weaknesses": [
        {"factor": "Средний этаж", "discount": "-0%"}
      ]
    }
  }
}
```

**Новые функции v2.0:**
- ✅ Доверительные интервалы (95%) для цены
- ✅ Медианный подход (устойчивость к выбросам)
- ✅ Статистическая валидность (t-критерий Стьюдента)

---

## Административные эндпоинты

### Cache Stats

```http
GET /api/cache/stats
```

**Response:**
```json
{
  "status": "success",
  "stats": {
    "status": "active",
    "available": true,
    "namespace": "housler",
    "total_keys": 142,
    "keyspace_hits": 856,
    "keyspace_misses": 234,
    "hit_rate": 78.53
  }
}
```

### Cache Clear

```http
POST /api/cache/clear
Content-Type: application/json
```

**Request:**
```json
{
  "pattern": "*"  // Опционально
}
```

**Response:**
```json
{
  "status": "success",
  "deleted": 142,
  "pattern": "*"
}
```

---

## Примеры использования

### Полный цикл анализа

```bash
# 1. Парсинг объекта
curl -X POST http://localhost:5000/api/parse \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.cian.ru/sale/flat/123456/"
  }'

# Ответ: {"session_id": "abc-123", ...}

# 2. Поиск аналогов
curl -X POST http://localhost:5000/api/search-similar \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "abc-123",
    "search_type": "building",
    "limit": 10
  }'

# 3. Анализ
curl -X POST http://localhost:5000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "abc-123",
    "filter_outliers": true,
    "use_median": true
  }'
```

### Мониторинг

```bash
# Health check
curl http://localhost:5000/health

# Prometheus metrics
curl http://localhost:5000/metrics
```

### Проверка кэша

```bash
# Статистика
curl http://localhost:5000/api/cache/stats

# Очистка
curl -X POST http://localhost:5000/api/cache/clear \
  -H "Content-Type: application/json" \
  -d '{"pattern": "property:*"}'
```

---

## Коды ошибок

| Код | Описание | Причина |
|-----|----------|---------|
| 200 | OK | Успешно |
| 400 | Bad Request | Неверные параметры |
| 404 | Not Found | Сессия не найдена |
| 422 | Unprocessable Entity | Недостаточно аналогов (<3) |
| 500 | Internal Server Error | Внутренняя ошибка |
| 503 | Service Unavailable | Сервис недоступен |

---

## Производительность

| Операция | До (v1.0) | После (v2.0) | Улучшение |
|----------|-----------|--------------|-----------|
| Парсинг 1 объекта (cache miss) | 30-60s | 30-60s | - |
| Парсинг 1 объекта (cache hit) | - | 0.01s | ⚡ 3000x |
| Парсинг 10 аналогов | ~50s | ~10s | 🚀 5x |
| Устойчивость к сбоям | 85% | 99%+ | ✅ +14% |
| Полнота данных | 60% | 95% | ✅ +35% |

---

## Changelog

### v2.0.0 (2025-11-08)

**Новые функции:**
- ✅ Redis кэширование (TTL: 24h)
- ✅ Поддержка Москвы (автоопределение региона)
- ✅ Async параллельный парсинг (5x ускорение)
- ✅ Доверительные интервалы (95% CI)
- ✅ Health check endpoint
- ✅ Prometheus metrics

**Улучшения:**
- ✅ Retry с exponential backoff (3 попытки)
- ✅ Memory leak исправлен (graceful browser shutdown)
- ✅ Умные дефолты (контекстно-зависимые)
- ✅ Валидация консистентности данных
- ✅ Обработка пустых аналогов (min 3 required)

### v1.0.0 (2025-10-15)
- Initial release

---

## Лицензия

Proprietary - Housler © 2025
