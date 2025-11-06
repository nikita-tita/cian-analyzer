# Быстрый старт

## Установка и запуск

### 1. Создайте виртуальное окружение

```bash
python3 -m venv venv
source venv/bin/activate  # На Windows: venv\Scripts\activate
```

### 2. Установите зависимости

```bash
pip install -r requirements.txt
```

### 3. Запустите тесты

```bash
python test_simple.py
```

### 4. Запустите примеры

```bash
python examples/example_usage.py
```

## Быстрый пример использования

```python
from src.cian_parser import CianParser

# Создаем парсер
parser = CianParser(delay=2.0)

# Парсим страницу поиска (продажа квартир в Москве)
url = "https://www.cian.ru/cat.php?deal_type=sale&engine_version=2&offer_type=flat&region=1"
listings = parser.parse_search_page(url)

# Выводим результаты
print(f"Найдено объявлений: {len(listings)}")
for listing in listings[:5]:
    print(f"{listing['title']} - {listing['price']}")

# Сохраняем в JSON
parser.save_to_json(listings, 'results.json')
```

## Популярные URL для поиска

### Москва

**Продажа:**
- Все квартиры: `https://www.cian.ru/cat.php?deal_type=sale&engine_version=2&offer_type=flat&region=1`
- 1-комнатные: `https://www.cian.ru/cat.php?deal_type=sale&engine_version=2&offer_type=flat&region=1&room1=1`
- 2-комнатные: `https://www.cian.ru/cat.php?deal_type=sale&engine_version=2&offer_type=flat&region=1&room2=1`

**Аренда:**
- Все квартиры: `https://www.cian.ru/cat.php?deal_type=rent&engine_version=2&offer_type=flat&region=1`
- 1-комнатные: `https://www.cian.ru/cat.php?deal_type=rent&engine_version=2&offer_type=flat&region=1&room1=1`

### Санкт-Петербург

**Продажа:**
- Все квартиры: `https://www.cian.ru/cat.php?deal_type=sale&engine_version=2&offer_type=flat&region=2`

**Аренда:**
- Все квартиры: `https://www.cian.ru/cat.php?deal_type=rent&engine_version=2&offer_type=flat&region=2`

## Параметры URL

- `deal_type`: `sale` (продажа) или `rent` (аренда)
- `offer_type`: `flat` (квартира), `suburban` (загородная), `commercial` (коммерческая)
- `region`: `1` (Москва), `2` (СПб)
- `room1=1`, `room2=1`, `room3=1` - фильтр по количеству комнат

## Важно!

1. **Задержки между запросами** - используйте `delay=2.0` или больше
2. **Проверьте robots.txt** - убедитесь, что парсинг разрешен
3. **Защита от блокировок** - Cian может использовать капчу или другие методы защиты
4. **Изменение структуры** - HTML может измениться, потребуется обновление кода

## Решение проблем

### Не находит объявления

- Проверьте, что URL корректный и открывается в браузере
- Возможно изменилась структура HTML - проверьте селекторы в [src/cian_parser.py](src/cian_parser.py)

### Блокировка запросов

- Увеличьте задержку между запросами: `parser = CianParser(delay=5.0)`
- Используйте прокси (требуется доработка кода)
- Рассмотрите использование Selenium для эмуляции браузера

### Ошибки импорта

```bash
# Убедитесь, что виртуальное окружение активировано
source venv/bin/activate

# Переустановите зависимости
pip install -r requirements.txt
```

## Что дальше?

- Посмотрите полную документацию в [README.md](README.md)
- Изучите примеры в [examples/example_usage.py](examples/example_usage.py)
- Настройте фильтры поиска под свои нужды
