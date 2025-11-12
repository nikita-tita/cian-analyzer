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

    # Ищем упоминание городов
    if 'moskva' in url.lower() or 'moscow' in url.lower():
        return 'msk'
    elif 'sankt-peterburg' in url.lower() or 'spb' in url.lower():
        return 'spb'

    # По умолчанию - СПб
    return 'spb'


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

    @retry_with_exponential_backoff(max_retries=3, base_delay=2.0, max_delay=10.0)
    def _get_page_content(self, url: str) -> Optional[str]:
        """
        Получить HTML контент через Playwright

        Args:
            url: URL для загрузки

        Returns:
            HTML контент или None

        Raises:
            Exception: После 3 неудачных попыток загрузки
        """
        if not self.context:
            raise RuntimeError("Браузер не запущен. Используйте with context или вызовите .start()")

        page: Page = self.context.new_page()

        try:
            logger.info(f"Загрузка страницы: {url}")

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
            logger.error(f"Ошибка при загрузке {url}: {e}")
            raise  # Пробрасываем для retry-механизма

        finally:
            page.close()
            time.sleep(self.delay)

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
        enable_validation: bool = True
    ) -> List[Dict]:
        """
        Валидация и подготовка результатов перед возвратом

        Args:
            results: Список спарсенных объявлений
            limit: Максимальное количество результатов
            enable_validation: Включить валидацию данных

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
                return self._validate_and_prepare_results(results, limit)
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

        # Строим URL поиска с текстовым запросом
        search_params = {
            'deal_type': 'sale',
            'offer_type': 'flat',
            'engine_version': '2',
            'region': self.region_code,
            'text': encoded_query,
        }

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
        return self._validate_and_prepare_results(filtered_results, limit)

    def search_similar(self, target_property: Dict, limit: int = 20) -> List[Dict]:
        """
        Автоматический поиск похожих квартир (широкий поиск по городу)

        Args:
            target_property: Целевой объект с полями price, total_area, rooms
            limit: максимальное количество результатов

        Returns:
            Список похожих объявлений
        """
        logger.info("🔍 Начинаем широкий поиск похожих квартир по городу...")

        # Формируем критерии поиска
        target_price = target_property.get('price', 100_000_000)
        target_area = target_property.get('total_area', 100)
        target_rooms = target_property.get('rooms', 2)

        # DEBUG: Показываем параметры поиска
        logger.info("📋 DEBUG: Параметры широкого поиска:")
        logger.info(f"   - Цена: {target_price:,} ₽ (диапазон: {int(target_price * 0.5):,} - {int(target_price * 1.5):,})")
        logger.info(f"   - Площадь: {target_area} м² (диапазон: {int(target_area * 0.6)} - {int(target_area * 1.4)})")
        logger.info(f"   - Комнаты: {target_rooms} (диапазон: {max(1, target_rooms - 1)} - {target_rooms + 1})")

        # Строим URL поиска
        search_params = {
            'deal_type': 'sale',
            'offer_type': 'flat',
            'engine_version': '2',
            'price_min': int(target_price * 0.5),
            'price_max': int(target_price * 1.5),
            'minArea': int(target_area * 0.6),
            'maxArea': int(target_area * 1.4),
            'region': self.region_code,
        }

        # Комнаты (диапазон ±1)
        rooms_min = max(1, target_rooms - 1)
        rooms_max = target_rooms + 1
        for i in range(rooms_min, rooms_max + 1):
            search_params[f'room{i}'] = '1'

        url = f"{self.base_url}/cat.php?" + '&'.join([f"{k}={v}" for k, v in search_params.items()])

        logger.info(f"URL поиска: {url}")

        # Парсим результаты
        results = self.parse_search_page(url)

        logger.info(f"✓ Найдено {len(results)} похожих объявлений")

        # Валидация и подготовка
        return self._validate_and_prepare_results(results, limit)
