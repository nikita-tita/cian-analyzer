"""
Асинхронный парсер для параллельного парсинга множества объектов
Использует asyncio и Playwright async API для ускорения
"""

import asyncio
import logging
from typing import List, Dict, Optional, Callable
from datetime import datetime
import time

try:
    from playwright.async_api import async_playwright, Browser, Page, Playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from src.parsers.base_parser import BaseCianParser

logger = logging.getLogger(__name__)


class AsyncCianParser(BaseCianParser):
    """
    Асинхронный парсер для Cian.ru

    Features:
    - Параллельный парсинг множества URL
    - Connection pooling (несколько браузерных контекстов)
    - Автоматическое управление ресурсами
    - Progress callbacks
    - Error handling с retry логикой
    """

    def __init__(
        self,
        headless: bool = True,
        delay: float = 1.0,
        max_concurrent: int = 5,
        timeout: int = 30000,
        retry_attempts: int = 3,
        user_agent: str = None
    ):
        """
        Инициализация асинхронного парсера

        Args:
            headless: Запускать браузер в headless режиме
            delay: Задержка между запросами (секунды)
            max_concurrent: Максимальное количество одновременных запросов
            timeout: Таймаут для страниц (мс)
            retry_attempts: Количество попыток при ошибках
            user_agent: Custom User-Agent
        """
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError(
                "Playwright не установлен. Установите: pip install playwright && playwright install"
            )

        super().__init__()

        self.headless = headless
        self.delay = delay
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.user_agent = user_agent or self._get_random_user_agent()

        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None

        # Статистика
        self.stats = {
            'total_parsed': 0,
            'successful': 0,
            'failed': 0,
            'total_time': 0,
            'avg_time_per_page': 0
        }

    async def __aenter__(self):
        """Async context manager entry"""
        await self._initialize_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self._close_browser()

    async def _initialize_browser(self):
        """Инициализация Playwright и браузера"""
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox'
                ]
            )
            logger.info(f"✅ Async browser launched (max_concurrent={self.max_concurrent})")

        except Exception as e:
            logger.error(f"❌ Ошибка запуска браузера: {e}")
            raise

    async def _close_browser(self):
        """Закрытие браузера"""
        try:
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            logger.info("🔌 Async browser closed")

        except Exception as e:
            logger.error(f"❌ Ошибка закрытия браузера: {e}")

    async def _create_page(self) -> Page:
        """
        Создание новой страницы с настройками

        Returns:
            Настроенная Page
        """
        context = await self.browser.new_context(
            user_agent=self.user_agent,
            viewport={'width': 1920, 'height': 1080},
            locale='ru-RU',
            timezone_id='Europe/Moscow'
        )

        page = await context.new_page()
        page.set_default_timeout(self.timeout)

        return page

    async def _parse_single_page(
        self,
        url: str,
        retry_count: int = 0
    ) -> Optional[Dict]:
        """
        Парсинг одной страницы

        Args:
            url: URL страницы
            retry_count: Текущая попытка (для retry)

        Returns:
            Распарсенные данные или None при ошибке
        """
        page = None
        start_time = time.time()

        try:
            page = await self._create_page()

            logger.debug(f"🕷️ Parsing: {url}")

            # Переходим на страницу
            response = await page.goto(url, wait_until='networkidle')

            if response.status != 200:
                logger.warning(f"⚠️ HTTP {response.status}: {url}")
                if retry_count < self.retry_attempts:
                    await asyncio.sleep(self.delay * 2)
                    return await self._parse_single_page(url, retry_count + 1)
                return None

            # Ждем загрузки контента
            await page.wait_for_load_state('domcontentloaded')
            await asyncio.sleep(0.5)  # Небольшая задержка для JS

            # Извлекаем JSON-LD
            json_ld_data = await self._extract_json_ld_async(page)

            # Извлекаем HTML данные
            html = await page.content()
            html_data = self._parse_html_content(html)

            # Объединяем данные
            parsed_data = self._merge_parsed_data(json_ld_data, html_data)
            parsed_data['url'] = url

            duration = time.time() - start_time
            logger.debug(f"✅ Parsed in {duration:.2f}s: {url}")

            self.stats['successful'] += 1
            self.stats['total_time'] += duration

            # Задержка между запросами
            await asyncio.sleep(self.delay)

            return parsed_data

        except Exception as e:
            logger.error(f"❌ Ошибка парсинга {url}: {e}")

            # Retry логика
            if retry_count < self.retry_attempts:
                logger.info(f"🔄 Retry {retry_count + 1}/{self.retry_attempts}: {url}")
                await asyncio.sleep(self.delay * 2)
                return await self._parse_single_page(url, retry_count + 1)

            self.stats['failed'] += 1
            return None

        finally:
            if page:
                await page.close()
                await page.context.close()

    async def _extract_json_ld_async(self, page: Page) -> Dict:
        """
        Асинхронное извлечение JSON-LD данных

        Args:
            page: Playwright Page

        Returns:
            Извлеченные данные
        """
        try:
            json_ld_content = await page.locator('script[type="application/ld+json"]').first.inner_text()
            if json_ld_content:
                import json
                data = json.loads(json_ld_content)
                return self._extract_from_json_ld(data)

        except Exception as e:
            logger.debug(f"⚠️ Не удалось извлечь JSON-LD: {e}")

        return {}

    async def parse_urls(
        self,
        urls: List[str],
        progress_callback: Optional[Callable] = None
    ) -> List[Dict]:
        """
        Параллельный парсинг списка URL

        Args:
            urls: Список URL для парсинга
            progress_callback: Callback для отслеживания прогресса (url, index, total, data)

        Returns:
            Список распарсенных данных
        """
        if not self.browser:
            await self._initialize_browser()

        self.stats['total_parsed'] = len(urls)
        self.stats['successful'] = 0
        self.stats['failed'] = 0
        self.stats['total_time'] = 0

        logger.info(f"🚀 Starting async parsing of {len(urls)} URLs (max_concurrent={self.max_concurrent})")

        # Семафор для ограничения параллельных запросов
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def parse_with_semaphore(url: str, index: int):
            async with semaphore:
                result = await self._parse_single_page(url)

                if progress_callback:
                    progress_callback(url, index, len(urls), result)

                return result

        # Запускаем параллельный парсинг
        start_time = time.time()
        tasks = [parse_with_semaphore(url, i) for i, url in enumerate(urls)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        total_duration = time.time() - start_time
        self.stats['total_time'] = total_duration

        # Фильтруем None и исключения
        valid_results = [
            r for r in results
            if r is not None and not isinstance(r, Exception)
        ]

        self.stats['avg_time_per_page'] = (
            total_duration / len(urls) if urls else 0
        )

        logger.info(
            f"✅ Async parsing completed: {len(valid_results)}/{len(urls)} successful "
            f"in {total_duration:.2f}s (avg: {self.stats['avg_time_per_page']:.2f}s/page)"
        )

        return valid_results

    async def search_similar_async(
        self,
        target_property: Dict,
        limit: int = 20
    ) -> List[Dict]:
        """
        Асинхронный поиск аналогов

        Args:
            target_property: Целевой объект
            limit: Количество аналогов

        Returns:
            Список аналогов
        """
        if not self.browser:
            await self._initialize_browser()

        # Строим поисковый запрос
        search_url = self._build_search_url(target_property)

        logger.info(f"🔍 Async search: {search_url}")

        # Получаем список URL аналогов
        page = None
        try:
            page = await self._create_page()
            await page.goto(search_url, wait_until='networkidle')
            await asyncio.sleep(1)

            html = await page.content()
            comparable_urls = self._extract_listing_urls(html, limit=limit)

            logger.info(f"📋 Found {len(comparable_urls)} comparable URLs")

        except Exception as e:
            logger.error(f"❌ Ошибка поиска: {e}")
            return []

        finally:
            if page:
                await page.close()
                await page.context.close()

        # Параллельно парсим все найденные URL
        comparables = await self.parse_urls(comparable_urls)

        return comparables

    def get_stats(self) -> Dict:
        """
        Получение статистики парсинга

        Returns:
            Словарь со статистикой
        """
        return self.stats.copy()


# Convenience functions для синхронного использования

def parse_urls_sync(
    urls: List[str],
    headless: bool = True,
    delay: float = 1.0,
    max_concurrent: int = 5,
    progress_callback: Optional[Callable] = None
) -> List[Dict]:
    """
    Синхронная обертка для асинхронного парсинга

    Args:
        urls: Список URL
        headless: Headless режим
        delay: Задержка между запросами
        max_concurrent: Максимальное количество одновременных запросов
        progress_callback: Callback для прогресса

    Returns:
        Список распарсенных данных
    """
    async def _async_parse():
        async with AsyncCianParser(
            headless=headless,
            delay=delay,
            max_concurrent=max_concurrent
        ) as parser:
            return await parser.parse_urls(urls, progress_callback)

    return asyncio.run(_async_parse())


def search_similar_async_sync(
    target_property: Dict,
    limit: int = 20,
    headless: bool = True
) -> List[Dict]:
    """
    Синхронная обертка для асинхронного поиска аналогов

    Args:
        target_property: Целевой объект
        limit: Количество аналогов
        headless: Headless режим

    Returns:
        Список аналогов
    """
    async def _async_search():
        async with AsyncCianParser(headless=headless) as parser:
            return await parser.search_similar_async(target_property, limit)

    return asyncio.run(_async_search())
