"""
Иерархия исключений для HOUSLER

Единая система исключений для всего приложения.
Позволяет обрабатывать ошибки специфично на каждом уровне.

Иерархия:
    HouslerError (базовый)
    ├── ValidationError (валидация входных данных)
    │   ├── URLValidationError (невалидный URL)
    │   ├── SSRFError (попытка SSRF атаки)
    │   └── PropertyValidationError (невалидные данные объекта)
    ├── ParsingError (ошибки парсинга)
    │   ├── SourceNotSupportedError (источник не поддерживается)
    │   ├── PageNotFoundError (страница не найдена)
    │   ├── ParsingTimeoutError (превышено время парсинга)
    │   └── RateLimitedError (сайт заблокировал запросы)
    ├── AnalysisError (ошибки анализа)
    │   ├── InsufficientDataError (недостаточно данных)
    │   └── CalculationError (ошибка расчёта)
    ├── SessionError (ошибки сессий)
    │   ├── SessionNotFoundError (сессия не найдена)
    │   └── SessionExpiredError (сессия истекла)
    └── ExportError (ошибки экспорта)
        └── PDFGenerationError (ошибка генерации PDF)
"""

from typing import Optional, Dict, Any


class HouslerError(Exception):
    """
    Базовое исключение для всех ошибок HOUSLER

    Attributes:
        message: Человекочитаемое сообщение об ошибке
        error_code: Код ошибки для API (например, 'VALIDATION_ERROR')
        details: Дополнительные детали для логирования
    """

    error_code: str = 'INTERNAL_ERROR'
    http_status: int = 500

    def __init__(
        self,
        message: str,
        error_code: str = None,
        details: Dict[str, Any] = None
    ):
        super().__init__(message)
        self.message = message
        if error_code:
            self.error_code = error_code
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в dict для JSON ответа"""
        result = {
            'error': self.error_code,
            'message': self.message
        }
        if self.details:
            result['details'] = self.details
        return result


# ═══════════════════════════════════════════════════════════════════════════
# VALIDATION ERRORS (400 Bad Request)
# ═══════════════════════════════════════════════════════════════════════════

class ValidationError(HouslerError):
    """Базовая ошибка валидации входных данных"""
    error_code = 'VALIDATION_ERROR'
    http_status = 400


class URLValidationError(ValidationError):
    """Невалидный URL"""
    error_code = 'INVALID_URL'

    def __init__(self, url: str, reason: str = None):
        message = f"Невалидный URL: {url}"
        if reason:
            message = f"{message}. {reason}"
        super().__init__(message, details={'url': url, 'reason': reason})


class SSRFError(ValidationError):
    """
    Попытка SSRF (Server-Side Request Forgery) атаки

    Возникает при попытке обратиться к:
    - Внутренним IP адресам (127.0.0.1, 192.168.*, 10.*, etc.)
    - Запрещённым протоколам (file://, ftp://, etc.)
    - Доменам не из whitelist
    """
    error_code = 'SSRF_BLOCKED'
    http_status = 403

    def __init__(self, url: str, reason: str):
        message = f"Доступ заблокирован: {reason}"
        super().__init__(message, details={'url': url, 'reason': reason})


class PropertyValidationError(ValidationError):
    """Невалидные данные объекта недвижимости"""
    error_code = 'INVALID_PROPERTY_DATA'

    def __init__(self, field: str, value: Any, reason: str):
        message = f"Невалидное значение поля '{field}': {reason}"
        super().__init__(message, details={'field': field, 'value': value, 'reason': reason})


# ═══════════════════════════════════════════════════════════════════════════
# PARSING ERRORS (422 Unprocessable Entity / 502 Bad Gateway)
# ═══════════════════════════════════════════════════════════════════════════

class ParsingError(HouslerError):
    """Базовая ошибка парсинга"""
    error_code = 'PARSING_ERROR'
    http_status = 422

    def __init__(self, message: str, url: str = None, **kwargs):
        details = kwargs.pop('details', {})
        if url:
            details['url'] = url
        super().__init__(message, details=details, **kwargs)


class SourceNotSupportedError(ParsingError):
    """Источник (домен) не поддерживается"""
    error_code = 'SOURCE_NOT_SUPPORTED'

    def __init__(self, url: str, supported_sources: list = None):
        message = f"Источник не поддерживается. Используйте ЦИАН или ДомКлик."
        super().__init__(
            message,
            url=url,
            details={'supported_sources': supported_sources or ['cian.ru', 'domclick.ru']}
        )


class PageNotFoundError(ParsingError):
    """Страница объявления не найдена (404 или удалена)"""
    error_code = 'PAGE_NOT_FOUND'
    http_status = 404

    def __init__(self, url: str):
        message = "Объявление не найдено. Возможно, оно удалено или снято с публикации."
        super().__init__(message, url=url)


class ParsingTimeoutError(ParsingError):
    """Превышено время ожидания при парсинге"""
    error_code = 'PARSING_TIMEOUT'
    http_status = 504

    def __init__(self, url: str, timeout_seconds: int):
        message = f"Превышено время ожидания ({timeout_seconds} сек). Попробуйте позже."
        super().__init__(message, url=url, details={'timeout_seconds': timeout_seconds})


class RateLimitedError(ParsingError):
    """Сайт заблокировал запросы (rate limiting)"""
    error_code = 'RATE_LIMITED'
    http_status = 429

    def __init__(self, url: str, retry_after: int = None):
        message = "Слишком много запросов к источнику. Попробуйте через несколько минут."
        details = {}
        if retry_after:
            details['retry_after_seconds'] = retry_after
        super().__init__(message, url=url, details=details)


# ═══════════════════════════════════════════════════════════════════════════
# ANALYSIS ERRORS (422 Unprocessable Entity)
# ═══════════════════════════════════════════════════════════════════════════

class AnalysisError(HouslerError):
    """Базовая ошибка анализа"""
    error_code = 'ANALYSIS_ERROR'
    http_status = 422


class InsufficientDataError(AnalysisError):
    """Недостаточно данных для анализа"""
    error_code = 'INSUFFICIENT_DATA'

    def __init__(self, required: int, actual: int, data_type: str = 'аналогов'):
        message = f"Недостаточно {data_type} для анализа. Требуется минимум {required}, найдено {actual}."
        super().__init__(message, details={'required': required, 'actual': actual, 'data_type': data_type})


class CalculationError(AnalysisError):
    """Ошибка при выполнении расчёта"""
    error_code = 'CALCULATION_ERROR'

    def __init__(self, calculation_type: str, reason: str):
        message = f"Ошибка расчёта '{calculation_type}': {reason}"
        super().__init__(message, details={'calculation_type': calculation_type, 'reason': reason})


# ═══════════════════════════════════════════════════════════════════════════
# SESSION ERRORS (404 Not Found / 410 Gone)
# ═══════════════════════════════════════════════════════════════════════════

class SessionError(HouslerError):
    """Базовая ошибка сессии"""
    error_code = 'SESSION_ERROR'
    http_status = 400


class SessionNotFoundError(SessionError):
    """Сессия не найдена"""
    error_code = 'SESSION_NOT_FOUND'
    http_status = 404

    def __init__(self, session_id: str):
        message = "Сессия не найдена. Начните анализ заново."
        super().__init__(message, details={'session_id': session_id})


class SessionExpiredError(SessionError):
    """Сессия истекла"""
    error_code = 'SESSION_EXPIRED'
    http_status = 410

    def __init__(self, session_id: str, expired_at: str = None):
        message = "Сессия истекла. Начните анализ заново."
        details = {'session_id': session_id}
        if expired_at:
            details['expired_at'] = expired_at
        super().__init__(message, details=details)


# ═══════════════════════════════════════════════════════════════════════════
# EXPORT ERRORS (500 Internal Server Error)
# ═══════════════════════════════════════════════════════════════════════════

class ExportError(HouslerError):
    """Базовая ошибка экспорта"""
    error_code = 'EXPORT_ERROR'
    http_status = 500


class PDFGenerationError(ExportError):
    """Ошибка генерации PDF"""
    error_code = 'PDF_GENERATION_ERROR'

    def __init__(self, reason: str):
        message = f"Не удалось сгенерировать PDF: {reason}"
        super().__init__(message, details={'reason': reason})


# ═══════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def wrap_exception(exc: Exception, default_class: type = HouslerError) -> HouslerError:
    """
    Оборачивает произвольное исключение в HouslerError

    Полезно для обработки неожиданных исключений с сохранением контекста.

    Args:
        exc: Оригинальное исключение
        default_class: Класс HouslerError для обёртки

    Returns:
        Экземпляр HouslerError с информацией об оригинальном исключении
    """
    if isinstance(exc, HouslerError):
        return exc

    return default_class(
        message=str(exc),
        details={
            'original_type': type(exc).__name__,
            'original_message': str(exc)
        }
    )
