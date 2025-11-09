"""
Экспорт логов обработки объектов в Markdown формат
"""

from typing import List, Dict, Any
from datetime import datetime
from .property_tracker import PropertyLog, PropertyTracker, EventType


class MarkdownExporter:
    """
    Экспорт логов обработки в читаемый и действенный отчёт
    """

    def __init__(self):
        pass

    def format_number(self, value: Any) -> str:
        """Форматирование чисел"""
        if isinstance(value, (int, float)):
            if value > 1_000_000:
                return f"{value:,.0f} ₽"
            elif value > 1000:
                return f"{value:,.2f}"
            else:
                return f"{value:.4f}"
        return str(value)

    def format_price_millions(self, value: float) -> str:
        """Форматирование в миллионах"""
        return f"{value / 1_000_000:.1f}M"

    def export_single_property(self, log: PropertyLog) -> str:
        """Экспорт одного объекта в Markdown"""
        md = []

        # =========================================================================
        # ЗАГОЛОВОК
        # =========================================================================
        md.append("# Отчет по объекту недвижимости")
        md.append("")

        if log.url:
            md.append(f"Ссылка: [{log.url}]({log.url})")
            md.append("")

        md.append(f"Дата создания: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        md.append("")
        md.append("---")
        md.append("")

        # =========================================================================
        # 1. EXECUTIVE SUMMARY - Главные выводы за 30 секунд
        # =========================================================================
        md.append("## Главные выводы")
        md.append("")

        # Извлекаем данные
        current_price = log.property_info.get('price', 0) if log.property_info else 0
        fair_price = log.fair_price_result.get('fair_price_total', 0) if log.fair_price_result else current_price
        price_diff = log.fair_price_result.get('price_diff_percent', 0) if log.fair_price_result else 0
        is_overpriced = log.fair_price_result.get('is_overpriced', False) if log.fair_price_result else False
        is_underpriced = log.fair_price_result.get('is_underpriced', False) if log.fair_price_result else False
        is_fair = log.fair_price_result.get('is_fair', False) if log.fair_price_result else False

        expected_time = log.time_forecast.get('expected_time_months', 0) if hasattr(log, 'time_forecast') and log.time_forecast else 3
        time_range = log.time_forecast.get('time_range_description', '2-4 месяца') if hasattr(log, 'time_forecast') and log.time_forecast else '2-4 месяца'

        attractiveness = log.attractiveness_index.get('total_index', 0) if hasattr(log, 'attractiveness_index') and log.attractiveness_index else 0
        attr_category = log.attractiveness_index.get('category', 'Средняя') if hasattr(log, 'attractiveness_index') and log.attractiveness_index else 'Средняя'

        # Статус цены
        if is_fair:
            price_status = f"**Цена СПРАВЕДЛИВАЯ** (в рыночном диапазоне, {price_diff:+.1f}%)"
        elif is_overpriced:
            price_status = f"**Цена ЗАВЫШЕНА** на {abs(price_diff):.1f}%"
        elif is_underpriced:
            price_status = f"**Цена ЗАНИЖЕНА** на {abs(price_diff):.1f}%"
        else:
            price_status = "Цена близка к рыночной"

        md.append(f"**Ваша квартира:**")
        md.append(f"- {price_status}")
        md.append(f"- Справедливая цена: {self.format_price_millions(fair_price)} ({self.format_number(fair_price)})")
        md.append(f"- Текущая цена: {self.format_price_millions(current_price)} ({self.format_number(current_price)})")
        md.append(f"- Прогноз продажи: {time_range}")
        md.append(f"- Привлекательность: {attractiveness:.0f}/100 ({attr_category})")
        md.append("")

        # Рекомендации
        md.append("**Что делать прямо сейчас:**")

        # Рекомендация 1 - в зависимости от цены
        if is_overpriced and abs(price_diff) > 5:
            md.append(f"1. **Скорректировать цену** до {self.format_price_millions(fair_price)} для реалистичных ожиданий")
        elif is_underpriced and abs(price_diff) > 5:
            md.append(f"1. **Можно поднять цену** до {self.format_price_millions(fair_price)} без риска потерять покупателей")
        else:
            md.append("1. **Цена хорошая** - оставить как есть")

        # Рекомендация 2 - всегда про презентацию
        md.append("2. **Профессиональные фото обязательны** - без них теряете 60% покупателей еще до показа")

        # Рекомендация 3 - в зависимости от привлекательности
        if attractiveness < 60:
            md.append("3. **Усилить продвижение** - конкуренция высокая, нужна активная реклама")
        else:
            md.append("3. **Подготовить 2-3 главных преимущества** для описания объявления")

        md.append("")
        md.append("Детальный план действий смотрите в разделе \"План продажи\" ниже.")
        md.append("")
        md.append("---")
        md.append("")

        # =========================================================================
        # 2. РЫНОЧНЫЙ КОНТЕКСТ - Где вы на рынке
        # =========================================================================
        md.append("## Ваш объект на фоне рынка")
        md.append("")

        # Рыночная статистика
        comparables_count = len(log.comparables_data) if log.comparables_data else 0
        median_price_sqm = 0

        if log.market_stats:
            # Поддержка двух форматов: вложенный 'all' или прямые поля
            if 'all' in log.market_stats:
                all_stats = log.market_stats['all']
                median_price_sqm = all_stats.get('median', 0)
                mean_price_sqm = all_stats.get('mean', 0)
            else:
                # Fallback для прямых полей
                median_price_sqm = log.market_stats.get('median_price_per_sqm', 0)
                mean_price_sqm = log.market_stats.get('mean_price_per_sqm', 0)

        your_price_sqm = current_price / log.property_info.get('total_area', 50) if log.property_info and current_price > 0 else 0

        md.append("**Что происходит в вашем районе:**")
        md.append(f"- Средняя цена за м²: {self.format_number(median_price_sqm)} (рыночная медиана)")
        if your_price_sqm > 0:
            diff_from_market = ((your_price_sqm - median_price_sqm) / median_price_sqm * 100) if median_price_sqm > 0 else 0
            if abs(diff_from_market) < 3:
                md.append(f"- Ваша цена за м²: {self.format_number(your_price_sqm)} (соответствует рынку)")
            elif diff_from_market > 0:
                md.append(f"- Ваша цена за м²: {self.format_number(your_price_sqm)} (на {diff_from_market:.1f}% выше рынка)")
            else:
                md.append(f"- Ваша цена за м²: {self.format_number(your_price_sqm)} (на {abs(diff_from_market):.1f}% ниже рынка - хороший шанс быстро продать)")

        md.append(f"- Похожих объектов в продаже: {comparables_count}")
        md.append(f"- Среднее время продажи: {expected_time:.1f} месяца")
        md.append("")

        # Интерпретация позиции
        md.append("**Ваша позиция:**")

        if is_underpriced and abs(price_diff) > 3:
            md.append(f"- Ваша цена НИЖЕ медианы на {abs(price_diff):.1f}% - отличный шанс быстро продать")
            md.append(f"- При текущей цене ожидайте повышенный интерес покупателей")
        elif is_overpriced and abs(price_diff) > 5:
            md.append(f"- Ваша цена ВЫШЕ медианы на {abs(price_diff):.1f}% - риск долгой продажи")
            md.append(f"- Конкуренция с {comparables_count} объектами - покупатели будут сравнивать")
        else:
            md.append(f"- Ваша цена соответствует рынку - оптимально для продажи за {time_range}")
            md.append(f"- Конкуренция умеренная ({comparables_count} объектов)")

        md.append("")

        # Инсайт
        if comparables_count > 20:
            md.append(f"> **Инсайт:** Высокая конкуренция ({comparables_count} объектов) означает, что покупатели избирательны.")
            md.append("> Ключ к успеху: выделиться качественной презентацией и уникальными преимуществами.")
        elif comparables_count < 10:
            md.append(f"> **Инсайт:** Низкая конкуренция ({comparables_count} объектов) - у вас хорошие шансы привлечь внимание покупателей.")
            md.append("> Важно: не завышать цену, чтобы не отпугнуть редких покупателей в вашем сегменте.")

        md.append("")
        md.append("---")
        md.append("")

        # =========================================================================
        # 3. ВАША СИТУАЦИЯ - Риски и возможности
        # =========================================================================
        md.append("## Что может помешать продаже и как это исправить")
        md.append("")

        # Анализируем риски на основе данных
        risks = []
        opportunities = []

        # Риск 1: Цена
        if is_overpriced and abs(price_diff) > 5:
            risks.append({
                'title': 'Завышенная цена',
                'description': f'При цене на {abs(price_diff):.1f}% выше рынка продажа займет {expected_time:.0f}+ месяцев. Покупатели увидят "долго висит" и будут агрессивно торговаться.',
                'solution': f'Снизить до {self.format_price_millions(fair_price)} для реалистичных ожиданий'
            })

        # Риск 2: Привлекательность
        if attractiveness < 60:
            risks.append({
                'title': 'Низкая привлекательность объекта',
                'description': f'Индекс {attractiveness:.0f}/100 означает, что объект проигрывает конкурентам по ключевым параметрам.',
                'solution': 'Компенсировать профессиональной презентацией: качественные фото, виртуальный тур, подчеркнуть уникальные преимущества'
            })

        # Риск 3: Презентация (всегда актуален)
        risks.append({
            'title': 'Плохая презентация',
            'description': 'Без профессиональных фото и продающего описания теряете 60% покупателей до первого показа.',
            'solution': 'Инвестировать 5,000-10,000₽ в профессиональную фотосъемку (окупится ценой)'
        })

        # Возможность 1: Быстрая продажа
        if is_underpriced or (is_fair and attractiveness > 70):
            fast_price = current_price * 0.95
            opportunities.append({
                'title': 'Быстрая продажа (1-2 месяца)',
                'description': f'При цене {self.format_price_millions(fast_price)} с активным продвижением можете продать за 3-4 недели.',
                'benefit': 'Экономия времени, быстрое получение денег'
            })

        # Возможность 2: Максимальная цена
        if hasattr(log, 'price_range') and log.price_range:
            max_price = log.price_range.get('max_price', 0)
            if max_price > fair_price * 1.03:
                opportunities.append({
                    'title': 'Максимальная цена',
                    'description': f'При идеальной подготовке (стейджинг, профессиональное фото, активное продвижение) можете продать за {self.format_price_millions(max_price)}.',
                    'benefit': f'Дополнительно +{self.format_price_millions(max_price - current_price)}'
                })

        # Выводим риски
        if risks:
            md.append("**Ваши риски:**")
            md.append("")
            for i, risk in enumerate(risks, 1):
                md.append(f"{i}. **{risk['title']}**")
                md.append(f"   - Проблема: {risk['description']}")
                md.append(f"   - Решение: {risk['solution']}")
                md.append("")

        # Выводим возможности
        if opportunities:
            md.append("**Ваши возможности:**")
            md.append("")
            for i, opp in enumerate(opportunities, 1):
                md.append(f"{i}. **{opp['title']}**")
                md.append(f"   - {opp['description']}")
                md.append(f"   - Выгода: {opp['benefit']}")
                md.append("")

        md.append("---")
        md.append("")

        # =========================================================================
        # 4. ПСИХОЛОГИЯ ПОКУПАТЕЛЯ
        # =========================================================================
        md.append("## Кто покупает квартиры в вашем сегменте")
        md.append("")

        # Определяем профиль покупателя на основе цены и характеристик
        rooms = log.property_info.get('rooms', 2) if log.property_info else 2
        area = log.property_info.get('total_area', 50) if log.property_info else 50

        # Профиль в зависимости от цены и характеристик
        if current_price < 15_000_000:
            buyer_profile = "Молодые семьи, первое жилье или инвестиция"
            income = "200-300k/мес"
            priorities = ["Цена", "Инфраструктура (школы, сады)", "Транспортная доступность"]
        elif current_price < 30_000_000:
            buyer_profile = "Семьи с детьми, улучшение жилищных условий"
            income = "300-500k/мес"
            priorities = ["Планировка", "Район и безопасность", "Парковка"]
        else:
            buyer_profile = "Состоятельные семьи, премиум-сегмент"
            income = "500k+/мес"
            priorities = ["Престиж района", "Качество отделки", "Виды и окружение"]

        md.append(f"**Типичный покупатель:**")
        md.append(f"- Профиль: {buyer_profile}")
        md.append(f"- Доход: {income}")
        md.append(f"- Время принятия решения: 2-4 недели после первого просмотра")
        md.append("")

        md.append("**Что их привлекает:**")
        for priority in priorities:
            md.append(f"- {priority}")
        md.append("- Светлые, качественные фотографии (представляют себя в квартире)")
        md.append("- Конкретные выгоды в описании: \"5 минут до метро\" вместо \"хорошая локация\"")
        md.append("- Виртуальный тур (возможность \"прогуляться\" до показа)")
        md.append("")

        md.append("**Что их отталкивает:**")
        md.append("- Темные или плохие фотографии (ассоциация с проблемами)")
        md.append("- Общие фразы без деталей")
        md.append("- Отсутствие важной информации (приходится звонить выяснять)")
        md.append("- Завышенная цена (видят \"долго висит\" и начинают подозревать)")
        md.append("")

        md.append("> **Практический совет:** Сделайте описание с точки зрения покупателя.")
        md.append("> Не \"2-комнатная, 50м², 5 этаж\", а \"Светлая квартира для семьи: тихий двор, 2 минуты до парка, свежий ремонт\".")
        md.append("")
        md.append("---")
        md.append("")

        # =========================================================================
        # 5. ПЛАН ДЕЙСТВИЙ - Пошаговый план
        # =========================================================================
        md.append("## План продажи (пошагово)")
        md.append("")
        md.append("Конкретные действия по неделям для эффективной продажи.")
        md.append("")

        md.append("### Неделя 1: Подготовка (обязательно!)")
        md.append("")
        md.append("**День 1-2: Профессиональная фотосъемка**")
        md.append("- Стоимость: 5,000-8,000₽")
        md.append("- Эффект: +60% просмотров объявления")
        md.append("- Что снимать: все комнаты при дневном свете, 2-3 ракурса на комнату, виды из окон")
        md.append("")

        md.append("**День 2-3: Написать продающее описание**")
        md.append("- Начните с главного преимущества (локация/ремонт/планировка)")
        md.append("- Добавьте конкретные выгоды: \"3 минуты до метро\", \"тихий двор без машин\"")
        md.append("- Укажите, для кого подходит: \"идеально для семьи с детьми\" или \"отличный вариант для первой квартиры\"")
        md.append("")

        md.append("**День 3-4: Виртуальный тур (опционально)**")
        md.append("- Стоимость: 3,000-5,000₽")
        md.append("- Эффект: покупатели приходят на показ уже заинтересованными")
        md.append("")

        md.append("### Неделя 2: Размещение и продвижение")
        md.append("")
        md.append("**Разместить на всех площадках:**")
        md.append("- ЦИАН (обязательно!) - основной источник покупателей")
        md.append("- Авито - дополнительный охват")
        md.append("- Локальные группы ВКонтакте/Telegram в вашем районе")
        md.append("")

        md.append("**Включить платное продвижение:**")
        md.append("- Поднятие в топ на ЦИАН: 300-500₽/день")
        md.append("- Результат: в 3-5 раз больше звонков")
        md.append("- Бюджет: 10,000-15,000₽ на первый месяц")
        md.append("")

        md.append("**Отслеживать метрики:**")
        md.append("- Цель: минимум 50 просмотров объявления в день")
        md.append("- Если меньше: улучшить фото или снизить цену на 3-5%")
        md.append("")

        md.append("### Неделя 3-4: Показы и работа с возражениями")
        md.append("")
        md.append("**Подготовиться к показам:**")
        md.append("- Чистота и порядок (очевидно, но критично)")
        md.append("- Проветрить перед показом")
        md.append("- Подготовить ответы на типичные вопросы:")
        md.append("  - \"Почему продаете?\" → честный ответ (переезд/улучшение)")
        md.append("  - \"Какие соседи?\" → нейтрально-позитивно")
        md.append("  - \"Торг возможен?\" → заранее определите минимальную цену")
        md.append("")

        md.append("**Документы держите наготове:**")
        md.append("- Выписка из ЕГРН (показывает отсутствие обременений)")
        md.append("- Счета ЖКХ (подтверждение отсутствия долгов)")
        md.append("- Технический паспорт")
        md.append("")

        md.append("### Неделя 4+: Корректировка стратегии")
        md.append("")
        md.append("**Если после 5-7 показов нет предложений:**")
        md.append("- Соберите обратную связь: что не понравилось покупателям?")
        md.append("- Проанализируйте конкурентов: возможно они улучшили предложения")
        md.append("- Рассмотрите снижение цены на 3-5%")
        md.append("")

        md.append("**Получили предложение:**")
        md.append("- Не соглашайтесь моментально (даже если устраивает)")
        md.append("- Возьмите 1-2 дня подумать - покупатель будет ценить больше")
        md.append("- Попросите предоплату 50,000-100,000₽ для подтверждения серьезности")
        md.append("")
        md.append("---")
        md.append("")

        # =========================================================================
        # 6. СЦЕНАРИИ ПРОДАЖИ - 3 варианта
        # =========================================================================
        md.append("## Сценарии: выберите свою стратегию")
        md.append("")

        # Рассчитываем цены для сценариев
        fast_price = fair_price * 0.95  # -5% для быстрой продажи
        optimal_price = fair_price
        premium_price = fair_price * 1.05  # +5% для премиум

        md.append("### Сценарий A: Быстрая продажа (1-2 месяца)")
        md.append("")
        md.append("**Ваши действия:**")
        md.append(f"- Цена: {self.format_price_millions(fast_price)} ({self.format_number(fast_price)})")
        md.append("- Профессиональные фото + описание")
        md.append("- Активное продвижение (ЦИАН топ + Авито)")
        md.append("- Готовность к показам в любое удобное время")
        md.append("")

        md.append("**Ожидаемый результат:**")
        md.append("- 1-2 недели: 10-15 показов")
        md.append("- 3-4 недели: 2-3 серьезных предложения")
        md.append("- 6-8 недель: сделка")
        md.append("")

        md.append("**Финансы:**")
        md.append(f"- Выручка: {self.format_number(fast_price)}")
        md.append("- Расходы на подготовку: ~10,000₽ (фото)")
        md.append(f"- Чистая выручка: ~{self.format_number(fast_price - 10000)}")
        md.append("")

        md.append("---")
        md.append("")

        md.append("### Сценарий B: Оптимальная продажа (2-3 месяца) - РЕКОМЕНДУЕТСЯ")
        md.append("")
        md.append("**Ваши действия:**")
        md.append(f"- Цена: {self.format_price_millions(optimal_price)} ({self.format_number(optimal_price)})")
        md.append("- Качественная подготовка: профессиональное фото + виртуальный тур")
        md.append("- Продвижение на всех площадках")
        md.append("- Гибкий график показов")
        md.append("")

        md.append("**Ожидаемый результат:**")
        md.append("- 3-4 недели: 15-20 показов")
        md.append("- 6-8 недель: 3-4 серьезных предложения")
        md.append(f"- 10-12 недель: сделка по {self.format_price_millions(optimal_price * 0.98)}-{self.format_price_millions(optimal_price)}")
        md.append("")

        md.append("**Финансы:**")
        md.append(f"- Выручка: {self.format_number(optimal_price)} (средняя)")
        md.append("- Расходы: ~20,000₽ (фото + тур + продвижение)")
        md.append(f"- Чистая выручка: ~{self.format_number(optimal_price - 20000)}")
        md.append(f"- **Преимущество:** Дополнительно +{self.format_number(optimal_price - fast_price)} к сценарию А!")
        md.append("")

        md.append("---")
        md.append("")

        md.append("### Сценарий C: Премиум продажа (3-6 месяцев)")
        md.append("")
        md.append("**Ваши действия:**")
        md.append(f"- Цена: {self.format_price_millions(premium_price)} ({self.format_number(premium_price)})")
        md.append("- VIP-подготовка: стейджинг + профессиональная съемка + видео")
        md.append("- Работа с риелтором для доступа к базе покупателей")
        md.append("- Терпение и готовность к долгому поиску \"своего\" покупателя")
        md.append("")

        md.append("**Ожидаемый результат:**")
        md.append("- 2-3 месяца: 20-30 показов")
        md.append("- 4-5 месяцев: 2-3 предложения от платежеспособных покупателей")
        md.append(f"- 5-6 месяцев: сделка по {self.format_price_millions(premium_price * 0.97)}-{self.format_price_millions(premium_price)}")
        md.append("")

        md.append("**Финансы:**")
        md.append(f"- Выручка: {self.format_number(premium_price)} (ожидаемая)")
        md.append("- Расходы: ~40,000₽ (стейджинг + съемка + риелтор)")
        md.append(f"- Чистая выручка: ~{self.format_number(premium_price - 40000)}")
        md.append(f"- **Преимущество:** +{self.format_number(premium_price - fast_price)} к сценарию А")
        md.append("")

        md.append("**Риски:**")
        md.append("- Может потребовать 6+ месяцев")
        md.append("- Рынок может измениться за это время")
        md.append("- Упущенная выгода от альтернативного использования денег")
        md.append("")

        md.append("> **Наша рекомендация:** Сценарий B - оптимальный баланс цены, времени и усилий.")
        md.append("")
        md.append("---")
        md.append("")

        # =========================================================================
        # 7. ТЕХНИЧЕСКИЕ ДЕТАЛИ (collapsible)
        # =========================================================================
        md.append("## Технические детали анализа")
        md.append("")
        md.append("Эта секция содержит подробную информацию о расчетах и методологии.")
        md.append("")

        # Информация об объекте
        md.append("<details>")
        md.append("<summary><strong>Информация об объекте</strong> (нажмите, чтобы развернуть)</summary>")
        md.append("")

        if log.property_info:
            info = log.property_info
            md.append("| Параметр | Значение |")
            md.append("|----------|----------|")
            if 'price' in info:
                md.append(f"| Цена | {self.format_number(info['price'])} |")
            if 'total_area' in info:
                md.append(f"| Площадь | {info['total_area']} м² |")
            if 'rooms' in info:
                md.append(f"| Комнат | {info['rooms']} |")
            if 'floor' in info and 'total_floors' in info:
                md.append(f"| Этаж | {info['floor']} из {info['total_floors']} |")
            if 'address' in info:
                md.append(f"| Адрес | {info['address']} |")

        md.append("")
        md.append("</details>")
        md.append("")

        # Найденные аналоги
        if log.comparables_data:
            md.append("<details>")
            md.append(f"<summary><strong>Найденные аналоги</strong> ({len(log.comparables_data)} объектов)</summary>")
            md.append("")

            md.append("| № | Цена | Площадь | Цена за м² | Адрес |")
            md.append("|---|------|---------|-----------|--------|")

            for i, comp in enumerate(log.comparables_data[:20], 1):  # Показываем топ-20
                price = self.format_number(comp.get('price', 0))
                area = comp.get('total_area', 0)
                price_sqm = self.format_number(comp.get('price_per_sqm', 0))
                address = comp.get('address', '')[:50] + '...' if len(comp.get('address', '')) > 50 else comp.get('address', '-')
                md.append(f"| {i} | {price} | {area} м² | {price_sqm} | {address} |")

            if len(log.comparables_data) > 20:
                md.append(f"| ... | _(ещё {len(log.comparables_data) - 20})_ | | | |")

            md.append("")
            md.append("</details>")
            md.append("")

        # Рыночная статистика
        if log.market_stats:
            md.append("<details>")
            md.append("<summary><strong>Рыночная статистика</strong></summary>")
            md.append("")

            stats = log.market_stats
            if 'all' in stats:
                all_stats = stats['all']
                md.append("**Все аналоги:**")
                md.append("")
                md.append(f"- Количество: {all_stats.get('count', 0)}")
                md.append(f"- Медиана цены за м²: {self.format_number(all_stats.get('median', 0))}")
                md.append(f"- Среднее: {self.format_number(all_stats.get('mean', 0))}")
                md.append(f"- Минимум: {self.format_number(all_stats.get('min', 0))}")
                md.append(f"- Максимум: {self.format_number(all_stats.get('max', 0))}")
                md.append("")

            md.append("</details>")
            md.append("")

        # Применённые корректировки
        if log.adjustments:
            md.append("<details>")
            md.append("<summary><strong>Применённые корректировки</strong></summary>")
            md.append("")

            md.append("| Корректировка | Коэффициент | Влияние | Описание |")
            md.append("|--------------|-------------|---------|----------|")

            for adj_name, adj_data in log.adjustments.items():
                if isinstance(adj_data, dict):
                    coef = adj_data.get('value', 1.0)
                    desc = adj_data.get('description', '')
                    percent = (coef - 1) * 100
                    sign = '+' if percent > 0 else ''
                    md.append(f"| {adj_name} | {coef:.4f} | {sign}{percent:.2f}% | {desc} |")

            md.append("")
            md.append("</details>")
            md.append("")

        # Методология расчетов
        md.append("<details>")
        md.append("<summary><strong>Методология расчетов</strong></summary>")
        md.append("")

        md.append("**Как мы рассчитываем справедливую цену:**")
        md.append("")
        md.append("1. **Сбор аналогов**")
        md.append("   - Ищем похожие объекты в том же районе")
        md.append("   - Фильтруем по площади (±20%), этажу, типу дома")
        md.append("")

        md.append("2. **Медианный подход**")
        md.append("   - Берем среднюю цену из всех аналогов (медиану)")
        md.append("   - Медиана устойчива к выбросам (1-2 сильно завышенных объекта не испортят картину)")
        md.append("")

        md.append("3. **Корректировки**")
        md.append("   - Учитываем отличия вашего объекта: ремонт, вид из окон, этаж и т.д.")
        md.append("   - Каждый фактор имеет научно обоснованный коэффициент влияния")
        md.append("")

        md.append("4. **Диапазон цен**")
        md.append("   - Минимум: цена быстрой продажи (-5% от справедливой)")
        md.append("   - Справедливая: медиана с учетом корректировок")
        md.append("   - Максимум: верхняя граница при идеальной презентации (+5-7%)")
        md.append("")

        md.append("**Прогноз времени продажи:**")
        md.append("")
        md.append("Основан на:")
        md.append("- Отклонении вашей цены от рыночной медианы")
        md.append("- Индексе привлекательности объекта")
        md.append("- Исторических данных о времени продажи похожих объектов")
        md.append("")

        md.append("> **Важно:** Этот анализ - математическая оценка на основе текущих рыночных данных.")
        md.append("> Реальный рынок сложнее: на продажу влияют сезонность, макроэкономика, качество")
        md.append("> презентации и даже настроение конкретного покупателя. Цифры дают ориентир,")
        md.append("> но финальный успех зависит от вашей подготовки и активности.")
        md.append("")

        md.append("</details>")
        md.append("")

        # Объяснение индекса привлекательности
        if hasattr(log, 'attractiveness_index') and log.attractiveness_index:
            md.append("<details>")
            md.append("<summary><strong>Что означает индекс привлекательности</strong></summary>")
            md.append("")

            attr = log.attractiveness_index
            total = attr.get('total_index', 0)

            md.append(f"**Ваш индекс: {total:.0f}/100**")
            md.append("")
            md.append("Это НЕ \"качество квартиры\", а \"насколько легко её продать\".")
            md.append("")
            md.append("Мы учитываем:")
            md.append("- Цену относительно рынка (у вас завышена/занижена?)")
            md.append("- Характеристики (площадь, этаж, планировка)")
            md.append("- Конкуренцию (сколько похожих объектов)")
            md.append("- Уникальность (чем выделяетесь)")
            md.append("")

            if total >= 80:
                md.append("**80-100: Отличная привлекательность**")
                md.append("- Объект легко продается")
                md.append("- При правильной презентации - быстрая продажа")
            elif total >= 60:
                md.append("**60-80: Хорошая привлекательность**")
                md.append("- Продать можно, но нужны усилия")
                md.append("- Критично: качественные фото и активное продвижение")
            else:
                md.append("**Ниже 60: Требуется особое внимание**")
                md.append("- Высокая конкуренция или завышенная цена")
                md.append("- Рекомендуем: снизить цену или максимально улучшить презентацию")

            md.append("")
            md.append("**Как поднять индекс:**")
            md.append("- Скорректировать цену ближе к медиане рынка")
            md.append("- Профессиональные фото (это влияет на восприятие)")
            md.append("- Уникальное описание (не копипаста)")
            md.append("- Активное продвижение (больше охват = больше шансов)")
            md.append("")

            md.append("</details>")
            md.append("")

        # Footer
        md.append("---")
        md.append("")
        md.append(f"*Отчет создан: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
        md.append("")
        md.append("*Этот анализ основан на текущих рыночных данных и не является финансовой рекомендацией.")
        md.append("Финальное решение о цене и стратегии продажи остается за вами.*")

        return "\n".join(md)

    def export_multiple_properties(self, logs: List[PropertyLog]) -> str:
        """Экспорт нескольких объектов в один Markdown файл"""
        md = []

        # Заголовок и оглавление
        md.append("# Отчет по обработке объектов недвижимости")
        md.append("")
        md.append(f"**Дата создания:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        md.append(f"**Всего объектов:** {len(logs)}")
        md.append("")

        # Сводка
        completed = sum(1 for log in logs if log.status == 'completed')
        failed = sum(1 for log in logs if log.status == 'failed')
        processing = sum(1 for log in logs if log.status == 'processing')

        md.append("## Сводка")
        md.append("")
        md.append(f"- Успешно: {completed}")
        md.append(f"- Ошибки: {failed}")
        md.append(f"- В процессе: {processing}")
        md.append("")
        md.append("---")
        md.append("")

        # Оглавление
        md.append("## Оглавление")
        md.append("")
        for i, log in enumerate(logs, 1):
            status_mark = {'completed': 'OK', 'failed': 'FAIL', 'processing': 'WIP'}.get(log.status, '?')
            md.append(f"{i}. [{status_mark}] [{log.property_id}](#{log.property_id})")

        md.append("")
        md.append("---")
        md.append("")

        # Детальные отчёты
        for log in logs:
            md.append(f'<a name="{log.property_id}"></a>')
            md.append("")
            md.append(self.export_single_property(log))
            md.append("")
            md.append("---")
            md.append("")

        return "\n".join(md)

    def export_tracker_summary(self, tracker: PropertyTracker) -> str:
        """Экспорт краткой сводки по всем объектам"""
        summary = tracker.get_summary()
        logs = tracker.get_all_logs()

        md = []

        md.append("# Сводка по обработке объектов")
        md.append("")
        md.append(f"**Дата:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        md.append("")

        md.append("## Общая статистика")
        md.append("")
        md.append(f"- **Всего объектов:** {summary['total']}")
        md.append(f"- **Успешно обработано:** {summary['completed']} ({summary['success_rate']:.1f}%)")
        md.append(f"- **Ошибки:** {summary['failed']}")
        md.append(f"- **В процессе:** {summary['processing']}")
        md.append("")

        # Таблица объектов
        md.append("## Список объектов")
        md.append("")
        md.append("| ID | URL | Статус | Начало | Завершение |")
        md.append("|----|-----|--------|--------|-----------|")

        for log in logs:
            status_mark = {'completed': 'OK', 'failed': 'FAIL', 'processing': 'WIP'}.get(log.status, '?')
            url_link = f"[ссылка]({log.url})" if log.url else "-"
            start_time = datetime.fromisoformat(log.started_at).strftime('%H:%M:%S')
            end_time = datetime.fromisoformat(log.completed_at).strftime('%H:%M:%S') if log.completed_at else "-"

            md.append(f"| {log.property_id} | {url_link} | {status_mark} | {start_time} | {end_time} |")

        md.append("")

        return "\n".join(md)

    def _get_event_emoji(self, event_type: EventType) -> str:
        """Получить маркер для типа события"""
        emoji_map = {
            EventType.PARSING_STARTED: "[PARSE]",
            EventType.PARSING_COMPLETED: "[OK]",
            EventType.PARSING_FAILED: "[FAIL]",
            EventType.DATA_EXTRACTED: "[DATA]",
            EventType.ANALYSIS_STARTED: "[ANALYZE]",
            EventType.ANALYSIS_COMPLETED: "[OK]",
            EventType.ANALYSIS_FAILED: "[FAIL]",
            EventType.MARKET_STATS_CALCULATED: "[STATS]",
            EventType.OUTLIERS_FILTERED: "[FILTER]",
            EventType.FAIR_PRICE_CALCULATED: "[PRICE]",
            EventType.ADJUSTMENT_APPLIED: "[ADJUST]",
            EventType.SCENARIOS_GENERATED: "[SCENARIOS]",
            EventType.WARNING: "[WARN]",
            EventType.ERROR: "[ERROR]"
        }
        return emoji_map.get(event_type, "[INFO]")
