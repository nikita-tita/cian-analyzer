"""
httpx Strategy - Современный async HTTP клиент с HTTP/2

Основные возможности:
1. Асинхронные запросы (async/await)
2. HTTP/2 поддержка
3. Connection pooling
4. Автоматические retry

Применение:
- Массовые API запросы
- Параллельный парсинг
- GraphQL endpoints (Yandex)
"""

import logging
import time
import asyncio
from typing import Optional, Dict, List
from .base_strategy import BaseParsingStrategy

logger = logging.getLogger(__name__)

# Попытка импорта httpx
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    logger.warning("⚠️ httpx не установлен. Установите: pip install httpx[http2]")


class HttpxStrategy(BaseParsingStrategy):
    """
    Стратегия парсинга через httpx

    Поддерживает async запросы и HTTP/2
    """

    def __init__(
        self,
        timeout: int = 30,
        max_retries: int = 3,
        enable_http2: bool = True
    ):
        """
        Args:
            timeout: Таймаут запроса (секунды)
            max_retries: Максимальное количество повторов
            enable_http2: Включить HTTP/2
        """
        super().__init__(name='httpx')

        if not HTTPX_AVAILABLE:
            raise ImportError("httpx не установлен")

        self.timeout = timeout
        self.max_retries = max_retries
        self.enable_http2 = enable_http2

        # Создаем синхронный клиент
        self.client = httpx.Client(
            http2=enable_http2,
            timeout=timeout,
            follow_redirects=True,
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)
        )

        # Асинхронный клиент (создается при необходимости)
        self.async_client = None

        # Заголовки по умолчанию
        self.default_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
        }

        logger.info(f"✓ HttpxStrategy инициализирован (HTTP/2={enable_http2})")

    def fetch_content(self, url: str, **kwargs) -> Optional[str]:
        """
        Получить HTML контент страницы (синхронно)

        Args:
            url: URL для загрузки
            **kwargs: headers, params, proxy

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
                logger.debug(f"httpx GET: {url} (attempt {attempt+1}/{self.max_retries})")

                start_time = time.time()

                proxies = {'http://': proxy, 'https://': proxy} if proxy else None

                response = self.client.get(
                    url,
                    headers=headers,
                    params=params,
                    proxies=proxies
                )

                elapsed = time.time() - start_time

                if response.status_code == 200:
                    logger.info(f"✓ httpx SUCCESS ({elapsed:.2f}s): {url[:60]}...")
                    self.stats['success'] += 1
                    return response.text

                elif response.status_code in [403, 429]:
                    logger.warning(f"⚠️ HTTP {response.status_code}: {url}")
                    time.sleep(2 ** attempt)
                    continue

                else:
                    logger.error(f"❌ HTTP {response.status_code}: {url}")
                    self.stats['errors'] += 1
                    return None

            except httpx.TimeoutException:
                logger.warning(f"⏱️ httpx timeout (attempt {attempt+1})")
                if attempt < self.max_retries - 1:
                    time.sleep(1)
                    continue

            except Exception as e:
                logger.error(f"❌ httpx error (attempt {attempt+1}): {e}")

                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    self.stats['errors'] += 1
                    return None

        logger.error(f"❌ httpx: Все {self.max_retries} попытки провалились")
        self.stats['errors'] += 1
        return None

    def fetch_api(self, api_url: str, **kwargs) -> Optional[Dict]:
        """
        Получить JSON данные через API (синхронно)

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
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'ru-RU,ru;q=0.9',
            'Content-Type': 'application/json' if json_data else 'application/x-www-form-urlencoded',
        }
        headers = {**api_headers, **headers}

        for attempt in range(self.max_retries):
            try:
                logger.debug(f"httpx {method}: {api_url} (attempt {attempt+1}/{self.max_retries})")

                start_time = time.time()

                proxies = {'http://': proxy, 'https://': proxy} if proxy else None

                if method == 'GET':
                    response = self.client.get(
                        api_url,
                        headers=headers,
                        params=params,
                        proxies=proxies
                    )
                elif method == 'POST':
                    response = self.client.post(
                        api_url,
                        headers=headers,
                        json=json_data,
                        params=params,
                        proxies=proxies
                    )
                else:
                    logger.error(f"Неподдерживаемый метод: {method}")
                    return None

                elapsed = time.time() - start_time

                if response.status_code == 200:
                    logger.info(f"✓ httpx API SUCCESS ({elapsed:.2f}s): {api_url[:60]}...")
                    data = response.json()
                    self.stats['success'] += 1
                    return data

                elif response.status_code in [403, 429]:
                    logger.warning(f"⚠️ API HTTP {response.status_code}: {api_url}")
                    time.sleep(2 ** attempt)
                    continue

                else:
                    logger.error(f"❌ API HTTP {response.status_code}: {api_url}")
                    self.stats['errors'] += 1
                    return None

            except Exception as e:
                logger.error(f"❌ httpx API error (attempt {attempt+1}): {e}")

                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    self.stats['errors'] += 1
                    return None

        logger.error(f"❌ httpx API: Все {self.max_retries} попытки провалились")
        self.stats['errors'] += 1
        return None

    async def fetch_content_async(self, url: str, **kwargs) -> Optional[str]:
        """
        Получить HTML контент асинхронно

        Args:
            url: URL для загрузки
            **kwargs: headers, params, proxy

        Returns:
            HTML контент или None
        """
        if not self.async_client:
            self.async_client = httpx.AsyncClient(
                http2=self.enable_http2,
                timeout=self.timeout,
                follow_redirects=True
            )

        headers = kwargs.get('headers', {})
        headers = {**self.default_headers, **headers}

        params = kwargs.get('params', {})

        try:
            response = await self.async_client.get(url, headers=headers, params=params)

            if response.status_code == 200:
                return response.text
            else:
                logger.error(f"❌ async HTTP {response.status_code}: {url}")
                return None

        except Exception as e:
            logger.error(f"❌ async httpx error: {e}")
            return None

    async def fetch_many_async(self, urls: List[str], **kwargs) -> List[Optional[str]]:
        """
        Получить контент нескольких URL параллельно

        Args:
            urls: Список URL
            **kwargs: headers, params

        Returns:
            Список HTML контента (или None для провалившихся)
        """
        tasks = [self.fetch_content_async(url, **kwargs) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        processed = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"❌ Error fetching {urls[i]}: {result}")
                processed.append(None)
            else:
                processed.append(result)

        return processed

    def __del__(self):
        """Закрываем клиенты при уничтожении объекта"""
        if hasattr(self, 'client'):
            try:
                self.client.close()
            except:
                pass

        if hasattr(self, 'async_client') and self.async_client:
            try:
                # Для async клиента нужен event loop
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        loop.create_task(self.async_client.aclose())
                    else:
                        loop.run_until_complete(self.async_client.aclose())
                except:
                    pass
            except:
                pass
