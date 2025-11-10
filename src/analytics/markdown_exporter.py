"""
Экспорт логов обработки объектов в Markdown формат
"""

from typing import List, Any
from datetime import datetime
from .property_tracker import PropertyLog, PropertyTracker, EventType


class MarkdownExporter:
    """
    Экспорт логов обработки в красивый Markdown отчёт
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

    def export_single_property(self, log: PropertyLog) -> str:
        """Экспорт одного объекта в Markdown"""
        md = []

        # Заголовок
        md.append(f"# 🏢 Отчёт по объекту недвижимости")
        md.append("")
        md.append(f"**ID:** {log.property_id}")

        if log.url:
            md.append(f"**URL:** [{log.url}]({log.url})")

        md.append(f"**Начало обработки:** {log.started_at}")
        if log.completed_at:
            md.append(f"**Завершение:** {log.completed_at}")

        # Статус с эмодзи
        status_emoji = {
            'completed': '✅',
            'failed': '❌',
            'processing': '⏳'
        }
        emoji = status_emoji.get(log.status, '❓')
        md.append(f"**Статус:** {emoji} {log.status.upper()}")
        md.append("")
        md.append("---")
        md.append("")

        # МЕТОДОЛОГИЯ АНАЛИЗА
        md.append("## 🔬 Методология анализа")
        md.append("")
        md.append("Данный отчет основан на **математической модели сравнительного анализа** конкурентных предложений "
                  "с применением методов статистической оценки и вероятностного прогнозирования.")
        md.append("")
        md.append("**Ключевые принципы:**")
        md.append("")
        md.append("- **Медианный подход** — устойчивость к выбросам и аномальным предложениям")
        md.append("- **Кластерный анализ** — оценка по 6 группам параметров с научно обоснованными коэффициентами")
        md.append("- **Доверительные интервалы** — расчет диапазона цен с 95% уровнем доверия (t-распределение Стьюдента)")
        md.append("- **Вероятностное моделирование** — прогноз времени продажи на основе исторических данных и индекса привлекательности")
        md.append("- **Многофакторная корректировка** — учет только значимых отличий от рыночной медианы")
        md.append("")
        md.append("> ⚠️ **Важно:** Представленный анализ является количественной оценкой на основе доступных данных. "
                  "Реальный рынок недвижимости значительно сложнее и зависит от множества факторов, включая макроэкономическую "
                  "ситуацию, сезонность, индивидуальные особенности покупателей и качество презентации объекта. "
                  "**Рекомендации по комплексному подходу к продаже приведены в конце отчета.**")
        md.append("")
        md.append("---")
        md.append("")

        # 1. Информация об объекте
        if log.property_info:
            md.append("## 📋 Информация об объекте")
            md.append("")

            info = log.property_info
            if 'price' in info:
                md.append(f"- **Цена:** {self.format_number(info['price'])}")
            if 'total_area' in info:
                md.append(f"- **Площадь:** {info['total_area']} м²")
            if 'rooms' in info:
                md.append(f"- **Комнат:** {info['rooms']}")
            if 'floor' in info and 'total_floors' in info:
                md.append(f"- **Этаж:** {info['floor']} из {info['total_floors']}")
            if 'address' in info:
                md.append(f"- **Адрес:** {info['address']}")

            md.append("")

        # 2. Этапы обработки (временная шкала)
        if log.events:
            md.append("## ⏱️ Временная шкала обработки")
            md.append("")

            for event in log.events:
                event_emoji = self._get_event_emoji(event.event_type)
                time = datetime.fromisoformat(event.timestamp).strftime("%H:%M:%S")

                md.append(f"### {event_emoji} {time} - {event.message}")

                if event.details:
                    md.append("")
                    md.append("```json")
                    import json
                    md.append(json.dumps(event.details, indent=2, ensure_ascii=False))
                    md.append("```")

                md.append("")

        # 3. Данные парсинга
        if log.parsing_data:
            md.append("## 🌐 Результаты парсинга")
            md.append("")
            md.append("```json")
            import json
            md.append(json.dumps(log.parsing_data, indent=2, ensure_ascii=False))
            md.append("```")
            md.append("")

        # 4. Аналоги
        if log.comparables_data:
            md.append("## 🏘️ Найденные аналоги")
            md.append("")
            md.append(f"**Всего найдено:** {len(log.comparables_data)}")
            md.append("")

            md.append("| № | Цена | Площадь | Цена за м² |")
            md.append("|---|------|---------|-----------|")

            for i, comp in enumerate(log.comparables_data[:10], 1):
                price = self.format_number(comp.get('price', 0))
                area = comp.get('total_area', 0)
                price_sqm = self.format_number(comp.get('price_per_sqm', 0))
                md.append(f"| {i} | {price} | {area} м² | {price_sqm} |")

            if len(log.comparables_data) > 10:
                md.append(f"| ... | _(ещё {len(log.comparables_data) - 10})_ | | |")

            md.append("")

        # 5. Рыночная статистика
        if log.market_stats:
            md.append("## 📊 Рыночная статистика")
            md.append("")

            stats = log.market_stats
            if 'with_design' in stats:
                design_stats = stats['with_design']
                md.append("### С дизайнерской отделкой")
                md.append("")
                md.append(f"- **Количество:** {design_stats.get('count', 0)}")
                md.append(f"- **Медиана:** {self.format_number(design_stats.get('median', 0))} за м²")
                md.append(f"- **Среднее:** {self.format_number(design_stats.get('mean', 0))} за м²")
                md.append(f"- **Мин/Макс:** {self.format_number(design_stats.get('min', 0))} / {self.format_number(design_stats.get('max', 0))}")
                md.append("")

            if 'all' in stats:
                all_stats = stats['all']
                md.append("### Все аналоги")
                md.append("")
                md.append(f"- **Количество:** {all_stats.get('count', 0)}")
                md.append(f"- **Медиана:** {self.format_number(all_stats.get('median', 0))} за м²")
                md.append(f"- **Среднее:** {self.format_number(all_stats.get('mean', 0))} за м²")
                md.append("")

        # 6. Применённые корректировки
        if log.adjustments:
            md.append("## 🔧 Применённые корректировки")
            md.append("")

            md.append("| Корректировка | Коэффициент | Описание |")
            md.append("|--------------|-------------|----------|")

            for adj_name, adj_data in log.adjustments.items():
                if isinstance(adj_data, dict):
                    coef = adj_data.get('value', 1.0)
                    desc = adj_data.get('description', '')
                    percent = (coef - 1) * 100
                    sign = '+' if percent > 0 else ''
                    md.append(f"| {adj_name} | {coef:.4f} ({sign}{percent:.2f}%) | {desc} |")

            md.append("")

        # 7. Справедливая цена
        if log.fair_price_result:
            md.append("## 💰 Расчёт справедливой цены")
            md.append("")

            result = log.fair_price_result

            md.append(f"- **Базовая цена за м²:** {self.format_number(result.get('base_price_per_sqm', 0))}")
            md.append(f"- **Итоговый multiplier:** {result.get('final_multiplier', 1.0):.4f}")
            md.append(f"- **Справедливая цена за м²:** {self.format_number(result.get('fair_price_per_sqm', 0))}")
            md.append("")

            md.append(f"### Результат")
            md.append(f"- **Справедливая цена:** {self.format_number(result.get('fair_price_total', 0))}")
            md.append(f"- **Текущая цена:** {self.format_number(result.get('current_price', 0))}")

            diff = result.get('price_diff_percent', 0)
            if result.get('is_overpriced'):
                md.append(f"- **Статус:** ⚠️ Переоценен на {diff:.2f}%")
            elif result.get('is_underpriced'):
                md.append(f"- **Статус:** ✅ Недооценен на {abs(diff):.2f}%")
            elif result.get('is_fair'):
                md.append(f"- **Статус:** ✅ Справедливая цена ({diff:+.2f}%)")

            md.append("")

        # 7.1. Диапазон цен (НОВОЕ)
        if hasattr(log, 'price_range') and log.price_range:
            md.append("### 📊 Диапазон справедливой цены")
            md.append("")

            pr = log.price_range
            md.append(f"- **Минимальная цена:** {self.format_number(pr.get('min_price', 0))} ({pr.get('min_price_description', '')})")
            md.append(f"- **Справедливая цена:** {self.format_number(pr.get('fair_price', 0))}")
            md.append(f"- **Рекомендуемая цена листинга:** {self.format_number(pr.get('recommended_listing', 0))} ({pr.get('recommended_listing_description', '')})")
            md.append(f"- **Максимальная цена:** {self.format_number(pr.get('max_price', 0))} ({pr.get('max_price_description', '')})")
            md.append("")

            # Интерпретация
            if 'interpretation' in pr:
                interp = pr['interpretation']
                md.append("**Рекомендации:**")
                md.append(f"- {interp.get('pricing_strategy', '')}")
                md.append(f"- Ожидаемый срок: {interp.get('expected_timeline', '')}")
                md.append(f"- {interp.get('negotiation_advice', '')}")
                md.append("")

        # 7.2. Индекс привлекательности (НОВОЕ)
        if hasattr(log, 'attractiveness_index') and log.attractiveness_index:
            md.append("### 🌟 Индекс привлекательности объекта")
            md.append("")

            attr = log.attractiveness_index
            total = attr.get('total_index', 0)
            category = attr.get('category', '')
            emoji = attr.get('category_emoji', '')

            md.append(f"**Общая оценка:** {emoji} {total:.1f}/100 ({category})")
            md.append("")
            md.append(attr.get('category_description', ''))
            md.append("")

            # Компоненты
            if 'components' in attr:
                md.append("**Компоненты оценки:**")
                md.append("")
                md.append("| Компонент | Оценка | Вес | Вклад |")
                md.append("|-----------|--------|-----|-------|")

                for comp_name, comp_data in attr['components'].items():
                    score = comp_data.get('score', 0)
                    weight = comp_data.get('weight', 0)
                    weighted = comp_data.get('weighted_score', 0)
                    md.append(f"| {comp_name.capitalize()} | {score:.1f}/100 | {weight}% | {weighted:.1f} |")

                md.append("")

            # Сводка рекомендаций
            if 'summary' in attr:
                md.append("**Сводка:**")
                md.append("```")
                md.append(attr['summary'])
                md.append("```")
                md.append("")

        # 7.3. Прогноз времени продажи (НОВОЕ)
        if hasattr(log, 'time_forecast') and log.time_forecast:
            md.append("### ⏱️ Прогноз времени продажи")
            md.append("")

            tf = log.time_forecast
            expected = tf.get('expected_time_months', 0)
            time_range = tf.get('time_range_description', '')

            md.append(f"**Ожидаемое время:** {expected:.1f} месяцев ({time_range})")
            md.append("")

            # Вероятности продажи
            if 'probability_milestones' in tf:
                pm = tf['probability_milestones']
                md.append("**Вероятность продажи:**")
                md.append(f"- За 1 месяц: {pm.get('1_month', 0):.0%}")
                md.append(f"- За 3 месяца: {pm.get('3_months', 0):.0%}")
                md.append(f"- За 6 месяцев: {pm.get('6_months', 0):.0%}")
                md.append(f"- За 12 месяцев: {pm.get('12_months', 0):.0%}")
                md.append("")

            # Интерпретация
            if 'interpretation' in tf:
                interp = tf['interpretation']
                md.append("**Интерпретация:**")
                md.append(f"- {interp.get('overall', '')}")
                md.append(f"- {interp.get('price_factor', '')}")
                md.append(f"- {interp.get('attractiveness_factor', '')}")
                md.append("")

        # 7.4. Анализ чувствительности (НОВОЕ)
        if hasattr(log, 'price_sensitivity') and log.price_sensitivity:
            md.append("### 📉 Анализ чувствительности к цене")
            md.append("")
            md.append("Как изменение цены влияет на вероятность и время продажи:")
            md.append("")

            md.append("| Цена (млн₽) | Отклонение | Время продажи | Вероятность (6 мес) |")
            md.append("|-------------|------------|---------------|---------------------|")

            for ps in log.price_sensitivity[:10]:  # Топ-10 точек
                price_m = ps.get('price', 0) / 1_000_000
                discount = ps.get('discount_percent', 0)
                time_m = ps.get('expected_time_months', 0)
                prob_6 = ps.get('probability_6_months', 0)

                # Выделяем справедливую цену
                if abs(discount) < 1:
                    price_str = f"**{price_m:.2f}**"
                    time_str = f"**{time_m:.1f} мес**"
                else:
                    price_str = f"{price_m:.2f}"
                    time_str = f"{time_m:.1f} мес"

                md.append(f"| {price_str} | {discount:+.1f}% | {time_str} | {prob_6:.0%} |")

            md.append("")

        # 7.5. Рекомендации (НОВОЕ)
        if hasattr(log, 'recommendations') and log.recommendations:
            md.append("## 💡 Персональные рекомендации")
            md.append("")
            md.append("На основе анализа объекта выявлены следующие рекомендации по улучшению результатов продажи:")
            md.append("")

            # Группируем рекомендации по приоритету
            priorities = {
                1: {'label': 'КРИТИЧНО', 'emoji': '🔴', 'recs': []},
                2: {'label': 'ВАЖНО', 'emoji': '🟠', 'recs': []},
                3: {'label': 'СРЕДНЕ', 'emoji': '🟡', 'recs': []},
                4: {'label': 'ИНФО', 'emoji': '🔵', 'recs': []}
            }

            for rec in log.recommendations:
                priority = rec.get('priority', 4)
                if priority in priorities:
                    priorities[priority]['recs'].append(rec)

            # Выводим рекомендации по приоритетам
            for priority_num in sorted(priorities.keys()):
                priority_data = priorities[priority_num]
                recs_list = priority_data['recs']

                if recs_list:
                    md.append(f"### {priority_data['emoji']} {priority_data['label']}")
                    md.append("")

                    for rec in recs_list:
                        title = rec.get('title', '')
                        message = rec.get('message', '')
                        action = rec.get('action', '')
                        expected = rec.get('expected_result', '')
                        roi = rec.get('roi')
                        financial = rec.get('financial_impact', {})

                        md.append(f"#### {rec.get('icon', '•')} {title}")
                        md.append("")
                        md.append(f"**Проблема:** {message}")
                        md.append("")
                        md.append(f"**Действие:** {action}")
                        md.append("")
                        md.append(f"**Ожидаемый результат:** {expected}")
                        md.append("")

                        # ROI если есть
                        if roi is not None:
                            md.append(f"**ROI:** {roi:.1f}x (окупаемость)")
                            md.append("")

                        # Финансовый эффект если есть
                        if financial:
                            md.append("**Финансовый эффект:**")
                            for key, value in financial.items():
                                if isinstance(value, (int, float)) and abs(value) > 1000:
                                    md.append(f"- {key}: {self.format_number(value)}")
                                else:
                                    md.append(f"- {key}: {value}")
                            md.append("")

            md.append("---")
            md.append("")

        # 8. Сценарии продажи
        if log.scenarios:
            md.append("## 📈 Сценарии продажи")
            md.append("")

            for scenario in log.scenarios:
                name = scenario.get('name', 'Неизвестный сценарий')
                md.append(f"### {name}")
                md.append("")

                md.append(f"- **Стартовая цена:** {self.format_number(scenario.get('start_price', 0))}")
                md.append(f"- **Ожидаемая итоговая:** {self.format_number(scenario.get('expected_final_price', 0))}")
                md.append(f"- **Срок продажи:** {scenario.get('time_months', 0)} мес")

                if 'financials' in scenario:
                    fin = scenario['financials']
                    md.append(f"- **Чистая прибыль:** {self.format_number(fin.get('net_profit', 0))}")

                md.append("")

        # 9. Метрики производительности
        if log.metrics:
            md.append("## ⚡ Метрики производительности")
            md.append("")

            for metric_name, metric_value in log.metrics.items():
                md.append(f"- **{metric_name}:** {metric_value}")

            md.append("")

        # КОМПЛЕКСНЫЙ ПОДХОД К ПРОДАЖЕ
        md.append("## 🎯 Комплексный подход к продаже недвижимости")
        md.append("")
        md.append("Математический анализ дает объективную оценку стоимости, но **успешная продажа** требует не только "
                  "правильной цены, а комплексного подхода, который включает:")
        md.append("")
        md.append("### 🌟 Ключевые факторы успеха")
        md.append("")
        md.append("1. **Клиентоориентированный подход** — понимание потребностей целевой аудитории и адаптация презентации под них")
        md.append("2. **Максимизация охватов** — использование всех доступных каналов продвижения для привлечения максимального количества потенциальных покупателей")
        md.append("3. **Вовлеченность и эмоции** — создание желания жить в этом объекте через профессиональную презентацию")
        md.append("4. **Юридическая чистота** — полное сопровождение сделки для снижения рисков покупателя")
        md.append("")
        md.append("---")
        md.append("")
        md.append("### 📦 Рекомендуемый пакет услуг по ценовым сегментам")
        md.append("")
        md.append("В зависимости от стоимости объекта, мы рекомендуем различные уровни подготовки и продвижения:")
        md.append("")

        # Определяем ценовой сегмент объекта
        current_price = log.property_info.get('price', 0) if log.property_info else 0
        price_segment = ""
        if current_price > 0:
            if current_price < 25_000_000:
                price_segment = "до 25 млн"
            elif current_price < 50_000_000:
                price_segment = "25–50 млн"
            else:
                price_segment = "50+ млн"

        md.append("| Ценовой сегмент | Рекомендуемые инструменты |")
        md.append("|----------------|---------------------------|")

        # Сегмент до 25 млн
        segment_marker_1 = "**→**" if price_segment == "до 25 млн" else ""
        md.append(f"| {segment_marker_1} **До 25 млн** | **Базовая подготовка:** Лайт-стейджинг (расстановка акцентов), профессиональная фото/видеосъемка, 3D-тур, планировка с расстановкой мебели<br>**Продвижение:** Размещение на ЦИАН + Авито с продвижением, таргет в соцсетях района, автоматические календари показов<br>**Сопровождение:** Юридическое сопровождение сделки |")

        # Сегмент 25-50 млн
        segment_marker_2 = "**→**" if price_segment == "25–50 млн" else ""
        md.append(f"| {segment_marker_2} **25–50 млн** | **Профессиональная подготовка:** Полноценный стейджинг, вечерняя и дрон-съемка, 4K видео-ролики, интерактивный 3D-тур<br>**Расширенное продвижение:** Персональный лендинг объекта, PR-кампания в Telegram-каналах района, авто-подъемы объявлений, ретаргетинг заинтересованных<br>**Премиум-сервис:** Организация показов с консультантом, детальная аналитика просмотров |")

        # Сегмент 50+ млн
        segment_marker_3 = "**→**" if price_segment == "50+ млн" else ""
        md.append(f"| {segment_marker_3} **50+ млн** | **Премиальная подготовка:** Премиум-стейджинг с арендой дизайнерской мебели, профессиональная дрон и ночная съемка, киношные 4K-ролики, интерактивная 3D-планировка<br>**VIP-продвижение:** Персональный лендинг + data room с документами, персонализированные показы с историей района, PR в федеральных медиа, эксклюзивные каналы продвижения<br>**Консьерж-сервис:** Полное сопровождение от подготовки до закрытия сделки |")

        md.append("")

        # Выделяем текущий сегмент если известен
        if price_segment:
            md.append(f"> 💡 **Для вашего объекта ({price_segment})** рекомендуется соответствующий пакет услуг для максимально эффективной продажи.")
            md.append("")

        md.append("### 🎨 Почему это важно?")
        md.append("")
        md.append("**Математика показывает ЦЕНУ, а эмоции продают квартиру.**")
        md.append("")
        md.append("Даже при идеальной цене объект может продаваться долго, если:")
        md.append("- Фотографии не раскрывают потенциал квартиры")
        md.append("- Описание не вызывает желания приехать на показ")
        md.append("- Охваты недостаточны для привлечения целевой аудитории")
        md.append("- Отсутствует эмоциональная связь с объектом")
        md.append("")
        md.append("**Профессиональная подготовка и продвижение:**")
        md.append("- Увеличивает количество просмотров на 40-60%")
        md.append("- Повышает конверсию в показы на 25-35%")
        md.append("- Сокращает время продажи в 1.5-2 раза")
        md.append("- Позволяет продать по верхней границе диапазона")
        md.append("")
        md.append("---")
        md.append("")
        md.append("### 📞 Следующие шаги")
        md.append("")
        md.append("Для получения детальной консультации по подготовке и продвижению вашего объекта, "
                  "а также расчета индивидуального пакета услуг, свяжитесь с нашими специалистами.")
        md.append("")

        md.append("---")
        md.append(f"*Отчёт создан: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

        return "\n".join(md)

    def export_multiple_properties(self, logs: List[PropertyLog]) -> str:
        """Экспорт нескольких объектов в один Markdown файл"""
        md = []

        # Заголовок и оглавление
        md.append("# 📊 Отчёт по обработке объектов недвижимости")
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
        md.append(f"- ✅ Успешно: {completed}")
        md.append(f"- ❌ Ошибки: {failed}")
        md.append(f"- ⏳ В процессе: {processing}")
        md.append("")
        md.append("---")
        md.append("")

        # Оглавление
        md.append("## Оглавление")
        md.append("")
        for i, log in enumerate(logs, 1):
            status_emoji = {'completed': '✅', 'failed': '❌', 'processing': '⏳'}.get(log.status, '❓')
            md.append(f"{i}. {status_emoji} [{log.property_id}](#{log.property_id})")

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

        md.append("# 📋 Сводка по обработке объектов")
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
            status_emoji = {'completed': '✅', 'failed': '❌', 'processing': '⏳'}.get(log.status, '❓')
            url_link = f"[🔗]({log.url})" if log.url else "-"
            start_time = datetime.fromisoformat(log.started_at).strftime('%H:%M:%S')
            end_time = datetime.fromisoformat(log.completed_at).strftime('%H:%M:%S') if log.completed_at else "-"

            md.append(f"| {log.property_id} | {url_link} | {status_emoji} {log.status} | {start_time} | {end_time} |")

        md.append("")

        return "\n".join(md)

    def _get_event_emoji(self, event_type: EventType) -> str:
        """Получить эмодзи для типа события"""
        emoji_map = {
            EventType.PARSING_STARTED: "🌐",
            EventType.PARSING_COMPLETED: "✅",
            EventType.PARSING_FAILED: "❌",
            EventType.DATA_EXTRACTED: "📥",
            EventType.ANALYSIS_STARTED: "🔍",
            EventType.ANALYSIS_COMPLETED: "✅",
            EventType.ANALYSIS_FAILED: "❌",
            EventType.MARKET_STATS_CALCULATED: "📊",
            EventType.OUTLIERS_FILTERED: "🔧",
            EventType.FAIR_PRICE_CALCULATED: "💰",
            EventType.ADJUSTMENT_APPLIED: "🔧",
            EventType.SCENARIOS_GENERATED: "📈",
            EventType.WARNING: "⚠️",
            EventType.ERROR: "🚨"
        }
        return emoji_map.get(event_type, "📌")
