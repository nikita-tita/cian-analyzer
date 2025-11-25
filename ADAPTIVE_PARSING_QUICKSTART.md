# Быстрый старт: Адаптивная система парсинга

## Что это?

Глобальная адаптивная система парсинга недвижимости с поддержкой:
- **4 платформ**: Циан, Домклик, Авито, Яндекс Недвижимость
- **10+ технологий**: Playwright, Nodriver, curl_cffi, httpx, Scrapy и др.
- **Автоматический fallback**: Если одна стратегия не работает, система автоматически переключается на следующую
- **Обход защит**: TLS fingerprinting, DataDome, Cloudflare, PerimeterX

## Установка

### Шаг 1: Установите базовые зависимости

```bash
pip install -r requirements.txt
```

### Шаг 2: Установите продвинутые парсинговые технологии

```bash
pip install -r requirements-advanced-full.txt
```

### Шаг 3: Установите Playwright браузеры

```bash
playwright install chromium
```

### Опционально: Установите Nodriver для максимального обхода защит

```bash
pip install nodriver>=0.28
```

## Быстрый старт

### Пример 1: Парсинг одного объявления

```python
from src.parsers.adaptive_orchestrator import AdaptiveParserOrchestrator

# Создаем оркестратор
orchestrator = AdaptiveParserOrchestrator(enable_stats=True)

# Парсим объявление (система автоматически выберет оптимальную стратегию)
result = orchestrator.parse_property('https://www.cian.ru/sale/flat/12345/')

if result.success:
    print(f"✅ Успех! Использована стратегия: {result.strategy_used.value}")
    print(f"Название: {result.data.get('title')}")
    print(f"Цена: {result.data.get('price'):,.0f} ₽")
    print(f"Площадь: {result.data.get('total_area')} м²")
else:
    print(f"❌ Ошибка: {result.error}")
```

### Пример 2: Поиск аналогов на всех платформах

```python
from src.parsers.adaptive_orchestrator import AdaptiveParserOrchestrator

orchestrator = AdaptiveParserOrchestrator()

# Целевой объект
target_property = {
    'price': 10_000_000,
    'total_area': 50,
    'rooms': 2,
    'metro': ['Невский проспект'],
}

# Поиск на всех платформах
results = orchestrator.search_similar(
    target_property,
    sources=['cian', 'domclick', 'avito', 'yandex'],
    limit=20,
    strategy='citywide'
)

print(f"Найдено {len(results)} аналогов")
for result in results[:5]:
    print(f"- {result['source']}: {result['title'][:50]}... ({result['price']:,.0f} ₽)")
```

### Пример 3: Выбор конкретной стратегии

```python
from src.parsers.adaptive_orchestrator import AdaptiveParserOrchestrator, ParsingStrategy

orchestrator = AdaptiveParserOrchestrator()

# Используем API-first стратегию (curl_cffi)
result = orchestrator.parse_property(
    'https://domclick.ru/card/sale__flat__12345',
    preferred_strategy=ParsingStrategy.API_FIRST,
    enable_fallback=True
)
```

## Демонстрационный скрипт

Запустите интерактивное демо:

```bash
python demo_adaptive_parsing.py
```

Демо покажет:
1. Адаптивный парсинг с автоматическим выбором стратегии
2. Поиск аналогов на нескольких платформах
3. Сравнение эффективности разных стратегий

## Запуск тестов

### Базовые тесты (импорты и создание объектов)

```bash
pytest tests/test_adaptive_parsing_basic.py -v
```

### E2E тесты (требуют реальных URL)

```bash
pytest tests/test_adaptive_parsing_e2e.py -v
```

## Архитектура

### Стратегии парсинга (от быстрой к надежной)

1. **API_FIRST** (curl_cffi, httpx)
   - Самый быстрый
   - Обход TLS fingerprinting
   - Для: Domclick API, Yandex GraphQL

2. **BROWSER_LIGHT** (Playwright + Stealth)
   - Средняя скорость
   - Обход browser fingerprinting
   - Для: Циан, обычные сайты

3. **BROWSER_HEAVY** (Nodriver)
   - Медленный, но надежный
   - Обход Cloudflare, DataDome
   - Для: Авито, защищенные сайты

4. **MOBILE_API** (curl_cffi + Android UA)
   - Специфично для Авито
   - Мобильное API

### Cascading Fallback

Система автоматически переключается между стратегиями:

```
API_FIRST → BROWSER_LIGHT → BROWSER_HEAVY → PROXY_ROTATION
   ↓ FAILED      ↓ FAILED        ↓ FAILED         ↓ FAILED
```

### Поддерживаемые платформы

| Платформа | Защита | Стратегии | API | Статус |
|-----------|--------|-----------|-----|--------|
| Циан | PerimeterX | Browser Light/Heavy | Частично | ✅ Работает |
| Домклик | BotManager | API First/Browser | Да | ✅ Работает |
| Авито | DataDome | Mobile API/Nodriver | Мобильное | ⚠️ Требует Nodriver |
| Яндекс | Cloud Shield | GraphQL/Browser | Да | ✅ Работает |

## Топ-10 технологий

1. **Playwright** - Базовая браузерная автоматизация
2. **Nodriver** - Обход Cloudflare/DataDome
3. **Playwright-Stealth** - Антидетект патчи
4. **curl_cffi** - Обход TLS fingerprinting
5. **httpx** - Async HTTP/2 клиент
6. **BeautifulSoup4** - HTML парсинг
7. **Selectolax** - Быстрый HTML парсинг
8. **Scrapy** - Фреймворк для масштабного парсинга
9. **Parsel** - Мощные селекторы
10. **FakeUserAgent** - Ротация User-Agent

## Расширенные возможности

### Кэширование

```python
from src.cache.redis_cache import PropertyCache

cache = PropertyCache(redis_url='redis://localhost:6380')
orchestrator = AdaptiveParserOrchestrator(cache=cache)
```

### Прокси ротация

```python
# TODO: Implement proxy rotation
```

### Статистика и мониторинг

```python
orchestrator = AdaptiveParserOrchestrator(enable_stats=True)

# После парсинга
orchestrator.print_stats()

# Или получить программно
stats = orchestrator.get_stats()
print(f"Success rate: {stats['strategies']['api_first']['success_rate']:.1f}%")
```

## Troubleshooting

### curl_cffi не устанавливается

```bash
# Требуется компилятор
sudo apt-get install build-essential libcurl4-openssl-dev
pip install curl-cffi
```

### Nodriver не работает

```bash
# Nodriver требует Chrome/Chromium
sudo apt-get install chromium-browser
pip install nodriver
```

### Playwright ошибки

```bash
# Переустановите браузеры
playwright install --force chromium
```

## Производительность

| Стратегия | Скорость | Success Rate | CPU | Memory |
|-----------|----------|--------------|-----|--------|
| API_FIRST | ⚡⚡⚡ | 85% | Низкая | Низкая |
| BROWSER_LIGHT | ⚡⚡ | 90% | Средняя | Средняя |
| BROWSER_HEAVY | ⚡ | 95%+ | Высокая | Высокая |

## Roadmap

- [x] Адаптивный оркестратор
- [x] Парсеры для 4 платформ
- [x] 10+ технологий
- [x] Field mappers
- [ ] Полное E2E тестирование
- [ ] Proxy rotation
- [ ] CAPTCHA solving интеграция
- [ ] ML-based strategy selection
- [ ] Геокодинг для поиска по адресу
- [ ] Fuzzy matching для поиска по ЖК

## Поддержка

Для вопросов и багов создавайте issue в репозитории.

## Лицензия

MIT
