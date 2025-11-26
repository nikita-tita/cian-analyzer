"""
Движок умных рекомендаций для анализа недвижимости

Генерирует персонализированные рекомендации на основе анализа объекта:
- Критичные (цена)
- Важные (улучшения с ROI)
- Средние (презентация)
- Информационные (стратегия)
"""

from typing import List, Dict, Optional, Tuple, Any
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
            'financial_impact': self.financial_impact or {},
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
    OPPORTUNITY_RATE = 0.08  # Годовая ставка упущенной выгоды (дефолт)

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
        self.market_profile = analysis_result.get('market_profile', {}) or {}
        (
            self.opportunity_rate,
            self.opportunity_rate_note,
            self.opportunity_metadata,
        ) = self._resolve_opportunity_rate()

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
                    'Текущий сценарий': 'Не продано 12+ месяцев',
                    'После корректировки': 'Продано за 4 месяца',
                    'Экономия времени': '8 мес.',
                    'Экономия на упущенной выгоде': f'{savings:,.0f} ₽',
                    'Рекомендация': f'Снизить на {abs(overpricing):.1f}%'
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
                    'Снижение цены': f'{current_price * 0.07:,.0f} ₽',
                    'Рост вероятности продажи': '30-40%',
                    'Сокращение срока': '2-3 месяца'
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
                    'Потенциальная выгода': f'{fair_price - current_price:,.0f} ₽',
                    'Уровень риска': 'Низкий'
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
                    'Диапазон торга': f'{current_price * 0.93:,.0f} - {current_price:,.0f} ₽',
                    'Ожидаемый срок': '3-6 месяцев'
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
            area = self.target.get('total_area', 0)
            current_price = self.target.get('price', 0)

            # ИСПРАВЛЕНО: Реалистичная стоимость ремонта зависит от площади
            # Средняя стоимость: 30-50 тыс/м² для дизайн-ремонта
            cost_per_sqm = 40_000  # ₽/м²
            cost = area * cost_per_sqm if area > 0 else self.DESIGN_COST

            # ИСПРАВЛЕНО: Реалистичный прирост стоимости от премиум-ремонта: 5-10%
            # (не 8% к цене/м², а 5-10% к общей стоимости)
            realistic_premium = 0.08  # 8% прирост к стоимости
            gain = current_price * realistic_premium if current_price > 0 else 0

            # ROI = (прирост - затраты) / затраты * 100%
            roi = ((gain - cost) / cost * 100) if cost > 0 else 0

            # Только если ROI положительный (окупается)
            if roi > 0:
                recs.append(Recommendation(
                    priority=self.HIGH if roi > 20 else self.MEDIUM,
                    icon='🎨',
                    title='Дизайн-ремонт может окупиться' if roi > 20 else 'Дизайн-ремонт повысит привлекательность',
                    message=f'Инвестируя {cost:,.0f} ₽ в дизайнерскую отделку (~{cost_per_sqm:,.0f} ₽/м²), получите +{gain:,.0f} ₽ к стоимости.',
                    action='Заказать дизайн-проект и ремонт',
                    expected_result=f'ROI: {roi:.0f}%. Прирост стоимости: {realistic_premium*100:.0f}%.',
                    roi=roi,
                    category='improvement',
                    financial_impact={
                        'Инвестиция': f'{cost:,.0f} ₽',
                        'Стоимость за м²': f'{cost_per_sqm:,.0f} ₽/м²',
                        'Прирост стоимости': f'{gain:,.0f} ₽',
                        'Чистая прибыль': f'{gain - cost:,.0f} ₽',
                        'Срок окупаемости': 'При продаже'
                    }
                ))
            else:
                # ROI отрицательный - не окупится
                recs.append(Recommendation(
                    priority=self.MEDIUM,
                    icon='🎨',
                    title='Дизайн-ремонт не окупится',
                    message=f'Инвестиция {cost:,.0f} ₽ даст прирост всего {gain:,.0f} ₽. ROI: {roi:.0f}% (убыток {abs(gain - cost):,.0f} ₽).',
                    action='Продавать как есть или сделать косметический ремонт',
                    expected_result='Экономия средств на ремонте',
                    roi=roi,
                    category='improvement',
                    financial_impact={
                        'Инвестиция': f'{cost:,.0f} ₽',
                        'Прирост стоимости': f'{gain:,.0f} ₽',
                        'Чистый убыток': f'{cost - gain:,.0f} ₽',
                        'Рекомендация': 'Не делать дорогой ремонт перед продажей'
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
                    'Прирост стоимости': f'{parking_premium:,.0f} ₽',
                    'Рост ликвидности': '40%'
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

            # ИСПРАВЛЕНО v2: Фотосессия НЕ увеличивает стоимость, а УСКОРЯЕТ продажу
            # ROI = польза от ускорения (не полная упущенная выгода, а экономия на процентах)
            current_price = self.target.get('price', 0)

            # Без фото: продажа затягивается на 1-2 месяца дольше
            # С фото: экономим 1-1.5 месяца
            time_saved_months = 1.0  # Консервативная оценка

            # Экономия = стоимость денег во времени (альтернативная доходность)
            # Используем ставку упущенной выгоды для расчета экономии
            monthly_rate = self.opportunity_rate / 12
            time_value = current_price * monthly_rate * time_saved_months

            # ROI = (выгода от экономии времени - стоимость) / стоимость
            roi = ((time_value - cost) / cost * 100) if cost > 0 else 0

            # Качественная оценка влияния
            estimated_impact = "ускорение продажи на 1-1.5 месяца"
            if roi > 100:
                estimated_impact = "существенное ускорение продажи"
            elif roi < 0:
                estimated_impact = "минимальное ускорение"

            recs.append(Recommendation(
                priority=self.MEDIUM,
                icon='📸',
                title='Улучшить фотографии',
                message=f'{"Рендеры снижают доверие покупателей." if renders_only else f"Только {images_count} фото - недостаточно для привлечения покупателей."} Качественные фото увеличивают просмотры на {views_increase}% и конверсию на {conversion_increase}%.',
                action=f'Заказать профессиональную фотосессию (~{cost:,.0f} ₽)',
                expected_result=f'Ускорение продажи на {time_saved_months:.0f} мес. Экономия на альтернативной доходности: {time_value:,.0f} ₽.',
                roi=roi,
                category='presentation',
                financial_impact={
                    'Инвестиция': f'{cost:,.0f} ₽',
                    'Рост просмотров': f'{views_increase}%',
                    'Рост конверсии': f'{conversion_increase}%',
                    'Экономия времени': f'{time_saved_months:.0f} мес.',
                    'Экономия на упущенной выгоде': f'{time_value:,.0f} ₽',
                    'Чистая выгода': f'{time_value - cost:,.0f} ₽'
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
                    'Инвестиция': '30 000 ₽',
                    'Рост серьёзных обращений': '60%'
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
                    'Затраты': 'минимальные',
                    'Эффект': 'высокий',
                    'Срок реализации': '1-2 дня'
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
            key=lambda s: s.financials.get('expected_value', 0)
        )

        best_name = best_scenario.name
        best_months = best_scenario.time_months
        best_profit = best_scenario.financials.get('net_after_opportunity', 0)
        best_expected_value = best_scenario.financials.get('expected_value', 0)
        best_prob = best_scenario.base_probability

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
                'Сценарий': best_name,
                'Ожидаемый срок': f'{best_months} мес.',
                'Вероятность продажи': f'{best_prob}%',
                'Чистая прибыль': f'{best_profit:,.0f} ₽',
                'Ожидаемый доход': f'{best_expected_value:,.0f} ₽'
            }
        ))

        # ИСПРАВЛЕНО: Сравнение быстрой vs максимальной цены по ОЖИДАЕМОМУ доходу
        fast_scenario = next((s for s in self.scenarios if s.type == 'fast'), None)
        max_scenario = next((s for s in self.scenarios if s.type == 'maximum'), None)

        if fast_scenario and max_scenario:
            fast_expected = fast_scenario.financials.get('expected_value', 0)
            max_expected = max_scenario.financials.get('expected_value', 0)

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
                        'Быстрая продажа (ожид. доход)': f'{fast_expected:,.0f} ₽',
                        'Максимум (ожид. доход)': f'{max_expected:,.0f} ₽',
                        'Разница': f'{diff:,.0f} ₽'
                    }
                ))

        liquidity_score = self.market_profile.get('liquidity_score')
        if liquidity_score:
            expected_dom = self.market_profile.get('expected_dom_months')
            segment_label = self.market_profile.get('segment_label')
            notes = self.market_profile.get('notes', [])

            if liquidity_score < 0.9:
                recs.append(Recommendation(
                    priority=self.INFO,
                    icon='🐢',
                    title='Низкая ликвидность сегмента',
                    message=(
                        f'{segment_label or "Сегмент"} показывает пониженную ликвидность '
                        f'(индекс {liquidity_score:.2f}). Стоит закладывать больший срок экспозиции '
                        f'и работать с ценой активнее.'
                    ),
                    action='Запланировать переговорный дисконт и дополнительные активности продаж',
                    expected_result=(
                        f'Срок продажи ~{expected_dom or "?"} мес. при текущем спросе. '
                        'Готовность к дисконту снижает риск зависания.'
                    ),
                    category='strategy',
                    financial_impact={
                        'Ожидаемый срок': f'{expected_dom or "?"} мес.',
                        'Индекс ликвидности': f'{liquidity_score:.2f}'
                    }
                ))
            elif liquidity_score > 1.1:
                recs.append(Recommendation(
                    priority=self.INFO,
                    icon='🚀',
                    title='Высокая ликвидность — можно ускориться',
                    message=(
                        f'{segment_label or "Сегмент"} сейчас в спросе (индекс {liquidity_score:.2f}). '
                        'Агрессивный торг не требуется — есть шанс продать быстрее средних сроков.'
                    ),
                    action='Фиксировать цену ближе к справедливой и ставить дедлайны по торгу',
                    expected_result=(
                        f'Планируемый срок экспозиции ~{expected_dom or "?"} мес., '
                        'что на 20-30% быстрее типового рынка.'
                    ),
                    category='strategy',
                    financial_impact={
                        'Ожидаемый срок': f'{expected_dom or "?"} мес.',
                        'Индекс ликвидности': f'{liquidity_score:.2f}'
                    }
                ))

        return recs

    def _resolve_opportunity_rate(self) -> Tuple[float, Optional[str], Dict[str, Any]]:
        """Извлекает актуальную ставку упущенной выгоды из сценариев."""

        if not self.scenarios:
            return self.OPPORTUNITY_RATE, None, {}

        for scenario in self.scenarios:
            financials = getattr(scenario, 'financials', None)
            if financials is None and isinstance(scenario, dict):
                financials = scenario.get('financials')

            if not financials:
                continue

            rate = financials.get('opportunity_rate')
            if rate:
                return (
                    rate,
                    financials.get('opportunity_note'),
                    financials.get('opportunity_metadata') or {},
                )

        return self.OPPORTUNITY_RATE, None, {}

    def _calc_opportunity_cost(self, price: float, months: int) -> float:
        """
        Расчет упущенной выгоды

        Args:
            price: Цена объекта
            months: Количество месяцев

        Returns:
            Упущенная выгода в рублях
        """
        rate = self.opportunity_rate or self.OPPORTUNITY_RATE
        return price * rate * (months / 12)

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
                            'Системный штраф': f'{area_impact:.1f}%',
                            'Реальный эффект': '+3-5% (ликвидность)',
                            'Объяснение': 'Компактность = преимущество в премиум-сегменте'
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
                                'Системный бонус': f'+{area_impact:.1f}%',
                                'Реальный риск': 'Затянутая продажа на 2-4 месяца'
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
