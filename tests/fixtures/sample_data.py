"""
Тестовые фикстуры для unit-тестов

Реалистичные данные для тестирования аналитических модулей
"""

from typing import Dict, List
from src.models.property import ComparableProperty


# ═══════════════════════════════════════════════════════════════════════════
# SAMPLE ANALYSIS RESULTS
# ═══════════════════════════════════════════════════════════════════════════

def get_overpriced_analysis() -> Dict:
    """Анализ сильно переоцененного объекта (>15%)"""
    return {
        'target_property': {
            'price': 12_000_000,
            'total_area': 60,
            'rooms': 2,
            'address': 'СПб, Невский район',
            'has_design': False,
            'premium_location': False,
            'parking': False,
            'photos_count': 5,
            'description_length': 150
        },
        'fair_price_analysis': {
            'fair_price_total': 10_000_000,
            'overpricing_percent': 20.0,  # Сильно переоценен
            'base_price_per_sqm': 166_667,
            'confidence_interval': {
                'lower': 9_500_000,
                'upper': 10_500_000,
                'margin': 500_000
            }
        },
        'price_scenarios': [
            {'type': 'quick', 'price': 9_500_000, 'months': 2},
            {'type': 'standard', 'price': 10_000_000, 'months': 4},
            {'type': 'patient', 'price': 10_500_000, 'months': 6},
            {'type': 'luxury', 'price': 11_000_000, 'months': 12}
        ],
        'comparables': [],
        'market_statistics': {
            'median_price_per_sqm': 165_000,
            'sample_size': 15
        }
    }


def get_fair_priced_analysis() -> Dict:
    """Анализ справедливо оцененного объекта (-5% до +5%)"""
    return {
        'target_property': {
            'price': 15_000_000,
            'total_area': 75,
            'rooms': 3,
            'address': 'СПб, Центральный район',
            'has_design': True,
            'premium_location': True,
            'parking': True,
            'photos_count': 25,
            'description_length': 500
        },
        'fair_price_analysis': {
            'fair_price_total': 15_200_000,
            'overpricing_percent': -1.3,  # Справедливая цена
            'base_price_per_sqm': 202_667,
            'confidence_interval': {
                'lower': 14_500_000,
                'upper': 15_900_000,
                'margin': 700_000
            }
        },
        'price_scenarios': [
            {'type': 'quick', 'price': 14_500_000, 'months': 2},
            {'type': 'standard', 'price': 15_200_000, 'months': 3},
            {'type': 'patient', 'price': 15_900_000, 'months': 5},
            {'type': 'luxury', 'price': 16_500_000, 'months': 8}
        ],
        'comparables': [],
        'market_statistics': {
            'median_price_per_sqm': 203_000,
            'sample_size': 20
        }
    }


def get_underpriced_analysis() -> Dict:
    """Анализ недооцененного объекта (<-5%)"""
    return {
        'target_property': {
            'price': 8_000_000,
            'total_area': 50,
            'rooms': 2,
            'address': 'СПб, Приморский район',
            'has_design': True,
            'premium_location': False,
            'parking': False,
            'photos_count': 15,
            'description_length': 300
        },
        'fair_price_analysis': {
            'fair_price_total': 9_000_000,
            'overpricing_percent': -11.1,  # Недооценен
            'base_price_per_sqm': 180_000,
            'confidence_interval': {
                'lower': 8_700_000,
                'upper': 9_300_000,
                'margin': 300_000
            }
        },
        'price_scenarios': [
            {'type': 'quick', 'price': 8_500_000, 'months': 1},
            {'type': 'standard', 'price': 9_000_000, 'months': 2},
            {'type': 'patient', 'price': 9_300_000, 'months': 3},
            {'type': 'luxury', 'price': 9_500_000, 'months': 5}
        ],
        'comparables': [],
        'market_statistics': {
            'median_price_per_sqm': 180_000,
            'sample_size': 12
        }
    }


def get_needs_improvement_analysis() -> Dict:
    """Анализ объекта без дизайна (потенциал для улучшений)"""
    return {
        'target_property': {
            'price': 10_000_000,
            'total_area': 65,
            'rooms': 2,
            'address': 'СПб, Василеостровский район',
            'has_design': False,  # Нет дизайна - возможность улучшения
            'premium_location': True,
            'parking': False,  # Нет парковки - возможность улучшения
            'photos_count': 8,  # Мало фото - возможность улучшения
            'description_length': 100  # Короткое описание
        },
        'fair_price_analysis': {
            'fair_price_total': 10_200_000,
            'overpricing_percent': -2.0,
            'base_price_per_sqm': 156_923,
            'confidence_interval': {
                'lower': 9_800_000,
                'upper': 10_600_000,
                'margin': 400_000
            }
        },
        'price_scenarios': [
            {'type': 'quick', 'price': 9_800_000, 'months': 2},
            {'type': 'standard', 'price': 10_200_000, 'months': 4},
            {'type': 'patient', 'price': 10_600_000, 'months': 6},
            {'type': 'luxury', 'price': 11_000_000, 'months': 10}
        ],
        'comparables': [],
        'market_statistics': {
            'median_price_per_sqm': 157_000,
            'sample_size': 18
        }
    }


# ═══════════════════════════════════════════════════════════════════════════
# SAMPLE COMPARABLES FOR STATISTICAL TESTS
# ═══════════════════════════════════════════════════════════════════════════

def get_clean_comparables() -> List[ComparableProperty]:
    """Набор чистых данных без выбросов (нормальное распределение)"""
    data = [
        {'price': 10_000_000, 'total_area': 60, 'price_per_sqm': 166_667},
        {'price': 10_200_000, 'total_area': 62, 'price_per_sqm': 164_516},
        {'price': 9_800_000, 'total_area': 58, 'price_per_sqm': 168_966},
        {'price': 10_100_000, 'total_area': 61, 'price_per_sqm': 165_574},
        {'price': 10_300_000, 'total_area': 63, 'price_per_sqm': 163_492},
        {'price': 9_900_000, 'total_area': 59, 'price_per_sqm': 167_797},
        {'price': 10_150_000, 'total_area': 61, 'price_per_sqm': 166_393},
        {'price': 10_050_000, 'total_area': 60, 'price_per_sqm': 167_500},
    ]

    return [
        ComparableProperty(
            url=f'https://cian.ru/test/{i}',
            address=f'СПб, Тестовая {i}',
            price=item['price'],
            total_area=item['total_area'],
            price_per_sqm=item['price_per_sqm'],
            rooms=2,
            floor=5,
            floors_total=10
        )
        for i, item in enumerate(data, 1)
    ]


def get_comparables_with_outliers() -> List[ComparableProperty]:
    """Набор данных с явными выбросами"""
    base = get_clean_comparables()

    # Добавляем выбросы
    outliers = [
        ComparableProperty(
            url='https://cian.ru/outlier/1',
            address='СПб, Выброс 1',
            price=15_000_000,  # +50% выше медианы
            total_area=60,
            price_per_sqm=250_000,  # Выброс!
            rooms=2,
            floor=5,
            floors_total=10
        ),
        ComparableProperty(
            url='https://cian.ru/outlier/2',
            address='СПб, Выброс 2',
            price=6_000_000,  # -40% ниже медианы
            total_area=60,
            price_per_sqm=100_000,  # Выброс!
            rooms=2,
            floor=1,
            floors_total=5
        ),
    ]

    return base + outliers


def get_small_sample() -> List[ComparableProperty]:
    """Маленькая выборка (< 5 элементов)"""
    data = [
        {'price': 10_000_000, 'total_area': 60, 'price_per_sqm': 166_667},
        {'price': 10_200_000, 'total_area': 62, 'price_per_sqm': 164_516},
        {'price': 9_800_000, 'total_area': 58, 'price_per_sqm': 168_966},
    ]

    return [
        ComparableProperty(
            url=f'https://cian.ru/small/{i}',
            address=f'СПб, Маленькая выборка {i}',
            price=item['price'],
            total_area=item['total_area'],
            price_per_sqm=item['price_per_sqm'],
            rooms=2,
            floor=5,
            floors_total=10
        )
        for i, item in enumerate(data, 1)
    ]


def get_high_variance_comparables() -> List[ComparableProperty]:
    """Набор с высокой вариацией (CV > 20%)"""
    data = [
        {'price': 8_000_000, 'total_area': 60, 'price_per_sqm': 133_333},
        {'price': 12_000_000, 'total_area': 60, 'price_per_sqm': 200_000},
        {'price': 9_000_000, 'total_area': 60, 'price_per_sqm': 150_000},
        {'price': 13_000_000, 'total_area': 60, 'price_per_sqm': 216_667},
        {'price': 10_000_000, 'total_area': 60, 'price_per_sqm': 166_667},
        {'price': 11_000_000, 'total_area': 60, 'price_per_sqm': 183_333},
    ]

    return [
        ComparableProperty(
            url=f'https://cian.ru/variance/{i}',
            address=f'СПб, Высокая вариация {i}',
            price=item['price'],
            total_area=item['total_area'],
            price_per_sqm=item['price_per_sqm'],
            rooms=2,
            floor=5,
            floors_total=10
        )
        for i, item in enumerate(data, 1)
    ]
