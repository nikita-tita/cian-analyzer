"""
Production-Ready Real Estate Analytics Dashboard
Spotify-inspired UX/UI with enhanced calculations
"""

from flask import Flask, render_template, request, jsonify
from typing import Dict, List, Optional
import statistics
import math
from datetime import datetime
import re

# Импортируем парсер (Playwright version для обхода блокировок)
from cian_parser_playwright import CianParserPlaywright as CianParser

app = Flask(__name__)


class CianDataMapper:
    """
    Маппер данных из парсера Cian в формат дашборда

    Преобразует данные парсинга в структуру для анализатора
    """

    @staticmethod
    def parse_price(price_str: str) -> Optional[float]:
        """
        Парсинг цены из строки

        Examples:
            "195 000 000 ₽" -> 195000000
            "180 млн ₽" -> 180000000
        """
        if not price_str:
            return None

        # Убираем все пробелы и валюту
        clean_price = price_str.replace(' ', '').replace('₽', '').replace(',', '')

        # Проверяем на "млн"
        if 'млн' in clean_price.lower():
            try:
                num = float(clean_price.lower().replace('млн', ''))
                return num * 1_000_000
            except:
                pass

        # Обычное число
        try:
            return float(clean_price)
        except:
            return None

    @staticmethod
    def parse_area(area_str: str) -> Optional[float]:
        """
        Парсинг площади из строки

        Examples:
            "180.4 м²" -> 180.4
            "180,4 м²" -> 180.4
            "Продается 3-комн. квартира, 180,4 м²" -> 180.4
        """
        if not area_str:
            return None

        # Use regex to find number pattern before м² or м
        import re
        match = re.search(r'(\d+[,.]?\d*)\s*(?:м²|м)', area_str)
        if match:
            number_str = match.group(1).replace(',', '.')
            try:
                return float(number_str)
            except:
                return None

        # Fallback to old method for cases without м² marker
        clean = area_str.replace('м²', '').replace('м', '').replace(',', '.').strip()
        try:
            return float(clean)
        except:
            return None

    @staticmethod
    def parse_floor(floor_str: str) -> tuple:
        """
        Парсинг этажа

        Examples:
            "6/7" -> (6, 7)
            "6 из 7" -> (6, 7)
        """
        if not floor_str:
            return (None, None)

        # Варианты: "6/7", "6 из 7", "6-й этаж из 7"
        match = re.search(r'(\d+)\D+(\d+)', floor_str)
        if match:
            return (int(match.group(1)), int(match.group(2)))

        return (None, None)

    @staticmethod
    def parse_rooms(title: str) -> Optional[int]:
        """
        Определение количества комнат из заголовка

        Examples:
            "3-комн. квартира" -> 3
            "Квартира-студия" -> 0
        """
        if not title:
            return None

        # Студия
        if 'студ' in title.lower():
            return 0

        # N-комн
        match = re.search(r'(\d+)-комн', title)
        if match:
            return int(match.group(1))

        return None

    @staticmethod
    def detect_design_quality(description: str, title: str) -> bool:
        """
        Определение наличия дизайнерского ремонта

        Ключевые слова: дизайн, авторск, премиум, элитн, де-люкс
        """
        text = (description or '') + ' ' + (title or '')
        text = text.lower()

        design_keywords = [
            'дизайн', 'авторск', 'премиум', 'элитн',
            'де-люкс', 'deluxe', 'эксклюзив', 'индивидуальн'
        ]

        return any(keyword in text for keyword in design_keywords)

    @staticmethod
    def detect_panoramic_views(description: str, title: str) -> bool:
        """Определение панорамных видов"""
        text = (description or '') + ' ' + (title or '')
        text = text.lower()

        view_keywords = [
            'панорам', 'вид на воду', 'вид на залив', 'вид на реку',
            'на воду', 'на море', 'на парк', 'прекрасный вид'
        ]

        return any(keyword in text for keyword in view_keywords)

    @staticmethod
    def detect_premium_location(address: str) -> bool:
        """Определение премиум локации"""
        if not address:
            return False

        address_lower = address.lower()

        premium_areas = [
            'петровск', 'крестовск', 'каменный остров',
            'центр', 'невский', 'литейный', 'дворцов',
            'петроградск', 'васильевск'
        ]

        return any(area in address_lower for area in premium_areas)

    @staticmethod
    def parse_metro_distance(metro_info) -> Optional[int]:
        """
        Парсинг расстояния до метро

        Args:
            metro_info: Строка или список станций метро

        Examples:
            "7 мин пешком" -> 7
            "10 минут" -> 10
            ["Площадь Восстания • 7 мин"] -> 7
        """
        if not metro_info:
            return None

        # Если список, берем первую станцию
        if isinstance(metro_info, list):
            if not metro_info:
                return None
            metro_info = metro_info[0]

        # Парсим строку
        if isinstance(metro_info, str):
            match = re.search(r'(\d+)\s*мин', metro_info)
            if match:
                return int(match.group(1))

        return None

    @staticmethod
    def detect_renders(description: str) -> bool:
        """Определение, что на фото только рендеры"""
        if not description:
            return False

        text = description.lower()

        render_keywords = [
            'рендер', 'визуализац', 'проект', 'планируется',
            'будет завершен', 'окончание ремонта', 'сдача'
        ]

        return any(keyword in text for keyword in render_keywords)

    @classmethod
    def map_to_target_property(cls, parsed_data: Dict) -> Dict:
        """
        Преобразование данных парсинга в формат дашборда

        Args:
            parsed_data: Данные из CianParser

        Returns:
            Словарь для RealEstateAnalyzer
        """
        title = parsed_data.get('title', '')
        description = parsed_data.get('description', '')
        address = parsed_data.get('address', '')

        # Парсим основные данные
        price = cls.parse_price(parsed_data.get('price'))

        # Площадь может быть в поле area или в title
        total_area = cls.parse_area(parsed_data.get('area'))
        if not total_area and title:
            # Пытаемся извлечь из title (например, "180,4 м²")
            total_area = cls.parse_area(title)

        rooms = cls.parse_rooms(title)
        current_floor, total_floors = cls.parse_floor(parsed_data.get('floor'))

        # Определяем характеристики
        has_design = cls.detect_design_quality(description, title)
        panoramic_views = cls.detect_panoramic_views(description, title)
        premium_location = cls.detect_premium_location(address)
        renders_only = cls.detect_renders(description)
        metro_distance = cls.parse_metro_distance(parsed_data.get('metro', ''))

        # Формируем объект
        target = {
            'price': price,
            'total_area': total_area,
            'rooms': rooms,
            'floor': parsed_data.get('floor'),
            'current_floor': current_floor,
            'total_floors': total_floors,
            'has_design': has_design,
            'panoramic_views': panoramic_views,
            'premium_location': premium_location,
            'renders_only': renders_only,
            'metro_distance_min': metro_distance,

            # Дополнительная информация
            'title': title,
            'description': description,
            'address': address,
            'url': parsed_data.get('url'),
            'images': parsed_data.get('images', []),

            # Параметры по умолчанию (пользователь может уточнить)
            'living_area': None,  # Нужно уточнить
            'build_year': 2020,   # Нужно уточнить
            'house_type': 'монолит',  # По умолчанию для премиума
            'parking': 'подземная' if premium_location else 'нет',
            'ceiling_height': 3.0 if has_design else 2.7,
            'security_247': premium_location,
            'has_elevator': True if total_floors and total_floors > 5 else False
        }

        # Убираем None значения
        return {k: v for k, v in target.items() if v is not None}


class RealEstateAnalyzer:
    """
    Production-grade анализатор недвижимости

    Features:
    - Фильтрация выбросов (±3σ)
    - Медиана для базовой цены
    - 14 коэффициентов корректировки
    - Финансовые расчеты
    - Кумулятивная вероятность
    - Детальные траектории (14 точек)
    """

    def __init__(self):
        self.target_property = {}
        self.comparables = []
        self.filtered_comparables = []

    def set_target_property(self, data: Dict):
        """Установить целевой объект"""
        self.target_property = data
        self._calculate_derived_metrics()

    def add_comparable(self, data: Dict):
        """Добавить аналог"""
        if 'price_per_sqm' not in data and 'price' in data and 'total_area' in data:
            data['price_per_sqm'] = data['price'] / data['total_area']
        self.comparables.append(data)

    def _calculate_derived_metrics(self):
        """Рассчитать производные метрики"""
        if 'price' in self.target_property and 'total_area' in self.target_property:
            self.target_property['price_per_sqm'] = (
                self.target_property['price'] / self.target_property['total_area']
            )

        if 'living_area' in self.target_property and 'total_area' in self.target_property:
            self.target_property['living_area_percent'] = (
                self.target_property['living_area'] / self.target_property['total_area'] * 100
            )

    def filter_outliers(self) -> List[Dict]:
        """
        Фильтрация выбросов ±3σ
        """
        if not self.comparables:
            return []

        prices_per_sqm = [c.get('price_per_sqm', 0) for c in self.comparables if c.get('price_per_sqm')]

        if len(prices_per_sqm) < 2:
            return self.comparables

        mean = statistics.mean(prices_per_sqm)
        stdev = statistics.stdev(prices_per_sqm)

        filtered = [
            c for c in self.comparables
            if abs(c.get('price_per_sqm', mean) - mean) <= 3 * stdev
        ]

        self.filtered_comparables = filtered
        return filtered

    def calculate_market_statistics(self) -> Dict:
        """Рыночная статистика с медианой"""
        filtered = self.filter_outliers()

        if not filtered:
            return {}

        prices_per_sqm = [c.get('price_per_sqm', 0) for c in filtered if c.get('price_per_sqm')]

        with_design = [c for c in filtered if c.get('has_design', False)]
        without_design = [c for c in filtered if not c.get('has_design', False)]

        prices_with_design = [c.get('price_per_sqm', 0) for c in with_design if c.get('price_per_sqm')]
        prices_without_design = [c.get('price_per_sqm', 0) for c in without_design if c.get('price_per_sqm')]

        return {
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

    def calculate_fair_price(self) -> Dict:
        """Справедливая цена с 14 коэффициентами"""
        market_stats = self.calculate_market_statistics()

        if not market_stats or not self.target_property:
            return {}

        # Медиана вместо среднего
        base_price_per_sqm = market_stats['with_design']['median']

        if base_price_per_sqm == 0:
            base_price_per_sqm = market_stats['all']['median']

        adjustments = {}
        multiplier = 1.0

        # === ПОЛОЖИТЕЛЬНЫЕ КОРРЕКТИРОВКИ ===

        # 1. Размер квартиры (+0-5%)
        if self.target_property.get('total_area', 0) > 150:
            coef = 1 + ((self.target_property['total_area'] / 150) - 1) * 0.10
            coef = min(coef, 1.05)
            adjustments['large_size'] = coef
            multiplier *= coef

        # 2. Дизайнерская отделка (+8%)
        if self.target_property.get('has_design', False):
            adjustments['design'] = 1.08
            multiplier *= 1.08

        # 3. Панорамные виды (+7%)
        if self.target_property.get('panoramic_views', False):
            adjustments['panoramic_views'] = 1.07
            multiplier *= 1.07

        # 4. Расстояние до метро (+0-6%)
        metro_distance = self.target_property.get('metro_distance_min', 10)
        if metro_distance <= 7:
            coef = 1 + (7 - metro_distance) / 7 * 0.06
            adjustments['metro_proximity'] = coef
            multiplier *= coef

        # 5. Премиум локация (+6%)
        if self.target_property.get('premium_location', False):
            adjustments['premium_location'] = 1.06
            multiplier *= 1.06

        # 6. Тип дома (+5% или -5%)
        house_type = self.target_property.get('house_type', 'кирпич')
        if house_type == 'монолит':
            adjustments['house_type'] = 1.05
            multiplier *= 1.05
        elif house_type == 'панель':
            adjustments['house_type'] = 0.95
            multiplier *= 0.95

        # 7. Парковка (+3-4%)
        parking = self.target_property.get('parking', 'нет')
        if parking == 'подземная':
            adjustments['parking'] = 1.04
            multiplier *= 1.04
        elif parking == 'закрытая':
            adjustments['parking'] = 1.03
            multiplier *= 1.03

        # 8. Высота потолков (+0-3%)
        ceiling_height = self.target_property.get('ceiling_height', 2.7)
        if ceiling_height >= 3.0:
            coef = 1 + (ceiling_height - 2.7) / 0.5 * 0.03
            adjustments['ceiling_height'] = coef
            multiplier *= coef

        # 9. Охрана 24/7 (+3%)
        if self.target_property.get('security_247', False):
            adjustments['security'] = 1.03
            multiplier *= 1.03

        # 10. Лифт (+3%)
        if self.target_property.get('has_elevator', True):
            adjustments['elevator'] = 1.03
            multiplier *= 1.03

        # === НЕГАТИВНЫЕ КОРРЕКТИРОВКИ ===

        # 11. Низкая жилая площадь (-0-8%)
        living_percent = self.target_property.get('living_area_percent', 100)
        if living_percent < 30:
            coef = 1 - (30 - living_percent) / 30 * 0.08
            coef = max(coef, 0.92)
            adjustments['low_living_area'] = coef
            multiplier *= coef

        # 12. Возраст дома (-0-5%)
        build_year = self.target_property.get('build_year', 2020)
        current_year = datetime.now().year
        age = current_year - build_year
        if age > 10:
            coef = 1 - (age - 10) / 100 * 0.05
            coef = max(coef, 0.95)
            adjustments['building_age'] = coef
            multiplier *= coef

        # 13. Неликвидность (-4%)
        if self.target_property.get('price', 0) > 150_000_000:
            adjustments['high_price'] = 0.96
            multiplier *= 0.96

        # 14. Рендеры (-3%)
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
            'method': 'median'
        }

    def calculate_price_trajectory(self, start_price: float, reduction_rate: float, months: int = 14) -> List[Dict]:
        """Траектория цены по месяцам"""
        trajectory = []
        for month in range(months):
            price = start_price * math.pow(1 - reduction_rate, month)
            trajectory.append({
                'month': month,
                'price': price
            })
        return trajectory

    def calculate_monthly_probability(self, scenario_type: str, fair_price: float, start_price: float) -> List[float]:
        """Месячная вероятность продажи"""
        price_ratio = start_price / fair_price if fair_price > 0 else 1.0

        if scenario_type == 'fast':
            base_prob = [0.45, 0.70, 0.75, 0.75, 0.73, 0.70, 0.68, 0.65, 0.62, 0.60, 0.58, 0.55, 0.53, 0.50]
        elif scenario_type == 'optimal':
            base_prob = [0.40, 0.65, 0.70, 0.72, 0.70, 0.68, 0.65, 0.62, 0.60, 0.57, 0.55, 0.52, 0.50, 0.48]
        elif scenario_type == 'standard':
            base_prob = [0.35, 0.55, 0.60, 0.65, 0.63, 0.60, 0.57, 0.54, 0.51, 0.48, 0.45, 0.42, 0.40, 0.38]
        elif scenario_type == 'maximum':
            base_prob = [0.15, 0.20, 0.20, 0.18, 0.15, 0.12, 0.10, 0.08, 0.07, 0.06, 0.05, 0.05, 0.04, 0.04]
        else:
            base_prob = [0.50] * 14

        if price_ratio > 1.1:
            adjustment = 0.7
        elif price_ratio > 1.05:
            adjustment = 0.85
        elif price_ratio < 0.95:
            adjustment = 1.15
        else:
            adjustment = 1.0

        return [min(p * adjustment, 0.98) for p in base_prob]

    def calculate_cumulative_probability(self, monthly_probabilities: List[float]) -> List[float]:
        """Кумулятивная вероятность"""
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
        """Финансовый расчет"""
        commission = sale_price * commission_rate
        taxes = sale_price * tax_rate
        other = sale_price * other_expenses
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
        """4 сценария продажи"""
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
                'reduction_rate': 0.015
            },
            {
                'name': 'Оптимальная продажа',
                'type': 'optimal',
                'description': 'Рекомендуемая стратегия с балансом цены и времени',
                'start_price': current_price * 0.95,
                'expected_final_price': current_price * 0.90,
                'time_months': 4,
                'base_probability': 75,
                'reduction_rate': 0.012
            },
            {
                'name': 'Стандартная продажа',
                'type': 'standard',
                'description': 'Средние сроки с небольшими скидками',
                'start_price': current_price * 0.92,
                'expected_final_price': current_price * 0.85,
                'time_months': 6,
                'base_probability': 65,
                'reduction_rate': 0.020
            },
            {
                'name': 'Попытка максимума',
                'type': 'maximum',
                'description': 'Ставка на максимальную цену (высокий риск)',
                'start_price': current_price,
                'expected_final_price': current_price * 0.82,
                'time_months': 10,
                'base_probability': 30,
                'reduction_rate': 0.025
            }
        ]

        for scenario in scenarios:
            scenario['price_trajectory'] = self.calculate_price_trajectory(
                scenario['start_price'],
                scenario['reduction_rate'],
                14
            )

            scenario['monthly_probability'] = self.calculate_monthly_probability(
                scenario['type'],
                fair_price,
                scenario['start_price']
            )

            scenario['cumulative_probability'] = self.calculate_cumulative_probability(
                scenario['monthly_probability']
            )

            scenario['financials'] = self.calculate_financials(
                scenario['expected_final_price'],
                scenario['time_months']
            )

        return scenarios

    def generate_comparison_chart_data(self) -> Dict:
        """Данные для графика сравнения"""
        all_properties = [self.target_property] + (self.filtered_comparables or self.comparables)

        labels = []
        prices_per_sqm = []
        colors = []

        for i, prop in enumerate(all_properties):
            if i == 0:
                labels.append('ЦЕЛЕВОЙ')
                colors.append('rgba(255, 68, 68, 0.8)')
            else:
                labels.append(f'Аналог {i}')
                colors.append('rgba(29, 185, 84, 0.8)')

            price_per_sqm = prop.get('price_per_sqm', 0) / 1_000_000
            prices_per_sqm.append(price_per_sqm)

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

        if self.target_property.get('security_247'):
            strengths.append({
                'factor': 'Охрана 24/7',
                'impact': 3,
                'premium_percent': 3
            })

        if self.target_property.get('parking') in ['подземная', 'гараж']:
            strengths.append({
                'factor': 'Паркинг',
                'impact': 4,
                'premium_percent': 4
            })

        if self.target_property.get('ceiling_height', 0) >= 3.0:
            strengths.append({
                'factor': 'Высокие потолки',
                'impact': 3,
                'premium_percent': 3
            })

        # Слабые стороны
        if self.target_property.get('living_area') and self.target_property.get('total_area'):
            living_percent = (self.target_property['living_area'] / self.target_property['total_area']) * 100
            if living_percent < 60:
                weaknesses.append({
                    'factor': 'Низкий процент жилой площади',
                    'impact': 5,
                    'discount_percent': 5
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

        if self.target_property.get('metro_distance_min', 0) > 15:
            weaknesses.append({
                'factor': 'Далеко от метро',
                'impact': 3,
                'discount_percent': 3
            })

        if not self.target_property.get('has_elevator') and self.target_property.get('current_floor', 0) > 3:
            weaknesses.append({
                'factor': 'Нет лифта + высокий этаж',
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

    def generate_box_plot_data(self) -> Dict:
        """
        Генерация данных для box-plot

        Returns:
            Данные для построения "ящика с усами"
        """
        filtered = self.filtered_comparables or self.comparables
        prices = [c.get('price_per_sqm', 0) / 1_000_000 for c in filtered if c.get('price_per_sqm')]

        if not prices:
            return {
                'min': 0,
                'q1': 0,
                'median': 0,
                'q3': 0,
                'max': 0,
                'target': 0
            }

        prices.sort()
        n = len(prices)

        q1_index = n // 4
        q2_index = n // 2
        q3_index = 3 * n // 4

        target_price_per_sqm = self.target_property.get('price_per_sqm', 0) / 1_000_000

        return {
            'min': prices[0],
            'q1': prices[q1_index],
            'median': prices[q2_index],
            'q3': prices[q3_index],
            'max': prices[-1],
            'target': target_price_per_sqm,
            'mean': sum(prices) / len(prices) if prices else 0
        }


@app.route('/')
def index():
    """Production dashboard"""
    return render_template('dashboard_pro.html')


@app.route('/api/parse-cian', methods=['POST'])
def parse_cian_url():
    """
    Парсинг объявления Cian по URL

    POST data:
        {
            "url": "https://spb.cian.ru/sale/flat/123456/"
        }

    Returns:
        {
            "success": true,
            "target_property": {...},
            "missing_fields": [...]
        }
    """
    data = request.json
    url = data.get('url')

    if not url:
        return jsonify({
            'success': False,
            'error': 'URL не указан'
        }), 400

    try:
        # Инициализируем парсер
        parser = CianParser(delay=1.0)

        # Парсим объявление
        parsed_data = parser.parse_detail_page(url)

        if not parsed_data:
            return jsonify({
                'success': False,
                'error': 'Не удалось спарсить объявление'
            }), 400

        # Преобразуем в формат дашборда
        mapper = CianDataMapper()
        target_property = mapper.map_to_target_property(parsed_data)

        # Определяем недостающие поля
        required_fields = {
            'price': 'Цена',
            'total_area': 'Общая площадь',
            'living_area': 'Жилая площадь',
            'rooms': 'Количество комнат',
            'build_year': 'Год постройки'
        }

        missing_fields = []
        for field, label in required_fields.items():
            if field not in target_property or target_property[field] is None:
                missing_fields.append({
                    'field': field,
                    'label': label
                })

        return jsonify({
            'success': True,
            'target_property': target_property,
            'missing_fields': missing_fields,
            'parsed_data': parsed_data  # Для отладки
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Ошибка парсинга: {str(e)}'
        }), 500


@app.route('/api/search-comparables', methods=['POST'])
def search_comparables():
    """
    Автоматический поиск аналогов для целевого объекта

    POST data:
        {
            "target_property": {
                "price": 195000000,
                "total_area": 180.4,
                "rooms": 3
            },
            "limit": 20
        }

    Returns:
        {
            "success": true,
            "comparables": [...],
            "count": 15
        }
    """
    data = request.json
    target_property = data.get('target_property')
    limit = data.get('limit', 20)

    if not target_property:
        return jsonify({
            'success': False,
            'error': 'Целевой объект не указан'
        }), 400

    try:
        # Ищем похожие квартиры
        parser = CianParser(delay=1.0)
        search_results = parser.search_similar(target_property, limit=limit)

        # Преобразуем в формат дашборда
        mapper = CianDataMapper()
        comparables = []

        for result in search_results:
            comp = mapper.map_to_target_property(result)
            # Добавляем price_per_sqm
            if comp.get('price') and comp.get('total_area'):
                comp['price_per_sqm'] = comp['price'] / comp['total_area']
            comparables.append(comp)

        return jsonify({
            'success': True,
            'comparables': comparables,
            'count': len(comparables),
            'search_criteria': {
                'price_range': f"{target_property.get('price', 0) * 0.5:.0f} - {target_property.get('price', 0) * 1.5:.0f}",
                'area_range': f"{target_property.get('total_area', 0) * 0.6:.0f} - {target_property.get('total_area', 0) * 1.4:.0f}",
                'rooms': target_property.get('rooms', 0)
            }
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Ошибка поиска аналогов: {str(e)}'
        }), 500


@app.route('/api/analyze', methods=['POST'])
def analyze():
    """API endpoint для анализа"""
    try:
        data = request.json

        if not data or 'target_property' not in data:
            return jsonify({
                'error': 'Целевой объект не указан'
            }), 400

        analyzer = RealEstateAnalyzer()
        analyzer.set_target_property(data['target_property'])

        for comp in data.get('comparables', []):
            analyzer.add_comparable(comp)

        market_stats = analyzer.calculate_market_statistics()
        fair_price = analyzer.calculate_fair_price()
        scenarios = analyzer.generate_price_scenarios()
        comparison_chart = analyzer.generate_comparison_chart_data()
        strengths_weaknesses = analyzer.calculate_strengths_weaknesses()
        box_plot = analyzer.generate_box_plot_data()

        return jsonify({
            'market_statistics': market_stats,
            'fair_price_analysis': fair_price,
            'price_scenarios': scenarios,
            'comparison_chart_data': comparison_chart,
            'strengths_weaknesses': strengths_weaknesses,
            'box_plot_data': box_plot,
            'target_property': analyzer.target_property,
            'version': 'production_v1.0'
        })

    except Exception as e:
        return jsonify({
            'error': str(e)
        }), 500


if __name__ == '__main__':
    # Production settings
    app.run(
        debug=False,  # Выключаем debug в production
        host='0.0.0.0',
        port=5003,
        threaded=True
    )
