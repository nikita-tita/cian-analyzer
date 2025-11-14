"""
Стратегии парсинга

Этот пакет содержит различные имплементации стратегий парсинга:
- API-first (curl_cffi, httpx)
- Browser-light (Playwright + Stealth)
- Browser-heavy (Nodriver)
- Proxy rotation
"""

from .curl_cffi_strategy import CurlCffiStrategy
from .httpx_strategy import HttpxStrategy
from .playwright_stealth_strategy import PlaywrightStealthStrategy

__all__ = [
    'CurlCffiStrategy',
    'HttpxStrategy',
    'PlaywrightStealthStrategy',
]
