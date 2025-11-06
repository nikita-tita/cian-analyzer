"""
Примеры использования парсера Cian
"""

import sys
import os

# Добавляем путь к модулю
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.cian_parser import CianParser


def example_search_page():
    """Пример парсинга страницы поиска"""
    print("=" * 60)
    print("Пример 1: Парсинг страницы поиска")
    print("=" * 60)

    parser = CianParser(delay=2.0)

    # Пример URL для поиска квартир на продажу в Москве
    url = "https://www.cian.ru/cat.php?deal_type=sale&engine_version=2&offer_type=flat&region=1"

    listings = parser.parse_search_page(url)

    print(f"\nНайдено объявлений: {len(listings)}")

    # Показываем первые 3 объявления
    for i, listing in enumerate(listings[:3], 1):
        print(f"\n--- Объявление {i} ---")
        print(f"Заголовок: {listing.get('title')}")
        print(f"Цена: {listing.get('price')}")
        print(f"Адрес: {listing.get('address')}")
        print(f"Метро: {listing.get('metro')}")
        print(f"Площадь: {listing.get('area')}")
        print(f"URL: {listing.get('url')}")

    # Сохраняем в JSON
    if listings:
        parser.save_to_json(listings, 'search_results.json')


def example_detail_page():
    """Пример парсинга детальной страницы"""
    print("\n" + "=" * 60)
    print("Пример 2: Парсинг детальной страницы объявления")
    print("=" * 60)

    parser = CianParser(delay=2.0)

    # Замените на реальный URL объявления
    url = "https://www.cian.ru/sale/flat/123456789/"

    print(f"\nПарсинг объявления: {url}")

    detail_data = parser.parse_detail_page(url)

    print(f"\nЗаголовок: {detail_data.get('title')}")
    print(f"Цена: {detail_data.get('price')}")
    print(f"Адрес: {detail_data.get('address')}")
    print(f"Метро: {', '.join(detail_data.get('metro', []))}")
    print(f"\nОписание: {detail_data.get('description')[:200] if detail_data.get('description') else 'Нет'}...")

    print("\nХарактеристики:")
    for key, value in detail_data.get('characteristics', {}).items():
        print(f"  {key}: {value}")

    print(f"\nИзображений: {len(detail_data.get('images', []))}")
    print(f"Продавец: {detail_data.get('seller', {}).get('name')}")

    # Сохраняем в JSON
    parser.save_to_json([detail_data], 'detail_result.json')


def example_batch_parsing():
    """Пример пакетного парсинга"""
    print("\n" + "=" * 60)
    print("Пример 3: Пакетный парсинг с детальными данными")
    print("=" * 60)

    parser = CianParser(delay=2.0)

    # Парсим страницу поиска
    search_url = "https://www.cian.ru/cat.php?deal_type=rent&engine_version=2&offer_type=flat&region=1&room1=1"

    print(f"\nПарсинг страницы поиска: {search_url}")
    listings = parser.parse_search_page(search_url)

    print(f"Найдено {len(listings)} объявлений")

    # Парсим детальные данные для первых 3 объявлений
    detailed_listings = []

    for i, listing in enumerate(listings[:3], 1):
        if listing.get('url'):
            print(f"\nПарсинг детального объявления {i}/3...")
            detail = parser.parse_detail_page(listing['url'])
            detailed_listings.append(detail)

    # Сохраняем результаты
    parser.save_to_json(detailed_listings, 'detailed_results.json')

    print(f"\nПарсинг завершен. Детальных объявлений: {len(detailed_listings)}")


def main():
    """Главная функция"""
    print("Парсер Cian.ru")
    print("Выберите пример для запуска:")
    print("1. Парсинг страницы поиска")
    print("2. Парсинг детальной страницы")
    print("3. Пакетный парсинг")
    print("4. Запустить все примеры")

    choice = input("\nВаш выбор (1-4): ").strip()

    if choice == '1':
        example_search_page()
    elif choice == '2':
        example_detail_page()
    elif choice == '3':
        example_batch_parsing()
    elif choice == '4':
        example_search_page()
        example_detail_page()
        example_batch_parsing()
    else:
        print("Неверный выбор")


if __name__ == "__main__":
    main()
