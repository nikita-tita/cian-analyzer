"""
Базовый класс для всех стратегий парсинга
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


class BaseParsingStrategy(ABC):
    """
    Базовый класс для стратегии парсинга

    Каждая стратегия реализует:
    - fetch_content() - получение контента страницы
    - fetch_api() - получение данных через API (опционально)
    - supports_source() - проверка поддержки источника
    """

    def __init__(self, name: str):
        """
        Args:
            name: Название стратегии
        """
        self.name = name
        self.stats = {
            'requests': 0,
            'errors': 0,
            'success': 0,
        }

    @abstractmethod
    def fetch_content(self, url: str, **kwargs) -> Optional[str]:
        """
        Получить HTML контент страницы

        Args:
            url: URL для загрузки
            **kwargs: Дополнительные параметры

        Returns:
            HTML контент или None при ошибке
        """
        pass

    def fetch_api(self, api_url: str, **kwargs) -> Optional[Dict]:
        """
        Получить данные через API

        Args:
            api_url: URL API endpoint
            **kwargs: Дополнительные параметры (headers, params и т.д.)

        Returns:
            JSON данные или None при ошибке
        """
        # По умолчанию не поддерживается, переопределяется в подклассах
        logger.warning(f"{self.name} не поддерживает fetch_api")
        return None

    def supports_source(self, source: str) -> bool:
        """
        Проверить, поддерживает ли стратегия данный источник

        Args:
            source: Название источника ('cian', 'domclick', etc.)

        Returns:
            True если поддерживает
        """
        # По умолчанию поддерживает все источники
        return True

    def get_stats(self) -> Dict:
        """Получить статистику работы стратегии"""
        return {
            **self.stats,
            'success_rate': (
                self.stats['success'] / self.stats['requests'] * 100
                if self.stats['requests'] > 0 else 0
            )
        }

    def __repr__(self):
        return f"<{self.__class__.__name__} name='{self.name}'>"
