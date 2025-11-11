#!/usr/bin/env python3
"""
Полный тест пайплайна: парсинг → анализ → проверка всех блоков отчета

Тестируем на реальном объекте: https://spb.cian.ru/sale/flat/319271562/
"""

import sys
import logging
from typing import Dict, Any

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Импорты модулей проекта
try:
    from src.parsers.playwright_parser import PlaywrightParser
    from src.analytics.analyzer import RealEstateAnalyzer
    from src.models.property import TargetProperty, AnalysisRequest
    from src.analytics.offer_generator import generate_housler_offer
except ImportError as e:
    logger.error(f"Ошибка импорта: {e}")
    logger.error("Запустите скрипт из корневой директории проекта")
    sys.exit(1)


def print_section(title: str, emoji: str = ""):
    """Печать разделителя секции"""
    print("\n" + "="*80)
    print(f"{emoji} {title}")
    print("="*80)


def health_check_block(block_name: str, data: Any, required_fields: list) -> bool:
    """
    Проверка заполнения блока данных

    Args:
        block_name: Название блока
        data: Данные блока
        required_fields: Список обязательных полей

    Returns:
        True если все поля заполнены
    """
    print(f"\n{'='*60}")
    print(f"🔍 HEALTH CHECK: {block_name}")
    print(f"{'='*60}")

    if not data:
        print("❌ FAILED: Блок отсутствует или пустой")
        return False

    if isinstance(data, dict):
        all_ok = True
        for field in required_fields:
            if '.' in field:
                # Nested field check
                parts = field.split('.')
                value = data
                for part in parts:
                    if isinstance(value, dict):
                        value = value.get(part)
                    else:
                        value = None
                        break
            else:
                value = data.get(field)

            if value is None or (isinstance(value, (list, dict, str)) and not value):
                print(f"  ❌ {field}: MISSING или EMPTY")
                all_ok = False
            else:
                # Показываем краткое значение
                if isinstance(value, (int, float)):
                    print(f"  ✅ {field}: {value:,.0f}" if isinstance(value, (int, float)) and value > 100 else f"  ✅ {field}: {value}")
                elif isinstance(value, str):
                    preview = value[:50] + "..." if len(value) > 50 else value
                    print(f"  ✅ {field}: {preview}")
                elif isinstance(value, list):
                    print(f"  ✅ {field}: [{len(value)} items]")
                elif isinstance(value, dict):
                    print(f"  ✅ {field}: {{dict with {len(value)} keys}}")
                else:
                    print(f"  ✅ {field}: {type(value).__name__}")

        if all_ok:
            print(f"\n✅ SUCCESS: Все обязательные поля заполнены")
        else:
            print(f"\n❌ FAILED: Некоторые поля отсутствуют")

        return all_ok

    elif isinstance(data, list):
        if len(data) == 0:
            print(f"❌ FAILED: Список пустой")
            return False
        else:
            print(f"✅ SUCCESS: Список содержит {len(data)} элементов")
            # Проверяем первый элемент
            if required_fields and isinstance(data[0], dict):
                print(f"\n  Проверка первого элемента:")
                for field in required_fields:
                    value = data[0].get(field)
                    if value is None:
                        print(f"    ⚠️  {field}: MISSING")
                    else:
                        print(f"    ✅ {field}: OK")
            return True

    else:
        print(f"✅ SUCCESS: Значение есть ({type(data).__name__})")
        return True


def main():
    """Основной тест пайплайна"""

    # Тестовый URL
    test_url = "https://spb.cian.ru/sale/flat/319271562/"

    print_section("НАЧАЛО ПОЛНОГО ТЕСТИРОВАНИЯ ПАЙПЛАЙНА", "🚀")
    print(f"Тестовый объект: {test_url}")

    # ========================================================================
    # ШАГ 1: ПАРСИНГ ОБЪЕКТА
    # ========================================================================
    print_section("ШАГ 1: Парсинг целевого объекта", "📡")

    parser = PlaywrightParser(region='spb')

    try:
        target_data = parser.parse_property(test_url)

        if not target_data:
            logger.error("❌ Парсинг не удался - нет данных")
            return

        logger.info(f"✅ Объект спарсен успешно")
        logger.info(f"  Цена: {target_data.get('price', 'N/A'):,} ₽")
        logger.info(f"  Площадь: {target_data.get('total_area', 'N/A')} м²")
        logger.info(f"  Комнат: {target_data.get('rooms', 'N/A')}")
        logger.info(f"  Этаж: {target_data.get('floor', 'N/A')}/{target_data.get('total_floors', 'N/A')}")
        logger.info(f"  Адрес: {target_data.get('address', 'N/A')}")
        logger.info(f"  ЖК: {target_data.get('residential_complex', 'N/A')}")

    except Exception as e:
        logger.error(f"❌ Ошибка парсинга: {e}", exc_info=True)
        return

    # ========================================================================
    # ШАГ 2: ПОИСК АНАЛОГОВ
    # ========================================================================
    print_section("ШАГ 2: Поиск аналогов", "🔎")

    try:
        # Пробуем сначала поиск в ЖК
        if target_data.get('residential_complex'):
            logger.info(f"Ищем аналоги в ЖК: {target_data['residential_complex']}")
            comparables = parser.search_similar_in_building(target_data, limit=30)
        else:
            logger.info("ЖК не указан, широкий поиск")
            comparables = parser.search_similar(target_data, limit=30)

        if not comparables:
            logger.error("❌ Аналоги не найдены")
            return

        logger.info(f"✅ Найдено {len(comparables)} аналогов")

        # Показываем статистику по аналогам
        prices = [c.get('price_per_sqm', 0) for c in comparables if c.get('price_per_sqm')]
        if prices:
            import statistics
            logger.info(f"  Медиана цены/м²: {statistics.median(prices):,.0f} ₽")
            logger.info(f"  Мин: {min(prices):,.0f} ₽, Макс: {max(prices):,.0f} ₽")

    except Exception as e:
        logger.error(f"❌ Ошибка поиска аналогов: {e}", exc_info=True)
        return

    # ========================================================================
    # ШАГ 3: СОЗДАНИЕ МОДЕЛЕЙ
    # ========================================================================
    print_section("ШАГ 3: Создание моделей для анализа", "📦")

    try:
        target_property = TargetProperty(**target_data)
        logger.info(f"✅ TargetProperty создан")

        # Конвертируем аналоги в ComparableProperty
        from src.models.property import ComparableProperty
        comparable_objects = []
        for comp_data in comparables:
            try:
                comp = ComparableProperty(**comp_data)
                comparable_objects.append(comp)
            except Exception as e:
                logger.debug(f"Пропускаем невалидный аналог: {e}")

        logger.info(f"✅ Создано {len(comparable_objects)} объектов ComparableProperty")

    except Exception as e:
        logger.error(f"❌ Ошибка создания моделей: {e}", exc_info=True)
        return

    # ========================================================================
    # ШАГ 4: АНАЛИЗ
    # ========================================================================
    print_section("ШАГ 4: Запуск анализа", "🧮")

    try:
        analyzer = RealEstateAnalyzer()

        analysis_request = AnalysisRequest(
            target_property=target_property,
            comparables=comparable_objects
        )

        logger.info("Запускаем анализ...")
        result = analyzer.analyze(analysis_request)

        logger.info(f"✅ Анализ завершен успешно")

    except Exception as e:
        logger.error(f"❌ Ошибка анализа: {e}", exc_info=True)
        return

    # ========================================================================
    # ШАГ 5: ГЕНЕРАЦИЯ ОФФЕРА
    # ========================================================================
    print_section("ШАГ 5: Генерация персонализированного оффера Housler", "🎯")

    try:
        # Конвертируем результат в dict для оффера
        analysis_dict = {
            'fair_price_analysis': result.fair_price_analysis,
            'recommendations': result.recommendations,
            'attractiveness_index': result.attractiveness_index,
            'time_forecast': result.time_forecast,
        }

        target_dict = target_data

        housler_offer = generate_housler_offer(
            analysis=analysis_dict,
            property_info=target_dict,
            recommendations=result.recommendations
        )

        logger.info(f"✅ Оффер Housler сгенерирован")

    except Exception as e:
        logger.error(f"❌ Ошибка генерации оффера: {e}", exc_info=True)
        housler_offer = None

    # ========================================================================
    # ШАГ 6: HEALTH CHECK ВСЕХ БЛОКОВ
    # ========================================================================
    print_section("ШАГ 6: HEALTH CHECK ВСЕХ БЛОКОВ ОТЧЕТА", "🏥")

    results = {}

    # 1. Сводная информация (целевой объект)
    results['target'] = health_check_block(
        "1️⃣  СВОДНАЯ ИНФОРМАЦИЯ (Целевой объект)",
        target_data,
        ['price', 'total_area', 'rooms', 'floor', 'total_floors', 'address']
    )

    # 2. Справедливая цена
    results['fair_price'] = health_check_block(
        "2️⃣  СПРАВЕДЛИВАЯ ЦЕНА",
        result.fair_price_analysis,
        [
            'fair_price_total',
            'fair_price_per_sqm',
            'base_price_per_sqm',
            'final_multiplier',
            'price_diff_percent',
            'is_overpriced',
            'is_underpriced',
            'is_fair'
        ]
    )

    # 3. УВЕРЕННОСТЬ В РАСЧЕТЕ (НОВОЕ!)
    results['confidence'] = health_check_block(
        "3️⃣  ✨ УВЕРЕННОСТЬ В РАСЧЕТЕ (NEW!)",
        result.fair_price_analysis.get('confidence') if isinstance(result.fair_price_analysis, dict) else None,
        [
            'confidence_score',
            'level',
            'reasons',
            'recommendation'
        ]
    )

    # 4. Детальный отчет (НОВОЕ!)
    results['detailed_report'] = health_check_block(
        "4️⃣  ✨ ДЕТАЛЬНЫЙ РАСЧЕТ (NEW!)",
        result.fair_price_analysis.get('detailed_report') if isinstance(result.fair_price_analysis, dict) else None,
        []
    )

    # 5. Рыночная статистика
    results['market_stats'] = health_check_block(
        "5️⃣  РЫНОЧНАЯ СТАТИСТИКА",
        result.market_statistics,
        ['all.count', 'all.median', 'all.mean', 'all.min', 'all.max']
    )

    # 6. Сценарии продажи
    results['scenarios'] = health_check_block(
        "6️⃣  СЦЕНАРИИ ПРОДАЖИ",
        result.price_scenarios,
        ['name', 'start_price', 'expected_final_price', 'time_months']
    )

    # 7. Сильные/слабые стороны
    results['strengths_weaknesses'] = health_check_block(
        "7️⃣  СИЛЬНЫЕ/СЛАБЫЕ СТОРОНЫ",
        result.strengths_weaknesses,
        ['strengths', 'weaknesses']
    )

    # 8. Графики (данные для графиков)
    results['charts'] = health_check_block(
        "8️⃣  ГРАФИКИ",
        {
            'comparison_chart': result.comparison_chart_data,
            'box_plot': result.box_plot_data
        },
        []
    )

    # 9. Персональные рекомендации
    results['recommendations'] = health_check_block(
        "9️⃣  💡 ПЕРСОНАЛЬНЫЕ РЕКОМЕНДАЦИИ",
        result.recommendations,
        ['title', 'message', 'priority']
    )

    # 10. Оффер Housler
    results['housler_offer'] = health_check_block(
        "🔟 КАК HOUSLER ПРОДАСТ ВАШ ОБЪЕКТ",
        housler_offer,
        ['goal', 'actions', 'result', 'price_tier']
    )

    # 11. Индекс привлекательности
    results['attractiveness'] = health_check_block(
        "1️⃣1️⃣  ИНДЕКС ПРИВЛЕКАТЕЛЬНОСТИ",
        result.attractiveness_index,
        ['total_index', 'category']
    )

    # 12. Прогноз времени продажи
    results['time_forecast'] = health_check_block(
        "1️⃣2️⃣  ПРОГНОЗ ВРЕМЕНИ ПРОДАЖИ",
        result.time_forecast,
        ['time_range_description', 'time_category']
    )

    # ========================================================================
    # ИТОГОВЫЙ ОТЧЕТ
    # ========================================================================
    print_section("ИТОГОВЫЙ ОТЧЕТ ПО ТЕСТИРОВАНИЮ", "📊")

    total = len(results)
    passed = sum(1 for v in results.values() if v)
    failed = total - passed

    print(f"\n{'='*60}")
    print(f"Всего блоков проверено: {total}")
    print(f"✅ Успешно: {passed}")
    print(f"❌ Провалено: {failed}")
    print(f"{'='*60}")

    # Детали по блокам
    print("\nДетальная статистика:")
    for block_name, status in results.items():
        emoji = "✅" if status else "❌"
        print(f"  {emoji} {block_name}: {'PASS' if status else 'FAIL'}")

    # Финальный вердикт
    print(f"\n{'='*60}")
    if failed == 0:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! Система готова к деплою в продакшн!")
        print("='*60}")
        return 0
    else:
        print(f"⚠️  ВНИМАНИЕ: {failed} блоков не прошли проверку")
        print(f"{'='*60}")
        return 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code or 0)
    except KeyboardInterrupt:
        print("\n\n⚠️  Тест прерван пользователем")
        sys.exit(130)
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)
