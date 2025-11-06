#!/usr/bin/env python3
"""
Скрипт для скачивания последнего Markdown файла
"""

import os
import glob
import shutil
from datetime import datetime


def find_latest_markdown():
    """Находит последний созданный Markdown файл"""
    # Ищем все файлы с результатами
    patterns = [
        'cian_results_*.md',
        'demo_export.md'
    ]

    all_files = []
    for pattern in patterns:
        files = glob.glob(pattern)
        all_files.extend(files)

    if not all_files:
        return None

    # Сортируем по времени изменения (новейшие первыми)
    all_files.sort(key=os.path.getmtime, reverse=True)
    return all_files[0]


def copy_to_downloads(source_file):
    """Копирует файл в папку Загрузки"""
    # Определяем папку Загрузки
    home = os.path.expanduser("~")
    downloads = os.path.join(home, "Downloads")

    if not os.path.exists(downloads):
        downloads = home  # Если нет папки Downloads, копируем в домашнюю

    # Создаем имя файла с временной меткой
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"cian_export_{timestamp}.md"
    destination = os.path.join(downloads, filename)

    # Копируем файл
    shutil.copy2(source_file, destination)
    return destination


def main():
    print("=" * 80)
    print("📥 СКАЧИВАНИЕ ПОСЛЕДНЕГО РЕЗУЛЬТАТА")
    print("=" * 80)
    print()

    # Находим последний файл
    latest_file = find_latest_markdown()

    if not latest_file:
        print("❌ Не найдено файлов с результатами!")
        print()
        print("Сначала запустите один из скриптов:")
        print("  • python3 demo_markdown_export.py")
        print("  • python3 parse_with_playwright.py")
        return

    print(f"📄 Найден файл: {latest_file}")
    file_size = os.path.getsize(latest_file) / 1024  # в KB
    print(f"📊 Размер: {file_size:.1f} KB")
    print()

    # Копируем в Downloads
    try:
        destination = copy_to_downloads(latest_file)
        print("✅ УСПЕШНО СКАЧАНО!")
        print()
        print(f"📁 Сохранено в: {destination}")
        print()
        print("🎯 Что можно сделать дальше:")
        print(f"  • Открыть файл: open '{destination}'")
        print(f"  • Просмотреть: cat '{destination}'")
        print(f"  • Конвертировать в PDF: pandoc '{destination}' -o export.pdf")
        print()
        print("=" * 80)

    except Exception as e:
        print(f"❌ Ошибка при копировании: {e}")


if __name__ == "__main__":
    main()
