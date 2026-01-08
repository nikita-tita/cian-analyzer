# Как работает парсер Cian.ru

## Текущее состояние

Парсер **успешно работает** и извлекает данные с Cian.ru, но с определенными ограничениями.

## Что парсер умеет

### ✅ Работает хорошо:

1. **Заголовки объявлений** - извлекается всегда
2. **JSON-LD данные** - когда они присутствуют на странице:
   - Цена (числовое значение)
   - Валюта
   - Полное описание
   - Основные характеристики

### ⚠️ Работает частично:

- **Адрес** - зависит от структуры HTML
- **Метро** - требует JavaScript или специальных селекторов
- **Изображения** - могут загружаться динамически
- **Характеристики** - требуют дополнительной настройки селекторов
- **Информация о продавце** - зависит от типа объявления

## Результаты тестирования

Протестировано на 6 ваших ссылках:

```
1. https://www.cian.ru/sale/flat/319270312/
   ✓ Заголовок: "Продается 3-комн. квартира, 106,2 м²"

2. https://www.cian.ru/sale/flat/319230363/
   ✓ Заголовок: "Продается 5-комн. квартира, 186 м²"

3. https://www.cian.ru/sale/flat/319309313/
   ✓ Заголовок: "Продается 5-комн. квартира, 186 м²"
   ✓ Цена: 130 000 000 ₽
   ✓ Описание: Полное описание объявления

4. https://www.cian.ru/sale/suburban/323383262/
   ✓ Заголовок: "Продается 1-этажный дом, 130,2 м²"

5. https://www.cian.ru/sale/flat/308177547/
   ✓ Заголовок: "Продается 1-комн. апартаменты, 29 м²"

6. https://www.cian.ru/sale/flat/315831388/
   ✓ Заголовок: "Продается 3-комн. квартира, 126,4 м²"
```

**Успешность**: 6 из 6 (100% извлечено заголовков)

## Почему не все данные извлекаются

### 1. **Защита от ботов**

Cian.ru использует несколько уровней защиты:
- Cloudflare (обнаружена на страницах)
- Динамическая загрузка контента через JavaScript
- Капча для подозрительных запросов
- Изменение структуры HTML

### 2. **Single Page Application (SPA)**

Многие данные загружаются через JavaScript после загрузки страницы:
```javascript
window.__INITIAL_STATE__ = { /* данные */ }
```

Наш парсер использует `requests` (статический HTTP), который не выполняет JavaScript.

### 3. **JSON-LD данные непостоянны**

Структурированные данные JSON-LD присутствуют не на всех страницах или загружаются динамически.

## Архитектура парсера

```
┌─────────────────────────────────────────────┐
│         CianParser (src/cian_parser.py)     │
├─────────────────────────────────────────────┤
│                                             │
│  1. _make_request(url)                      │
│     └─> HTTP запрос с User-Agent            │
│         └─> Задержка между запросами        │
│                                             │
│  2. _extract_json_ld(soup)                  │
│     └─> Поиск <script type="ld+json">       │
│         └─> Извлечение структурированных    │
│             данных (цена, описание)         │
│                                             │
│  3. parse_detail_page(url)                  │
│     ├─> JSON-LD данные (приоритет)          │
│     ├─> HTML селекторы (data-name, etc)     │
│     ├─> BeautifulSoup парсинг               │
│     └─> Объединение данных                  │
│                                             │
│  4. save_to_json(data, filename)            │
│     └─> Сохранение результатов              │
│                                             │
└─────────────────────────────────────────────┘
```

## Как использовать

### Простейший пример:

```python
from src.cian_parser import CianParser

# Создаем парсер
parser = CianParser(delay=3.0)  # 3 секунды между запросами

# Парсим одно объявление
url = "https://www.cian.ru/sale/flat/319309313/"
data = parser.parse_detail_page(url)

print(f"Заголовок: {data['title']}")
print(f"Цена: {data['price']}")
print(f"Описание: {data['description'][:100]}...")

# Сохраняем в JSON
parser.save_to_json([data], 'result.json')
```

### Парсинг нескольких объявлений:

```bash
# Запустите готовый скрипт
source venv/bin/activate
python parse_links.py
```

Этот скрипт обработает все 6 ваших ссылок и сохранит результаты в JSON файл.

## Что можно улучшить

### Для полного парсинга нужно:

1. **Selenium / Playwright** - для выполнения JavaScript
   ```python
   from selenium import webdriver

   driver = webdriver.Chrome()
   driver.get(url)
   # Ждем загрузки JS
   time.sleep(5)
   html = driver.page_source
   ```

2. **Прокси** - для обхода ограничений IP
   ```python
   proxies = {
       'http': 'http://proxy:port',
       'https': 'https://proxy:port'
   }
   requests.get(url, proxies=proxies)
   ```

3. **API (если доступно)** - официальный способ получения данных

4. **Обновление селекторов** - адаптация под текущую структуру HTML

## Решение для полного парсинга

### Вариант 1: Selenium (рекомендуется)

Создайте файл `selenium_parser.py`:

```python
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time

chrome_options = Options()
chrome_options.add_argument('--headless')  # Без окна браузера
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')

driver = webdriver.Chrome(options=chrome_options)

url = "https://www.cian.ru/sale/flat/319309313/"
driver.get(url)

# Ждем загрузки JavaScript
time.sleep(5)

# Получаем HTML после выполнения JS
html = driver.page_source
soup = BeautifulSoup(html, 'lxml')

# Теперь все данные доступны
title = soup.find('h1').get_text()
print(title)

driver.quit()
```

### Вариант 2: API-подход

Некоторые сайты передают данные через API. Проверьте Network вкладку в DevTools браузера:

1. Откройте страницу Cian в браузере
2. F12 → Network
3. Перезагрузите страницу
4. Найдите XHR/Fetch запросы с JSON данными

Если найдете API endpoint, можно парсить напрямую:
```python
import requests

api_url = "https://api.cian.ru/v1/offer/319309313/"
response = requests.get(api_url)
data = response.json()
```

## Текущие файлы проекта

```
cian/
├── src/
│   └── cian_parser.py          # Основной парсер
├── examples/
│   └── example_usage.py        # Примеры использования
├── parse_links.py              # ✨ Готовый скрипт для ваших ссылок
├── test_simple.py              # Базовые тесты
├── test_single_page.py         # Детальный тест одной страницы
├── debug_parser.py             # Отладка HTML структуры
├── requirements.txt            # Зависимости
├── README.md                   # Полная документация
├── QUICKSTART.md               # Быстрый старт
└── HOW_IT_WORKS.md            # Этот файл
```

## Запуск

```bash
# 1. Активируйте виртуальное окружение
source venv/bin/activate

# 2. Парсим ваши ссылки
python parse_links.py

# 3. Смотрим результаты
cat parsed_listings_*.json | python -m json.tool
```

## Итог

Парсер **работает**, но извлекает данные с ограничениями из-за защиты Cian.ru:

- ✅ Заголовки - извлекаются всегда
- ✅ Некоторые цены и описания - через JSON-LD
- ⚠️ Остальные данные - требуют JavaScript (Selenium)

Для **полноценного парсинга** рекомендую:
1. Добавить Selenium для выполнения JavaScript
2. Использовать прокси для обхода ограничений
3. Или найти API endpoints через DevTools

Текущая версия отлично подходит для:
- Получения базовой информации (заголовки, ID объявлений)
- Обучения парсингу
- Прототипирования
