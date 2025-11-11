"""
Тесты для модуля валидации данных (data_validator.py)

pytest tests/test_data_validator.py -v
"""

import pytest
from src.models.property import ComparableProperty
from src.analytics.data_validator import (
    validate_comparable,
    filter_valid_comparables,
    get_validation_summary,
    check_minimum_comparables
)


# ═══════════════════════════════════════════════════════════════════════════
# ФИКСТУРЫ
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def valid_comparable():
    """Валидный аналог с полными данными"""
    return ComparableProperty(
        url="https://www.cian.ru/sale/flat/123456/",
        price=100_000_000,
        total_area=100.0,
        price_per_sqm=1_000_000,
        floor=5,
        total_floors=10,
        rooms=3,
        build_year=2020,
        object_status="готов"
    )


@pytest.fixture
def invalid_comparable_no_price():
    """Невалидный - нет цены"""
    return ComparableProperty(
        url="https://www.cian.ru/sale/flat/999999/",
        price=None,
        total_area=100.0,
        price_per_sqm=None
    )


@pytest.fixture
def invalid_comparable_bad_price():
    """Невалидный - цена за м² вне пределов"""
    return ComparableProperty(
        url="https://www.cian.ru/sale/flat/888888/",
        price=1_000_000_000,  # 1 млрд
        total_area=100.0,
        price_per_sqm=10_000_000  # 10 млн за м² - нереалистично
    )


@pytest.fixture
def invalid_comparable_bad_status():
    """Невалидный - статус 'проект'"""
    return ComparableProperty(
        url="https://www.cian.ru/sale/flat/777777/",
        price=100_000_000,
        total_area=100.0,
        price_per_sqm=1_000_000,
        object_status="проект"  # Недопустимый статус
    )


@pytest.fixture
def comparable_minimal():
    """Валидный с минимальными данными"""
    return ComparableProperty(
        url="https://www.cian.ru/sale/flat/555555/",
        price=50_000_000,
        total_area=50.0,
        price_per_sqm=1_000_000
    )


# ═══════════════════════════════════════════════════════════════════════════
# ТЕСТЫ: validate_comparable()
# ═══════════════════════════════════════════════════════════════════════════

def test_validate_comparable_valid(valid_comparable):
    """Тест: валидный аналог проходит проверку"""
    is_valid, details = validate_comparable(valid_comparable)

    assert is_valid is True
    assert details['is_valid'] is True
    assert len(details['failures']) == 0
    assert details['completeness'] > 0  # Должна быть полнота данных


def test_validate_comparable_no_price(invalid_comparable_no_price):
    """Тест: аналог без цены не проходит проверку"""
    is_valid, details = validate_comparable(invalid_comparable_no_price)

    assert is_valid is False
    assert 'Отсутствует цена' in details['failures']


def test_validate_comparable_bad_price(invalid_comparable_bad_price):
    """Тест: аналог с нереалистичной ценой не проходит"""
    is_valid, details = validate_comparable(invalid_comparable_bad_price)

    assert is_valid is False
    assert any('Цена/м² вне пределов' in f for f in details['failures'])


def test_validate_comparable_bad_status(invalid_comparable_bad_status):
    """Тест: аналог со статусом 'проект' не проходит"""
    is_valid, details = validate_comparable(invalid_comparable_bad_status)

    assert is_valid is False
    assert any('статус' in f.lower() for f in details['failures'])


def test_validate_comparable_minimal(comparable_minimal):
    """Тест: аналог с минимальными данными валиден"""
    is_valid, details = validate_comparable(comparable_minimal)

    assert is_valid is True
    # Но полнота данных должна быть низкая
    assert details['completeness'] < 50  # Нет этажа, года и т.д.


# ═══════════════════════════════════════════════════════════════════════════
# ТЕСТЫ: filter_valid_comparables()
# ═══════════════════════════════════════════════════════════════════════════

def test_filter_valid_comparables_all_valid(valid_comparable):
    """Тест: все валидные аналоги остаются"""
    comparables = [valid_comparable] * 5

    valid, excluded = filter_valid_comparables(comparables, verbose=False)

    assert len(valid) == 5
    assert len(excluded) == 0


def test_filter_valid_comparables_mixed(
    valid_comparable,
    invalid_comparable_no_price,
    invalid_comparable_bad_price,
    invalid_comparable_bad_status
):
    """Тест: смешанный список - фильтруются невалидные"""
    comparables = [
        valid_comparable,
        invalid_comparable_no_price,
        valid_comparable,
        invalid_comparable_bad_price,
        valid_comparable,
        invalid_comparable_bad_status
    ]

    valid, excluded = filter_valid_comparables(comparables, verbose=False)

    assert len(valid) == 3  # Только 3 валидных
    assert len(excluded) == 3  # 3 исключены


def test_filter_valid_comparables_all_invalid(invalid_comparable_no_price):
    """Тест: все невалидные - пустой результат"""
    comparables = [invalid_comparable_no_price] * 3

    valid, excluded = filter_valid_comparables(comparables, verbose=False)

    assert len(valid) == 0
    assert len(excluded) == 3


def test_filter_valid_comparables_empty():
    """Тест: пустой список - пустой результат"""
    valid, excluded = filter_valid_comparables([], verbose=False)

    assert len(valid) == 0
    assert len(excluded) == 0


# ═══════════════════════════════════════════════════════════════════════════
# ТЕСТЫ: get_validation_summary()
# ═══════════════════════════════════════════════════════════════════════════

def test_get_validation_summary_all_valid(valid_comparable):
    """Тест: сводка для всех валидных"""
    comparables = [valid_comparable] * 10

    summary = get_validation_summary(comparables)

    assert summary['total'] == 10
    assert summary['valid'] == 10
    assert summary['invalid'] == 0
    assert summary['valid_percentage'] == 100.0


def test_get_validation_summary_mixed(
    valid_comparable,
    invalid_comparable_no_price
):
    """Тест: сводка для смешанного списка"""
    comparables = [valid_comparable] * 7 + [invalid_comparable_no_price] * 3

    summary = get_validation_summary(comparables)

    assert summary['total'] == 10
    assert summary['valid'] == 7
    assert summary['invalid'] == 3
    assert summary['valid_percentage'] == 70.0
    assert 'Отсутствует цена' in summary['issues']
    assert summary['issues']['Отсутствует цена'] == 3


def test_get_validation_summary_empty():
    """Тест: сводка для пустого списка"""
    summary = get_validation_summary([])

    assert summary['total'] == 0
    assert summary['valid'] == 0
    assert summary['invalid'] == 0
    assert summary['valid_percentage'] == 0.0


# ═══════════════════════════════════════════════════════════════════════════
# ТЕСТЫ: check_minimum_comparables()
# ═══════════════════════════════════════════════════════════════════════════

def test_check_minimum_comparables_enough(valid_comparable):
    """Тест: достаточно аналогов"""
    comparables = [valid_comparable] * 10

    result = check_minimum_comparables(comparables, minimum=5, raise_error=False)

    assert result is True


def test_check_minimum_comparables_not_enough(valid_comparable):
    """Тест: недостаточно аналогов - без ошибки"""
    comparables = [valid_comparable] * 3

    result = check_minimum_comparables(comparables, minimum=5, raise_error=False)

    assert result is False


def test_check_minimum_comparables_raises_error(valid_comparable):
    """Тест: недостаточно аналогов - выброс ошибки"""
    comparables = [valid_comparable] * 3

    with pytest.raises(ValueError) as exc_info:
        check_minimum_comparables(comparables, minimum=5, raise_error=True)

    assert "Недостаточно аналогов" in str(exc_info.value)


# ═══════════════════════════════════════════════════════════════════════════
# ТЕСТЫ: ГРАНИЧНЫЕ СЛУЧАИ
# ═══════════════════════════════════════════════════════════════════════════

def test_validate_comparable_edge_price():
    """Тест: граничные значения цены"""
    # Минимально допустимая цена
    comp_min = ComparableProperty(
        url="https://test.com/1",
        price=1_500_000,  # 1.5 млн
        total_area=50.0,
        price_per_sqm=30_000  # Ровно минимум
    )

    is_valid_min, _ = validate_comparable(comp_min)
    assert is_valid_min is True

    # Максимально допустимая цена
    comp_max = ComparableProperty(
        url="https://test.com/2",
        price=500_000_000,  # 500 млн
        total_area=250.0,
        price_per_sqm=2_000_000  # Ровно максимум
    )

    is_valid_max, _ = validate_comparable(comp_max)
    assert is_valid_max is True


def test_validate_comparable_edge_area():
    """Тест: граничные значения площади"""
    # Минимальная площадь
    comp_min = ComparableProperty(
        url="https://test.com/3",
        price=15_000_000,
        total_area=15.0,  # Ровно минимум
        price_per_sqm=1_000_000
    )

    is_valid_min, _ = validate_comparable(comp_min)
    assert is_valid_min is True

    # Максимальная площадь
    comp_max = ComparableProperty(
        url="https://test.com/4",
        price=1_000_000_000,
        total_area=1000.0,  # Ровно максимум
        price_per_sqm=1_000_000
    )

    is_valid_max, _ = validate_comparable(comp_max)
    assert is_valid_max is True


def test_validate_comparable_allowed_statuses():
    """Тест: разрешенные статусы объектов"""
    allowed_statuses = ['готов', 'отделка', 'строительство']

    for status in allowed_statuses:
        comp = ComparableProperty(
            url=f"https://test.com/{status}",
            price=100_000_000,
            total_area=100.0,
            price_per_sqm=1_000_000,
            object_status=status
        )

        is_valid, details = validate_comparable(comp)
        assert is_valid is True, f"Статус '{status}' должен быть валидным"


def test_validate_comparable_excluded_statuses():
    """Тест: исключенные статусы объектов"""
    excluded_statuses = ['проект', 'котлован', 'снесен']

    for status in excluded_statuses:
        comp = ComparableProperty(
            url=f"https://test.com/{status}",
            price=100_000_000,
            total_area=100.0,
            price_per_sqm=1_000_000,
            object_status=status
        )

        is_valid, details = validate_comparable(comp)
        assert is_valid is False, f"Статус '{status}' должен быть невалидным"


# ═══════════════════════════════════════════════════════════════════════════
# ТЕСТЫ: ИНТЕГРАЦИЯ
# ═══════════════════════════════════════════════════════════════════════════

def test_integration_realistic_dataset(
    valid_comparable,
    invalid_comparable_no_price,
    invalid_comparable_bad_price
):
    """Тест: реалистичный датасет с разными типами проблем"""
    # Создаем датасет похожий на реальный:
    # - 15 валидных
    # - 3 без цены
    # - 2 с нереальной ценой
    # - Итого: 20 объявлений
    comparables = (
        [valid_comparable] * 15 +
        [invalid_comparable_no_price] * 3 +
        [invalid_comparable_bad_price] * 2
    )

    # Сводка
    summary = get_validation_summary(comparables)
    assert summary['total'] == 20
    assert summary['valid'] == 15
    assert summary['invalid'] == 5
    assert summary['valid_percentage'] == 75.0

    # Фильтрация
    valid, excluded = filter_valid_comparables(comparables, verbose=False)
    assert len(valid) == 15
    assert len(excluded) == 5

    # Проверка минимума
    assert check_minimum_comparables(valid, minimum=10, raise_error=False) is True
    assert check_minimum_comparables(valid, minimum=20, raise_error=False) is False
