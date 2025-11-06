#!/usr/bin/env python3
"""
Интерактивный экспорт Markdown в выбранное место
"""

import os
from src.markdown_exporter import save_results_as_markdown


def get_demo_data():
    """Возвращает демонстрационные данные"""
    return [
        {
            'url': 'https://www.cian.ru/sale/flat/319270312/',
            'title': '3-комн. квартира, 82 м², 5/9 эт.',
            'price': '15 млн ₽',
            'address': 'Москва, Сущёвский Вал улица, 5с1',
            'metro': ['Цветной бульвар (5 мин пешком)', 'Менделеевская (8 мин пешком)'],
            'area': '82 м²',
            'floor': '5 из 9',
            'rooms': '3',
            'description': 'Продается отличная 3-комнатная квартира в центре Москвы.',
            'characteristics': {
                'Тип дома': 'Панельный',
                'Год постройки': '1985',
            },
            'images': [
                'https://cdn-p.cian.site/images/1/example1.jpg',
                'https://cdn-p.cian.site/images/1/example2.jpg',
            ],
            'coordinates': {'lat': 55.777594, 'lon': 37.618916},
        }
    ]


def main():
    print("=" * 80)
    print("📝 ЭКСПОРТ В MARKDOWN")
    print("=" * 80)
    print()
    print("Выберите действие:")
    print()
    print("1. Экспорт в текущую папку")
    print("2. Экспорт в ~/Downloads")
    print("3. Экспорт в ~/Desktop")
    print("4. Указать свой путь")
    print()

    try:
        choice = input("Ваш выбор (1-4): ").strip()
    except KeyboardInterrupt:
        print("\n\nОтменено")
        return

    # Определяем путь
    home = os.path.expanduser("~")

    if choice == "1":
        path = "."
        location = "текущая папка"
    elif choice == "2":
        path = os.path.join(home, "Downloads")
        location = "~/Downloads"
    elif choice == "3":
        path = os.path.join(home, "Desktop")
        location = "~/Desktop"
    elif choice == "4":
        try:
            path = input("Введите полный путь: ").strip()
            location = path
        except KeyboardInterrupt:
            print("\n\nОтменено")
            return
    else:
        print("❌ Неверный выбор!")
        return

    # Проверяем существование пути
    if not os.path.exists(path):
        print(f"❌ Путь не существует: {path}")
        return

    # Имя файла
    print()
    try:
        filename = input("Имя файла (Enter = auto): ").strip()
    except KeyboardInterrupt:
        print("\n\nОтменено")
        return

    if not filename:
        filename = None
    elif not filename.endswith('.md'):
        filename = filename + '.md'

    # Полный путь к файлу
    if filename:
        full_path = os.path.join(path, filename)
    else:
        full_path = None

    print()
    print("📊 Создание Markdown файла...")
    print()

    # Создаем демо данные (в реальности здесь будут ваши спарсенные данные)
    results = get_demo_data()

    # Экспортируем
    if full_path:
        md_file = save_results_as_markdown(results, full_path)
    else:
        # Создаем временно в текущей папке, потом переносим
        md_file = save_results_as_markdown(results)
        if path != ".":
            new_path = os.path.join(path, os.path.basename(md_file))
            os.rename(md_file, new_path)
            md_file = new_path

    # Получаем размер файла
    file_size = os.path.getsize(md_file) / 1024  # KB

    print("=" * 80)
    print("✅ УСПЕШНО ЭКСПОРТИРОВАНО!")
    print("=" * 80)
    print()
    print(f"📁 Место: {location}")
    print(f"📄 Файл: {os.path.basename(md_file)}")
    print(f"📊 Размер: {file_size:.1f} KB")
    print(f"🔗 Полный путь: {md_file}")
    print()
    print("🎯 Что делать дальше:")
    print(f"  • Открыть: open '{md_file}'")
    print(f"  • Просмотр в терминале: cat '{md_file}'")
    print(f"  • Конвертация в PDF: pandoc '{md_file}' -o export.pdf")
    print()
    print("=" * 80)


if __name__ == "__main__":
    main()
