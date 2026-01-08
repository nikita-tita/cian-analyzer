# 🧪 Гайд по тестированию парсера

## Быстрый старт (5 минут)

### Шаг 1: Простой тест с реальным объявлением

```bash
# Активируйте виртуальное окружение
source venv/bin/activate

# Запустите готовый тест
python test_final_parser.py
```

**Что увидите**:
```
✅ ЖК: Моисеенко 10
✅ Ссылка на ЖК: https://zhk-po-ul-moiseenko-spb-i.cian.ru/
✅ РЕЗУЛЬТАТ: Найдено 28 похожих объявлений
```

---

## Тест с вашим объявлением

### Вариант 1: Редактируем готовый скрипт

Откройте `test_final_parser.py` и замените URL:

```python
# Было:
test_url = "https://spb.cian.ru/sale/flat/309818461/"

# Станет (ваш URL):
test_url = "https://spb.cian.ru/sale/flat/ВАШ_ID/"
```

Запустите:
```bash
python test_final_parser.py
```

### Вариант 2: Создайте свой тест

Создайте файл `my_test.py`:

```python
from src.parsers.playwright_parser import PlaywrightParser

# Ваш URL
url = "https://spb.cian.ru/sale/flat/ВАШЕ_ОБЪЯВЛЕНИЕ/"

with PlaywrightParser(headless=True) as parser:
    # 1. Парсим объявление
    target = parser.parse_detail_page(url)

    print(f"Заголовок: {target['title']}")
    print(f"ЖК: {target.get('residential_complex', 'не найден')}")
    print(f"Ссылка на ЖК: {target.get('residential_complex_url', 'нет')}")

    # 2. Ищем похожие
    similar = parser.search_similar_in_building(target, limit=10)

    print(f"\nНайдено: {len(similar)} объявлений")

    # 3. Показываем первые 3
    for i, listing in enumerate(similar[:3], 1):
        print(f"\n{i}. {listing['title']}")
        print(f"   Цена: {listing['price']}")
```

Запустите:
```bash
python my_test.py
```

---

## Проверка разных сценариев

### Сценарий 1: Новостройка с ЖК (должно работать идеально ✅)

```bash
# Тест с объявлением из ЖК
python test_final_parser.py
```

**Ожидаемый результат**:
- ✅ ЖК найден
- ✅ Прямая ссылка найдена
- ✅ Найдено 10-50 объявлений

### Сценарий 2: Вторичка без ЖК (fallback на текстовый поиск)

```python
# my_test_secondary.py
from src.parsers.playwright_parser import PlaywrightParser

# Объявление БЕЗ ЖК (старый дом)
url = "https://spb.cian.ru/sale/flat/[ID_ВТОРИЧКИ]/"

with PlaywrightParser(headless=True) as parser:
    target = parser.parse_detail_page(url)

    print(f"ЖК: {target.get('residential_complex', 'НЕТ')}")

    # Должен использовать fallback (широкий поиск)
    similar = parser.search_similar(target, limit=10)

    print(f"Найдено (широкий поиск): {len(similar)}")
```

### Сценарий 3: Проверка качества результатов

```python
# check_quality.py
from src.parsers.playwright_parser import PlaywrightParser

url = "https://spb.cian.ru/sale/flat/[ВАШ_ID]/"

with PlaywrightParser(headless=True) as parser:
    target = parser.parse_detail_page(url)
    similar = parser.search_similar_in_building(target, limit=20)

    target_complex = target.get('residential_complex', '').lower()

    # Проверяем что все объявления из того же ЖК
    matches = 0
    for listing in similar:
        address = listing.get('address', '').lower()
        if target_complex in address:
            matches += 1

    print(f"\n📊 Качество результатов:")
    print(f"   Всего найдено: {len(similar)}")
    print(f"   Из того же ЖК: {matches}")
    print(f"   Точность: {matches/len(similar)*100:.1f}%")
```

---

## Тест через веб-приложение

### Запуск приложения

```bash
# Запустите сервер
python app_new.py

# Откройте в браузере
# http://localhost:5002
```

### Тест через API (curl)

```bash
# 1. Парсинг объявления
curl -X POST http://localhost:5002/api/parse \
  -H "Content-Type: application/json" \
  -d '{"url": "https://spb.cian.ru/sale/flat/309818461/"}'

# Сохраните session_id из ответа

# 2. Поиск похожих
curl -X POST http://localhost:5002/api/find-similar \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "ВАШ_SESSION_ID",
    "search_type": "building",
    "limit": 10
  }'
```

### Тест через Postman

1. **POST** `http://localhost:5002/api/parse`
   ```json
   {
     "url": "https://spb.cian.ru/sale/flat/309818461/"
   }
   ```

2. Скопируйте `session_id`

3. **POST** `http://localhost:5002/api/find-similar`
   ```json
   {
     "session_id": "YOUR_SESSION_ID",
     "search_type": "building",
     "limit": 10
   }
   ```

---

## Отладка проблем

### Проблема 1: ЖК не найден

**Проверка**:
```python
from src.parsers.playwright_parser import PlaywrightParser

url = "ВАШЕ_ОБЪЯВЛЕНИЕ"

with PlaywrightParser(headless=True) as parser:
    target = parser.parse_detail_page(url)

    print("=" * 50)
    print("ОТЛАДКА ИЗВЛЕЧЕНИЯ ЖК")
    print("=" * 50)
    print(f"Title: {target.get('title')}")
    print(f"Address: {target.get('address')}")
    print(f"ЖК: {target.get('residential_complex')}")
    print(f"URL ЖК: {target.get('residential_complex_url')}")
    print(f"Characteristics: {target.get('characteristics')}")
```

**Решения**:
- Если ЖК есть, но не извлекается → проверьте HTML страницы
- Если это вторичка → используйте `search_similar()` вместо `search_similar_in_building()`
- Если нужно вручную указать ЖК:

```python
target = {
    'residential_complex': 'Название ЖК',
    'residential_complex_url': 'https://spb.cian.ru/kupit-kvartiru-zhiloy-kompleks-*',
}
similar = parser.search_similar_in_building(target, limit=10)
```

### Проблема 2: Найдено 0 объявлений

**Проверка**:
```bash
# Включите подробное логирование
python -c "
import logging
logging.basicConfig(level=logging.DEBUG)

from src.parsers.playwright_parser import PlaywrightParser

url = 'ВАШЕ_ОБЪЯВЛЕНИЕ'

with PlaywrightParser(headless=True) as parser:
    target = parser.parse_detail_page(url)
    similar = parser.search_similar_in_building(target, limit=10)
    print(f'Найдено: {len(similar)}')
"
```

**Возможные причины**:
- В ЖК действительно нет других объявлений
- Страница ЖК не загрузилась
- URL ЖК некорректный

### Проблема 3: Playwright не установлен

```bash
# Установите Playwright
pip install playwright

# Установите браузеры
playwright install chromium
```

---

## Автоматизированное тестирование

### Создайте набор тестов

```python
# test_suite.py
from src.parsers.playwright_parser import PlaywrightParser

test_urls = [
    "https://spb.cian.ru/sale/flat/309818461/",  # ЖК Моисеенко 10
    "https://spb.cian.ru/sale/flat/[URL2]/",     # Другой ЖК
    "https://spb.cian.ru/sale/flat/[URL3]/",     # Вторичка
]

results = []

with PlaywrightParser(headless=True) as parser:
    for url in test_urls:
        print(f"\n{'='*60}")
        print(f"Тест: {url}")
        print('='*60)

        try:
            target = parser.parse_detail_page(url)
            similar = parser.search_similar_in_building(target, limit=5)

            result = {
                'url': url,
                'zk': target.get('residential_complex'),
                'zk_url': target.get('residential_complex_url'),
                'found': len(similar),
                'success': len(similar) > 0
            }

            print(f"✓ ЖК: {result['zk']}")
            print(f"✓ Найдено: {result['found']}")

            results.append(result)

        except Exception as e:
            print(f"✗ Ошибка: {e}")
            results.append({'url': url, 'success': False, 'error': str(e)})

# Итог
print(f"\n{'='*60}")
print("ИТОГИ ТЕСТИРОВАНИЯ")
print('='*60)
successful = sum(1 for r in results if r.get('success'))
print(f"Успешно: {successful}/{len(results)}")

for r in results:
    status = "✓" if r.get('success') else "✗"
    print(f"{status} {r['url'][:50]}: {r.get('found', 0)} объявлений")
```

Запустите:
```bash
python test_suite.py
```

---

## Производительность

### Измерение скорости

```python
# benchmark.py
import time
from src.parsers.playwright_parser import PlaywrightParser

url = "https://spb.cian.ru/sale/flat/309818461/"

start = time.time()

with PlaywrightParser(headless=True) as parser:
    # Парсинг объявления
    t1 = time.time()
    target = parser.parse_detail_page(url)
    parse_time = time.time() - t1

    # Поиск похожих
    t2 = time.time()
    similar = parser.search_similar_in_building(target, limit=10)
    search_time = time.time() - t2

total_time = time.time() - start

print(f"\n⏱️ ПРОИЗВОДИТЕЛЬНОСТЬ")
print(f"   Парсинг объявления: {parse_time:.2f}с")
print(f"   Поиск похожих: {search_time:.2f}с")
print(f"   Общее время: {total_time:.2f}с")
print(f"   Найдено объявлений: {len(similar)}")
```

---

## Чеклист перед использованием в production

- [ ] Тест с 5+ разными объявлениями из ЖК
- [ ] Тест с вторичкой (без ЖК)
- [ ] Проверка точности (>90% объявлений из нужного ЖК)
- [ ] Тест производительности (<10 секунд на поиск)
- [ ] Обработка ошибок (нет падений при некорректных URL)
- [ ] Тест API endpoints
- [ ] Проверка работы в headless режиме

---

## Быстрые команды

```bash
# Основной тест
python test_final_parser.py

# Веб-приложение
python app_new.py

# Отладка структуры Cian
python analyze_cian_structure.py

# Тест разных методов поиска
python test_cian_api.py

# Производительность
python benchmark.py  # создайте как показано выше
```

---

## Если что-то не работает

1. **Проверьте зависимости**:
   ```bash
   pip install playwright beautifulsoup4 lxml
   playwright install chromium
   ```

2. **Включите подробное логирование**:
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

3. **Сохраните HTML для анализа**:
   ```python
   with open('debug.html', 'w', encoding='utf-8') as f:
       f.write(html)
   ```

4. **Проверьте визуально** (отключите headless):
   ```python
   with PlaywrightParser(headless=False) as parser:  # Видно браузер
       ...
   ```

---

## Контакты для помощи

Если возникли проблемы:
1. Проверьте логи
2. Сохраните HTML страницы
3. Опишите проблему с примером URL

**Готово!** 🚀

Теперь вы можете тестировать парсер со своими объявлениями.
