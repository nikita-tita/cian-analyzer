"""
Nodriver Strategy - Максимальный обход детекции

Основные возможности:
1. Патченный Chrome DevTools Protocol (CDP)
2. Обход Cloudflare, DataDome, PerimeterX
3. Полная имитация реального браузера
4. Нет selenium/playwright артефактов

Применение:
- Avito (DataDome)
- Сайты с Cloudflare
- Сайты с продвинутой bot-detection

Важно: Nodriver работает медленнее чем Playwright, используйте как fallback
"""

import logging
import time
import asyncio
from typing import Optional
from .base_strategy import BaseParsingStrategy

logger = logging.getLogger(__name__)

# Попытка импорта nodriver
try:
    import nodriver as uc
    from nodriver import Browser, Tab
    NODRIVER_AVAILABLE = True
except ImportError:
    NODRIVER_AVAILABLE = False
    logger.warning("⚠️ nodriver не установлен. Установите: pip install nodriver")


class NodriverStrategy(BaseParsingStrategy):
    """
    Стратегия парсинга через Nodriver

    Обходит практически все виды детекции ботов
    """

    def __init__(
        self,
        headless: bool = False,  # Nodriver лучше работает в не-headless режиме
        timeout: int = 30,
        block_resources: bool = True
    ):
        """
        Args:
            headless: Запускать браузер в фоновом режиме (не рекомендуется для Nodriver)
            timeout: Таймаут загрузки страницы (секунды)
            block_resources: Блокировать картинки/шрифты
        """
        super().__init__(name='nodriver')

        if not NODRIVER_AVAILABLE:
            raise ImportError("nodriver не установлен")

        self.headless = headless
        self.timeout = timeout
        self.block_resources = block_resources

        # Браузер (создается для каждого запроса, т.к. nodriver async)
        self.browser: Optional[Browser] = None

        logger.info(f"✓ NodriverStrategy инициализирован (headless={headless})")

        if headless:
            logger.warning("⚠️ Nodriver в headless режиме может быть менее эффективен")

    async def _fetch_content_async(self, url: str, **kwargs) -> Optional[str]:
        """
        Получить контент через Nodriver (async)

        Args:
            url: URL для загрузки
            **kwargs: wait_for_selector, additional_wait

        Returns:
            HTML контент или None
        """
        browser = None
        tab = None

        try:
            logger.info(f"🚀 Запуск Nodriver для {url}")

            start_time = time.time()

            # Запускаем браузер
            browser = await uc.start(
                headless=self.headless,
                browser_args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                ]
            )

            # Открываем вкладку
            tab = await browser.get(url, new_tab=True)

            # Ждем загрузки
            wait_for_selector = kwargs.get('wait_for_selector', 'body')
            additional_wait = kwargs.get('additional_wait', 2)  # секунды

            try:
                await tab.wait_for(wait_for_selector, timeout=self.timeout)
            except:
                logger.warning(f"⚠️ Selector '{wait_for_selector}' не найден, но продолжаем")

            # Дополнительное ожидание
            if additional_wait > 0:
                await tab.sleep(additional_wait)

            # Получаем HTML
            html = await tab.get_content()

            elapsed = time.time() - start_time

            if html and len(html) > 1000:
                logger.info(f"✓ Nodriver SUCCESS ({elapsed:.2f}s): {len(html)} байт")
                return html
            else:
                logger.error(f"❌ Получен пустой/короткий HTML ({len(html) if html else 0} байт)")
                return None

        except asyncio.TimeoutError:
            logger.error(f"❌ Nodriver timeout после {self.timeout}s")
            return None

        except Exception as e:
            logger.error(f"❌ Nodriver error: {e}")
            return None

        finally:
            # Закрываем браузер
            if browser:
                try:
                    await browser.stop()
                except:
                    pass

    def fetch_content(self, url: str, **kwargs) -> Optional[str]:
        """
        Получить HTML контент страницы (синхронная обертка)

        Args:
            url: URL для загрузки
            **kwargs: wait_for_selector, additional_wait

        Returns:
            HTML контент или None
        """
        self.stats['requests'] += 1

        try:
            # Запускаем async функцию в event loop
            html = asyncio.run(self._fetch_content_async(url, **kwargs))

            if html:
                self.stats['success'] += 1
                return html
            else:
                self.stats['errors'] += 1
                return None

        except Exception as e:
            logger.error(f"❌ Nodriver sync wrapper error: {e}")
            self.stats['errors'] += 1
            return None

    async def fetch_content_multiple_async(self, urls: list[str], **kwargs) -> list[Optional[str]]:
        """
        Получить контент нескольких URL последовательно через один браузер

        Args:
            urls: Список URL
            **kwargs: wait_for_selector, additional_wait

        Returns:
            Список HTML контента
        """
        results = []
        browser = None

        try:
            logger.info(f"🚀 Запуск Nodriver для {len(urls)} URLs")

            # Запускаем браузер один раз
            browser = await uc.start(
                headless=self.headless,
                browser_args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                ]
            )

            for i, url in enumerate(urls):
                logger.info(f"🌐 [{i+1}/{len(urls)}] Загрузка: {url[:60]}...")

                try:
                    # Открываем вкладку
                    tab = await browser.get(url, new_tab=True)

                    # Ждем загрузки
                    wait_for_selector = kwargs.get('wait_for_selector', 'body')
                    additional_wait = kwargs.get('additional_wait', 2)

                    try:
                        await tab.wait_for(wait_for_selector, timeout=self.timeout)
                    except:
                        logger.warning(f"⚠️ Selector не найден для {url[:40]}")

                    if additional_wait > 0:
                        await tab.sleep(additional_wait)

                    # Получаем HTML
                    html = await tab.get_content()

                    results.append(html if html else None)

                    # Закрываем вкладку
                    await tab.close()

                except Exception as e:
                    logger.error(f"❌ Ошибка для {url}: {e}")
                    results.append(None)

        finally:
            if browser:
                try:
                    await browser.stop()
                except:
                    pass

        return results
