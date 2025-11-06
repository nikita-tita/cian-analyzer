"""
Веб-дашборд для анализа недвижимости
Интерактивная визуализация расчетов по объектам
"""

from flask import Flask, render_template, request, jsonify
from typing import Dict, List, Tuple
import statistics
from datetime import datetime, timedelta

app = Flask(__name__)


class RealEstateAnalyzer:
    """Анализатор недвижимости с расчетами и сценариями"""

    def __init__(self):
        self.target_property = {}
        self.comparables = []

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

    def calculate_market_statistics(self) -> Dict:
        """Рассчитать рыночную статистику по аналогам"""
        if not self.comparables:
            return {}

        prices_per_sqm = [c.get('price_per_sqm', 0) for c in self.comparables if c.get('price_per_sqm')]

        # Разделить по типу отделки
        with_design = [c for c in self.comparables if c.get('has_design', False)]
        without_design = [c for c in self.comparables if not c.get('has_design', False)]

        prices_with_design = [c.get('price_per_sqm', 0) for c in with_design if c.get('price_per_sqm')]
        prices_without_design = [c.get('price_per_sqm', 0) for c in without_design if c.get('price_per_sqm')]

        stats = {
            'all': {
                'mean': statistics.mean(prices_per_sqm) if prices_per_sqm else 0,
                'median': statistics.median(prices_per_sqm) if prices_per_sqm else 0,
                'min': min(prices_per_sqm) if prices_per_sqm else 0,
                'max': max(prices_per_sqm) if prices_per_sqm else 0,
                'stdev': statistics.stdev(prices_per_sqm) if len(prices_per_sqm) > 1 else 0,
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
        """Рассчитать справедливую цену методом корректировок"""
        market_stats = self.calculate_market_statistics()

        if not market_stats or not self.target_property:
            return {}

        # Базовая цена (средняя по дизайнерским)
        base_price_per_sqm = market_stats['with_design']['mean']

        if base_price_per_sqm == 0:
            base_price_per_sqm = market_stats['all']['mean']

        # Корректировки
        adjustments = {}
        multiplier = 1.0

        # Размер квартиры
        if self.target_property.get('total_area', 0) > 150:
            adjustments['large_size'] = 1.05
            multiplier *= 1.05

        # Дизайнерская отделка
        if self.target_property.get('has_design', False):
            adjustments['design'] = 1.08
            multiplier *= 1.08

        # Панорамные виды
        if self.target_property.get('panoramic_views', False):
            adjustments['panoramic_views'] = 1.07
            multiplier *= 1.07

        # Премиум локация
        if self.target_property.get('premium_location', False):
            adjustments['premium_location'] = 1.06
            multiplier *= 1.06

        # Низкий процент жилой площади (негатив)
        if self.target_property.get('living_area_percent', 100) < 30:
            adjustments['low_living_area'] = 0.92
            multiplier *= 0.92

        # Рендеры вместо фото (негатив)
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
            'overpricing_percent': overpricing_percent
        }

    def generate_price_scenarios(self) -> List[Dict]:
        """Генерация ценовых сценариев продажи"""
        current_price = self.target_property.get('price', 0)

        scenarios = [
            {
                'name': 'Быстрая продажа',
                'description': 'Агрессивная цена для быстрой реализации',
                'start_price': current_price * 0.95,
                'expected_final_price': current_price * 0.87,
                'time_months': 2,
                'probability': 85,
                'steps': [
                    {'month': 0, 'price': current_price * 0.95},
                    {'month': 1, 'price': current_price * 0.90},
                    {'month': 2, 'price': current_price * 0.87}
                ]
            },
            {
                'name': 'Оптимальная продажа',
                'description': 'Рекомендуемая стратегия с балансом цены и времени',
                'start_price': current_price * 0.95,
                'expected_final_price': current_price * 0.90,
                'time_months': 4,
                'probability': 75,
                'steps': [
                    {'month': 0, 'price': current_price * 0.95},
                    {'month': 1, 'price': current_price * 0.95},
                    {'month': 2, 'price': current_price * 0.92},
                    {'month': 3, 'price': current_price * 0.92},
                    {'month': 4, 'price': current_price * 0.90}
                ]
            },
            {
                'name': 'Стандартная продажа',
                'description': 'Средние сроки с небольшими скидками',
                'start_price': current_price * 0.92,
                'expected_final_price': current_price * 0.85,
                'time_months': 6,
                'probability': 65,
                'steps': [
                    {'month': 0, 'price': current_price * 0.92},
                    {'month': 2, 'price': current_price * 0.90},
                    {'month': 4, 'price': current_price * 0.87},
                    {'month': 6, 'price': current_price * 0.85}
                ]
            },
            {
                'name': 'Попытка максимума',
                'description': 'Ставка на максимальную цену (высокий риск)',
                'start_price': current_price,
                'expected_final_price': current_price * 0.82,
                'time_months': 10,
                'probability': 30,
                'steps': [
                    {'month': 0, 'price': current_price},
                    {'month': 3, 'price': current_price * 0.95},
                    {'month': 6, 'price': current_price * 0.88},
                    {'month': 9, 'price': current_price * 0.85},
                    {'month': 10, 'price': current_price * 0.82}
                ]
            }
        ]

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
        all_properties = [self.target_property] + self.comparables

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

    return jsonify({
        'market_statistics': market_stats,
        'fair_price_analysis': fair_price,
        'price_scenarios': scenarios,
        'strengths_weaknesses': strengths_weaknesses,
        'comparison_chart_data': comparison_chart,
        'target_property': analyzer.target_property
    })


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
