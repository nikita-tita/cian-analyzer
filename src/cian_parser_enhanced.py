"""
Улучшенный парсер Cian.ru - извлекает ВСЕ данные + похожие объявления
"""

import json
import time
import logging
import re
from typing import List, Dict, Optional
from playwright.sync_api import sync_playwright, Page, Browser
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CianParserEnhanced:
    """
    Улучшенный парсер с полным извлечением данных

    Извлекает:
    - Все характеристики (высота потолков, этаж, площадь и т.д.)
    - Похожие объявления в том же доме
    - Историю продаж
    - Сравнение с аналогами
    """

    def __init__(self, headless: bool = True, delay: float = 2.0):
        self.headless = headless
        self.delay = delay
        self.playwright = None
        self.browser = None
        self.context = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def start(self):
        """Запуск браузера"""
        logger.info("Запуск Playwright браузера...")
        self.playwright = sync_playwright().start()

        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ]
        )

        self.context = self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            locale='ru-RU',
            timezone_id='Europe/Moscow',
        )

        # Скрываем автоматизацию
        self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            window.chrome = { runtime: {} };
        """)

        logger.info("✓ Браузер запущен")

    def close(self):
        """Закрытие браузера"""
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        logger.info("Браузер закрыт")

    def _extract_all_characteristics(self, page: Page, soup: BeautifulSoup) -> Dict:
        """
        Извлекает ВСЕ характеристики объявления

        Returns:
            Dict с полными характеристиками
        """
        chars = {}

        try:
            # Метод 1: Из списков характеристик
            char_items = soup.find_all(['li', 'div'], class_=lambda x: x and 'offer' in str(x).lower())

            for item in char_items:
                text = item.get_text(strip=True)

                # Парсим пары "Ключ: Значение"
                if ':' in text and len(text) < 200:
                    parts = text.split(':', 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip()
                        if key and value:
                            chars[key] = value

            # Метод 2: Playwright селекторы
            try:
                # Все элементы с данными
                all_text_elements = page.query_selector_all('[class*="offer"], [data-name*="Offer"]')

                for elem in all_text_elements:
                    try:
                        text = elem.inner_text().strip()
                        if ':' in text and 10 < len(text) < 200:
                            parts = text.split(':', 1)
                            if len(parts) == 2:
                                chars[parts[0].strip()] = parts[1].strip()
                    except:
                        continue

            except Exception as e:
                logger.debug(f"Ошибка при извлечении через Playwright: {e}")

            # Метод 3: Специфичные характеристики
            specific_selectors = {
                'Высота потолков': ['ceiling', 'потолк', 'height'],
                'Площадь кухни': ['kitchen', 'кухн'],
                'Жилая площадь': ['living', 'жил'],
                'Этаж': ['floor', 'этаж'],
                'Год постройки': ['year', 'год'],
                'Тип дома': ['building', 'дом'],
                'Материал стен': ['material', 'материал'],
                'Отделка': ['finishing', 'отделк'],
                'Балкон': ['balcony', 'балкон'],
                'Санузел': ['bathroom', 'санузел'],
                'Вид из окон': ['view', 'вид'],
                'Парковка': ['parking', 'парк'],
                'Лифт': ['elevator', 'лифт'],
            }

            # Ищем по всему тексту страницы
            page_text = soup.get_text().lower()

            for char_name, keywords in specific_selectors.items():
                if char_name not in chars:
                    for keyword in keywords:
                        # Ищем паттерн: "ключевое_слово: значение"
                        pattern = rf'{keyword}[^\n]*?[:：]\s*([^\n]+)'
                        matches = re.findall(pattern, page_text, re.IGNORECASE)
                        if matches:
                            chars[char_name] = matches[0].strip()
                            break

        except Exception as e:
            logger.error(f"Ошибка при извлечении характеристик: {e}")

        return chars

    def _extract_similar_listings(self, page: Page, building_address: str) -> List[Dict]:
        """
        Извлекает похожие объявления из того же дома

        Args:
            page: Playwright страница
            building_address: Адрес дома

        Returns:
            Список похожих объявлений
        """
        similar = []

        try:
            logger.info("Поиск похожих объявлений в этом доме...")

            # Ищем кнопку "Другие квартиры в доме" или похожую
            buttons_to_try = [
                'text="квартир в доме"',
                'text="объявлений в доме"',
                'text="Похожие"',
                'text="В этом доме"',
                '[data-name*="similar"]',
                '[data-name*="building"]',
            ]

            for button_selector in buttons_to_try:
                try:
                    button = page.query_selector(button_selector)
                    if button:
                        logger.info(f"Найдена кнопка похожих объявлений: {button_selector}")
                        button.click()
                        time.sleep(2)
                        break
                except:
                    continue

            # Ждем загрузки списка
            time.sleep(1)

            # Извлекаем похожие объявления
            similar_cards = page.query_selector_all('[data-name*="offer"], [class*="offer-card"]')

            logger.info(f"Найдено {len(similar_cards)} похожих карточек")

            for card in similar_cards[:20]:  # Максимум 20
                try:
                    card_data = {}

                    # Заголовок
                    title_elem = card.query_selector('a, h3, [data-name*="title"]')
                    if title_elem:
                        card_data['title'] = title_elem.inner_text().strip()

                    # Цена
                    price_elem = card.query_selector('[data-mark*="price"], [class*="price"]')
                    if price_elem:
                        card_data['price'] = price_elem.inner_text().strip()

                    # Ссылка
                    link_elem = card.query_selector('a[href*="/sale/"], a[href*="/rent/"]')
                    if link_elem:
                        href = link_elem.get_attribute('href')
                        if href:
                            if not href.startswith('http'):
                                href = f"https://www.cian.ru{href}"
                            card_data['url'] = href

                    # Площадь, этаж
                    text = card.inner_text()

                    # Площадь
                    area_match = re.search(r'(\d+[.,]\d+|\d+)\s*м²', text)
                    if area_match:
                        card_data['area'] = area_match.group(0)

                    # Этаж
                    floor_match = re.search(r'(\d+)/(\d+)\s*этаж', text)
                    if floor_match:
                        card_data['floor'] = f"{floor_match.group(1)} из {floor_match.group(2)}"

                    if card_data.get('title') and card_data.get('url'):
                        similar.append(card_data)

                except Exception as e:
                    logger.debug(f"Ошибка при парсинге карточки: {e}")
                    continue

        except Exception as e:
            logger.warning(f"Не удалось извлечь похожие объявления: {e}")

        return similar

    def _extract_sold_history(self, page: Page) -> List[Dict]:
        """
        Извлекает историю проданных квартир в доме

        Returns:
            Список проданных объявлений
        """
        sold = []

        try:
            logger.info("Поиск истории продаж...")

            # Ищем вкладку "Проданные" или "История"
            tabs = [
                'text="Проданные"',
                'text="История"',
                'text="Продано"',
                '[data-name*="sold"]',
                '[data-name*="history"]',
            ]

            for tab_selector in tabs:
                try:
                    tab = page.query_selector(tab_selector)
                    if tab:
                        logger.info(f"Найдена вкладка истории: {tab_selector}")
                        tab.click()
                        time.sleep(2)
                        break
                except:
                    continue

            # Ждем загрузки
            time.sleep(1)

            # Извлекаем проданные объявления
            sold_cards = page.query_selector_all('[data-name*="offer"], [class*="offer-card"]')

            for card in sold_cards[:10]:  # Максимум 10
                try:
                    card_data = {}

                    text = card.inner_text()

                    # Заголовок
                    title_elem = card.query_selector('a, h3')
                    if title_elem:
                        card_data['title'] = title_elem.inner_text().strip()

                    # Цена
                    price_match = re.search(r'([\d\s]+)₽', text)
                    if price_match:
                        card_data['price'] = price_match.group(0)

                    # Дата продажи
                    date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', text)
                    if date_match:
                        card_data['date'] = date_match.group(0)

                    # Площадь
                    area_match = re.search(r'(\d+[.,]\d+|\d+)\s*м²', text)
                    if area_match:
                        card_data['area'] = area_match.group(0)

                    if card_data.get('title'):
                        card_data['status'] = 'Продано'
                        sold.append(card_data)

                except Exception as e:
                    logger.debug(f"Ошибка при парсинге проданного: {e}")
                    continue

        except Exception as e:
            logger.warning(f"Не удалось извлечь историю продаж: {e}")

        return sold

    def parse_detail_page_full(self, url: str) -> Dict:
        """
        Полный парсинг с ВСЕ данными + похожие объявления

        Args:
            url: URL объявления

        Returns:
            Dict с полными данными
        """
        logger.info(f"Полный парсинг: {url}")

        if not self.context:
            raise RuntimeError("Браузер не запущен")

        page = self.context.new_page()

        try:
            # Открываем страницу
            page.goto(url, wait_until='domcontentloaded', timeout=30000)
            page.wait_for_load_state('networkidle')
            time.sleep(2)  # Ждем динамический контент

            html = page.content()
            soup = BeautifulSoup(html, 'lxml')

            # Базовая структура
            data = {
                'url': url,
                'title': None,
                'price': None,
                'price_raw': None,
                'currency': None,
                'price_per_sqm': None,
                'description': None,
                'address': None,
                'metro': [],
                'characteristics': {},
                'images': [],
                'seller': {},
                'similar_listings': [],
                'sold_history': [],
            }

            # JSON-LD данные (быстро и надежно)
            json_ld = self._extract_json_ld(soup)
            if json_ld:
                logger.info("✓ JSON-LD данные найдены")
                data['title'] = json_ld.get('name')

                offers = json_ld.get('offers', {})
                if offers:
                    data['price_raw'] = offers.get('price')
                    data['currency'] = offers.get('priceCurrency')
                    if data['price_raw']:
                        price_formatted = f"{data['price_raw']:,}".replace(',', ' ')
                        data['price'] = f"{price_formatted} ₽"

            # Заголовок
            if not data['title']:
                title_elem = page.query_selector('h1')
                if title_elem:
                    data['title'] = title_elem.inner_text().strip()

            # Цена (если не было в JSON-LD)
            if not data['price']:
                price_selectors = [
                    '[data-testid*="price"]',
                    '[data-mark*="Price"]',
                    '[itemprop="price"]',
                ]
                for selector in price_selectors:
                    elem = page.query_selector(selector)
                    if elem:
                        data['price'] = elem.inner_text().strip()
                        break

            # Адрес
            address_elem = page.query_selector('[data-name*="Geo"], a[href*="/geo/"]')
            if address_elem:
                data['address'] = address_elem.inner_text().strip()

            # Метро
            metro_elems = page.query_selector_all('a[href*="metro"], [data-name*="Underground"]')
            if metro_elems:
                metros = []
                for elem in metro_elems:
                    metro_text = elem.inner_text().strip()
                    if metro_text and metro_text not in metros:
                        metros.append(metro_text)
                data['metro'] = metros[:5]  # Первые 5

            # Описание
            desc_selectors = [
                '[data-name="Description"]',
                '[itemprop="description"]',
                'div[class*="description"]',
            ]
            for selector in desc_selectors:
                elem = page.query_selector(selector)
                if elem:
                    desc = elem.inner_text().strip()
                    if len(desc) > 50:
                        data['description'] = desc
                        break

            # ВСЕ характеристики
            logger.info("Извлечение всех характеристик...")
            data['characteristics'] = self._extract_all_characteristics(page, soup)

            # Специфичные поля из характеристик
            for key, value in data['characteristics'].items():
                key_lower = key.lower()
                if 'этаж' in key_lower and not data.get('floor'):
                    data['floor'] = value
                elif ('площадь' in key_lower or 'м²' in value) and not data.get('area'):
                    data['area'] = value
                elif 'комнат' in key_lower and not data.get('rooms'):
                    data['rooms'] = value
                elif 'потолк' in key_lower:
                    data['ceiling_height'] = value

            # Цена за м²
            price_per_sqm_elem = page.query_selector('text=/₽\\/м²/')
            if price_per_sqm_elem:
                try:
                    data['price_per_sqm'] = price_per_sqm_elem.inner_text().strip()
                except:
                    pass

            # Изображения
            img_elems = page.query_selector_all('img[src*="cdn"], img[data-src*="cdn"]')
            images = []
            for img in img_elems:
                src = img.get_attribute('src') or img.get_attribute('data-src')
                if src and 'cdn' in src and src not in images and not src.endswith('.svg'):
                    images.append(src)
            data['images'] = images[:30]  # Максимум 30

            # Продавец
            seller_elem = page.query_selector('[data-name*="Author"], [class*="seller"]')
            if seller_elem:
                data['seller']['name'] = seller_elem.inner_text().strip()

            # ПОХОЖИЕ ОБЪЯВЛЕНИЯ В ДОМЕ
            if data.get('address'):
                logger.info("Поиск похожих объявлений в доме...")
                data['similar_listings'] = self._extract_similar_listings(page, data['address'])
                logger.info(f"✓ Найдено {len(data['similar_listings'])} похожих объявлений")

            # ИСТОРИЯ ПРОДАЖ
            logger.info("Поиск истории продаж...")
            data['sold_history'] = self._extract_sold_history(page)
            logger.info(f"✓ Найдено {len(data['sold_history'])} проданных объявлений")

            time.sleep(self.delay)

            return data

        except Exception as e:
            logger.error(f"Ошибка при парсинге: {e}")
            import traceback
            traceback.print_exc()
            return {'url': url, 'error': str(e)}

        finally:
            page.close()

    def _extract_json_ld(self, soup: BeautifulSoup) -> Optional[Dict]:
        """Извлечь JSON-LD данные"""
        try:
            json_ld_script = soup.find('script', type='application/ld+json')
            if json_ld_script and json_ld_script.string:
                return json.loads(json_ld_script.string)
        except Exception as e:
            logger.debug(f"JSON-LD не найден: {e}")
        return None

    def save_to_json(self, data: Dict, filename: str):
        """Сохранить данные в JSON"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"✓ Данные сохранены в {filename}")
        except Exception as e:
            logger.error(f"Ошибка при сохранении: {e}")


if __name__ == "__main__":
    # Тест
    url = "https://www.cian.ru/sale/flat/315831388/"

    with CianParserEnhanced(headless=True, delay=2.0) as parser:
        data = parser.parse_detail_page_full(url)
        parser.save_to_json(data, 'enhanced_result.json')

        print(f"\n✓ Заголовок: {data.get('title')}")
        print(f"✓ Характеристик: {len(data.get('characteristics', {}))}")
        print(f"✓ Похожих объявлений: {len(data.get('similar_listings', []))}")
        print(f"✓ Проданных: {len(data.get('sold_history', []))}")
