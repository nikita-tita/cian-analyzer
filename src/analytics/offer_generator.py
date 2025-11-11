"""
Генератор персонализированных офферов Housler

Создает адаптивное предложение на основе анализа объекта:
- Цена и ценовой диапазон
- Статус цены (завышена/занижена)
- Проблемы и рекомендации
- Характеристики объекта
"""

from typing import Dict, List, Optional


class HouslerOfferGenerator:
    """Генератор персонализированных офферов для продажи недвижимости"""

    def __init__(self, analysis: Dict, property_info: Dict, recommendations: List[Dict]):
        self.analysis = analysis
        self.property_info = property_info
        self.recommendations = recommendations

    def generate_offer(self) -> Dict:
        """
        Генерирует персонализированный оффер

        Returns:
            Dict с полями:
            - situation: текущая ситуация с объектом
            - goal: что хотим достичь
            - actions: список действий которые сделаем
            - result: ожидаемый результат
            - price_tier: ценовой диапазон для тарифа
            - commission_option: вариант оплаты
            - prepay_option: вариант с предоплатой
        """
        price = self.property_info.get('price', 0)
        fair_price_analysis = self.analysis.get('fair_price_analysis', {})

        # Определяем ценовой диапазон
        price_tier = self._get_price_tier(price)

        # Анализируем ситуацию
        situation = self._analyze_situation(fair_price_analysis)

        # Определяем цель
        goal = self._determine_goal(fair_price_analysis, situation)

        # Составляем план действий
        actions = self._build_action_plan(situation)

        # Прогнозируем результат
        result = self._predict_result(fair_price_analysis, situation)

        # Варианты оплаты
        commission_option, prepay_option = self._get_payment_options(price_tier)

        return {
            'situation': situation,
            'goal': goal,
            'actions': actions,
            'result': result,
            'price_tier': price_tier,
            'commission_option': commission_option,
            'prepay_option': prepay_option,
            'timeline': self._estimate_timeline(situation)
        }

    def _get_price_tier(self, price: float) -> Dict:
        """Определяет ценовой диапазон объекта"""
        price_millions = price / 1_000_000

        if price_millions < 25:
            return {
                'range': 'до 25 млн ₽',
                'tier': 'basic',
                'commission': '2%',
                'prepay': '100 000 ₽',
                'success_fee': '1%'
            }
        elif price_millions < 50:
            return {
                'range': '25-50 млн ₽',
                'tier': 'standard',
                'commission': '2%',
                'prepay': '200 000 ₽',
                'success_fee': '1%'
            }
        else:
            return {
                'range': '50+ млн ₽',
                'tier': 'premium',
                'commission': '2%',
                'prepay': '500 000 ₽',
                'success_fee': '1%'
            }

    def _analyze_situation(self, fair_price_analysis: Dict) -> Dict:
        """Анализирует текущую ситуацию с объектом"""
        status = fair_price_analysis.get('status', 'normal')
        current_price = fair_price_analysis.get('current_price', 0)
        fair_price = fair_price_analysis.get('fair_price', current_price)
        diff_percent = fair_price_analysis.get('difference_percent', 0)

        # Критичные проблемы
        critical_issues = [
            rec for rec in self.recommendations
            if rec.get('priority') == 1
        ]

        # Проблемы с презентацией
        presentation_issues = self._check_presentation_issues()

        return {
            'price_status': status,
            'price_diff_percent': diff_percent,
            'current_price': current_price,
            'fair_price': fair_price,
            'critical_issues': critical_issues,
            'presentation_issues': presentation_issues,
            'has_critical': len(critical_issues) > 0,
            'needs_staging': presentation_issues.get('needs_staging', False),
            'needs_photos': presentation_issues.get('needs_photos', False)
        }

    def _check_presentation_issues(self) -> Dict:
        """Проверяет проблемы с презентацией объекта"""
        repair = self.property_info.get('repair', '')

        needs_staging = repair in ['без отделки', 'косметический', '']
        needs_photos = True  # По умолчанию всегда рекомендуем проф фото
        needs_video = self.property_info.get('price', 0) > 30_000_000

        return {
            'needs_staging': needs_staging,
            'needs_photos': needs_photos,
            'needs_video': needs_video,
            'repair_level': repair
        }

    def _determine_goal(self, fair_price_analysis: Dict, situation: Dict) -> str:
        """Определяет главную цель"""
        status = situation['price_status']
        diff = abs(situation['price_diff_percent'])

        if status == 'overpriced' and diff > 10:
            return f"Продать объект по справедливой цене {self._format_price(situation['fair_price'])}, несмотря на текущую завышенную стоимость"
        elif status == 'underpriced':
            return f"Продать объект быстро и выгодно, используя конкурентное преимущество в цене"
        elif situation['has_critical']:
            return "Устранить критичные проблемы и продать объект в оптимальные сроки"
        else:
            return "Продать объект максимально быстро с помощью агрессивного маркетинга"

    def _build_action_plan(self, situation: Dict) -> List[Dict]:
        """Составляет персонализированный план действий"""
        actions = []

        # 1. Диагностика (всегда первый шаг)
        actions.append({
            'icon': '🔍',
            'title': 'Диагностика объекта',
            'description': 'Выезд специалиста, оценка состояния, выявление скрытых проблем'
        })

        # 2. Ценовое позиционирование
        if situation['price_status'] == 'overpriced':
            actions.append({
                'icon': '💰',
                'title': 'Корректировка ценовой стратегии',
                'description': f"Снижение цены до справедливой ({self._format_price(situation['fair_price'])}) или агрессивный маркетинг текущей цены"
            })
        elif situation['price_status'] == 'underpriced':
            actions.append({
                'icon': '💰',
                'title': 'Использование конкурентного преимущества',
                'description': 'Акцент на выгодной цене в рекламе, быстрый выход на рынок'
            })

        # 3. Стейджинг (если нужен)
        if situation['presentation_issues']['needs_staging']:
            actions.append({
                'icon': '🎨',
                'title': 'Лайт-стейджинг',
                'description': 'Косметические улучшения, расстановка мебели, декор для презентабельного вида'
            })

        # 4. Фото/видео (всегда)
        if situation['presentation_issues']['needs_video']:
            actions.append({
                'icon': '📸',
                'title': 'Премиум фото + видео + 3D-тур',
                'description': 'Профессиональная съемка, видео-тур, интерактивный 3D-тур для онлайн просмотра'
            })
        else:
            actions.append({
                'icon': '📸',
                'title': 'Профессиональная фотосессия',
                'description': 'Качественные фото объекта с правильным светом и ракурсами'
            })

        # 5. Размещение (всегда)
        actions.append({
            'icon': '📱',
            'title': 'Размещение на топ площадках',
            'description': 'ЦИАН, Авито с ежедневными подъемами в топ, оптимизация объявления'
        })

        # 6. Локальный маркетинг
        actions.append({
            'icon': '📢',
            'title': 'PR в районе',
            'description': 'Посты в соцсетях района, чаты жителей, местные паблики'
        })

        # 7. Контент-маркетинг (для дорогих объектов)
        if self.property_info.get('price', 0) > 30_000_000:
            actions.append({
                'icon': '🎬',
                'title': 'Контент-продвижение',
                'description': 'Рилсы для Instagram/TikTok, Stories, профессиональный видео-обзор'
            })

        # 8. Таргетинг
        actions.append({
            'icon': '🎯',
            'title': 'Таргетированная реклама',
            'description': 'Показы объекта целевой аудитории через соцсети и поисковые системы'
            })

        # 9. Еженедельные отчеты
        actions.append({
            'icon': '📊',
            'title': 'Прозрачность процесса',
            'description': 'Еженедельные отчеты: просмотры, звонки, показы, корректировки стратегии'
        })

        return actions

    def _predict_result(self, fair_price_analysis: Dict, situation: Dict) -> Dict:
        """Прогнозирует результат"""
        status = situation['price_status']

        if status == 'overpriced':
            timeline = '14-30 дней после корректировки цены'
            final_price = situation['fair_price']
        elif status == 'underpriced':
            timeline = '7-14 дней'
            final_price = situation['current_price']
        else:
            timeline = '10-20 дней'
            final_price = situation['current_price']

        return {
            'timeline': timeline,
            'final_price': final_price,
            'final_price_formatted': self._format_price(final_price),
            'confidence': 'высокая' if status != 'overpriced' else 'средняя'
        }

    def _estimate_timeline(self, situation: Dict) -> str:
        """Оценивает сроки продажи"""
        if situation['price_status'] == 'underpriced':
            return '7-14 дней'
        elif situation['price_status'] == 'overpriced':
            return '14-30 дней'
        else:
            return '10-20 дней'

    def _get_payment_options(self, price_tier: Dict) -> tuple:
        """Возвращает варианты оплаты"""
        commission_option = {
            'type': 'Комиссия',
            'value': price_tier['commission'],
            'description': 'Без предоплат. Оплата в день сделки.'
        }

        prepay_option = {
            'type': 'Предоплата + успех',
            'prepay': price_tier['prepay'],
            'success_fee': price_tier['success_fee'],
            'description': f"{price_tier['prepay']} предоплата + {price_tier['success_fee']} при продаже. Возврат, если не продадим."
        }

        return commission_option, prepay_option

    def _format_price(self, price: float) -> str:
        """Форматирует цену"""
        millions = price / 1_000_000
        if millions >= 1:
            return f"{millions:.1f} млн ₽"
        else:
            thousands = price / 1_000
            return f"{thousands:.0f} тыс ₽"


def generate_housler_offer(analysis: Dict, property_info: Dict, recommendations: List[Dict]) -> Dict:
    """
    Главная функция для генерации персонализированного оффера

    Args:
        analysis: результаты анализа объекта
        property_info: информация об объекте
        recommendations: список рекомендаций

    Returns:
        Dict с персонализированным оффером
    """
    generator = HouslerOfferGenerator(analysis, property_info, recommendations)
    return generator.generate_offer()
