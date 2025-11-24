"""
Асинхронные задачи с использованием RQ (Redis Queue)

Этот модуль содержит задачи, которые могут выполняться в фоне:
- Парсинг URL недвижимости
- Поиск аналогов
- Генерация отчетов
"""

from .queue import get_task_queue, get_task_status, init_task_queue
from .tasks import parse_property_task, find_similar_task

__all__ = [
    'init_task_queue',
    'get_task_queue',
    'get_task_status',
    'parse_property_task',
    'find_similar_task'
]
