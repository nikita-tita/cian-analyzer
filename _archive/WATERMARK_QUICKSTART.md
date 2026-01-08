# 🚀 Быстрый старт: Удаление водяных знаков

## Установка

```bash
pip install opencv-python Pillow
```

## Использование

### 1️⃣ Запустить встроенное демо

```bash
python src/watermark_remover.py
```

Результат: `test_images/cleaned.jpg`

### 2️⃣ Обработать одно изображение

```python
from src.watermark_remover import WatermarkRemover

remover = WatermarkRemover(method='telea')
cleaned = remover.process_url(
    url="https://images.cdn-cian.ru/images/kvartira-...",
    auto_detect_positions=['bottom-right', 'top-right']
)
cleaned.save('result.jpg')
```

### 3️⃣ Пакетная обработка

```python
from src.watermark_remover import WatermarkRemover

remover = WatermarkRemover()
urls = [
    "https://images.cdn-cian.ru/images/1.jpg",
    "https://images.cdn-cian.ru/images/2.jpg",
]

results = remover.batch_process_urls(urls)

for i, img in enumerate(results):
    if img:
        img.save(f'cleaned_{i}.jpg')
```

### 4️⃣ Кастомная маска

```python
import cv2
import numpy as np
from src.watermark_remover import WatermarkRemover

# Загрузить изображение как numpy array
remover = WatermarkRemover()

# Создать маску (белые области = удалить)
mask = np.zeros((height, width), dtype=np.uint8)
mask[-100:, -200:] = 255  # Правый нижний угол

# Применить
cleaned = remover.remove_watermark(image, mask=mask)
```

## Параметры

### Методы inpainting

```python
remover = WatermarkRemover(method='telea')  # Быстрый, хорошее качество (по умолчанию)
remover = WatermarkRemover(method='ns')     # Navier-Stokes, чуть медленнее
```

### Позиции автообнаружения

```python
auto_detect_positions=[
    'bottom-right',  # Правый нижний угол (логотип Cian)
    'top-right',     # Правый верхний (телефон)
    'bottom-left',   # Левый нижний
    'center'         # Центр
]
```

## Примеры

### Запустить все примеры

```bash
python example_watermark_usage.py
```

Это создаст:
- `example_cleaned_1.jpg` - одиночная обработка
- `example_batch_*.jpg` - пакетная обработка
- `example_custom_mask.jpg` - кастомная маска
- `cleaned_photos/` - интеграция с парсером

### Тестовые скрипты

```bash
# Простой тест на одном фото
python test_simple_live.py

# Тест на нескольких фото
python test_multiple_photos.py

# Расширенный тест (с детекцией прозрачности)
python test_enhanced_watermark.py
```

## Результаты

**Что удаляется хорошо:**
- ✅ Логотипы в углах (100%)
- ✅ Номера телефонов (100%)
- ✅ Непрозрачный текст (90%)

**Что удаляется частично:**
- ⚠️ Полупрозрачный текст "cian.ru" (~50%)

**Скорость:** ~2 секунды на фото 720x960px

## API

### Класс WatermarkRemover

#### `__init__(method='telea')`
Создать ремувер

**Параметры:**
- `method`: 'telea' или 'ns'

#### `process_url(url, auto_detect_positions=['bottom-right'])`
Обработать изображение по URL

**Параметры:**
- `url`: URL изображения
- `auto_detect_positions`: список позиций для поиска

**Возвращает:** PIL.Image или None

#### `batch_process_urls(urls, auto_detect_positions, max_concurrent=5)`
Пакетная обработка

**Параметры:**
- `urls`: список URL
- `auto_detect_positions`: позиции для поиска
- `max_concurrent`: максимум одновременных загрузок

**Возвращает:** список PIL.Image

#### `remove_watermark(image, mask=None, auto_detect_positions=None)`
Удалить водяной знак

**Параметры:**
- `image`: numpy array (BGR)
- `mask`: numpy array (маска) или None
- `auto_detect_positions`: позиции или None

**Возвращает:** numpy array (BGR)

#### `detect_watermark_region(image, position='bottom-right')`
Создать маску по позиции

**Возвращает:** numpy array (маска)

#### `detect_watermark_by_color(image, target_color='white', tolerance=30)`
Создать маску по цвету

**Параметры:**
- `target_color`: 'white', 'black', 'logo'
- `tolerance`: допуск цвета

**Возвращает:** numpy array (маска)

## Интеграция с парсером Cian

Добавьте в `src/cian_parser_breadcrumbs.py`:

```python
from src.watermark_remover import WatermarkRemover

class CianParserBreadcrumbs:
    def __init__(self):
        # ...
        self.watermark_remover = WatermarkRemover()

    def download_images_clean(self, image_urls):
        """Скачать и очистить изображения"""
        return self.watermark_remover.batch_process_urls(
            urls=image_urls,
            auto_detect_positions=['bottom-right', 'top-right']
        )
```

## Полная документация

См. [WATERMARK_REMOVAL_RESULTS.md](WATERMARK_REMOVAL_RESULTS.md) для:
- Подробных результатов тестирования
- Сравнения методов
- Решения проблем
- Альтернативных решений (IOPaint, API сервисы)

---

**Файлы:**
- [src/watermark_remover.py](src/watermark_remover.py) - основной модуль
- [example_watermark_usage.py](example_watermark_usage.py) - примеры использования
- [WATERMARK_REMOVAL_RESULTS.md](WATERMARK_REMOVAL_RESULTS.md) - полная документация
