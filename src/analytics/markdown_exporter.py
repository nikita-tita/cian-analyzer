"""
Экспорт логов обработки объектов в Markdown формат
"""

from typing import List, Dict, Any
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
