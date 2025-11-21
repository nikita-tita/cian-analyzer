"""
Пример использования мультиисточникового поиска аналогов

Демонстрирует поиск по нескольким источникам одновременно (ЦИАН + ДомКлик)
"""

import sys
import os

# Добавляем путь к src
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.parsers.multi_source_search import MultiSourceSearchStrategy, SearchConfig, search_across_sources
from src.parsers import get_global_registry
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def example_simple_search():
    """Простой пример поиска по нескольким источникам"""
    print("="*80)
    print("🔍 ПРИМЕР 1: Простой мультиисточниковый поиск")
    print("="*80)

    # Целевая квартира (эталон для поиска аналогов)
    target_property = {
        'price': 5000000,
        'total_area': 50,
        'rooms': 2,
        'floor': 5,
        'floor_total': 10,
        'address': 'Санкт-Петербург, Невский проспект',
    }

    print(f"\n📍 Целевая квартира:")
    print(f"  Цена: {target_property['price']:,} ₽")
    print(f"  Площадь: {target_property['total_area']} м²")
    print(f"  Комнат: {target_property['rooms']}")
    print(f"  Этаж: {target_property['floor']}/{target_property['floor_total']}")

    # Используем удобную функцию
    print(f"\n🔄 Поиск аналогов в ЦИАН и ДомКлик...")
    results = search_across_sources(
        target_property=target_property,
        sources=['cian', 'domclick'],  # Поиск в двух источниках
        strategy='citywide',  # Стратегия: по всему городу
        limit_per_source=10,  # Максимум 10 результатов с каждого источника
        parallel=True  # Параллельный поиск (быстрее)
    )

    print(f"\n✅ Найдено {len(results)} аналогов")

    # Показываем первые 5 результатов
    print(f"\n📋 Первые 5 результатов:")
    for i, result in enumerate(results[:5], 1):
        print(f"\n  {i}. [{result.get('source', 'unknown').upper()}] {result.get('title', 'N/A')}")
        print(f"     Цена: {result.get('price', 0):,.0f} ₽")
        print(f"     Площадь: {result.get('total_area', 0)} м²")
        print(f"     Адрес: {result.get('address', 'N/A')[:60]}...")

    # Статистика по источникам
    sources_count = {}
    for result in results:
        source = result.get('source', 'unknown')
        sources_count[source] = sources_count.get(source, 0) + 1

    print(f"\n📊 Статистика по источникам:")
    for source, count in sources_count.items():
        print(f"  {source.upper()}: {count} объектов")


def example_advanced_search():
    """Продвинутый пример с настройкой конфигурации"""
    print("\n\n")
    print("="*80)
    print("🔍 ПРИМЕР 2: Продвинутый поиск с настройкой")
    print("="*80)

    # Целевая квартира
    target_property = {
        'price': 8000000,
        'total_area': 70,
        'rooms': 3,
        'residential_complex': 'ЖК Премьер Палас',  # Для стратегии same_building
        'metro': ['Адмиралтейская', 'Невский проспект'],
    }

    print(f"\n📍 Целевая квартира:")
    print(f"  Цена: {target_property['price']:,} ₽")
    print(f"  Площадь: {target_property['total_area']} м²")
    print(f"  Комнат: {target_property['rooms']}")
    print(f"  ЖК: {target_property['residential_complex']}")

    # Создаем стратегию
    strategy = MultiSourceSearchStrategy()

    # Конфигурация поиска
    config = SearchConfig(
        sources=['cian', 'domclick'],  # Источники
        strategy='same_building',  # Ищем в том же ЖК
        limit_per_source=20,  # Больше результатов
        parallel=True,
        merge_duplicates=True,  # Убираем дубликаты
        sort_by='price'  # Сортируем по цене
    )

    print(f"\n🔄 Поиск в том же ЖК ({config.strategy})...")
    results = strategy.search(target_property, config)

    print(f"\n✅ Найдено {len(results)} аналогов в том же ЖК")

    # Показываем результаты
    if results:
        print(f"\n📋 Результаты (отсортированы по цене):")
        for i, result in enumerate(results[:5], 1):
            print(f"\n  {i}. [{result.get('source', 'unknown').upper()}] {result.get('title', 'N/A')}")
            print(f"     Цена: {result.get('price', 0):,.0f} ₽")
            print(f"     Площадь: {result.get('total_area', 0)} м²")
            print(f"     ЖК: {result.get('residential_complex', 'N/A')}")
    else:
        print("\n⚠️ Аналогов в том же ЖК не найдено")
        print("💡 Попробуйте стратегию 'same_area' или 'citywide'")


def example_all_sources():
    """Пример поиска по всем доступным источникам"""
    print("\n\n")
    print("="*80)
    print("🔍 ПРИМЕР 3: Поиск по всем доступным источникам")
    print("="*80)

    # Получаем реестр парсеров
    registry = get_global_registry()

    # Показываем доступные источники
    available_sources = registry.get_all_sources()
    print(f"\n📚 Доступные источники: {', '.join(available_sources)}")

    # Показываем информацию о каждом парсере
    print(f"\n📊 Информация о парсерах:")
    for source in available_sources:
        info = registry.get_parser_info(source)
        if info:
            print(f"\n  {source.upper()}:")
            print(f"    Поиск: {'✅' if info.get('supports_search') else '❌'}")
            print(f"    Регионы: {', '.join(info.get('supports_regions', []))}")
            print(f"    API: {'✅' if info.get('has_api') else '❌'}")

    # Целевая квартира
    target_property = {
        'price': 6000000,
        'total_area': 55,
        'rooms': 2,
    }

    print(f"\n🔄 Поиск по всем источникам с поддержкой search...")

    # Поиск только в источниках с поддержкой search
    sources_with_search = []
    for source in available_sources:
        info = registry.get_parser_info(source)
        if info and info.get('supports_search'):
            sources_with_search.append(source)

    if sources_with_search:
        results = search_across_sources(
            target_property=target_property,
            sources=sources_with_search,
            strategy='citywide',
            limit_per_source=15,
            parallel=True
        )

        print(f"\n✅ Найдено {len(results)} аналогов")

        # Статистика
        sources_count = {}
        for result in results:
            source = result.get('source', 'unknown')
            sources_count[source] = sources_count.get(source, 0) + 1

        print(f"\n📊 Статистика по источникам:")
        for source, count in sorted(sources_count.items()):
            print(f"  {source.upper()}: {count} объектов")
    else:
        print("\n⚠️ Нет доступных источников с поддержкой поиска")


def main():
    """Главная функция"""
    print("\n")
    print("╔" + "="*78 + "╗")
    print("║" + " "*15 + "ПРИМЕРЫ МУЛЬТИИСТОЧНИКОВОГО ПОИСКА" + " "*29 + "║")
    print("╚" + "="*78 + "╝")

    try:
        # Пример 1: Простой поиск
        example_simple_search()

        # Пример 2: Продвинутый поиск
        example_advanced_search()

        # Пример 3: Все источники
        example_all_sources()

        print("\n\n")
        print("="*80)
        print("✅ ВСЕ ПРИМЕРЫ ЗАВЕРШЕНЫ")
        print("="*80)

    except Exception as e:
        logger.error(f"Ошибка выполнения примеров: {e}", exc_info=True)
        print(f"\n❌ Ошибка: {e}")
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
