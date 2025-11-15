#!/usr/bin/env python3
"""
Пример интеграции адаптивной системы парсинга с существующим приложением

Этот файл показывает как интегрировать новую систему в app_new.py
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from parsers.adaptive_orchestrator import AdaptiveParserOrchestrator, ParsedResult
from parsers.utils import (
    detect_platform,
    is_valid_property_url,
    normalize_property_data,
    filter_properties,
    deduplicate_properties,
    sort_properties,
    format_property_summary,
    validate_property_data
)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


class EnhancedPropertyParser:
    """
    Улучшенный парсер для интеграции с существующим приложением

    Обертка над AdaptiveParserOrchestrator с дополнительной функциональностью
    """

    def __init__(self, cache=None):
        """
        Args:
            cache: Redis cache instance (опционально)
        """
        self.orchestrator = AdaptiveParserOrchestrator(cache=cache, enable_stats=True)
        logger.info("✓ EnhancedPropertyParser инициализирован")

    def parse_url(self, url: str, validate: bool = True) -> dict:
        """
        Парсинг URL с валидацией и нормализацией

        Args:
            url: URL объявления
            validate: Валидировать результат

        Returns:
            Словарь с данными или информацией об ошибке

        Examples:
            >>> parser = EnhancedPropertyParser()
            >>> result = parser.parse_url('https://www.cian.ru/sale/flat/12345/')
        """
        # Проверяем валидность URL
        if not is_valid_property_url(url):
            return {
                'success': False,
                'error': 'Invalid URL format',
                'url': url
            }

        # Определяем платформу
        platform = detect_platform(url)
        logger.info(f"Платформа: {platform}")

        # Парсим
        result: ParsedResult = self.orchestrator.parse_property(url)

        if not result.success:
            return {
                'success': False,
                'error': result.error,
                'platform': platform,
                'url': url,
                'fallback_chain': result.fallback_chain
            }

        # Нормализуем данные
        data = normalize_property_data(result.data)

        # Валидация
        if validate:
            is_valid, errors = validate_property_data(data)
            if not is_valid:
                logger.warning(f"Данные не прошли валидацию: {errors}")
                data['validation_errors'] = errors
                data['validation_passed'] = False
            else:
                data['validation_passed'] = True

        # Добавляем метаданные
        data['platform'] = platform
        data['strategy_used'] = result.strategy_used.value if result.strategy_used else None
        data['response_time'] = result.response_time
        data['parsing_success'] = True

        return data

    def search_analogs(
        self,
        target_property: dict,
        sources: list = None,
        limit: int = 20,
        strategy: str = 'citywide',
        filters: dict = None
    ) -> list:
        """
        Поиск аналогов с фильтрацией и сортировкой

        Args:
            target_property: Целевой объект
            sources: Список источников (None = все)
            limit: Максимальное количество результатов
            strategy: Стратегия поиска
            filters: Дополнительные фильтры (min_price, max_price, etc.)

        Returns:
            Список аналогов

        Examples:
            >>> parser = EnhancedPropertyParser()
            >>> target = {'price': 10_000_000, 'total_area': 50, 'rooms': 2}
            >>> analogs = parser.search_analogs(target, sources=['cian', 'domclick'])
        """
        logger.info(f"Поиск аналогов (sources={sources}, limit={limit}, strategy={strategy})")

        # Поиск через оркестратор
        results = self.orchestrator.search_similar(
            target_property,
            sources=sources,
            limit=limit * 2,  # Берем с запасом для фильтрации
            strategy=strategy
        )

        # Нормализуем все результаты
        normalized_results = [normalize_property_data(r) for r in results]

        # Применяем фильтры если указаны
        if filters:
            normalized_results = filter_properties(
                normalized_results,
                min_price=filters.get('min_price'),
                max_price=filters.get('max_price'),
                min_area=filters.get('min_area'),
                max_area=filters.get('max_area'),
                rooms=filters.get('rooms'),
                sources=filters.get('sources')
            )

        # Удаляем дубликаты
        unique_results = deduplicate_properties(normalized_results)

        # Сортируем по цене
        sorted_results = sort_properties(unique_results, by='price')

        # Возвращаем с ограничением
        return sorted_results[:limit]

    def get_statistics(self) -> dict:
        """
        Получить статистику работы парсера

        Returns:
            Словарь со статистикой
        """
        return self.orchestrator.get_stats()

    def print_statistics(self):
        """Вывести статистику в консоль"""
        self.orchestrator.print_stats()


def demo_integration():
    """Демонстрация интеграции"""
    print("\n" + "="*80)
    print("ДЕМОНСТРАЦИЯ ИНТЕГРАЦИИ С СУЩЕСТВУЮЩИМ ПРИЛОЖЕНИЕМ")
    print("="*80 + "\n")

    # Создаем enhanced parser
    parser = EnhancedPropertyParser()

    # Пример 1: Парсинг одного объявления
    print("\n📋 ПРИМЕР 1: Парсинг одного объявления")
    print("-"*60)

    # Замените на реальный URL для тестирования
    test_url = 'https://www.cian.ru/sale/flat/12345/'

    print(f"URL: {test_url}")
    print(f"Платформа: {detect_platform(test_url)}\n")

    result = parser.parse_url(test_url)

    if result.get('parsing_success'):
        print("✅ Успешно спарсено!")
        print(format_property_summary(result))
        print(f"\nСтратегия: {result.get('strategy_used')}")
        print(f"Время: {result.get('response_time', 0):.2f}s")
        print(f"Валидация: {'✅ Пройдена' if result.get('validation_passed') else '❌ Не пройдена'}")
    else:
        print(f"❌ Ошибка: {result.get('error')}")

    # Пример 2: Поиск аналогов
    print("\n\n📋 ПРИМЕР 2: Поиск аналогов с фильтрацией")
    print("-"*60)

    target = {
        'price': 10_000_000,
        'total_area': 50,
        'rooms': 2,
        'metro': ['Невский проспект']
    }

    print("Целевой объект:")
    print(f"  Цена: {target['price']:,.0f} ₽")
    print(f"  Площадь: {target['total_area']} м²")
    print(f"  Комнаты: {target['rooms']}\n")

    filters = {
        'min_price': 8_000_000,
        'max_price': 12_000_000,
        'min_area': 45,
        'max_area': 60,
    }

    analogs = parser.search_analogs(
        target,
        sources=['cian', 'domclick'],
        limit=5,
        filters=filters
    )

    print(f"Найдено аналогов: {len(analogs)}\n")

    for i, analog in enumerate(analogs[:3], 1):
        print(f"{i}. {format_property_summary(analog)}")

    # Пример 3: Статистика
    print("\n\n📋 ПРИМЕР 3: Статистика работы")
    print("-"*60)

    parser.print_statistics()

    print("\n" + "="*80)


def integration_with_existing_app():
    """
    Пример интеграции с существующим app_new.py

    Показывает как заменить старый парсер на новый
    """
    print("\n" + "="*80)
    print("ИНТЕГРАЦИЯ С app_new.py")
    print("="*80 + "\n")

    print("""
    # ===== СТАРЫЙ КОД (app_new.py) =====

    from src.parsers.playwright_parser import PlaywrightParser

    parser = PlaywrightParser(cache=cache)
    parser.start()

    # Парсинг
    data = parser.parse_detail_page(url)

    # Поиск аналогов
    analogs = parser.search_similar(target_property, limit=20)

    parser.close()


    # ===== НОВЫЙ КОД (с адаптивной системой) =====

    from integration_example import EnhancedPropertyParser

    parser = EnhancedPropertyParser(cache=cache)

    # Парсинг (автоматический выбор стратегии!)
    result = parser.parse_url(url, validate=True)
    data = result if result.get('parsing_success') else None

    # Поиск аналогов (на ВСЕХ платформах!)
    analogs = parser.search_analogs(
        target_property,
        sources=['cian', 'domclick', 'avito', 'yandex'],
        limit=20,
        filters={'min_price': 8000000, 'max_price': 12000000}
    )

    # Статистика
    stats = parser.get_statistics()


    # ===== ПРЕИМУЩЕСТВА =====

    1. ✅ Автоматический выбор стратегии (API, Browser, Nodriver)
    2. ✅ Cascading fallback при неудаче
    3. ✅ Поддержка 4 платформ вместо 1
    4. ✅ Обход защит (TLS fingerprinting, Cloudflare, DataDome)
    5. ✅ Встроенная валидация данных
    6. ✅ Нормализация и фильтрация
    7. ✅ Детальная статистика

    """)


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == '--integration':
        integration_with_existing_app()
    else:
        demo_integration()
