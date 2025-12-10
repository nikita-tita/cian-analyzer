"""
CIAN RSS Feed Parser
Parses news from CIAN Journal RSS feed without browser automation
No captcha, no blocks - just clean RSS parsing
"""

import feedparser
import logging
import re
from typing import List, Dict, Optional
from datetime import datetime
from email.utils import parsedate_to_datetime
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class CianRSSParser:
    """Parser for CIAN Journal RSS feed"""

    RSS_URL = "https://content-cdn.cian.site/realty/journal/yandex_feeds/rssnews.xml"

    def __init__(self):
        self.feed = None

    def get_recent_articles(self, limit: int = 10) -> List[Dict]:
        """Get recent articles from RSS feed"""
        articles = []

        try:
            logger.info(f"Fetching RSS feed: {self.RSS_URL}")
            self.feed = feedparser.parse(self.RSS_URL)

            if self.feed.bozo:
                logger.warning(f"RSS parse warning: {self.feed.bozo_exception}")

            logger.info(f"Found {len(self.feed.entries)} entries in RSS feed")

            for entry in self.feed.entries[:limit]:
                try:
                    article = self._parse_entry(entry)
                    if article:
                        articles.append(article)
                except Exception as e:
                    logger.warning(f"Failed to parse RSS entry: {e}")
                    continue

            logger.info(f"Parsed {len(articles)} valid articles from RSS")

        except Exception as e:
            logger.error(f"Failed to fetch RSS feed: {e}")

        return articles

    def _parse_entry(self, entry) -> Optional[Dict]:
        """Parse single RSS entry"""
        title = entry.get('title', '').strip()
        if not title or len(title) < 10:
            return None

        url = entry.get('link', '')
        if not url:
            return None

        # Get description/excerpt
        description = entry.get('description', '') or entry.get('summary', '')

        # Parse publication date
        published_date = None
        if entry.get('published'):
            try:
                published_date = parsedate_to_datetime(entry.published)
            except Exception:
                pass

        # Get image URL from enclosure
        image_url = None
        if entry.get('enclosures'):
            for enc in entry.enclosures:
                if enc.get('type', '').startswith('image/'):
                    image_url = enc.get('href') or enc.get('url')
                    break

        return {
            'url': url,
            'title': title,
            'excerpt': description,
            'published_date': published_date.isoformat() if published_date else None,
            'image_url': image_url
        }

    def parse_article_content(self, url: str) -> Optional[Dict]:
        """
        Get full article content from RSS entry.
        RSS feed includes full text in yandex:full-text field.
        """
        # Find entry by URL in cached feed
        if not self.feed:
            self.get_recent_articles(limit=100)

        for entry in self.feed.entries:
            if entry.get('link') == url:
                return self._extract_full_content(entry)

        # If not found, try fetching fresh
        logger.info(f"Entry not in cache, refetching feed for: {url}")
        self.feed = feedparser.parse(self.RSS_URL)

        for entry in self.feed.entries:
            if entry.get('link') == url:
                return self._extract_full_content(entry)

        logger.warning(f"Article not found in RSS feed: {url}")
        return None

    def _extract_full_content(self, entry) -> Optional[Dict]:
        """Extract full content from RSS entry"""
        title = entry.get('title', '').strip()

        # Get full text from yandex:full-text or content:encoded
        full_text = None

        # Try yandex:full-text (stored as yandex_full-text in feedparser)
        if 'yandex_full-text' in entry:
            full_text = entry['yandex_full-text']

        # Try content:encoded
        if not full_text and entry.get('content'):
            for content in entry.content:
                if content.get('value'):
                    full_text = content.value
                    break

        # Fall back to summary/description
        if not full_text:
            full_text = entry.get('summary', '') or entry.get('description', '')

        if not full_text:
            logger.warning(f"No content found for: {entry.get('link')}")
            return None

        # Clean HTML from content
        content = self._clean_html(full_text)

        if len(content) < 100:
            logger.warning(f"Content too short for: {entry.get('link')}")
            return None

        # Parse date
        published_at = None
        if entry.get('published'):
            try:
                published_at = parsedate_to_datetime(entry.published)
            except Exception:
                published_at = datetime.now()
        else:
            published_at = datetime.now()

        # Create excerpt
        excerpt = content[:200].rsplit(' ', 1)[0] + '...' if len(content) > 200 else content

        return {
            'title': title,
            'content': content,
            'excerpt': excerpt,
            'url': entry.get('link'),
            'published_at': published_at.isoformat()
        }

    def _clean_html(self, html_content: str) -> str:
        """Remove HTML tags and clean up text"""
        soup = BeautifulSoup(html_content, 'html.parser')

        # Remove script and style elements
        for element in soup(['script', 'style', 'nav', 'footer', 'header']):
            element.decompose()

        # Get text
        text = soup.get_text(separator='\n')

        # Clean up whitespace
        lines = []
        for line in text.split('\n'):
            line = line.strip()
            if line and len(line) > 20:  # Filter short lines
                lines.append(line)

        return '\n\n'.join(lines)

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
