#!/usr/bin/env python3
"""
Проверка извлечения данных через парсер напрямую
"""

import sys
import os

# Добавляем путь к модулям
sys.path.insert(0, '/Users/fatbookpro/Desktop/cian')

# Устанавливаем переменные окружения
os.environ['PYTHONPATH'] = '/Users/fatbookpro/Desktop/cian'

from src.parsers.playwright_parser import PlaywrightParser

print("=" * 80)
print("ПРОВЕРКА ИЗВЛЕЧЕНИЯ ДАННЫХ")
print("=" * 80)

url = "https://www.cian.ru/sale/flat/319271562/"
print(f"\nПарсим: {url}\n")

try:
    parser = PlaywrightParser()
    data = parser.parse_detail_page(url)

    print("✓ Данные успешно извлечены!")
    print("\n" + "=" * 80)
    print("КЛЮЧЕВЫЕ ПОЛЯ:")
    print("=" * 80)

    fields_to_check = {
        'title': 'Заголовок',
        'area': 'Площадь',
        'rooms': 'Комнат',
        'floor': 'Этаж',
        'price': 'Цена',
        'address': 'Адрес',
        'residential_complex': 'ЖК',
    }

    for field, label in fields_to_check.items():
        value = data.get(field, 'НЕТ')
        print(f"  {label:20s}: {value}")

    print("\n" + "=" * 80)
    print("ХАРАКТЕРИСТИКИ:")
    print("=" * 80)

    chars = data.get('characteristics', {})
    print(f"\nВсего характеристик: {len(chars)}")

    key_chars = ['Общая площадь', 'Этаж', 'Высота потолков', 'Год постройки']
    for key in key_chars:
        if key in chars:
            print(f"  {key:20s}: {chars[key]}")

    print("\n" + "=" * 80)
    print("РЕЗУЛЬТАТ:")
    print("=" * 80)

    expected = {
        'area': 180.4,
        'rooms': 3,
        'floor': '6',
    }

    all_ok = True
    for field, expected_value in expected.items():
        actual = data.get(field)
        if actual != expected_value:
            print(f"❌ {field}: ожидалось {expected_value}, получено {actual}")
            all_ok = False

    if all_ok:
        print("✅ Все ключевые поля извлечены корректно!")
        print(f"   area: {data.get('area')} м²")
        print(f"   rooms: {data.get('rooms')} комн.")
        print(f"   floor: {data.get('floor')} этаж")
    else:
        print("\n❌ Некоторые поля извлечены некорректно")

except Exception as e:
    print(f"\n❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
