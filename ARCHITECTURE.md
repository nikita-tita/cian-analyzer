# Архитектура системы Housler

## Обзор

Housler - интеллектуальная система анализа недвижимости с веб-интерфейсом и асинхронной обработкой задач.

## Компоненты системы

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND                                 │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Wizard UI  │  │ Pixel Loader │  │   Analytics  │          │
│  │   (3 steps)  │  │  (Progress)  │  │  Dashboard   │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                  │                  │                   │
│         └──────────────────┴──────────────────┘                  │
│                            │                                      │
└────────────────────────────┼──────────────────────────────────────┘
                             │ HTTPS/REST API
┌────────────────────────────┼──────────────────────────────────────┐
│                            ▼                                      │
│                     FLASK APP (app_new.py)                       │
│                                                                   │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌───────────┐│
│  │   Parser   │  │ Analytics  │  │  Session   │  │   CSRF    ││
│  │  Registry  │  │  Engine    │  │  Storage   │  │Protection ││
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └───────────┘│
│        │               │               │                        │
│        │    ┌──────────┴───────┐      │                        │
│        │    │                  │      │                        │
│  ┌─────▼────▼─────┐  ┌─────────▼──────▼───────┐               │
│  │  Task Queue    │  │   Redis Cache/Storage   │               │
│  │  (RQ/Redis)    │  │  (Sessions, Results)    │               │
│  └────────┬───────┘  └─────────────────────────┘               │
│           │                                                      │
└───────────┼──────────────────────────────────────────────────────┘
            │ Job Queue
┌───────────▼──────────────────────────────────────────────────────┐
│                    RQ WORKER PROCESS                             │
│                                                                   │
│  ┌────────────────────────────────────────────────────┐         │
│  │         Async Tasks Processing                      │         │
│  │                                                      │         │
│  │  • parse_property_task()  - парсинг URL            │         │
│  │  • find_similar_task()    - поиск аналогов         │         │
│  └────────┬───────────────────────────────────────────┘         │
│           │                                                      │
│           ▼                                                      │
│  ┌──────────────────────────────────────────┐                  │
│  │     Playwright Parser (Browser Pool)      │                  │
│  │                                            │                  │
│  │  • Headless Chrome                         │                  │
│  │  • Stealth plugins                         │                  │
│  │  • Resource blocking                       │                  │
│  │  • Browser pooling (max 3-5)              │                  │
│  └──────────┬─────────────────────────────────┘                  │
│             │                                                     │
└─────────────┼─────────────────────────────────────────────────────┘
              │ HTTP Requests
┌─────────────▼─────────────────────────────────────────────────────┐
│                    EXTERNAL SERVICES                              │
│                                                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │   ЦИАН API   │  │  Яндекс.Карты│  │    RBC.ru    │           │
│  │  (cian.ru)   │  │  (geocoding) │  │   (blog)     │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

## Модульная структура

### 1. Parsers (`src/parsers/`)

**Назначение:** Извлечение данных о недвижимости из внешних источников

```python
src/parsers/
├── __init__.py              # Экспорты модуля
├── base_parser.py           # Абстрактный базовый класс
├── base_real_estate_parser.py  # Специализация для недвижимости
├── parser_registry.py       # Реестр парсеров
├── playwright_parser.py     # Playwright-based парсер (ЦИАН)
├── cian_parser_adapter.py   # Адаптер для ЦИАН
├── browser_pool.py          # Пул браузеров Playwright
├── field_mapper.py          # Маппинг полей
└── multi_source_search.py   # Мультиисточниковый поиск
```

**Ключевые классы:**
- `BaseRealEstateParser` - интерфейс парсера
- `ParserRegistry` - регистрация и получение парсеров
- `PlaywrightParser` - реализация через Playwright
- `BrowserPool` - управление браузерами

**Возможности:**
- ✅ Парсинг детальной страницы объекта
- ✅ Поиск аналогов (same_building, same_area, citywide)
- ✅ Кеширование результатов
- ✅ Rate limiting
- ✅ Browser pooling (защита от утечек памяти)

### 2. Analytics (`src/analytics/`)

**Назначение:** Анализ данных и ценообразование

```python
src/analytics/
├── analyzer.py              # Главный аналитический движок
├── price_calculator.py      # Расчет справедливой цены
├── statistical_analysis.py  # Статистические методы
├── comparables_quality.py   # Оценка качества аналогов
└── offer_generator.py       # Генерация коммерческих предложений
```

**Алгоритм анализа:**

```
1. Сбор аналогов
   ↓
2. Фильтрация (валидация, outliers)
   ↓
3. Сегментация (с ремонтом / без)
   ↓
4. Расчет справедливой цены
   - Базовая цена (медиана по м²)
   - Корректировки (этаж, отделка, метро)
   - Взвешивание по качеству аналогов
   ↓
5. Генерация инсайтов
   - Сильные стороны
   - Слабые стороны
   - Рекомендации
   ↓
6. Результат (AnalysisResult)
```

### 3. Models (`src/models/`)

**Назначение:** Pydantic модели данных

```python
src/models/
└── property.py
    ├── TargetProperty      # Целевой объект
    ├── ComparableProperty  # Аналог
    ├── AnalysisRequest     # Запрос анализа
    └── AnalysisResult      # Результат анализа
```

**Валидация:**
- Type checking через Pydantic
- Обязательные поля
- Диапазоны значений
- Форматирование данных

### 4. Tasks (`src/tasks/`)

**Назначение:** Асинхронная обработка долгих операций

```python
src/tasks/
├── __init__.py
├── queue.py      # RQ queue управление
└── tasks.py      # Определения задач
    ├── parse_property_task()
    └── find_similar_task()
```

**Workflow задачи:**

```
1. Client → POST /api/tasks/parse
   {"url": "...", "session_id": "..."}
   ↓
2. Flask → enqueue_task(parse_property_task, ...)
   ↓
3. RQ Queue (Redis)
   ↓
4. Worker Process → fetch & execute task
   ↓
5. Update progress (job.meta)
   ↓
6. Save result to session storage
   ↓
7. Client ← poll GET /api/tasks/status/{job_id}
   {"status": "finished", "result": {...}}
```

### 5. API (`src/api/`)

**Назначение:** REST API endpoints

```python
src/api/
├── __init__.py
└── task_endpoints.py
    ├── POST /api/tasks/parse
    ├── POST /api/tasks/find-similar
    ├── GET  /api/tasks/status/<job_id>
    └── GET  /api/tasks/queue-stats
```

### 6. Utils (`src/utils/`)

**Назначение:** Вспомогательные утилиты

```python
src/utils/
├── session_storage.py       # Session management (Redis/Memory)
├── duplicate_detector.py    # Детекция дубликатов аналогов
└── validators.py            # Валидация данных
```

## Потоки данных

### Поток 1: Синхронный парсинг (быстрый)

```
User → POST /api/parse
  → validate_url()
  → parser.parse_detail_page(url)
  → save to session_storage
  → return result
```

### Поток 2: Асинхронный парсинг (рекомендуемый)

```
User → POST /api/tasks/parse
  → enqueue_task(parse_property_task)
  → return {"job_id": "..."}

Worker → execute task
  → update progress
  → save result

User → poll GET /api/tasks/status/{job_id}
  → return status & result
```

### Поток 3: Поиск и анализ

```
User → POST /api/find-similar
  → parser.search_similar()
  → filter_valid_comparables()
  → save to session_storage

User → POST /api/analyze
  → RealEstateAnalyzer.analyze()
  → calculate fair_price
  → generate insights
  → return AnalysisResult
```

## Безопасность

### Защиты:

1. **CSRF Protection** (Flask-WTF)
   - Token validation для всех POST/PUT/DELETE
   - Session-based tokens

2. **Rate Limiting** (Flask-Limiter)
   - 200 requests/day
   - 50 requests/hour
   - Moving window strategy
   - Redis-backed (distributed)

3. **SSRF Protection**
   - Whitelist доменов
   - Блокировка private IP
   - URL validation

4. **Input Validation**
   - Pydantic models
   - Type checking
   - Sanitization

5. **Browser Pool Limits**
   - Max 3-5 браузеров
   - Автоматическое закрытие
   - Таймауты

## Производительность

### Кеширование:

```python
# Redis Cache
property_cache = RedisCache(
    namespace='housler',
    ttl=3600  # 1 hour
)

# Session Storage
session_storage = SessionStorage(
    ttl=86400,  # 24 hours
    max_memory_sessions=1000,
    lru_eviction=True
)
```

### Browser Pool:

```python
browser_pool = BrowserPool(
    max_browsers=3,           # Production: 3-5
    max_age_seconds=3600,     # 1 hour
    max_use_count=100,        # Recycle after 100 uses
    headless=True,
    block_resources=True      # CSS/images/fonts
)
```

## Мониторинг

### Endpoints:

- `GET /health` - Health check всех компонентов
- `GET /metrics` - Prometheus metrics
- `GET /api/cache/stats` - Статистика кеша
- `GET /api/tasks/queue-stats` - Статистика очереди

### Логирование:

```python
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

**Логи находятся в:**
- Flask app: `journalctl -u housler`
- RQ worker: `journalctl -u housler-worker`
- Nginx: `/var/log/nginx/access.log`, `/var/log/nginx/error.log`

## Деплой

### Systemd Services:

```bash
# Main application
/etc/systemd/system/housler.service
  → 4x gunicorn workers
  → bind 127.0.0.1:8001

# RQ Worker
/etc/systemd/system/housler-worker.service
  → rq worker housler-tasks
  → connects to Redis

# Redis
systemctl status redis
  → Task queue backend
  → Cache backend
```

### Nginx:

```nginx
location / {
    proxy_pass http://127.0.0.1:8001;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

## Конфигурация

### Environment Variables:

```bash
# Security
SECRET_KEY=<random-hex-32>
FLASK_ENV=production

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_ENABLED=true
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=<optional>

# Browser Pool
USE_BROWSER_POOL=true
MAX_BROWSERS=3

# Rate Limiting (default)
RATELIMIT_STORAGE_URL=<redis-url>
```

## Масштабирование

### Горизонтальное:

```bash
# Запустить несколько воркеров
systemctl start housler-worker@{1..4}

# Запустить несколько Flask инстансов
# (gunicorn уже использует 4 воркера)
```

### Вертикальное:

```bash
# Увеличить количество gunicorn воркеров
gunicorn --workers 8 ...

# Увеличить лимиты browser pool
MAX_BROWSERS=10
```

## Технологический стек

**Backend:**
- Python 3.11+
- Flask 3.0
- Pydantic 2.5+
- RQ 2.6+
- Playwright 1.40+

**Storage:**
- Redis 7 (cache, sessions, queue)

**Frontend:**
- Vanilla JS
- CSS Grid/Flexbox
- Pixel art design

**Infrastructure:**
- Nginx 1.18
- Systemd
- Ubuntu 22.04
- Gunicorn

## Ссылки

- **Production:** https://housler.ru
- **Repository:** https://github.com/nikita-tita/cian-analyzer
- **Documentation:**
  - TASK_QUEUE_GUIDE.md
  - ASYNC_QUEUE_QUICKSTART.md
  - README.md

---

**Версия:** 1.0
**Дата:** 2025-11-23
**Автор:** Generated with Claude Code
