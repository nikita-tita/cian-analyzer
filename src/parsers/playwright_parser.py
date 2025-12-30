"""
Эффективный Playwright парсер с переиспользованием браузера
"""

import time
import logging
from typing import Optional, List, Dict, Callable, Any
from functools import wraps
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext
from bs4 import BeautifulSoup

from .base_parser import BaseCianParser
from ..exceptions import CaptchaError, ContentBlockedError

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
    logger.warning("Валидатор данных недоступен - фильтрация отключена")


# Глобальный маппинг поддоменов ЦИАН на коды регионов (для detect_region_from_url)
SUBDOMAIN_TO_REGION = {
    # Основные города
    'spb': 'spb', 'piter': 'spb', 'saint-petersburg': 'spb',
    'msk': 'msk', 'moskva': 'msk', 'moscow': 'msk',
    # Области
    'mo': 'mo', 'moskovskaya-oblast': 'mo',
    'lo': 'lo', 'leningradskaya-oblast': 'lo',
    # Города-миллионники и крупные города
    'ekaterinburg': 'sverdlovsk', 'ekb': 'sverdlovsk',
    'novosibirsk': 'novosibirsk', 'nsk': 'novosibirsk',
    'kazan': 'tatarstan', 'tatarstan': 'tatarstan',
    'nizhniy-novgorod': 'nizhniy-novgorod', 'nn': 'nizhniy-novgorod',
    'krasnodar': 'krasnodar', 'sochi': 'krasnodar',
    'rostov': 'rostov', 'rostov-na-donu': 'rostov',
    'samara': 'samara',
    'chelyabinsk': 'chelyabinsk',
    'voronezh': 'voronezh',
    'omsk': 'omsk',
    'krasnoyarsk': 'krasnoyarsk',
    # Тула и другие регионы
    'tula': 'tula',
    'tver': 'tver',
    'kaliningrad': 'kaliningrad',
    'tyumen': 'tyumen',
    'irkutsk': 'irkutsk',
    'perm': 'perm',
    'ufa': 'bashkortostan', 'bashkortostan': 'bashkortostan',
    'vladivostok': 'primorye', 'primorye': 'primorye',
    'khabarovsk': 'khabarovsk',
    'yaroslavl': 'yaroslavl',
    'ryazan': 'ryazan',
    'lipetsk': 'lipetsk',
    'ivanovo': 'ivanovo',
    'vladimir': 'vladimir',
    'bryansk': 'bryansk',
    'orel': 'orel',
    'kursk': 'kursk',
    'belgorod': 'belgorod',
    'tambov': 'tambov',
    'saratov': 'saratov',
    'penza': 'penza',
    'volgograd': 'volgograd',
    'astrakhan': 'astrakhan',
    'kaluga': 'kaluga',
    'smolensk': 'smolensk',
    'pskov': 'pskov',
    'novgorod': 'novgorod',
    'vologda': 'vologda',
    'arkhangelsk': 'arkhangelsk',
    'murmansk': 'murmansk',
    'karelia': 'karelia',
    'crimea': 'crimea', 'krym': 'crimea', 'simferopol': 'crimea',
    'sevastopol': 'sevastopol',
    'komi': 'komi',
    'kirov': 'kirov',
    'kostroma': 'kostroma',
    'tomsk': 'tomsk',
    'kemerovo': 'kemerovo',
    'ulyanovsk': 'ulyanovsk',
    'orenburg': 'orenburg',
    'kurgan': 'kurgan',
    'magadan': 'magadan',
    'sakhalin': 'sakhalin',
    'amur': 'amur',
}


def detect_region_from_url(url: str) -> str:
    """
    Автоопределение региона по URL объекта.
    Поддерживает все регионы России через поддомены ЦИАН.

    Args:
        url: URL объявления

    Returns:
        Ключ региона (например 'msk', 'spb', 'tula') или None если не удалось определить
    """
    if not url:
        return None

    url_lower = url.lower()

    # Извлекаем поддомен из URL
    # Формат: https://tula.cian.ru/... -> tula
    import re
    subdomain_match = re.search(r'https?://([a-z0-9-]+)\.cian\.ru', url_lower)

    if subdomain_match:
        subdomain = subdomain_match.group(1)

        # www.cian.ru = Москва (дефолтный регион)
        if subdomain == 'www':
            logger.info(f"URL www.cian.ru определен как МОСКВА (дефолтный регион)")
            return 'msk'

        # Ищем поддомен в маппинге
        if subdomain in SUBDOMAIN_TO_REGION:
            region = SUBDOMAIN_TO_REGION[subdomain]
            logger.info(f"Регион определен по поддомену: {subdomain} -> {region}")
            return region

        # Если поддомен неизвестен, возвращаем его как есть (возможно новый регион)
        logger.warning(f"Неизвестный поддомен: {subdomain}, используем как ключ региона")
        return subdomain

    # cian.ru без поддомена = Москва
    if 'cian.ru' in url_lower:
        logger.info(f"URL cian.ru без поддомена определен как МОСКВА")
        return 'msk'

    # Резервные проверки для старого формата URL
    if any(word in url_lower for word in ['sankt-peterburg', 'saint-petersburg', '/spb/']):
        return 'spb'
    if any(word in url_lower for word in ['moskva', 'moscow', '/msk/']):
        return 'msk'

    logger.warning(f"Не удалось определить регион по URL: {url}")
    return None


# Маппинг ключевых слов в адресе на регионы
ADDRESS_KEYWORDS_TO_REGION = {
    # Москва и МО
    'msk': ['москва', 'moscow', 'г москва', 'г.москва'],
    'mo': ['московская область', 'московская обл', 'мо,'],
    # Санкт-Петербург и ЛО
    'spb': ['санкт-петербург', 'спб', 'с-петербург', 'с.петербург', 'питер', 'saint-petersburg'],
    'lo': ['ленинградская область', 'ленинградская обл', 'ло,'],
    # Города-миллионники
    'novosibirsk': ['новосибирск', 'новосибирская'],
    'sverdlovsk': ['екатеринбург', 'свердловская'],
    'tatarstan': ['казань', 'татарстан', 'республика татарстан'],
    'nizhniy-novgorod': ['нижний новгород', 'нижегородская'],
    'chelyabinsk': ['челябинск', 'челябинская'],
    'omsk': ['омск', 'омская'],
    'samara': ['самара', 'самарская'],
    'rostov': ['ростов-на-дону', 'ростов на дону', 'ростовская'],
    'bashkortostan': ['уфа', 'башкортостан', 'республика башкортостан'],
    'krasnoyarsk': ['красноярск', 'красноярская'],
    'perm': ['пермь', 'пермская', 'пермский'],
    'voronezh': ['воронеж', 'воронежская'],
    'volgograd': ['волгоград', 'волгоградская'],
    'krasnodar': ['краснодар', 'сочи', 'краснодарский'],
    # Областные центры
    'tula': ['тула', 'тульская'],
    'tver': ['тверь', 'тверская'],
    'kaluga': ['калуга', 'калужская'],
    'ryazan': ['рязань', 'рязанская'],
    'vladimir': ['владимир', 'владимирская'],
    'yaroslavl': ['ярославль', 'ярославская'],
    'ivanovo': ['иваново', 'ивановская'],
    'kostroma': ['кострома', 'костромская'],
    'bryansk': ['брянск', 'брянская'],
    'orel': ['орёл', 'орел', 'орловская'],
    'kursk': ['курск', 'курская'],
    'belgorod': ['белгород', 'белгородская'],
    'lipetsk': ['липецк', 'липецкая'],
    'tambov': ['тамбов', 'тамбовская'],
    'penza': ['пенза', 'пензенская'],
    'saratov': ['саратов', 'саратовская'],
    'ulyanovsk': ['ульяновск', 'ульяновская'],
    'orenburg': ['оренбург', 'оренбургская'],
    'tyumen': ['тюмень', 'тюменская'],
    'tomsk': ['томск', 'томская'],
    'kemerovo': ['кемерово', 'кемеровская'],
    'irkutsk': ['иркутск', 'иркутская'],
    'kaliningrad': ['калининград', 'калининградская'],
    'arkhangelsk': ['архангельск', 'архангельская'],
    'murmansk': ['мурманск', 'мурманская'],
    'vologda': ['вологда', 'вологодская'],
    'pskov': ['псков', 'псковская'],
    'novgorod': ['великий новгород', 'новгородская'],
    'smolensk': ['смоленск', 'смоленская'],
    'astrakhan': ['астрахань', 'астраханская'],
    'kurgan': ['курган', 'курганская'],
    'primorye': ['владивосток', 'приморский край'],
    'khabarovsk': ['хабаровск', 'хабаровский'],
    'sakhalin': ['сахалин', 'южно-сахалинск'],
    'amur': ['благовещенск', 'амурская'],
    'crimea': ['симферополь', 'крым', 'республика крым'],
    'sevastopol': ['севастополь'],
    'karelia': ['петрозаводск', 'карелия', 'республика карелия'],
    'komi': ['сыктывкар', 'коми', 'республика коми'],
}


def detect_region_from_address(address: str) -> str:
    """
    Определение региона по адресу объекта.
    Поддерживает все регионы России.

    Args:
        address: Адрес объявления

    Returns:
        Ключ региона (например 'msk', 'spb', 'tula') или None
    """
    if not address:
        return None

    address_lower = address.lower()

    # Ищем совпадения с ключевыми словами
    for region_key, keywords in ADDRESS_KEYWORDS_TO_REGION.items():
        for keyword in keywords:
            if keyword in address_lower:
                logger.info(f"Регион определен по адресу: {region_key} (ключевое слово: {keyword})")
                return region_key

    logger.warning(f"Не удалось определить регион по адресу: {address}")
    return None


def retry_with_exponential_backoff(max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 10.0) -> Callable:
    """
    Декоратор для повторных попыток с экспоненциальной задержкой

    Args:
        max_retries: Максимальное количество попыток
        base_delay: Базовая задержка между попытками (секунды)
        max_delay: Максимальная задержка между попытками (секунды)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
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

    # Константы для валидации и фильтрации
    MIN_HTML_SIZE = 1000  # Минимальный размер HTML (символов)
    MAX_ADDRESS_LENGTH = 200  # Максимальная длина адреса (символов)
    MIN_RESULTS_THRESHOLD = 5  # Минимум аналогов для завершения уровня 0
    PREFERRED_RESULTS_THRESHOLD = 10  # Предпочтительное количество аналогов
    MIN_LOCAL_FOR_STOP = 5  # Минимум близких аналогов для остановки БЕЗ расширения на город

    # Словарь соседних станций метро Москвы (основные линии)
    # Формат: 'станция': ['соседняя1', 'соседняя2', ...]
    NEARBY_METRO = {
        # Красная линия (1)
        'сокольники': ['красносельская', 'преображенская площадь'],
        'красносельская': ['сокольники', 'комсомольская'],
        'комсомольская': ['красносельская', 'красные ворота'],
        'красные ворота': ['комсомольская', 'чистые пруды'],
        'чистые пруды': ['красные ворота', 'лубянка'],
        'лубянка': ['чистые пруды', 'охотный ряд'],
        'охотный ряд': ['лубянка', 'библиотека имени ленина'],
        'библиотека имени ленина': ['охотный ряд', 'кропоткинская'],
        'кропоткинская': ['библиотека имени ленина', 'парк культуры'],
        'парк культуры': ['кропоткинская', 'фрунзенская'],
        'фрунзенская': ['парк культуры', 'спортивная'],
        'спортивная': ['фрунзенская', 'воробьёвы горы'],
        'воробьёвы горы': ['спортивная', 'университет'],
        'университет': ['воробьёвы горы', 'проспект вернадского'],
        'проспект вернадского': ['университет', 'юго-западная'],
        'юго-западная': ['проспект вернадского', 'тропарёво'],

        # Зелёная линия (2)
        'речной вокзал': ['водный стадион'],
        'водный стадион': ['речной вокзал', 'войковская'],
        'войковская': ['водный стадион', 'сокол'],
        'сокол': ['войковская', 'аэропорт'],
        'аэропорт': ['сокол', 'динамо'],
        'динамо': ['аэропорт', 'белорусская'],
        'белорусская': ['динамо', 'маяковская'],
        'маяковская': ['белорусская', 'тверская'],
        'тверская': ['маяковская', 'театральная'],
        'театральная': ['тверская', 'новокузнецкая'],
        'новокузнецкая': ['театральная', 'павелецкая'],
        'павелецкая': ['новокузнецкая', 'автозаводская'],
        'автозаводская': ['павелецкая', 'коломенская', 'дубровка'],  # Замоскворецкая + БКЛ
        'коломенская': ['автозаводская', 'каширская'],
        'каширская': ['коломенская', 'кантемировская'],
        'технопарк': ['автозаводская', 'коломенская'],  # Ближайшие станции

        # Синяя линия (3)
        'щёлковская': ['первомайская'],
        'первомайская': ['щёлковская', 'измайловская'],
        'измайловская': ['первомайская', 'партизанская'],
        'партизанская': ['измайловская', 'семёновская'],
        'семёновская': ['партизанская', 'электрозаводская'],
        'электрозаводская': ['семёновская', 'бауманская'],
        'бауманская': ['электрозаводская', 'курская'],
        'курская': ['бауманская', 'площадь революции'],
        'площадь революции': ['курская', 'арбатская'],
        'арбатская': ['площадь революции', 'смоленская'],
        'смоленская': ['арбатская', 'киевская'],
        'киевская': ['смоленская', 'парк победы'],
        'парк победы': ['киевская', 'славянский бульвар'],

        # Кольцевая линия (5)
        'проспект мира': ['комсомольская', 'новослободская'],
        'новослободская': ['проспект мира', 'белорусская'],
        'краснопресненская': ['белорусская', 'киевская'],
        'октябрьская': ['парк культуры', 'добрынинская'],
        'добрынинская': ['октябрьская', 'павелецкая'],
        'таганская': ['павелецкая', 'курская'],

        # Оранжевая линия (6)
        'медведково': ['бабушкинская'],
        'бабушкинская': ['медведково', 'свиблово'],
        'свиблово': ['бабушкинская', 'ботанический сад'],
        'ботанический сад': ['свиблово', 'вднх'],
        'вднх': ['ботанический сад', 'алексеевская'],
        'алексеевская': ['вднх', 'рижская'],
        'рижская': ['алексеевская', 'проспект мира'],
        'сухаревская': ['проспект мира', 'тургеневская'],
        'тургеневская': ['сухаревская', 'китай-город'],
        'китай-город': ['тургеневская', 'третьяковская'],
        'третьяковская': ['китай-город', 'октябрьская'],

        # Серая линия (9)
        'алтуфьево': ['бибирево'],
        'бибирево': ['алтуфьево', 'отрадное'],
        'отрадное': ['бибирево', 'владыкино'],
        'владыкино': ['отрадное', 'петровско-разумовская'],
        'петровско-разумовская': ['владыкино', 'тимирязевская'],
        'тимирязевская': ['петровско-разумовская', 'дмитровская'],
        'дмитровская': ['тимирязевская', 'савёловская'],
        'савёловская': ['дмитровская', 'менделеевская'],
        'менделеевская': ['савёловская', 'цветной бульвар'],
        'цветной бульвар': ['менделеевская', 'чеховская'],
        'чеховская': ['цветной бульвар', 'боровицкая'],
        'боровицкая': ['чеховская', 'полянка'],
        'полянка': ['боровицкая', 'серпуховская'],

        # Салатовая линия (10)
        'люблино': ['братиславская', 'волжская'],
        'братиславская': ['люблино', 'марьино'],
        'марьино': ['братиславская', 'борисово'],
        'волжская': ['люблино', 'печатники'],
        'печатники': ['волжская', 'кожуховская'],
        'кожуховская': ['печатники', 'дубровка'],
        'дубровка': ['кожуховская', 'крестьянская застава'],

        # Бирюзовая линия (11 - БКЛ) - основные станции
        'савёловская': ['марьина роща', 'петровский парк'],
        'марьина роща': ['савёловская', 'рижская'],
        'петровский парк': ['савёловская', 'цска'],
        'цска': ['петровский парк', 'хорошёвская'],
        'хорошёвская': ['цска', 'шелепиха'],
        'шелепиха': ['хорошёвская', 'деловой центр'],
        'деловой центр': ['шелепиха', 'москва-сити'],
    }

    # Словарь соседних станций метро Санкт-Петербурга (5 линий)
    # Формат: 'станция': ['соседняя1', 'соседняя2', ...]
    NEARBY_METRO_SPB = {
        # Линия 1 (Кировско-Выборгская, красная)
        'девяткино': ['гражданский проспект'],
        'гражданский проспект': ['девяткино', 'академическая'],
        'академическая': ['гражданский проспект', 'политехническая'],
        'политехническая': ['академическая', 'площадь мужества'],
        'площадь мужества': ['политехническая', 'лесная'],
        'лесная': ['площадь мужества', 'выборгская'],
        'выборгская': ['лесная', 'площадь ленина'],
        'площадь ленина': ['выборгская', 'чернышевская'],
        'чернышевская': ['площадь ленина', 'площадь восстания'],
        'площадь восстания': ['чернышевская', 'владимирская', 'маяковская'],  # пересадка на 3
        'владимирская': ['площадь восстания', 'пушкинская', 'достоевская'],  # пересадка на 4
        'пушкинская': ['владимирская', 'технологический институт', 'звенигородская'],  # пересадка на 5
        'технологический институт': ['пушкинская', 'балтийская', 'фрунзенская'],  # пересадка на 2
        'балтийская': ['технологический институт', 'нарвская'],
        'нарвская': ['балтийская', 'кировский завод'],
        'кировский завод': ['нарвская', 'автово'],
        'автово': ['кировский завод', 'ленинский проспект'],
        'ленинский проспект': ['автово', 'проспект ветеранов'],
        'проспект ветеранов': ['ленинский проспект'],

        # Линия 2 (Московско-Петроградская, синяя)
        'парнас': ['проспект просвещения'],
        'проспект просвещения': ['парнас', 'озерки'],
        'озерки': ['проспект просвещения', 'удельная'],
        'удельная': ['озерки', 'пионерская'],
        'пионерская': ['удельная', 'чёрная речка'],
        'чёрная речка': ['пионерская', 'петроградская'],
        'черная речка': ['пионерская', 'петроградская'],  # альтернативное написание
        'петроградская': ['чёрная речка', 'горьковская'],
        'горьковская': ['петроградская', 'невский проспект'],
        'невский проспект': ['горьковская', 'сенная площадь', 'гостиный двор'],  # пересадка на 3
        'сенная площадь': ['невский проспект', 'технологический институт', 'садовая', 'спасская'],  # пересадки 4,5
        'фрунзенская': ['технологический институт', 'московские ворота'],
        'московские ворота': ['фрунзенская', 'электросила'],
        'электросила': ['московские ворота', 'парк победы'],
        'парк победы': ['электросила', 'московская'],
        'московская': ['парк победы', 'звёздная'],
        'звёздная': ['московская', 'купчино'],
        'звездная': ['московская', 'купчино'],  # альтернативное написание
        'купчино': ['звёздная'],

        # Линия 3 (Невско-Василеостровская, зелёная)
        'беговая': ['новокрестовская'],
        'новокрестовская': ['беговая', 'приморская'],
        'зенит': ['беговая', 'приморская'],  # альтернативное название
        'приморская': ['новокрестовская', 'василеостровская'],
        'василеостровская': ['приморская', 'гостиный двор'],
        'гостиный двор': ['василеостровская', 'маяковская', 'невский проспект'],  # пересадка на 2
        'маяковская': ['гостиный двор', 'площадь александра невского', 'площадь восстания'],  # пересадка на 1
        'площадь александра невского': ['маяковская', 'елизаровская', 'новочеркасская'],  # пересадка на 4
        'елизаровская': ['площадь александра невского', 'ломоносовская'],
        'ломоносовская': ['елизаровская', 'пролетарская'],
        'пролетарская': ['ломоносовская', 'обухово'],
        'обухово': ['пролетарская', 'рыбацкое'],
        'рыбацкое': ['обухово'],

        # Линия 4 (Правобережная, оранжевая)
        'спасская': ['достоевская', 'сенная площадь', 'садовая'],  # пересадки 2,5
        'достоевская': ['спасская', 'лиговский проспект', 'владимирская'],  # пересадка на 1
        'лиговский проспект': ['достоевская', 'площадь александра невского'],
        'новочеркасская': ['площадь александра невского', 'ладожская'],
        'ладожская': ['новочеркасская', 'проспект большевиков'],
        'проспект большевиков': ['ладожская', 'улица дыбенко'],
        'улица дыбенко': ['проспект большевиков'],

        # Линия 5 (Фрунзенско-Приморская, фиолетовая)
        'комендантский проспект': ['старая деревня'],
        'старая деревня': ['комендантский проспект', 'крестовский остров'],
        'крестовский остров': ['старая деревня', 'чкаловская'],
        'чкаловская': ['крестовский остров', 'спортивная'],
        'спортивная': ['чкаловская', 'адмиралтейская'],
        'адмиралтейская': ['спортивная', 'садовая'],
        'садовая': ['адмиралтейская', 'звенигородская', 'сенная площадь', 'спасская'],  # пересадки 2,4
        'звенигородская': ['садовая', 'обводный канал', 'пушкинская'],  # пересадка на 1
        'обводный канал': ['звенигородская', 'волковская'],
        'волковская': ['обводный канал', 'бухарестская'],
        'бухарестская': ['волковская', 'международная'],
        'международная': ['бухарестская', 'проспект славы'],
        'проспект славы': ['международная', 'дунайская'],
        'дунайская': ['проспект славы', 'шушары'],
        'шушары': ['дунайская'],
    }

    @staticmethod
    def _normalize_rooms(target_rooms) -> int:
        """
        Конвертирует значение rooms в int

        Args:
            target_rooms: Количество комнат (str, int или None)

        Returns:
            int: Количество комнат (студия → 1, '2-комн' → 2, None → 0)

        Examples:
            >>> PlaywrightParser._normalize_rooms('студия')
            1
            >>> PlaywrightParser._normalize_rooms('2-комн. квартира')
            2
            >>> PlaywrightParser._normalize_rooms(3)
            3
            >>> PlaywrightParser._normalize_rooms(None)
            0
        """
        if not target_rooms:
            return 0

        if isinstance(target_rooms, str):
            # Проверка на студию
            if 'студ' in target_rooms.lower():
                return 1

            # Извлечение числа из строки
            import re
            match = re.search(r'\d+', target_rooms)
            return int(match.group()) if match else 0

        # Если уже int
        return int(target_rooms)

    @staticmethod
    def _get_room_filter_params(target_rooms: int, strict: bool = True) -> dict:
        """
        Генерирует параметры фильтра комнат для ЦИАН API

        Args:
            target_rooms: Количество комнат (нормализованное)
            strict: Если True - только точное совпадение, False - ±1 комната

        Returns:
            dict: Параметры для URL (например {'room2': '1', 'room3': '1'})

        Examples:
            >>> PlaywrightParser._get_room_filter_params(3, strict=True)
            {'room3': '1'}
            >>> PlaywrightParser._get_room_filter_params(3, strict=False)
            {'room2': '1', 'room3': '1', 'room4': '1'}
        """
        if target_rooms <= 0:
            target_rooms = 2  # дефолт

        if strict:
            return {f'room{target_rooms}': '1'}

        # Нестрогий режим: ±1 комната с учетом крайних случаев
        params = {}

        # Студия (room9 в ЦИАН) или 1-комн → разрешаем студии + 1 + 2
        if target_rooms == 1:
            params['room9'] = '1'  # студия в ЦИАН
            params['room1'] = '1'
            params['room2'] = '1'
        # 5+ комнат → 4, 5, 6 (все большие квартиры схожий сегмент)
        elif target_rooms >= 5:
            params['room4'] = '1'
            params['room5'] = '1'
            params['room6'] = '1'  # 6+ в ЦИАН
        # 2-4 комнаты → ±1
        else:
            for r in range(max(1, target_rooms - 1), min(6, target_rooms + 2)):
                params[f'room{r}'] = '1'

        return params

    @classmethod
    def _get_nearby_metros(cls, metro_name: str, region: str = 'msk') -> List[str]:
        """
        Возвращает список соседних станций метро

        Args:
            metro_name: Название станции метро
            region: Регион ('msk' для Москвы, 'spb' для СПб)

        Returns:
            List[str]: Список соседних станций (включая исходную)

        Example:
            >>> PlaywrightParser._get_nearby_metros('Сокольники', 'msk')
            ['сокольники', 'красносельская', 'преображенская площадь']
            >>> PlaywrightParser._get_nearby_metros('Невский проспект', 'spb')
            ['невский проспект', 'горьковская', 'сенная площадь', 'гостиный двор']
        """
        if not metro_name:
            return []

        # Выбираем словарь в зависимости от региона
        metro_dict = cls.NEARBY_METRO_SPB if region == 'spb' else cls.NEARBY_METRO

        # Нормализуем название (lowercase, убираем лишние пробелы)
        metro_lower = metro_name.lower().strip()

        # Убираем префиксы типа "м. ", "метро "
        for prefix in ['м. ', 'м.', 'метро ']:
            if metro_lower.startswith(prefix):
                metro_lower = metro_lower[len(prefix):].strip()

        # Ищем в словаре
        nearby = [metro_lower]  # всегда включаем исходную станцию

        if metro_lower in metro_dict:
            nearby.extend(metro_dict[metro_lower])

        # Также проверяем частичные совпадения (например "парк культуры" vs "парк-культуры")
        metro_normalized = metro_lower.replace('-', ' ').replace('ё', 'е')
        for station, neighbors in metro_dict.items():
            station_normalized = station.replace('-', ' ').replace('ё', 'е')
            if station_normalized == metro_normalized and station != metro_lower:
                nearby.extend(neighbors)
                break

        return list(set(nearby))  # убираем дубликаты

    def __init__(
        self,
        headless: bool = True,
        delay: float = 2.0,
        block_resources: bool = True,
        cache=None,
        region: str = 'spb',
        browser_pool=None,
        proxy_config: Optional[Dict] = None
    ):
        """
        Args:
            headless: Запускать браузер в фоновом режиме
            delay: Задержка между запросами
            block_resources: Блокировать картинки/шрифты для ускорения
            cache: PropertyCache instance (опционально)
            region: Регион поиска ('spb' или 'msk')
            browser_pool: BrowserPool instance (опционально, рекомендуется для production)
            proxy_config: Конфигурация прокси {'server': 'http://host:port', 'username': '...', 'password': '...'}
        """
        super().__init__(delay, cache=cache)
        self.headless = headless
        self.block_resources = block_resources
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.browser_pool = browser_pool
        self.using_pool = browser_pool is not None
        self.proxy_config = proxy_config
        self._own_context = False  # Флаг: контекст создан нами (для прокси)

        # Полный маппинг регионов на коды ЦИАН (получено из API ЦИАН)
        self.region_codes = {
            # Основные регионы
            'msk': '1',           # Москва
            'spb': '2',           # Санкт-Петербург

            # Области вокруг крупных городов
            'mo': '4593',         # Московская область
            'lo': '4588',         # Ленинградская область

            # Республики
            'adygea': '4553',     # Республика Адыгея
            'altai-republic': '4554',  # Республика Алтай
            'bashkortostan': '4560',   # Республика Башкортостан
            'buryatia': '4563',   # Республика Бурятия
            'dagestan': '4568',   # Республика Дагестан
            'ingushetia': '4571', # Республика Ингушетия
            'kbr': '4573',        # Кабардино-Балкарская Республика
            'kalmykia': '4575',   # Республика Калмыкия
            'kchr': '4578',       # Карачаево-Черкесская Республика
            'karelia': '4579',    # Республика Карелия
            'komi': '4582',       # Республика Коми
            'mariy-el': '4591',   # Республика Марий Эл
            'mordovia': '4592',   # Республика Мордовия
            'yakutia': '4610',    # Республика Саха (Якутия)
            'osetia': '4613',     # Республика Северная Осетия - Алания
            'tatarstan': '4618',  # Республика Татарстан
            'tyva': '4622',       # Республика Тыва
            'udmurtia': '4624',   # Удмуртская Республика
            'khakassia': '4628',  # Республика Хакасия
            'chechnya': '4631',   # Чеченская Республика
            'chuvashia': '4633',  # Чувашская Республика
            'crimea': '181462',   # Республика Крым

            # Края
            'altai': '4555',      # Алтайский край
            'kamchatka': '4577',  # Камчатский край
            'krasnodar': '4584',  # Краснодарский край
            'krasnoyarsk': '4585', # Красноярский край
            'perm': '4603',       # Пермский край
            'primorye': '4604',   # Приморский край
            'stavropol': '4615',  # Ставропольский край
            'khabarovsk': '4627', # Хабаровский край
            'zabaikalye': '187450', # Забайкальский край

            # Области
            'amur': '4556',       # Амурская область
            'arkhangelsk': '4557', # Архангельская область
            'astrakhan': '4558',  # Астраханская область
            'belgorod': '4561',   # Белгородская область
            'bryansk': '4562',    # Брянская область
            'vladimir': '4564',   # Владимирская область
            'volgograd': '4565',  # Волгоградская область
            'vologda': '4566',    # Вологодская область
            'voronezh': '4567',   # Воронежская область
            'ivanovo': '4570',    # Ивановская область
            'irkutsk': '4572',    # Иркутская область
            'kaliningrad': '4574', # Калининградская область
            'kaluga': '4576',     # Калужская область
            'kemerovo': '4580',   # Кемеровская область
            'kirov': '4581',      # Кировская область
            'kostroma': '4583',   # Костромская область
            'kurgan': '4586',     # Курганская область
            'kursk': '4587',      # Курская область
            'lipetsk': '4589',    # Липецкая область
            'magadan': '4590',    # Магаданская область
            'murmansk': '4594',   # Мурманская область
            'nizhniy-novgorod': '4596', # Нижегородская область
            'novgorod': '4597',   # Новгородская область
            'novosibirsk': '4598', # Новосибирская область
            'omsk': '4599',       # Омская область
            'orenburg': '4600',   # Оренбургская область
            'orel': '4601',       # Орловская область
            'penza': '4602',      # Пензенская область
            'pskov': '4605',      # Псковская область
            'rostov': '4606',     # Ростовская область
            'ryazan': '4607',     # Рязанская область
            'samara': '4608',     # Самарская область
            'saratov': '4609',    # Саратовская область
            'sakhalin': '4611',   # Сахалинская область
            'sverdlovsk': '4612', # Свердловская область
            'smolensk': '4614',   # Смоленская область
            'tambov': '4617',     # Тамбовская область
            'tver': '4619',       # Тверская область
            'tomsk': '4620',      # Томская область
            'tula': '4621',       # Тульская область
            'tyumen': '4623',     # Тюменская область
            'ulyanovsk': '4625',  # Ульяновская область
            'chelyabinsk': '4630', # Челябинская область
            'yaroslavl': '4636',  # Ярославская область

            # Автономные округа
            'eao': '4569',        # Еврейская автономная область
            'nao': '4595',        # Ненецкий автономный округ
            'khanty-mansiysk': '4629', # Ханты-Мансийский автономный округ
            'chukotka': '4634',   # Чукотский автономный округ
            'yamalo-nenets': '4635', # Ямало-Ненецкий автономный округ

            # Город федерального значения
            'sevastopol': '184723', # Севастополь
        }

        # Маппинг поддоменов ЦИАН на ключи region_codes
        self.subdomain_to_region = {
            'spb': 'spb', 'piter': 'spb', 'saint-petersburg': 'spb',
            'msk': 'msk', 'moskva': 'msk', 'moscow': 'msk',
            'mo': 'mo', 'moskovskaya-oblast': 'mo',
            'lo': 'lo', 'leningradskaya-oblast': 'lo',
            'ekaterinburg': 'sverdlovsk', 'ekb': 'sverdlovsk',
            'novosibirsk': 'novosibirsk', 'nsk': 'novosibirsk',
            'kazan': 'tatarstan', 'tatarstan': 'tatarstan',
            'nizhniy-novgorod': 'nizhniy-novgorod', 'nn': 'nizhniy-novgorod',
            'krasnodar': 'krasnodar', 'sochi': 'krasnodar',
            'rostov': 'rostov', 'rostov-na-donu': 'rostov',
            'samara': 'samara',
            'chelyabinsk': 'chelyabinsk',
            'voronezh': 'voronezh',
            'omsk': 'omsk',
            'krasnoyarsk': 'krasnoyarsk',
            'tula': 'tula',
            'tver': 'tver',
            'kaliningrad': 'kaliningrad',
            'tyumen': 'tyumen',
            'irkutsk': 'irkutsk',
            'perm': 'perm',
            'ufa': 'bashkortostan', 'bashkortostan': 'bashkortostan',
            'vladivostok': 'primorye', 'primorye': 'primorye',
            'khabarovsk': 'khabarovsk',
            'yaroslavl': 'yaroslavl',
            'ryazan': 'ryazan',
            'lipetsk': 'lipetsk',
            'ivanovo': 'ivanovo',
            'vladimir': 'vladimir',
            'bryansk': 'bryansk',
            'orel': 'orel',
            'kursk': 'kursk',
            'belgorod': 'belgorod',
            'tambov': 'tambov',
            'saratov': 'saratov',
            'penza': 'penza',
            'volgograd': 'volgograd',
            'astrakhan': 'astrakhan',
            'kaluga': 'kaluga',
            'smolensk': 'smolensk',
            'pskov': 'pskov',
            'novgorod': 'novgorod',
            'vologda': 'vologda',
            'arkhangelsk': 'arkhangelsk',
            'murmansk': 'murmansk',
            'karelia': 'karelia',
            'crimea': 'crimea', 'krym': 'crimea', 'simferopol': 'crimea',
            'sevastopol': 'sevastopol',
            'komi': 'komi',
            'kirov': 'kirov',
            'kostroma': 'kostroma',
        }

        self.region = region
        self.region_code = self.region_codes.get(region, '1')  # Default: MSK (Moscow)

        logger.info(f"Регион: {region} (код: {self.region_code}), using_pool: {self.using_pool}")

    def __enter__(self) -> 'PlaywrightParser':
        """Context manager вход"""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager выход"""
        self.close()

    def _create_context_with_proxy(self) -> None:
        """
        Создаёт новый контекст браузера с прокси.
        Используется при работе с browser_pool для ротации прокси.
        """
        import random
        
        viewports = [
            {'width': 1920, 'height': 1080},
            {'width': 1536, 'height': 864},
            {'width': 1440, 'height': 900},
            {'width': 1366, 'height': 768},
        ]
        
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
        ]
        
        context_options = {
            'viewport': random.choice(viewports),
            'user_agent': random.choice(user_agents),
            'locale': 'ru-RU',
            'timezone_id': 'Europe/Moscow',
        }
        
        # Добавляем прокси
        if self.proxy_config:
            context_options['proxy'] = self.proxy_config
        
        self.context = self.browser.new_context(**context_options)
        
        # Скрываем автоматизацию (stealth)
        self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            delete navigator.__proto__.webdriver;
            window.chrome = { runtime: {}, loadTimes: function() { return {}; }, csi: function() { return {}; } };
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['ru-RU', 'ru', 'en-US', 'en'] });
        """)
        
        # Блокируем ненужные ресурсы для ускорения
        if self.block_resources:
            self.context.route(
                "**/*.{png,jpg,jpeg,gif,svg,webp,woff,woff2,ttf,mp4,mp3,pdf}",
                lambda route: route.abort()
            )
        
        logger.info(f"✓ Контекст создан с прокси: {self.proxy_config.get('server', 'unknown')}")

    def start(self) -> None:
        """Запуск браузера (один раз за сессию) или получение из пула"""
        if self.browser:
            logger.warning("Браузер уже запущен")
            return

        try:
            # Если используем browser pool, получаем браузер из пула
            if self.using_pool:
                logger.info("Acquiring browser from pool...")
                self.browser, pool_context = self.browser_pool.acquire(timeout=30.0)
                
                # КРИТИЧНО: Если есть proxy_config, создаём НОВЫЙ контекст с прокси
                # вместо использования контекста из пула (который без прокси)
                if self.proxy_config:
                    logger.info(f"🔒 Создаём новый контекст с прокси: {self.proxy_config['server']}")
                    self._own_context = True
                    self._create_context_with_proxy()
                else:
                    # Нет прокси - используем контекст из пула
                    self.context = pool_context
                    self._own_context = False
                
                logger.info("Браузер получен из пула")
                return

            # Иначе создаем собственный браузер (legacy режим)
            logger.info("Запуск Playwright браузера...")
            self.playwright = sync_playwright().start()

            self.browser = self.playwright.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-gpu',
                    '--disable-software-rasterizer',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--disable-setuid-sandbox',
                    '--disable-accelerated-2d-canvas',
                    '--no-first-run',
                    '--no-zygote',
                    '--disable-background-timer-throttling',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-renderer-backgrounding',
                ]
            )

            # Настройки контекста
            import random
            viewports = [
                {'width': 1920, 'height': 1080},
                {'width': 1536, 'height': 864},
                {'width': 1440, 'height': 900},
                {'width': 1366, 'height': 768},
            ]
            context_options = {
                'viewport': random.choice(viewports),
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                'locale': 'ru-RU',
                'timezone_id': 'Europe/Moscow',
            }

            # Добавляем прокси если настроен
            if self.proxy_config:
                context_options['proxy'] = self.proxy_config
                logger.info(f"Прокси настроен: {self.proxy_config['server']}")

            self.context = self.browser.new_context(**context_options)

            # Скрываем автоматизацию (расширенный stealth)
            self.context.add_init_script("""
                // Удаляем webdriver флаг
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });

                // Удаляем automation флаг
                delete navigator.__proto__.webdriver;

                // Добавляем chrome runtime
                window.chrome = {
                    runtime: {},
                    loadTimes: function() { return {}; },
                    csi: function() { return {}; },
                    app: { isInstalled: false, InstallState: { DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' }, RunningState: { CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' } }
                };

                // Скрываем автоматизацию в plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });

                // Скрываем languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['ru-RU', 'ru', 'en-US', 'en']
                });

                // Подмена permissions
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );

                // Скрываем headless в User-Agent data
                Object.defineProperty(navigator, 'userAgentData', {
                    get: () => ({
                        brands: [
                            { brand: 'Google Chrome', version: '131' },
                            { brand: 'Chromium', version: '131' },
                            { brand: 'Not_A Brand', version: '24' }
                        ],
                        mobile: false,
                        platform: 'Windows'
                    })
                });

                // Эмуляция WebGL vendor/renderer
                const getParameterProxyHandler = {
                    apply: function(target, ctx, args) {
                        if (args[0] === 37445) return 'Intel Inc.';
                        if (args[0] === 37446) return 'Intel Iris OpenGL Engine';
                        return Reflect.apply(target, ctx, args);
                    }
                };
                try {
                    const canvas = document.createElement('canvas');
                    const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
                    if (gl) {
                        gl.getParameter = new Proxy(gl.getParameter.bind(gl), getParameterProxyHandler);
                    }
                } catch(e) {}

                // Подмена battery API
                Object.defineProperty(navigator, 'getBattery', {
                    value: () => Promise.resolve({
                        charging: true,
                        chargingTime: 0,
                        dischargingTime: Infinity,
                        level: 1
                    })
                });

                // Подмена connection API
                Object.defineProperty(navigator, 'connection', {
                    value: {
                        effectiveType: '4g',
                        rtt: 50,
                        downlink: 10,
                        saveData: false
                    },
                    writable: false
                });

                // Подмена hardwareConcurrency
                Object.defineProperty(navigator, 'hardwareConcurrency', {
                    get: () => 8
                });

                // Подмена deviceMemory
                Object.defineProperty(navigator, 'deviceMemory', {
                    get: () => 8
                });
            """)

            # Блокируем ненужные ресурсы для ускорения
            if self.block_resources:
                self.context.route(
                    "**/*.{png,jpg,jpeg,gif,svg,webp,woff,woff2,ttf,mp4,mp3,pdf}",
                    lambda route: route.abort()
                )

            logger.info("Браузер запущен и готов к работе")

        except Exception as e:
            logger.error(f"Ошибка при запуске браузера: {e}")
            # Гарантируем очистку ресурсов при ошибке
            self.close()
            raise

    def close(self) -> None:
        """Закрытие браузера или возврат в пул"""
        # Если используем browser pool, возвращаем браузер в пул
        if self.using_pool and self.browser:
            try:
                # КРИТИЧНО: Если мы создали свой контекст (для прокси), закрываем его
                if self._own_context and self.context:
                    try:
                        logger.info("Закрываем созданный контекст с прокси...")
                        self.context.close()
                    except Exception as e:
                        logger.warning(f"Ошибка при закрытии контекста: {e}")
                    finally:
                        self.context = None
                
                logger.info("Returning browser to pool...")
                self.browser_pool.release(self.browser)
                self.browser = None
                self.context = None
                self._own_context = False
                logger.info("Browser returned to pool")
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

    def _check_for_captcha_or_block(self, html: str, url: str) -> None:
        """
        Проверяет HTML на наличие капчи или блокировки.
        Вызывает исключение если обнаружена проблема.

        Args:
            html: HTML контент страницы
            url: URL для диагностики

        Raises:
            CaptchaError: если страница содержит активную капчу
            ContentBlockedError: если контент заблокирован
        """
        html_lower = html.lower()

        # Признаки активной капчи (не просто наличие скрипта, а блокирующей капчи)
        captcha_blocking_signs = [
            'g-recaptcha' in html_lower and 'offertitle' not in html_lower,
            'captcha-form' in html_lower,
            'please verify you are human' in html_lower,
            'подтвердите, что вы не робот' in html_lower,
            'пройдите проверку' in html_lower and 'offertitle' not in html_lower,
        ]

        if any(captcha_blocking_signs):
            logger.warning(f"Обнаружена блокирующая капча для {url}")
            raise CaptchaError(url)

        # Признаки блокировки доступа
        block_signs = [
            'доступ заблокирован' in html_lower,
            'access denied' in html_lower,
            'доступ запрещен' in html_lower,
            'вы заблокированы' in html_lower,
        ]

        if any(block_signs):
            logger.warning(f"Обнаружена блокировка доступа для {url}")
            raise ContentBlockedError(url, reason="access_denied")

        # Проверка на пустую страницу (есть HTML но нет контента)
        content_indicators = ['offertitle', 'offerprice', 'application/ld+json']
        has_content = any(ind in html_lower for ind in content_indicators)

        if not has_content and len(html) > 10000:
            # Большая страница без контента - возможно редирект или ошибка
            logger.warning(f"Страница загружена ({len(html)} bytes) но контент не найден: {url}")
            raise ContentBlockedError(url, reason="no_content_found")

    def _get_page_content(self, url: str, max_retries: int = 5) -> Optional[str]:
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
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
                    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
                    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0',
                ]
                chosen_ua = random.choice(user_agents)
                page.set_extra_http_headers({
                    'User-Agent': chosen_ua,
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Cache-Control': 'no-cache',
                    'Sec-Ch-Ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
                    'Sec-Ch-Ua-Mobile': '?0',
                    'Sec-Ch-Ua-Platform': '"Windows"' if 'Windows' in chosen_ua else '"macOS"',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                    'Upgrade-Insecure-Requests': '1',
                })

                logger.info(f"Загрузка страницы (попытка {attempt}/{max_retries}): {url}")

                # Загружаем страницу
                page.goto(url, wait_until='domcontentloaded', timeout=30000)

                # Случайная задержка для имитации человека
                time.sleep(random.uniform(2.0, 4.0))

                # Имитация движения мыши (защита от антибота)
                try:
                    page.mouse.move(random.randint(100, 300), random.randint(100, 300))
                    time.sleep(random.uniform(0.3, 0.6))
                    page.mouse.move(random.randint(400, 600), random.randint(200, 400))
                    time.sleep(random.uniform(0.2, 0.5))
                except:
                    pass

                # Имитация скроллинга (защита от антибота)
                try:
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight / 4)")
                    time.sleep(random.uniform(0.8, 1.5))
                    page.evaluate("window.scrollTo(0, 0)")
                    time.sleep(random.uniform(0.5, 1.0))
                except:
                    pass

                # Ждем появления контента
                try:
                    page.wait_for_selector(
                        'h1, [data-mark="OfferTitle"], script[type="application/ld+json"]',
                        timeout=25000  # Увеличили timeout до 25 секунд
                    )
                except Exception as e:
                    logger.warning(f"Селекторы не найдены, но продолжаем: {e}")

                # Дополнительное ожидание для динамического контента
                time.sleep(random.uniform(1.0, 2.0))

                html = page.content()

                if not html or len(html) < self.MIN_HTML_SIZE:
                    raise ValueError(f"Получен пустой или слишком короткий HTML ({len(html) if html else 0} символов)")

                # Проверка на капчу/блокировку в HTML
                self._check_for_captcha_or_block(html, url)

                logger.info(f"Страница загружена ({len(html)} символов)")
                return html

            except (CaptchaError, ContentBlockedError) as e:
                # Специфичные ошибки капчи/блокировки - увеличиваем задержку
                last_error = e
                logger.warning(f"Попытка {attempt}/{max_retries}: {type(e).__name__}")
                if attempt < max_retries:
                    # Увеличенная случайная задержка для обхода капчи
                    delay = random.uniform(15, 25)
                    logger.info(f"   ⏳ Задержка {delay:.1f}с перед попыткой #{attempt + 1}")
                    time.sleep(delay)

            except Exception as e:
                last_error = e
                logger.warning(f"Попытка {attempt}/{max_retries} не удалась: {e}")

                # Если это капча или блокировка в exception - увеличиваем задержку
                if 'captcha' in str(e).lower() or '403' in str(e) or '429' in str(e):
                    logger.warning(f"Обнаружена блокировка/капча, увеличиваем задержку")
                    if attempt < max_retries:
                        time.sleep(10)

                if attempt == max_retries:
                    logger.error(f"Все {max_retries} попытки исчерпаны для {url}")
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
            logger.warning("DEBUG: _get_page_content вернул пустой HTML")
            return []

        soup = BeautifulSoup(html, 'lxml')

        # Используем адаптивные селекторы для поиска карточек
        from .adaptive_selectors import AdaptiveSelector, CARD_SELECTORS

        selector = AdaptiveSelector(soup)
        cards = selector.find_elements(CARD_SELECTORS, "карточки объявлений")

        logger.info(f"Найдено {len(cards)} карточек объявлений на странице")

        if len(cards) == 0:
            logger.warning("DEBUG: На странице не найдено ни одной карточки объявления")
            logger.warning(f"DEBUG: Размер HTML: {len(html)} байт")
            # Сохраним первые 2000 символов HTML для диагностики
            logger.debug(f"DEBUG: Начало HTML: {html[:2000]}")

        listings = []
        for i, card in enumerate(cards):
            try:
                listing_data = self._parse_listing_card(card)
                if listing_data.get('title'):
                    listings.append(listing_data)
                    if i < 3:  # Логируем первые 3 для отладки
                        logger.debug(f"Карточка {i+1} спарсена: {listing_data.get('title', '')[:80]}")
                else:
                    logger.debug(f"✗ Карточка {i+1}: отсутствует title, пропущена")
            except Exception as e:
                logger.warning(f"Ошибка при парсинге карточки {i+1}: {e}")
                continue

        logger.info(f"Успешно спарсено {len(listings)} объявлений из {len(cards)} карточек")

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
                    if len(text) < self.MAX_ADDRESS_LENGTH:  # Не берем слишком длинные тексты
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
        target_property: Dict = None,
        relaxed_filters: bool = False
    ) -> List[Dict]:
        """
        Валидация и подготовка результатов перед возвратом

        Args:
            results: Список спарсенных объявлений
            limit: Максимальное количество результатов
            enable_validation: Включить валидацию данных
            target_property: Целевой объект для проверки разумности аналогов (опционально)
            relaxed_filters: Ослабить фильтры (для ЖК где цена/м² важнее площади)

        Returns:
            Список валидных и подготовленных результатов
        """
        if not results:
            logger.info("DEBUG: _validate_and_prepare_results получил пустой список результатов")
            return []

        logger.info(f"DEBUG: Начинаем валидацию {len(results)} результатов (enable_validation={enable_validation})")

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
                        f"Исключен аналог из другого региона: "
                        f"{result_region} (ожидался {self.region}), "
                        f"адрес: {result_address[:80] if result_address else 'не указан'}"
                    )
            else:
                # КРИТИЧНО: Не удалось определить регион - ИСКЛЮЧАЕМ для безопасности
                # Это предотвращает попадание аналогов из других регионов в отчет
                region_excluded += 1
                logger.warning(
                    f"Исключен аналог с неопределенным регионом, "
                    f"URL: {result_url[:80] if result_url else 'не указан'}, "
                    f"адрес: {result_address[:80] if result_address else 'не указан'}"
                )

        if region_excluded > 0:
            logger.info(f"📊 Фильтрация по региону: {len(results)} → {len(region_filtered)} (исключено {region_excluded} из других регионов)")

        results = region_filtered

        # ═══════════════════════════════════════════════════════════════════════════
        # ДОРАБОТКА #3: ВАЛИДАЦИЯ РАЗУМНОСТИ АНАЛОГОВ
        # УЛУЧШЕНИЕ: relaxed_filters для ЖК (цена/м² важнее площади)
        # ═══════════════════════════════════════════════════════════════════════════
        if target_property:
            target_price = target_property.get('price', 0)
            # Ensure target_price is numeric (may come as string with currency symbols)
            if isinstance(target_price, str):
                import re
                cleaned = re.sub(r'[^\d.,]', '', target_price.replace(',', '.'))
                target_price = float(cleaned) if cleaned else 0
            target_price = float(target_price) if target_price else 0

            target_area = target_property.get('total_area', 0)

            # Адаптивные пороги в зависимости от режима
            if relaxed_filters:
                # Для ЖК: ослабленные фильтры (цена/м² важнее)
                price_ratio_threshold = 5.0      # было 3.0
                area_ratio_threshold = 3.0       # было 1.5 (для ЖК не так важно)
                price_sqm_threshold = 0.40       # было 0.30
                logger.info(f"   📊 Режим: ОСЛАБЛЕННЫЕ фильтры для ЖК (площадь ±{area_ratio_threshold}x, цена/м² ±{int(price_sqm_threshold*100)}%)")
            else:
                # Стандартные строгие фильтры
                price_ratio_threshold = 3.0
                area_ratio_threshold = 1.5
                price_sqm_threshold = 0.30

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

                    # Проверка 1: Цена не должна отличаться слишком сильно
                    price_ratio = max(comp_price, target_price) / min(comp_price, target_price)
                    if price_ratio > price_ratio_threshold:
                        unreasonable_count += 1
                        logger.warning(
                            f"Исключен неразумный аналог: цена отличается в {price_ratio:.1f} раз "
                            f"(аналог {comp_price:,} ₽ vs целевой {target_price:,} ₽), "
                            f"URL: {result.get('url', '')[:60]}..."
                        )
                        continue

                    # Проверка 2: Площадь (для ЖК - ослабленная)
                    area_ratio = max(comp_area, target_area) / min(comp_area, target_area)
                    if area_ratio > area_ratio_threshold:
                        unreasonable_count += 1
                        logger.warning(
                            f"Исключен неразумный аналог: площадь отличается в {area_ratio:.1f} раз "
                            f"(аналог {comp_area} м² vs целевой {target_area} м²), "
                            f"URL: {result.get('url', '')[:60]}..."
                        )
                        continue

                    # Проверка 3: Цена за м² (главный критерий для ЖК)
                    target_price_per_sqm = target_price / target_area
                    comp_price_per_sqm = comp_price / comp_area
                    price_per_sqm_diff = abs(comp_price_per_sqm - target_price_per_sqm) / target_price_per_sqm

                    if price_per_sqm_diff > price_sqm_threshold:
                        unreasonable_count += 1
                        logger.warning(
                            f"Исключен по цене/м²: отличие {price_per_sqm_diff*100:.0f}% "
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
                            f"Результат {i+1}: валиден "
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
                logger.info(f"Все {len(validated)} результатов прошли валидацию")

            results = validated
        else:
            logger.info(f"DEBUG: Валидация отключена или недоступна (VALIDATION_AVAILABLE={VALIDATION_AVAILABLE})")

        # Ограничиваем количество
        logger.info(f"Возвращаем {min(len(results), limit)} результатов (limit={limit})")
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
        logger.info("Начинаем поиск похожих квартир в том же ЖК...")

        residential_complex = target_property.get('residential_complex') or ''
        residential_complex_url = target_property.get('residential_complex_url') or ''
        address = target_property.get('address') or ''

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
                    logger.info(f"DEBUG: Найдено {len(catalog_links)} ссылок на странице ЖК")
                    for link in catalog_links:
                        href = link.get('href')

                        if ('/kupit-kvartiru-zhiloy-kompleks-' in href or
                                ('/cat.php' in href and 'newobject' in href)):
                            residential_complex_url = href if href.startswith('http') else f"https://www.cian.ru{href}"
                            logger.info(f"   Найдена ссылка на каталог: {residential_complex_url[:100]}")
                            break
                else:
                    logger.warning(f"DEBUG: Не удалось загрузить HTML страницы ЖК: {residential_complex_url}")

            # Парсим страницу с объявлениями ЖК
            logger.info(f"DEBUG: Парсим страницу ЖК: {residential_complex_url}")
            results = self.parse_search_page(residential_complex_url)

            if results:
                logger.info(f"Найдено {len(results)} объявлений через прямую ссылку на ЖК")
                # Валидация и подготовка
                return self._validate_and_prepare_results(results, limit, target_property=target_property)
            else:
                logger.warning("По прямой ссылке ничего не найдено, пробуем текстовый поиск")

        # ПРИОРИТЕТ 2: Текстовый поиск по названию ЖК (fallback)
        if not residential_complex:
            logger.warning("Не указан ЖК, используется поиск по адресу")
            # Пробуем извлечь из адреса
            import re
            match = re.search(r'ЖК\s+([А-Яа-яёЁ\s\-\d]+?)(?:,|$)', address or '')
            if match:
                residential_complex = match.group(1).strip()
            else:
                # Если нет ЖК - используем старый метод
                logger.warning("ЖК не найден, используется широкий поиск")
                return self.search_similar(target_property, limit)

        logger.info(f"📍 Текстовый поиск по ЖК: {residential_complex}")

        # Формируем поисковый запрос
        import urllib.parse

        # Вариант 1: Точное название ЖК
        search_query = f"ЖК {residential_complex}"
        encoded_query = urllib.parse.quote(search_query)

        # УЛУЧШЕНИЕ: Для ЖК ищем ВСЕ квартиры, т.к. цена/м² одинаковая
        # Фильтр комнат УБРАН - в ЖК 1-комн и 3-комн = хорошие аналоги по цене/м²
        target_area = target_property.get('total_area', 0)

        # Строим URL поиска с текстовым запросом БЕЗ строгих фильтров
        search_params = {
            'deal_type': 'sale',
            'offer_type': 'flat',
            'engine_version': '2',
            'region': self.region_code,
            'text': encoded_query,
        }

        # НЕ добавляем фильтр по площади для ЖК - цена/м² важнее!
        # В ЖК все квартиры имеют примерно одинаковую цену за м²
        logger.info(f"   📊 Поиск в ЖК: БЕЗ фильтра площади и комнат (цена/м² важнее)")

        # НЕ добавляем фильтр по комнатам - в ЖК это не важно

        url = f"{self.base_url}/cat.php?" + '&'.join([f"{k}={v}" for k, v in search_params.items()])

        logger.info(f"🔗 URL поиска: {url}")

        # Парсим результаты
        results = self.parse_search_page(url)

        logger.info(f"DEBUG: parse_search_page вернул {len(results)} результатов для текстового поиска")

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
                logger.info(f"     Добавлена (полное совпадение)")
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
                    logger.info(f"     Добавлена (частичное совпадение: {matching_in_title} в title, {matching_in_address} в address)")
                elif i < 5:
                    logger.info(f"     ✗ Пропущена (мало совпадений: {matching_in_title} в title, {matching_in_address} в address)")

        logger.info(f"Найдено {len(filtered_results)} похожих объявлений после фильтрации по ЖК '{residential_complex}'")

        # Валидация и подготовка с ОСЛАБЛЕННЫМИ фильтрами для ЖК
        # В ЖК цена/м² одинакова, поэтому площадь менее важна
        return self._validate_and_prepare_results(filtered_results, limit, target_property=target_property, relaxed_filters=True)

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
            logger.info(f"   Определен как новостройка (по URL)")
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
                    logger.info(f"   Определен как новостройка (год сдачи {year} >= {current_year})")
                    return True
                elif year >= current_year - 2:  # Сдан недавно (последние 2 года)
                    logger.info(f"   Определен как новостройка (сдан недавно: {year})")
                    return True
            except (ValueError, TypeError):
                pass

        # Метод 3: Проверка статуса объекта
        object_status = target_property.get('object_status', '').lower()
        if 'новостр' in object_status or 'строит' in object_status:
            logger.info(f"   Определен как новостройка (статус: {object_status})")
            return True

        # Метод 4: Эвристика - без отделки + высокая цена за м²
        repair_level = target_property.get('repair_level', '').lower()
        price_per_sqm = target_property.get('price_per_sqm', 0)
        if not price_per_sqm:
            raw_price = target_property.get('price', 0)
            # Convert string price to float (e.g., "12 000 000 ₽" -> 12000000.0)
            if isinstance(raw_price, str):
                import re
                cleaned = re.sub(r'[^\d.,]', '', raw_price.replace(',', '.'))
                raw_price = float(cleaned) if cleaned else 0
            raw_price = float(raw_price) if raw_price else 0
            total_area = float(target_property.get('total_area', 1) or 1)
            price_per_sqm = raw_price / max(total_area, 1)

        if 'без отделки' in repair_level and price_per_sqm > 200_000:  # Премиум без отделки = скорее всего новостройка
            logger.info(f"   Определен как новостройка (без отделки + цена {price_per_sqm:,.0f} ₽/м²)")
            return True

        # По умолчанию считаем вторичкой
        logger.info(f"   Определен как вторичка (не найдено признаков новостройки)")
        return False

    def _get_segment_tolerances(self, target_price: float) -> tuple[float, float, str]:
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

    def _parse_address(self, address: str) -> dict:
        """
        Парсит адрес и извлекает улицу и номер дома

        Примеры:
            "Санкт-Петербург, ул. Примерная, д. 4к2" -> {"street": "Примерная", "house": "4", "building": "к2"}
            "ул. Ленина, 15/3" -> {"street": "Ленина", "house": "15", "building": "/3"}

        Returns:
            dict: {"street": str, "house": str, "building": str} или пустой dict если не удалось распарсить
        """
        import re

        if not address:
            return {}

        # Нормализуем адрес
        addr = address.lower().strip()

        # Паттерны для извлечения улицы
        # ВАЖНО: ограничиваем захват до запятой или "д./дом"
        street_patterns = [
            r'(?:ул(?:\.|ица)?|пр(?:-т|оспект)?|пер(?:\.|еулок)?|б(?:-р|ульвар)?|наб(?:\.|ережная)?|ш(?:\.|оссе)?|пл(?:\.|ощадь)?)[.\s]+([а-яё][а-яё\s\-]*?)(?:,|\s+д\.|\s+д\s|\s+дом|\s*$)',
            r'([а-яё][а-яё\s\-]+?)\s+(?:улица|проспект|переулок|бульвар)',
        ]

        street = ""
        for pattern in street_patterns:
            match = re.search(pattern, addr)
            if match:
                street = match.group(1).strip()
                break

        # Паттерны для извлечения номера дома
        # Поддерживаем: д. 4, д.4, дом 4, 4к2, 4/3, 4 корп. 2, 4 стр. 1
        house_patterns = [
            r'(?:д(?:\.|ом)?)\s*(\d+)\s*(к(?:орп(?:\.|ус)?)?\.?\s*\d+|/\d+|стр(?:\.|оение)?\.?\s*\d+|лит(?:\.|ера)?\.?\s*[а-яa-z])?',
            r',\s*(\d+)\s*(к(?:орп(?:\.|ус)?)?\.?\s*\d+|/\d+|стр(?:\.|оение)?\.?\s*\d+|лит(?:\.|ера)?\.?\s*[а-яa-z])?\s*(?:,|$)',
        ]

        house = ""
        building = ""
        for pattern in house_patterns:
            match = re.search(pattern, addr)
            if match:
                house = match.group(1)
                building = match.group(2) or ""
                # Нормализуем корпус: "корп. 2" -> "к2", "корпус2" -> "к2"
                if building:
                    building = re.sub(r'корп(?:ус)?\.?\s*', 'к', building)
                    building = re.sub(r'стр(?:оение)?\.?\s*', 'с', building)
                    building = re.sub(r'\s+', '', building)
                break

        if not street and not house:
            return {}

        result = {
            "street": street.strip(' ,-'),
            "house": house,
            "building": building
        }

        logger.debug(f"   📍 Парсинг адреса '{address}' -> {result}")
        return result

    def _filter_by_house_proximity(
        self,
        results: List[Dict],
        target_address: str,
        max_distance: int = 5
    ) -> List[Dict]:
        """
        Фильтрует результаты по близости номера дома к целевому.

        Args:
            results: Список объявлений с полем 'address'
            target_address: Адрес целевого объекта
            max_distance: Максимальная разница в номерах домов (по умолчанию ±5)

        Returns:
            Отфильтрованный и отсортированный список (ближайшие дома первые)
        """
        target_parsed = self._parse_address(target_address)
        try:
            target_house = int(target_parsed.get('house', 0))
        except (ValueError, TypeError):
            target_house = 0

        if not target_house:
            logger.debug("   Не удалось определить номер целевого дома, фильтрация пропущена")
            return results

        filtered = []
        for r in results:
            result_address = r.get('address', '')
            if not result_address:
                continue

            parsed = self._parse_address(result_address)
            try:
                result_house = int(parsed.get('house', 0))
            except (ValueError, TypeError):
                result_house = 0

            if result_house:
                distance = abs(result_house - target_house)
                if distance <= max_distance:
                    r['_house_distance'] = distance
                    filtered.append(r)

        # Сортируем по близости (ближайшие первые)
        filtered.sort(key=lambda x: x.get('_house_distance', 999))

        logger.debug(f"   Фильтр по близости дома: {len(results)} -> {len(filtered)} (±{max_distance} от дома {target_house})")
        return filtered

    def _extract_okrug(self, address: str) -> str:
        """
        Извлекает административный округ Москвы из адреса.

        Args:
            address: Адрес объекта

        Returns:
            Код округа (ЦАО, ЮВАО, СЗАО и т.д.) или пустая строка
        """
        if not address:
            return ''

        address_upper = address.upper()

        # Все округа Москвы (в порядке от более длинных к более коротким для корректного матчинга)
        okrugs = [
            'ЮВАО',   # Юго-Восточный
            'ЮЗАО',   # Юго-Западный
            'СВАО',   # Северо-Восточный
            'СЗАО',   # Северо-Западный
            'ЦАО',    # Центральный
            'САО',    # Северный
            'ВАО',    # Восточный
            'ЗАО',    # Западный
            'ЮАО',    # Южный
            'НАО',    # Новомосковский (Новая Москва)
            'ТАО',    # Троицкий (Новая Москва)
            'ЗелАО',  # Зеленоградский
        ]

        for okrug in okrugs:
            if okrug in address_upper:
                return okrug

        return ''

    def _extract_district_spb(self, address: str) -> str:
        """
        Извлекает район Санкт-Петербурга из адреса.

        Args:
            address: Адрес объекта

        Returns:
            Название района или пустая строка
        """
        if not address:
            return ''

        address_lower = address.lower()

        # Районы СПб (18 районов) - порядок от более длинных к коротким
        districts = [
            ('красногвардейский', 'Красногвардейский'),
            ('красносельский', 'Красносельский'),
            ('василеостровский', 'Василеостровский'),
            ('петродворцовый', 'Петродворцовый'),
            ('адмиралтейский', 'Адмиралтейский'),
            ('калининский', 'Калининский'),
            ('кронштадтский', 'Кронштадтский'),
            ('петроградский', 'Петроградский'),
            ('фрунзенский', 'Фрунзенский'),
            ('выборгский', 'Выборгский'),
            ('колпинский', 'Колпинский'),
            ('курортный', 'Курортный'),
            ('московский', 'Московский'),
            ('приморский', 'Приморский'),
            ('пушкинский', 'Пушкинский'),
            ('центральный', 'Центральный'),
            ('кировский', 'Кировский'),
            ('невский', 'Невский'),
        ]

        for pattern, district in districts:
            if pattern in address_lower:
                return district

        return ''

    def _filter_by_okrug(
        self,
        results: List[Dict],
        target_okrug: str,
        fallback_metro: str = ''
    ) -> List[Dict]:
        """
        Фильтрует результаты по административному округу Москвы.
        Fallback: если округ не найден, фильтрует по метро.

        Args:
            results: Список найденных объявлений
            target_okrug: Целевой округ (ЦАО, ЮВАО и т.д.)
            fallback_metro: Метро для fallback если округ не определён

        Returns:
            Отфильтрованный список
        """
        if not results:
            return results

        filtered = []

        for r in results:
            result_address = r.get('address', '')
            result_okrug = self._extract_okrug(result_address)

            # Если есть целевой округ - фильтруем по нему
            if target_okrug:
                if result_okrug == target_okrug:
                    filtered.append(r)
                    continue

            # Fallback: если нет округа, но есть метро - фильтруем по метро
            if fallback_metro and not target_okrug:
                result_metro_raw = r.get('metro', '')
                if isinstance(result_metro_raw, list):
                    result_metro = ', '.join(result_metro_raw).lower()
                else:
                    result_metro = str(result_metro_raw).lower() if result_metro_raw else ''

                # ВАЖНО: проверяем что обе строки непустые, иначе "" in "любая" = True
                if result_metro and fallback_metro and (fallback_metro.lower() in result_metro or result_metro in fallback_metro.lower()):
                    filtered.append(r)
                    continue

        logger.info(f"   Фильтр по округу: {len(results)} -> {len(filtered)} (округ: {target_okrug or 'не определён'})")
        return filtered

    def _generate_nearby_houses(self, parsed_address: dict, radius: int = 3) -> List[str]:
        """
        Генерирует список соседних домов для поиска аналогов

        Args:
            parsed_address: Результат _parse_address()
            radius: Радиус поиска (сколько домов в каждую сторону)

        Returns:
            Список номеров домов для поиска: ["4к1", "4к2", "3", "3к1", "5", "5к1", ...]
        """
        if not parsed_address or not parsed_address.get("house"):
            return []

        try:
            base_house = int(parsed_address["house"])
        except (ValueError, TypeError):
            return []

        nearby = []

        # Генерируем соседние номера домов
        for offset in range(0, radius + 1):
            for direction in [0, 1, -1] if offset == 0 else [1, -1]:
                house_num = base_house + (offset * direction)
                if house_num <= 0:
                    continue

                # Добавляем сам дом и его корпуса
                nearby.append(str(house_num))
                for korpus in range(1, 5):  # к1, к2, к3, к4
                    nearby.append(f"{house_num}к{korpus}")
                # Также добавляем литеры для некоторых домов
                if offset <= 1:
                    for lit in ['а', 'б', 'в']:
                        nearby.append(f"{house_num}{lit}")

        # Убираем дубликаты, сохраняя порядок
        seen = set()
        unique = []
        for h in nearby:
            if h not in seen:
                seen.add(h)
                unique.append(h)

        logger.debug(f"   🏠 Сгенерировано {len(unique)} вариантов соседних домов: {unique[:10]}...")
        return unique

    def _search_by_address(self, street: str, house: str, target_property: Dict,
                           price_tolerance: float, area_tolerance: float, limit: int = 5) -> List[Dict]:
        """
        Поиск аналогов по конкретному адресу (улица + дом)

        Использует текстовый поиск ЦИАН по адресу
        """
        if not street:
            return []

        target_price = target_property.get('price', 100_000_000)
        # Ensure target_price is numeric (may come as string with currency symbols)
        if isinstance(target_price, str):
            import re
            cleaned = re.sub(r'[^\d.,]', '', target_price.replace(',', '.'))
            target_price = float(cleaned) if cleaned else 100_000_000
        target_price = float(target_price) if target_price else 100_000_000

        target_area = target_property.get('total_area', 100)
        target_rooms = target_property.get('rooms', 2)

        # Нормализуем комнаты
        target_rooms_int = self._normalize_rooms(target_rooms) or 2

        # Базовые параметры поиска
        search_params = {
            'deal_type': 'sale',
            'offer_type': 'flat',
            'engine_version': '2',
            'price_min': int(target_price * (1 - price_tolerance)),
            'price_max': int(target_price * (1 + price_tolerance)),
            'minArea': int(target_area * (1 - area_tolerance)),
            'maxArea': int(target_area * (1 + area_tolerance)),
            'region': self.region_code,
            f'room{target_rooms_int}': '1',
        }

        # Тип объекта
        is_new_building = self._is_new_building(target_property)
        search_params['type'] = '4' if is_new_building else '1'

        # Формируем поисковый запрос по адресу
        # ЦИАН поддерживает параметр 'text' для текстового поиска
        search_query = f"{street}"
        if house:
            search_query += f" {house}"

        search_params['text'] = search_query

        url = f"{self.base_url}/cat.php?" + '&'.join([f"{k}={v}" for k, v in search_params.items()])

        logger.debug(f"   Поиск по адресу: {search_query}")

        results = self.parse_search_page(url)

        # Дополнительная фильтрация - проверяем что адрес действительно содержит нужную улицу
        filtered = []
        street_lower = street.lower()
        for r in results:
            r_address = (r.get('address', '') or '').lower()
            if street_lower in r_address:
                filtered.append(r)

        return filtered[:limit]

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
            logger.info(f"   Целевой объект - НОВОСТРОЙКА, фильтруем поиск (type=4)")
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
                    logger.info(f"   Фильтр типа дома: кирпично-монолитный")
                else:
                    search_params['building_type'] = '4'  # Монолитный
                    logger.info(f"   Фильтр типа дома: монолитный")
            elif 'кирпич' in house_type:
                search_params['building_type'] = '1'  # Кирпичный
                logger.info(f"   Фильтр типа дома: кирпичный")
            elif 'панел' in house_type:
                search_params['building_type'] = '2'  # Панельный
                logger.info(f"   Фильтр типа дома: панельный")
            elif 'блочн' in house_type:
                search_params['building_type'] = '3'  # Блочный
                logger.info(f"   Фильтр типа дома: блочный")

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
        target_rooms_int = self._normalize_rooms(target_rooms) or 2  # дефолт 2 для этого метода

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

        target_address = target_property.get('address') or ''.lower().strip()

        if not target_metro and not target_address:
            logger.info("   Нет данных о локации целевого объекта, фильтрация пропущена")
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
            # ВАЖНО: проверяем что result_metro непустое, иначе "" in "любая" = True
            if strict and target_metro:
                if result_metro and (target_metro in result_metro or result_metro in target_metro):
                    filtered.append(result)
                    continue

            # FIX: Для ручного ввода (без метро) - используем адрес даже в строгом режиме
            # Это позволяет искать по улице когда метро не указано
            if strict and not target_metro and target_keywords:
                result_keywords = set()
                for word in result_address.replace(',', ' ').split():
                    word = word.strip()
                    if len(word) > 3 and word not in stop_words:
                        result_keywords.add(word)

                # Требуем совпадение минимум 1 ключевого слова (улица, район)
                if target_keywords & result_keywords:
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
        logger.info("НАЧИНАЕМ МНОГОУРОВНЕВЫЙ ПОИСК АНАЛОГОВ (ДОРАБОТКА #5)")
        logger.info("=" * 80)

        # Формируем критерии поиска
        target_price = target_property.get('price', 100_000_000)
        # Ensure target_price is numeric (may come as string with currency symbols)
        if isinstance(target_price, str):
            import re
            # Remove all non-numeric chars except dot and comma
            cleaned = re.sub(r'[^\d.,]', '', target_price.replace(',', '.'))
            target_price = float(cleaned) if cleaned else 100_000_000
        target_price = float(target_price) if target_price else 100_000_000

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

        target_address = target_property.get('address') or ''

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
            logger.info(f"УРОВЕНЬ 0: Новостройка - пробуем поиск по ЖК '{residential_complex}'")
            try:
                results_level0 = self.search_similar_in_building(target_property, limit=limit)
                if len(results_level0) >= self.MIN_RESULTS_THRESHOLD:
                    logger.info(f"   УРОВЕНЬ 0: Нашли достаточно аналогов в ЖК ({len(results_level0)} шт.)")
                    validated_level0 = self._validate_and_prepare_results(results_level0, limit, target_property=target_property)
                    final_results.extend(validated_level0)
                    logger.info(f"   УРОВЕНЬ 0 ЗАВЕРШЁН: {len(validated_level0)} аналогов из того же ЖК")
                    logger.info("=" * 80)
                    return final_results[:limit]
                else:
                    logger.warning(f"   УРОВЕНЬ 0: В ЖК найдено мало аналогов ({len(results_level0)} шт.), переходим к широкому поиску")
                    # Добавляем то что нашли, и продолжаем
                    if results_level0:
                        validated_level0 = self._validate_and_prepare_results(results_level0, limit, target_property=target_property)
                        final_results.extend(validated_level0)
                        logger.info(f"   Добавлено {len(validated_level0)} аналогов из ЖК")
            except Exception as e:
                logger.warning(f"   УРОВЕНЬ 0: Ошибка поиска по ЖК - {e}")
                logger.info(f"   → Переходим к широкому поиску")
            logger.info("")

        # ═══════════════════════════════════════════════════════════════════════════
        # УРОВЕНЬ 0.5: ПОИСК ПО УЛИЦЕ (street_url из breadcrumbs)
        # Самый точный способ найти аналоги - по geo-id улицы от ЦИАН
        # URL вида: /kupit-1-komnatnuyu-kvartiru-moskva-proizvodstvennaya-ulica-021905
        # ═══════════════════════════════════════════════════════════════════════════
        street_url = target_property.get('street_url', '')
        if street_url and len(final_results) < self.PREFERRED_RESULTS_THRESHOLD:
            logger.info(f"🏠 УРОВЕНЬ 0.5: Поиск по улице (street_url)")
            logger.info(f"   URL: {street_url[:100]}...")
            try:
                results_street = self.parse_search_page(street_url)
                logger.info(f"   Найдено объявлений на улице: {len(results_street)}")

                # НОВОЕ: Фильтруем по близости номера дома (±5 домов)
                if results_street and target_address:
                    results_street = self._filter_by_house_proximity(
                        results_street, target_address, max_distance=5
                    )
                    logger.info(f"   После фильтра по близости дома (±5): {len(results_street)}")

                if results_street:
                    # Валидируем и добавляем
                    validated_street = self._validate_and_prepare_results(
                        results_street, limit, target_property=target_property
                    )
                    # Добавляем только новые (не дубликаты)
                    existing_urls = {r.get('url') for r in final_results}
                    new_street_results = [r for r in validated_street if r.get('url') not in existing_urls]
                    final_results.extend(new_street_results)
                    logger.info(f"   УРОВЕНЬ 0.5: Добавлено {len(new_street_results)} аналогов с той же улицы (близкие дома)")

                    # Если достаточно аналогов - можно завершать
                    if len(final_results) >= self.PREFERRED_RESULTS_THRESHOLD:
                        logger.info(f"Найдено достаточно аналогов ({len(final_results)} шт.), поиск завершен")
                        logger.info("=" * 80)
                        return final_results[:limit]
            except Exception as e:
                logger.warning(f"   УРОВЕНЬ 0.5: Ошибка поиска по улице - {e}")
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
        logger.info(f"   Найдено объявлений: {len(results_level1)}")

        # ═══════════════════════════════════════════════════════════════════════════
        # КРИТИЧЕСКИЙ ФИКС БАГ #2: PROGRESSIVE FILTER RELAXATION
        # Если 0 результатов → убираем доп. фильтры (год/класс/этажи/отделка)
        # ═══════════════════════════════════════════════════════════════════════════
        if len(results_level1) == 0:
            logger.warning("Уровень 1 дал 0 результатов!")
            logger.warning("Пробуем БЕЗ фильтров (год/класс/этажи/отделка)...")

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
                logger.info(f"   Тип: НОВОСТРОЙКА (type=4)")
            else:
                search_params_relaxed['type'] = '1'
                logger.info(f"   🏠 Тип: ВТОРИЧКА (type=1)")

            # КРИТИЧНО: Комнаты (СТРОГО указанное количество)
            target_rooms_int = self._normalize_rooms(target_rooms) or 2  # дефолт 2

            search_params_relaxed[f'room{target_rooms_int}'] = '1'
            logger.info(f"   🏠 Комнаты: СТРОГО {target_rooms_int}-комнатные")

            # НЕ добавляем: deadline_from/to, class, not_first/last_floor, decoration, building_type
            url_relaxed = f"{self.base_url}/cat.php?" + '&'.join([f"{k}={v}" for k, v in search_params_relaxed.items()])
            logger.info(f"   🔄 Relaxed URL: {url_relaxed[:100]}...")

            results_level1 = self.parse_search_page(url_relaxed)
            logger.info(f"   После снятия доп. фильтров найдено: {len(results_level1)} объявлений")

        # Фильтруем по локации (строгий режим - только совпадение метро)
        if target_metro or target_address:
            filtered_level1 = self._filter_by_location(results_level1, target_property, strict=True)
            logger.info(f"   После фильтрации по локации: {len(filtered_level1)} объявлений")
        else:
            filtered_level1 = results_level1
            logger.info(f"   Фильтрация по локации пропущена (нет данных о метро/адресе)")

        # ═══════════════════════════════════════════════════════════════════════════
        # FALLBACK: Если нет street_url - дополнительно фильтруем по округу
        # Это предотвращает выдачу аналогов из разных концов Москвы
        # ═══════════════════════════════════════════════════════════════════════════
        if not street_url and str(self.region_code) == '1':  # Только для Москвы (region_code может быть str или int)
            logger.info(f"   FALLBACK: Нет street_url для Москвы, применяем фильтр по округу")

            # ВАЖНО: Если фильтр по локации вернул 0, работаем с исходными результатами
            # Это исправляет баг когда все 28 результатов имеют пустое metro поле
            fallback_source = filtered_level1 if filtered_level1 else results_level1
            if not filtered_level1 and results_level1:
                logger.info(f"   FALLBACK: Фильтр локации пустой, используем исходные {len(results_level1)} результатов")

            # Пытаемся определить округ из адреса целевого объекта
            target_okrug = self._extract_okrug(target_address)

            # Если округ не определён из адреса, пробуем определить из первых аналогов с тем же метро
            if not target_okrug and target_metro and fallback_source:
                for analog in fallback_source[:10]:  # Проверяем первые 10
                    analog_metro_raw = analog.get('metro', '')
                    if isinstance(analog_metro_raw, list):
                        analog_metro = ', '.join(analog_metro_raw).lower()
                    else:
                        analog_metro = str(analog_metro_raw).lower() if analog_metro_raw else ''

                    # КРИТИЧНО: analog_metro должен быть непустым, иначе "" in "автозаводская" = True
                    if analog_metro and (target_metro.lower() in analog_metro or analog_metro in target_metro.lower()):
                        detected_okrug = self._extract_okrug(analog.get('address', ''))
                        if detected_okrug:
                            target_okrug = detected_okrug
                            logger.info(f"   FALLBACK: Округ определён из аналога с метро '{analog_metro}': {target_okrug}")
                            break

            # ВАЖНО: Если metro пустое у всех аналогов, определяем target_okrug по метро Москвы
            if not target_okrug and target_metro:
                # Маппинг станций метро на округа Москвы (полный список)
                METRO_TO_OKRUG = {
                    # ЮАО (Южный административный округ)
                    'автозаводская': 'ЮАО', 'коломенская': 'ЮАО', 'каширская': 'ЮАО', 'кантемировская': 'ЮАО',
                    'технопарк': 'ЮАО', 'царицыно': 'ЮАО', 'орехово': 'ЮАО', 'домодедовская': 'ЮАО',
                    'красногвардейская': 'ЮАО', 'алма-атинская': 'ЮАО', 'зябликово': 'ЮАО', 'шипиловская': 'ЮАО',
                    'борисово': 'ЮАО', 'марьино': 'ЮАО', 'братиславская': 'ЮАО',
                    'волжская': 'ЮАО', 'печатники': 'ЮАО', 'текстильщики': 'ЮАО', 'нагатинская': 'ЮАО',
                    'нагорная': 'ЮАО', 'нахимовский проспект': 'ЮАО', 'варшавская': 'ЮАО', 'каховская': 'ЮАО',
                    'южная': 'ЮАО', 'пражская': 'ЮАО', 'чертановская': 'ЮАО', 'севастопольская': 'ЮАО',
                    'аннино': 'ЮАО', 'бульвар дмитрия донского': 'ЮАО', 'улица академика янгеля': 'ЮАО',
                    # ЮВАО (Юго-Восточный административный округ)
                    'кузьминки': 'ЮВАО', 'рязанский проспект': 'ЮВАО', 'выхино': 'ЮВАО', 'лермонтовский проспект': 'ЮВАО',
                    'жулебино': 'ЮВАО', 'котельники': 'ЮВАО', 'дубровка': 'ЮВАО', 'кожуховская': 'ЮВАО',
                    'авиамоторная': 'ЮВАО', 'окская': 'ЮВАО', 'стахановская': 'ЮВАО', 'некрасовка': 'ЮВАО',
                    'косино': 'ЮВАО', 'улица дмитриевского': 'ЮВАО', 'лухмановская': 'ЮВАО', 'юго-восточная': 'ЮВАО', 'люблино': 'ЮВАО',
                    # ЦАО (Центральный административный округ)
                    'охотный ряд': 'ЦАО', 'театральная': 'ЦАО', 'площадь революции': 'ЦАО', 'кузнецкий мост': 'ЦАО',
                    'лубянка': 'ЦАО', 'чистые пруды': 'ЦАО', 'красные ворота': 'ЦАО', 'китай-город': 'ЦАО',
                    'тверская': 'ЦАО', 'пушкинская': 'ЦАО', 'чеховская': 'ЦАО', 'цветной бульвар': 'ЦАО',
                    'арбатская': 'ЦАО', 'смоленская': 'ЦАО', 'кропоткинская': 'ЦАО', 'боровицкая': 'ЦАО',
                    'библиотека имени ленина': 'ЦАО', 'александровский сад': 'ЦАО', 'новокузнецкая': 'ЦАО',
                    'третьяковская': 'ЦАО', 'полянка': 'ЦАО', 'серпуховская': 'ЦАО', 'добрынинская': 'ЦАО',
                    'октябрьская': 'ЦАО', 'павелецкая': 'ЦАО', 'таганская': 'ЦАО', 'курская': 'ЦАО',
                    'комсомольская': 'ЦАО', 'маяковская': 'ЦАО', 'белорусская': 'ЦАО', 'менделеевская': 'ЦАО',
                    'новослободская': 'ЦАО', 'сухаревская': 'ЦАО', 'тургеневская': 'ЦАО', 'сретенский бульвар': 'ЦАО',
                    'трубная': 'ЦАО', 'марксистская': 'ЦАО', 'площадь ильича': 'ЦАО', 'римская': 'ЦАО',
                    'парк культуры': 'ЦАО', 'фрунзенская': 'ЦАО', 'краснопресненская': 'ЦАО', 'баррикадная': 'ЦАО',
                    # САО (Северный административный округ)
                    'речной вокзал': 'САО', 'водный стадион': 'САО', 'войковская': 'САО', 'сокол': 'САО',
                    'аэропорт': 'САО', 'динамо': 'САО', 'петровско-разумовская': 'САО', 'тимирязевская': 'САО',
                    'дмитровская': 'САО', 'савёловская': 'САО', 'ховрино': 'САО', 'беломорская': 'САО',
                    'селигерская': 'САО', 'верхние лихоборы': 'САО', 'окружная': 'САО', 'коптево': 'САО',
                    'лихоборы': 'САО', 'балтийская': 'САО', 'стрешнево': 'САО', 'беговая': 'САО',
                    # СВАО (Северо-Восточный административный округ)
                    'медведково': 'СВАО', 'бабушкинская': 'СВАО', 'свиблово': 'СВАО', 'ботанический сад': 'СВАО',
                    'вднх': 'СВАО', 'алексеевская': 'СВАО', 'рижская': 'СВАО', 'проспект мира': 'СВАО',
                    'алтуфьево': 'СВАО', 'бибирево': 'СВАО', 'отрадное': 'СВАО', 'владыкино': 'СВАО',
                    'марьина роща': 'СВАО', 'бутырская': 'СВАО', 'фонвизинская': 'СВАО', 'петровский парк': 'СВАО',
                    'достоевская': 'СВАО', 'ростокино': 'СВАО', 'белокаменная': 'СВАО',
                    # ВАО (Восточный административный округ)
                    'щёлковская': 'ВАО', 'первомайская': 'ВАО', 'измайловская': 'ВАО', 'партизанская': 'ВАО',
                    'семёновская': 'ВАО', 'электрозаводская': 'ВАО', 'бауманская': 'ВАО', 'преображенская площадь': 'ВАО',
                    'сокольники': 'ВАО', 'красносельская': 'ВАО', 'черкизовская': 'ВАО', 'бульвар рокоссовского': 'ВАО',
                    'локомотив': 'ВАО', 'измайлово': 'ВАО', 'соколиная гора': 'ВАО', 'шоссе энтузиастов': 'ВАО',
                    'перово': 'ВАО', 'новогиреево': 'ВАО', 'новокосино': 'ВАО',
                    # ЮЗАО (Юго-Западный административный округ)
                    'калужская': 'ЮЗАО', 'беляево': 'ЮЗАО', 'коньково': 'ЮЗАО', 'тёплый стан': 'ЮЗАО',
                    'ясенево': 'ЮЗАО', 'новоясеневская': 'ЮЗАО', 'битцевский парк': 'ЮЗАО', 'профсоюзная': 'ЮЗАО',
                    'академическая': 'ЮЗАО', 'университет': 'ЮЗАО', 'проспект вернадского': 'ЮЗАО',
                    'юго-западная': 'ЮЗАО', 'тропарёво': 'ЮЗАО', 'румянцево': 'ЮЗАО', 'саларьево': 'ЮЗАО',
                    'воробьёвы горы': 'ЮЗАО', 'спортивная': 'ЮЗАО', 'ленинский проспект': 'ЮЗАО',
                    'шаболовская': 'ЮЗАО', 'крымская': 'ЮЗАО', 'воронцовская': 'ЮЗАО', 'зюзино': 'ЮЗАО',
                    # ЗАО (Западный административный округ)
                    'киевская': 'ЗАО', 'студенческая': 'ЗАО', 'кутузовская': 'ЗАО', 'фили': 'ЗАО',
                    'багратионовская': 'ЗАО', 'филёвский парк': 'ЗАО', 'пионерская': 'ЗАО', 'кунцевская': 'ЗАО',
                    'молодёжная': 'ЗАО', 'крылатское': 'ЗАО', 'мякинино': 'ЗАО',
                    'парк победы': 'ЗАО', 'славянский бульвар': 'ЗАО', 'минская': 'ЗАО', 'ломоносовский проспект': 'ЗАО',
                    'раменки': 'ЗАО', 'мичуринский проспект': 'ЗАО', 'озёрная': 'ЗАО', 'говорово': 'ЗАО',
                    'солнцево': 'ЗАО', 'боровское шоссе': 'ЗАО', 'новопеределкино': 'ЗАО', 'рассказовка': 'ЗАО',
                    'очаково': 'ЗАО', 'давыдково': 'ЗАО', 'аминьевская': 'ЗАО',
                    # СЗАО (Северо-Западный административный округ)
                    'тушинская': 'СЗАО', 'сходненская': 'СЗАО', 'планерная': 'СЗАО', 'спартак': 'СЗАО',
                    'щукинская': 'СЗАО', 'октябрьское поле': 'СЗАО', 'полежаевская': 'СЗАО', 'митино': 'СЗАО',
                    'волоколамская': 'СЗАО', 'мневники': 'СЗАО', 'народное ополчение': 'СЗАО',
                    'хорошёво': 'СЗАО', 'хорошёвская': 'СЗАО', 'зорге': 'СЗАО', 'панфиловская': 'СЗАО',
                    'пятницкое шоссе': 'СЗАО', 'строгино': 'СЗАО',
                    # НАО (Новомосковский административный округ)
                    'филатов луг': 'НАО', 'прокшино': 'НАО', 'ольховая': 'НАО', 'коммунарка': 'НАО',
                    'столбово': 'НАО', 'потапово': 'НАО',
                }
                metro_lower = target_metro.lower().strip()
                if metro_lower in METRO_TO_OKRUG:
                    target_okrug = METRO_TO_OKRUG[metro_lower]
                    logger.info(f"   FALLBACK: Округ определён по станции метро '{target_metro}': {target_okrug}")

            if target_okrug:
                logger.info(f"   FALLBACK: Фильтрация по округу {target_okrug}")
                filtered_level1 = self._filter_by_okrug(fallback_source, target_okrug, fallback_metro=target_metro)
                logger.info(f"   FALLBACK: После фильтрации по округу: {len(filtered_level1)} объявлений")
            elif target_metro:
                logger.info(f"   FALLBACK: Округ не определён, фильтрация по метро {target_metro}")
                # Усиленная фильтрация по метро когда нет округа
                strict_metro_filtered = []
                for r in fallback_source:
                    result_metro_raw = r.get('metro', '')
                    if isinstance(result_metro_raw, list):
                        result_metro = ', '.join(result_metro_raw).lower()
                    else:
                        result_metro = str(result_metro_raw).lower() if result_metro_raw else ''

                    # КРИТИЧНО: result_metro должен быть непустым, иначе "" in "любая" = True
                    if result_metro and (target_metro.lower() in result_metro or result_metro in target_metro.lower()):
                        strict_metro_filtered.append(r)
                logger.info(f"   FALLBACK: После строгой фильтрации по метро: {len(strict_metro_filtered)} объявлений")
                if len(strict_metro_filtered) == 0:
                    logger.warning(f"   FALLBACK: Фильтрация по метро дала 0 результатов, пропускаем")
                else:
                    filtered_level1 = strict_metro_filtered
            else:
                logger.info(f"   FALLBACK: target_metro пустой, пропускаем фильтрацию")

        # ═══════════════════════════════════════════════════════════════════════════
        # FALLBACK для СПб: Если нет street_url - фильтруем по району
        # Аналогично московскому fallback, но с районами вместо округов
        # ═══════════════════════════════════════════════════════════════════════════
        elif not street_url and str(self.region_code) == '2':  # Санкт-Петербург
            logger.info(f"   FALLBACK: Нет street_url для СПб, применяем фильтр по району")

            fallback_source = filtered_level1 if filtered_level1 else results_level1
            if not filtered_level1 and results_level1:
                logger.info(f"   FALLBACK: Фильтр локации пустой, используем исходные {len(results_level1)} результатов")

            # Пытаемся определить район из адреса целевого объекта
            target_district = self._extract_district_spb(target_address)

            # Если район не определён из адреса, пробуем определить из аналогов с тем же метро
            if not target_district and target_metro and fallback_source:
                for analog in fallback_source[:10]:
                    analog_metro_raw = analog.get('metro', '')
                    if isinstance(analog_metro_raw, list):
                        analog_metro = ', '.join(analog_metro_raw).lower()
                    else:
                        analog_metro = str(analog_metro_raw).lower() if analog_metro_raw else ''

                    if analog_metro and (target_metro.lower() in analog_metro or analog_metro in target_metro.lower()):
                        detected_district = self._extract_district_spb(analog.get('address', ''))
                        if detected_district:
                            target_district = detected_district
                            logger.info(f"   FALLBACK: Район определён из аналога с метро '{analog_metro}': {target_district}")
                            break

            # Если район не определён, пробуем по метро СПб
            if not target_district and target_metro:
                # Маппинг станций метро СПб на районы (5 линий, ~72 станции)
                METRO_TO_DISTRICT_SPB = {
                    # Линия 1 (Кировско-Выборгская, красная)
                    'девяткино': 'Выборгский', 'гражданский проспект': 'Калининский',
                    'академическая': 'Калининский', 'политехническая': 'Калининский',
                    'площадь мужества': 'Калининский', 'лесная': 'Выборгский',
                    'выборгская': 'Выборгский', 'площадь ленина': 'Калининский',
                    'чернышевская': 'Центральный', 'площадь восстания': 'Центральный',
                    'владимирская': 'Центральный', 'пушкинская': 'Центральный',
                    'технологический институт': 'Адмиралтейский', 'балтийская': 'Адмиралтейский',
                    'нарвская': 'Кировский', 'кировский завод': 'Кировский',
                    'автово': 'Кировский', 'ленинский проспект': 'Красносельский',
                    'проспект ветеранов': 'Кировский',
                    # Линия 2 (Московско-Петроградская, синяя)
                    'парнас': 'Выборгский', 'проспект просвещения': 'Выборгский',
                    'озерки': 'Выборгский', 'удельная': 'Выборгский',
                    'пионерская': 'Приморский', 'чёрная речка': 'Приморский',
                    'черная речка': 'Приморский',  # альтернативное написание
                    'петроградская': 'Петроградский', 'горьковская': 'Петроградский',
                    'невский проспект': 'Центральный', 'сенная площадь': 'Адмиралтейский',
                    'фрунзенская': 'Адмиралтейский', 'московские ворота': 'Московский',
                    'электросила': 'Московский', 'парк победы': 'Московский',
                    'московская': 'Московский', 'звёздная': 'Московский',
                    'звездная': 'Московский',  # альтернативное написание
                    'купчино': 'Фрунзенский',
                    # Линия 3 (Невско-Василеостровская, зелёная)
                    'беговая': 'Приморский', 'новокрестовская': 'Приморский',
                    'зенит': 'Приморский',  # новое название Новокрестовской
                    'приморская': 'Василеостровский', 'василеостровская': 'Василеостровский',
                    'гостиный двор': 'Центральный', 'маяковская': 'Центральный',
                    'площадь александра невского': 'Центральный',
                    'елизаровская': 'Невский', 'ломоносовская': 'Невский',
                    'пролетарская': 'Невский', 'обухово': 'Невский', 'рыбацкое': 'Невский',
                    # Линия 4 (Правобережная, оранжевая)
                    'спасская': 'Адмиралтейский', 'достоевская': 'Центральный',
                    'лиговский проспект': 'Центральный', 'новочеркасская': 'Красногвардейский',
                    'ладожская': 'Красногвардейский', 'проспект большевиков': 'Невский',
                    'улица дыбенко': 'Невский',
                    # Линия 5 (Фрунзенско-Приморская, фиолетовая)
                    'комендантский проспект': 'Приморский', 'старая деревня': 'Приморский',
                    'крестовский остров': 'Петроградский', 'чкаловская': 'Петроградский',
                    'спортивная': 'Петроградский', 'адмиралтейская': 'Адмиралтейский',
                    'садовая': 'Адмиралтейский', 'звенигородская': 'Адмиралтейский',
                    'обводный канал': 'Фрунзенский', 'волковская': 'Фрунзенский',
                    'бухарестская': 'Фрунзенский', 'международная': 'Фрунзенский',
                    'проспект славы': 'Фрунзенский', 'дунайская': 'Фрунзенский',
                    'шушары': 'Пушкинский',
                    # Будущие станции и альтернативные названия
                    'театральная': 'Центральный',  # строится
                    'горный институт': 'Василеостровский',  # строится
                }
                metro_lower = target_metro.lower().strip()
                if metro_lower in METRO_TO_DISTRICT_SPB:
                    target_district = METRO_TO_DISTRICT_SPB[metro_lower]
                    logger.info(f"   FALLBACK: Район определён по станции метро '{target_metro}': {target_district}")

            if target_district:
                logger.info(f"   FALLBACK: Фильтрация по району {target_district}")
                # Используем _filter_by_district_spb для СПб
                filtered_by_district = []
                for r in fallback_source:
                    result_district = self._extract_district_spb(r.get('address', ''))
                    if result_district == target_district:
                        filtered_by_district.append(r)
                logger.info(f"   FALLBACK: После фильтрации по району: {len(filtered_by_district)} объявлений")
                if filtered_by_district:
                    filtered_level1 = filtered_by_district
            elif target_metro:
                logger.info(f"   FALLBACK: Район не определён, фильтрация по метро {target_metro}")
                strict_metro_filtered = []
                for r in fallback_source:
                    result_metro_raw = r.get('metro', '')
                    if isinstance(result_metro_raw, list):
                        result_metro = ', '.join(result_metro_raw).lower()
                    else:
                        result_metro = str(result_metro_raw).lower() if result_metro_raw else ''

                    if result_metro and (target_metro.lower() in result_metro or result_metro in target_metro.lower()):
                        strict_metro_filtered.append(r)
                logger.info(f"   FALLBACK: После строгой фильтрации по метро: {len(strict_metro_filtered)} объявлений")
                if strict_metro_filtered:
                    filtered_level1 = strict_metro_filtered
            else:
                logger.info(f"   FALLBACK: target_metro пустой, пропускаем фильтрацию")

        # Валидация и добавление
        validated_level1 = self._validate_and_prepare_results(filtered_level1, limit, target_property=target_property)
        final_results.extend(validated_level1)
        logger.info(f"   УРОВЕНЬ 1: Добавлено {len(validated_level1)} валидных аналогов")
        logger.info("")

        # Проверяем, достаточно ли аналогов
        if len(final_results) >= self.PREFERRED_RESULTS_THRESHOLD:
            logger.info(f"Найдено достаточно аналогов ({len(final_results)} шт.), поиск завершен")
            logger.info("=" * 80)
            return final_results[:limit]

        # ═══════════════════════════════════════════════════════════════════════════
        # УРОВЕНЬ 1.5: ПОИСК ПО СОСЕДНИМ ДОМАМ/КОРПУСАМ
        # Для вторички: соседние дома (4 → 3, 5, 4к1...)
        # Для новостроек: соседние корпуса ЖК (9Ак3 → 9Ак1, 9Ак2, 9Б...)
        # ═══════════════════════════════════════════════════════════════════════════
        new_results_level15 = []
        if target_address:  # Убрано ограничение "not is_new_building"
            search_type = "корпусам" if is_new_building else "домам"
            logger.info(f"🏠 УРОВЕНЬ 1.5: Поиск по соседним {search_type}")
            logger.info(f"   (текущее количество: {len(final_results)}, нужно минимум 10)")

            parsed_addr = self._parse_address(target_address)
            if parsed_addr.get('street'):
                nearby_houses = self._generate_nearby_houses(parsed_addr, radius=2)  # Уменьшено с 5 до 2 для меньшего кол-ва запросов
                logger.info(f"   📍 Улица: {parsed_addr.get('street')}, дом: {parsed_addr.get('house')}{parsed_addr.get('building', '')}")
                logger.info(f"   Проверяем {len(nearby_houses)} вариантов соседних домов...")

                existing_urls = {r.get('url') for r in final_results}
                houses_checked = 0
                houses_with_results = 0

                for house_variant in nearby_houses:
                    # Прерываем если уже достаточно аналогов
                    if len(final_results) + len(new_results_level15) >= self.PREFERRED_RESULTS_THRESHOLD:
                        logger.info(f"   Достаточно аналогов, прерываем поиск по домам")
                        break

                    # Ищем по конкретному адресу
                    results_house = self._search_by_address(
                        parsed_addr['street'], house_variant, target_property,
                        price_tolerance, area_tolerance, limit=3
                    )
                    houses_checked += 1

                    if results_house:
                        houses_with_results += 1
                        # Валидируем и добавляем только новые
                        validated_house = self._validate_and_prepare_results(
                            results_house, limit=3, target_property=target_property
                        )
                        for r in validated_house:
                            if r.get('url') not in existing_urls:
                                new_results_level15.append(r)
                                existing_urls.add(r.get('url'))

                final_results.extend(new_results_level15)
                logger.info(f"   УРОВЕНЬ 1.5: Проверено {houses_checked} домов, найдено в {houses_with_results}")
                logger.info(f"   УРОВЕНЬ 1.5: Добавлено {len(new_results_level15)} новых аналогов из соседних домов")
                logger.info("")
            else:
                logger.info(f"   Не удалось распарсить адрес: {target_address}")
                logger.info("")

        # Проверяем после уровня 1.5
        if len(final_results) >= self.PREFERRED_RESULTS_THRESHOLD:
            logger.info(f"Найдено достаточно аналогов ({len(final_results)} шт.), поиск завершен")
            logger.info("=" * 80)
            return final_results[:limit]

        # ═══════════════════════════════════════════════════════════════════════════
        # УРОВЕНЬ 1.6: ПОИСК ПО СОСЕДНИМ СТАНЦИЯМ МЕТРО
        # Расширяем географию на 1-2 станции по ветке метро
        # ═══════════════════════════════════════════════════════════════════════════
        new_results_level16 = []
        if target_metro and self.region in ('msk', 'spb'):  # Москва и СПб
            nearby_metros = self._get_nearby_metros(target_metro, self.region)

            if len(nearby_metros) > 1:  # Есть соседние станции
                logger.info(f"🚇 УРОВЕНЬ 1.6: Поиск по соседним станциям метро")
                logger.info(f"   (текущее количество: {len(final_results)}, нужно минимум 10)")
                logger.info(f"   📍 Исходная станция: {target_metro}")
                logger.info(f"   🔄 Соседние станции: {', '.join(nearby_metros[1:])}")

                existing_urls = {r.get('url') for r in final_results}

                for metro_station in nearby_metros[1:]:  # Пропускаем исходную станцию
                    # Прерываем если достаточно аналогов
                    if len(final_results) + len(new_results_level16) >= self.PREFERRED_RESULTS_THRESHOLD:
                        logger.info(f"   Достаточно аналогов, прерываем поиск по метро")
                        break

                    # Фильтруем уже найденные по этой станции
                    metro_results = []
                    for r in results_level1:  # Используем результаты Level 1 (весь город)
                        result_metro = r.get('metro', '').lower() if r.get('metro') else ''
                        # КРИТИЧНО: оба должны быть непустыми, иначе "" in "любая" = True
                        if result_metro and metro_station and metro_station in result_metro and r.get('url') not in existing_urls:
                            metro_results.append(r)

                    if metro_results:
                        validated_metro = self._validate_and_prepare_results(
                            metro_results[:5], limit=5, target_property=target_property
                        )
                        for r in validated_metro:
                            if r.get('url') not in existing_urls:
                                new_results_level16.append(r)
                                existing_urls.add(r.get('url'))

                final_results.extend(new_results_level16)
                logger.info(f"   УРОВЕНЬ 1.6: Добавлено {len(new_results_level16)} аналогов с соседних станций")
                logger.info("")

        # Проверяем после уровня 1.6 - используем MIN_LOCAL_FOR_STOP вместо расширения на город
        if len(final_results) >= self.MIN_LOCAL_FOR_STOP:
            logger.info(f"Найдено {len(final_results)} близких аналогов (порог: {self.MIN_LOCAL_FOR_STOP}), поиск завершен БЕЗ расширения на город")
            logger.info("=" * 80)
            return final_results[:limit]
        else:
            logger.warning(f"Найдено только {len(final_results)} аналогов (порог: {self.MIN_LOCAL_FOR_STOP})")
            logger.warning(f"Уровни 2-4 (расширение на город) отключены для приоритета близких аналогов")
            logger.info("=" * 80)
            return final_results[:limit]

        # ═══════════════════════════════════════════════════════════════════════════
        # УРОВНИ 2-4 ЗАКОММЕНТИРОВАНЫ: Приоритет близких аналогов вместо расширения на весь город
        # Раскомментировать при необходимости расширенного поиска
        # ═══════════════════════════════════════════════════════════════════════════

        '''
        # ═══════════════════════════════════════════════════════════════════════════
        # УРОВЕНЬ 2: РЕАЛЬНЫЙ поиск по всему городу (новый запрос без фильтра локации)
        # ИСПРАВЛЕНО: Теперь делаем новый запрос к ЦИАН, а не переиспользуем результаты уровня 1
        # ═══════════════════════════════════════════════════════════════════════════
        logger.info(f"🌆 УРОВЕНЬ 2: Расширяем поиск на весь город (НОВЫЙ запрос)")
        logger.info(f"   (текущее количество: {len(final_results)}, нужно минимум 10)")

        # Строим URL БЕЗ дополнительных фильтров (год, класс, этажи, отделка)
        search_params_city = {
            'deal_type': 'sale',
            'offer_type': 'flat',
            'engine_version': '2',
            'price_min': int(target_price * (1 - price_tolerance)),
            'price_max': int(target_price * (1 + price_tolerance)),
            'minArea': int(target_area * (1 - area_tolerance)),
            'maxArea': int(target_area * (1 + area_tolerance)),
            'region': self.region_code,
        }

        # Тип объекта
        if is_new_building:
            search_params_city['type'] = '4'
        else:
            search_params_city['type'] = '1'

        # Комнаты (ОСЛАБЛЕННЫЙ фильтр ±1 комната для расширения поиска)
        target_rooms_int = self._normalize_rooms(target_rooms) or 2
        room_params = self._get_room_filter_params(target_rooms_int, strict=False)
        search_params_city.update(room_params)
        room_range = ', '.join([k.replace('room', '') for k in room_params.keys()])
        logger.info(f"   🏠 Фильтр комнат: {room_range}-комнатные (±1 для расширения)")

        url_level2 = f"{self.base_url}/cat.php?" + '&'.join([f"{k}={v}" for k, v in search_params_city.items()])
        logger.info(f"   URL: {url_level2[:100]}...")

        results_level2 = self.parse_search_page(url_level2)
        logger.info(f"   Найдено объявлений: {len(results_level2)}")

        # Валидируем БЕЗ фильтра локации
        validated_level2 = self._validate_and_prepare_results(results_level2, limit, target_property=target_property)

        # Добавляем только новые (которых нет в final_results)
        existing_urls = {r.get('url') for r in final_results}
        new_results_level2 = [r for r in validated_level2 if r.get('url') not in existing_urls]

        final_results.extend(new_results_level2)
        logger.info(f"   УРОВЕНЬ 2: Добавлено {len(new_results_level2)} новых аналогов из города")
        logger.info("")

        # Проверяем снова
        if len(final_results) >= 5:
            logger.info(f"Найдено достаточно аналогов ({len(final_results)} шт.), поиск завершен")
            logger.info("=" * 80)
            return final_results[:limit]

        # ═══════════════════════════════════════════════════════════════════════════
        # УРОВЕНЬ 3: Сверхрасширенный поиск (допуски +50% + ослабленный фильтр комнат)
        # ═══════════════════════════════════════════════════════════════════════════
        logger.info(f"УРОВЕНЬ 3: Расширяем диапазоны поиска (+50% к допускам, ±1 комната)")
        logger.info(f"   (текущее количество: {len(final_results)}, нужно минимум 5)")

        expanded_price_tolerance = price_tolerance * 1.5
        expanded_area_tolerance = area_tolerance * 1.5

        logger.info(f"   Новые допуски: цена ±{expanded_price_tolerance*100:.0f}%, площадь ±{expanded_area_tolerance*100:.0f}%")
        logger.info(f"   Диапазон цен: {int(target_price * (1-expanded_price_tolerance)):,} - {int(target_price * (1+expanded_price_tolerance)):,} ₽")
        logger.info(f"   Диапазон площади: {int(target_area * (1-expanded_area_tolerance))} - {int(target_area * (1+expanded_area_tolerance))} м²")

        # Строим URL с расширенными допусками и ослабленным фильтром комнат
        search_params_level3 = {
            'deal_type': 'sale',
            'offer_type': 'flat',
            'engine_version': '2',
            'price_min': int(target_price * (1 - expanded_price_tolerance)),
            'price_max': int(target_price * (1 + expanded_price_tolerance)),
            'minArea': int(target_area * (1 - expanded_area_tolerance)),
            'maxArea': int(target_area * (1 + expanded_area_tolerance)),
            'region': self.region_code,
        }

        # Тип объекта
        if is_new_building:
            search_params_level3['type'] = '4'
        else:
            search_params_level3['type'] = '1'

        # Комнаты (ОСЛАБЛЕННЫЙ фильтр ±1 комната)
        target_rooms_int = self._normalize_rooms(target_rooms) or 2
        room_params = self._get_room_filter_params(target_rooms_int, strict=False)
        search_params_level3.update(room_params)
        room_range = ', '.join([k.replace('room', '') for k in room_params.keys()])
        logger.info(f"   🏠 Фильтр комнат: {room_range}-комнатные (±1 для расширения)")

        url_level3 = f"{self.base_url}/cat.php?" + '&'.join([f"{k}={v}" for k, v in search_params_level3.items()])
        logger.info(f"   URL: {url_level3[:100]}...")

        results_level3 = self.parse_search_page(url_level3)
        logger.info(f"   Найдено объявлений: {len(results_level3)}")

        validated_level3 = self._validate_and_prepare_results(results_level3, limit, target_property=target_property)

        # Добавляем только новые
        existing_urls = {r.get('url') for r in final_results}
        new_results_level3 = [r for r in validated_level3 if r.get('url') not in existing_urls]

        final_results.extend(new_results_level3)
        logger.info(f"   УРОВЕНЬ 3: Добавлено {len(new_results_level3)} новых аналогов")
        logger.info("")

        # Проверяем снова
        if len(final_results) >= 5:
            logger.info(f"Найдено достаточно аналогов ({len(final_results)} шт.), поиск завершен")
            logger.info("=" * 80)
            return final_results[:limit]

        # ═══════════════════════════════════════════════════════════════════════════
        # УРОВЕНЬ 4: FALLBACK ДЛЯ ВСЕХ СЕГМЕНТОВ (максимально широкий поиск)
        # ИСПРАВЛЕНО: Теперь работает для ВСЕХ ценовых сегментов, не только премиум
        # ═══════════════════════════════════════════════════════════════════════════
        logger.info(f"🆘 УРОВЕНЬ 4: FALLBACK - максимально широкий поиск")
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

        # Комнаты (ОСЛАБЛЕННЫЙ фильтр ±1 комната для максимального охвата)
        target_rooms_int = self._normalize_rooms(target_rooms) or 2  # дефолт 2
        room_params = self._get_room_filter_params(target_rooms_int, strict=False)
        search_params_fallback.update(room_params)
        room_range = ', '.join([k.replace('room', '') for k in room_params.keys()])
        logger.info(f"   🏠 Фильтр комнат: {room_range}-комнатные (±1 для максимального охвата)")

        url_fallback = f"{self.base_url}/cat.php?" + '&'.join([f"{k}={v}" for k, v in search_params_fallback.items()])
        logger.info(f"   URL: {url_fallback[:100]}...")

        results_fallback = self.parse_search_page(url_fallback)
        logger.info(f"   Найдено объявлений: {len(results_fallback)}")

        # Фильтруем по локации (нестрогий режим)
        if target_metro or target_address:
            filtered_fallback = self._filter_by_location(results_fallback, target_property, strict=False)
            logger.info(f"   После фильтрации по локации (нестрогий режим): {len(filtered_fallback)} объявлений")
        else:
            filtered_fallback = results_fallback

        validated_fallback = self._validate_and_prepare_results(filtered_fallback, limit, target_property=target_property)

        # Добавляем только новые
        existing_urls = {r.get('url') for r in final_results}
        new_results_fallback = [r for r in validated_fallback if r.get('url') not in existing_urls]

        final_results.extend(new_results_fallback)
        logger.info(f"   УРОВЕНЬ 4 (FALLBACK): Добавлено {len(new_results_fallback)} новых аналогов")
        logger.info("")

        # ═══════════════════════════════════════════════════════════════════════════
        # НОВОЕ: Приоритизация аналогов из того же ЖК
        # ═══════════════════════════════════════════════════════════════════════════
        target_rc = target_property.get('residential_complex', '').lower().strip()
        if target_rc and len(final_results) > 0:
            # Захватываем target_price и target_area для использования в замыкании
            _target_price = target_price
            _target_area = target_area

            def sort_key(result: Dict) -> tuple[bool, float]:
                """
                Ключ сортировки: сначала аналоги из того же ЖК, затем по близости цены/м²

                Returns:
                    tuple: (not same_rc, price_diff) для сортировки
                """
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
                logger.info(f"Приоритизация: {same_rc_count} аналогов из того же ЖК '{target_property.get('residential_complex')}' выше в списке")

        # Итоговый результат (фильтрация по региону уже выполнена в _validate_and_prepare_results)
        logger.info("=" * 80)
        logger.info(f"🏁 ПОИСК ЗАВЕРШЕН: Найдено {len(final_results)} аналогов")
        logger.info(f"   - Уровень 1 (район/метро): {len(validated_level1)} шт.")
        if new_results_level15:
            logger.info(f"   - Уровень 1.5 (соседние дома): +{len(new_results_level15)} шт.")
        logger.info(f"   - Уровень 2 (город): +{len(new_results_level2)} шт.")
        logger.info(f"   - Уровень 3 (расширенный): +{len(new_results_level3)} шт.")
        if 'new_results_fallback' in locals():
            logger.info(f"   - Уровень 4 (fallback): +{len(new_results_fallback)} шт.")

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
                    logger.warning(f"ВНИМАНИЕ: Разброс цен {spread:.0f}% превышает 50%!")
                    logger.warning(f"   Рекомендуется ручная проверка аналогов")
                elif spread > 30:
                    logger.warning(f"Разброс цен {spread:.0f}% умеренно высокий")
                else:
                    logger.info(f"Разброс цен {spread:.0f}% в допустимых пределах")

        logger.info("=" * 80)
        '''
        # КОНЕЦ ЗАКОММЕНТИРОВАННЫХ УРОВНЕЙ 2-4

        return final_results[:limit]
