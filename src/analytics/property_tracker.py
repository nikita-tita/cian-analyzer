"""
Система отслеживания обработки объектов недвижимости
Логирует все этапы: парсинг → анализ → расчёты → результаты
"""

import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum


class EventType(Enum):
    """Типы событий в процессе обработки"""
    # Парсинг
    PARSING_STARTED = "parsing_started"
    PARSING_COMPLETED = "parsing_completed"
    PARSING_FAILED = "parsing_failed"
    DATA_EXTRACTED = "data_extracted"

    # Анализ
    ANALYSIS_STARTED = "analysis_started"
    ANALYSIS_COMPLETED = "analysis_completed"
    ANALYSIS_FAILED = "analysis_failed"

    # Расчёты
    MARKET_STATS_CALCULATED = "market_stats_calculated"
    OUTLIERS_FILTERED = "outliers_filtered"
    FAIR_PRICE_CALCULATED = "fair_price_calculated"
    ADJUSTMENT_APPLIED = "adjustment_applied"
    SCENARIOS_GENERATED = "scenarios_generated"

    # Предупреждения
    WARNING = "warning"
    ERROR = "error"


@dataclass
class ProcessingEvent:
    """Событие в процессе обработки объекта"""
    timestamp: str
    event_type: EventType
    message: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            'timestamp': self.timestamp,
            'event_type': self.event_type.value,
            'message': self.message,
            'details': self.details
        }


@dataclass
class PropertyLog:
    """Полный лог обработки одного объекта недвижимости"""
    property_id: str
    url: Optional[str]
    started_at: str
    completed_at: Optional[str] = None
    status: str = "processing"  # processing, completed, failed

    # Основная информация об объекте
    property_info: Dict[str, Any] = field(default_factory=dict)

    # События в хронологическом порядке
    events: List[ProcessingEvent] = field(default_factory=list)

    # Этапы обработки
    parsing_data: Dict[str, Any] = field(default_factory=dict)
    comparables_data: List[Dict[str, Any]] = field(default_factory=list)
    market_stats: Dict[str, Any] = field(default_factory=dict)
    adjustments: Dict[str, Any] = field(default_factory=dict)
    fair_price_result: Dict[str, Any] = field(default_factory=dict)
    scenarios: List[Dict[str, Any]] = field(default_factory=list)

    # Метрики производительности
    metrics: Dict[str, Any] = field(default_factory=dict)

    def add_event(self, event_type: EventType, message: str, details: Dict[str, Any] = None):
        """Добавить событие в лог"""
        event = ProcessingEvent(
            timestamp=datetime.now().isoformat(),
            event_type=event_type,
            message=message,
            details=details or {}
        )
        self.events.append(event)

    def complete(self, status: str = "completed"):
        """Завершить обработку"""
        self.completed_at = datetime.now().isoformat()
        self.status = status

    def to_dict(self) -> Dict:
        """Конвертировать в словарь для JSON"""
        return {
            'property_id': self.property_id,
            'url': self.url,
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'status': self.status,
            'property_info': self.property_info,
            'events': [e.to_dict() for e in self.events],
            'parsing_data': self.parsing_data,
            'comparables_data': self.comparables_data,
            'market_stats': self.market_stats,
            'adjustments': self.adjustments,
            'fair_price_result': self.fair_price_result,
            'scenarios': self.scenarios,
            'metrics': self.metrics
        }

    def to_json(self, indent: int = 2) -> str:
        """Экспорт в JSON"""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


class PropertyTracker:
    """
    Менеджер для отслеживания обработки множества объектов
    """

    def __init__(self):
        self.logs: Dict[str, PropertyLog] = {}
        self.current_property_id: Optional[str] = None

    def start_tracking(self, property_id: str, url: Optional[str] = None) -> PropertyLog:
        """Начать отслеживание объекта"""
        log = PropertyLog(
            property_id=property_id,
            url=url,
            started_at=datetime.now().isoformat()
        )
        self.logs[property_id] = log
        self.current_property_id = property_id

        log.add_event(
            EventType.PARSING_STARTED,
            f"Начата обработка объекта {property_id}",
            {'url': url}
        )

        return log

    def get_log(self, property_id: str) -> Optional[PropertyLog]:
        """Получить лог по ID объекта"""
        return self.logs.get(property_id)

    def get_current_log(self) -> Optional[PropertyLog]:
        """Получить лог текущего объекта"""
        if self.current_property_id:
            return self.logs.get(self.current_property_id)
        return None

    def add_event(self, property_id: str, event_type: EventType, message: str, details: Dict = None):
        """Добавить событие для объекта"""
        log = self.get_log(property_id)
        if log:
            log.add_event(event_type, message, details)

    def complete_property(self, property_id: str, status: str = "completed"):
        """Завершить обработку объекта"""
        log = self.get_log(property_id)
        if log:
            log.complete(status)

    def get_all_logs(self) -> List[PropertyLog]:
        """Получить все логи"""
        return list(self.logs.values())

    def export_to_json(self, filepath: str):
        """Экспорт всех логов в JSON"""
        data = {
            'export_time': datetime.now().isoformat(),
            'total_properties': len(self.logs),
            'logs': [log.to_dict() for log in self.logs.values()]
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dumps(data, f, indent=2, ensure_ascii=False)

    def get_summary(self) -> Dict[str, Any]:
        """Получить сводку по всем объектам"""
        total = len(self.logs)
        completed = sum(1 for log in self.logs.values() if log.status == "completed")
        failed = sum(1 for log in self.logs.values() if log.status == "failed")
        processing = sum(1 for log in self.logs.values() if log.status == "processing")

        return {
            'total': total,
            'completed': completed,
            'failed': failed,
            'processing': processing,
            'success_rate': (completed / total * 100) if total > 0 else 0
        }


# Глобальный tracker для использования во всём приложении
global_tracker = PropertyTracker()


def get_tracker() -> PropertyTracker:
    """Получить глобальный tracker"""
    return global_tracker
