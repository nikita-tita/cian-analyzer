#!/usr/bin/env python3
"""
Скрипт для экспорта логов обработки объектов в Markdown
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from analytics.property_tracker import get_tracker
from analytics.markdown_exporter import MarkdownExporter


def export_logs(output_file: str = None, summary_only: bool = False):
    """
    Экспортировать логи в Markdown

    Args:
        output_file: Путь к выходному файлу (по умолчанию: property_logs.md)
        summary_only: Только краткая сводка (без детальных отчётов)
    """
    tracker = get_tracker()
    exporter = MarkdownExporter()

    if not tracker.logs:
        print("❌ Нет логов для экспорта")
        return

    # Определяем имя файла
    if not output_file:
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"property_logs_{timestamp}.md"

    # Генерируем Markdown
    if summary_only:
        content = exporter.export_tracker_summary(tracker)
    else:
        logs = tracker.get_all_logs()
        if len(logs) == 1:
            content = exporter.export_single_property(logs[0])
        else:
            content = exporter.export_multiple_properties(logs)

    # Сохраняем
    output_path = Path(output_file)
    output_path.write_text(content, encoding='utf-8')

    # Статистика
    summary = tracker.get_summary()
    print(f"\n✅ Логи экспортированы в: {output_path.absolute()}")
    print("\n📊 Статистика:")
    print(f"  Всего объектов: {summary['total']}")
    print(f"  Успешно: {summary['completed']}")
    print(f"  Ошибки: {summary['failed']}")
    print(f"  В процессе: {summary['processing']}")
    print(f"  Успешность: {summary['success_rate']:.1f}%")


def export_single_property(property_id: str, output_file: str = None):
    """
    Экспортировать один объект

    Args:
        property_id: ID объекта
        output_file: Путь к выходному файлу
    """
    tracker = get_tracker()
    log = tracker.get_log(property_id)

    if not log:
        print(f"❌ Объект {property_id} не найден")
        return

    exporter = MarkdownExporter()
    content = exporter.export_single_property(log)

    # Определяем имя файла
    if not output_file:
        output_file = f"property_{property_id}.md"

    output_path = Path(output_file)
    output_path.write_text(content, encoding='utf-8')

    print(f"✅ Отчёт по объекту {property_id} экспортирован в: {output_path.absolute()}")


def main():
    parser = argparse.ArgumentParser(description='Экспорт логов обработки объектов недвижимости')

    parser.add_argument('-o', '--output', help='Путь к выходному файлу')
    parser.add_argument('-s', '--summary', action='store_true', help='Только краткая сводка')
    parser.add_argument('-p', '--property-id', help='Экспортировать только один объект по ID')

    args = parser.parse_args()

    if args.property_id:
        export_single_property(args.property_id, args.output)
    else:
        export_logs(args.output, args.summary)


if __name__ == '__main__':
    main()
