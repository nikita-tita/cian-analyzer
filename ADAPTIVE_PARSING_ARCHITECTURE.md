# Адаптивная Архитектура Парсинга Недвижимости

## Обзор

Глобальная система парсинга недвижимости с максимальной адаптивностью и обходом защит для:
- **Домклик** (domclick.ru)
- **Циан** (cian.ru)
- **Авито Недвижимость** (avito.ru)
- **Яндекс Недвижимость** (realty.yandex.ru)

## Топ-10 Open-Source Технологий

### Уровень 1: Основные инструменты браузерной автоматизации

1. **Playwright** (playwright.dev)
   - ✅ Уже используется
   - Преимущества: Быстрый, стабильный, хорошая поддержка
   - Применение: Базовый парсинг для всех сайтов
   - Антидетект: Средний (требует доработок)

2. **Nodriver** (github.com/ultrafunkamsterdam/nodriver)
   - ⭐ Топ выбор для обхода Cloudflare
   - Преимущества: Патчит CDP, обходит большинство детекторов
   - Применение: Fallback для Cloudflare-защищенных сайтов
   - Антидетект: Очень высокий

3. **Playwright-Stealth** (github.com/AtuboDad/playwright_stealth)
   - Плагин для Playwright с антидетект патчами
   - Преимущества: Расширяет возможности Playwright
   - Применение: Средний уровень защиты
   - Антидетект: Высокий

### Уровень 2: HTTP клиенты и обход TLS fingerprinting

4. **curl_cffi** (github.com/yifeikong/curl_cffi)
   - HTTP клиент с имитацией TLS fingerprint браузеров
   - Преимущества: Обходит TLS fingerprinting, очень быстрый
   - Применение: API запросы, JSON endpoints
   - Антидетект: Высокий для HTTP/HTTPS

5. **httpx[http2]** (www.python-httpx.org)
   - Современный async HTTP клиент с HTTP/2
   - Преимущества: Быстрый, асинхронный
   - Применение: Массовые API запросы
   - Антидетект: Средний

### Уровень 3: Фреймворки для масштабного парсинга

6. **Scrapy** (scrapy.org)
   - Полнофункциональный фреймворк для веб-скрейпинга
   - Преимущества: Middleware, пайплайны, управление прокси
   - Применение: Массовый парсинг каталогов
   - Антидетект: Средний (требует настройки)

7. **Scrapy-Playwright** (github.com/scrapy-plugins/scrapy-playwright)
   - Интеграция Playwright в Scrapy
   - Преимущества: Мощь Scrapy + возможности Playwright
   - Применение: Сложные пайплайны с JS-рендерингом
   - Антидетект: Средний-Высокий

### Уровень 4: Парсинг и извлечение данных

8. **BeautifulSoup4** (www.crummy.com/software/BeautifulSoup/)
   - ✅ Уже используется
   - Преимущества: Простой, гибкий HTML парсинг
   - Применение: Извлечение данных из HTML
   - Скорость: Средняя

9. **Selectolax** (github.com/rushter/selectolax)
   - Быстрый HTML парсер на базе Modest/LexBor
   - Преимущества: В 5-10 раз быстрее BS4
   - Применение: Парсинг больших объемов HTML
   - Скорость: Очень высокая

10. **Parsel** (github.com/scrapy/parsel)
    - Библиотека для извлечения данных (CSS, XPath)
    - Преимущества: Мощные селекторы, используется в Scrapy
    - Применение: Сложное извлечение данных
    - Скорость: Высокая

## Дополнительные технологии

### Обход защит и прокси

- **FakeBrowser** (github.com/kkoooqq/fakebrowser) - Имитация реального браузера
- **undetected-chromedriver** (github.com/ultrafunkamsterdam/undetected-chromedriver) - Обход Selenium детекции
- **playwright-extra** (для Node.js, но есть Python порты) - Плагины для Playwright

### Управление сессиями и прокси

- **aiohttp-socks** - SOCKS прокси для async запросов
- **playwright-rotating-proxy** - Ротация прокси
- **fake-useragent** - ✅ Уже используется

## Архитектура: Стратегия переключения

### Цепочка Fallback (Cascading Strategy)

```
┌─────────────────────────────────────────────────────────────┐
│                    ADAPTIVE PARSER                           │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  STRATEGY CHAIN (выполняется последовательно)          │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘

Уровень 1: API/JSON (самый быстрый)
    ├─ curl_cffi (TLS fingerprint evasion)
    ├─ httpx (HTTP/2, async)
    └─ requests (fallback)
         ↓ FAILED

Уровень 2: Легкий браузер (средняя скорость)
    ├─ Playwright + Stealth
    ├─ Scrapy-Playwright
    └─ Playwright (vanilla)
         ↓ FAILED

Уровень 3: Продвинутый антидетект (медленно, но надежно)
    ├─ Nodriver (Cloudflare bypass)
    ├─ undetected-chromedriver
    └─ Playwright + ручные патчи
         ↓ FAILED

Уровень 4: Ротация прокси + CAPTCHA solving
    ├─ Прокси пул + Nodriver
    └─ 2captcha/AntiCaptcha интеграция
```

### Адаптивный выбор стратегии

```python
class AdaptiveParserOrchestrator:
    """
    Главный оркестратор парсинга

    Логика:
    1. Анализирует URL и определяет источник
    2. Выбирает оптимальную стратегию на основе:
       - Истории успешности (success rate tracking)
       - Текущей защиты сайта
       - Требуемой скорости
    3. При неудаче автоматически переключается на следующую стратегию
    4. Обучается на результатах (ML-based selection опционально)
    """

    strategies = {
        'api_first': [curl_cffi, httpx, requests],
        'browser_stealth': [playwright_stealth, scrapy_playwright],
        'anti_detect': [nodriver, undetected_chrome],
        'proxy_rotation': [proxy_pool + nodriver]
    }
```

## Особенности для каждого сайта

### Домклик (domclick.ru)
- **Защита:** Средняя (BotManager, TLS fingerprinting)
- **API:** Есть REST API ✅
- **Стратегия:**
  1. API через curl_cffi (TLS evasion)
  2. Playwright + Stealth
  3. Nodriver fallback

### Циан (cian.ru)
- **Защита:** Высокая (PerimeterX, Browser fingerprinting)
- **API:** Частично (скрытые JSON endpoints)
- **Стратегия:**
  1. JSON endpoints через curl_cffi
  2. Playwright-Stealth для детальных страниц
  3. Nodriver для поиска
  4. JSON-LD парсинг (существующий механизм)

### Авито (avito.ru)
- **Защита:** Очень высокая (DataDome, Cloudflare)
- **API:** Защищенное мобильное API
- **Стратегия:**
  1. Nodriver (обход DataDome)
  2. Мобильное API через curl_cffi (User-Agent Android)
  3. Ротация прокси + браузеров

### Яндекс Недвижимость (realty.yandex.ru)
- **Защита:** Средняя-Высокая (Yandex Cloud Shield)
- **API:** GraphQL API
- **Стратегия:**
  1. GraphQL через httpx (быстро)
  2. Playwright для поиска
  3. curl_cffi fallback

## Система поиска аналогов

### Multi-Source Search Coordinator

```python
class MultiSourceSearchCoordinator:
    """
    Координатор поиска по нескольким источникам

    Возможности:
    1. Поиск по адресу (нормализация, геокодинг)
    2. Поиск по названию ЖК (fuzzy matching)
    3. Поиск по похожим объявлениям (ML similarity)
    """

    def search_by_address(self, address: str):
        # Нормализация адреса
        # Геокодинг через Яндекс/Google
        # Поиск в радиусе

    def search_by_residential_complex(self, rc_name: str):
        # Fuzzy matching названия ЖК
        # Поиск на всех платформах
        # Дедупликация

    def search_similar(self, target_property: Dict):
        # ML-based similarity
        # Мульти-параметрический поиск
        # Ранжирование результатов
```

### Извлечение скрытых полей

Система должна извлекать:
- ✅ Основные: цена, площадь, комнаты, этаж
- ✅ Дополнительные: высота потолков, ремонт, вид из окон
- ⭐ Скрытые: история цены, дата публикации, количество просмотров
- ⭐ Meta: ID продавца, тип собственности, обременения

## План тестирования

### Unit Tests
- Каждая стратегия парсинга
- Селекторы и извлечение данных
- Валидация результатов

### Integration Tests
- Цепочки fallback
- Переключение стратегий
- Работа с кэшем

### E2E Tests
- Полный цикл парсинга для каждого сайта
- Поиск аналогов
- Обработка ошибок

### Performance Tests
- Скорость парсинга (целевой результат: <2 сек на объявление)
- Потребление ресурсов
- Конкурентность (параллельный парсинг)

### Anti-Bot Bypass Tests
- Тестирование обхода защит
- Success rate monitoring
- CAPTCHA handling

## Метрики успеха

**Целевые показатели:**
- ✅ Success Rate: 95%+ для всех сайтов
- ✅ Скорость: <2 сек на объявление (API), <5 сек (браузер)
- ✅ Полнота данных: 90%+ заполненность ключевых полей
- ✅ Стабильность: 10/10 успешных запусков тестов

## Roadmap

### Phase 1: Фундамент (1-2 дня)
- [x] Анализ существующей архитектуры
- [ ] Создание AdaptiveParserOrchestrator
- [ ] Интеграция curl_cffi, httpx
- [ ] Интеграция Nodriver
- [ ] Базовые тесты

### Phase 2: Парсеры (2-3 дня)
- [ ] Авито парсер (все стратегии)
- [ ] Яндекс парсер (GraphQL + browser)
- [ ] Улучшение Домклик (новые стратегии)
- [ ] Улучшение Циан (новые стратегии)

### Phase 3: Поиск и извлечение (1-2 дня)
- [ ] MultiSourceSearchCoordinator
- [ ] Поиск по адресу (геокодинг)
- [ ] Поиск по ЖК (fuzzy matching)
- [ ] Извлечение скрытых полей

### Phase 4: Тестирование (2-3 дня)
- [ ] Unit tests (100% coverage критичных функций)
- [ ] Integration tests
- [ ] E2E tests для всех сайтов
- [ ] Достижение 10/10 success rate

### Phase 5: Оптимизация (1-2 дня)
- [ ] Performance tuning
- [ ] Мониторинг и логирование
- [ ] Документация
- [ ] CI/CD интеграция

**Общее время: 7-12 дней**

## Технологический стек (финал)

```python
# requirements-advanced-full.txt

# Core
requests>=2.31.0
beautifulsoup4>=4.12.0
lxml>=4.9.0

# Browser automation (уровень 1-3)
playwright>=1.40.0
playwright-stealth>=0.1.0
nodriver>=0.28
scrapy>=2.11.0
scrapy-playwright>=0.0.34

# HTTP clients (уровень 4)
curl-cffi>=0.6.0
httpx[http2]>=0.25.0

# Fast parsing (уровень 5)
selectolax>=0.3.0
parsel>=1.8.0

# Anti-detection
fake-useragent>=1.4.0
undetected-chromedriver>=3.5.0

# Utilities
python-dotenv>=1.0.0
tenacity>=8.2.3
redis>=5.0.0

# Testing
pytest>=7.4.0
pytest-cov>=4.1.0
pytest-asyncio>=0.21.0
pytest-playwright>=0.4.0

# Data validation
pydantic>=2.5.0
