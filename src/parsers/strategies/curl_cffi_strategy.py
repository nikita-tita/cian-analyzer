"""
curl_cffi Strategy - HTTP клиент с TLS Fingerprint Evasion

Основные возможности:
1. Имитация TLS fingerprint реальных браузеров (Chrome, Firefox, Safari)
2. Обход TLS-based bot detection
3. Быстрые HTTP/HTTPS запросы
4. Поддержка HTTP/2, HTTP/3

Применение:
- API endpoints (Domclick, Yandex GraphQL)
- Сайты с TLS fingerprinting защитой
- Быстрые запросы без браузера
"""

import logging
import time
import json
from typing import Optional, Dict
from .base_strategy import BaseParsingStrategy

logger = logging.getLogger(__name__)

# Попытка импорта curl_cffi
try:
    from curl_cffi import requests as cffi_requests
    from curl_cffi.requests import Session
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False
    logger.warning("⚠️ curl_cffi не установлен. Установите: pip install curl-cffi")


class CurlCffiStrategy(BaseParsingStrategy):
    """
    Стратегия парсинга через curl_cffi

    Имитирует TLS fingerprint реального браузера для обхода защит
    """

    def __init__(
        self,
        impersonate: str = 'chrome110',
        timeout: int = 30,
        max_retries: int = 3
    ):
        """
        Args:
            impersonate: Какой браузер имитировать:
                - 'chrome110', 'chrome107', 'chrome104', 'chrome101'
                - 'edge101', 'edge99'
                - 'safari15_5', 'safari15_3'
                - 'firefox109', 'firefox108', 'firefox102'
            timeout: Таймаут запроса (секунды)
            max_retries: Максимальное количество повторов
        """
        super().__init__(name='curl_cffi')

        if not CURL_CFFI_AVAILABLE:
            raise ImportError("curl_cffi не установлен")

        self.impersonate = impersonate
        self.timeout = timeout
        self.max_retries = max_retries

        # Создаем сессию
        self.session = Session(impersonate=impersonate)

        # Заголовки по умолчанию
        self.default_headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'max-age=0',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
        }

        logger.info(f"✓ CurlCffiStrategy инициализирован (impersonate={impersonate})")

    def fetch_content(self, url: str, **kwargs) -> Optional[str]:
        """
        Получить HTML контент страницы

        Args:
            url: URL для загрузки
            **kwargs: headers, params, proxy и т.д.

        Returns:
            HTML контент или None
        """
        self.stats['requests'] += 1

        headers = kwargs.get('headers', {})
        headers = {**self.default_headers, **headers}

        params = kwargs.get('params', {})
        proxy = kwargs.get('proxy', None)

        for attempt in range(self.max_retries):
            try:
                logger.debug(f"curl_cffi GET: {url} (attempt {attempt+1}/{self.max_retries})")

                start_time = time.time()

                response = self.session.get(
                    url,
                    headers=headers,
                    params=params,
                    proxies={'http': proxy, 'https': proxy} if proxy else None,
                    timeout=self.timeout,
                    allow_redirects=True
                )

                elapsed = time.time() - start_time

                if response.status_code == 200:
                    logger.info(f"✓ curl_cffi SUCCESS ({elapsed:.2f}s): {url[:60]}...")
                    self.stats['success'] += 1
                    return response.text

                elif response.status_code in [301, 302, 303, 307, 308]:
                    # Редирект (обрабатывается автоматически, но логируем)
                    logger.warning(f"⚠️ Редирект {response.status_code}: {url}")
                    continue

                elif response.status_code in [403, 429]:
                    # Rate limit или блокировка
                    logger.warning(f"⚠️ Блокировка {response.status_code}: {url}")
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue

                else:
                    logger.error(f"❌ HTTP {response.status_code}: {url}")
                    self.stats['errors'] += 1
                    return None

            except Exception as e:
                logger.error(f"❌ curl_cffi error (attempt {attempt+1}): {e}")

                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    self.stats['errors'] += 1
                    return None

        logger.error(f"❌ curl_cffi: Все {self.max_retries} попытки провалились")
        self.stats['errors'] += 1
        return None

    def fetch_api(self, api_url: str, **kwargs) -> Optional[Dict]:
        """
        Получить JSON данные через API

        Args:
            api_url: URL API endpoint
            **kwargs: method, headers, json, params

        Returns:
            JSON данные или None
        """
        self.stats['requests'] += 1

        method = kwargs.get('method', 'GET').upper()
        headers = kwargs.get('headers', {})
        json_data = kwargs.get('json', None)
        params = kwargs.get('params', {})
        proxy = kwargs.get('proxy', None)

        # Заголовки для API
        api_headers = {
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'ru-RU,ru;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Content-Type': 'application/json' if json_data else 'application/x-www-form-urlencoded',
        }
        headers = {**api_headers, **headers}

        for attempt in range(self.max_retries):
            try:
                logger.debug(f"curl_cffi {method}: {api_url} (attempt {attempt+1}/{self.max_retries})")

                start_time = time.time()

                if method == 'GET':
                    response = self.session.get(
                        api_url,
                        headers=headers,
                        params=params,
                        proxies={'http': proxy, 'https': proxy} if proxy else None,
                        timeout=self.timeout
                    )
                elif method == 'POST':
                    response = self.session.post(
                        api_url,
                        headers=headers,
                        json=json_data,
                        params=params,
                        proxies={'http': proxy, 'https': proxy} if proxy else None,
                        timeout=self.timeout
                    )
                else:
                    logger.error(f"Неподдерживаемый метод: {method}")
                    return None

                elapsed = time.time() - start_time

                if response.status_code == 200:
                    logger.info(f"✓ curl_cffi API SUCCESS ({elapsed:.2f}s): {api_url[:60]}...")

                    try:
                        data = response.json()
                        self.stats['success'] += 1
                        return data
                    except json.JSONDecodeError as e:
                        logger.error(f"❌ JSON decode error: {e}")
                        logger.debug(f"Response text: {response.text[:500]}")
                        self.stats['errors'] += 1
                        return None

                elif response.status_code in [403, 429]:
                    logger.warning(f"⚠️ API Блокировка {response.status_code}: {api_url}")
                    time.sleep(2 ** attempt)
                    continue

                else:
                    logger.error(f"❌ API HTTP {response.status_code}: {api_url}")
                    logger.debug(f"Response: {response.text[:500]}")
                    self.stats['errors'] += 1
                    return None

            except Exception as e:
                logger.error(f"❌ curl_cffi API error (attempt {attempt+1}): {e}")

                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    self.stats['errors'] += 1
                    return None

        logger.error(f"❌ curl_cffi API: Все {self.max_retries} попытки провалились")
        self.stats['errors'] += 1
        return None

    def __del__(self):
        """Закрываем сессию при уничтожении объекта"""
        if hasattr(self, 'session'):
            try:
                self.session.close()
            except:
                pass
