#!/usr/bin/env python3
"""
Проверка здоровья всех модулей системы (без реального парсинга)

Этот тест проверяет:
1. Импорты всех модулей
2. Наличие всех функций
3. Структуру возвращаемых данных
"""

import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def print_section(title: str):
    """Печать разделителя"""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)


def test_imports():
    """Тест 1: Проверка импортов всех модулей"""
    print_section("ТЕСТ 1: Импорт модулей")

    modules_to_test = {
        'Модели данных': [
            'src.models.property',
        ],
        'Парсеры': [
            'src.parsers.base_parser',
        ],
        'Аналитика - Валидация (Phase 1)': [
            'src.analytics.data_validator',
        ],
        'Аналитика - Статистика (Phase 2)': [
            'src.analytics.statistical_analysis',
        ],
        'Аналитика - Коэффициенты (Phase 3)': [
            'src.analytics.coefficients',
        ],
        'Аналитика - Уверенность (Phase 4)': [
            'src.analytics.confidence_calculator',
        ],
        'Аналитика - Расчеты': [
            'src.analytics.fair_price_calculator',
            'src.analytics.analyzer',
            'src.analytics.offer_generator',
        ],
    }

    results = {}
    for category, modules in modules_to_test.items():
        print(f"\n📦 {category}:")
        for module_name in modules:
            try:
                __import__(module_name)
                print(f"  ✅ {module_name}")
                results[module_name] = True
            except ImportError as e:
                print(f"  ❌ {module_name}: {e}")
                results[module_name] = False
            except Exception as e:
                print(f"  ⚠️  {module_name}: Неожиданная ошибка - {e}")
                results[module_name] = False

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    print(f"\n{'='*60}")
    print(f"Импорты: {passed}/{total} успешно")
    print(f"{'='*60}")

    return all(results.values())


def test_phase1_validator():
    """Тест 2: Валидация данных (Phase 1)"""
    print_section("ТЕСТ 2: Phase 1 - Валидация данных")

    try:
        from src.analytics.data_validator import (
            validate_comparable,
            filter_valid_comparables,
            get_validation_summary,
            check_minimum_comparables
        )
        from src.models.property import ComparableProperty

        # Тестовый аналог
        test_comp = ComparableProperty(
            url="https://test.com/1",
            price=100_000_000,
            total_area=100.0,
            price_per_sqm=1_000_000,
            floor=5,
            total_floors=10,
            rooms=3
        )

        # Проверка валидации
        is_valid, details = validate_comparable(test_comp)

        print(f"  ✅ validate_comparable: работает")
        print(f"     - Результат: valid={is_valid}, completeness={details.get('completeness', 0):.0f}%")

        # Проверка фильтрации
        valid, excluded = filter_valid_comparables([test_comp], verbose=False)
        print(f"  ✅ filter_valid_comparables: работает ({len(valid)} valid, {len(excluded)} excluded)")

        # Проверка summary
        summary = get_validation_summary([test_comp])
        print(f"  ✅ get_validation_summary: работает ({summary['valid']}/{summary['total']} valid)")

        # Проверка минимума
        result = check_minimum_comparables([test_comp] * 10, minimum=5, raise_error=False)
        print(f"  ✅ check_minimum_comparables: работает (result={result})")

        print(f"\n✅ Phase 1 (Валидация): ВСЕ ФУНКЦИИ РАБОТАЮТ")
        return True

    except Exception as e:
        print(f"\n❌ Phase 1 (Валидация): ОШИБКА - {e}")
        import traceback
        traceback.print_exc()
        return False


def test_phase2_statistics():
    """Тест 3: Статистический анализ (Phase 2)"""
    print_section("ТЕСТ 3: Phase 2 - Статистический анализ")

    try:
        from src.analytics.statistical_analysis import (
            detect_outliers_iqr,
            calculate_data_quality,
            check_data_sufficiency
        )
        from src.models.property import ComparableProperty

        # Создаем тестовый набор
        test_comps = [
            ComparableProperty(
                url=f"https://test.com/{i}",
                price=100_000_000 + i * 1_000_000,
                total_area=100.0,
                price_per_sqm=1_000_000 + i * 10_000
            )
            for i in range(15)
        ]

        # IQR фильтрация
        valid, outliers = detect_outliers_iqr(test_comps)
        print(f"  ✅ detect_outliers_iqr: работает ({len(valid)} valid, {len(outliers)} outliers)")

        # Качество данных
        quality = calculate_data_quality(test_comps)
        print(f"  ✅ calculate_data_quality: работает")
        print(f"     - CV: {quality['cv']:.1%}")
        print(f"     - Quality: {quality['quality']}")
        print(f"     - Quality score: {quality['quality_score']}/100")

        # Достаточность данных
        is_sufficient, reason = check_data_sufficiency(test_comps)
        print(f"  ✅ check_data_sufficiency: работает (sufficient={is_sufficient})")

        print(f"\n✅ Phase 2 (Статистика): ВСЕ ФУНКЦИИ РАБОТАЮТ")
        return True

    except Exception as e:
        print(f"\n❌ Phase 2 (Статистика): ОШИБКА - {e}")
        import traceback
        traceback.print_exc()
        return False


def test_phase3_adaptive_coefficients():
    """Тест 4: Адаптивные коэффициенты (Phase 3)"""
    print_section("ТЕСТ 4: Phase 3 - Адаптивные коэффициенты")

    try:
        from src.analytics.coefficients import (
            calculate_floor_coefficient_adaptive,
            calculate_area_coefficient_adaptive
        )
        from src.models.property import ComparableProperty

        # Тестовые аналоги
        test_comps = [
            ComparableProperty(
                url=f"https://test.com/{i}",
                price=100_000_000,
                total_area=100.0 + i * 5,
                price_per_sqm=1_000_000 + i * 10_000,
                floor=i + 1,
                total_floors=10
            )
            for i in range(10)
        ]

        # Адаптивный коэффициент этажа
        floor_coef, floor_explanation = calculate_floor_coefficient_adaptive(
            target_floor=8,
            target_total_floors=10,
            comparables=test_comps
        )
        print(f"  ✅ calculate_floor_coefficient_adaptive: работает")
        print(f"     - Coefficient: {floor_coef:.3f}")
        print(f"     - Type: {floor_explanation.get('type', 'N/A')}")

        # Адаптивный коэффициент площади
        area_coef, area_explanation = calculate_area_coefficient_adaptive(
            target_area=120.0,
            comparables=test_comps
        )
        print(f"  ✅ calculate_area_coefficient_adaptive: работает")
        print(f"     - Coefficient: {area_coef:.3f}")
        print(f"     - Type: {area_explanation.get('type', 'N/A')}")

        print(f"\n✅ Phase 3 (Адаптивные коэффициенты): ВСЕ ФУНКЦИИ РАБОТАЮТ")
        return True

    except Exception as e:
        print(f"\n❌ Phase 3 (Адаптивные коэффициенты): ОШИБКА - {e}")
        import traceback
        traceback.print_exc()
        return False


def test_phase4_confidence():
    """Тест 5: Расчет уверенности (Phase 4)"""
    print_section("ТЕСТ 5: Phase 4 - Расчет уверенности")

    try:
        from src.analytics.confidence_calculator import (
            calculate_confidence,
            generate_detailed_report,
            generate_summary_report
        )
        from src.models.property import ComparableProperty, TargetProperty

        # Тестовые данные
        test_comps = [
            ComparableProperty(
                url=f"https://test.com/{i}",
                price=100_000_000,
                total_area=100.0,
                price_per_sqm=1_000_000
            )
            for i in range(12)
        ]

        test_target = TargetProperty(
            url="https://test.com/target",
            price=110_000_000,
            total_area=100.0,
            rooms=3
        )

        data_quality = {
            'cv': 0.085,
            'quality': 'excellent',
            'quality_score': 95
        }

        adjustments = {
            'floor': {'type': 'adaptive', 'value': 1.05, 'description': 'Этаж'},
            'area': {'type': 'fixed', 'value': 0.98, 'description': 'Площадь'}
        }

        # Расчет уверенности
        confidence = calculate_confidence(
            comparables=test_comps,
            data_quality=data_quality,
            adjustments=adjustments,
            final_multiplier=1.03
        )

        print(f"  ✅ calculate_confidence: работает")
        print(f"     - Score: {confidence['confidence_score']}/100")
        print(f"     - Level: {confidence['level']}")
        print(f"     - Reasons: {len(confidence['reasons'])} факторов")

        # Детальный отчет
        fair_price_result = {
            'base_price_per_sqm': 1_000_000,
            'final_multiplier': 1.03,
            'fair_price_per_sqm': 1_030_000,
            'fair_price_total': 103_000_000,
            'current_price': 110_000_000,
            'adjustments': adjustments,
            'data_quality': data_quality
        }

        detailed_report = generate_detailed_report(
            target=test_target,
            comparables=test_comps,
            fair_price_result=fair_price_result,
            confidence=confidence
        )

        print(f"  ✅ generate_detailed_report: работает ({len(detailed_report)} символов)")

        # Краткий отчет
        summary_report = generate_summary_report(
            fair_price_result=fair_price_result,
            confidence=confidence
        )

        print(f"  ✅ generate_summary_report: работает")
        print(f"     - Summary: {summary_report[:80]}...")

        print(f"\n✅ Phase 4 (Уверенность): ВСЕ ФУНКЦИИ РАБОТАЮТ")
        return True

    except Exception as e:
        print(f"\n❌ Phase 4 (Уверенность): ОШИБКА - {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Главная функция тестирования"""

    print_section("🚀 ПРОВЕРКА ЗДОРОВЬЯ СИСТЕМЫ")
    print("Тестируем все модули без реального парсинга\n")

    tests = [
        ("Импорт модулей", test_imports),
        ("Phase 1: Валидация", test_phase1_validator),
        ("Phase 2: Статистика", test_phase2_statistics),
        ("Phase 3: Адаптивные коэффициенты", test_phase3_adaptive_coefficients),
        ("Phase 4: Уверенность", test_phase4_confidence),
    ]

    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            logger.error(f"Критическая ошибка в тесте '{test_name}': {e}")
            results[test_name] = False

    # Итоги
    print_section("📊 ИТОГОВЫЙ ОТЧЕТ")

    total = len(results)
    passed = sum(1 for v in results.values() if v)
    failed = total - passed

    print(f"\nВсего тестов: {total}")
    print(f"✅ Успешно: {passed}")
    print(f"❌ Провалено: {failed}\n")

    for test_name, status in results.items():
        emoji = "✅" if status else "❌"
        print(f"  {emoji} {test_name}")

    print(f"\n{'='*80}")

    if failed == 0:
        print("🎉 ВСЕ МОДУЛИ РАБОТАЮТ КОРРЕКТНО!")
        print("✅ Система готова к тестированию с реальными данными")
        print("='*80}\n")
        return 0
    else:
        print(f"⚠️  ВНИМАНИЕ: {failed} тестов провалено")
        print(f"{'='*80}\n")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Тестирование прервано")
        sys.exit(130)
