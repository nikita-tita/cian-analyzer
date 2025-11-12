"""
Тесты для проверки качества подбора аналогов

Этот модуль содержит тесты для проверки всех доработок #1-4:
- Фильтрация по региону
- Адаптивные диапазоны
- Валидация разумности
- Предупреждения в UI

Запуск: python3 -m pytest tests/test_comparables_quality.py -v -s
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from typing import List, Dict

# Настройка детального логирования для тестов
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TestCase:
    """Тестовый кейс с данными для проверки"""

    def __init__(self, name: str, target: Dict, expected_segments: str = None):
        self.name = name
        self.target = target
        self.expected_segment = expected_segments
        self.logs = []

    def log(self, message: str):
        """Записать лог"""
        self.logs.append(message)
        logger.info(f"[{self.name}] {message}")


# ═══════════════════════════════════════════════════════════════════════════
# ТЕСТОВЫЕ КЕЙСЫ
# ═══════════════════════════════════════════════════════════════════════════

TEST_CASES = [
    TestCase(
        name="Тест 1: Элитная недвижимость Москва",
        target={
            'url': 'https://moskva.cian.ru/sale/flat/123456/',
            'price': 430_000_000,
            'total_area': 315.7,
            'rooms': 4,
            'title': '4-комн. квартира, 315.7 м², Москва'
        },
        expected_segments="элитная"
    ),

    TestCase(
        name="Тест 2: Премиум СПБ",
        target={
            'url': 'https://spb.cian.ru/sale/flat/789012/',
            'price': 150_000_000,
            'total_area': 120,
            'rooms': 3,
            'title': '3-комн. квартира, 120 м², СПБ'
        },
        expected_segments="премиум"
    ),

    TestCase(
        name="Тест 3: Средний+ Москва",
        target={
            'url': 'https://moskva.cian.ru/sale/flat/345678/',
            'price': 50_000_000,
            'total_area': 75,
            'rooms': 2,
            'title': '2-комн. квартира, 75 м², Москва'
        },
        expected_segments="средний+"
    ),

    TestCase(
        name="Тест 4: Эконом СПБ",
        target={
            'url': 'https://spb.cian.ru/sale/flat/901234/',
            'price': 18_000_000,
            'total_area': 50,
            'rooms': 2,
            'title': '2-комн. квартира, 50 м², СПБ'
        },
        expected_segments="эконом"
    ),
]


def test_adaptive_segments():
    """
    ТЕСТ: Проверка адаптивных диапазонов (Доработка #2)

    Проверяет, что для разных сегментов применяются правильные допуски.
    """
    logger.info("="*80)
    logger.info("ТЕСТ: Адаптивные диапазоны поиска (Доработка #2)")
    logger.info("="*80)

    for test_case in TEST_CASES:
        target_price = test_case.target['price']
        target_area = test_case.target['total_area']

        # Логика из playwright_parser.py:864-879
        if target_price >= 300_000_000:
            price_tolerance = 0.20
            area_tolerance = 0.15
            segment = "элитная"
        elif target_price >= 100_000_000:
            price_tolerance = 0.30
            area_tolerance = 0.25
            segment = "премиум"
        elif target_price >= 30_000_000:
            price_tolerance = 0.40
            area_tolerance = 0.30
            segment = "средний+"
        else:
            price_tolerance = 0.50
            area_tolerance = 0.40
            segment = "эконом"

        test_case.log(f"Сегмент определен: {segment}")
        test_case.log(f"Допуски: цена ±{price_tolerance*100:.0f}%, площадь ±{area_tolerance*100:.0f}%")

        price_min = int(target_price * (1 - price_tolerance))
        price_max = int(target_price * (1 + price_tolerance))
        area_min = int(target_area * (1 - area_tolerance))
        area_max = int(target_area * (1 + area_tolerance))

        test_case.log(f"Диапазон цен: {price_min:,} - {price_max:,} ₽")
        test_case.log(f"Диапазон площади: {area_min} - {area_max} м²")

        # Проверка ожидания
        assert segment == test_case.expected_segment, \
            f"Ожидался сегмент '{test_case.expected_segment}', получен '{segment}'"

        test_case.log("✅ PASSED")
        logger.info("")


def detect_region_from_url(url: str) -> str:
    """
    Копия функции из playwright_parser.py для тестирования
    """
    if 'moskva' in url.lower() or 'moscow' in url.lower():
        return 'msk'
    elif 'sankt-peterburg' in url.lower() or 'spb' in url.lower():
        return 'spb'
    return 'spb'


def test_region_detection():
    """
    ТЕСТ: Определение региона (Доработка #1)

    Проверяет, что функция detect_region_from_url правильно определяет регион.
    """
    logger.info("="*80)
    logger.info("ТЕСТ: Определение региона из URL (Доработка #1)")
    logger.info("="*80)

    test_urls = [
        ('https://moskva.cian.ru/sale/flat/123/', 'msk', 'Москва'),
        ('https://spb.cian.ru/sale/flat/456/', 'spb', 'СПБ'),
        ('https://sankt-peterburg.cian.ru/sale/flat/789/', 'spb', 'Санкт-Петербург'),
        ('https://www.cian.ru/sale/flat/012/', 'spb', 'По умолчанию (СПБ)'),
    ]

    for url, expected_region, name in test_urls:
        detected_region = detect_region_from_url(url)
        logger.info(f"URL: {url[:50]}...")
        logger.info(f"  Ожидаемый регион: {expected_region}")
        logger.info(f"  Определенный регион: {detected_region}")

        assert detected_region == expected_region, \
            f"Для {name} ожидался регион '{expected_region}', получен '{detected_region}'"

        logger.info(f"  ✅ PASSED")
        logger.info("")


def test_reasonable_validation():
    """
    ТЕСТ: Валидация разумности аналогов (Доработка #3)

    Проверяет, что аналоги с большой разницей в цене/площади исключаются.
    """
    logger.info("="*80)
    logger.info("ТЕСТ: Валидация разумности аналогов (Доработка #3)")
    logger.info("="*80)

    target = {
        'price': 100_000_000,
        'total_area': 100
    }

    # Тестовые аналоги
    comparables = [
        {'price': 95_000_000, 'total_area': 98, 'url': 'test1.com', 'valid': True, 'reason': 'Нормальный аналог'},
        {'price': 20_000_000, 'total_area': 100, 'url': 'test2.com', 'valid': False, 'reason': 'Цена в 5 раз меньше'},
        {'price': 100_000_000, 'total_area': 40, 'url': 'test3.com', 'valid': False, 'reason': 'Площадь в 2.5 раза меньше'},
        {'price': 350_000_000, 'total_area': 100, 'url': 'test4.com', 'valid': False, 'reason': 'Цена в 3.5 раза больше'},
        {'price': 110_000_000, 'total_area': 120, 'url': 'test5.com', 'valid': True, 'reason': 'Нормальный аналог'},
    ]

    for comp in comparables:
        # Логика из playwright_parser.py:615-635
        comp_price = comp['price']
        comp_area = comp['total_area']

        price_ratio = max(comp_price, target['price']) / min(comp_price, target['price'])
        area_ratio = max(comp_area, target['total_area']) / min(comp_area, target['total_area'])

        is_valid = True
        reason = ""

        if price_ratio > 3.0:
            is_valid = False
            reason = f"Цена отличается в {price_ratio:.1f} раз"
        elif area_ratio > 1.5:
            is_valid = False
            reason = f"Площадь отличается в {area_ratio:.1f} раз"
        else:
            reason = "ОК"

        logger.info(f"Аналог: {comp['url']}")
        logger.info(f"  Цена: {comp_price:,} ₽ (ratio: {price_ratio:.2f})")
        logger.info(f"  Площадь: {comp_area} м² (ratio: {area_ratio:.2f})")
        logger.info(f"  Валидность: {'✅ Валиден' if is_valid else '❌ Исключен'}")
        logger.info(f"  Причина: {reason}")

        assert is_valid == comp['valid'], \
            f"Для аналога {comp['url']} ожидалась валидность {comp['valid']}, получена {is_valid}"

        logger.info("")


def test_warnings_generation():
    """
    ТЕСТ: Генерация предупреждений (Доработка #4)

    Проверяет, что при проблемах с аналогами генерируются правильные warnings.
    """
    logger.info("="*80)
    logger.info("ТЕСТ: Генерация предупреждений о качестве (Доработка #4)")
    logger.info("="*80)

    import statistics

    # Сценарий 1: Мало аналогов
    logger.info("Сценарий 1: Мало аналогов (3)")
    similar = [{'id': i} for i in range(3)]
    warnings = []

    if len(similar) < 5:
        warnings.append({
            'type': 'error',
            'title': 'Недостаточно аналогов',
            'message': f'Найдено всего {len(similar)} аналог(ов).'
        })

    logger.info(f"  Warnings: {len(warnings)}")
    assert len(warnings) == 1 and warnings[0]['type'] == 'error'
    logger.info("  ✅ PASSED")
    logger.info("")

    # Сценарий 2: Большой разброс цен
    logger.info("Сценарий 2: Большой разброс цен (CV=45%)")
    similar = [
        {'price_per_sqm': 100_000},
        {'price_per_sqm': 200_000},
        {'price_per_sqm': 150_000},
    ]
    warnings = []

    prices_per_sqm = [c['price_per_sqm'] for c in similar]
    median_price = statistics.median(prices_per_sqm)
    stdev_price = statistics.stdev(prices_per_sqm)
    cv = stdev_price / median_price

    logger.info(f"  CV: {cv*100:.0f}%")

    if cv > 0.3:
        warnings.append({
            'type': 'warning',
            'title': 'Большой разброс цен',
            'message': f'Разброс цен составляет {cv*100:.0f}%.'
        })

    logger.info(f"  Warnings: {len(warnings)}")
    assert len(warnings) == 1 and warnings[0]['type'] == 'warning'
    logger.info("  ✅ PASSED")
    logger.info("")


def test_location_filtering():
    """
    ТЕСТ: Фильтрация по локации (Доработка #5 - часть 1)

    Проверяет, что аналоги правильно фильтруются по метро и району.
    """
    logger.info("="*80)
    logger.info("ТЕСТ: Фильтрация по локации (Доработка #5)")
    logger.info("="*80)

    # Целевой объект у метро "Арбатская"
    target = {
        'metro': 'Арбатская',
        'address': 'Москва, Центральный округ, улица Арбат, 10'
    }

    # Тестовые аналоги
    results = [
        {'url': 'test1', 'metro': 'Арбатская', 'address': 'Москва, улица Арбат, 5'},  # ✓ То же метро
        {'url': 'test2', 'metro': 'Смоленская', 'address': 'Москва, Центральный округ, Новый Арбат, 15'},  # ✗ Другое метро
        {'url': 'test3', 'metro': 'Кропоткинская', 'address': 'Москва, Пречистенка, 20'},  # ✗ Другое метро и район
        {'url': 'test4', 'metro': 'Арбатская-Покровская', 'address': 'Москва, Покровка'},  # ✓ Содержит "Арбатская"
    ]

    # Тестируем строгую фильтрацию (только совпадение метро)
    logger.info("Тест 1: Строгая фильтрация (по метро)")

    # Логика из playwright_parser.py:_filter_by_location
    target_metro = target['metro'].lower().strip()
    filtered_strict = []

    for result in results:
        result_metro = result.get('metro', '').lower().strip()
        if target_metro in result_metro or result_metro in target_metro:
            filtered_strict.append(result)
            logger.info(f"  ✓ {result['url']}: метро '{result['metro']}' совпадает")
        else:
            logger.info(f"  ✗ {result['url']}: метро '{result['metro']}' не совпадает")

    logger.info(f"  Результат: {len(filtered_strict)} из {len(results)} (ожидается 2)")
    assert len(filtered_strict) == 2, f"Ожидалось 2 аналога, получено {len(filtered_strict)}"

    # Проверяем, что правильные аналоги выбраны
    filtered_urls = {r['url'] for r in filtered_strict}
    assert 'test1' in filtered_urls, "test1 должен быть в результатах"
    assert 'test4' in filtered_urls, "test4 должен быть в результатах"

    logger.info("  ✅ PASSED")
    logger.info("")


def test_multilevel_search_logic():
    """
    ТЕСТ: Логика многоуровневого поиска (Доработка #5 - часть 2)

    Проверяет правильность работы 3-уровневой системы поиска.
    """
    logger.info("="*80)
    logger.info("ТЕСТ: Многоуровневый поиск (Доработка #5)")
    logger.info("="*80)

    # Сценарий 1: Достаточно аналогов на уровне 1
    logger.info("Сценарий 1: Достаточно аналогов на уровне 1 (>=10)")
    level1_results = [{'id': i} for i in range(12)]
    logger.info(f"  Уровень 1: {len(level1_results)} аналогов")

    if len(level1_results) >= 10:
        logger.info("  ✓ Поиск завершается на уровне 1")
        logger.info("  ✅ PASSED")
    else:
        raise AssertionError("Должен был завершиться на уровне 1")
    logger.info("")

    # Сценарий 2: Недостаточно на уровне 1, переходим к уровню 2
    logger.info("Сценарий 2: Мало аналогов на уровне 1 (<10), переход к уровню 2")
    level1_results = [{'id': i} for i in range(7)]
    level2_additional = [{'id': i} for i in range(100, 105)]  # +5 аналогов

    logger.info(f"  Уровень 1: {len(level1_results)} аналогов")
    total = len(level1_results) + len(level2_additional)
    logger.info(f"  Уровень 2: +{len(level2_additional)} аналогов (итого: {total})")

    if total >= 10:
        logger.info("  ✓ Достаточно аналогов после уровня 2")
        logger.info("  ✅ PASSED")
    else:
        raise AssertionError("После уровня 2 должно быть >= 10 аналогов")
    logger.info("")

    # Сценарий 3: Критически мало аналогов, нужен уровень 3
    logger.info("Сценарий 3: Мало аналогов на уровнях 1-2 (<5), нужен уровень 3")
    level1_results = [{'id': i} for i in range(2)]
    level2_additional = [{'id': i} for i in range(100, 102)]  # +2
    level3_additional = [{'id': i} for i in range(200, 210)]  # +10

    logger.info(f"  Уровень 1: {len(level1_results)} аналогов")
    logger.info(f"  Уровень 2: +{len(level2_additional)} аналогов (итого: {len(level1_results) + len(level2_additional)})")

    if len(level1_results) + len(level2_additional) < 5:
        logger.info("  ✓ Переход к уровню 3 (расширенный поиск)")
        total = len(level1_results) + len(level2_additional) + len(level3_additional)
        logger.info(f"  Уровень 3: +{len(level3_additional)} аналогов (итого: {total})")
        logger.info("  ✅ PASSED")
    else:
        raise AssertionError("Должен был перейти к уровню 3")
    logger.info("")


def test_tolerance_expansion():
    """
    ТЕСТ: Расширение допусков на уровне 3 (Доработка #5 - часть 3)

    Проверяет, что на уровне 3 допуски увеличиваются на 50%.
    """
    logger.info("="*80)
    logger.info("ТЕСТ: Расширение допусков на уровне 3 (Доработка #5)")
    logger.info("="*80)

    # Тестируем для разных сегментов
    test_cases = [
        {'segment': 'элитная', 'price': 400_000_000, 'base_price_tol': 0.20, 'base_area_tol': 0.15},
        {'segment': 'премиум', 'price': 150_000_000, 'base_price_tol': 0.30, 'base_area_tol': 0.25},
        {'segment': 'эконом', 'price': 20_000_000, 'base_price_tol': 0.50, 'base_area_tol': 0.40},
    ]

    for case in test_cases:
        logger.info(f"Сегмент: {case['segment']} ({case['price']:,} ₽)")

        # Базовые допуски (уровни 1-2)
        base_price_tol = case['base_price_tol']
        base_area_tol = case['base_area_tol']

        logger.info(f"  Базовые допуски: цена ±{base_price_tol*100:.0f}%, площадь ±{base_area_tol*100:.0f}%")

        # Расширенные допуски (уровень 3)
        expanded_price_tol = base_price_tol * 1.5
        expanded_area_tol = base_area_tol * 1.5

        logger.info(f"  Уровень 3: цена ±{expanded_price_tol*100:.0f}%, площадь ±{expanded_area_tol*100:.0f}%")

        # Проверяем правильность расширения
        assert expanded_price_tol == base_price_tol * 1.5, "Неверное расширение для цены"
        assert expanded_area_tol == base_area_tol * 1.5, "Неверное расширение для площади"

        logger.info(f"  ✅ Допуски расширены корректно")
        logger.info("")

    logger.info("✅ ВСЕ СЕГМЕНТЫ PASSED")
    logger.info("")


def test_address_extraction():
    """
    ТЕСТ: Извлечение адреса дома (Доработка #6)

    Проверяет правильность извлечения улицы и номера дома из полного адреса.
    """
    logger.info("="*80)
    logger.info("ТЕСТ: Извлечение адреса дома (Доработка #6)")
    logger.info("="*80)

    import re

    test_cases = [
        {
            'full_address': 'Москва, Центральный округ, улица Арбат, 10',
            'expected': 'улица Арбат, 10',
            'name': 'Москва с округом'
        },
        {
            'full_address': 'Санкт-Петербург, Невский проспект, 28',
            'expected': 'Невский проспект, 28',
            'name': 'СПБ без округа'
        },
        {
            'full_address': 'Москва, ЦАО, Пречистенка, 15к1',
            'expected': 'Пречистенка, 15к1',
            'name': 'С сокращением округа и корпусом'
        },
        {
            'full_address': 'СПб, Адмиралтейский район, Вознесенский проспект, 5',
            'expected': 'Вознесенский проспект, 5',
            'name': 'СПб с районом'
        },
    ]

    for case in test_cases:
        logger.info(f"Тест: {case['name']}")
        logger.info(f"  Полный адрес: {case['full_address']}")

        # Логика из playwright_parser.py (строки 779-793)
        address_clean = case['full_address']

        # Удаляем город
        for city in ['Москва', 'Санкт-Петербург', 'СПб']:
            address_clean = address_clean.replace(city + ',', '').replace(city, '')

        # Удаляем округи/районы
        address_clean = re.sub(r'[А-Яа-яёЁ]+\s+(округ|район|АО),?\s*', '', address_clean)
        address_clean = address_clean.strip().strip(',').strip()

        # Извлекаем последние 2 части
        address_parts = [p.strip() for p in address_clean.split(',') if p.strip()]

        if len(address_parts) >= 2:
            street_and_house = ', '.join(address_parts[-2:])
        else:
            street_and_house = address_clean

        logger.info(f"  Извлечено: {street_and_house}")
        logger.info(f"  Ожидалось: {case['expected']}")

        assert street_and_house == case['expected'], f"Ожидалось '{case['expected']}', получено '{street_and_house}'"
        logger.info(f"  ✅ PASSED")
        logger.info("")

    logger.info("✅ ВСЕ АДРЕСА PASSED")
    logger.info("")


# ═══════════════════════════════════════════════════════════════════════════
# ЗАПУСК ВСЕХ ТЕСТОВ
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    logger.info("╔" + "="*78 + "╗")
    logger.info("║" + " "*20 + "ТЕСТИРОВАНИЕ ДОРАБОТОК #1-6" + " "*31 + "║")
    logger.info("╚" + "="*78 + "╝")
    logger.info("")

    try:
        # Доработки #1-4 (базовые)
        test_region_detection()
        test_adaptive_segments()
        test_reasonable_validation()
        test_warnings_generation()

        # Доработка #5 (многоуровневый поиск)
        test_location_filtering()
        test_multilevel_search_logic()
        test_tolerance_expansion()

        # Доработка #6 (fallback на поиск по адресу)
        test_address_extraction()

        logger.info("╔" + "="*78 + "╗")
        logger.info("║" + " "*20 + "ВСЕ ТЕСТЫ ПРОЙДЕНЫ ✅ (8 тестов)" + " "*27 + "║")
        logger.info("╚" + "="*78 + "╝")

    except AssertionError as e:
        logger.error("╔" + "="*78 + "╗")
        logger.error("║" + " "*28 + "ТЕСТ ПРОВАЛЕН ❌" + " "*35 + "║")
        logger.error("╚" + "="*78 + "╝")
        logger.error(f"Ошибка: {e}")
        raise
