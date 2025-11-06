"""
Скрипт для парсинга конкретных объявлений с Cian.ru
"""

from src.cian_parser import CianParser
import json
from datetime import datetime

def main():
    # Список ваших ссылок
    urls = [
        "https://www.cian.ru/sale/flat/319270312/",
        "https://www.cian.ru/sale/flat/319230363/",
        "https://www.cian.ru/sale/flat/319309313/",
        "https://www.cian.ru/sale/suburban/323383262/",
        "https://www.cian.ru/sale/flat/308177547/",
        "https://www.cian.ru/sale/flat/315831388/",
    ]

    # Создаем парсер с задержкой 3 секунды между запросами
    # (чтобы не нагружать сервер)
    parser = CianParser(delay=3.0)

    print("=" * 80)
    print("ПАРСИНГ ОБЪЯВЛЕНИЙ С CIAN.RU")
    print("=" * 80)
    print(f"\nВсего объявлений для парсинга: {len(urls)}")
    print(f"Задержка между запросами: {parser.delay} секунд")
    print(f"Примерное время выполнения: ~{len(urls) * parser.delay} секунд\n")

    results = []

    for i, url in enumerate(urls, 1):
        print(f"\n[{i}/{len(urls)}] Парсинг: {url}")
        print("-" * 80)

        try:
            # Парсим детальную страницу
            data = parser.parse_detail_page(url)

            if data and data.get('title'):
                print(f"✓ Успешно!")
                print(f"  Заголовок: {data.get('title', 'Н/Д')[:70]}...")
                print(f"  Цена: {data.get('price', 'Н/Д')}")
                print(f"  Адрес: {data.get('address', 'Н/Д')}")

                # Показываем основные характеристики
                chars = data.get('characteristics', {})
                if chars:
                    print(f"  Характеристики:")
                    for key, value in list(chars.items())[:5]:  # Первые 5
                        print(f"    - {key}: {value}")

                results.append(data)
            else:
                print(f"✗ Не удалось извлечь данные")
                results.append({
                    'url': url,
                    'error': 'Не удалось извлечь данные'
                })

        except Exception as e:
            print(f"✗ Ошибка: {e}")
            results.append({
                'url': url,
                'error': str(e)
            })

    # Сохраняем результаты
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"parsed_listings_{timestamp}.json"

    parser.save_to_json(results, filename)

    # Итоги
    print("\n" + "=" * 80)
    print("ПАРСИНГ ЗАВЕРШЕН")
    print("=" * 80)
    print(f"Успешно обработано: {len([r for r in results if r.get('title')])} из {len(urls)}")
    print(f"Результаты сохранены в: {filename}")

    # Краткая статистика
    print("\n📊 КРАТКАЯ СТАТИСТИКА:")
    for i, result in enumerate(results, 1):
        if result.get('title'):
            print(f"{i}. ✓ {result['title'][:60]}... - {result.get('price', 'Н/Д')}")
        else:
            print(f"{i}. ✗ Ошибка: {result.get('error', 'Неизвестная ошибка')}")

    print(f"\n💾 Полные данные в файле: {filename}")
    print("\n📝 Для просмотра JSON:")
    print(f"   cat {filename} | python -m json.tool")


if __name__ == "__main__":
    main()
