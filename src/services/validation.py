"""
Сервис валидации данных

Централизованная валидация пользовательского ввода.
"""

import re
from typing import Optional
from urllib.parse import urlparse

from src.config import settings
from src.exceptions import URLValidationError, SSRFError


def validate_phone(phone: str) -> bool:
    """
    Валидация номера телефона

    Args:
        phone: Номер телефона

    Returns:
        True если формат корректный
    """
    # Удаляем всё кроме цифр и + в начале
    cleaned = re.sub(r'[^\d+]', '', phone)
    # Должно быть 10-15 цифр, опционально начинается с +
    return bool(re.match(r'^\+?\d{10,15}$', cleaned))


def validate_name(name: str) -> bool:
    """
    Валидация имени

    Args:
        name: Имя пользователя

    Returns:
        True если формат корректный (буквы, пробелы, дефисы, 2-100 символов)
    """
    if len(name) < 2 or len(name) > 100:
        return False
    # Разрешаем unicode буквы, пробелы, дефисы, апострофы
    return bool(re.match(r"^[\w\s\-']+$", name, re.UNICODE))


def sanitize_string(text: str, max_length: int = 1000) -> str:
    """
    Очистка строки от опасных символов

    Args:
        text: Исходная строка
        max_length: Максимальная длина

    Returns:
        Очищенная строка
    """
    if not text:
        return ''

    # Обрезаем
    text = text[:max_length]

    # Удаляем управляющие символы (кроме \n, \t)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

    # Нормализуем пробелы
    text = ' '.join(text.split())

    return text.strip()


def validate_url(url: str) -> None:
    """
    Валидация URL для парсинга (защита от SSRF)

    Args:
        url: URL для проверки

    Raises:
        URLValidationError: Если URL некорректный
        SSRFError: Если URL указывает на запрещённый домен
    """
    if not url:
        raise URLValidationError("URL не может быть пустым")

    # Базовая валидация
    if len(url) > 2048:
        raise URLValidationError("URL слишком длинный")

    if not url.startswith(('http://', 'https://')):
        raise URLValidationError("URL должен начинаться с http:// или https://")

    try:
        parsed = urlparse(url)
    except Exception:
        raise URLValidationError("Некорректный формат URL")

    if not parsed.netloc:
        raise URLValidationError("Некорректный формат URL")

    # SSRF защита - проверяем домен
    domain = parsed.netloc.lower()

    # Удаляем порт если есть
    if ':' in domain:
        domain = domain.split(':')[0]

    # Проверяем по белому списку
    allowed = False
    for allowed_domain in settings.ALLOWED_PARSING_DOMAINS:
        if domain == allowed_domain or domain.endswith('.' + allowed_domain):
            allowed = True
            break

    if not allowed:
        raise SSRFError(
            f"Домен {domain} не разрешён для парсинга",
            details={'domain': domain, 'allowed': settings.ALLOWED_PARSING_DOMAINS}
        )

    # Дополнительная защита от внутренних адресов
    forbidden_patterns = [
        r'^localhost',
        r'^127\.',
        r'^192\.168\.',
        r'^10\.',
        r'^172\.(1[6-9]|2[0-9]|3[0-1])\.',
        r'^0\.',
        r'\.local$',
        r'^169\.254\.',  # link-local
    ]

    for pattern in forbidden_patterns:
        if re.match(pattern, domain):
            raise SSRFError(
                "Доступ к внутренним адресам запрещён",
                details={'domain': domain}
            )


def extract_cian_id(url: str) -> Optional[int]:
    """
    Извлечь ID объявления из URL ЦИАН

    Args:
        url: URL объявления

    Returns:
        ID объявления или None
    """
    if not url:
        return None

    # Паттерны URL ЦИАН:
    # https://spb.cian.ru/sale/flat/123456789/
    # https://www.cian.ru/rent/commercial/987654321/
    match = re.search(r'/(\d{7,12})/?(?:\?|$)', url)
    if match:
        return int(match.group(1))

    return None
