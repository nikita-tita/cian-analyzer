"""
Тесты для новых аналитических модулей:
- price_range (диапазон цен)
- attractiveness_index (индекс привлекательности)
- time_forecast (прогноз времени продажи)
"""

import pytest
from src.analytics.price_range import calculate_price_range, calculate_price_sensitivity
from src.analytics.attractiveness_index import calculate_attractiveness_index
from src.analytics.time_forecast import forecast_time_to_sell, forecast_at_different_prices
from src.models.property import TargetProperty


# ═══════════════════════════════════════════════════════════════════════════
# ТЕСТЫ ДИАПАЗОНА ЦЕН
# ═══════════════════════════════════════════════════════════════════════════

def test_calculate_price_range_basic():
    """Тест базового расчета диапазона цен"""
    fair_price = 15_000_000
    ci = {'lower': 14_000_000, 'upper': 16_000_000, 'margin': 1_000_000}

    result = calculate_price_range(
        fair_price=fair_price,
        confidence_interval=ci,
        overpricing_percent=0
    )

    assert result is not None
    assert 'min_price' in result
    assert 'fair_price' in result
    assert 'recommended_listing' in result
    assert 'max_price' in result
    assert 'min_acceptable_price' in result

    # Проверка логических границ
    assert result['min_price'] < result['fair_price'] < result['max_price']
    assert result['min_price'] < result['min_acceptable_price'] <= result['recommended_listing']


def test_calculate_price_range_overpriced():
    """Тест расчета диапазона для переоцененного объекта"""
    fair_price = 15_000_000
    ci = {'lower': 14_000_000, 'upper': 16_000_000, 'margin': 1_000_000}

    result = calculate_price_range(
        fair_price=fair_price,
        confidence_interval=ci,
        overpricing_percent=15  # Сильно переоценен
    )

    # Для переоцененного объекта рекомендуемая цена = справедливой
    assert result['recommended_listing'] == fair_price
    assert 'interpretation' in result


def test_calculate_price_range_underpriced():
    """Тест расчета диапазона для недооцененного объекта"""
    fair_price = 15_000_000
    ci = {'lower': 14_000_000, 'upper': 16_000_000, 'margin': 1_000_000}

    result = calculate_price_range(
        fair_price=fair_price,
        confidence_interval=ci,
        overpricing_percent=-8  # Недооценен
    )

    # Для недооцененного можно добавить премию
    assert result['recommended_listing'] >= fair_price


def test_calculate_price_range_without_ci():
    """Тест расчета диапазона без доверительного интервала"""
    fair_price = 15_000_000

    result = calculate_price_range(
        fair_price=fair_price,
        confidence_interval=None,
        overpricing_percent=0
    )

    # Должен использовать дефолтный ±5%
    assert result is not None
    assert 'min_price' in result
    assert 'max_price' in result


def test_calculate_price_sensitivity():
    """Тест расчета чувствительности к цене"""
    fair_price = 15_000_000

    sensitivity = calculate_price_sensitivity(
        fair_price=fair_price,
        base_probability=0.75,
        time_months=6
    )

    assert len(sensitivity) > 0
    for point in sensitivity:
        assert 'price' in point
        assert 'discount_percent' in point
        assert 'probability' in point
        assert 'expected_time_months' in point

        # Вероятность должна быть от 0 до 1
        assert 0 <= point['probability'] <= 1


# ═══════════════════════════════════════════════════════════════════════════
# ТЕСТЫ ИНДЕКСА ПРИВЛЕКАТЕЛЬНОСТИ
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def sample_target():
    """Пример целевого объекта для тестов"""
    return TargetProperty(
        url="https://example.com/1",
        price=15_000_000,
        total_area=85.0,
        living_area=50.0,
        rooms=2,
        floor=10,
        total_floors=20,
        repair_level="капитальная",
        ceiling_height=2.9,
        bathrooms=1,
        window_type="пластиковые",
        view_type="парк",
        parking_type="подземная",
        elevator_count="два",
        security_level="24/7",
        house_type="монолит",
        photo_type="реальные",
        object_status="готов",
        images=["photo1.jpg", "photo2.jpg", "photo3.jpg"] * 5,  # 15 фото
        description="Отличная квартира в хорошем районе с развитой инфраструктурой" * 3
    )


@pytest.fixture
def sample_fair_price_analysis():
    """Пример анализа справедливой цены"""
    return {
        'fair_price_total': 15_000_000,
        'current_price': 15_500_000,
        'overpricing_percent': 3.3
    }


@pytest.fixture
def sample_market_stats():
    """Пример рыночной статистики"""
    return {
        'all': {
            'mean': 180_000,
            'median': 175_000,
            'count': 25
        }
    }


def test_attractiveness_index_basic(sample_target, sample_fair_price_analysis, sample_market_stats):
    """Тест базового расчета индекса привлекательности"""
    result = calculate_attractiveness_index(
        target=sample_target,
        fair_price_analysis=sample_fair_price_analysis,
        market_stats=sample_market_stats
    )

    assert result is not None
    assert 'total_index' in result
    assert 0 <= result['total_index'] <= 100
    assert 'category' in result
    assert 'components' in result

    # Проверка компонентов
    components = result['components']
    assert 'price' in components
    assert 'presentation' in components
    assert 'features' in components

    # Каждый компонент должен иметь score и weight
    for comp_name, comp_data in components.items():
        assert 'score' in comp_data
        assert 'weight' in comp_data
        assert 0 <= comp_data['score'] <= 100


def test_attractiveness_index_overpriced():
    """Тест индекса для сильно переоцененного объекта"""
    target = TargetProperty(
        url="https://example.com/1",
        price=20_000_000,
        total_area=80.0,
        images=["photo1.jpg"]  # Мало фото
    )

    fair_price_analysis = {
        'fair_price_total': 15_000_000,
        'overpricing_percent': 33  # Сильно переоценен
    }

    result = calculate_attractiveness_index(
        target=target,
        fair_price_analysis=fair_price_analysis,
        market_stats={'all': {'mean': 180_000, 'median': 175_000}}
    )

    # Индекс должен быть низким из-за переоценки
    assert result['total_index'] < 60
    # Оценка цены должна быть низкой
    assert result['components']['price']['score'] < 50


def test_attractiveness_index_excellent():
    """Тест индекса для отличного объекта"""
    target = TargetProperty(
        url="https://example.com/1",
        price=15_000_000,
        total_area=85.0,
        living_area=55.0,
        rooms=2,
        floor=10,
        total_floors=20,
        repair_level="премиум",
        ceiling_height=3.2,
        bathrooms=2,
        window_type="панорамные",
        view_type="вода",
        parking_type="подземная",
        elevator_count="два",
        security_level="24/7+консьерж+видео",
        house_type="монолит",
        photo_type="реальные",
        object_status="готов",
        images=["photo.jpg"] * 20,  # 20 фото
        description="Роскошная квартира с панорамным видом на воду" * 5
    )

    fair_price_analysis = {
        'fair_price_total': 15_000_000,
        'overpricing_percent': -2  # Недооценен
    }

    result = calculate_attractiveness_index(
        target=target,
        fair_price_analysis=fair_price_analysis,
        market_stats={'all': {'mean': 180_000, 'median': 175_000}}
    )

    # Индекс должен быть высоким
    assert result['total_index'] >= 80
    assert result['category'] in ['Отличная', 'Хорошая']


# ═══════════════════════════════════════════════════════════════════════════
# ТЕСТЫ ПРОГНОЗА ВРЕМЕНИ ПРОДАЖИ
# ═══════════════════════════════════════════════════════════════════════════

def test_forecast_time_to_sell_basic():
    """Тест базового прогноза времени продажи"""
    result = forecast_time_to_sell(
        current_price=15_000_000,
        fair_price=15_000_000,
        attractiveness_index=75
    )

    assert result is not None
    assert 'expected_time_months' in result
    assert 'probability_milestones' in result
    assert result['expected_time_months'] > 0


def test_forecast_time_to_sell_overpriced():
    """Тест прогноза для переоцененного объекта"""
    result = forecast_time_to_sell(
        current_price=18_000_000,
        fair_price=15_000_000,  # Переоценка на 20%
        attractiveness_index=75
    )

    # Время продажи должно быть больше из-за переоценки
    assert result['expected_time_months'] > 3


def test_forecast_time_to_sell_excellent():
    """Тест прогноза для отличного объекта по справедливой цене"""
    result = forecast_time_to_sell(
        current_price=15_000_000,
        fair_price=15_000_000,
        attractiveness_index=90  # Очень привлекательный
    )

    # Время продажи должно быть маленьким
    assert result['expected_time_months'] <= 3


def test_forecast_time_to_sell_poor():
    """Тест прогноза для слабого объекта"""
    result = forecast_time_to_sell(
        current_price=15_000_000,
        fair_price=15_000_000,
        attractiveness_index=30  # Слабо привлекательный
    )

    # Время продажи должно быть большим
    assert result['expected_time_months'] > 6


def test_forecast_at_different_prices():
    """Тест прогноза при разных ценах"""
    forecasts = forecast_at_different_prices(
        fair_price=15_000_000,
        attractiveness_index=75
    )

    assert len(forecasts) > 0

    for forecast in forecasts:
        assert 'price' in forecast
        assert 'discount_percent' in forecast
        assert 'expected_time_months' in forecast
        assert 'probability_6_months' in forecast
        assert 'probability_12_months' in forecast

        # Вероятности должны быть от 0 до 1
        assert 0 <= forecast['probability_6_months'] <= 1
        assert 0 <= forecast['probability_12_months'] <= 1

        # 12-месячная вероятность >= 6-месячной
        assert forecast['probability_12_months'] >= forecast['probability_6_months']


def test_time_forecast_probability_milestones():
    """Тест вех вероятности продажи"""
    result = forecast_time_to_sell(
        current_price=15_000_000,
        fair_price=15_000_000,
        attractiveness_index=75
    )

    pm = result['probability_milestones']

    # Кумулятивная вероятность должна расти
    assert pm['1_month'] <= pm['3_months'] <= pm['6_months'] <= pm['12_months']

    # 12-месячная вероятность должна быть существенной
    assert pm['12_months'] >= 0.5


# ═══════════════════════════════════════════════════════════════════════════
# ИНТЕГРАЦИОННЫЕ ТЕСТЫ
# ═══════════════════════════════════════════════════════════════════════════

def test_integration_all_modules(sample_target, sample_fair_price_analysis, sample_market_stats):
    """Интеграционный тест: все модули работают вместе"""

    # 1. Индекс привлекательности
    attractiveness = calculate_attractiveness_index(
        target=sample_target,
        fair_price_analysis=sample_fair_price_analysis,
        market_stats=sample_market_stats
    )

    assert attractiveness is not None
    assert 'total_index' in attractiveness

    # 2. Диапазон цен
    price_range = calculate_price_range(
        fair_price=sample_fair_price_analysis['fair_price_total'],
        confidence_interval={'lower': 14_000_000, 'upper': 16_000_000, 'margin': 1_000_000},
        overpricing_percent=sample_fair_price_analysis['overpricing_percent']
    )

    assert price_range is not None
    assert 'recommended_listing' in price_range

    # 3. Прогноз времени
    time_forecast = forecast_time_to_sell(
        current_price=sample_target.price,
        fair_price=sample_fair_price_analysis['fair_price_total'],
        attractiveness_index=attractiveness['total_index']
    )

    assert time_forecast is not None
    assert 'expected_time_months' in time_forecast

    # 4. Все результаты согласованы
    assert price_range['fair_price'] == sample_fair_price_analysis['fair_price_total']
    assert time_forecast['expected_time_months'] > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
