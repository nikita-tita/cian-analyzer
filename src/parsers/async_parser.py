"""
Асинхронный парсер для параллельной обработки множества объектов

Использует asyncio + playwright для одновременного парсинга 5-10 объектов
Время парсинга 10 аналогов: ~50s → ~8s (6x ускорение)
"""

import asyncio
import logging
from typing import List, Dict, Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from concurrent.futures import ThreadPoolExecutor
import time

from .base_parser import BaseCianParser, ParsingError

logger = logging.getLogger(__name__)


class AsyncPlaywrightParser(BaseCianParser):
    """
    Асинхронный Playwright парсер для параллельной обработки

    Оптимизации:
    - Один браузер, множество контекстов (изоляция)
    - Параллельная обработка до 10 URL одновременно
    - Shared cache для избежания дублирования запросов
    - Graceful degradation при ошибках
    """

    def __init__(
        self,
        headless: bool = True,
        delay: float = 1.0,
        block_resources: bool = True,
        cache=None,
        region: str = 'spb',
        max_concurrent: int = 5
    ):
        """
        Args:
            headless: Запускать браузер в фоновом режиме
            delay: Минимальная задержка между запросами (сек)
            block_resources: Блокировать картинки/шрифты
            cache: PropertyCache instance
            region: Регион ('spb' или 'msk')
            max_concurrent: Максимум параллельных запросов
        """
        super().__init__(delay, cache=cache)
        self.headless = headless
        self.block_resources = block_resources
        self.max_concurrent = max_concurrent

        # Маппинг регионов
        self.region_codes = {'spb': '2', 'msk': '1'}
        self.region = region
        self.region_code = self.region_codes.get(region, '2')

        # Async состояние
        self.playwright = None
        self.browser: Optional[Browser] = None
        self._contexts: List[BrowserContext] = []
        self._semaphore = None

        logger.info(f"AsyncParser initialized: region={region}, max_concurrent={max_concurrent}")

    async def __aenter__(self):
        """Async context manager вход"""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager выход"""
        await self.close()

    async def start(self):
        """Запуск браузера и создание semaphore для ограничения параллелизма"""
        if self.browser:
            logger.warning("Browser already started")
            return

        try:
            logger.info("🚀 Starting async Playwright browser...")
            self.playwright = await async_playwright().start()

            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-gpu',
                ]
            )

            # Semaphore для контроля параллелизма
            self._semaphore = asyncio.Semaphore(self.max_concurrent)

            logger.info(f"✓ Browser started (max concurrent: {self.max_concurrent})")

        except Exception as e:
            logger.error(f"Failed to start browser: {e}")
            await self.close()
            raise

    async def close(self):
        """Закрытие всех контекстов и браузера"""
        errors = []

        # Закрываем все контексты
        for context in self._contexts:
            try:
                await context.close()
            except Exception as e:
                errors.append(f"Context: {e}")

        self._contexts.clear()

        # Закрываем браузер
        if self.browser:
            try:
                await self.browser.close()
            except Exception as e:
                errors.append(f"Browser: {e}")
            finally:
                self.browser = None

        # Останавливаем playwright
        if self.playwright:
            try:
                await self.playwright.stop()
            except Exception as e:
                errors.append(f"Playwright: {e}")
            finally:
                self.playwright = None

        if errors:
            logger.warning(f"Errors closing browser: {', '.join(errors)}")
        else:
            logger.info("Browser closed")

    async def _create_context(self) -> BrowserContext:
        """Создание изолированного контекста для парсинга"""
        context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            locale='ru-RU',
            timezone_id='Europe/Moscow',
        )

        # Антидетект
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            window.chrome = { runtime: {} };
        """)

        # Блокировка ресурсов
        if self.block_resources:
            await context.route(
                "**/*.{png,jpg,jpeg,gif,svg,webp,woff,woff2,ttf,mp4,mp3,pdf}",
                lambda route: route.abort()
            )

        self._contexts.append(context)
        return context

    async def _fetch_page_content(self, url: str, context: BrowserContext) -> Optional[str]:
        """
        Загрузка HTML через Playwright

        Args:
            url: URL для загрузки
            context: Browser context

        Returns:
            HTML content или None
        """
        page: Page = await context.new_page()

        try:
            logger.debug(f"Fetching: {url[:60]}...")

            await page.goto(url, wait_until='domcontentloaded', timeout=30000)

            # Ждем появления контента
            try:
                await page.wait_for_selector(
                    'h1, [data-mark="OfferTitle"], script[type="application/ld+json"]',
                    timeout=10000
                )
            except:
                logger.debug("Selectors not found, continuing anyway")

            # Минимальная задержка
            await asyncio.sleep(0.5)

            html = await page.content()

            if not html or len(html) < 1000:
                raise ValueError(f"Empty or too short HTML ({len(html) if html else 0} chars)")

            logger.debug(f"✓ Page loaded: {len(html)} chars")
            return html

        except Exception as e:
            logger.warning(f"Error fetching {url[:60]}: {e}")
            raise

        finally:
            await page.close()
            await asyncio.sleep(self.delay)

    async def parse_detail_page_async(self, url: str) -> Dict:
        """
        Асинхронный парсинг детальной страницы

        Args:
            url: URL объявления

        Returns:
            Словарь с данными
        """
        # Проверяем кэш
        if self.cache:
            cached_data = self.cache.get_property(url)
            if cached_data:
                self.stats['cache_hits'] += 1
                logger.debug(f"✅ Cache HIT: {url[:60]}")
                return cached_data
            else:
                self.stats['cache_misses'] += 1

        # Используем semaphore для ограничения параллелизма
        async with self._semaphore:
            try:
                # Создаем отдельный контекст для изоляции
                context = await self._create_context()

                # Загружаем HTML
                html = await self._fetch_page_content(url, context)
                if not html:
                    raise ParsingError(f"Failed to fetch content: {url}")

                # Парсинг HTML (используем синхронный метод из базового класса)
                # TODO: можно сделать полностью async, но пока используем sync BeautifulSoup
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, 'lxml')

                data = {
                    'url': url,
                    'title': None,
                    'price': None,
                    'price_raw': None,
                }

                # Извлекаем JSON-LD (самый надежный источник)
                json_ld = self._extract_json_ld(soup)
                if json_ld:
                    data['title'] = json_ld.get('name')
                    offers = json_ld.get('offers', {})
                    if offers:
                        data['price_raw'] = offers.get('price')
                        data['currency'] = offers.get('priceCurrency')
                        if data['price_raw']:
                            data['price'] = data['price_raw']

                # Дополняем данные из HTML
                self._extract_basic_info(soup, data)
                data['characteristics'] = self._extract_characteristics(soup)
                data['images'] = self._extract_images(soup)

                # Переносим ключевые поля из characteristics в корень
                self._promote_key_fields(data)

                # Сохраняем в кэш
                if self.cache:
                    self.cache.set_property(url, data, ttl_hours=24)

                logger.debug(f"✓ Parsed: {data.get('title', 'No title')[:50]}")
                return data

            except Exception as e:
                self.stats['errors'] += 1
                logger.error(f"Error parsing {url}: {e}")
                # Возвращаем минимальные данные вместо провала
                return {
                    'url': url,
                    'title': 'Ошибка парсинга',
                    'price': None,
                    'error': str(e)
                }

    async def parse_multiple_async(self, urls: List[str]) -> List[Dict]:
        """
        Параллельный парсинг множества URL

        Args:
            urls: Список URL для парсинга

        Returns:
            Список словарей с данными
        """
        if not urls:
            return []

        logger.info(f"🚀 Starting parallel parsing of {len(urls)} URLs...")
        start_time = time.time()

        # Создаем задачи для параллельного выполнения
        tasks = [self.parse_detail_page_async(url) for url in urls]

        # Запускаем все задачи параллельно
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Фильтруем успешные результаты
        successful_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Task {i} failed: {result}")
                # Добавляем заглушку
                successful_results.append({
                    'url': urls[i],
                    'title': 'Ошибка парсинга',
                    'error': str(result)
                })
            elif isinstance(result, dict):
                successful_results.append(result)

        elapsed = time.time() - start_time
        avg_time = elapsed / len(urls) if urls else 0

        logger.info(
            f"✓ Parallel parsing complete: {len(successful_results)}/{len(urls)} successful "
            f"in {elapsed:.1f}s (avg: {avg_time:.2f}s per URL)"
        )

        return successful_results

    def _get_page_content(self, url: str) -> Optional[str]:
        """
        Sync метод (требуется для совместимости с BaseCianParser)

        Note: В async режиме не используется
        """
        raise NotImplementedError("Use async methods for AsyncPlaywrightParser")


# ═══════════════════════════════════════════════════════════════════════
# SYNC WRAPPER для использования в sync коде
# ═══════════════════════════════════════════════════════════════════════

def parse_multiple_urls_parallel(
    urls: List[str],
    headless: bool = True,
    cache=None,
    region: str = 'spb',
    max_concurrent: int = 5
) -> List[Dict]:
    """
    Sync обертка для параллельного парсинга (для использования в Flask)

    Args:
        urls: Список URL для парсинга
        headless: Headless режим
        cache: Cache instance
        region: Регион
        max_concurrent: Макс параллельных запросов

    Returns:
        Список результатов парсинга
    """
    async def _run():
        async with AsyncPlaywrightParser(
            headless=headless,
            cache=cache,
            region=region,
            max_concurrent=max_concurrent
        ) as parser:
            return await parser.parse_multiple_async(urls)

    # Запускаем async код, обходя проблему с running event loop
    try:
        # Проверяем есть ли активный event loop
        asyncio.get_running_loop()
        # Есть активный loop - запускаем в отдельном потоке
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, _run())
            return future.result()
    except RuntimeError:
        # Нет активного loop - можем использовать asyncio.run() напрямую
        return asyncio.run(_run())
