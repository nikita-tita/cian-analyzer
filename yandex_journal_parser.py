"""
Yandex Realty Journal Parser
Parses news from https://realty.yandex.ru/journal/category/news/
"""

from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from datetime import datetime
import re
import logging
import subprocess

logger = logging.getLogger(__name__)


class YandexJournalParser:
    def __init__(self, headless: bool = True):
        self.base_url = "https://realty.yandex.ru"
        self.news_url = f"{self.base_url}/journal/category/news/"
        self.headless = headless

    def _fetch_with_curl(self, url: str, timeout: int = 30) -> Optional[str]:
        """Fetch URL content using curl (more reliable for Yandex)"""
        try:
            result = subprocess.run(
                ['curl', '-s', '--max-time', str(timeout), url,
                 '-H', 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'],
                capture_output=True,
                text=True,
                timeout=timeout + 5
            )
            if result.returncode == 0:
                return result.stdout
            return None
        except Exception as e:
            logger.error(f"Curl failed: {e}")
            return None

    def get_recent_articles(self, limit: int = 10) -> List[Dict]:
        """Get recent news from Yandex Realty Journal"""
        articles = []

        try:
            logger.info(f"Fetching {self.news_url}")
            html = self._fetch_with_curl(self.news_url)

            if not html:
                logger.error("Failed to fetch news page")
                return []

            soup = BeautifulSoup(html, 'html.parser')

            # Find article links - Yandex uses /journal/post/ format
            article_links = []

            # Look for links to journal posts
            for link in soup.find_all('a', href=re.compile(r'/journal/post/[^/]+/?')):
                href = link.get('href')
                if href and '/journal/post/' in href:
                    full_url = href if href.startswith('http') else f"{self.base_url}{href}"
                    article_links.append({
                        'url': full_url,
                        'element': link
                    })

            # Remove duplicates
            seen_urls = set()
            unique_articles = []
            for item in article_links:
                if item['url'] not in seen_urls:
                    seen_urls.add(item['url'])
                    unique_articles.append(item)

            logger.info(f"Found {len(unique_articles)} unique article links")

            # Parse each article preview
            for item in unique_articles[:limit]:
                try:
                    article = self._parse_article_from_link(item)
                    if article:
                        articles.append(article)
                except Exception as e:
                    logger.warning(f"Failed to parse article {item['url']}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Failed to fetch articles: {e}")

        return articles

    def _parse_article_from_link(self, item: Dict) -> Optional[Dict]:
        """Parse article metadata from link element"""
        element = item['element']
        url = item['url']

        # Yandex uses titleLink-kMFO class for article titles
        # Check if this element has titleLink class
        element_classes = element.get('class', [])
        if isinstance(element_classes, list):
            element_classes = ' '.join(element_classes)

        if 'titleLink' in element_classes:
            title = element.get_text(strip=True)
        else:
            # Find card container and look for title link
            parent = element.parent
            title = None
            for _ in range(10):
                if parent:
                    title_elem = parent.find('a', class_=re.compile(r'titleLink'))
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        break
                    parent = parent.parent

            if not title:
                title = element.get_text(strip=True)

        if not title or len(title) < 10:
            return None

        # Look for date
        excerpt = None
        parent = element.parent
        for _ in range(10):
            if parent:
                time_elem = parent.find('time')
                if time_elem:
                    date_text = time_elem.get('datetime', '')
                    if date_text:
                        excerpt = f"Опубликовано: {date_text[:10]}"
                    break
                parent = parent.parent

        return {
            'url': url,
            'title': title,
            'excerpt': excerpt
        }

    def parse_article_content(self, url: str) -> Optional[Dict]:
        """Parse full article content from article page"""
        try:
            logger.info(f"Parsing article: {url}")
            html = self._fetch_with_curl(url)

            if not html:
                logger.warning(f"Failed to fetch article: {url}")
                return None

            soup = BeautifulSoup(html, 'html.parser')

            # Find title
            title_elem = soup.find('h1')
            title = title_elem.get_text(strip=True) if title_elem else None

            # Find article content - Yandex uses contentWrapper class
            content_elem = (
                soup.find('div', class_=re.compile(r'contentWrapper')) or
                soup.find('article') or
                soup.find('div', class_=re.compile(r'article|content|text|body|post', re.I)) or
                soup.find('main')
            )

            if not content_elem:
                logger.warning(f"No content found for {url}")
                return None

            # Extract paragraphs
            paragraphs = content_elem.find_all('p')
            content_parts = []

            for p in paragraphs:
                text = p.get_text(strip=True)
                # Filter out very short texts only
                if text and len(text) > 50:
                    content_parts.append(text)

            content = '\n\n'.join(content_parts)

            if not content or len(content) < 100:
                logger.warning(f"Content too short for {url}")
                return None

            # Look for date
            date_elem = soup.find('time')
            published_date = None
            if date_elem:
                date_text = date_elem.get('datetime', '')
                try:
                    if date_text and ('T' in str(date_text) or '-' in str(date_text)):
                        published_date = datetime.fromisoformat(str(date_text).replace('Z', '+00:00'))
                    else:
                        published_date = datetime.now()
                except:
                    published_date = datetime.now()

            # Create excerpt from first paragraph
            excerpt = content_parts[0][:200] + '...' if content_parts else None

            return {
                'title': title,
                'content': content,
                'excerpt': excerpt,
                'url': url,
                'published_at': published_date.isoformat() if published_date else datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to parse article content from {url}: {e}")
            return None

    def create_slug(self, title: str) -> str:
        """Create URL-friendly slug from title"""
        translit_map = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
            'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
            'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
            'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
            'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
        }

        slug = title.lower()
        for ru, en in translit_map.items():
            slug = slug.replace(ru, en)

        slug = re.sub(r'[^a-z0-9]+', '-', slug)
        slug = slug.strip('-')

        return slug
