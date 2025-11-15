#!/usr/bin/env python3
"""
Демонстрация адаптивной системы парсинга недвижимости

Этот скрипт показывает возможности новой архитектуры:
1. Автоматический выбор оптимальной стратегии
2. Cascading fallback при неудаче
3. Парсинг со всех поддерживаемых источников
4. Сбор аналогов с нескольких платформ
"""

import logging
import sys
from pathlib import Path

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from parsers.adaptive_orchestrator import AdaptiveParserOrchestrator

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def demo_single_property_parsing():
    """Демонстрация парсинга одного объявления"""
    print("\n" + "="*80)
    print("ДЕМО 1: Парсинг одного объявления с адаптивным выбором стратегии")
    print("="*80 + "\n")

    orchestrator = AdaptiveParserOrchestrator(enable_stats=True)

    # Примеры URL для тестирования (замените на реальные)
    test_urls = {
        'cian': 'https://www.cian.ru/sale/flat/12345/',  # Замените на реальный URL
        'domclick': 'https://domclick.ru/card/sale__flat__12345',  # Замените на реальный URL
        # 'avito': 'https://www.avito.ru/sankt-peterburg/kvartiry/2-k._kvartira_56m_44et._1234567890',
        # 'yandex': 'https://realty.yandex.ru/offer/1234567890/',
    }

    print("📋 Тестовые URL:")
    for source, url in test_urls.items():
        print(f"   - {source}: {url[:60]}...")

    print("\n" + "-"*80 + "\n")

    # Парсим каждый URL
    for source, url in test_urls.items():
        print(f"\n🚀 Парсинг {source.upper()}...")
        print("-"*60)

        result = orchestrator.parse_property(url, enable_fallback=True)

        if result.success:
            print(f"✅ УСПЕХ!")
            print(f"   Стратегия: {result.strategy_used.value}")
            print(f"   Время: {result.response_time:.2f}s")
            print(f"   Fallback chain: {' → '.join(result.fallback_chain)}")

            # Выводим ключевые данные
            data = result.data
            print(f"\n📊 Данные:")
            print(f"   Название: {data.get('title', 'N/A')[:60]}...")
            print(f"   Цена: {data.get('price', 'N/A'):,.0f} ₽" if data.get('price') else "   Цена: N/A")
            print(f"   Площадь: {data.get('total_area', 'N/A')} м²")
            print(f"   Комнат: {data.get('rooms', 'N/A')}")
            print(f"   Этаж: {data.get('floor', 'N/A')}/{data.get('floor_total', 'N/A')}")
        else:
            print(f"❌ НЕУДАЧА: {result.error}")
            print(f"   Fallback chain: {' → '.join(result.fallback_chain)}")

        print("\n" + "-"*60)

    # Выводим статистику
    print("\n" + "="*80)
    print("📊 СТАТИСТИКА РАБОТЫ ОРКЕСТРАТОРА")
    print("="*80)
    orchestrator.print_stats()


def demo_multi_source_search():
    """Демонстрация поиска аналогов со всех источников"""
    print("\n" + "="*80)
    print("ДЕМО 2: Поиск аналогов на нескольких платформах")
    print("="*80 + "\n")

    orchestrator = AdaptiveParserOrchestrator(enable_stats=True)

    # Целевой объект для поиска аналогов
    target_property = {
        'price': 10_000_000,
        'total_area': 50,
        'rooms': 2,
        'floor': 5,
        'floor_total': 10,
        'metro': ['Невский проспект'],
        'address': 'Санкт-Петербург, Невский проспект'
    }

    print("🎯 Целевой объект:")
    print(f"   Цена: {target_property['price']:,.0f} ₽")
    print(f"   Площадь: {target_property['total_area']} м²")
    print(f"   Комнаты: {target_property['rooms']}")
    print(f"   Метро: {', '.join(target_property['metro'])}")

    print("\n" + "-"*80 + "\n")

    # Поиск на всех доступных источниках
    sources = ['cian', 'domclick']  # Начнем с доступных

    results = orchestrator.search_similar(
        target_property,
        sources=sources,
        limit=10,
        strategy='citywide'
    )

    print(f"\n📊 Найдено {len(results)} аналогов:")
    for i, result in enumerate(results[:5], 1):  # Показываем первые 5
        print(f"\n{i}. {result.get('source', 'N/A').upper()}")
        print(f"   Название: {result.get('title', 'N/A')[:60]}...")
        print(f"   Цена: {result.get('price', 'N/A'):,.0f} ₽" if result.get('price') else f"   Цена: N/A")
        print(f"   Площадь: {result.get('total_area', 'N/A')} м²")
        print(f"   URL: {result.get('url', 'N/A')[:60]}...")


def demo_strategy_comparison():
    """Демонстрация сравнения стратегий"""
    print("\n" + "="*80)
    print("ДЕМО 3: Сравнение эффективности разных стратегий")
    print("="*80 + "\n")

    # Это демонстрация, реальный URL нужно заменить
    test_url = 'https://www.cian.ru/sale/flat/12345/'

    from parsers.adaptive_orchestrator import ParsingStrategy

    orchestrator = AdaptiveParserOrchestrator(enable_stats=True)

    strategies_to_test = [
        ParsingStrategy.API_FIRST,
        ParsingStrategy.BROWSER_LIGHT,
        ParsingStrategy.BROWSER_HEAVY,
    ]

    print(f"📋 Тестируем URL: {test_url[:60]}...")
    print(f"🔧 Стратегии: {[s.value for s in strategies_to_test]}\n")

    results = []

    for strategy in strategies_to_test:
        print(f"\n🎯 Тестирование: {strategy.value}")
        print("-"*60)

        result = orchestrator.parse_property(
            test_url,
            preferred_strategy=strategy,
            enable_fallback=False  # Без fallback для чистоты эксперимента
        )

        results.append({
            'strategy': strategy,
            'success': result.success,
            'time': result.response_time,
            'error': result.error
        })

        if result.success:
            print(f"   ✅ Успех за {result.response_time:.2f}s")
        else:
            print(f"   ❌ Неудача: {result.error}")

    # Сравнительная таблица
    print("\n" + "="*80)
    print("📊 СРАВНИТЕЛЬНАЯ ТАБЛИЦА")
    print("="*80 + "\n")

    print(f"{'Стратегия':<30} {'Результат':<15} {'Время (s)':<15}")
    print("-"*60)

    for r in results:
        status = "✅ Успех" if r['success'] else f"❌ {r['error'][:20]}"
        time_str = f"{r['time']:.2f}" if r['success'] else "N/A"
        print(f"{r['strategy'].value:<30} {status:<15} {time_str:<15}")

    print("\n" + "="*80)


def main():
    """Главная функция"""
    print("""
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║     АДАПТИВНАЯ СИСТЕМА ПАРСИНГА НЕДВИЖИМОСТИ                 ║
║                                                               ║
║     Поддержка: Циан, Домклик, Авито, Яндекс Недвижимость    ║
║     Технологии: Playwright, Nodriver, curl_cffi, httpx       ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
    """)

    print("\nВыберите демо:")
    print("  1. Парсинг одного объявления (адаптивный выбор стратегии)")
    print("  2. Поиск аналогов на нескольких платформах")
    print("  3. Сравнение эффективности стратегий")
    print("  4. Запустить все демо")
    print("  0. Выход")

    try:
        choice = input("\nВаш выбор (1-4): ").strip()

        if choice == '1':
            demo_single_property_parsing()
        elif choice == '2':
            demo_multi_source_search()
        elif choice == '3':
            demo_strategy_comparison()
        elif choice == '4':
            demo_single_property_parsing()
            demo_multi_source_search()
            demo_strategy_comparison()
        elif choice == '0':
            print("Выход...")
            return
        else:
            print("❌ Неверный выбор")

    except KeyboardInterrupt:
        print("\n\n⏹️  Прервано пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

    print("\n✅ Демонстрация завершена!")


if __name__ == '__main__':
    main()
