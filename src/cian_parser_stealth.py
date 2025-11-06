#!/usr/bin/env python3
"""
Cian.ru Parser с ПОЛНЫМ anti-detection для обхода Cloudflare
Основано на лучших практиках 2025 года
"""

from playwright.sync_api import sync_playwright, Playwright, Browser, BrowserContext, Page
from typing import Dict, List, Optional
import logging
import time
import random
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CianParserStealth:
    """
    Stealth-парсер Cian.ru с anti-detection техниками
    """

    def __init__(self, headless: bool = True, delay: float = 1.0):
        """
        Инициализация парсера
        
        Args:
            headless: Запуск в headless режиме
            delay: Задержка между действиями (секунды)
        """
        self.headless = headless
        self.delay = delay
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None

    def __enter__(self):
        """Context manager entry"""
        self.playwright = sync_playwright().start()
        
        logger.info("🚀 Запуск stealth браузера...")
        
        # Запускаем с anti-detection параметрами
        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
                '--disable-setuid-sandbox',
            ]
        )

        # Создаем контекст с реалистичными параметрами
        self.context = self.browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='ru-RU',
            timezone_id='Europe/Moscow',
            extra_http_headers={
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
        )

        # Убираем признаки автоматизации через JavaScript
        self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            Object.defineProperty(navigator, 'languages', {
                get: () => ['ru-RU', 'ru', 'en-US', 'en']
            });
            
            window.chrome = {
                runtime: {}
            };
        """)

        logger.info("✅ Браузер готов")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        logger.info("✅ Браузер закрыт")

    def _extract_characteristics(self, page: Page) -> Dict[str, str]:
        """Извлечение всех характеристик"""
        characteristics = {}

        try:
            items = page.locator('[data-testid="OfferSummaryInfoItem"]').all()
            logger.info(f"   Найдено {len(items)} элементов характеристик")

            for item in items:
                try:
                    paragraphs = item.locator('p').all()
                    if len(paragraphs) >= 2:
                        key = paragraphs[0].text_content().strip()
                        value = paragraphs[1].text_content().strip()
                        if key and value:
                            characteristics[key] = value
                except:
                    pass

            # Дополнительно извлекаем этаж из meta
            try:
                og_title = page.locator('meta[property="og:title"]').first
                if og_title:
                    content = og_title.get_attribute('content')
                    if content:
                        floor_match = re.search(r'этаж (\d+/\d+)', content, re.IGNORECASE)
                        if floor_match:
                            characteristics['Этаж'] = floor_match.group(1)
            except:
                pass

        except Exception as e:
            logger.error(f"   ⚠️ Ошибка извлечения характеристик: {e}")

        return characteristics

    def parse_detail_page_full(self, url: str) -> Dict:
        """
        Полный парсинг страницы объявления с anti-detection
        
        Args:
            url: URL объявления
            
        Returns:
            Dict с полной информацией
        """
        result = {
            'url': url,
            'title': None,
            'price': None,
            'price_raw': None,
            'currency': 'RUB',
            'price_per_sqm': None,
            'description': None,
            'address': None,
            'metro': [],
            'characteristics': {},
            'images': [],
            'seller': {},
        }

        try:
            page = self.context.new_page()
            
            logger.info(f"📄 Загрузка страницы: {url}")
            
            # Случайная задержка (имитация человека)
            time.sleep(random.uniform(0.5, 1.5))

            # Загружаем с увеличенным timeout
            page.goto(url, wait_until='domcontentloaded', timeout=60000)
            
            # Ждем критические элементы
            try:
                page.wait_for_selector('h1', timeout=10000)
            except:
                logger.warning("   ⚠️ Заголовок не загрузился быстро, продолжаем...")

            # Дополнительное ожидание
            time.sleep(2 + random.uniform(0, 1))

            # Эмулируем человеческое поведение - скроллинг
            page.evaluate('window.scrollTo(0, document.body.scrollHeight / 4)')
            time.sleep(0.3)
            page.evaluate('window.scrollTo(0, 0)')
            time.sleep(0.3)

            # Заголовок
            try:
                h1 = page.locator('h1').first
                if h1:
                    result['title'] = h1.text_content().strip()
            except:
                pass

            # Цена
            try:
                price_selectors = [
                    '[data-testid="price-amount"]',
                    '[data-name="PriceInfo"]',
                    '[itemprop="price"]',
                ]
                for selector in price_selectors:
                    price_elem = page.locator(selector).first
                    if price_elem:
                        price_text = price_elem.text_content()
                        result['price'] = price_text.strip()
                        price_match = re.search(r'(\d+[\s\d]*)', price_text.replace(' ', ''))
                        if price_match:
                            result['price_raw'] = int(price_match.group(1).replace(' ', ''))
                        break
                
                # Если не нашли, пробуем из meta
                if not result['price']:
                    og_title = page.locator('meta[property="og:title"]').first
                    if og_title:
                        content = og_title.get_attribute('content')
                        if content:
                            price_match = re.search(r'(\d+\s*\d+\s*\d+)\s*руб', content)
                            if price_match:
                                result['price'] = price_match.group(1) + ' ₽'
                                result['price_raw'] = int(price_match.group(1).replace(' ', ''))
            except:
                pass

            # Адрес
            try:
                address_elem = page.locator('[data-name="Geo"]').first
                if address_elem:
                    result['address'] = address_elem.text_content().strip()
            except:
                pass

            # Метро
            try:
                metro_items = page.locator('[data-name="UndergroundLabel"]').all()
                for item in metro_items:
                    metro_text = item.text_content().strip()
                    if metro_text and metro_text not in result['metro']:
                        result['metro'].append(metro_text)
            except:
                pass

            # Описание
            try:
                desc_elem = page.locator('[data-name="Description"]').first
                if desc_elem:
                    result['description'] = desc_elem.text_content().strip()
            except:
                pass

            # Характеристики
            logger.info("📊 Извлечение характеристик...")
            result['characteristics'] = self._extract_characteristics(page)

            # Изображения
            try:
                img_elements = page.locator('img[src*="cdn-cian.ru/images"]').all()
                images = []
                for img in img_elements[:30]:  # Ограничиваем 30
                    src = img.get_attribute('src')
                    if src and src.startswith('http') and 'cdn-cian' in src:
                        images.append(src)
                result['images'] = list(dict.fromkeys(images))
            except:
                pass

            logger.info(f"✅ Успешно извлечено: {len(result['characteristics'])} характеристик, {len(result['images'])} фото")

            page.close()

        except Exception as e:
            logger.error(f"❌ Ошибка парсинга: {e}")
            result['error'] = str(e)

        return result


# Для совместимости с текущим кодом
CianParserEnhanced = CianParserStealth
