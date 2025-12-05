"""
Модуль конфигурации HOUSLER

Централизованное управление настройками приложения.
Все значения загружаются из переменных окружения с разумными дефолтами.

Использование:
    from src.config import settings

    print(settings.REDIS_HOST)
    print(settings.is_production)
"""

from .settings import Settings, get_settings

# Singleton instance
settings = get_settings()

__all__ = ['Settings', 'settings', 'get_settings']
