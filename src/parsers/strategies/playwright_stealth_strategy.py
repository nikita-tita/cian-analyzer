"""
Playwright-Stealth Strategy - Браузер с антидетект патчами

Основные возможности:
1. Playwright + патчи для обхода детекции
2. Скрытие автоматизации (webdriver, chrome.runtime и т.д.)
3. Имитация реального поведения пользователя
4. Обход PerimeterX, DataDome (частично)

Применение:
- Cian (PerimeterX защита)
- Domclick (средняя защита)
- Любые сайты с browser fingerprinting
"""

import logging
import time
from typing import Optional
from .base_strategy import BaseParsingStrategy

logger = logging.getLogger(__name__)

# Попытка импорта playwright и stealth
try:
    from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("⚠️ Playwright не установлен. Установите: pip install playwright && playwright install")

try:
    from playwright_stealth import stealth_sync
    STEALTH_AVAILABLE = True
except ImportError:
    STEALTH_AVAILABLE = False
    logger.warning("⚠️ playwright-stealth не установлен. Установите: pip install playwright-stealth")


class PlaywrightStealthStrategy(BaseParsingStrategy):
    """
    Стратегия парсинга через Playwright + Stealth патчи

    Обходит многие виды browser fingerprinting и автодетекции
    """

    def __init__(
        self,
        headless: bool = True,
        block_resources: bool = True,
        stealth_mode: bool = True,
        timeout: int = 30000
    ):
        """
        Args:
            headless: Запускать браузер в фоновом режиме
            block_resources: Блокировать картинки/шрифты для ускорения
            stealth_mode: Включить stealth патчи
            timeout: Таймаут загрузки страницы (миллисекунды)
        """
        super().__init__(name='playwright_stealth')

        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError("Playwright не установлен")

        if stealth_mode and not STEALTH_AVAILABLE:
            logger.warning("⚠️ Stealth патчи недоступны, используется обычный Playwright")
            stealth_mode = False

        self.headless = headless
        self.block_resources = block_resources
        self.stealth_mode = stealth_mode
        self.timeout = timeout

        # Браузер (ленивая инициализация)
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None

        logger.info(f"✓ PlaywrightStealthStrategy инициализирован (stealth={stealth_mode})")

    def _start_browser(self):
        """Запустить браузер"""
        if self.browser:
            return

        logger.info("🚀 Запуск Playwright браузера с stealth патчами...")

        self.playwright = sync_playwright().start()

        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-gpu',
                '--disable-software-rasterizer',
                '--disable-web-security',  # Для обхода CORS (осторожно!)
            ]
        )

        self.context = self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='ru-RU',
            timezone_id='Europe/Moscow',
            permissions=['geolocation'],  # Даем разрешения как реальный пользователь
        )

        # Скрываем автоматизацию (базовые патчи)
        self.context.add_init_script("""
            // Удаляем webdriver флаг
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });

            // Добавляем chrome runtime
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {}
            };

            // Переопределяем permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );

            // Скрываем автоматизацию в plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });

            // Скрываем headless режим
            Object.defineProperty(navigator, 'languages', {
                get: () => ['ru-RU', 'ru', 'en-US', 'en']
            });
        """)

        # Блокируем ненужные ресурсы для ускорения
        if self.block_resources:
            self.context.route(
                "**/*.{png,jpg,jpeg,gif,svg,webp,woff,woff2,ttf,mp4,mp3,pdf}",
                lambda route: route.abort()
            )

        logger.info("✓ Playwright браузер запущен")

    def _close_browser(self):
        """Закрыть браузер"""
        errors = []

        if self.context:
            try:
                self.context.close()
            except Exception as e:
                errors.append(f"Context: {e}")
            finally:
                self.context = None

        if self.browser:
            try:
                self.browser.close()
            except Exception as e:
                errors.append(f"Browser: {e}")
            finally:
                self.browser = None

        if self.playwright:
            try:
                self.playwright.stop()
            except Exception as e:
                errors.append(f"Playwright: {e}")
            finally:
                self.playwright = None

        if errors:
            logger.warning(f"Ошибки при закрытии: {', '.join(errors)}")
        else:
            logger.info("Браузер закрыт")

    def fetch_content(self, url: str, **kwargs) -> Optional[str]:
        """
        Получить HTML контент страницы через браузер

        Args:
            url: URL для загрузки
            **kwargs: wait_for_selector, additional_wait

        Returns:
            HTML контент или None
        """
        self.stats['requests'] += 1

        # Запускаем браузер если не запущен
        self._start_browser()

        wait_for_selector = kwargs.get('wait_for_selector', 'body')
        additional_wait = kwargs.get('additional_wait', 1000)  # ms

        page: Page = None

        try:
            page = self.context.new_page()

            # Применяем stealth патчи если включены
            if self.stealth_mode and STEALTH_AVAILABLE:
                stealth_sync(page)

            logger.info(f"🌐 Загрузка через Playwright-Stealth: {url}")

            start_time = time.time()

            # Загружаем страницу
            page.goto(url, wait_until='domcontentloaded', timeout=self.timeout)

            # Ждем появления контента
            try:
                page.wait_for_selector(wait_for_selector, timeout=10000)
            except:
                logger.warning(f"⚠️ Selector '{wait_for_selector}' не найден, но продолжаем")

            # Дополнительное ожидание для динамического контента
            if additional_wait > 0:
                page.wait_for_timeout(additional_wait)

            html = page.content()

            elapsed = time.time() - start_time

            if html and len(html) > 1000:
                logger.info(f"✓ Playwright-Stealth SUCCESS ({elapsed:.2f}s): {len(html)} байт")
                self.stats['success'] += 1
                return html
            else:
                logger.error(f"❌ Получен пустой/короткий HTML ({len(html) if html else 0} байт)")
                self.stats['errors'] += 1
                return None

        except Exception as e:
            logger.error(f"❌ Playwright-Stealth error: {e}")
            self.stats['errors'] += 1
            return None

        finally:
            if page:
                try:
                    page.close()
                except:
                    pass

    def __del__(self):
        """Закрываем браузер при уничтожении объекта"""
        self._close_browser()

    def __enter__(self):
        """Context manager вход"""
        self._start_browser()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager выход"""
        self._close_browser()
