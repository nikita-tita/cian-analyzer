"""
Lambda Parser Client

HTTP клиент для вызова AWS Lambda парсера.
Используется как fallback когда локальный Playwright парсер не справился.

Использование:
    from src.services import lambda_client

    # Парсинг через Lambda
    result = lambda_client.parse("https://spb.cian.ru/sale/flat/123/")
    if result:
        print(result['title'], result['price'])
"""

import os
import json
import logging
import urllib.request
import urllib.error
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class LambdaParserClient:
    """
    HTTP клиент для AWS Lambda парсера

    Конфигурация через env vars:
        LAMBDA_PARSER_URL: URL API Gateway endpoint
        LAMBDA_API_KEY: API Key для авторизации (опционально)
    """

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: int = 60
    ):
        """
        Args:
            api_url: URL Lambda API (по умолчанию из env LAMBDA_PARSER_URL)
            api_key: API Key (по умолчанию из env LAMBDA_API_KEY)
            timeout: Таймаут запроса в секундах
        """
        self.api_url = api_url or os.environ.get('LAMBDA_PARSER_URL', '')
        self.api_key = api_key or os.environ.get('LAMBDA_API_KEY', '')
        self.timeout = timeout
        self._enabled = bool(self.api_url)

        if self._enabled:
            logger.info(f"Lambda parser client configured: {self.api_url[:50]}...")
        else:
            logger.debug("Lambda parser client disabled (no LAMBDA_PARSER_URL)")

    @property
    def enabled(self) -> bool:
        """Проверить, настроен ли Lambda клиент"""
        return self._enabled

    def parse(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Парсинг URL через Lambda

        Args:
            url: Cian URL для парсинга

        Returns:
            Словарь с данными объекта или None при ошибке
        """
        if not self._enabled:
            logger.warning("Lambda parser not configured, skipping")
            return None

        logger.info(f"Lambda parse request: {url}")

        try:
            # Подготовка запроса
            payload = json.dumps({'url': url}).encode('utf-8')

            headers = {
                'Content-Type': 'application/json',
            }

            if self.api_key:
                headers['X-Api-Key'] = self.api_key

            req = urllib.request.Request(
                self.api_url,
                data=payload,
                headers=headers,
                method='POST'
            )

            # Выполнение запроса
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                result = json.loads(response.read().decode('utf-8'))

            # Проверка результата
            if result.get('success'):
                data = result.get('data', {})
                logger.info(f"Lambda parse success: {data.get('title', 'Unknown')[:50]}")
                return data
            else:
                error = result.get('error', 'Unknown error')
                logger.error(f"Lambda parse failed: {error}")
                return None

        except urllib.error.HTTPError as e:
            logger.error(f"Lambda HTTP error {e.code}: {e.reason}")
            return None
        except urllib.error.URLError as e:
            logger.error(f"Lambda URL error: {e.reason}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Lambda JSON decode error: {e}")
            return None
        except Exception as e:
            logger.error(f"Lambda parse error: {e}")
            return None

    def health_check(self) -> bool:
        """
        Проверка доступности Lambda API

        Returns:
            True если API доступен
        """
        if not self._enabled:
            return False

        try:
            # Отправляем невалидный URL для быстрой проверки
            result = self.parse("https://invalid-url-for-health-check")
            # Если получили ответ (даже с ошибкой) - API работает
            return True
        except Exception:
            return False


# Singleton instance
_lambda_client: Optional[LambdaParserClient] = None


def get_lambda_client() -> LambdaParserClient:
    """
    Получить singleton экземпляр Lambda клиента

    Returns:
        LambdaParserClient instance
    """
    global _lambda_client
    if _lambda_client is None:
        _lambda_client = LambdaParserClient()
    return _lambda_client


# Удобный алиас для импорта
lambda_client = get_lambda_client()
