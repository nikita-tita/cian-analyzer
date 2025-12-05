"""
Маршруты (Blueprints) HOUSLER

Модульная структура HTTP-эндпоинтов.
"""

from .contacts import contacts_bp

__all__ = ['contacts_bp']
