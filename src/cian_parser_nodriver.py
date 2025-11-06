#!/usr/bin/env python3
"""
Cian.ru парсер используя nodriver (successor of undetected-chromedriver)
Обходит Cloudflare и другие anti-bot системы
"""

import asyncio
import nodriver as uc
from typing import Dict, List, Optional
import json
import logging
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CianParserNodriver:
    """
    Парсер Cian.ru с использованием nodriver для обхода anti-bot защиты
    """

    def __init__(self):
        """Инициализация парсера"""
        self.browser = None
        self.page = None

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.browser:
            await self.browser.stop()

    async def _start_browser(self):
        """Запуск браузера nodriver"""
        if not self.browser:
            logger.info("🚀 Запуск nodriver браузера...")
            self.browser = await uc.start(
                headless=True,
                # Дополнительные опции для обхода детекции
                browser_args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                ]
            )
            logger.info("✅ Браузер запущен")

    async def extract_characteristics(self, page) -> Dict[str, str]:
        """
        Извлечение ВСЕХ характеристик используя правильные селекторы
        """
        characteristics = {}

        try:
            # Ждем загрузки характеристик
            await asyncio.sleep(2)

            # Ищем элементы с характеристиками
            items = await page.select_all('[data-testid="OfferSummaryInfoItem"]')
            
            logger.info(f"   Найдено {len(items)} элементов характеристик")

            for item in items:
                try:
                    # Получаем текст всего элемента
                    text = await item.get_html()
                    
                    # Ищем все параграфы
                    paragraphs = await item.select_all('p')
                    
                    if len(paragraphs) >= 2:
                        key = await paragraphs[0].text
                        value = await paragraphs[1].text
                        
                        if key and value:
                            characteristics[key.strip()] = value.strip()
                
                except Exception as e:
                    continue

            # Дополнительно извлекаем из meta tags (для этажа)
            try:
                og_title = await page.select('meta[property="og:title"]')
                if og_title:
                    content = await og_title.get_attribute('content')
                    if content:
                        # Извлекаем "этаж X/Y"
                        floor_match = re.search(r'этаж (\d+/\d+)', content, re.IGNORECASE)
                        if floor_match:
                            characteristics['Этаж'] = floor_match.group(1)
            except:
                pass

        except Exception as e:
            logger.error(f"   ⚠️ Ошибка извлечения характеристик: {e}")

        return characteristics

    async def parse_detail_page(self, url: str) -> Dict:
        """
        Парсинг детальной страницы объявления
        
        Args:
            url: URL объявления
            
        Returns:
            Dict с полной информацией об объявлении
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
            await self._start_browser()
            
            # Открываем новую вкладку
            page = await self.browser.get(url)
            self.page = page

            logger.info(f"📄 Загрузка страницы: {url}")
            
            # Ждем полной загрузки
            await asyncio.sleep(3)

            # Заголовок
            try:
                h1 = await page.select('h1')
                if h1:
                    result['title'] = await h1.text
            except:
                pass

            # Цена
            try:
                price_selectors = [
                    '[data-testid="price-amount"]',
                    '[data-name="PriceInfo"]',
                    '[itemprop="price"]'
                ]
                for selector in price_selectors:
                    price_elem = await page.select(selector)
                    if price_elem:
                        price_text = await price_elem.text
                        result['price'] = price_text.strip()
                        # Извлекаем число
                        price_match = re.search(r'(\d+[\s\d]*)', price_text.replace(' ', ''))
                        if price_match:
                            result['price_raw'] = int(price_match.group(1).replace(' ', ''))
                        break
            except:
                pass

            # Адрес
            try:
                address_elem = await page.select('[data-name="Geo"]')
                if address_elem:
                    result['address'] = await address_elem.text
            except:
                pass

            # Метро
            try:
                metro_items = await page.select_all('[data-name="UndergroundLabel"]')
                for item in metro_items:
                    metro_text = await item.text
                    if metro_text:
                        result['metro'].append(metro_text.strip())
            except:
                pass

            # Описание
            try:
                desc_elem = await page.select('[data-name="Description"]')
                if desc_elem:
                    result['description'] = await desc_elem.text
            except:
                pass

            # ХАРАКТЕРИСТИКИ - используем улучшенный метод
            logger.info("   📊 Извлечение характеристик...")
            result['characteristics'] = await self.extract_characteristics(page)

            # Изображения
            try:
                img_elements = await page.select_all('img[src*="cdn-cian.ru/images"]')
                images = []
                for img in img_elements:
                    src = await img.get_attribute('src')
                    if src and src.startswith('http') and 'cdn-cian' in src:
                        images.append(src)
                result['images'] = list(dict.fromkeys(images))  # Убираем дубли
            except:
                pass

            logger.info(f"✅ Успешно извлечено:")
            logger.info(f"   • Характеристик: {len(result['characteristics'])}")
            logger.info(f"   • Изображений: {len(result['images'])}")
            logger.info(f"   • Метро: {len(result['metro'])}")

        except Exception as e:
            logger.error(f"❌ Ошибка парсинга: {e}")
            result['error'] = str(e)

        return result


async def main():
    """Пример использования"""
    url = "https://spb.cian.ru/sale/flat/315047056/"
    
    print("=" * 80)
    print("🧪 ТЕСТ NODRIVER ПАРСЕРА")
    print("=" * 80)
    print(f"\n🔗 URL: {url}\n")

    async with CianParserNodriver() as parser:
        result = await parser.parse_detail_page(url)

    print("\n" + "=" * 80)
    print("📊 РЕЗУЛЬТАТЫ:")
    print("=" * 80)
    
    print(f"\n📋 Заголовок: {result.get('title', 'N/A')}")
    print(f"💰 Цена: {result.get('price', 'N/A')}")
    print(f"📍 Адрес: {result.get('address', 'N/A')[:80]}...")
    print(f"\n📊 Характеристик: {len(result.get('characteristics', {}))}")
    
    if result.get('characteristics'):
        print("\n🔑 Характеристики:")
        for key, value in list(result['characteristics'].items())[:10]:
            print(f"   • {key}: {value}")
    
    print(f"\n📷 Изображений: {len(result.get('images', []))}")
    print(f"🚇 Метро: {len(result.get('metro', []))}")

    # Сохраняем результат
    with open('/Users/fatbookpro/Desktop/cian/nodriver_test_result.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 Результат сохранен в: nodriver_test_result.json")


if __name__ == '__main__':
    # nodriver работает асинхронно
    asyncio.run(main())
