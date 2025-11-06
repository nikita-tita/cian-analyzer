#!/usr/bin/env python3
"""
Cian.ru Parser с использованием breadcrumbs для поиска похожих объявлений
"""

from playwright.sync_api import sync_playwright, Page
from typing import Dict, List, Optional
import logging
import time
import random
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CianParserBreadcrumbs:
    """
    Парсер с поиском через breadcrumbs (хлебные крошки)
    """

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.playwright = None
        self.browser = None
        self.context = None

    def __enter__(self):
        self.playwright = sync_playwright().start()
        
        logger.info("🚀 Запуск браузера...")
        
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
        """Извлечение всех характеристик"""
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
            logger.error(f"Ошибка характеристик: {e}")

        return characteristics

    def _find_breadcrumb_link(self, page: Page) -> Optional[str]:
        """
        Находим ссылку на страницу поиска через breadcrumbs
        """
        try:
            # Ищем breadcrumbs (хлебные крошки)
            breadcrumb_selectors = [
                'nav[data-name="Breadcrumbs"] a',
                '[data-name="Breadcrumbs"] a',
                'nav a[href*="/cat.php"]',
                'a[href*="deal_type=sale"]',
            ]
            
            for selector in breadcrumb_selectors:
                links = page.locator(selector).all()
                
                for link in links:
                    href = link.get_attribute('href')
                    text = link.text_content()
                    
                    # Ищем ссылку на страницу поиска (не главную, не регион)
                    if href and '/cat.php' in href and 'deal_type=sale' in href:
                        full_url = href if href.startswith('http') else f"https://www.cian.ru{href}"
                        logger.info(f"🔗 Найден breadcrumb: '{text}' -> {full_url}")
                        return full_url
            
            logger.warning("⚠️ Breadcrumb не найден")
            return None
            
        except Exception as e:
            logger.error(f"Ошибка поиска breadcrumb: {e}")
            return None

    def _parse_listing_card(self, card, page: Page) -> Optional[Dict]:
        """
        Парсинг одной карточки объявления на странице поиска
        """
        try:
            listing = {}
            
            # URL объявления
            link = card.locator('a[href*="/sale/flat/"]').first
            if link:
                href = link.get_attribute('href')
                if href:
                    listing['url'] = href if href.startswith('http') else f"https://www.cian.ru{href}"
            
            if not listing.get('url'):
                return None
            
            # Заголовок
            title_selectors = [
                '[data-mark="OfferTitle"]',
                'h3',
                'span[data-mark="OfferTitle"]'
            ]
            for sel in title_selectors:
                title_elem = card.locator(sel).first
                if title_elem:
                    listing['title'] = title_elem.text_content().strip()
                    break
            
            # Цена
            price_selectors = [
                '[data-mark="MainPrice"]',
                'span[data-mark="MainPrice"]',
                '[class*="price"]'
            ]
            for sel in price_selectors:
                price_elem = card.locator(sel).first
                if price_elem:
                    price_text = price_elem.text_content().strip()
                    if price_text and ('₽' in price_text or 'руб' in price_text):
                        listing['price'] = price_text
                        # Извлекаем число
                        price_match = re.search(r'(\d+[\s\d]*)', price_text.replace(' ', ''))
                        if price_match:
                            listing['price_raw'] = int(price_match.group(1).replace(' ', ''))
                        break
            
            # Площадь и этаж из текста
            text_content = card.text_content()
            
            area_match = re.search(r'(\d+[,.]?\d*)\s*м²', text_content)
            if area_match:
                listing['area'] = area_match.group(0)
            
            floor_match = re.search(r'(\d+)/(\d+)\s*эт', text_content)
            if floor_match:
                listing['floor'] = f"{floor_match.group(1)}/{floor_match.group(2)}"
            
            return listing if listing.get('title') and listing.get('price') else None
            
        except Exception as e:
            logger.debug(f"Ошибка парсинга карточки: {e}")
            return None

    def _parse_full_listing(self, url: str) -> Dict:
        """
        Полный парсинг одного объявления (для похожих)
        """
        result = {
            'url': url,
            'title': None,
            'price': None,
            'characteristics': {},
        }
        
        try:
            page = self.context.new_page()
            
            logger.info(f"   📄 Парсинг: {url[:60]}...")
            
            page.goto(url, wait_until='domcontentloaded', timeout=30000)
            time.sleep(1)
            
            # Заголовок
            try:
                h1 = page.locator('h1').first
                if h1:
                    result['title'] = h1.text_content().strip()
            except:
                pass
            
            # Цена
            try:
                price_elem = page.locator('[data-testid="price-amount"]').first
                if price_elem:
                    result['price'] = price_elem.text_content().strip()
            except:
                pass
            
            # Характеристики
            result['characteristics'] = self._extract_characteristics(page)
            
            page.close()
            
        except Exception as e:
            logger.debug(f"   ⚠️ Ошибка: {e}")
        
        return result

    def _get_similar_from_search(self, breadcrumb_url: str, max_similar: int = 10) -> List[Dict]:
        """
        Получаем похожие объявления со страницы поиска
        """
        similar = []
        
        try:
            logger.info(f"🔍 Открываем страницу поиска...")
            
            page = self.context.new_page()
            page.goto(breadcrumb_url, wait_until='domcontentloaded', timeout=30000)
            time.sleep(2)
            
            # Ищем карточки объявлений
            card_selectors = [
                '[data-name="CardComponent"]',
                'article[data-name="CardComponent"]',
                'div[data-name="OfferCard"]',
            ]
            
            cards = []
            for selector in card_selectors:
                cards = page.locator(selector).all()
                if cards:
                    logger.info(f"   Найдено {len(cards)} карточек")
                    break
            
            # Парсим карточки
            for i, card in enumerate(cards[:max_similar]):
                listing = self._parse_listing_card(card, page)
                if listing:
                    similar.append(listing)
                    logger.info(f"   ✅ [{i+1}] {listing.get('title', 'N/A')[:40]}... - {listing.get('price', 'N/A')}")
            
            page.close()
            
            logger.info(f"✅ Собрано {len(similar)} похожих объявлений")
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения похожих: {e}")
        
        return similar

    def _get_full_data_for_similar(self, similar_list: List[Dict], max_full: int = 5) -> List[Dict]:
        """
        Получаем ПОЛНЫЕ данные (все характеристики) для похожих объявлений
        """
        logger.info(f"📊 Получаем полные данные для {min(len(similar_list), max_full)} похожих...")
        
        full_similar = []
        
        for i, listing in enumerate(similar_list[:max_full]):
            if listing.get('url'):
                full_data = self._parse_full_listing(listing['url'])
                
                # Объединяем данные
                listing.update(full_data)
                full_similar.append(listing)
                
                time.sleep(1)  # Пауза между запросами
        
        logger.info(f"✅ Получены полные данные для {len(full_similar)} объявлений")
        
        return full_similar

    def parse_detail_page_full(self, url: str, get_full_similar: bool = True) -> Dict:
        """
        Полный парсинг с похожими объявлениями через breadcrumbs
        
        Args:
            url: URL объявления
            get_full_similar: Получать ли полные данные для похожих (медленнее, но больше данных)
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
            
            logger.info(f"📄 Загрузка основной страницы: {url}")
            
            time.sleep(random.uniform(0.5, 1.0))
            page.goto(url, wait_until='domcontentloaded', timeout=60000)
            
            try:
                page.wait_for_selector('h1', timeout=10000)
            except:
                pass

            time.sleep(2)

            # === ОСНОВНЫЕ ДАННЫЕ ===
            
            # Заголовок
            try:
                h1 = page.locator('h1').first
                if h1:
                    result['title'] = h1.text_content().strip()
            except:
                pass

            # Цена
            try:
                price_elem = page.locator('[data-testid="price-amount"]').first
                if price_elem:
                    price_text = price_elem.text_content()
                    result['price'] = price_text.strip()
                    price_match = re.search(r'(\d+[\s\d]*)', price_text.replace(' ', ''))
                    if price_match:
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
                for img in img_elements[:30]:
                    src = img.get_attribute('src')
                    if src and src.startswith('http'):
                        images.append(src)
                result['images'] = list(dict.fromkeys(images))
            except:
                pass

            # === ПОИСК ПОХОЖИХ ЧЕРЕЗ BREADCRUMBS ===
            
            logger.info("🔍 Поиск breadcrumb для похожих объявлений...")
            breadcrumb_url = self._find_breadcrumb_link(page)
            
            page.close()
            
            if breadcrumb_url:
                # Получаем список похожих
                similar_basic = self._get_similar_from_search(breadcrumb_url, max_similar=10)

                if get_full_similar and similar_basic:
                    # Получаем полные данные для ВСЕХ похожих объявлений
                    result['similar_listings'] = self._get_full_data_for_similar(similar_basic, max_full=len(similar_basic))
                else:
                    result['similar_listings'] = similar_basic
            
            logger.info(f"✅ Готово: {len(result['characteristics'])} характеристик, {len(result['similar_listings'])} похожих")

        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            result['error'] = str(e)

        return result


# Alias для совместимости
CianParserWithSimilar = CianParserBreadcrumbs
