"""
Browser Pool для эффективного управления Playwright браузерами

Защита от:
- Исчерпание памяти при большом количестве одновременных парсингов
- Утечки ресурсов браузера
- DoS через множественные запросы

Features:
- Пул с ограниченным количеством браузеров
- Переиспользование браузеров
- Автоматическая очистка при ошибках
- Thread-safe операции с блокировками
"""

import logging
import threading
import time
from typing import Optional, List, Dict
from dataclasses import dataclass, field
from datetime import datetime
from playwright.sync_api import sync_playwright, Browser, BrowserContext

from ..config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class BrowserInstance:
    """Инстанс браузера в пуле"""
    browser: Browser
    context: Optional[BrowserContext] = None
    in_use: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    last_used: datetime = field(default_factory=datetime.now)
    use_count: int = 0
    max_uses: int = 50  # Пересоздавать браузер после N использований


class BrowserPool:
    """
    Пул Playwright браузеров с ограничением ресурсов

    CRITICAL для production:
    - Ограничивает количество одновременно открытых браузеров
    - Предотвращает утечки памяти
    - Защищает от DoS атак через парсинг

    Usage:
        pool = BrowserPool(max_browsers=5)
        pool.start()

        browser, context = pool.acquire()
        try:
            # Use browser/context
            pass
        finally:
            pool.release(browser)

        pool.shutdown()
    """

    def __init__(
        self,
        max_browsers: int = 5,
        max_age_seconds: int = 3600,  # 1 час
        headless: bool = True,
        block_resources: bool = True,
        proxy_config: Optional[Dict] = None
    ):
        """
        Args:
            max_browsers: Максимальное количество браузеров в пуле
            max_age_seconds: Максимальный возраст браузера (секунды)
            headless: Запускать браузеры в headless режиме
            block_resources: Блокировать ненужные ресурсы (картинки, шрифты)
            proxy_config: Конфигурация прокси (если None - берётся из settings)
        """
        self.max_browsers = max_browsers
        self.max_age_seconds = max_age_seconds
        self.headless = headless
        self.block_resources = block_resources

        # Получаем прокси из настроек если не передан явно
        if proxy_config is None:
            settings = get_settings()
            self.proxy_config = settings.proxy_config
        else:
            self.proxy_config = proxy_config

        self.playwright = None
        self.browsers: List[BrowserInstance] = []
        self.lock = threading.Lock()  # Thread-safety

        # Метрики
        self.total_acquisitions = 0
        self.total_releases = 0
        self.total_created = 0
        self.total_destroyed = 0

        proxy_info = f", proxy={self.proxy_config['server']}" if self.proxy_config else ""
        logger.info(f"Browser Pool initialized: max_browsers={max_browsers}, headless={headless}{proxy_info}")

    def start(self):
        """Запуск Playwright (необходимо перед использованием)"""
        if self.playwright:
            logger.warning("Playwright already started")
            return

        try:
            logger.info("Starting Playwright...")
            self.playwright = sync_playwright().start()
            logger.info("✓ Playwright started")
        except Exception as e:
            logger.error(f"Failed to start Playwright: {e}")
            raise

    def _create_browser(self) -> BrowserInstance:
        """Создает новый инстанс браузера"""
        if not self.playwright:
            raise RuntimeError("Playwright not started. Call start() first.")

        try:
            logger.info("Creating new browser instance...")

            browser = self.playwright.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-gpu',
                    '--disable-software-rasterizer',
                ]
            )

            # Настройки контекста
            context_options = {
                'viewport': {'width': 1920, 'height': 1080},
                'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'locale': 'ru-RU',
                'timezone_id': 'Europe/Moscow',
            }

            # Добавляем прокси если настроен
            if self.proxy_config:
                context_options['proxy'] = self.proxy_config
                logger.info(f"Browser using proxy: {self.proxy_config['server']}")

            context = browser.new_context(**context_options)

            # Скрываем автоматизацию
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                window.chrome = { runtime: {} };
            """)

            # Блокируем ненужные ресурсы
            if self.block_resources:
                context.route(
                    "**/*.{png,jpg,jpeg,gif,svg,webp,woff,woff2,ttf,mp4,mp3,pdf}",
                    lambda route: route.abort()
                )

            instance = BrowserInstance(browser=browser, context=context)
            self.total_created += 1

            logger.info(f"✓ Browser instance created (total created: {self.total_created})")
            return instance

        except Exception as e:
            logger.error(f"Failed to create browser: {e}")
            raise

    def _destroy_browser(self, instance: BrowserInstance):
        """Уничтожает инстанс браузера"""
        errors = []

        # Закрываем context
        if instance.context:
            try:
                instance.context.close()
            except Exception as e:
                errors.append(f"Context: {e}")

        # Закрываем browser
        if instance.browser:
            try:
                instance.browser.close()
            except Exception as e:
                errors.append(f"Browser: {e}")

        self.total_destroyed += 1

        if errors:
            logger.warning(f"Errors during browser cleanup: {'; '.join(errors)}")
        else:
            logger.info(f"Browser instance destroyed (total destroyed: {self.total_destroyed})")

    def _is_browser_stale(self, instance: BrowserInstance) -> bool:
        """Проверяет, устарел ли браузер"""
        age = (datetime.now() - instance.created_at).total_seconds()

        # Проверка по возрасту
        if age > self.max_age_seconds:
            logger.info(f"Browser is stale: age={age:.0f}s > max={self.max_age_seconds}s")
            return True

        # Проверка по количеству использований
        if instance.use_count >= instance.max_uses:
            logger.info(f"Browser is stale: use_count={instance.use_count} >= max={instance.max_uses}")
            return True

        return False

    def acquire(self, timeout: float = 30.0) -> tuple[Browser, BrowserContext]:
        """
        Получить браузер из пула

        Args:
            timeout: Максимальное время ожидания (секунды)

        Returns:
            (Browser, BrowserContext) tuple

        Raises:
            TimeoutError: если не удалось получить браузер за timeout секунд
        """
        start_time = time.time()

        while True:
            with self.lock:
                # Ищем свободный браузер
                for instance in self.browsers:
                    if not instance.in_use and not self._is_browser_stale(instance):
                        instance.in_use = True
                        instance.last_used = datetime.now()
                        instance.use_count += 1
                        self.total_acquisitions += 1

                        logger.info(
                            f"Browser acquired from pool "
                            f"(in_use: {sum(1 for b in self.browsers if b.in_use)}/{len(self.browsers)}, "
                            f"use_count: {instance.use_count})"
                        )
                        return instance.browser, instance.context

                # Если все браузеры заняты, но есть место для нового
                if len(self.browsers) < self.max_browsers:
                    instance = self._create_browser()
                    instance.in_use = True
                    instance.use_count = 1
                    self.browsers.append(instance)
                    self.total_acquisitions += 1

                    logger.info(f"New browser created (pool size: {len(self.browsers)}/{self.max_browsers})")
                    return instance.browser, instance.context

                # Очищаем устаревшие браузеры
                stale_browsers = [b for b in self.browsers if not b.in_use and self._is_browser_stale(b)]
                for stale in stale_browsers:
                    self._destroy_browser(stale)
                    self.browsers.remove(stale)

            # Проверка таймаута
            if time.time() - start_time > timeout:
                raise TimeoutError(
                    f"Failed to acquire browser within {timeout}s. "
                    f"Pool is full ({self.max_browsers} browsers all in use)"
                )

            # Ждем перед следующей попыткой
            time.sleep(0.5)

    def release(self, browser: Browser):
        """
        Вернуть браузер в пул

        Args:
            browser: Браузер для возврата
        """
        with self.lock:
            for instance in self.browsers:
                if instance.browser == browser:
                    instance.in_use = False
                    self.total_releases += 1

                    logger.info(
                        f"Browser released to pool "
                        f"(in_use: {sum(1 for b in self.browsers if b.in_use)}/{len(self.browsers)})"
                    )
                    return

            logger.warning("Attempted to release browser that's not in pool")

    def shutdown(self):
        """Закрыть все браузеры и Playwright"""
        logger.info("Shutting down browser pool...")

        with self.lock:
            # Закрываем все браузеры
            for instance in self.browsers:
                try:
                    self._destroy_browser(instance)
                except Exception as e:
                    logger.error(f"Error destroying browser during shutdown: {e}")

            self.browsers.clear()

            # Закрываем Playwright
            if self.playwright:
                try:
                    self.playwright.stop()
                    logger.info("✓ Playwright stopped")
                except Exception as e:
                    logger.error(f"Error stopping Playwright: {e}")
                finally:
                    self.playwright = None

        logger.info(
            f"Browser pool shutdown complete. "
            f"Stats: created={self.total_created}, destroyed={self.total_destroyed}, "
            f"acquisitions={self.total_acquisitions}, releases={self.total_releases}"
        )

    def get_stats(self) -> dict:
        """Получить статистику пула"""
        with self.lock:
            return {
                'pool_size': len(self.browsers),
                'max_browsers': self.max_browsers,
                'browsers_in_use': sum(1 for b in self.browsers if b.in_use),
                'browsers_free': sum(1 for b in self.browsers if not b.in_use),
                'total_created': self.total_created,
                'total_destroyed': self.total_destroyed,
                'total_acquisitions': self.total_acquisitions,
                'total_releases': self.total_releases,
                'browsers': [
                    {
                        'in_use': b.in_use,
                        'use_count': b.use_count,
                        'age_seconds': (datetime.now() - b.created_at).total_seconds(),
                    }
                    for b in self.browsers
                ]
            }

    def __enter__(self):
        """Context manager support"""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager support"""
        self.shutdown()


# Глобальный синглтон пула (опционально)
_global_pool: Optional[BrowserPool] = None
_global_pool_lock = threading.Lock()


def get_global_pool(
    max_browsers: int = 5,
    headless: bool = True
) -> BrowserPool:
    """
    Получить глобальный синглтон пула браузеров

    Args:
        max_browsers: Максимальное количество браузеров
        headless: Headless режим

    Returns:
        BrowserPool instance
    """
    global _global_pool

    with _global_pool_lock:
        if _global_pool is None:
            _global_pool = BrowserPool(
                max_browsers=max_browsers,
                headless=headless
            )
            _global_pool.start()
            logger.info("Global browser pool created and started")

        return _global_pool


def shutdown_global_pool():
    """Закрыть глобальный пул браузеров"""
    global _global_pool

    with _global_pool_lock:
        if _global_pool:
            _global_pool.shutdown()
            _global_pool = None
            logger.info("Global browser pool shut down")
