"""
Продвинутая система логирования и мониторинга
Поддерживает структурированное логирование, метрики, алерты
"""

import logging
import sys
import os
import json
from datetime import datetime
from typing import Dict, Any, Optional
from functools import wraps
import time
import traceback


class ColoredFormatter(logging.Formatter):
    """
    Форматтер с цветным выводом для консоли
    """

    # ANSI escape codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'
    }

    EMOJIS = {
        'DEBUG': '🔍',
        'INFO': 'ℹ️',
        'WARNING': '⚠️',
        'ERROR': '❌',
        'CRITICAL': '🚨'
    }

    def format(self, record):
        # Добавляем цвет и эмодзи
        levelname = record.levelname
        color = self.COLORS.get(levelname, self.COLORS['RESET'])
        emoji = self.EMOJIS.get(levelname, '')

        record.levelname = f"{color}{emoji} {levelname}{self.COLORS['RESET']}"

        # Форматируем сообщение
        formatted = super().format(record)

        return formatted


class JSONFormatter(logging.Formatter):
    """
    Форматтер для структурированного JSON логирования
    """

    def format(self, record):
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }

        # Добавляем дополнительные поля
        if hasattr(record, 'extra_data'):
            log_data['extra'] = record.extra_data

        # Добавляем exception info
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }

        return json.dumps(log_data, ensure_ascii=False)


class MetricsLogger:
    """
    Логгер для метрик производительности
    """

    def __init__(self):
        self.metrics: Dict[str, list] = {}

    def record(self, metric_name: str, value: float, tags: Optional[Dict] = None):
        """
        Запись метрики

        Args:
            metric_name: Название метрики
            value: Значение
            tags: Теги для фильтрации
        """
        if metric_name not in self.metrics:
            self.metrics[metric_name] = []

        self.metrics[metric_name].append({
            'timestamp': datetime.now().isoformat(),
            'value': value,
            'tags': tags or {}
        })

    def get_stats(self, metric_name: str) -> Dict[str, float]:
        """
        Получение статистики по метрике

        Args:
            metric_name: Название метрики

        Returns:
            Словарь со статистикой (avg, min, max, count)
        """
        if metric_name not in self.metrics:
            return {}

        values = [m['value'] for m in self.metrics[metric_name]]

        return {
            'count': len(values),
            'avg': sum(values) / len(values) if values else 0,
            'min': min(values) if values else 0,
            'max': max(values) if values else 0,
            'total': sum(values)
        }

    def get_all_stats(self) -> Dict[str, Dict]:
        """
        Получение статистики по всем метрикам

        Returns:
            Словарь с метриками
        """
        return {
            metric_name: self.get_stats(metric_name)
            for metric_name in self.metrics.keys()
        }

    def clear(self, metric_name: Optional[str] = None):
        """
        Очистка метрик

        Args:
            metric_name: Название метрики (если None - очищает все)
        """
        if metric_name:
            self.metrics.pop(metric_name, None)
        else:
            self.metrics.clear()


# Global metrics instance
_metrics = MetricsLogger()


def get_metrics() -> MetricsLogger:
    """Получение глобального экземпляра метрик"""
    return _metrics


def setup_logging(
    level: str = None,
    log_file: str = None,
    json_logs: bool = False,
    colored_console: bool = True
) -> logging.Logger:
    """
    Настройка системы логирования

    Args:
        level: Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Путь к файлу логов (опционально)
        json_logs: Использовать JSON формат для файлов
        colored_console: Цветной вывод в консоль

    Returns:
        Настроенный root logger
    """
    level = level or os.getenv('LOG_LEVEL', 'INFO')
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Очищаем существующие handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    if colored_console:
        console_formatter = ColoredFormatter(
            '%(asctime)s | %(levelname)s | %(name)s | %(message)s',
            datefmt='%H:%M:%S'
        )
    else:
        console_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # File handler (если указан)
    if log_file:
        # Создаем директорию если не существует
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(log_level)

        if json_logs:
            file_formatter = JSONFormatter()
        else:
            file_formatter = logging.Formatter(
                '%(asctime)s | %(levelname)s | %(name)s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )

        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

        root_logger.info(f"📝 Логи пишутся в файл: {log_file}")

    return root_logger


def log_execution_time(logger: Optional[logging.Logger] = None, metric_name: str = None):
    """
    Декоратор для логирования времени выполнения функции

    Args:
        logger: Логгер (по умолчанию создается автоматически)
        metric_name: Название метрики для записи

    Usage:
        @log_execution_time()
        def my_function():
            pass
    """
    def decorator(func):
        nonlocal logger
        if logger is None:
            logger = logging.getLogger(func.__module__)

        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            func_name = func.__name__

            logger.debug(f"▶️ Начало выполнения: {func_name}")

            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time

                logger.info(f"✅ {func_name} завершен за {duration:.3f}s")

                # Записываем метрику
                if metric_name:
                    _metrics.record(metric_name, duration)
                else:
                    _metrics.record(f'execution_time.{func_name}', duration)

                return result

            except Exception as e:
                duration = time.time() - start_time
                logger.error(
                    f"❌ {func_name} завершен с ошибкой за {duration:.3f}s: {e}",
                    exc_info=True
                )
                raise

        return wrapper
    return decorator


def log_api_call(logger: Optional[logging.Logger] = None):
    """
    Декоратор для логирования API вызовов

    Args:
        logger: Логгер (по умолчанию создается автоматически)

    Usage:
        @log_api_call()
        def api_endpoint():
            pass
    """
    def decorator(func):
        nonlocal logger
        if logger is None:
            logger = logging.getLogger(func.__module__)

        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            func_name = func.__name__

            # Логируем входящий запрос
            logger.info(f"📨 API вызов: {func_name}")

            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time

                # Логируем успешный ответ
                logger.info(f"✅ API ответ: {func_name} ({duration:.3f}s)")

                # Записываем метрику
                _metrics.record(f'api.{func_name}.success', duration)
                _metrics.record(f'api.{func_name}.duration', duration)

                return result

            except Exception as e:
                duration = time.time() - start_time

                # Логируем ошибку
                logger.error(
                    f"❌ API ошибка: {func_name} ({duration:.3f}s): {e}",
                    exc_info=True
                )

                # Записываем метрику ошибки
                _metrics.record(f'api.{func_name}.error', 1)

                raise

        return wrapper
    return decorator


def log_parser_call(parser_type: str, logger: Optional[logging.Logger] = None):
    """
    Декоратор для логирования парсинга

    Args:
        parser_type: Тип парсера (playwright, simple, etc.)
        logger: Логгер

    Usage:
        @log_parser_call('playwright')
        def parse_page():
            pass
    """
    def decorator(func):
        nonlocal logger
        if logger is None:
            logger = logging.getLogger(func.__module__)

        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            func_name = func.__name__

            logger.info(f"🕷️ Парсинг [{parser_type}]: {func_name}")

            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time

                logger.info(f"✅ Парсинг завершен [{parser_type}]: {func_name} ({duration:.3f}s)")

                # Записываем метрики
                _metrics.record(f'parser.{parser_type}.success', 1)
                _metrics.record(f'parser.{parser_type}.duration', duration)

                return result

            except Exception as e:
                duration = time.time() - start_time

                logger.error(
                    f"❌ Ошибка парсинга [{parser_type}]: {func_name} ({duration:.3f}s): {e}",
                    exc_info=True
                )

                _metrics.record(f'parser.{parser_type}.error', 1)

                raise

        return wrapper
    return decorator


class StructuredLogger:
    """
    Структурированный логгер с поддержкой дополнительных полей
    """

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)

    def log(
        self,
        level: str,
        message: str,
        extra_data: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        """
        Логирование с дополнительными данными

        Args:
            level: Уровень (debug, info, warning, error, critical)
            message: Сообщение
            extra_data: Дополнительные данные
            **kwargs: Дополнительные параметры для logger
        """
        log_func = getattr(self.logger, level.lower())

        if extra_data:
            # Добавляем extra_data в LogRecord
            extra = {'extra_data': extra_data}
            kwargs.setdefault('extra', {}).update(extra)

        log_func(message, **kwargs)

    def debug(self, message: str, **kwargs):
        self.log('debug', message, **kwargs)

    def info(self, message: str, **kwargs):
        self.log('info', message, **kwargs)

    def warning(self, message: str, **kwargs):
        self.log('warning', message, **kwargs)

    def error(self, message: str, **kwargs):
        self.log('error', message, **kwargs)

    def critical(self, message: str, **kwargs):
        self.log('critical', message, **kwargs)


def get_logger(name: str) -> StructuredLogger:
    """
    Получение структурированного логгера

    Args:
        name: Имя логгера

    Returns:
        StructuredLogger instance
    """
    return StructuredLogger(name)


class PerformanceMonitor:
    """
    Контекстный менеджер для мониторинга производительности
    """

    def __init__(self, operation_name: str, logger: Optional[logging.Logger] = None):
        self.operation_name = operation_name
        self.logger = logger or logging.getLogger(__name__)
        self.start_time = None
        self.duration = None

    def __enter__(self):
        self.start_time = time.time()
        self.logger.debug(f"⏱️ Начало операции: {self.operation_name}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.duration = time.time() - self.start_time

        if exc_type is None:
            self.logger.info(
                f"✅ Операция завершена: {self.operation_name} ({self.duration:.3f}s)"
            )
            _metrics.record(f'operation.{self.operation_name}', self.duration)
        else:
            self.logger.error(
                f"❌ Операция завершена с ошибкой: {self.operation_name} "
                f"({self.duration:.3f}s): {exc_val}"
            )
            _metrics.record(f'operation.{self.operation_name}.error', 1)

        return False  # Не подавляем исключения


# Convenience function
def monitor(operation_name: str, logger: Optional[logging.Logger] = None):
    """
    Создание Performance Monitor

    Usage:
        with monitor('database_query'):
            # some operation
            pass
    """
    return PerformanceMonitor(operation_name, logger)
