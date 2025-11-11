#!/usr/bin/env python3
"""
Smoke test - быстрая проверка что основные функции работают

Этот тест НЕ требует playwright/pydantic и проверяет:
1. Импорты всех модулей
2. Базовую логику калькулятора
3. Что новые функции не сломали старые
"""

import sys


def test_imports():
    """Проверка что все модули импортируются"""
    print("🔍 Проверка импортов...")

    errors = []

    # Базовые модули которые должны импортироваться
    try:
        from src.analytics import coefficients
        print("  ✅ coefficients")
    except Exception as e:
        errors.append(f"coefficients: {e}")
        print(f"  ❌ coefficients: {e}")

    try:
        from src.analytics import confidence_calculator
        print("  ✅ confidence_calculator")
    except Exception as e:
        errors.append(f"confidence_calculator: {e}")
        print(f"  ❌ confidence_calculator: {e}")

    return len(errors) == 0


def test_coefficients_functions():
    """Проверка что функции коэффициентов работают"""
    print("\n🔍 Проверка функций коэффициентов...")

    try:
        from src.analytics.coefficients import (
            get_floor_coefficient,
            get_area_coefficient,
            get_ceiling_height_coefficient,
        )

        # Тест старых функций
        floor_coef = get_floor_coefficient(5, 10)
        assert 0.8 <= floor_coef <= 1.2, f"Floor coef out of range: {floor_coef}"
        print(f"  ✅ get_floor_coefficient(5, 10) = {floor_coef:.3f}")

        area_coef = get_area_coefficient(100, 80)
        assert 0.8 <= area_coef <= 1.2, f"Area coef out of range: {area_coef}"
        print(f"  ✅ get_area_coefficient(100, 80) = {area_coef:.3f}")

        height_coef = get_ceiling_height_coefficient(3.0)
        assert 0.9 <= height_coef <= 1.2, f"Height coef out of range: {height_coef}"
        print(f"  ✅ get_ceiling_height_coefficient(3.0) = {height_coef:.3f}")

        return True

    except Exception as e:
        print(f"  ❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_confidence_functions():
    """Проверка что функции уверенности работают"""
    print("\n🔍 Проверка функций уверенности...")

    try:
        from src.analytics.confidence_calculator import (
            calculate_confidence,
            generate_summary_report,
        )

        # Минимальные тестовые данные
        test_comparables = [None] * 12  # просто 12 элементов
        test_quality = {
            'cv': 0.085,
            'quality': 'excellent',
            'quality_score': 95
        }
        test_adjustments = {
            'floor': {'type': 'adaptive', 'value': 1.05},
            'area': {'type': 'fixed', 'value': 0.98}
        }

        # Тест расчета уверенности
        confidence = calculate_confidence(
            comparables=test_comparables,
            data_quality=test_quality,
            adjustments=test_adjustments,
            final_multiplier=1.03
        )

        assert 'confidence_score' in confidence, "Missing confidence_score"
        assert 'level' in confidence, "Missing level"
        assert 'reasons' in confidence, "Missing reasons"
        assert 'recommendation' in confidence, "Missing recommendation"

        print(f"  ✅ calculate_confidence() возвращает все поля")
        print(f"     - Score: {confidence['confidence_score']}/100")
        print(f"     - Level: {confidence['level']}")
        print(f"     - Reasons: {len(confidence['reasons'])} факторов")

        # Тест краткого отчета
        summary = generate_summary_report(
            fair_price_result={
                'fair_price_total': 100_000_000,
                'current_price': 110_000_000
            },
            confidence=confidence
        )

        assert isinstance(summary, str), "Summary should be string"
        assert len(summary) > 0, "Summary should not be empty"
        print(f"  ✅ generate_summary_report() работает ({len(summary)} символов)")

        return True

    except Exception as e:
        print(f"  ❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_backward_compatibility():
    """Проверка обратной совместимости - старый код должен работать"""
    print("\n🔍 Проверка обратной совместимости...")

    try:
        # Проверяем что старые функции все еще работают как раньше
        from src.analytics.coefficients import get_floor_coefficient

        # Тест граничных случаев из старого кода
        first_floor = get_floor_coefficient(1, 10)
        assert first_floor < 1.0, "Первый этаж должен иметь скидку"
        print(f"  ✅ Первый этаж работает: {first_floor:.3f}")

        last_floor = get_floor_coefficient(10, 10)
        assert last_floor < 1.0, "Последний этаж должен иметь скидку"
        print(f"  ✅ Последний этаж работает: {last_floor:.3f}")

        middle_floor = get_floor_coefficient(5, 10)
        assert middle_floor >= 0.95, "Средний этаж должен быть близок к 1.0"
        print(f"  ✅ Средний этаж работает: {middle_floor:.3f}")

        return True

    except Exception as e:
        print(f"  ❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Запуск всех smoke тестов"""
    print("="*80)
    print("🚨 SMOKE TEST - Быстрая проверка основной функциональности")
    print("="*80)

    tests = [
        ("Импорты модулей", test_imports),
        ("Функции коэффициентов", test_coefficients_functions),
        ("Функции уверенности", test_confidence_functions),
        ("Обратная совместимость", test_backward_compatibility),
    ]

    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"\n❌ Критическая ошибка в тесте '{test_name}': {e}")
            results[test_name] = False

    # Итоги
    print("\n" + "="*80)
    print("📊 РЕЗУЛЬТАТЫ SMOKE TEST")
    print("="*80)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, status in results.items():
        emoji = "✅" if status else "❌"
        print(f"{emoji} {test_name}")

    print(f"\nИтого: {passed}/{total} тестов пройдено")

    if passed == total:
        print("\n🎉 ВСЕ SMOKE ТЕСТЫ ПРОЙДЕНЫ!")
        print("✅ Основная функциональность работает")
        print("✅ Обратная совместимость сохранена")
        print("✅ Новые функции корректны")
        print("\n💡 Рекомендация: Можно тестировать на staging или локально")
        return 0
    else:
        print(f"\n⚠️ {total - passed} тестов провалено")
        print("❌ НЕ деплоить на прод без исправления!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
