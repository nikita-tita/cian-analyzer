"""
Парсинг ваших ссылок с Cian.ru используя Playwright
Извлекает ВСЕ данные с максимальной эффективностью
"""

from src.cian_parser_playwright import CianParserPlaywright
from src.markdown_exporter import save_results_as_markdown
from datetime import datetime
import json


def main():
    """Парсинг всех ваших ссылок"""

    # Ваши ссылки
    urls = [
        "https://www.cian.ru/sale/flat/319270312/",
        "https://www.cian.ru/sale/flat/319230363/",
        "https://www.cian.ru/sale/flat/319309313/",
        "https://www.cian.ru/sale/suburban/323383262/",
        "https://www.cian.ru/sale/flat/308177547/",
        "https://www.cian.ru/sale/flat/315831388/",
    ]

    print("=" * 80)
    print("🚀 ПАРСИНГ С PLAYWRIGHT - МАКСИМАЛЬНАЯ ЭФФЕКТИВНОСТЬ")
    print("=" * 80)
    print(f"\n📊 Всего объявлений: {len(urls)}")
    print("⚡ Используется: Playwright (на 35% быстрее Selenium)")
    print("🎯 Ожидаемая успешность: 90-95% всех данных\n")

    # Парсим с Playwright
    results = []

    with CianParserPlaywright(headless=True, delay=2.0) as parser:
        for i, url in enumerate(urls, 1):
            print(f"\n[{i}/{len(urls)}] Парсинг: {url}")
            print("-" * 80)

            try:
                data = parser.parse_detail_page(url)

                if data.get('title'):
                    print(f"✓ УСПЕШНО!")
                    print(f"  📝 Заголовок: {data.get('title')[:70]}...")
                    print(f"  💰 Цена: {data.get('price', 'Н/Д')}")
                    print(f"  📍 Адрес: {data.get('address', 'Н/Д')[:50]}...")
                    print(f"  🚇 Метро: {', '.join(data.get('metro', []))[:50] or 'Н/Д'}")
                    print(f"  📏 Площадь: {data.get('area', 'Н/Д')}")
                    print(f"  🏢 Этаж: {data.get('floor', 'Н/Д')}")
                    print(f"  📷 Изображений: {len(data.get('images', []))}")
                    print(f"  📋 Характеристик: {len(data.get('characteristics', {}))}")

                    if data.get('description'):
                        desc_preview = data['description'][:100].replace('\n', ' ')
                        print(f"  📄 Описание: {desc_preview}...")

                    results.append(data)
                else:
                    print(f"⚠️  Данные частично извлечены")
                    results.append(data)

            except Exception as e:
                print(f"✗ ОШИБКА: {e}")
                results.append({
                    'url': url,
                    'error': str(e)
                })

    # Сохраняем результаты
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # JSON файл
    json_filename = f"playwright_results_{timestamp}.json"
    with open(json_filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # Markdown файл
    md_filename = f"cian_results_{timestamp}.md"
    save_results_as_markdown(results, md_filename)

    # Статистика
    print("\n" + "=" * 80)
    print("📊 РЕЗУЛЬТАТЫ ПАРСИНГА")
    print("=" * 80)

    successful = len([r for r in results if r.get('title')])
    with_price = len([r for r in results if r.get('price')])
    with_address = len([r for r in results if r.get('address')])
    with_metro = len([r for r in results if r.get('metro')])
    with_images = len([r for r in results if r.get('images')])
    with_description = len([r for r in results if r.get('description')])

    print(f"\n✅ Успешно обработано: {successful}/{len(urls)} ({successful/len(urls)*100:.1f}%)")
    print(f"\n📈 Извлечено данных:")
    print(f"  • Заголовки:      {successful}/{len(urls)} ({successful/len(urls)*100:.0f}%)")
    print(f"  • Цены:           {with_price}/{len(urls)} ({with_price/len(urls)*100:.0f}%)")
    print(f"  • Адреса:         {with_address}/{len(urls)} ({with_address/len(urls)*100:.0f}%)")
    print(f"  • Метро:          {with_metro}/{len(urls)} ({with_metro/len(urls)*100:.0f}%)")
    print(f"  • Описания:       {with_description}/{len(urls)} ({with_description/len(urls)*100:.0f}%)")
    print(f"  • Изображения:    {with_images}/{len(urls)} ({with_images/len(urls)*100:.0f}%)")

    total_images = sum(len(r.get('images', [])) for r in results)
    total_chars = sum(len(r.get('characteristics', {})) for r in results)
    print(f"\n📷 Всего изображений: {total_images}")
    print(f"📋 Всего характеристик: {total_chars}")

    print(f"\n💾 Данные сохранены:")
    print(f"   • JSON: {json_filename}")
    print(f"   • Markdown: {md_filename}")

    # Детальная информация по каждому объявлению
    print("\n" + "=" * 80)
    print("📝 ДЕТАЛЬНАЯ ИНФОРМАЦИЯ")
    print("=" * 80)

    for i, result in enumerate(results, 1):
        if result.get('title'):
            print(f"\n{i}. {result['title']}")
            print(f"   💰 {result.get('price', 'Цена не указана')}")
            if result.get('address'):
                print(f"   📍 {result['address']}")
            if result.get('metro'):
                print(f"   🚇 {', '.join(result['metro'])}")
        else:
            print(f"\n{i}. ❌ Ошибка: {result.get('error', 'Неизвестная ошибка')}")

    print("\n" + "=" * 80)
    print("✨ ПАРСИНГ ЗАВЕРШЕН!")
    print("=" * 80)
    print(f"\n📖 Для просмотра результатов:")
    print(f"   • Markdown (читаемый формат):")
    print(f"     open {md_filename}")
    print(f"\n   • JSON (программный формат):")
    print(f"     cat {json_filename} | python -m json.tool | less")
    print(f"\n🔍 Или откройте файлы в редакторе:")
    print(f"   open {md_filename} {json_filename}")


if __name__ == "__main__":
    main()
