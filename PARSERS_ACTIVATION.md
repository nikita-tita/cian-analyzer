# Активация всех парсеров

## Что изменилось?

Парсеры **Авито**, **Яндекс.Недвижимость** и **ДомКлик** были реализованы, но не работали. Теперь они активированы!

### Проблема
1. ❌ Парсеры не импортировались в `__init__.py` → декораторы не выполнялись
2. ❌ Зависимости не были установлены
3. ❌ На фронтенде было написано "в разработке"

### Решение
✅ Добавлены импорты в `src/parsers/__init__.py`
✅ Добавлены зависимости в `requirements.txt`
✅ Обновлен текст на фронтенде

---

## Установка зависимостей

### 1. Установите Python-пакеты

```bash
pip install -r requirements.txt
```

Новые зависимости:
- **curl-cffi** (0.6.0+) - для обхода защиты Авито и мобильного API
- **nodriver** (0.5.0+) - для обхода DataDome на Авито
- **httpx** (0.25.0+) - для GraphQL API Яндекс.Недвижимость

### 2. Установите браузер Chromium для Playwright

```bash
playwright install chromium
```

### 3. Перезапустите приложение

```bash
# Локально
python src/app.py

# Или через Docker
bash scripts/auto-deploy.sh 1

# На проде
bash scripts/deploy.sh
```

---

## Поддерживаемые источники

| Источник | Статус | Метод парсинга |
|----------|--------|----------------|
| **ЦИАН** | ✅ Работает | Playwright + селекторы |
| **Авито** | ✅ Работает | Мобильное API + nodriver |
| **Яндекс.Недвижимость** | ✅ Работает | GraphQL API + httpx |
| **ДомКлик** | ✅ Работает | REST API Сбербанка |

---

## Тестирование парсеров

### 1. Проверьте регистрацию парсеров

```python
from src.parsers import get_global_registry

registry = get_global_registry()
print("Зарегистрированные парсеры:", registry.get_all_sources())
# Должно вывести: ['cian', 'domclick', 'avito', 'yandex']
```

### 2. Протестируйте парсинг URL

```python
from src.parsers import get_global_registry

registry = get_global_registry()

# ЦИАН
parser = registry.get_parser('https://spb.cian.ru/sale/flat/123/')
print("ЦИАН:", parser.__class__.__name__)  # CianParser

# Авито
parser = registry.get_parser('https://www.avito.ru/moskva/kvartiry/...')
print("Авито:", parser.__class__.__name__)  # AvitoParser

# Яндекс
parser = registry.get_parser('https://realty.yandex.ru/offer/...')
print("Яндекс:", parser.__class__.__name__)  # YandexRealtyParser

# ДомКлик
parser = registry.get_parser('https://domclick.ru/card/sale_flat?id=...')
print("ДомКлик:", parser.__class__.__name__)  # DomClickParser
```

### 3. Тест через веб-интерфейс

1. Откройте http://localhost:5000
2. Вставьте ссылку на объявление (любой источник)
3. Нажмите "Загрузить объект"
4. Проверьте, что данные успешно загрузились

**Примеры ссылок для тестирования:**
- ЦИАН: `https://spb.cian.ru/sale/flat/...`
- Авито: `https://www.avito.ru/sankt-peterburg/kvartiry/...`
- Яндекс: `https://realty.yandex.ru/offer/...`
- ДомКлик: `https://domclick.ru/card/sale_flat?id=...`

---

## Устранение проблем

### Ошибка: "Parser not registered"

**Причина:** Парсер не импортировался → декоратор не выполнился

**Решение:**
```bash
# Проверьте, что парсеры импортируются
python -c "from src.parsers import AvitoParser, YandexRealtyParser; print('OK')"
```

### Ошибка: "ModuleNotFoundError: No module named 'curl_cffi'"

**Причина:** Зависимости не установлены

**Решение:**
```bash
pip install curl-cffi nodriver httpx
```

### Ошибка: "Playwright not installed"

**Причина:** Браузер Chromium не установлен

**Решение:**
```bash
playwright install chromium
```

### Авито возвращает капчу или блокирует

**Причина:** DataDome защита

**Решение:**
1. Парсер автоматически использует `nodriver` для обхода
2. Если не помогает, добавьте задержку между запросами:
```python
parser = AvitoParser(delay=5.0)  # 5 секунд между запросами
```

---

## Технические детали

### Архитектура парсеров

```
src/parsers/
├── __init__.py             # Импорты и регистрация
├── parser_registry.py      # Реестр парсеров (Factory pattern)
├── base_real_estate_parser.py  # Базовый класс
├── cian_parser_adapter.py  # ЦИАН
├── avito_parser.py         # Авито
├── yandex_realty_parser.py # Яндекс
├── domclick_parser.py      # ДомКлик
└── strategies/             # Стратегии парсинга
    ├── httpx_strategy.py
    ├── curl_cffi_strategy.py
    ├── nodriver_strategy.py
    └── playwright_stealth_strategy.py
```

### Регистрация парсеров

Парсеры регистрируются автоматически через декоратор:

```python
@register_parser('avito', [r'avito\.ru', r'www\.avito\.ru'])
class AvitoParser(BaseRealEstateParser):
    ...
```

При импорте модуля декоратор выполняется и регистрирует парсер в глобальном реестре.

### Выбор парсера

```python
registry = get_global_registry()
parser = registry.get_parser(url='https://avito.ru/...')
```

Реестр:
1. Извлекает домен из URL
2. Сравнивает с зарегистрированными паттернами
3. Возвращает подходящий парсер
4. Кэширует экземпляр парсера для повторного использования

---

## FAQ

**Q: Почему парсеры не работали раньше?**
A: Они были реализованы, но не импортировались в `__init__.py`. Декораторы `@register_parser` не выполнялись, поэтому парсеры не регистрировались в реестре.

**Q: Какие зависимости самые важные?**
A:
- `playwright` - для ЦИАН (обязательно)
- `curl-cffi` - для Авито и Яндекс (рекомендуется)
- `nodriver` - для обхода защиты Авито (опционально, но полезно)
- `httpx` - для GraphQL API Яндекс (альтернатива curl-cffi)

**Q: Можно ли использовать парсеры без всех зависимостей?**
A: Да, каждый парсер опционально зависит от своих библиотек. Если библиотека недоступна, парсер использует fallback стратегию:
- Авито: curl-cffi → nodriver → error
- Яндекс: httpx → curl-cffi → playwright
- ДомКлик: requests → playwright

**Q: Работают ли парсеры в продакшене?**
A: Да, после установки зависимостей и перезапуска сервера.

---

## Деплой на продакшн

```bash
# 1. Переключитесь на main
git checkout main
git merge claude/investigate-code-issue-01Jq9aGK4n21KDgU2krj3bqW

# 2. Запушьте изменения
git push origin main

# 3. Задеплойте
bash scripts/deploy.sh
```

Скрипт автоматически:
1. Подключится к серверу
2. Подтянет изменения
3. Установит новые зависимости (`pip install -r requirements.txt`)
4. Перезапустит сервис
5. Покажет логи

---

## Полезные ссылки

- [Документация curl-cffi](https://github.com/yifeikong/curl_cffi)
- [Документация nodriver](https://github.com/ultrafunkamsterdam/nodriver)
- [Документация httpx](https://www.python-httpx.org/)
- [Playwright Python](https://playwright.dev/python/)

---

**Дата активации:** 2025-01-21
**Версия:** 1.0.0
