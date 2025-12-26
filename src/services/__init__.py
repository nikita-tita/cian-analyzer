"""
Сервисы HOUSLER

Бизнес-логика, отделённая от HTTP-слоя.
"""

from .telegram import TelegramNotifier, telegram_notifier
from .validation import (
    validate_phone,
    validate_name,
    validate_url,
    sanitize_string,
    extract_cian_id,
)
from .lambda_client import LambdaParserClient, get_lambda_client, lambda_client

__all__ = [
    'TelegramNotifier',
    'telegram_notifier',
    'validate_phone',
    'validate_name',
    'validate_url',
    'sanitize_string',
    'extract_cian_id',
    'LambdaParserClient',
    'get_lambda_client',
    'lambda_client',
]
