"""
Lambda Parser - lightweight Cian parser with SOCKS5 proxy support
Reuses extraction logic from main project's BaseCianParser
"""

import re
import json
import logging
from typing import Dict, List, Optional, Any

import httpx
from bs4 import BeautifulSoup

from proxy_manager import get_proxy_url

logger = logging.getLogger(__name__)

# Modern browser User-Agent strings
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0',
]


class LambdaCianParser:
    """
    Lightweight Cian parser for AWS Lambda
    Uses httpx with SOCKS5 proxy (Decodo)
    """

    def __init__(self, timeout: int = 30, use_proxy: bool = True):
        """
        Args:
            timeout: Request timeout in seconds
            use_proxy: Whether to use Decodo proxy
        """
        self.timeout = timeout
        self.use_proxy = use_proxy
        self.proxy_url = None

        if use_proxy:
            try:
                self.proxy_url = get_proxy_url()
                logger.info(f"Proxy configured: {self.proxy_url[:30]}...")
            except Exception as e:
                logger.warning(f"Failed to configure proxy: {e}")

    def _get_headers(self) -> Dict[str, str]:
        """Get browser-like headers"""
        import random
        ua = random.choice(USER_AGENTS)

        return {
            'User-Agent': ua,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'no-cache',
            'Sec-Ch-Ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
        }

    def fetch_page(self, url: str) -> str:
        """
        Fetch page content via SOCKS5 proxy

        Args:
            url: URL to fetch

        Returns:
            HTML content

        Raises:
            Exception: On fetch error
        """
        logger.info(f"Fetching: {url}")

        # Configure proxy
        transport = None
        if self.proxy_url:
            transport = httpx.HTTPTransport(proxy=self.proxy_url)
            logger.info("Using SOCKS5 proxy")

        with httpx.Client(
            transport=transport,
            timeout=self.timeout,
            follow_redirects=True,
            headers=self._get_headers()
        ) as client:
            response = client.get(url)
            response.raise_for_status()

            logger.info(f"Response: {response.status_code}, {len(response.text)} bytes")
            return response.text

    def parse_detail_page(self, url: str) -> Dict[str, Any]:
        """
        Parse Cian property detail page

        Args:
            url: Cian property URL

        Returns:
            Parsed property data
        """
        html = self.fetch_page(url)
        soup = BeautifulSoup(html, 'lxml')

        data = {
            'url': url,
            'title': None,
            'price': None,
            'price_raw': None,
            'description': None,
            'address': None,
            'residential_complex': None,
            'metro': [],
            'characteristics': {},
            'images': [],
        }

        # Extract JSON-LD (most reliable source)
        json_ld = self._extract_json_ld(soup)
        if json_ld:
            data['title'] = json_ld.get('name')
            offers = json_ld.get('offers', {})
            if offers:
                data['price_raw'] = offers.get('price')
                data['price'] = data['price_raw']

        # Extract from HTML
        data = self._extract_basic_info(soup, data)
        data['characteristics'] = self._extract_characteristics(soup)
        data['images'] = self._extract_images(soup, max_images=10)

        # Promote key fields from characteristics
        self._promote_key_fields(data)

        return data

    def _extract_json_ld(self, soup: BeautifulSoup) -> Optional[Dict]:
        """Extract JSON-LD structured data"""
        try:
            script = soup.find('script', type='application/ld+json')
            if script and script.string:
                return json.loads(script.string)
        except (json.JSONDecodeError, AttributeError) as e:
            logger.debug(f"JSON-LD extraction failed: {e}")
        return None

    def _extract_basic_info(self, soup: BeautifulSoup, data: Dict) -> Dict:
        """Extract basic info from HTML"""

        # Title
        if not data.get('title'):
            title_elem = soup.find('h1', {'data-mark': 'OfferTitle'}) or soup.find('h1')
            if title_elem:
                data['title'] = title_elem.get_text(strip=True)

        # Address from multiple sources
        if not data.get('address'):
            # Method 1: GeoLabel
            addr = soup.find('a', {'data-name': 'GeoLabel'})
            if addr:
                data['address'] = addr.get_text(strip=True)

            # Method 2: AddressItem
            if not data.get('address'):
                addr = soup.find('a', {'data-name': 'AddressItem'})
                if addr:
                    data['address'] = addr.get_text(strip=True)

            # Method 3: Breadcrumbs
            if not data.get('address'):
                breadcrumbs = soup.find('div', {'data-name': 'OfferBreadcrumbs'})
                if breadcrumbs:
                    geo_links = breadcrumbs.find_all('a', href=lambda h: h and '/geo/' in h)
                    parts = []
                    for link in geo_links:
                        text = link.get_text(strip=True)
                        if text not in ['Санкт-Петербург', 'Москва', 'Продажа', 'Купить']:
                            parts.append(text)
                    if parts:
                        data['address'] = ', '.join(parts)

        # Residential complex
        if not data.get('residential_complex'):
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                if 'zhk-' in href and '.cian.ru' in href:
                    data['residential_complex'] = link.get_text(strip=True).replace('ЖК ', '').strip()
                    data['residential_complex_url'] = href
                    break
                elif '/zhiloy-kompleks-' in href:
                    data['residential_complex'] = link.get_text(strip=True).replace('ЖК ', '').strip()
                    break

        # Metro
        if not data.get('metro'):
            metro_items = soup.find_all('a', {'data-name': 'UndergroundLabel'})
            if not metro_items:
                metro_items = soup.find_all('div', {'data-name': 'UndergroundItem'})

            metro_list = []
            for item in metro_items:
                text = item.get_text(strip=True)
                # Remove travel time
                text = re.sub(r'\d+\s*мин\.?\s*(пешком)?', '', text).strip()
                if text and text not in metro_list:
                    metro_list.append(text)
            data['metro'] = metro_list

        # Description
        if not data.get('description'):
            desc = soup.find('div', {'data-name': 'Description'})
            if desc:
                p = desc.find('p')
                data['description'] = (p or desc).get_text(strip=True)

        return data

    def _extract_characteristics(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract property characteristics"""
        chars = {}

        # Method 1: OfferSummaryInfoItem
        for item in soup.find_all('div', {'data-name': 'OfferSummaryInfoItem'}):
            spans = item.find_all('span')
            if len(spans) >= 2:
                label = spans[0].get_text(strip=True)
                value = spans[1].get_text(strip=True)
                if label and value:
                    chars[label] = value

        # Method 2: ObjectFactoidsItem
        for item in soup.find_all('div', {'data-name': 'ObjectFactoidsItem'}):
            spans = item.find_all('span')
            if len(spans) >= 2:
                label = spans[0].get_text(strip=True)
                value = spans[1].get_text(strip=True)
                if label and value:
                    chars[label] = value

        # Method 3: OfferFactItem
        for item in soup.find_all('div', {'data-name': 'OfferFactItem'}):
            children = list(item.find_all(['span', 'p']))
            if len(children) >= 2:
                label = children[0].get_text(strip=True)
                value = children[1].get_text(strip=True)
                if label and value:
                    chars[label] = value

        return chars

    def _extract_images(self, soup: BeautifulSoup, max_images: int = 10) -> List[str]:
        """Extract image URLs"""
        images = []

        # From gallery
        gallery = soup.find('div', {'data-name': 'GalleryPreviews'})
        if gallery:
            for img in gallery.find_all('img'):
                src = img.get('src') or img.get('data-src')
                if src:
                    images.append(src)

        # Fallback: CDN images
        if not images:
            for img in soup.find_all('img', src=lambda x: x and 'cdn-p.cian.site' in x):
                images.append(img.get('src'))

        return images[:max_images]

    def _promote_key_fields(self, data: Dict) -> None:
        """Extract key fields from characteristics to root level"""
        chars = data.get('characteristics', {})
        if not chars:
            return

        # Area mappings
        area_keys = ['Общая площадь', 'Площадь', 'Общая, м²']
        for key in area_keys:
            if key in chars and not data.get('total_area'):
                try:
                    value = chars[key]
                    data['total_area'] = float(re.sub(r'[^\d,.]', '', value).replace(',', '.'))
                    break
                except (ValueError, AttributeError):
                    pass

        # Living area
        living_keys = ['Жилая площадь', 'Жилая', 'Жилая, м²']
        for key in living_keys:
            if key in chars and not data.get('living_area'):
                try:
                    value = chars[key]
                    data['living_area'] = float(re.sub(r'[^\d,.]', '', value).replace(',', '.'))
                    break
                except (ValueError, AttributeError):
                    pass

        # Kitchen area
        kitchen_keys = ['Площадь кухни', 'Кухня', 'Кухня, м²']
        for key in kitchen_keys:
            if key in chars and not data.get('kitchen_area'):
                try:
                    value = chars[key]
                    data['kitchen_area'] = float(re.sub(r'[^\d,.]', '', value).replace(',', '.'))
                    break
                except (ValueError, AttributeError):
                    pass

        # Floor
        if 'Этаж' in chars and not data.get('floor'):
            try:
                floor_val = chars['Этаж']
                if 'из' in floor_val:
                    parts = floor_val.split()
                    data['floor'] = int(parts[0])
                    data['total_floors'] = int(parts[-1])
                else:
                    data['floor'] = int(floor_val)
            except (ValueError, IndexError):
                pass

        # Build year
        year_keys = ['Год постройки', 'Построен']
        for key in year_keys:
            if key in chars and not data.get('build_year'):
                try:
                    value = chars[key]
                    data['build_year'] = int(re.sub(r'[^\d]', '', value))
                    break
                except (ValueError, AttributeError):
                    pass

        # Rooms from title
        if not data.get('rooms') and data.get('title'):
            title = data['title']
            if 'студи' in title.lower():
                data['rooms'] = 'студия'
            else:
                match = re.search(r'(\d+)-комн', title)
                if match:
                    data['rooms'] = int(match.group(1))


# For direct testing
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    # Test URL
    test_url = "https://spb.cian.ru/sale/flat/316296015/"

    parser = LambdaCianParser(use_proxy=False)  # Set to True to test with proxy
    result = parser.parse_detail_page(test_url)

    print("\n=== Parsed Data ===")
    for key, value in result.items():
        if value:
            print(f"{key}: {value}")
