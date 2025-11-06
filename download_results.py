#!/usr/bin/env python3
"""
🎯 Универсальный скрипт для скачивания/экспорта результатов

Выберите что вы хотите сделать:
1. Скопировать последний результат в Downloads
2. Скопировать в буфер обмена
3. Экспортировать в выбранное место
4. Показать все доступные файлы
"""

import os
import sys
import glob
import shutil
import subprocess
import platform
from datetime import datetime


class ResultsExporter:
    """Класс для работы с результатами парсинга"""

    @staticmethod
    def find_all_markdown_files():
        """Находит все Markdown файлы с результатами"""
        patterns = [
            'cian_results_*.md',
            'demo_export.md',
            'playwright_results_*.md'
        ]

        all_files = []
        for pattern in patterns:
            files = glob.glob(pattern)
            all_files.extend(files)

        # Сортируем по времени изменения (новейшие первыми)
        all_files.sort(key=os.path.getmtime, reverse=True)
        return all_files

    @staticmethod
    def get_file_info(filepath):
        """Получает информацию о файле"""
        if not os.path.exists(filepath):
            return None

        stat = os.stat(filepath)
        size_kb = stat.st_size / 1024
        modified = datetime.fromtimestamp(stat.st_mtime)

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.count('\n')
            chars = len(content)

        return {
            'size_kb': size_kb,
            'modified': modified,
            'lines': lines,
            'chars': chars
        }

    @staticmethod
    def copy_to_downloads(source_file):
        """Копирует файл в Downloads"""
        home = os.path.expanduser("~")
        downloads = os.path.join(home, "Downloads")

        if not os.path.exists(downloads):
            downloads = home

        # Создаем имя с timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        basename = os.path.splitext(os.path.basename(source_file))[0]
        filename = f"{basename}_{timestamp}.md"
        destination = os.path.join(downloads, filename)

        shutil.copy2(source_file, destination)
        return destination

    @staticmethod
    def copy_to_clipboard(text):
        """Копирует текст в буфер обмена"""
        system = platform.system()

        try:
            if system == 'Darwin':  # macOS
                process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
                process.communicate(text.encode('utf-8'))
                return True
            elif system == 'Linux':
                process = subprocess.Popen(['xclip', '-selection', 'clipboard'],
                                         stdin=subprocess.PIPE)
                process.communicate(text.encode('utf-8'))
                return True
            elif system == 'Windows':
                process = subprocess.Popen(['clip'], stdin=subprocess.PIPE)
                process.communicate(text.encode('utf-16le'))
                return True
        except FileNotFoundError:
            return False

        return False


def show_menu():
    """Показывает главное меню"""
    print("=" * 80)
    print("📥 СКАЧИВАНИЕ / ЭКСПОРТ РЕЗУЛЬТАТОВ")
    print("=" * 80)
    print()
    print("Выберите действие:")
    print()
    print("1. 📁 Скопировать последний результат в Downloads")
    print("2. 📋 Скопировать в буфер обмена")
    print("3. 📂 Экспортировать в выбранное место")
    print("4. 📊 Показать все доступные файлы")
    print("5. ❌ Выход")
    print()


def action_copy_to_downloads(exporter):
    """Действие 1: Копировать в Downloads"""
    files = exporter.find_all_markdown_files()

    if not files:
        print("\n❌ Не найдено файлов с результатами!")
        print("\nСначала запустите:")
        print("  • python3 demo_markdown_export.py")
        print("  • python3 parse_with_playwright.py")
        return

    latest = files[0]
    info = exporter.get_file_info(latest)

    print(f"\n📄 Файл: {latest}")
    print(f"📊 Размер: {info['size_kb']:.1f} KB")
    print(f"📅 Изменен: {info['modified'].strftime('%d.%m.%Y %H:%M')}")
    print()

    try:
        destination = exporter.copy_to_downloads(latest)
        print("✅ УСПЕШНО СКОПИРОВАНО!")
        print(f"\n📁 Сохранено в: {destination}")
        print(f"\n💡 Открыть файл: open '{destination}'")
    except Exception as e:
        print(f"❌ Ошибка: {e}")


def action_copy_to_clipboard(exporter):
    """Действие 2: Копировать в буфер"""
    files = exporter.find_all_markdown_files()

    if not files:
        print("\n❌ Не найдено файлов с результатами!")
        return

    latest = files[0]
    info = exporter.get_file_info(latest)

    print(f"\n📄 Файл: {latest}")
    print(f"📊 Строк: {info['lines']}, Символов: {info['chars']}")
    print()

    try:
        with open(latest, 'r', encoding='utf-8') as f:
            content = f.read()

        if exporter.copy_to_clipboard(content):
            print("✅ УСПЕШНО СКОПИРОВАНО В БУФЕР ОБМЕНА!")
            print("\n💡 Теперь можете вставить (Cmd/Ctrl+V) в любой редактор")
        else:
            print("⚠️  Не удалось скопировать автоматически")
            print(f"\n💡 Используйте: cat '{latest}' | pbcopy")
    except Exception as e:
        print(f"❌ Ошибка: {e}")


def action_export_to_custom(exporter):
    """Действие 3: Экспорт в выбранное место"""
    files = exporter.find_all_markdown_files()

    if not files:
        print("\n❌ Не найдено файлов с результатами!")
        return

    # Выбор файла
    print("\n📋 Доступные файлы:")
    for i, f in enumerate(files, 1):
        info = exporter.get_file_info(f)
        print(f"  {i}. {f} ({info['size_kb']:.1f} KB)")

    try:
        choice = int(input("\nВыберите файл (номер): ").strip())
        if choice < 1 or choice > len(files):
            print("❌ Неверный выбор!")
            return

        source_file = files[choice - 1]

        # Выбор места
        print("\n📁 Куда сохранить?")
        print("1. ~/Downloads")
        print("2. ~/Desktop")
        print("3. Текущая папка")
        print("4. Свой путь")

        dest_choice = input("\nВыбор (1-4): ").strip()
        home = os.path.expanduser("~")

        if dest_choice == "1":
            dest_path = os.path.join(home, "Downloads")
        elif dest_choice == "2":
            dest_path = os.path.join(home, "Desktop")
        elif dest_choice == "3":
            dest_path = "."
        elif dest_choice == "4":
            dest_path = input("Введите путь: ").strip()
        else:
            print("❌ Неверный выбор!")
            return

        if not os.path.exists(dest_path):
            print(f"❌ Путь не существует: {dest_path}")
            return

        # Имя файла
        filename = input("\nИмя файла (Enter = исходное): ").strip()
        if not filename:
            filename = os.path.basename(source_file)
        elif not filename.endswith('.md'):
            filename += '.md'

        destination = os.path.join(dest_path, filename)

        # Копируем
        shutil.copy2(source_file, destination)
        print("\n✅ УСПЕШНО ЭКСПОРТИРОВАНО!")
        print(f"\n📁 Сохранено: {destination}")

    except (ValueError, KeyboardInterrupt):
        print("\n❌ Отменено")


def action_show_all_files(exporter):
    """Действие 4: Показать все файлы"""
    files = exporter.find_all_markdown_files()

    if not files:
        print("\n❌ Не найдено файлов с результатами!")
        return

    print(f"\n📊 Найдено файлов: {len(files)}")
    print("\n" + "=" * 80)

    for i, f in enumerate(files, 1):
        info = exporter.get_file_info(f)
        print(f"\n{i}. {f}")
        print(f"   📊 Размер: {info['size_kb']:.1f} KB")
        print(f"   📅 Изменен: {info['modified'].strftime('%d.%m.%Y %H:%M')}")
        print(f"   📝 Строк: {info['lines']}, Символов: {info['chars']}")

    print("\n" + "=" * 80)


def main():
    """Главная функция"""
    exporter = ResultsExporter()

    while True:
        show_menu()

        try:
            choice = input("Ваш выбор (1-5): ").strip()
        except KeyboardInterrupt:
            print("\n\n👋 До свидания!")
            return

        print()

        if choice == "1":
            action_copy_to_downloads(exporter)
        elif choice == "2":
            action_copy_to_clipboard(exporter)
        elif choice == "3":
            action_export_to_custom(exporter)
        elif choice == "4":
            action_show_all_files(exporter)
        elif choice == "5":
            print("👋 До свидания!")
            break
        else:
            print("❌ Неверный выбор!")

        print()
        input("Нажмите Enter для продолжения...")
        print("\n" * 2)


if __name__ == "__main__":
    main()
