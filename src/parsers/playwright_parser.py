"""
Эффективный Playwright парсер с переиспользованием браузера
"""

import time
import logging
from typing import Optional, List, Dict
from functools import wraps
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext
from bs4 import BeautifulSoup

from .base_parser import BaseCianParser

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# ИМПОРТ ВАЛИДАТОРА
# ═══════════════════════════════════════════════════════════════════════════

try:
    from ..analytics.data_validator import validate_comparable
    from ..models.property import ComparableProperty
    from pydantic import ValidationError
    VALIDATION_AVAILABLE = True
except ImportError:
    VALIDATION_AVAILABLE = False
    logger.warning("⚠️ Валидатор данных недоступен - фильтрация отключена")


def detect_region_from_url(url: str) -> str:
    """
    Автоопределение региона по URL объекта

    Args:
        url: URL объявления

    Returns:
        'msk' или 'spb'
    """
    # Парсим URL для поиска региона
    url_lower = url.lower()

    # Ищем упоминание городов в URL
    # Москва: moskva, moscow, msk
    if any(word in url_lower for word in ['moskva', 'moscow', '/msk/', 'moscow-city']):
        return 'msk'
    # Санкт-Петербург: sankt-peterburg, spb, piter
    elif any(word in url_lower for word in ['sankt-peterburg', 'saint-petersburg', '/spb/', 'piter']):
        return 'spb'

    # КРИТИЧНО: По умолчанию возвращаем None вместо 'spb'
    # Регион должен определяться по адресу после парсинга
    logger.warning(f"⚠️ Не удалось определить регион по URL: {url}, требуется определение по адресу")
    return None


def detect_region_from_address(address: str) -> str:
    """
    Определение региона по адресу объекта

    Args:
        address: Адрес объявления

    Returns:
        'msk' или 'spb' или None
    """
    if not address:
        return None

    address_lower = address.lower()

    # Москва: ищем "Москва", "г. Москва", "Moscow"
    if any(word in address_lower for word in ['москва', 'moscow', 'г москва', 'г.москва']):
        return 'msk'
    # Санкт-Петербург: ищем "Санкт-Петербург", "СПб", "Питер"
    elif any(word in address_lower for word in ['санкт-петербург', 'спб', 'с-петербург', 'с.петербург', 'питер']):
        return 'spb'

    return None


def retry_with_exponential_backoff(max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 10.0):
    """
    Декоратор для повторных попыток с экспоненциальной задержкой

    Args:
        max_retries: Максимальное количество попыток
        base_delay: Базовая задержка между попытками (секунды)
        max_delay: Максимальная задержка между попытками (секунды)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    if attempt < max_retries - 1:
                        # Экспоненциальная задержка: 1s, 2s, 4s, ...
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        logger.warning(
                            f"Попытка {attempt + 1}/{max_retries} провалилась: {e}. "
                            f"Повтор через {delay:.1f}s..."
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"Все {max_retries} попытки провалились. "
                            f"Последняя ошибка: {e}"
                        )

            # Если все попытки провалились, пробрасываем последнее исключение
            raise last_exception

        return wrapper
    return decorator


class PlaywrightParser(BaseCianParser):
    """
    Playwright парсер с переиспользованием браузера

    ОПТИМИЗАЦИЯ:
    - Браузер запускается один раз на всю сессию
    - Context переиспользуется
    - Блокируются ненужные ресурсы (картинки, шрифты)
    - Redis кэширование парсинга
    """

    def __init__(
        self,
        headless: bool = True,
        delay: float = 2.0,
        block_resources: bool = True,
        cache=None,
        region: str = 'spb',
        browser_pool=None
    ):
        """
        Args:
            headless: Запускать браузер в фоновом режиме
            delay: Задержка между запросами
            block_resources: Блокировать картинки/шрифты для ускорения
            cache: PropertyCache instance (опционально)
            region: Регион поиска ('spb' или 'msk')
            browser_pool: BrowserPool instance (опционально, рекомендуется для production)
        """
        super().__init__(delay, cache=cache)
        self.headless = headless
        self.block_resources = block_resources
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.browser_pool = browser_pool
        self.using_pool = browser_pool is not None

        # Маппинг регионов на коды Cian
        self.region_codes = {
            'spb': '2',  # Санкт-Петербург
            'msk': '1',  # Москва
        }
        self.region = region
        self.region_code = self.region_codes.get(region, '2')  # Default: SPB

        logger.info(f"Регион: {region} (код: {self.region_code}), using_pool: {self.using_pool}")

    def __enter__(self):
        """Context manager вход"""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager выход"""
        self.close()

    def start(self):
        """Запуск браузера (один раз за сессию) или получение из пула"""
        if self.browser:
            logger.warning("Браузер уже запущен")
            return

        try:
            # Если используем browser pool, получаем браузер из пула
            if self.using_pool:
                logger.info("Acquiring browser from pool...")
                self.browser, self.context = self.browser_pool.acquire(timeout=30.0)
                logger.info("✓ Браузер получен из пула")
                return

            # Иначе создаем собственный браузер (legacy режим)
            logger.info("🚀 Запуск Playwright браузера...")
            self.playwright = sync_playwright().start()

            self.browser = self.playwright.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-gpu',
                    '--disable-software-rasterizer',
                ]
            )

            self.context = self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
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

            # Блокируем ненужные ресурсы для ускорения
            if self.block_resources:
                self.context.route(
                    "**/*.{png,jpg,jpeg,gif,svg,webp,woff,woff2,ttf,mp4,mp3,pdf}",
                    lambda route: route.abort()
                )

            logger.info("✓ Браузер запущен и готов к работе")

        except Exception as e:
            logger.error(f"Ошибка при запуске браузера: {e}")
            # Гарантируем очистку ресурсов при ошибке
            self.close()
            raise

    def close(self):
        """Закрытие браузера или возврат в пул"""
        # Если используем browser pool, возвращаем браузер в пул
        if self.using_pool and self.browser:
            try:
                logger.info("Returning browser to pool...")
                self.browser_pool.release(self.browser)
                self.browser = None
                self.context = None
                logger.info("✓ Browser returned to pool")
                return
            except Exception as e:
                logger.error(f"Error returning browser to pool: {e}")
                # Продолжаем с обычным закрытием

        # Legacy режим: закрываем браузер полностью
        errors = []

        # Закрываем context
        if self.context:
            try:
                self.context.close()
            except Exception as e:
                errors.append(f"Context: {e}")
            finally:
                self.context = None

        # Закрываем browser
        if self.browser:
            try:
                self.browser.close()
            except Exception as e:
                errors.append(f"Browser: {e}")
            finally:
                self.browser = None

        # Останавливаем playwright
        if self.playwright:
            try:
                self.playwright.stop()
            except Exception as e:
                errors.append(f"Playwright: {e}")
            finally:
                self.playwright = None

        if errors:
            logger.warning(f"Ошибки при закрытии браузера: {', '.join(errors)}")
        else:
            logger.info("Браузер закрыт")

    def _get_page_content(self, url: str, max_retries: int = 3) -> Optional[str]:
        """
        Получить HTML контент через Playwright с retry логикой

        Args:
            url: URL для загрузки
            max_retries: Максимальное количество попыток

        Returns:
            HTML контент или None

        Raises:
            Exception: После max_retries неудачных попыток загрузки
        """
        if not self.context:
            raise RuntimeError("Браузер не запущен. Используйте with context или вызовите .start()")

        last_error = None

        for attempt in range(1, max_retries + 1):
            page: Page = None
            try:
                # PATCH: Rate limiting - случайная задержка между запросами
                if attempt > 1:
                    import random
                    delay = random.uniform(2, 5)  # 2-5 секунд между попытками
                    logger.info(f"   ⏳ Задержка {delay:.1f}с перед попыткой #{attempt}")
                    time.sleep(delay)

                page = self.context.new_page()

                # PATCH: Добавляем случайный User-Agent (защита от блокировок)
                import random
                user_agents = [
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                ]
                page.set_extra_http_headers({
                    'User-Agent': random.choice(user_agents)
                })

                logger.info(f"Загрузка страницы (попытка {attempt}/{max_retries}): {url}")

                # Загружаем страницу
                page.goto(url, wait_until='domcontentloaded', timeout=30000)

                # Ждем появления контента
                try:
                    page.wait_for_selector(
                        'h1, [data-mark="OfferTitle"], script[type="application/ld+json"]',
                        timeout=10000
                    )
                except Exception as e:
                    logger.warning(f"Селекторы не найдены, но продолжаем: {e}")

                # Дополнительное ожидание для динамического контента
                time.sleep(1)

                html = page.content()

                if not html or len(html) < 1000:
                    raise ValueError(f"Получен пустой или слишком короткий HTML ({len(html) if html else 0} символов)")

                logger.info(f"✓ Страница загружена ({len(html)} символов)")
                return html

            except Exception as e:
                last_error = e
                logger.warning(f"⚠️ Попытка {attempt}/{max_retries} не удалась: {e}")

                # Если это капча или блокировка - увеличиваем задержку
                if 'captcha' in str(e).lower() or '403' in str(e) or '429' in str(e):
                    logger.warning(f"   🚫 Обнаружена блокировка/капча, увеличиваем задержку")
                    if attempt < max_retries:
                        time.sleep(10)  # Ждем 10 секунд перед повтором

                if attempt == max_retries:
                    logger.error(f"❌ Все {max_retries} попытки исчерпаны для {url}")
                    raise last_error

            finally:
                if page:
                    page.close()

        # На случай если что-то пошло не так
        if last_error:
            raise last_error
        return None

    def parse_search_page(self, url: str) -> List[Dict]:
        """
        Парсинг страницы с результатами поиска с адаптивными селекторами

        Args:
            url: URL страницы поиска

        Returns:
            Список словарей с данными объявлений
        """
        logger.info(f"Парсинг страницы поиска: {url}")

        html = self._get_page_content(url)
        if not html:
            logger.warning("⚠️ DEBUG: _get_page_content вернул пустой HTML")
            return []

        soup = BeautifulSoup(html, 'lxml')

        # Используем адаптивные селекторы для поиска карточек
        from .adaptive_selectors import AdaptiveSelector, CARD_SELECTORS

        selector = AdaptiveSelector(soup)
        cards = selector.find_elements(CARD_SELECTORS, "карточки объявлений")

        logger.info(f"Найдено {len(cards)} карточек объявлений на странице")

        if len(cards) == 0:
            logger.warning("⚠️ DEBUG: На странице не найдено ни одной карточки объявления")
            logger.warning(f"⚠️ DEBUG: Размер HTML: {len(html)} байт")
            # Сохраним первые 2000 символов HTML для диагностики
            logger.debug(f"⚠️ DEBUG: Начало HTML: {html[:2000]}")

        listings = []
        for i, card in enumerate(cards):
            try:
                listing_data = self._parse_listing_card(card)
                if listing_data.get('title'):
                    listings.append(listing_data)
                    if i < 3:  # Логируем первые 3 для отладки
                        logger.debug(f"✓ Карточка {i+1} спарсена: {listing_data.get('title', '')[:80]}")
                else:
                    logger.debug(f"✗ Карточка {i+1}: отсутствует title, пропущена")
            except Exception as e:
                logger.warning(f"Ошибка при парсинге карточки {i+1}: {e}")
                continue

        logger.info(f"✓ Успешно спарсено {len(listings)} объявлений из {len(cards)} карточек")

        # Логируем статистику успешных селекторов
        stats = selector.get_stats()
        if stats:
            logger.debug(f"📊 Статистика селекторов: {stats}")

        return listings

    def _parse_listing_card(self, card: BeautifulSoup) -> Dict:
        """
        Парсинг карточки объявления из списка с адаптивными селекторами

        Args:
            card: BeautifulSoup объект карточки

        Returns:
            Словарь с данными объявления
        """
        from .adaptive_selectors import (
            AdaptiveSelector, TITLE_SELECTORS, PRICE_SELECTORS,
            ADDRESS_SELECTORS, AREA_SELECTORS, METRO_SELECTORS,
            extract_rooms_from_text, extract_floor_from_text
        )

        data = {
            'title': None,
            'price': None,
            'price_per_sqm': None,  # Цена за кв.м
            'price_raw': None,  # Цена в числовом виде
            'address': None,
            'metro': None,
            'area': None,
            'area_value': None,  # Площадь в числовом виде
            'rooms': None,
            'floor': None,
            'renovation': None,  # Тип ремонта
            'url': None,
            'image_url': None,
        }

        # Создаем адаптивный селектор для карточки
        selector = AdaptiveSelector(BeautifulSoup(str(card), 'lxml'))

        # Заголовок - используем адаптивные селекторы
        data['title'] = selector.extract_text(TITLE_SELECTORS, "заголовок")

        # Извлекаем количество комнат из заголовка
        if data['title']:
            data['rooms'] = extract_rooms_from_text(data['title'])

        # Цена - используем адаптивные селекторы
        price_elem = selector.find_element(PRICE_SELECTORS, "цена")
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            data['price'] = price_text

            # Извлекаем числовое значение цены
            import re
            price_numbers = re.sub(r'[^\d]', '', price_text)
            if price_numbers:
                data['price_raw'] = int(price_numbers)

        # Адрес - используем адаптивные селекторы
        # Сначала пробуем найти множественные GeoLabel
        geo_labels = card.find_all('a', {'data-name': 'GeoLabel'})
        if geo_labels:
            # Собираем все части адреса
            address_parts = [label.get_text(strip=True) for label in geo_labels]
            # Соединяем через запятую, пропуская дубликаты
            unique_parts = []
            for part in address_parts:
                if part not in unique_parts:
                    unique_parts.append(part)
            data['address'] = ', '.join(unique_parts)

        # Если GeoLabel не найдены, используем адаптивные селекторы
        if not data['address']:
            data['address'] = selector.extract_text(ADDRESS_SELECTORS, "адрес")

        # Если адрес все еще не найден, пробуем найти любой текст с городом
        if not data['address']:
            # Ищем div/span с текстом, содержащим "Санкт-Петербург" или "Москва"
            for elem in card.find_all(['div', 'span', 'a']):
                text = elem.get_text(strip=True)
                if 'Санкт-Петербург' in text or 'Москва' in text:
                    if len(text) < 200:  # Не берем слишком длинные тексты
                        data['address'] = text
                        break

        # Метро - используем адаптивные селекторы
        metro_elem = selector.find_element(METRO_SELECTORS, "метро")
        if metro_elem:
            data['metro'] = metro_elem.get_text(strip=True)

        # Подзаголовок с характеристиками (ПРИОРИТЕТ - здесь содержится площадь!)
        # Формат: "2-комн. квартира, 85 м², 4/9 этаж"
        subtitle_elem = card.find('span', {'data-mark': 'OfferSubtitle'})
        if subtitle_elem:
            subtitle_text = subtitle_elem.get_text(strip=True)
            import re

            # Извлекаем площадь (85 м²)
            area_match = re.search(r'([\d,\.]+)\s*м²', subtitle_text)
            if area_match:
                data['area'] = area_match.group(0)  # "85 м²"
                area_str = area_match.group(1).replace(',', '.')
                try:
                    data['area_value'] = float(area_str)
                except ValueError:
                    pass

            # Извлекаем этаж используя новую функцию
            if not data.get('floor'):
                data['floor'] = extract_floor_from_text(subtitle_text)

            # Извлекаем количество комнат (2-комн.)
            if not data['rooms']:  # Если еще не извлекли из заголовка
                data['rooms'] = extract_rooms_from_text(subtitle_text)

        # Если площадь не найдена в подзаголовке, используем адаптивные селекторы
        if not data['area_value']:
            area_elem = selector.find_element(AREA_SELECTORS, "площадь")
            if area_elem:
                area_text = area_elem.get_text(strip=True)
                area_match = re.search(r'([\d,\.]+)\s*м²', area_text)
                if area_match:
                    data['area'] = area_match.group(0)
                    area_str = area_match.group(1).replace(',', '.')
                    try:
                        data['area_value'] = float(area_str)
                    except ValueError:
                        pass

        # Характеристики (FALLBACK - если не нашли в подзаголовке)
        characteristics = card.find_all('span', {'data-mark': 'OfferCharacteristics'})
        for char in characteristics:
            text = char.get_text(strip=True)
            if 'м²' in text and not data['area_value']:
                data['area'] = text
                # Извлекаем числовое значение площади
                area_match = re.search(r'([\d,\.]+)\s*м²', text)
                if area_match:
                    area_str = area_match.group(1).replace(',', '.')
                    try:
                        data['area_value'] = float(area_str)
                    except ValueError:
                        pass
            elif 'этаж' in text.lower() and not data['floor']:
                floor_extracted = extract_floor_from_text(text)
                if floor_extracted:
                    data['floor'] = floor_extracted
            elif 'ремонт' in text.lower() or 'отделк' in text.lower():
                data['renovation'] = text

        # Вычисляем цену за кв.м если есть цена и площадь
        if data['price_raw'] and data['area_value']:
            data['price_per_sqm'] = round(data['price_raw'] / data['area_value'])

        # Ссылка - пробуем несколько вариантов
        link_elem = (
            card.find('a', {'data-mark': 'OfferTitle'}) or
            card.find('a', {'data-name': 'LinkArea'}) or
            card.find('a', href=lambda x: x and '/sale/flat/' in str(x))
        )
        if link_elem and link_elem.get('href'):
            href = link_elem['href']
            data['url'] = self.base_url + href if not href.startswith('http') else href

        # Изображение
        img_elem = card.find('img', {'data-mark': 'OfferPreviewImage'})
        if img_elem:
            data['image_url'] = img_elem.get('src') or img_elem.get('data-src')

        return data

    def _validate_and_prepare_results(
        self,
        results: List[Dict],
        limit: int,
        enable_validation: bool = True,
        target_property: Dict = None
    ) -> List[Dict]:
        """
        Валидация и подготовка результатов перед возвратом

        Args:
            results: Список спарсенных объявлений
            limit: Максимальное количество результатов
            enable_validation: Включить валидацию данных
            target_property: Целевой объект для проверки разумности аналогов (опционально)

        Returns:
            Список валидных и подготовленных результатов
        """
        if not results:
            logger.info("⚠️ DEBUG: _validate_and_prepare_results получил пустой список результатов")
            return []

        logger.info(f"🔍 DEBUG: Начинаем валидацию {len(results)} результатов (enable_validation={enable_validation})")

        # Маппинг полей для Pydantic моделей
        for result in results:
            if 'area_value' in result and result['area_value']:
                result['total_area'] = result['area_value']
            if 'price_raw' in result and result['price_raw']:
                result['price'] = result['price_raw']
            # Конвертируем rooms в int если это строка с цифрой
            if 'rooms' in result and isinstance(result['rooms'], str) and result['rooms'].isdigit():
                result['rooms'] = int(result['rooms'])

        # ═══════════════════════════════════════════════════════════════════════════
        # ДОРАБОТКА #1: ФИЛЬТРАЦИЯ ПО РЕГИОНУ (КРИТИЧНО: по адресу, не только по URL!)
        # ═══════════════════════════════════════════════════════════════════════════
        region_filtered = []
        region_excluded = 0
        for result in results:
            result_url = result.get('url', '')
            result_address = result.get('address', '')

            # ПРИОРИТЕТ 1: Определяем регион по адресу
            result_region = detect_region_from_address(result_address)

            # ПРИОРИТЕТ 2: Если не удалось по адресу - пробуем по URL
            if not result_region:
                result_region = detect_region_from_url(result_url)

            # Если удалось определить регион - проверяем совпадение
            if result_region:
                if result_region == self.region:
                    region_filtered.append(result)
                else:
                    region_excluded += 1
                    logger.warning(
                        f"⚠️ Исключен аналог из другого региона: "
                        f"{result_region} (ожидался {self.region}), "
                        f"адрес: {result_address[:80] if result_address else 'не указан'}"
                    )
            else:
                # Не удалось определить регион - оставляем (возможно тот же регион)
                region_filtered.append(result)

        if region_excluded > 0:
            logger.info(f"📊 Фильтрация по региону: {len(results)} → {len(region_filtered)} (исключено {region_excluded} из других регионов)")

        results = region_filtered

        # ═══════════════════════════════════════════════════════════════════════════
        # ДОРАБОТКА #3: ВАЛИДАЦИЯ РАЗУМНОСТИ АНАЛОГОВ
        # ═══════════════════════════════════════════════════════════════════════════
        if target_property:
            target_price = target_property.get('price', 0)
            target_area = target_property.get('total_area', 0)

            if target_price > 0 and target_area > 0:
                reasonable = []
                unreasonable_count = 0

                for result in results:
                    comp_price = result.get('price') or result.get('price_raw') or 0
                    comp_area = result.get('total_area') or result.get('area_value') or 0

                    # Пропускаем если нет данных
                    if not comp_price or not comp_area:
                        reasonable.append(result)
                        continue

                    # Проверка 1: Цена не должна отличаться больше чем в 3 раза
                    price_ratio = max(comp_price, target_price) / min(comp_price, target_price)
                    if price_ratio > 3.0:
                        unreasonable_count += 1
                        logger.warning(
                            f"⚠️ Исключен неразумный аналог: цена отличается в {price_ratio:.1f} раз "
                            f"(аналог {comp_price:,} ₽ vs целевой {target_price:,} ₽), "
                            f"URL: {result.get('url', '')[:60]}..."
                        )
                        continue

                    # Проверка 2: Площадь не должна отличаться больше чем в 1.5 раза
                    area_ratio = max(comp_area, target_area) / min(comp_area, target_area)
                    if area_ratio > 1.5:
                        unreasonable_count += 1
                        logger.warning(
                            f"⚠️ Исключен неразумный аналог: площадь отличается в {area_ratio:.1f} раз "
                            f"(аналог {comp_area} м² vs целевой {target_area} м²), "
                            f"URL: {result.get('url', '')[:60]}..."
                        )
                        continue

                    # Проверка 3: НОВОЕ - Цена за м² не должна отличаться больше чем на ±30%
                    # КРИТИЧНО для устранения разброса 76%
                    target_price_per_sqm = target_price / target_area
                    comp_price_per_sqm = comp_price / comp_area
                    price_per_sqm_diff = abs(comp_price_per_sqm - target_price_per_sqm) / target_price_per_sqm

                    if price_per_sqm_diff > 0.30:  # ±30%
                        unreasonable_count += 1
                        logger.warning(
                            f"⚠️ Исключен по цене/м²: отличие {price_per_sqm_diff*100:.0f}% "
                            f"(аналог {comp_price_per_sqm:,.0f} ₽/м² vs целевой {target_price_per_sqm:,.0f} ₽/м²), "
                            f"адрес: {result.get('address', '')[:50]}"
                        )
                        continue

                    reasonable.append(result)

                if unreasonable_count > 0:
                    logger.info(
                        f"📊 Проверка разумности: {len(results)} → {len(reasonable)} "
                        f"(исключено {unreasonable_count} несопоставимых)"
                    )

                results = reasonable

        # Валидация (если доступна)
        if enable_validation and VALIDATION_AVAILABLE:
            validated = []
            excluded_count = 0

            for i, result in enumerate(results):
                try:
                    # Создаем ComparableProperty для валидации
                    comp = ComparableProperty(**result)

                    # Проверяем валидность
                    is_valid, details = validate_comparable(comp)

                    if is_valid:
                        validated.append(result)
                        logger.debug(
                            f"✓ Результат {i+1}: валиден "
                            f"(полнота: {details.get('completeness', 0):.0f}%)"
                        )
                    else:
                        excluded_count += 1
                        failures_str = '; '.join(details.get('failures', []))
                        logger.info(f"✗ Результат {i+1}: ИСКЛЮЧЕН - {failures_str}")
                        logger.info(f"   URL: {result.get('url', 'N/A')}")
                        logger.info(f"   Цена: {result.get('price', 'N/A')}, Площадь: {result.get('total_area', 'N/A')}, Цена/м²: {result.get('price_per_sqm', 'N/A')}")

                except ValidationError as e:
                    excluded_count += 1
                    logger.info(f"✗ Результат {i+1}: невалидная структура данных - {e}")
                    logger.info(f"   URL: {result.get('url', 'N/A')}")

            if excluded_count > 0:
                logger.info(
                    f"📊 Валидация: {len(results)} → {len(validated)} "
                    f"(исключено {excluded_count} некачественных)"
                )
            else:
                logger.info(f"✓ Все {len(validated)} результатов прошли валидацию")

            results = validated
        else:
            logger.info(f"⚠️ DEBUG: Валидация отключена или недоступна (VALIDATION_AVAILABLE={VALIDATION_AVAILABLE})")

        # Ограничиваем количество
        logger.info(f"✓ Возвращаем {min(len(results), limit)} результатов (limit={limit})")
        return results[:limit]

    def search_similar_in_building(self, target_property: Dict, limit: int = 20) -> List[Dict]:
        """
        Поиск похожих квартир в том же ЖК (жилом комплексе)

        Args:
            target_property: Целевой объект с полями residential_complex, residential_complex_url, address
            limit: максимальное количество результатов

        Returns:
            Список похожих объявлений из того же ЖК
        """
        logger.info("🔍 Начинаем поиск похожих квартир в том же ЖК...")

        residential_complex = target_property.get('residential_complex')
        residential_complex_url = target_property.get('residential_complex_url')
        address = target_property.get('address', '')

        # DEBUG: Показываем, какие данные мы получили
        logger.info("📋 DEBUG: Данные целевой квартиры:")
        logger.info(f"   - residential_complex: {residential_complex}")
        logger.info(f"   - residential_complex_url: {residential_complex_url}")
        logger.info(f"   - address: {address}")
        logger.info(f"   - price: {target_property.get('price', 'N/A')}")
        logger.info(f"   - total_area: {target_property.get('total_area', 'N/A')}")
        logger.info(f"   - rooms: {target_property.get('rooms', 'N/A')}")

        # ПРИОРИТЕТ 1: Используем прямую ссылку на страницу ЖК (самый точный метод!)
        if residential_complex_url:
            logger.info(f"✨ Используем прямую ссылку на ЖК: {residential_complex_url}")

            # Если это ссылка на поддомен (zhk-название.cian.ru), ищем кнопку "Все квартиры"
            # Если это ссылка /kupit-kvartiru-zhiloy-kompleks-*, она уже готова для парсинга
            if 'zhk-' in residential_complex_url and '.cian.ru' in residential_complex_url:
                # Загружаем страницу ЖК и ищем ссылку на каталог
                html = self._get_page_content(residential_complex_url)
                if html:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(html, 'lxml')

                    # Ищем ссылку на каталог квартир ЖК
                    catalog_links = soup.find_all('a', href=True)
                    logger.info(f"🔍 DEBUG: Найдено {len(catalog_links)} ссылок на странице ЖК")
                    for link in catalog_links:
                        href = link.get('href')

                        if ('/kupit-kvartiru-zhiloy-kompleks-' in href or
                                ('/cat.php' in href and 'newobject' in href)):
                            residential_complex_url = href if href.startswith('http') else f"https://www.cian.ru{href}"
                            logger.info(f"   ✓ Найдена ссылка на каталог: {residential_complex_url[:100]}")
                            break
                else:
                    logger.warning(f"⚠️ DEBUG: Не удалось загрузить HTML страницы ЖК: {residential_complex_url}")

            # Парсим страницу с объявлениями ЖК
            logger.info(f"🔍 DEBUG: Парсим страницу ЖК: {residential_complex_url}")
            results = self.parse_search_page(residential_complex_url)

            if results:
                logger.info(f"✓ Найдено {len(results)} объявлений через прямую ссылку на ЖК")
                # Валидация и подготовка
                return self._validate_and_prepare_results(results, limit, target_property=target_property)
            else:
                logger.warning("⚠️ По прямой ссылке ничего не найдено, пробуем текстовый поиск")

        # ПРИОРИТЕТ 2: Текстовый поиск по названию ЖК (fallback)
        if not residential_complex:
            logger.warning("⚠️ Не указан ЖК, используется поиск по адресу")
            # Пробуем извлечь из адреса
            import re
            match = re.search(r'ЖК\s+([А-Яа-яёЁ\s\-\d]+?)(?:,|$)', address)
            if match:
                residential_complex = match.group(1).strip()
            else:
                # Если нет ЖК - используем старый метод
                logger.warning("⚠️ ЖК не найден, используется широкий поиск")
                return self.search_similar(target_property, limit)

        logger.info(f"📍 Текстовый поиск по ЖК: {residential_complex}")

        # Формируем поисковый запрос
        import urllib.parse

        # Вариант 1: Точное название ЖК
        search_query = f"ЖК {residential_complex}"
        encoded_query = urllib.parse.quote(search_query)

        # ИСПРАВЛЕНИЕ: Добавляем фильтры по площади и комнатам для более точного подбора
        target_area = target_property.get('total_area', 0)
        target_rooms = target_property.get('rooms', 0)

        # Строим URL поиска с текстовым запросом и фильтрами
        search_params = {
            'deal_type': 'sale',
            'offer_type': 'flat',
            'engine_version': '2',
            'region': self.region_code,
            'text': encoded_query,
        }

        # Добавляем фильтр по площади (±30% для поиска в том же ЖК)
        if target_area > 0:
            area_tolerance = 0.30  # Более мягкий допуск для поиска в ЖК
            search_params['minArea'] = int(target_area * (1 - area_tolerance))
            search_params['maxArea'] = int(target_area * (1 + area_tolerance))
            logger.info(f"   Фильтр площади: {search_params['minArea']}-{search_params['maxArea']} м²")

        # Добавляем фильтр по комнатам (±1 комната)
        if target_rooms:
            # Обработка различных типов target_rooms
            if isinstance(target_rooms, str):
                if 'студия' in target_rooms.lower():
                    target_rooms_int = 1
                else:
                    import re
                    match = re.search(r'\d+', target_rooms)
                    target_rooms_int = int(match.group()) if match else 0
            else:
                target_rooms_int = int(target_rooms) if target_rooms else 0

            if target_rooms_int > 0:
                # СТРОГИЙ фильтр комнат (без смешивания!)
                search_params[f'room{target_rooms_int}'] = '1'
                logger.info(f"   🏠 Фильтр комнат: СТРОГО {target_rooms_int}-комнатные")

        url = f"{self.base_url}/cat.php?" + '&'.join([f"{k}={v}" for k, v in search_params.items()])

        logger.info(f"🔗 URL поиска: {url}")

        # Парсим результаты
        results = self.parse_search_page(url)

        logger.info(f"🔍 DEBUG: parse_search_page вернул {len(results)} результатов для текстового поиска")

        # Фильтруем результаты - оставляем только те, что точно из этого ЖК
        filtered_results = []
        rc_lower = residential_complex.lower()

        # Разбиваем название ЖК на слова для более гибкого поиска
        rc_words = set(rc_lower.split())

        logger.info(f"   Найдено {len(results)} карточек, фильтруем по ЖК '{residential_complex}'")
        logger.info(f"   Ключевые слова ЖК: {rc_words}")

        for i, result in enumerate(results):
            result_title = result.get('title', '').lower()
            result_address = result.get('address', '').lower()

            if i < 5:  # Логируем первые 5 для отладки
                logger.info(f"   Карточка {i+1}:")
                logger.info(f"     Title: {result_title[:100]}")
                logger.info(f"     Address: {result_address[:150]}")

            # Полное совпадение (приоритет)
            if rc_lower in result_title or rc_lower in result_address:
                filtered_results.append(result)
                logger.info(f"     ✓ Добавлена (полное совпадение)")
                continue

            # Частичное совпадение - проверяем основные слова
            # (минимум 2 слова из названия ЖК должны присутствовать)
            if len(rc_words) >= 2:
                title_words = set(result_title.split())
                address_words = set(result_address.split())

                matching_in_title = len(rc_words & title_words)
                matching_in_address = len(rc_words & address_words)

                if matching_in_title >= 2 or matching_in_address >= 2:
                    filtered_results.append(result)
                    logger.info(f"     ✓ Добавлена (частичное совпадение: {matching_in_title} в title, {matching_in_address} в address)")
                elif i < 5:
                    logger.info(f"     ✗ Пропущена (мало совпадений: {matching_in_title} в title, {matching_in_address} в address)")

        logger.info(f"✓ Найдено {len(filtered_results)} похожих объявлений после фильтрации по ЖК '{residential_complex}'")

        # Валидация и подготовка
        return self._validate_and_prepare_results(filtered_results, limit, target_property=target_property)

    def _is_new_building(self, target_property: Dict = None) -> bool:
        """
        Определяет, является ли объект новостройкой

        Args:
            target_property: Данные целевого объекта

        Returns:
            bool: True если новостройка, False если вторичка
        """
        if not target_property:
            return False

        # Метод 1: Проверка URL
        url = target_property.get('url', '')
        if '/newobject/' in url or 'newobject' in url:
            logger.info(f"   🔍 Определен как новостройка (по URL)")
            return True

        # Метод 2: Проверка года сдачи (если в будущем или близко к настоящему)
        from datetime import datetime
        current_year = datetime.now().year

        # Проверяем поле build_year
        build_year = target_property.get('build_year')
        if build_year:
            try:
                year = int(build_year)
                if year >= current_year:  # Сдача в будущем = новостройка
                    logger.info(f"   🔍 Определен как новостройка (год сдачи {year} >= {current_year})")
                    return True
                elif year >= current_year - 2:  # Сдан недавно (последние 2 года)
                    logger.info(f"   🔍 Определен как новостройка (сдан недавно: {year})")
                    return True
            except (ValueError, TypeError):
                pass

        # Метод 3: Проверка статуса объекта
        object_status = target_property.get('object_status', '').lower()
        if 'новостр' in object_status or 'строит' in object_status:
            logger.info(f"   🔍 Определен как новостройка (статус: {object_status})")
            return True

        # Метод 4: Эвристика - без отделки + высокая цена за м²
        repair_level = target_property.get('repair_level', '').lower()
        price_per_sqm = target_property.get('price_per_sqm', 0) or target_property.get('price', 0) / max(target_property.get('total_area', 1), 1)

        if 'без отделки' in repair_level and price_per_sqm > 200_000:  # Премиум без отделки = скорее всего новостройка
            logger.info(f"   🔍 Определен как новостройка (без отделки + цена {price_per_sqm:,.0f} ₽/м²)")
            return True

        # По умолчанию считаем вторичкой
        logger.info(f"   🔍 Определен как вторичка (не найдено признаков новостройки)")
        return False

    def _get_segment_tolerances(self, target_price: float):
        """
        Определяет допуски в зависимости от сегмента недвижимости

        Returns:
            tuple: (price_tolerance, area_tolerance, segment)
        """
        # FIX ISSUE #1: УЖЕСТОЧЕНЫ допуски для премиум-сегмента (новостройки дороже)
        # Для премиум-сегмента нужны узкие диапазоны, т.к. разброс цен меньше
        if target_price >= 300_000_000:  # Элитная недвижимость (300+ млн)
            return 0.15, 0.10, "элитная"  # ±15% цена, ±10% площадь (было 0.30/0.20)
        elif target_price >= 100_000_000:  # Премиум (100-300 млн)
            return 0.20, 0.15, "премиум"  # ±20% цена, ±15% площадь (было 0.40/0.30)
        elif target_price >= 25_000_000:   # Средний+ (25-100 млн) - УЖЕСТОЧЕНЫ ДОПУСКИ
            return 0.25, 0.20, "средний+"  # ±25% цена, ±20% площадь (было 0.50/0.35)
            # Для 31 млн: диапазон 23.25-38.75 млн вместо 15.5-46.5 млн
        else:  # Эконом (до 25 млн)
            return 0.40, 0.30, "эконом"  # ±40% цена, ±30% площадь (было 0.60/0.40)

    def _build_search_url(self, target_price: float, target_area: float, target_rooms: int,
                          price_tolerance: float, area_tolerance: float, target_property: Dict = None) -> str:
        """
        Строит URL для поиска на Циан

        Args:
            target_price: Целевая цена
            target_area: Целевая площадь
            target_rooms: Количество комнат
            price_tolerance: Допуск по цене (0.2 = ±20%)
            area_tolerance: Допуск по площади (0.15 = ±15%)
            target_property: Целевой объект (для определения типа)

        Returns:
            str: URL для поиска
        """
        search_params = {
            'deal_type': 'sale',
            'offer_type': 'flat',
            'engine_version': '2',
            'price_min': int(target_price * (1 - price_tolerance)),
            'price_max': int(target_price * (1 + price_tolerance)),
            'minArea': int(target_area * (1 - area_tolerance)),
            'maxArea': int(target_area * (1 + area_tolerance)),
            'region': self.region_code,
        }

        # PATCH: Определяем тип объекта (новостройка vs вторичка)
        is_new_building = self._is_new_building(target_property)

        # КРИТИЧЕСКИ ВАЖНО: Правильный параметр Циан!
        # type=4 - новостройки, type=1 - вторичка
        if is_new_building:
            search_params['type'] = '4'  # 4 = новостройка в Cian API
            logger.info(f"   🏗️ Целевой объект - НОВОСТРОЙКА, фильтруем поиск (type=4)")
        else:
            search_params['type'] = '1'  # 1 = вторичка в Cian API
            logger.info(f"   🏠 Целевой объект - ВТОРИЧКА, фильтруем поиск (type=1)")

        # PATCH: Фильтр по этажам (не первый и не последний для средних этажей)
        # Исключаем первый и последний этажи, если целевой объект - средний этаж
        if target_property:
            floor = target_property.get('floor')
            total_floors = target_property.get('total_floors')

            if floor and total_floors:
                try:
                    floor_num = int(floor)
                    total_num = int(total_floors)

                    # Если средний этаж (не 1 и не последний)
                    if floor_num > 1 and floor_num < total_num:
                        search_params['not_first_floor'] = '1'  # Исключить первый
                        search_params['not_last_floor'] = '1'   # Исключить последний
                        logger.info(f"   🏢 Фильтр этажей: ТОЛЬКО средние (не 1, не {total_num})")
                    elif floor_num == 1:
                        # Ищем только первые этажи
                        search_params['foot'] = '1'
                        logger.info(f"   🏢 Фильтр этажей: ТОЛЬКО первые")
                    elif floor_num == total_num:
                        # Ищем только последние этажи
                        search_params['max_foot'] = '1'
                        logger.info(f"   🏢 Фильтр этажей: ТОЛЬКО последние")
                except (ValueError, TypeError):
                    pass

        # PATCH: Фильтр по классу жилья для премиум-сегмента
        # class=1 - эконом, class=2 - комфорт, class=3 - бизнес, class=4 - элит
        if target_price >= 25_000_000 and is_new_building:
            # Для премиум-сегмента ищем только комфорт+ (2,3,4)
            search_params['class'] = '2'  # Комфорт как минимум
            logger.info(f"   💎 Фильтр класса: комфорт+ (премиум сегмент)")

        # PATCH: Фильтр по году сдачи (±1 год для новостроек)
        if is_new_building and target_property:
            build_year = target_property.get('build_year')
            if build_year:
                try:
                    year = int(build_year)
                    from datetime import datetime
                    current_year = datetime.now().year

                    # Для новостроек с годом сдачи в будущем
                    if year >= current_year:
                        # min_offer_date и max_offer_date в формате YYYY-Q (год-квартал)
                        # Например: 2028-3 = 3 квартал 2028
                        year_min = max(current_year, year - 1)
                        year_max = year + 1

                        # Циан использует формат: deadline_from=2027&deadline_to=2029
                        search_params['deadline_from'] = str(year_min)
                        search_params['deadline_to'] = str(year_max)
                        logger.info(f"   📅 Фильтр года сдачи: {year_min}-{year_max} (±1 год от {year})")
                except (ValueError, TypeError):
                    pass

        # PATCH: Фильтр по отделке (с отделкой/без)
        if target_property:
            repair_level = target_property.get('repair_level', '').lower()

            if 'без отделки' in repair_level or 'черновая' in repair_level:
                # Ищем объекты без отделки
                # decoration=1 - без отделки, decoration=2 - с отделкой, decoration=3 - под ключ
                search_params['decoration'] = '1'
                logger.info(f"   🎨 Фильтр отделки: БЕЗ отделки")
            elif 'отделк' in repair_level or 'ремонт' in repair_level:
                # Ищем объекты с отделкой
                search_params['decoration'] = '2'
                logger.info(f"   🎨 Фильтр отделки: С отделкой")

        # PATCH: Фильтр по типу дома (для вторички)
        # building_type: 1-кирпичный, 2-панельный, 3-блочный, 4-монолитный, 5-кирпично-монолитный
        if not is_new_building and target_property:
            house_type = target_property.get('house_type', '').lower()

            if 'монолит' in house_type:
                if 'кирпич' in house_type:
                    search_params['building_type'] = '5'  # Кирпично-монолитный
                    logger.info(f"   🏗️ Фильтр типа дома: кирпично-монолитный")
                else:
                    search_params['building_type'] = '4'  # Монолитный
                    logger.info(f"   🏗️ Фильтр типа дома: монолитный")
            elif 'кирпич' in house_type:
                search_params['building_type'] = '1'  # Кирпичный
                logger.info(f"   🏗️ Фильтр типа дома: кирпичный")
            elif 'панел' in house_type:
                search_params['building_type'] = '2'  # Панельный
                logger.info(f"   🏗️ Фильтр типа дома: панельный")
            elif 'блочн' in house_type:
                search_params['building_type'] = '3'  # Блочный
                logger.info(f"   🏗️ Фильтр типа дома: блочный")

        # PATCH: Фильтр по году постройки (для вторички, ±10 лет)
        if not is_new_building and target_property:
            build_year = target_property.get('build_year')
            if build_year:
                try:
                    year = int(build_year)
                    from datetime import datetime
                    current_year = datetime.now().year

                    # Только для вторички (не будущие года)
                    if year < current_year:
                        year_min = year - 10
                        year_max = year + 10

                        search_params['min_year'] = str(year_min)
                        search_params['max_year'] = str(year_max)
                        logger.info(f"   📅 Фильтр года постройки: {year_min}-{year_max} (±10 лет от {year})")
                except (ValueError, TypeError):
                    pass

        # Комнаты (диапазон ±1)
        # Обработка различных типов target_rooms
        if isinstance(target_rooms, str):
            if 'студия' in target_rooms.lower():
                target_rooms_int = 1
            else:
                # Извлекаем число из строки (например, "2-комн." -> 2)
                import re
                match = re.search(r'\d+', target_rooms)
                target_rooms_int = int(match.group()) if match else 2
        else:
            target_rooms_int = int(target_rooms) if target_rooms else 2

        # КРИТИЧЕСКИЙ ФИКС: СТРОГИЙ фильтр комнат (без смешивания!)
        # БЫЛО: rooms_min=1, rooms_max=2 → room1=1 И room2=1 (искало 1-комн И 2-комн!)
        # СЕЙЧАС: ТОЛЬКО room{target}=1 (ищем СТРОГО указанное количество комнат)
        search_params[f'room{target_rooms_int}'] = '1'
        logger.info(f"   🏠 Фильтр комнат: СТРОГО {target_rooms_int}-комнатные (без смешивания!)")

        return f"{self.base_url}/cat.php?" + '&'.join([f"{k}={v}" for k, v in search_params.items()])

    def _filter_by_location(self, results: List[Dict], target_property: Dict, strict: bool = True) -> List[Dict]:
        """
        Фильтрует результаты по локации (метро, район)

        Args:
            results: Список найденных объявлений
            target_property: Целевой объект
            strict: Если True, требуется точное совпадение метро/района
                   Если False, допускается совпадение хотя бы части адреса

        Returns:
            Отфильтрованный список
        """
        # Обработка metro как списка или строки
        target_metro_raw = target_property.get('metro', '')
        if isinstance(target_metro_raw, list):
            # Если metro - список, берем первую станцию или объединяем через запятую
            target_metro = ', '.join(target_metro_raw).lower().strip() if target_metro_raw else ''
        else:
            target_metro = str(target_metro_raw).lower().strip()

        target_address = target_property.get('address', '').lower().strip()

        if not target_metro and not target_address:
            logger.info("   ℹ️ Нет данных о локации целевого объекта, фильтрация пропущена")
            return results

        filtered = []

        # Извлекаем ключевые слова из адреса (районы, улицы)
        # Игнорируем город, короткие слова и стоп-слова
        stop_words = {'москва', 'санкт-петербург', 'спб', 'мск', 'улица', 'проспект', 'переулок',
                      'бульвар', 'шоссе', 'набережная', 'площадь', 'аллея', 'проезд'}

        target_keywords = set()
        if target_address:
            for word in target_address.replace(',', ' ').split():
                word = word.strip()
                if len(word) > 3 and word not in stop_words:
                    target_keywords.add(word)

        for result in results:
            # Обработка метро результата (может быть списком или строкой)
            result_metro_raw = result.get('metro', '')
            if isinstance(result_metro_raw, list):
                result_metro = ', '.join(result_metro_raw).lower().strip() if result_metro_raw else ''
            else:
                result_metro = result_metro_raw.lower().strip() if result_metro_raw else ''

            result_address = result.get('address', '').lower().strip() if result.get('address') else ''

            # Строгий режим: совпадение метро
            if strict and target_metro:
                if target_metro in result_metro or result_metro in target_metro:
                    filtered.append(result)
                    continue

            # Нестрогий режим: совпадение части адреса
            if not strict and target_keywords:
                result_keywords = set()
                for word in result_address.replace(',', ' ').split():
                    word = word.strip()
                    if len(word) > 3 and word not in stop_words:
                        result_keywords.add(word)

                # Если есть хотя бы 1 общее ключевое слово (район, улица и т.д.)
                if target_keywords & result_keywords:
                    filtered.append(result)
                    continue

        return filtered

    def search_similar(self, target_property: Dict, limit: int = 20) -> List[Dict]:
        """
        Многоуровневый поиск похожих квартир (ДОРАБОТКА #5)

        Уровень 1: Поиск с базовыми допусками + фильтр по району/метро
        Уровень 2: Поиск по всему городу (без фильтра локации)
        Уровень 3: Расширенный поиск (+50% к допускам)

        Args:
            target_property: Целевой объект с полями price, total_area, rooms, metro, address
            limit: максимальное количество результатов

        Returns:
            Список похожих объявлений
        """
        logger.info("=" * 80)
        logger.info("🔍 НАЧИНАЕМ МНОГОУРОВНЕВЫЙ ПОИСК АНАЛОГОВ (ДОРАБОТКА #5)")
        logger.info("=" * 80)

        # Формируем критерии поиска
        target_price = target_property.get('price', 100_000_000)
        target_area = target_property.get('total_area', 100)
        target_rooms = target_property.get('rooms', 2)

        # Обработка случая "студия" - считаем как 1 комнату
        if isinstance(target_rooms, str):
            if 'студ' in target_rooms.lower():
                target_rooms = 1
            else:
                # Попытка извлечь число из строки
                import re
                match = re.search(r'\d+', target_rooms)
                target_rooms = int(match.group()) if match else 2

        # Обработка метро (может быть списком или строкой)
        target_metro_raw = target_property.get('metro', '')
        if isinstance(target_metro_raw, list):
            target_metro = ', '.join(target_metro_raw) if target_metro_raw else ''
        else:
            target_metro = target_metro_raw if target_metro_raw else ''

        target_address = target_property.get('address', '')

        # ═══════════════════════════════════════════════════════════════════════════
        # ДОРАБОТКА #2: АДАПТИВНЫЕ ДИАПАЗОНЫ ПОИСКА (в зависимости от сегмента)
        # ═══════════════════════════════════════════════════════════════════════════
        price_tolerance, area_tolerance, segment = self._get_segment_tolerances(target_price)

        logger.info(f"📋 Параметры целевого объекта:")
        logger.info(f"   - Сегмент: {segment} (адаптивные допуски: цена ±{price_tolerance*100:.0f}%, площадь ±{area_tolerance*100:.0f}%)")
        logger.info(f"   - Цена: {target_price:,} ₽")
        logger.info(f"   - Площадь: {target_area} м²")
        logger.info(f"   - Комнаты: {target_rooms}")
        logger.info(f"   - Метро: {target_metro or 'не указано'}")
        logger.info(f"   - Адрес: {target_address or 'не указан'}")
        logger.info("")

        final_results = []
        # Инициализируем переменные для отслеживания новых результатов каждого уровня
        new_results_level2 = []
        new_results_level3 = []

        # ═══════════════════════════════════════════════════════════════════════════
        # УРОВЕНЬ 0: ДЛЯ НОВОСТРОЕК - ПРИОРИТЕТ ПОИСКА ПО ЖК
        # КРИТИЧЕСКИЙ ФИКС: Для новостроек сначала пробуем найти в том же ЖК
        # ═══════════════════════════════════════════════════════════════════════════
        is_new_building = self._is_new_building(target_property)
        residential_complex = target_property.get('residential_complex', '')

        if is_new_building and residential_complex:
            logger.info(f"🏗️ УРОВЕНЬ 0: Новостройка - пробуем поиск по ЖК '{residential_complex}'")
            try:
                results_level0 = self.search_similar_in_building(target_property, limit=limit)
                if len(results_level0) >= 5:
                    logger.info(f"   ✅ УРОВЕНЬ 0: Нашли достаточно аналогов в ЖК ({len(results_level0)} шт.)")
                    validated_level0 = self._validate_and_prepare_results(results_level0, limit, target_property=target_property)
                    final_results.extend(validated_level0)
                    logger.info(f"   ✅ УРОВЕНЬ 0 ЗАВЕРШЁН: {len(validated_level0)} аналогов из того же ЖК")
                    logger.info("=" * 80)
                    return final_results[:limit]
                else:
                    logger.warning(f"   ⚠️ УРОВЕНЬ 0: В ЖК найдено мало аналогов ({len(results_level0)} шт.), переходим к широкому поиску")
                    # Добавляем то что нашли, и продолжаем
                    if results_level0:
                        validated_level0 = self._validate_and_prepare_results(results_level0, limit, target_property=target_property)
                        final_results.extend(validated_level0)
                        logger.info(f"   ✓ Добавлено {len(validated_level0)} аналогов из ЖК")
            except Exception as e:
                logger.warning(f"   ⚠️ УРОВЕНЬ 0: Ошибка поиска по ЖК - {e}")
                logger.info(f"   → Переходим к широкому поиску")
            logger.info("")

        # ═══════════════════════════════════════════════════════════════════════════
        # УРОВЕНЬ 1: Поиск в том же районе/у того же метро
        # ═══════════════════════════════════════════════════════════════════════════
        logger.info("🎯 УРОВЕНЬ 1: Поиск аналогов в том же районе/у метро")
        logger.info(f"   Диапазон цен: {int(target_price * (1-price_tolerance)):,} - {int(target_price * (1+price_tolerance)):,} ₽")
        logger.info(f"   Диапазон площади: {int(target_area * (1-area_tolerance))} - {int(target_area * (1+area_tolerance))} м²")

        url_level1 = self._build_search_url(target_price, target_area, target_rooms,
                                            price_tolerance, area_tolerance, target_property)
        logger.info(f"   URL: {url_level1[:100]}...")

        results_level1 = self.parse_search_page(url_level1)
        logger.info(f"   ✓ Найдено объявлений: {len(results_level1)}")

        # ═══════════════════════════════════════════════════════════════════════════
        # КРИТИЧЕСКИЙ ФИКС БАГ #2: PROGRESSIVE FILTER RELAXATION
        # Если 0 результатов → убираем доп. фильтры (год/класс/этажи/отделка)
        # ═══════════════════════════════════════════════════════════════════════════
        if len(results_level1) == 0:
            logger.warning("⚠️ Уровень 1 дал 0 результатов!")
            logger.warning("⚠️ Пробуем БЕЗ фильтров (год/класс/этажи/отделка)...")

            # Строим URL ТОЛЬКО с критическими фильтрами
            search_params_relaxed = {
                'deal_type': 'sale',
                'offer_type': 'flat',
                'engine_version': '2',
                'price_min': int(target_price * (1 - price_tolerance)),
                'price_max': int(target_price * (1 + price_tolerance)),
                'minArea': int(target_area * (1 - area_tolerance)),
                'maxArea': int(target_area * (1 + area_tolerance)),
                'region': self.region_code,
            }

            # КРИТИЧНО: Тип объекта (новостройка/вторичка)
            is_new_building = self._is_new_building(target_property)
            if is_new_building:
                search_params_relaxed['type'] = '4'
                logger.info(f"   🏗️ Тип: НОВОСТРОЙКА (type=4)")
            else:
                search_params_relaxed['type'] = '1'
                logger.info(f"   🏠 Тип: ВТОРИЧКА (type=1)")

            # КРИТИЧНО: Комнаты (СТРОГО указанное количество)
            if isinstance(target_rooms, str):
                if 'студия' in target_rooms.lower():
                    target_rooms_int = 1
                else:
                    import re
                    match = re.search(r'\d+', target_rooms)
                    target_rooms_int = int(match.group()) if match else 2
            else:
                target_rooms_int = int(target_rooms) if target_rooms else 2

            search_params_relaxed[f'room{target_rooms_int}'] = '1'
            logger.info(f"   🏠 Комнаты: СТРОГО {target_rooms_int}-комнатные")

            # НЕ добавляем: deadline_from/to, class, not_first/last_floor, decoration, building_type
            url_relaxed = f"{self.base_url}/cat.php?" + '&'.join([f"{k}={v}" for k, v in search_params_relaxed.items()])
            logger.info(f"   🔄 Relaxed URL: {url_relaxed[:100]}...")

            results_level1 = self.parse_search_page(url_relaxed)
            logger.info(f"   ✅ После снятия доп. фильтров найдено: {len(results_level1)} объявлений")

        # Фильтруем по локации (строгий режим - только совпадение метро)
        if target_metro or target_address:
            filtered_level1 = self._filter_by_location(results_level1, target_property, strict=True)
            logger.info(f"   ✓ После фильтрации по локации: {len(filtered_level1)} объявлений")
        else:
            filtered_level1 = results_level1
            logger.info(f"   ℹ️ Фильтрация по локации пропущена (нет данных о метро/адресе)")

        # Валидация и добавление
        validated_level1 = self._validate_and_prepare_results(filtered_level1, limit, target_property=target_property)
        final_results.extend(validated_level1)
        logger.info(f"   ✅ УРОВЕНЬ 1: Добавлено {len(validated_level1)} валидных аналогов")
        logger.info("")

        # Проверяем, достаточно ли аналогов
        if len(final_results) >= 10:
            logger.info(f"✅ Найдено достаточно аналогов ({len(final_results)} шт.), поиск завершен")
            logger.info("=" * 80)
            return final_results[:limit]

        # ═══════════════════════════════════════════════════════════════════════════
        # УРОВЕНЬ 2: Расширенный поиск по городу (без фильтра локации)
        # ═══════════════════════════════════════════════════════════════════════════
        logger.info(f"🌆 УРОВЕНЬ 2: Расширяем поиск на весь город")
        logger.info(f"   (текущее количество: {len(final_results)}, нужно минимум 10)")

        # Используем все результаты с уровня 1, но без фильтра локации
        validated_level2 = self._validate_and_prepare_results(results_level1, limit, target_property=target_property)

        # Добавляем только новые (которых нет в final_results)
        existing_urls = {r.get('url') for r in final_results}
        new_results_level2 = [r for r in validated_level2 if r.get('url') not in existing_urls]

        final_results.extend(new_results_level2)
        logger.info(f"   ✅ УРОВЕНЬ 2: Добавлено {len(new_results_level2)} новых аналогов из города")
        logger.info("")

        # Проверяем снова
        if len(final_results) >= 5:
            logger.info(f"✅ Найдено достаточно аналогов ({len(final_results)} шт.), поиск завершен")
            logger.info("=" * 80)
            return final_results[:limit]

        # ═══════════════════════════════════════════════════════════════════════════
        # УРОВЕНЬ 3: Сверхрасширенный поиск (допуски +50%)
        # ═══════════════════════════════════════════════════════════════════════════
        logger.info(f"🚀 УРОВЕНЬ 3: Расширяем диапазоны поиска (+50% к допускам)")
        logger.info(f"   (текущее количество: {len(final_results)}, нужно минимум 5)")

        expanded_price_tolerance = price_tolerance * 1.5
        expanded_area_tolerance = area_tolerance * 1.5

        logger.info(f"   Новые допуски: цена ±{expanded_price_tolerance*100:.0f}%, площадь ±{expanded_area_tolerance*100:.0f}%")
        logger.info(f"   Диапазон цен: {int(target_price * (1-expanded_price_tolerance)):,} - {int(target_price * (1+expanded_price_tolerance)):,} ₽")
        logger.info(f"   Диапазон площади: {int(target_area * (1-expanded_area_tolerance))} - {int(target_area * (1+expanded_area_tolerance))} м²")

        url_level3 = self._build_search_url(target_price, target_area, target_rooms,
                                            expanded_price_tolerance, expanded_area_tolerance, target_property)
        logger.info(f"   URL: {url_level3[:100]}...")

        results_level3 = self.parse_search_page(url_level3)
        logger.info(f"   ✓ Найдено объявлений: {len(results_level3)}")

        validated_level3 = self._validate_and_prepare_results(results_level3, limit, target_property=target_property)

        # Добавляем только новые
        existing_urls = {r.get('url') for r in final_results}
        new_results_level3 = [r for r in validated_level3 if r.get('url') not in existing_urls]

        final_results.extend(new_results_level3)
        logger.info(f"   ✅ УРОВЕНЬ 3: Добавлено {len(new_results_level3)} новых аналогов")
        logger.info("")

        # Проверяем снова
        if len(final_results) >= 5:
            logger.info(f"✅ Найдено достаточно аналогов ({len(final_results)} шт.), поиск завершен")
            logger.info("=" * 80)
            return final_results[:limit]

        # ═══════════════════════════════════════════════════════════════════════════
        # УРОВЕНЬ 4: FALLBACK ДЛЯ ПРЕМИУМ-СЕГМЕНТА (только район, без фильтра цены)
        # FIX ISSUE #1: Добавлен fallback для премиум-сегмента
        # ═══════════════════════════════════════════════════════════════════════════
        if target_price >= 25_000_000:  # Только для премиум/средний+
            logger.info(f"🆘 УРОВЕНЬ 4: FALLBACK для премиум-сегмента")
            logger.info(f"   (текущее количество: {len(final_results)}, критический минимум: 5)")
            logger.info(f"   Ищем ТОЛЬКО по району, БЕЗ фильтра цены (максимально широкий поиск)")

            # Убираем фильтр цены, оставляем только площадь и комнаты
            search_params_fallback = {
                'deal_type': 'sale',
                'offer_type': 'flat',
                'engine_version': '2',
                'minArea': int(target_area * 0.5),  # Еще шире: ±50% площадь
                'maxArea': int(target_area * 1.5),
                'region': self.region_code,
            }

            # Комнаты (±1)
            if isinstance(target_rooms, str):
                if 'студия' in target_rooms.lower():
                    target_rooms_int = 1
                else:
                    import re
                    match = re.search(r'\d+', target_rooms)
                    target_rooms_int = int(match.group()) if match else 2
            else:
                target_rooms_int = int(target_rooms) if target_rooms else 2

            # СТРОГИЙ фильтр комнат (без смешивания!)
            search_params_fallback[f'room{target_rooms_int}'] = '1'
            logger.info(f"   🏠 Фильтр комнат: СТРОГО {target_rooms_int}-комнатные")

            url_fallback = f"{self.base_url}/cat.php?" + '&'.join([f"{k}={v}" for k, v in search_params_fallback.items()])
            logger.info(f"   URL: {url_fallback[:100]}...")

            results_fallback = self.parse_search_page(url_fallback)
            logger.info(f"   ✓ Найдено объявлений: {len(results_fallback)}")

            # Фильтруем по локации (нестрогий режим)
            if target_metro or target_address:
                filtered_fallback = self._filter_by_location(results_fallback, target_property, strict=False)
                logger.info(f"   ✓ После фильтрации по локации (нестрогий режим): {len(filtered_fallback)} объявлений")
            else:
                filtered_fallback = results_fallback

            validated_fallback = self._validate_and_prepare_results(filtered_fallback, limit, target_property=target_property)

            # Добавляем только новые
            existing_urls = {r.get('url') for r in final_results}
            new_results_fallback = [r for r in validated_fallback if r.get('url') not in existing_urls]

            final_results.extend(new_results_fallback)
            logger.info(f"   ✅ УРОВЕНЬ 4 (FALLBACK): Добавлено {len(new_results_fallback)} новых аналогов")
            logger.info("")

        # ═══════════════════════════════════════════════════════════════════════════
        # НОВОЕ: Приоритизация аналогов из того же ЖК
        # ═══════════════════════════════════════════════════════════════════════════
        target_rc = target_property.get('residential_complex', '').lower().strip()
        if target_rc and len(final_results) > 0:
            # Захватываем target_price и target_area для использования в замыкании
            _target_price = target_price
            _target_area = target_area

            def sort_key(result):
                # Проверяем наличие ЖК в заголовке или адресе аналога
                result_title = result.get('title', '').lower()
                result_address = result.get('address', '').lower()
                same_rc = target_rc in result_title or target_rc in result_address

                # Вычисляем разницу цены за м²
                result_price = result.get('price') or result.get('price_raw') or 0
                result_area = result.get('total_area') or result.get('area_value') or 1
                result_price_per_sqm = result_price / result_area if result_area > 0 else 0

                target_price_per_sqm = _target_price / _target_area if _target_area > 0 else 0
                price_diff = abs(result_price_per_sqm - target_price_per_sqm) if target_price_per_sqm > 0 else float('inf')

                # Сортируем: сначала из того же ЖК (False < True, инвертируем), затем по близости цены
                return (not same_rc, price_diff)

            final_results.sort(key=sort_key)
            same_rc_count = sum(1 for r in final_results if target_rc in r.get('title', '').lower() or target_rc in r.get('address', '').lower())
            if same_rc_count > 0:
                logger.info(f"🏘️ Приоритизация: {same_rc_count} аналогов из того же ЖК '{target_property.get('residential_complex')}' выше в списке")

        # Итоговый результат (фильтрация по региону уже выполнена в _validate_and_prepare_results)
        logger.info("=" * 80)
        logger.info(f"🏁 ПОИСК ЗАВЕРШЕН: Найдено {len(final_results)} аналогов")
        logger.info(f"   - Уровень 1 (район/метро): {len(validated_level1)} шт.")
        logger.info(f"   - Уровень 2 (город): +{len(new_results_level2)} шт.")
        logger.info(f"   - Уровень 3 (расширенный): +{len(new_results_level3)} шт.")
        if target_price >= 25_000_000 and 'new_results_fallback' in locals():
            logger.info(f"   - Уровень 4 (fallback для премиум): +{len(new_results_fallback)} шт.")

        # ═══════════════════════════════════════════════════════════════════════════
        # НОВОЕ: Статистика качества подбора (разброс цен за м²)
        # ═══════════════════════════════════════════════════════════════════════════
        if len(final_results) > 0:
            prices_per_sqm = []
            for result in final_results:
                price = result.get('price') or result.get('price_raw') or 0
                area = result.get('total_area') or result.get('area_value') or 0
                if price > 0 and area > 0:
                    prices_per_sqm.append(price / area)

            if len(prices_per_sqm) > 1:
                min_price_sqm = min(prices_per_sqm)
                max_price_sqm = max(prices_per_sqm)
                avg_price_sqm = sum(prices_per_sqm) / len(prices_per_sqm)
                spread = ((max_price_sqm - min_price_sqm) / min_price_sqm) * 100

                logger.info("")
                logger.info("📊 СТАТИСТИКА КАЧЕСТВА ПОДБОРА:")
                logger.info(f"   - Мин цена/м²: {min_price_sqm:,.0f} ₽")
                logger.info(f"   - Макс цена/м²: {max_price_sqm:,.0f} ₽")
                logger.info(f"   - Средняя цена/м²: {avg_price_sqm:,.0f} ₽")
                logger.info(f"   - Разброс: {spread:.0f}%")

                if spread > 50:
                    logger.warning(f"⚠️ ВНИМАНИЕ: Разброс цен {spread:.0f}% превышает 50%!")
                    logger.warning(f"   Рекомендуется ручная проверка аналогов")
                elif spread > 30:
                    logger.warning(f"⚠️ Разброс цен {spread:.0f}% умеренно высокий")
                else:
                    logger.info(f"✓ Разброс цен {spread:.0f}% в допустимых пределах")

        logger.info("=" * 80)

        return final_results[:limit]
