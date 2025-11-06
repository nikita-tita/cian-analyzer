"""
Улучшенный веб-дашборд для анализа недвижимости
Полное соответствие ТЗ с расширенными расчетами
"""

from flask import Flask, render_template, request, jsonify
from typing import Dict, List, Tuple, Optional
import statistics
import math
from datetime import datetime, timedelta

app = Flask(__name__)


class RealEstateAnalyzer:
    """
    Анализатор недвижимости с полным набором расчетов по ТЗ

    Новые возможности:
    - Фильтрация выбросов (±3σ)
    - Медиана для базовой цены
    - 14 коэффициентов корректировки
    - Финансовые расчеты (налоги, комиссия, упущенная выгода)
    - Кумулятивная вероятность продажи
    - Детальные траектории (14 точек)
    """

    def __init__(self):
        self.target_property = {}
        self.comparables = []
        self.filtered_comparables = []

    def set_target_property(self, data: Dict):
        """Установить целевой объект для анализа"""
        self.target_property = data
        self._calculate_derived_metrics()

    def add_comparable(self, data: Dict):
        """Добавить аналог для сравнения"""
        self.comparables.append(data)

    def _calculate_derived_metrics(self):
        """Рассчитать производные метрики"""
        if 'total_area' in self.target_property and 'price' in self.target_property:
            self.target_property['price_per_sqm'] = (
                self.target_property['price'] / self.target_property['total_area']
            )

        if 'living_area' in self.target_property and 'total_area' in self.target_property:
            self.target_property['living_area_percent'] = (
                self.target_property['living_area'] / self.target_property['total_area'] * 100
            )

    def filter_outliers(self) -> List[Dict]:
        """
        Фильтрация выбросов по правилу ±3σ (ТЗ: Раздел 2.1)

        Исключает аналоги, которые слишком далеки от среднего:
        - Цена/м² > (Средняя + 3×σ) → исключить
        - Цена/м² < (Средняя - 3×σ) → исключить
        """
        if not self.comparables:
            return []

        prices_per_sqm = [c.get('price_per_sqm', 0) for c in self.comparables if c.get('price_per_sqm')]

        if len(prices_per_sqm) < 2:
            return self.comparables

        mean = statistics.mean(prices_per_sqm)
        stdev = statistics.stdev(prices_per_sqm)

        # Фильтруем: оставляем только те, что в пределах ±3σ
        filtered = [
            c for c in self.comparables
            if abs(c.get('price_per_sqm', mean) - mean) <= 3 * stdev
        ]

        self.filtered_comparables = filtered
        return filtered

    def calculate_market_statistics(self) -> Dict:
        """
        Рассчитать рыночную статистику по аналогам (ТЗ: Раздел 2.1)

        ИЗМЕНЕНО: Используется МЕДИАНА вместо СРЕДНЕГО для базовой цены
        """
        # Фильтруем выбросы перед расчетом
        filtered = self.filter_outliers()

        if not filtered:
            return {}

        prices_per_sqm = [c.get('price_per_sqm', 0) for c in filtered if c.get('price_per_sqm')]

        # Разделить по типу отделки
        with_design = [c for c in filtered if c.get('has_design', False)]
        without_design = [c for c in filtered if not c.get('has_design', False)]

        prices_with_design = [c.get('price_per_sqm', 0) for c in with_design if c.get('price_per_sqm')]
        prices_without_design = [c.get('price_per_sqm', 0) for c in without_design if c.get('price_per_sqm')]

        stats = {
            'all': {
                'mean': statistics.mean(prices_per_sqm) if prices_per_sqm else 0,
                'median': statistics.median(prices_per_sqm) if prices_per_sqm else 0,
                'min': min(prices_per_sqm) if prices_per_sqm else 0,
                'max': max(prices_per_sqm) if prices_per_sqm else 0,
                'stdev': statistics.stdev(prices_per_sqm) if len(prices_per_sqm) > 1 else 0,
                'count': len(prices_per_sqm),
                'filtered_out': len(self.comparables) - len(filtered)
            },
            'with_design': {
                'mean': statistics.mean(prices_with_design) if prices_with_design else 0,
                'median': statistics.median(prices_with_design) if prices_with_design else 0,
                'count': len(with_design)
            },
            'without_design': {
                'mean': statistics.mean(prices_without_design) if prices_without_design else 0,
                'median': statistics.median(prices_without_design) if prices_without_design else 0,
                'count': len(without_design)
            }
        }

        return stats

    def calculate_fair_price(self) -> Dict:
        """
        Рассчитать справедливую цену методом корректировок (ТЗ: Раздел 2.1)

        ИЗМЕНЕНИЯ:
        - Используется МЕДИАНА вместо СРЕДНЕГО
        - Расширены коэффициенты до 14 факторов
        - Добавлены новые корректировки
        """
        market_stats = self.calculate_market_statistics()

        if not market_stats or not self.target_property:
            return {}

        # ✅ ИЗМЕНЕНО: Используем МЕДИАНУ (более устойчива к выбросам)
        base_price_per_sqm = market_stats['with_design']['median']

        if base_price_per_sqm == 0:
            base_price_per_sqm = market_stats['all']['median']

        # Корректировки (ТЗ: Таблица коэффициентов, стр. 2.1)
        adjustments = {}
        multiplier = 1.0

        # === ПОЛОЖИТЕЛЬНЫЕ КОРРЕКТИРОВКИ ===

        # 1. Размер квартиры (вес +0.10)
        if self.target_property.get('total_area', 0) > 150:
            coef = 1 + ((self.target_property['total_area'] / 150) - 1) * 0.10
            coef = min(coef, 1.05)  # Максимум +5%
            adjustments['large_size'] = coef
            multiplier *= coef

        # 2. Дизайнерская отделка (вес +0.08)
        if self.target_property.get('has_design', False):
            adjustments['design'] = 1.08
            multiplier *= 1.08

        # 3. Вид из окон (вес +0.07)
        if self.target_property.get('panoramic_views', False):
            adjustments['panoramic_views'] = 1.07
            multiplier *= 1.07

        # 4. Расстояние до метро (вес +0.06)
        metro_distance = self.target_property.get('metro_distance_min', 10)
        if metro_distance <= 7:
            coef = 1 + (7 - metro_distance) / 7 * 0.06
            adjustments['metro_proximity'] = coef
            multiplier *= coef

        # 5. Премиум локация (вес +0.06)
        if self.target_property.get('premium_location', False):
            adjustments['premium_location'] = 1.06
            multiplier *= 1.06

        # 6. Тип дома (вес +0.05)
        house_type = self.target_property.get('house_type', 'кирпич')
        if house_type == 'монолит':
            adjustments['house_type'] = 1.05
            multiplier *= 1.05
        elif house_type == 'панель':
            adjustments['house_type'] = 0.95
            multiplier *= 0.95

        # 7. Парковка (вес +0.04)
        parking = self.target_property.get('parking', 'нет')
        if parking == 'подземная':
            adjustments['parking'] = 1.04
            multiplier *= 1.04
        elif parking == 'закрытая':
            adjustments['parking'] = 1.03
            multiplier *= 1.03

        # 8. Высота потолков (вес +0.03)
        ceiling_height = self.target_property.get('ceiling_height', 2.7)
        if ceiling_height >= 3.0:
            coef = 1 + (ceiling_height - 2.7) / 0.5 * 0.03
            adjustments['ceiling_height'] = coef
            multiplier *= coef

        # 9. Охрана 24/7 (вес +0.03)
        if self.target_property.get('security_247', False):
            adjustments['security'] = 1.03
            multiplier *= 1.03

        # 10. Лифт (вес +0.03)
        if self.target_property.get('has_elevator', True):
            adjustments['elevator'] = 1.03
            multiplier *= 1.03

        # === НЕГАТИВНЫЕ КОРРЕКТИРОВКИ ===

        # 11. Низкий процент жилой площади (вес -0.08)
        living_percent = self.target_property.get('living_area_percent', 100)
        if living_percent < 30:
            coef = 1 - (30 - living_percent) / 30 * 0.08
            coef = max(coef, 0.92)  # Максимум -8%
            adjustments['low_living_area'] = coef
            multiplier *= coef

        # 12. Возраст дома (вес -0.05)
        build_year = self.target_property.get('build_year', 2020)
        current_year = datetime.now().year
        age = current_year - build_year
        if age > 10:
            coef = 1 - (age - 10) / 100 * 0.05
            coef = max(coef, 0.95)  # Максимум -5%
            adjustments['building_age'] = coef
            multiplier *= coef

        # 13. Неликвидность (очень высокая цена) (вес -0.04)
        if self.target_property.get('price', 0) > 150_000_000:
            adjustments['high_price'] = 0.96
            multiplier *= 0.96

        # 14. Рендеры вместо фото (вес -0.03)
        if self.target_property.get('renders_only', False):
            adjustments['renders_only'] = 0.97
            multiplier *= 0.97

        fair_price_per_sqm = base_price_per_sqm * multiplier
        fair_price_total = fair_price_per_sqm * self.target_property.get('total_area', 0)

        current_price = self.target_property.get('price', 0)
        overpricing_amount = current_price - fair_price_total
        overpricing_percent = (overpricing_amount / fair_price_total * 100) if fair_price_total > 0 else 0

        return {
            'base_price_per_sqm': base_price_per_sqm,
            'adjustments': adjustments,
            'final_multiplier': multiplier,
            'fair_price_per_sqm': fair_price_per_sqm,
            'fair_price_total': fair_price_total,
            'current_price': current_price,
            'overpricing_amount': overpricing_amount,
            'overpricing_percent': overpricing_percent,
            'method': 'median'  # Указываем, что используется медиана
        }

    def calculate_price_trajectory(self, start_price: float, reduction_rate: float, months: int = 14) -> List[Dict]:
        """
        Расчет траектории цены по месяцам (ТЗ: Раздел 2.3)

        Формула: Цена(t) = Начальная_цена × (1 - reduction_rate)^t

        Args:
            start_price: Стартовая цена
            reduction_rate: Коэффициент снижения (0.015 = 1.5% в месяц)
            months: Количество месяцев (по умолчанию 14)

        Returns:
            List точек траектории
        """
        trajectory = []
        for month in range(months):
            price = start_price * math.pow(1 - reduction_rate, month)
            trajectory.append({
                'month': month,
                'price': price
            })
        return trajectory

    def calculate_monthly_probability(self, scenario_type: str, fair_price: float, start_price: float) -> List[float]:
        """
        Расчет месячной вероятности продажи (ТЗ: Раздел 2.4)

        Логика:
        - Чем ближе цена к справедливой, тем выше вероятность
        - Чем дольше на рынке, тем ниже вероятность (после 3-4 месяцев)
        """
        # Базовая вероятность зависит от отклонения цены
        price_ratio = start_price / fair_price if fair_price > 0 else 1.0

        if scenario_type == 'fast':
            # Быстрая: агрессивная цена, высокая вероятность
            base_prob = [0.45, 0.70, 0.75, 0.75, 0.73, 0.70, 0.68, 0.65, 0.62, 0.60, 0.58, 0.55, 0.53, 0.50]
        elif scenario_type == 'optimal':
            # Оптимальная: сбалансированная
            base_prob = [0.40, 0.65, 0.70, 0.72, 0.70, 0.68, 0.65, 0.62, 0.60, 0.57, 0.55, 0.52, 0.50, 0.48]
        elif scenario_type == 'standard':
            # Стандартная: средняя вероятность
            base_prob = [0.35, 0.55, 0.60, 0.65, 0.63, 0.60, 0.57, 0.54, 0.51, 0.48, 0.45, 0.42, 0.40, 0.38]
        elif scenario_type == 'maximum':
            # Максимум: низкая вероятность (переоценено)
            base_prob = [0.15, 0.20, 0.20, 0.18, 0.15, 0.12, 0.10, 0.08, 0.07, 0.06, 0.05, 0.05, 0.04, 0.04]
        else:
            base_prob = [0.50] * 14

        # Корректировка по отклонению цены
        if price_ratio > 1.1:
            # Сильно переоценено - снижаем вероятность
            adjustment = 0.7
        elif price_ratio > 1.05:
            # Умеренно переоценено
            adjustment = 0.85
        elif price_ratio < 0.95:
            # Недооценено - повышаем вероятность
            adjustment = 1.15
        else:
            adjustment = 1.0

        return [min(p * adjustment, 0.98) for p in base_prob]

    def calculate_cumulative_probability(self, monthly_probabilities: List[float]) -> List[float]:
        """
        Расчет кумулятивной вероятности (ТЗ: Раздел 2.5)

        Формула: P_кум(N) = 1 - ∏[1 - P(t)] для t = 1 до N

        Логика: "Какова вероятность, что продам К концу месяца N?"
        """
        cumulative = []
        remaining = 1.0

        for p in monthly_probabilities:
            cumulative_p = 1 - (remaining * (1 - p))
            cumulative.append(cumulative_p)
            remaining *= (1 - p)

        return cumulative

    def calculate_financials(
        self,
        sale_price: float,
        months_waited: int,
        commission_rate: float = 0.02,
        tax_rate: float = 0.13,
        other_expenses: float = 0.01,
        opportunity_rate: float = 0.08
    ) -> Dict:
        """
        Финансовый расчет (ТЗ: Раздел 2.6)

        Args:
            sale_price: Цена продажи
            months_waited: Сколько месяцев ждали
            commission_rate: Комиссия риэлтора (обычно 2%)
            tax_rate: Налог (13% от суммы для физ.лиц)
            other_expenses: Прочие расходы (обычно 1%)
            opportunity_rate: Упущенная выгода (доходность альтернативных вложений, 8% в год)

        Returns:
            Детальный финансовый расчет
        """
        commission = sale_price * commission_rate
        taxes = sale_price * tax_rate
        other = sale_price * other_expenses

        # Упущенная выгода (ТЗ: Раздел 2.7)
        opportunity_cost = sale_price * opportunity_rate * (months_waited / 12)

        net_income = sale_price - commission - taxes - other
        net_after_opportunity = net_income - opportunity_cost

        effective_yield = (net_after_opportunity / sale_price * 100) if sale_price > 0 else 0

        return {
            'gross_price': sale_price,
            'commission': commission,
            'taxes': taxes,
            'other_expenses': other,
            'opportunity_cost': opportunity_cost,
            'net_income': net_income,
            'net_after_opportunity': net_after_opportunity,
            'effective_yield': effective_yield,
            'months_waited': months_waited
        }

    def generate_price_scenarios(self) -> List[Dict]:
        """
        Генерация ценовых сценариев продажи (ТЗ: Раздел 2.3, 2.4)

        УЛУЧШЕНИЯ:
        - Детальные траектории (14 точек вместо 4-5)
        - Месячная вероятность
        - Кумулятивная вероятность
        - Финансовые расчеты для каждого сценария
        """
        current_price = self.target_property.get('price', 0)
        fair_price_data = self.calculate_fair_price()
        fair_price = fair_price_data.get('fair_price_total', current_price)

        scenarios = [
            {
                'name': 'Быстрая продажа',
                'type': 'fast',
                'description': 'Агрессивная цена для быстрой реализации',
                'start_price': current_price * 0.95,
                'expected_final_price': current_price * 0.87,
                'time_months': 2,
                'base_probability': 85,
                'reduction_rate': 0.015  # 1.5% в месяц
            },
            {
                'name': 'Оптимальная продажа',
                'type': 'optimal',
                'description': 'Рекомендуемая стратегия с балансом цены и времени',
                'start_price': current_price * 0.95,
                'expected_final_price': current_price * 0.90,
                'time_months': 4,
                'base_probability': 75,
                'reduction_rate': 0.012  # 1.2% в месяц
            },
            {
                'name': 'Стандартная продажа',
                'type': 'standard',
                'description': 'Средние сроки с небольшими скидками',
                'start_price': current_price * 0.92,
                'expected_final_price': current_price * 0.85,
                'time_months': 6,
                'base_probability': 65,
                'reduction_rate': 0.020  # 2% в месяц
            },
            {
                'name': 'Попытка максимума',
                'type': 'maximum',
                'description': 'Ставка на максимальную цену (высокий риск)',
                'start_price': current_price,
                'expected_final_price': current_price * 0.82,
                'time_months': 10,
                'base_probability': 30,
                'reduction_rate': 0.025  # 2.5% в месяц
            }
        ]

        # Добавляем детальные траектории и вероятности
        for scenario in scenarios:
            # Траектория цен (14 точек)
            scenario['price_trajectory'] = self.calculate_price_trajectory(
                scenario['start_price'],
                scenario['reduction_rate'],
                14
            )

            # Месячная вероятность
            scenario['monthly_probability'] = self.calculate_monthly_probability(
                scenario['type'],
                fair_price,
                scenario['start_price']
            )

            # Кумулятивная вероятность
            scenario['cumulative_probability'] = self.calculate_cumulative_probability(
                scenario['monthly_probability']
            )

            # Финансовый расчет
            scenario['financials'] = self.calculate_financials(
                scenario['expected_final_price'],
                scenario['time_months']
            )

        return scenarios

    def calculate_strengths_weaknesses(self) -> Dict:
        """Рассчитать сильные и слабые стороны с оценкой влияния"""
        strengths = []
        weaknesses = []

        # Сильные стороны
        if self.target_property.get('has_design'):
            strengths.append({
                'factor': 'Дизайнерская отделка',
                'impact': 8,
                'premium_percent': 8
            })

        if self.target_property.get('panoramic_views'):
            strengths.append({
                'factor': 'Панорамные виды',
                'impact': 7,
                'premium_percent': 7
            })

        if self.target_property.get('premium_location'):
            strengths.append({
                'factor': 'Премиум локация',
                'impact': 6,
                'premium_percent': 6
            })

        if self.target_property.get('total_area', 0) > 150:
            strengths.append({
                'factor': 'Большая площадь',
                'impact': 5,
                'premium_percent': 5
            })

        # Слабые стороны
        if self.target_property.get('living_area_percent', 100) < 30:
            weaknesses.append({
                'factor': 'Низкий процент жилой площади',
                'impact': 8,
                'discount_percent': 8
            })

        if self.target_property.get('renders_only'):
            weaknesses.append({
                'factor': 'Только рендеры (нет реальных фото)',
                'impact': 3,
                'discount_percent': 3
            })

        if self.target_property.get('price', 0) > 150_000_000:
            weaknesses.append({
                'factor': 'Очень высокая цена (низкая ликвидность)',
                'impact': 4,
                'discount_percent': 4
            })

        total_premium = sum(s['premium_percent'] for s in strengths)
        total_discount = sum(w['discount_percent'] for w in weaknesses)

        return {
            'strengths': strengths,
            'weaknesses': weaknesses,
            'total_premium_percent': total_premium,
            'total_discount_percent': total_discount,
            'net_adjustment': total_premium - total_discount
        }

    def generate_comparison_chart_data(self) -> Dict:
        """Генерация данных для графика сравнения с аналогами"""
        # Используем отфильтрованные аналоги
        all_properties = [self.target_property] + (self.filtered_comparables or self.comparables)

        labels = []
        prices_per_sqm = []
        colors = []

        for i, prop in enumerate(all_properties):
            if i == 0:
                labels.append('ЦЕЛЕВОЙ')
                colors.append('rgba(255, 99, 132, 0.8)')
            else:
                label = f"{prop.get('rooms', '?')}-комн {prop.get('total_area', '?')}м²"
                labels.append(label)

                if prop.get('has_design'):
                    colors.append('rgba(75, 192, 192, 0.8)')
                else:
                    colors.append('rgba(201, 203, 207, 0.8)')

            prices_per_sqm.append(prop.get('price_per_sqm', 0) / 1_000_000)  # В млн

        return {
            'labels': labels,
            'datasets': [{
                'label': 'Цена за м² (млн ₽)',
                'data': prices_per_sqm,
                'backgroundColor': colors,
                'borderColor': [c.replace('0.8', '1') for c in colors],
                'borderWidth': 2
            }]
        }

    def generate_box_plot_data(self) -> Dict:
        """
        Генерация данных для box-plot (ТЗ: График 2)

        Returns:
            Данные для построения "ящика с усами"
        """
        filtered = self.filtered_comparables or self.comparables
        prices = [c.get('price_per_sqm', 0) / 1_000_000 for c in filtered if c.get('price_per_sqm')]

        if not prices:
            return {}

        prices.sort()
        n = len(prices)

        q1_index = n // 4
        q2_index = n // 2
        q3_index = 3 * n // 4

        return {
            'min': min(prices),
            'q1': prices[q1_index] if q1_index < n else prices[0],
            'median': statistics.median(prices),
            'q3': prices[q3_index] if q3_index < n else prices[-1],
            'max': max(prices),
            'target': self.target_property.get('price_per_sqm', 0) / 1_000_000
        }


@app.route('/')
def index():
    """Главная страница дашборда"""
    return render_template('dashboard.html')


@app.route('/api/analyze', methods=['POST'])
def analyze():
    """API для анализа объекта"""
    data = request.json

    analyzer = RealEstateAnalyzer()

    # Установить целевой объект
    target = data.get('target_property', {})
    analyzer.set_target_property(target)

    # Добавить аналоги
    for comp in data.get('comparables', []):
        analyzer.add_comparable(comp)

    # Выполнить расчеты
    market_stats = analyzer.calculate_market_statistics()
    fair_price = analyzer.calculate_fair_price()
    scenarios = analyzer.generate_price_scenarios()
    strengths_weaknesses = analyzer.calculate_strengths_weaknesses()
    comparison_chart = analyzer.generate_comparison_chart_data()
    box_plot = analyzer.generate_box_plot_data()

    return jsonify({
        'market_statistics': market_stats,
        'fair_price_analysis': fair_price,
        'price_scenarios': scenarios,
        'strengths_weaknesses': strengths_weaknesses,
        'comparison_chart_data': comparison_chart,
        'box_plot_data': box_plot,
        'target_property': analyzer.target_property,
        'version': 'enhanced_v2.0'
    })


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
