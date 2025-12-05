"""
Конфигурация регионов для парсинга недвижимости

Единый источник истины для маппинга регионов.
Используется парсерами, аналитикой и API.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class RegionConfig:
    """Конфигурация региона"""
    code: str                    # Внутренний код (spb, msk)
    name: str                    # Человекочитаемое название
    subdomains: List[str]        # Поддомены ЦИАН для этого региона
    cian_subdomain: str          # Основной поддомен ЦИАН
    metro_available: bool = True  # Есть ли метро


# Конфигурация всех поддерживаемых регионов
REGIONS: Dict[str, RegionConfig] = {
    'spb': RegionConfig(
        code='spb',
        name='Санкт-Петербург',
        subdomains=['spb', 'piter', 'saint-petersburg', 'petersburg', 'санкт-петербург'],
        cian_subdomain='spb.cian.ru',
        metro_available=True
    ),
    'msk': RegionConfig(
        code='msk',
        name='Москва',
        subdomains=['msk', 'moskva', 'moscow', 'москва', ''],  # '' - дефолт www.cian.ru
        cian_subdomain='www.cian.ru',
        metro_available=True
    ),
}

# Маппинг поддоменов на коды регионов (для быстрого поиска)
_SUBDOMAIN_TO_REGION: Dict[str, str] = {}
for region_code, config in REGIONS.items():
    for subdomain in config.subdomains:
        _SUBDOMAIN_TO_REGION[subdomain.lower()] = region_code


def detect_region_from_url(url: str) -> Optional[str]:
    """
    Определить регион по URL

    Args:
        url: URL объявления (например, https://spb.cian.ru/sale/flat/123/)

    Returns:
        Код региона (spb, msk) или None если не определён
    """
    if not url:
        return None

    url_lower = url.lower()

    # Проверяем поддомены
    for subdomain, region_code in _SUBDOMAIN_TO_REGION.items():
        if subdomain and f'{subdomain}.' in url_lower:
            return region_code

    # www.cian.ru или cian.ru без поддомена = Москва
    if 'cian.ru' in url_lower:
        return 'msk'

    return None


def detect_region_from_address(address: str) -> str:
    """
    Определить регион по адресу

    Args:
        address: Адрес объекта

    Returns:
        Код региона (по умолчанию 'msk')
    """
    if not address:
        return 'msk'

    address_lower = address.lower()

    # Ключевые слова для СПб
    spb_keywords = [
        'санкт-петербург', 'спб', 'петербург', 'питер',
        'ленинградская обл', 'лен. обл', 'ло,'
    ]

    for keyword in spb_keywords:
        if keyword in address_lower:
            return 'spb'

    return 'msk'


def get_region_config(region_code: str) -> Optional[RegionConfig]:
    """
    Получить конфигурацию региона

    Args:
        region_code: Код региона (spb, msk)

    Returns:
        RegionConfig или None
    """
    return REGIONS.get(region_code)


def get_cian_base_url(region_code: str) -> str:
    """
    Получить базовый URL ЦИАН для региона

    Args:
        region_code: Код региона

    Returns:
        Базовый URL (например, https://spb.cian.ru)
    """
    config = REGIONS.get(region_code)
    if config:
        return f"https://{config.cian_subdomain}"
    return "https://www.cian.ru"  # fallback


def get_all_region_codes() -> List[str]:
    """Получить список всех кодов регионов"""
    return list(REGIONS.keys())


def is_valid_region(region_code: str) -> bool:
    """Проверить валидность кода региона"""
    return region_code in REGIONS
