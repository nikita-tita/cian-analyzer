#!/usr/bin/env python3
"""
Cian.ru Parser с извлечением похожих объявлений через поиск по адресу
"""

from playwright.sync_api import sync_playwright, Page
from typing import Dict, List, Optional
import logging
import time
import random
import re
import urllib.parse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CianParserWithSimilar:
    """
    Парсер с поиском похожих объявлений в том же доме
    """

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.playwright = None
        self.browser = None
        self.context = None

    def __enter__(self):
        """Context manager entry"""
        self.playwright = sync_playwright().start()
        
        logger.info("🚀 Запуск stealth браузера...")
        
        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ]
        )

        self.context = self.browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='ru-RU',
            timezone_id='Europe/Moscow',
            extra_http_headers={
                'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            }
        )

        self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            window.chrome = { runtime: {} };
        """)

        logger.info("✅ Браузер готов")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def _extract_characteristics(self, page: Page) -> Dict[str, str]:
        """Извлечение характеристик"""
        characteristics = {}

        try:
            items = page.locator('[data-testid="OfferSummaryInfoItem"]').all()
            
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

            # Этаж из meta
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
            logger.error(f"Ошибка извлечения характеристик: {e}")

        return characteristics

    def _search_similar_by_address(self, address: str, city: str = "Санкт-Петербург") -> List[Dict]:
        """
        Поиск похожих объявлений через поиск по адресу
        """
        similar = []
        
        try:
            # Извлекаем улицу из адреса
            # Пример: "Санкт-Петербург, р-н Выборгский, Светлановское, Светлановский пр-кт, 60к2"
            street_match = re.search(r'([А-Яа-яёЁ\s-]+(?:ул\.|улица|пр-кт|проспект|наб\.|набережная)[\s,]+[\dкК\s-]+)', address)
            
            if not street_match:
                # Пробуем более простой паттерн
                parts = address.split(',')
                if len(parts) >= 3:
                    street_part = parts[-1].strip()
                else:
                    return similar
            else:
                street_part = street_match.group(1).strip()
            
            logger.info(f"🔍 Поиск объявлений по адресу: {street_part}")
            
            # Создаем URL для поиска
            search_query = f"{city} {street_part}"
            encoded_query = urllib.parse.quote(search_query)
            
            # URL поиска на Cian
            search_url = f"https://www.cian.ru/cat.php?deal_type=sale&engine_version=2&offer_type=flat&region=2&text={encoded_query}"
            
            page = self.context.new_page()
            page.goto(search_url, wait_until='domcontentloaded', timeout=30000)
            time.sleep(2)
            
            # Ищем карточки объявлений
            cards = page.locator('[data-name="CardComponent"], [data-name="OfferCard"], article').all()
            
            logger.info(f"   Найдено карточек на странице поиска: {len(cards)}")
            
            for card in cards[:10]:  # Берем первые 10
                try:
                    listing = {}
                    
                    # Заголовок
                    title_elem = card.locator('h3, [data-mark="OfferTitle"], a[class*="title"]').first
                    if title_elem:
                        listing['title'] = title_elem.text_content().strip()
                    
                    # Цена
                    price_elem = card.locator('[data-mark="MainPrice"], span[class*="price"]').first
                    if price_elem:
                        listing['price'] = price_elem.text_content().strip()
                    
                    # URL
                    link_elem = card.locator('a[href*="/sale/flat/"]').first
                    if link_elem:
                        href = link_elem.get_attribute('href')
                        if href:
                            listing['url'] = href if href.startswith('http') else f"https://www.cian.ru{href}"
                    
                    # Площадь и этаж из заголовка или описания
                    if 'title' in listing:
                        area_match = re.search(r'(\d+[,.]?\d*)\s*м²', listing['title'])
                        if area_match:
                            listing['area'] = area_match.group(0)
                        
                        floor_match = re.search(r'(\d+)/(\d+)\s*эт', listing['title'])
                        if floor_match:
                            listing['floor'] = f"{floor_match.group(1)}/{floor_match.group(2)}"
                    
                    if listing.get('title') and listing.get('price'):
                        similar.append(listing)
                
                except Exception as e:
                    continue
            
            page.close()
            
            logger.info(f"✅ Найдено похожих объявлений: {len(similar)}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка поиска похожих: {e}")
        
        return similar

    def parse_detail_page_full(self, url: str) -> Dict:
        """
        Полный парсинг с поиском похожих объявлений
        """
        result = {
            'url': url,
            'title': None,
            'price': None,
            'price_raw': None,
            'currency': 'RUB',
            'address': None,
            'metro': [],
            'characteristics': {},
            'images': [],
            'description': None,
            'similar_listings': [],
        }

        try:
            page = self.context.new_page()
            
            logger.info(f"📄 Загрузка страницы: {url}")
            
            time.sleep(random.uniform(0.5, 1.5))
            page.goto(url, wait_until='domcontentloaded', timeout=60000)
            
            try:
                page.wait_for_selector('h1', timeout=10000)
            except:
                pass

            time.sleep(2)

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
            except:
                pass

            # Адрес
            try:
                address_elem = page.locator('[data-name="Geo"]').first
                if address_elem:
                    result['address'] = address_elem.text_content().strip()
            except:
                pass

            # Характеристики
            logger.info("📊 Извлечение характеристик...")
            result['characteristics'] = self._extract_characteristics(page)

            # Изображения
            try:
                img_elements = page.locator('img[src*="cdn-cian.ru/images"]').all()
                images = []
                for img in img_elements[:30]:
                    src = img.get_attribute('src')
                    if src and src.startswith('http'):
                        images.append(src)
                result['images'] = list(dict.fromkeys(images))
            except:
                pass

            page.close()

            # ПОИСК ПОХОЖИХ ОБЪЯВЛЕНИЙ
            if result.get('address'):
                logger.info("🔍 Поиск похожих объявлений в доме...")
                result['similar_listings'] = self._search_similar_by_address(result['address'])

            logger.info(f"✅ Извлечено: {len(result['characteristics'])} характеристик, {len(result['similar_listings'])} похожих")

        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            result['error'] = str(e)

        return result


# Alias для совместимости
CianParserStealth = CianParserWithSimilar
