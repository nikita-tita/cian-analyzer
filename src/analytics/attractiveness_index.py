"""
Индекс привлекательности объекта недвижимости (0-100)

Комплексная оценка конкурентоспособности объекта на рынке.
Учитывает:
- Адекватность цены (40%)
- Качество презентации (30%)
- Характеристики объекта (30%)
"""

import logging
from typing import Dict
from ..models.property import TargetProperty

logger = logging.getLogger(__name__)


def calculate_attractiveness_index(
    target: TargetProperty,
    fair_price_analysis: Dict,
    market_stats: Dict
) -> Dict:
    """
    Расчет индекса привлекательности объекта (0-100)

    Args:
        target: Целевой объект
        fair_price_analysis: Результат анализа справедливой цены
        market_stats: Рыночная статистика

    Returns:
        Словарь с индексом и детализацией
    """

    # 1. Оценка адекватности цены (40% веса)
    price_score = _calculate_price_score(
        target,
        fair_price_analysis.get('overpricing_percent', 0)
    )

    # 2. Оценка качества презентации (30% веса)
    presentation_score = _calculate_presentation_score(target)

    # 3. Оценка характеристик объекта (30% веса)
    features_score = _calculate_features_score(target, market_stats)

    # Взвешенная сумма
    total_index = (
        price_score['score'] * 0.40 +
        presentation_score['score'] * 0.30 +
        features_score['score'] * 0.30
    )

    # Определяем категорию
    category = _get_attractiveness_category(total_index)

    result = {
        'total_index': round(total_index, 1),
        'category': category['name'],
        'category_emoji': category['emoji'],
        'category_description': category['description'],

        'components': {
            'price': {
                'score': round(price_score['score'], 1),
                'weight': 40,
                'weighted_score': round(price_score['score'] * 0.40, 1),
                'details': price_score['details'],
                'recommendations': price_score['recommendations']
            },
            'presentation': {
                'score': round(presentation_score['score'], 1),
                'weight': 30,
                'weighted_score': round(presentation_score['score'] * 0.30, 1),
                'details': presentation_score['details'],
                'recommendations': presentation_score['recommendations']
            },
            'features': {
                'score': round(features_score['score'], 1),
                'weight': 30,
                'weighted_score': round(features_score['score'] * 0.30, 1),
                'details': features_score['details'],
                'recommendations': features_score['recommendations']
            }
        },

        'summary': _generate_summary(total_index, price_score, presentation_score, features_score)
    }

    logger.info(f"Индекс привлекательности: {total_index:.1f}/100 ({category['name']})")

    return result


def _calculate_price_score(target: TargetProperty, overpricing_percent: float) -> Dict:
    """
    Оценка адекватности цены (0-100)

    Ключевой фактор привлекательности
    """

    details = {}
    recommendations = []

    if overpricing_percent < -10:
        # Сильно недооценен
        score = 100
        details['status'] = 'Сильно недооценен'
        details['emoji'] = '💰💰💰'
        recommendations.append('Можно повысить цену на 5-10% без риска')
    elif overpricing_percent < -5:
        # Недооценен
        score = 95
        details['status'] = 'Недооценен'
        details['emoji'] = '💰💰'
        recommendations.append('Рассмотрите повышение цены на 3-5%')
    elif overpricing_percent <= 5:
        # Справедливая цена
        score = 90
        details['status'] = 'Справедливая цена'
        details['emoji'] = '✅'
        recommendations.append('Цена адекватна рынку - держите курс')
    elif overpricing_percent <= 10:
        # Небольшая переоценка
        score = 70
        details['status'] = 'Немного переоценен'
        details['emoji'] = '⚠️'
        recommendations.append('Будьте готовы к активному торгу на 3-5%')
    elif overpricing_percent <= 15:
        # Умеренная переоценка
        score = 50
        details['status'] = 'Переоценен'
        details['emoji'] = '⚠️⚠️'
        recommendations.append('Рекомендуется снизить цену на 5-7%')
    elif overpricing_percent <= 20:
        # Сильная переоценка
        score = 30
        details['status'] = 'Сильно переоценен'
        details['emoji'] = '🔴'
        recommendations.append('КРИТИЧНО: Снизить цену на 10-15%')
    else:
        # Экстремальная переоценка
        score = 10
        details['status'] = 'Экстремально переоценен'
        details['emoji'] = '🔴🔴🔴'
        recommendations.append('СРОЧНО: Пересмотреть ценообразование')

    details['overpricing_percent'] = round(overpricing_percent, 1)

    return {
        'score': score,
        'details': details,
        'recommendations': recommendations
    }


def _calculate_presentation_score(target: TargetProperty) -> Dict:
    """
    Оценка качества презентации (0-100)

    Фотографии, описание, видео
    """

    score = 0
    details = {}
    recommendations = []

    # 1. Фотографии (50 баллов максимум)
    images_count = len(target.images) if target.images else 0

    if images_count >= 15:
        photo_score = 50
        details['photos'] = f'Отлично ({images_count} фото)'
    elif images_count >= 10:
        photo_score = 40
        details['photos'] = f'Хорошо ({images_count} фото)'
        recommendations.append('Добавьте еще 5+ фото для идеальной презентации')
    elif images_count >= 5:
        photo_score = 25
        details['photos'] = f'Удовлетворительно ({images_count} фото)'
        recommendations.append('ВАЖНО: Добавьте минимум 10 фотографий')
    else:
        photo_score = 10
        details['photos'] = f'Плохо ({images_count} фото)'
        recommendations.append('КРИТИЧНО: Минимум 10-15 качественных фото')

    score += photo_score

    # 2. Тип фотографий (25 баллов максимум)
    photo_type = target.photo_type or 'неизвестно'

    if photo_type == 'реальные':
        photo_type_score = 25
        details['photo_type'] = 'Реальные фото ✅'
    elif photo_type == 'реальные+рендеры':
        photo_type_score = 20
        details['photo_type'] = 'Реальные + рендеры'
    elif photo_type == 'рендеры+видео':
        photo_type_score = 15
        details['photo_type'] = 'Рендеры + видео'
        recommendations.append('Добавьте реальные фотографии объекта')
    elif photo_type == 'только_рендеры':
        photo_type_score = 10
        details['photo_type'] = 'Только рендеры ⚠️'
        recommendations.append('ВАЖНО: Рендеры снижают доверие - добавьте реальные фото')
    else:
        photo_type_score = 5
        details['photo_type'] = 'Нет информации'

    score += photo_type_score

    # 3. Описание (15 баллов максимум)
    description = target.description or ''
    desc_length = len(description)

    if desc_length >= 500:
        desc_score = 15
        details['description'] = 'Подробное описание ✅'
    elif desc_length >= 300:
        desc_score = 12
        details['description'] = 'Хорошее описание'
    elif desc_length >= 200:
        desc_score = 8
        details['description'] = 'Краткое описание'
        recommendations.append('Расширьте описание до 300-500 символов')
    else:
        desc_score = 3
        details['description'] = 'Очень краткое или отсутствует'
        recommendations.append('Напишите подробное описание (300-500 символов)')

    score += desc_score

    # 4. Статус объекта (10 баллов максимум)
    object_status = target.object_status or 'неизвестно'

    if object_status == 'готов':
        status_score = 10
        details['object_status'] = 'Готов к заселению ✅'
    elif object_status == 'отделка':
        status_score = 7
        details['object_status'] = 'Идет отделка'
    elif object_status == 'строительство':
        status_score = 5
        details['object_status'] = 'В строительстве ⚠️'
    else:
        status_score = 3
        details['object_status'] = f'{object_status}'

    score += status_score

    return {
        'score': min(score, 100),
        'details': details,
        'recommendations': recommendations
    }


def _calculate_features_score(target: TargetProperty, market_stats: Dict) -> Dict:
    """
    Оценка характеристик объекта (0-100)

    Ремонт, вид, парковка, лифт, потолки и т.д.
    """

    score = 0
    details = {}
    recommendations = []

    # 1. Уровень отделки (30 баллов максимум)
    repair_level = target.repair_level or 'неизвестно'

    repair_scores = {
        'дизайнерская': 30,
        'люкс': 28,
        'премиум': 25,
        'улучшенная': 20,
        'капитальная': 18,
        'стандартная': 15,
        'эконом': 10,
        'черновая': 5
    }

    repair_score = repair_scores.get(repair_level, 10)
    score += repair_score
    details['repair_level'] = repair_level.capitalize()

    if repair_score < 20:
        recommendations.append('Качественный ремонт значительно повысит привлекательность')

    # 2. Вид из окна (15 баллов максимум)
    view_type = target.view_type or 'неизвестно'

    view_scores = {
        'премиум': 15,
        'вода': 14,
        'закат': 14,
        'город': 12,
        'парк': 10,
        'улица': 7,
        'дом': 7,
        'худогов': 3
    }

    view_score = view_scores.get(view_type, 7)
    score += view_score
    details['view_type'] = view_type.capitalize()

    # 3. Парковка (15 баллов максимум)
    parking_type = target.parking_type or 'нет'

    parking_scores = {
        'гараж': 15,
        'подземная': 14,
        'несколько': 13,
        'закрытая': 12,
        'навес': 8,
        'открытая': 6,
        'нет': 0
    }

    parking_score = parking_scores.get(parking_type, 0)
    score += parking_score
    details['parking'] = parking_type.capitalize()

    if parking_score < 10 and target.total_area and target.total_area > 80:
        recommendations.append('Парковка важна для квартир площадью >80м²')

    # 4. Высота потолков (10 баллов максимум)
    ceiling_height = target.ceiling_height or 0

    if ceiling_height >= 3.2:
        ceiling_score = 10
        details['ceiling_height'] = f'{ceiling_height}м (очень высокие) ✅'
    elif ceiling_height >= 3.0:
        ceiling_score = 8
        details['ceiling_height'] = f'{ceiling_height}м (высокие)'
    elif ceiling_height >= 2.7:
        ceiling_score = 6
        details['ceiling_height'] = f'{ceiling_height}м (стандарт)'
    elif ceiling_height >= 2.5:
        ceiling_score = 4
        details['ceiling_height'] = f'{ceiling_height}м (низкие)'
    else:
        ceiling_score = 2
        details['ceiling_height'] = 'Не указана или очень низкие'

    score += ceiling_score

    # 5. Лифты (10 баллов максимум)
    elevator_count = target.elevator_count or 'нет'

    elevator_scores = {
        'панорамный': 10,
        'три+': 9,
        'два': 8,
        'один': 6,
        'нет': 0
    }

    elevator_score = elevator_scores.get(elevator_count, 0)
    score += elevator_score
    details['elevator'] = elevator_count.capitalize()

    # Лифт критичен для высоких этажей
    if elevator_score == 0 and target.floor and target.floor > 3:
        recommendations.append('ВАЖНО: Отсутствие лифта критично для этажей выше 3')

    # 6. Безопасность (10 баллов максимум)
    security_level = target.security_level or 'нет'

    security_scores = {
        '24/7+консьерж+видео': 10,
        '24/7+консьерж': 8,
        '24/7': 6,
        'дневная': 4,
        'нет': 0
    }

    security_score = security_scores.get(security_level, 0)
    score += security_score
    details['security'] = security_level if security_level != 'нет' else 'Отсутствует'

    # 7. Ванные комнаты (5 баллов максимум)
    bathrooms = target.bathrooms or 1

    if bathrooms >= 3:
        bathroom_score = 5
    elif bathrooms == 2:
        bathroom_score = 4
    elif bathrooms == 1:
        bathroom_score = 3
    else:
        bathroom_score = 1

    score += bathroom_score
    details['bathrooms'] = f'{bathrooms} ванные'

    # 8. Тип дома (5 баллов максимум)
    house_type = target.house_type or 'неизвестно'

    house_scores = {
        'монолит': 5,
        'кирпич': 4,
        'смешанный': 3,
        'панель': 2,
        'дерево': 1
    }

    house_score = house_scores.get(house_type, 2)
    score += house_score
    details['house_type'] = house_type.capitalize()

    return {
        'score': min(score, 100),
        'details': details,
        'recommendations': recommendations
    }


def _get_attractiveness_category(index: float) -> Dict:
    """
    Определение категории привлекательности

    Args:
        index: Индекс привлекательности (0-100)

    Returns:
        Словарь с названием и описанием категории
    """

    if index >= 85:
        return {
            'name': 'Отличная',
            'emoji': '🌟',
            'description': 'Объект очень привлекателен. Высокая вероятность быстрой продажи.'
        }
    elif index >= 70:
        return {
            'name': 'Хорошая',
            'emoji': '✅',
            'description': 'Объект конкурентоспособен. Продажа в разумные сроки.'
        }
    elif index >= 55:
        return {
            'name': 'Средняя',
            'emoji': '⚠️',
            'description': 'Объект имеет недостатки. Требуются улучшения для ускорения продажи.'
        }
    elif index >= 40:
        return {
            'name': 'Ниже среднего',
            'emoji': '🔴',
            'description': 'Объект слабо конкурентоспособен. Необходимы значительные улучшения.'
        }
    else:
        return {
            'name': 'Низкая',
            'emoji': '🔴🔴',
            'description': 'Объект неконкурентоспособен. Требуется комплексная работа над ценой и характеристиками.'
        }


def _generate_summary(
    total_index: float,
    price_score: Dict,
    presentation_score: Dict,
    features_score: Dict
) -> str:
    """
    Генерация краткой сводки по индексу

    Returns:
        Текстовая сводка
    """

    category = _get_attractiveness_category(total_index)

    summary_parts = [
        f"{category['emoji']} Индекс привлекательности: {total_index:.1f}/100 ({category['name']})",
        "",
        category['description'],
        "",
        "Компоненты:",
        f"  • Цена: {price_score['score']:.0f}/100 - {price_score['details']['status']}",
        f"  • Презентация: {presentation_score['score']:.0f}/100",
        f"  • Характеристики: {features_score['score']:.0f}/100",
    ]

    # Добавляем топ-рекомендации
    all_recommendations = (
        price_score['recommendations'] +
        presentation_score['recommendations'] +
        features_score['recommendations']
    )

    if all_recommendations:
        summary_parts.append("")
        summary_parts.append("Ключевые рекомендации:")
        for i, rec in enumerate(all_recommendations[:3], 1):
            summary_parts.append(f"  {i}. {rec}")

    return "\n".join(summary_parts)
