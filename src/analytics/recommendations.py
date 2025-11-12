"""
Движок умных рекомендаций для анализа недвижимости

Генерирует персонализированные рекомендации на основе анализа объекта:
- Критичные (цена)
- Важные (улучшения с ROI)
- Средние (презентация)
- Информационные (стратегия)
"""

from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class Recommendation:
    """Модель рекомендации"""
    priority: int  # 1=CRITICAL, 2=HIGH, 3=MEDIUM, 4=INFO
    icon: str
    title: str
    message: str
    action: str
    expected_result: str
    roi: Optional[float] = None
    financial_impact: Optional[Dict] = None
    category: str = 'general'

    def to_dict(self) -> Dict:
        """Конвертация в словарь для JSON"""
        return {
            'priority': self.priority,
            'priority_label': self._get_priority_label(),
            'icon': self.icon,
            'title': self.title,
            'message': self.message,
            'action': self.action,
            'expected_result': self.expected_result,
            'roi': self.roi,
            # financial_impact убран - вся информация уже в message/action/expected_result
            'category': self.category
        }

    def _get_priority_label(self) -> str:
        """Получить текстовую метку приоритета"""
        labels = {
            1: 'КРИТИЧНО',
            2: 'ВАЖНО',
            3: 'СРЕДНЕ',
            4: 'ИНФО'
        }
        return labels.get(self.priority, 'ИНФО')


class RecommendationEngine:
    """
    Генератор персонализированных рекомендаций

    Анализирует результаты оценки недвижимости и генерирует
    конкретные действия с расчетом ROI и финансового эффекта
    """

    # Приоритеты
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    INFO = 4

    # Константы для расчетов
    DESIGN_COST = 500_000  # Средняя стоимость дизайн-ремонта
    PHOTO_SESSION_COST = 15_000  # Профессиональная фотосессия
    OPPORTUNITY_RATE = 0.08  # Годовая ставка упущенной выгоды

    def __init__(self, analysis_result: Dict):
        """
        Args:
            analysis_result: Результат анализа из RealEstateAnalyzer
        """
        self.analysis = analysis_result
        self.target = analysis_result.get('target_property', {})
        self.fair_price_analysis = analysis_result.get('fair_price_analysis', {})
        self.scenarios = analysis_result.get('price_scenarios', [])
        self.comparables = analysis_result.get('comparables', [])
        self.market_stats = analysis_result.get('market_statistics', {})

    def generate(self) -> List[Recommendation]:
        """
        Генерация всех рекомендаций

        Returns:
            Список рекомендаций, отсортированных по приоритету
        """
        recommendations = []

        # 1. Критичные рекомендации по цене
        recommendations.extend(self._check_pricing())

        # 2. Важные рекомендации по улучшениям с ROI
        recommendations.extend(self._check_improvements())

        # 3. Средние рекомендации по презентации
        recommendations.extend(self._check_presentation())

        # 4. Информационные рекомендации по стратегии
        recommendations.extend(self._check_strategy())

        # 5. Контекстный анализ корректировок
        recommendations.extend(self._analyze_adjustments_context())

        # Сортируем по приоритету
        return sorted(recommendations, key=lambda r: (r.priority, -r.roi if r.roi else 0))

    def _check_pricing(self) -> List[Recommendation]:
        """
        Проверка ценообразования

        Критичные рекомендации по корректировке цены
        """
        recs = []
        overpricing = self.fair_price_analysis.get('overpricing_percent', 0)
        current_price = self.target.get('price', 0)
        fair_price = self.fair_price_analysis.get('fair_price_total', 0)

        if overpricing > 15:
            # КРИТИЧНО: Сильная переоценка
            opportunity_cost_12m = self._calc_opportunity_cost(current_price, 12)
            opportunity_cost_4m = self._calc_opportunity_cost(current_price, 4)
            savings = opportunity_cost_12m - opportunity_cost_4m

            recs.append(Recommendation(
                priority=self.CRITICAL,
                icon='⚠️',
                title='КРИТИЧНО: Сильная переоценка',
                message=f'Объект переоценен на {overpricing:.1f}%. Высокий риск не продать в течение года.',
                action=f'Снизить цену до рыночной: {fair_price:,.0f} ₽',
                expected_result='Продажа за 2-4 месяца с вероятностью 75%',
                category='pricing',
                financial_impact={
                    'current_scenario': 'Не продано 12+ месяцев',
                    'with_action': 'Продано за 4 месяца',
                    'time_saved_months': 8,
                    'opportunity_cost_saved': savings,
                    'recommendation': f'Снизить на {abs(overpricing):.1f}%'
                }
            ))

        elif overpricing > 10:
            # ВАЖНО: Умеренная переоценка
            recs.append(Recommendation(
                priority=self.HIGH,
                icon='⚠️',
                title='Умеренная переоценка',
                message=f'Цена выше рынка на {overpricing:.1f}%. Снижает вероятность продажи.',
                action=f'Рассмотреть снижение на 5-7% до {current_price * 0.93:,.0f} ₽',
                expected_result='Увеличение вероятности продажи на 30-40%',
                category='pricing',
                financial_impact={
                    'price_reduction': current_price * 0.07,
                    'probability_increase': '30-40%',
                    'expected_time_reduction': '2-3 месяца'
                }
            ))

        elif overpricing > 5:
            # СРЕДНЕ: Небольшая переоценка
            recs.append(Recommendation(
                priority=self.MEDIUM,
                icon='💡',
                title='Небольшая переоценка',
                message=f'Цена выше рынка на {overpricing:.1f}%. В пределах нормы, но можно оптимизировать.',
                action='Держать цену, но быть готовым к торгу',
                expected_result='Продажа за 4-6 месяцев',
                category='pricing'
            ))

        elif overpricing < -5:
            # ИНФО: Недооценка
            recs.append(Recommendation(
                priority=self.INFO,
                icon='💰',
                title='Цена ниже рынка',
                message=f'Объект недооценен на {abs(overpricing):.1f}%. Можно продать дороже.',
                action=f'Рассмотреть повышение цены до {fair_price:,.0f} ₽',
                expected_result='Дополнительная прибыль при сохранении скорости продажи',
                category='pricing',
                financial_impact={
                    'potential_gain': fair_price - current_price,
                    'risk_level': 'Низкий'
                }
            ))
        else:
            # Справедливая цена (-5% до +5%)
            recs.append(Recommendation(
                priority=self.INFO,
                icon='✅',
                title='Цена соответствует рынку',
                message=f'Цена находится в пределах справедливой (отклонение {overpricing:+.1f}%). Это хорошая стартовая позиция.',
                action='Держать текущую цену, но быть готовым к торгу 5-7%',
                expected_result='Продажа за 3-6 месяцев с высокой вероятностью',
                category='pricing',
                financial_impact={
                    'торг_диапазон': f'{current_price * 0.93:,.0f} - {current_price:,.0f} ₽',
                    'expected_time': '3-6 месяцев'
                }
            ))

        return recs

    def _check_improvements(self) -> List[Recommendation]:
        """
        Проверка возможностей улучшения

        Важные рекомендации по улучшениям с ROI
        """
        recs = []

        # Дизайн-ремонт
        if not self.target.get('has_design', False):
            cost = self.DESIGN_COST
            area = self.target.get('total_area', 0)
            base_price_per_sqm = self.fair_price_analysis.get('base_price_per_sqm', 0)

            # Расчет прироста стоимости от дизайна (+8%)
            gain = area * base_price_per_sqm * 0.08
            roi = ((gain - cost) / cost * 100) if cost > 0 else 0

            if roi > 50:  # Окупается
                recs.append(Recommendation(
                    priority=self.HIGH,
                    icon='🎨',
                    title='Дизайн-ремонт окупится',
                    message=f'Инвестируя {cost:,.0f} ₽ в дизайнерскую отделку, получите +{gain:,.0f} ₽ к стоимости.',
                    action='Заказать дизайн-проект и ремонт',
                    expected_result=f'ROI: {roi:.0f}%. Срок окупаемости: немедленно при продаже.',
                    roi=roi,
                    category='improvement',
                    financial_impact={
                        'investment': cost,
                        'return': gain,
                        'net_profit': gain - cost,
                        'payback_period': 'При продаже'
                    }
                ))

        # Парковка (если премиум и нет парковки)
        if self.target.get('premium_location') and not self.target.get('parking'):
            area = self.target.get('total_area', 0)
            base_price_per_sqm = self.fair_price_analysis.get('base_price_per_sqm', 0)
            parking_premium = area * base_price_per_sqm * 0.04  # +4% за парковку

            recs.append(Recommendation(
                priority=self.HIGH,
                icon='🚗',
                title='Парковка повысит ликвидность',
                message=f'В премиум локации наличие парковки критично. Добавит {parking_premium:,.0f} ₽ к стоимости.',
                action='Арендовать или купить машиноместо в доме',
                expected_result='Увеличение привлекательности для покупателей на 40%',
                category='improvement',
                financial_impact={
                    'value_increase': parking_premium,
                    'liquidity_boost': '40%'
                }
            ))

        # Высокие потолки (если низкие и премиум)
        ceiling = self.target.get('ceiling_height', 2.7)
        if ceiling < 2.8 and self.target.get('total_area', 0) > 100:
            recs.append(Recommendation(
                priority=self.MEDIUM,
                icon='📏',
                title='Указать высоту потолков',
                message='Если потолки выше 2.8м, обязательно укажите это в описании.',
                action='Проверить фактическую высоту и добавить в характеристики',
                expected_result='Дополнительная привлекательность для сегмента покупателей',
                category='improvement'
            ))

        return recs

    def _check_presentation(self) -> List[Recommendation]:
        """
        Проверка презентации объявления

        Средние рекомендации по фото, описанию, контенту
        """
        recs = []

        # Профессиональные фото
        images_count = len(self.target.get('images', []))
        renders_only = self.target.get('renders_only', False)

        if renders_only or images_count < 10:
            cost = self.PHOTO_SESSION_COST

            # Эффект от качественных фото
            views_increase = 40  # %
            conversion_increase = 15  # %

            # Примерный ROI (1 фотосессия vs потеря покупателей)
            current_price = self.target.get('price', 0)
            opportunity_cost_1m = self._calc_opportunity_cost(current_price, 1)
            roi = ((opportunity_cost_1m - cost) / cost * 100) if cost > 0 else 0

            recs.append(Recommendation(
                priority=self.MEDIUM,
                icon='📸',
                title='Улучшить фотографии',
                message=f'{"Рендеры снижают доверие на 3%." if renders_only else f"Только {images_count} фото - недостаточно."} Качественные фото увеличивают просмотры на {views_increase}%.',
                action=f'Заказать профессиональную фотосессию (~{cost:,.0f} ₽)',
                expected_result=f'Увеличение просмотров на {views_increase}%, конверсии на {conversion_increase}%',
                roi=roi,
                category='presentation',
                financial_impact={
                    'investment': cost,
                    'views_increase_percent': views_increase,
                    'conversion_boost_percent': conversion_increase,
                    'estimated_time_reduction': '1-2 месяца'
                }
            ))

        # Описание
        description = self.target.get('description', '')
        if not description or len(description) < 200:
            recs.append(Recommendation(
                priority=self.MEDIUM,
                icon='📝',
                title='Улучшить описание',
                message='Краткое или отсутствующее описание снижает доверие покупателей.',
                action='Написать подробное описание (300-500 символов) с акцентом на уникальные особенности',
                expected_result='Увеличение времени просмотра объявления на 50%',
                category='presentation'
            ))

        # Видео-обзор
        if self.target.get('price', 0) > 30_000_000:
            recs.append(Recommendation(
                priority=self.MEDIUM,
                icon='🎥',
                title='Добавить видео-обзор',
                message='Для премиум сегмента (>30 млн) видео критично важно.',
                action='Снять профессиональное видео квартиры (3-5 минут)',
                expected_result='Увеличение серьезных обращений на 60%',
                category='presentation',
                financial_impact={
                    'investment': 30_000,
                    'serious_inquiries_boost': '60%'
                }
            ))

        # Общая рекомендация по презентации (всегда)
        if len(recs) == 0:
            recs.append(Recommendation(
                priority=self.INFO,
                icon='✨',
                title='Качество презентации',
                message='Качественная презентация объекта — ключ к быстрой продаже. Даже при справедливой цене плохие фото могут затянуть продажу на месяцы.',
                action='Обновить фотографии при естественном освещении, добавить детальное описание с акцентом на преимущества',
                expected_result='Увеличение количества просмотров и звонков на 30-40%',
                category='presentation',
                financial_impact={
                    'cost': 'минимальная',
                    'impact': 'высокий',
                    'time_to_implement': '1-2 дня'
                }
            ))

        return recs

    def _check_strategy(self) -> List[Recommendation]:
        """
        Проверка стратегии продажи

        Информационные рекомендации по выбору оптимального сценария
        """
        recs = []

        if not self.scenarios:
            return recs

        # ИСПРАВЛЕНО: Найти оптимальный сценарий по ОЖИДАЕМОМУ доходу (expected_value)
        # а не просто по чистой прибыли, так как нужно учитывать вероятность продажи
        best_scenario = max(
            self.scenarios,
            key=lambda s: s.get('financials', {}).get('expected_value', 0)
        )

        best_name = best_scenario.get('name', '')
        best_months = best_scenario.get('time_months', 0)
        best_profit = best_scenario.get('financials', {}).get('net_after_opportunity', 0)
        best_expected_value = best_scenario.get('financials', {}).get('expected_value', 0)
        best_prob = best_scenario.get('base_probability', 0)

        recs.append(Recommendation(
            priority=self.INFO,
            icon='📊',
            title='Оптимальная стратегия продажи',
            message=(
                f'Сценарий "{best_name}" дает максимальный ОЖИДАЕМЫЙ доход '
                f'{best_expected_value:,.0f} ₽ с учетом вероятности продажи.'
            ),
            action=f'Следовать стратегии "{best_name}"',
            expected_result=(
                f'Продажа за {best_months} мес. с вероятностью {best_prob}%. '
                f'Чистая прибыль: {best_profit:,.0f} ₽. '
                f'Ожидаемый доход: {best_expected_value:,.0f} ₽.'
            ),
            category='strategy',
            financial_impact={
                'scenario': best_name,
                'expected_time_months': best_months,
                'probability_percent': best_prob,
                'net_profit': best_profit,
                'expected_value': best_expected_value
            }
        ))

        # ИСПРАВЛЕНО: Сравнение быстрой vs максимальной цены по ОЖИДАЕМОМУ доходу
        fast_scenario = next((s for s in self.scenarios if s.get('type') == 'fast'), None)
        max_scenario = next((s for s in self.scenarios if s.get('type') == 'maximum'), None)

        if fast_scenario and max_scenario:
            fast_expected = fast_scenario.get('financials', {}).get('expected_value', 0)
            max_expected = max_scenario.get('financials', {}).get('expected_value', 0)

            if fast_expected > max_expected:
                diff = fast_expected - max_expected
                recs.append(Recommendation(
                    priority=self.INFO,
                    icon='⚡',
                    title='Быстрая продажа выгоднее',
                    message=(
                        f'Попытка "выжать максимум" обойдется дороже на {diff:,.0f} ₽ '
                        f'при учете вероятности продажи и упущенной выгоды.'
                    ),
                    action='Не затягивать с продажей',
                    expected_result='Экономия времени и денег',
                    category='strategy',
                    financial_impact={
                        'fast_scenario_expected': fast_expected,
                        'max_scenario_expected': max_expected,
                        'difference': diff,
                        'explanation': (
                            'Ожидаемый доход учитывает как размер прибыли, '
                            'так и вероятность продажи. Быстрая продажа с высокой '
                            'вероятностью часто выгоднее долгого ожидания.'
                        )
                    }
                ))

        return recs

    def _calc_opportunity_cost(self, price: float, months: int) -> float:
        """
        Расчет упущенной выгоды

        Args:
            price: Цена объекта
            months: Количество месяцев

        Returns:
            Упущенная выгода в рублях
        """
        return price * self.OPPORTUNITY_RATE * (months / 12)

    def _analyze_adjustments_context(self) -> List[Recommendation]:
        """
        Контекстный анализ корректировок

        Анализирует корректировки и дает умные рекомендации с учетом контекста.
        Например, меньшая площадь в престижном районе может быть плюсом.
        """
        recs = []
        adjustments = self.fair_price_analysis.get('adjustments', {})

        # Анализ корректировки площади
        if 'total_area' in adjustments:
            area_adj = adjustments['total_area']
            area_impact = (area_adj.get('value', 1) - 1) * 100
            target_area = area_adj.get('target_value', 0)
            median_area = area_adj.get('median_value', 0)

            current_price = self.target.get('price', 0)
            price_per_sqm = self.target.get('price_per_sqm', 0)

            # Если площадь меньше медианы и получили штраф
            if target_area < median_area and area_impact < 0:
                # Но цена за м² высокая (>200k) или общая цена >20млн = престижный район
                is_premium = price_per_sqm > 200000 or current_price > 20000000

                if is_premium:
                    recs.append(Recommendation(
                        priority=self.INFO,
                        icon='💎',
                        title='Меньшая площадь в престижном районе — это плюс',
                        message=f'Система дала штраф {area_impact:.1f}% за площадь {target_area:.0f}м² vs {median_area:.0f}м² (медиана). '
                                f'Но в вашем случае это неверно! В престижных районах (цена {price_per_sqm:,.0f} ₽/м²) '
                                f'меньшая площадь = выше доступность для покупателей и выше ликвидность.',
                        action='Не снижать цену из-за площади. Ваш размер — оптимален для этого сегмента.',
                        expected_result='Реальная цена может быть на 3-5% выше расчетной',
                        category='pricing',
                        financial_impact={
                            'системный_штраф': f'{area_impact:.1f}%',
                            'реальный_эффект': '+3-5% (ликвидность)',
                            'объяснение': 'Компактность = преимущество в премиум-сегменте'
                        }
                    ))
                else:
                    # Обычный сегмент - штраф оправдан
                    recs.append(Recommendation(
                        priority=self.INFO,
                        icon='📏',
                        title='Меньшая площадь влияет на цену',
                        message=f'Ваша площадь {target_area:.0f}м² меньше медианы {median_area:.0f}м². '
                                f'В вашем сегменте (цена {price_per_sqm:,.0f} ₽/м²) это снижает привлекательность.',
                        action='Учитывать при ценообразовании',
                        expected_result='Корректировка {area_impact:.1f}% оправдана',
                        category='pricing'
                    ))

            # Если площадь больше медианы и получили бонус
            elif target_area > median_area and area_impact > 0:
                # Проверяем, не слишком ли большая квартира для рынка
                comparables_areas = [c.get('total_area', 0) for c in self.comparables if c.get('total_area')]
                if comparables_areas:
                    max_comparable = max(comparables_areas)
                    if target_area > max_comparable * 1.2:
                        recs.append(Recommendation(
                            priority=self.MEDIUM,
                            icon='⚠️',
                            title='Очень большая площадь может затруднить продажу',
                            message=f'Ваша площадь {target_area:.0f}м² значительно больше всех аналогов (макс {max_comparable:.0f}м²). '
                                    f'Система дала бонус +{area_impact:.1f}%, но это может быть ошибкой.',
                            action='Быть готовым к более длительной продаже или снижению цены',
                            expected_result='Узкая аудитория покупателей',
                            category='pricing',
                            financial_impact={
                                'системный_бонус': f'+{area_impact:.1f}%',
                                'реальный_риск': 'Затянутая продажа на 2-4 месяца'
                            }
                        ))

        return recs

    def get_summary(self) -> Dict:
        """
        Получить сводку рекомендаций

        Returns:
            Словарь с количеством рекомендаций по приоритетам
        """
        recommendations = self.generate()

        summary = {
            'total': len(recommendations),
            'by_priority': {
                'critical': len([r for r in recommendations if r.priority == self.CRITICAL]),
                'high': len([r for r in recommendations if r.priority == self.HIGH]),
                'medium': len([r for r in recommendations if r.priority == self.MEDIUM]),
                'info': len([r for r in recommendations if r.priority == self.INFO])
            },
            'by_category': {}
        }

        # Группировка по категориям
        for rec in recommendations:
            category = rec.category
            if category not in summary['by_category']:
                summary['by_category'][category] = 0
            summary['by_category'][category] += 1

        return summary
