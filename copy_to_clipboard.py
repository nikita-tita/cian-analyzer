#!/usr/bin/env python3
"""
Копирование Markdown содержимого в буфер обмена
"""

import os
import glob
import subprocess
import platform


def find_latest_markdown():
    """Находит последний созданный Markdown файл"""
    patterns = ['cian_results_*.md', 'demo_export.md']
    all_files = []

    for pattern in patterns:
        files = glob.glob(pattern)
        all_files.extend(files)

    if not all_files:
        return None

    all_files.sort(key=os.path.getmtime, reverse=True)
    return all_files[0]


def copy_to_clipboard(text):
    """Копирует текст в буфер обмена (кросс-платформенно)"""
    system = platform.system()

    try:
        if system == 'Darwin':  # macOS
            process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
            process.communicate(text.encode('utf-8'))
            return True
        elif system == 'Linux':
            # Попробуем xclip
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


def main():
    print("=" * 80)
    print("📋 КОПИРОВАНИЕ В БУФЕР ОБМЕНА")
    print("=" * 80)
    print()

    # Находим последний файл
    latest_file = find_latest_markdown()

    if not latest_file:
        print("❌ Не найдено файлов с результатами!")
        print()
        print("Сначала запустите:")
        print("  • python3 demo_markdown_export.py")
        print("  • python3 parse_with_playwright.py")
        return

    print(f"📄 Найден файл: {latest_file}")

    # Читаем содержимое
    try:
        with open(latest_file, 'r', encoding='utf-8') as f:
            content = f.read()

        lines = content.count('\n')
        chars = len(content)
        size = len(content.encode('utf-8')) / 1024  # KB

        print(f"📊 Статистика:")
        print(f"   • Строк: {lines}")
        print(f"   • Символов: {chars}")
        print(f"   • Размер: {size:.1f} KB")
        print()

        # Копируем в буфер
        print("📋 Копирование в буфер обмена...")

        if copy_to_clipboard(content):
            print()
            print("✅ УСПЕШНО СКОПИРОВАНО!")
            print()
            print("🎯 Теперь вы можете:")
            print("  • Вставить в любой редактор (Cmd/Ctrl+V)")
            print("  • Отправить в чат")
            print("  • Вставить в Notion, Google Docs и т.д.")
            print()
        else:
            print()
            print("⚠️  Не удалось скопировать в буфер обмена")
            print()
            print("💡 Альтернатива:")
            print(f"   cat '{latest_file}' | pbcopy    # macOS")
            print(f"   cat '{latest_file}' | xclip     # Linux")
            print(f"   cat '{latest_file}' | clip      # Windows")
            print()

        print("=" * 80)

    except Exception as e:
        print(f"❌ Ошибка при чтении файла: {e}")


if __name__ == "__main__":
    main()
