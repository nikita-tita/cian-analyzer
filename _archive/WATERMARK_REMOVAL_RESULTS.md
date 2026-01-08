# Результаты тестирования удаления водяных знаков Cian

## Резюме

Протестированы различные подходы к удалению водяных знаков с фотографий Cian.ru. Полупрозрачные водяные знаки "cian.ru" требуют AI-based решений (IOPaint/LaMa), которые недоступны для Python 3.13.

## Протестированные решения

### 1. IOPaint (LaMa) - AI-based инпейнтинг
**Статус:** ❌ Недоступно для Python 3.13
```
ERROR: Could not find a version that satisfies the requirement iopaint
```

**Качество:** Лучшее (по отзывам)
**Скорость:** Средняя (требует GPU)

### 2. OpenCV Inpainting (TELEA / Navier-Stokes)
**Статус:** ✅ Работает
**Установка:** `pip install opencv-python`

**Результаты тестирования:**

| Тип водяного знака | Качество удаления | Комментарий |
|--------------------|-------------------|-------------|
| Непрозрачный логотип в углу | ⭐⭐⭐⭐ Отлично | Полностью удаляется |
| Полупрозрачный текст "cian.ru" | ⭐⭐ Частично | Остается видимым |
| Номер телефона в углу | ⭐⭐⭐⭐ Отлично | Полностью удаляется |

**Проблема:** OpenCV inpainting не работает с полупрозрачными объектами, т.к. восстанавливает только области, помеченные в маске. Полупрозрачный текст смешивается с фоном, и его сложно выделить в маску.

## Созданные модули

### [src/watermark_remover.py](src/watermark_remover.py)

Полнофункциональный модуль для удаления водяных знаков с помощью OpenCV:

**Основные методы:**
- `detect_watermark_region()` - обнаружение по позиции (углы изображения)
- `detect_watermark_by_color()` - обнаружение по цвету (белый, черный, зеленый лого)
- `detect_transparent_watermark()` - попытка обнаружения полупрозрачного текста
- `remove_watermark()` - удаление с помощью inpainting
- `process_url()` - обработка изображения по URL
- `batch_process_urls()` - пакетная обработка

**Использование:**
```python
from src.watermark_remover import WatermarkRemover

remover = WatermarkRemover(method='telea')
cleaned_image = remover.process_url(
    url="https://images.cdn-cian.ru/...",
    auto_detect_positions=['bottom-right', 'top-right']
)
```

### Тестовые скрипты

1. **[test_watermark_removal.py](test_watermark_removal.py)** - проверка доступных библиотек
2. **[test_enhanced_watermark.py](test_enhanced_watermark.py)** - тест с расширенной детекцией
3. **[test_simple_live.py](test_simple_live.py)** - простой подход (нижняя область + углы)
4. **[test_multiple_photos.py](test_multiple_photos.py)** - пакетное тестирование

## Практические результаты

### Тест на реальном фото Cian (720x960px)

**Оригинал:**
- Логотип Cian в правом нижнем углу
- Полупрозрачный текст "cian.ru" по всей нижней части
- Название ЖК в центре (это НЕ водяной знак)

**После обработки OpenCV:**
- ✅ Логотип удален
- ✅ Верхний правый угол очищен
- ❌ Полупрозрачный "cian.ru" остался видимым (слабо, но заметно)

**Статистика:**
- Маска покрывает: ~9% изображения
- Время обработки: ~2 секунды
- Качество inpainting: хорошее для непрозрачных областей

### Проблемы на маленьких изображениях

На thumbnail изображениях (262x349px, 100x75px) фиксированные размеры масок (80px, 200px) покрывают слишком большую область.

**Решение:** Использовать пропорциональные размеры:
```python
corner_h = int(height * 0.10)  # 10% высоты
corner_w = int(width * 0.30)   # 30% ширины
```

## Рекомендации

### Для полноценного удаления водяных знаков Cian:

**Вариант 1: Использовать только хорошие фото**
- Не скачивать фото с полупрозрачными водяными знаками
- Использовать только версии без "cian.ru" текста
- Применять OpenCV для удаления логотипов в углах

**Вариант 2: Установить IOPaint отдельно (Python 3.10-3.11)**
```bash
# Создать отдельное окружение
conda create -n iopaint python=3.11
conda activate iopaint
pip install iopaint

# Запустить как сервис
iopaint start --model=lama --port=8080
```

Затем отправлять запросы из основного приложения к этому сервису.

**Вариант 3: Использовать готовый API**
- Есть платные API для удаления водяных знаков
- remove.bg (не только фон, но и объекты)
- watermarkremover.io API

### Что реализовано и готово к использованию

✅ **Модуль [src/watermark_remover.py](src/watermark_remover.py:1)**
- Обнаружение водяных знаков по позиции
- Обнаружение по цвету
- OpenCV inpainting
- Пакетная обработка URL

✅ **Демо-функция**
```bash
python src/watermark_remover.py
```

✅ **Интеграция в парсер**
Можно добавить в [src/cian_parser_breadcrumbs.py](src/cian_parser_breadcrumbs.py:1):
```python
from src.watermark_remover import WatermarkRemover

def download_images_clean(self, urls):
    """Скачать изображения и очистить от водяных знаков"""
    remover = WatermarkRemover()
    return remover.batch_process_urls(urls)
```

## Выводы

1. **OpenCV inpainting:**
   - ✅ Работает "из коробки"
   - ✅ Быстрый (2 сек на фото)
   - ✅ Хорошо удаляет непрозрачные объекты
   - ❌ Плохо справляется с полупрозрачными водяными знаками

2. **IOPaint (LaMa):**
   - ✅ Лучшее качество
   - ❌ Недоступен для Python 3.13
   - ⚠️ Требует установки отдельно или через API

3. **Практическое решение:**
   - Использовать OpenCV для базовой очистки
   - Полупрозрачные водяные знаки оставить как есть (они не критичны)
   - Или работать с версиями фото без водяных знаков (если Cian их предоставляет)

## Файлы проекта

- [src/watermark_remover.py](src/watermark_remover.py) - основной модуль
- [test_watermark_removal.py](test_watermark_removal.py) - проверка библиотек
- [test_enhanced_watermark.py](test_enhanced_watermark.py) - расширенный тест
- [test_simple_live.py](test_simple_live.py) - простой подход
- [test_multiple_photos.py](test_multiple_photos.py) - пакетный тест
- [test_images/](test_images/) - результаты тестов
- [test_images/batch/](test_images/batch/) - пакетные результаты

---

**Дата тестирования:** 2025-11-04
**Python версия:** 3.13
**OpenCV версия:** 4.12.0.88
