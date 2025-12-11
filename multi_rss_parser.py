"""
Multi-Source RSS Feed Parser
Aggregates real estate news from multiple Russian and international sources
"""

import feedparser
import logging
import re
import requests
from typing import List, Dict, Optional
from datetime import datetime
from email.utils import parsedate_to_datetime
from bs4 import BeautifulSoup
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RSSSource:
    """RSS feed source configuration"""
    name: str
    url: str
    language: str  # 'ru' or 'en'
    has_full_text: bool  # Whether RSS contains full article text
    full_text_field: Optional[str] = None  # Field name for full text (e.g., 'yandex_full-text')
    category: str = 'general'  # Category: general, commercial, residential, analytics


# Verified working RSS feeds
RSS_SOURCES = [
    # Russian sources with full text
    RSSSource(
        name='CIAN Journal',
        url='https://content-cdn.cian.site/realty/journal/yandex_feeds/rssnews.xml',
        language='ru',
        has_full_text=True,
        full_text_field='yandex_full-text',
        category='general'
    ),
    RSSSource(
        name='RBC Realty',
        url='https://rssexport.rbc.ru/realty/news/30/full.rss',
        language='ru',
        has_full_text=True,
        full_text_field='rbc_news_full-text',
        category='analytics'
    ),

    # Russian sources (headlines only - need web scraping for full text)
    RSSSource(
        name='Vedomosti Realty',
        url='https://www.vedomosti.ru/rss/rubric/realty',
        language='ru',
        has_full_text=False,
        category='analytics'
    ),
    RSSSource(
        name='RIA Realty',
        url='https://realty.ria.ru/export/rss2/index.xml',
        language='ru',
        has_full_text=False,
        category='general'
    ),
    # Novostroy.ru excluded - broken RSS feed

    # International sources with full text
    RSSSource(
        name='World Property Journal',
        url='https://www.worldpropertyjournal.com/feed.xml',
        language='en',
        has_full_text=True,
        full_text_field='content',  # Atom feed uses content element
        category='international'
    ),
]


class MultiRSSParser:
    """Parser for multiple RSS sources"""

    def __init__(self, sources: List[RSSSource] = None):
        self.sources = sources or RSS_SOURCES
        self.cache = {}  # Cache feeds by source name

    def get_all_articles(self, limit_per_source: int = 10, language: str = None) -> List[Dict]:
        """Get articles from all configured sources"""
        all_articles = []

        for source in self.sources:
            if language and source.language != language:
                continue

            try:
                articles = self._fetch_source(source, limit_per_source)
                all_articles.extend(articles)
                logger.info(f"Fetched {len(articles)} articles from {source.name}")
            except Exception as e:
                logger.error(f"Failed to fetch from {source.name}: {e}")

        # Sort by date (newest first)
        all_articles.sort(key=lambda x: x.get('published_date') or '', reverse=True)

        return all_articles

    def get_russian_articles(self, limit_per_source: int = 10) -> List[Dict]:
        """Get articles from Russian sources only"""
        return self.get_all_articles(limit_per_source, language='ru')

    def get_international_articles(self, limit_per_source: int = 10) -> List[Dict]:
        """Get articles from international sources only"""
        return self.get_all_articles(limit_per_source, language='en')

    def _fetch_source(self, source: RSSSource, limit: int) -> List[Dict]:
        """Fetch articles from a single source"""
        articles = []

        logger.info(f"Fetching RSS feed: {source.url}")
        feed = feedparser.parse(source.url)
        self.cache[source.name] = feed

        if feed.bozo and not feed.entries:
            logger.warning(f"RSS parse error for {source.name}: {feed.bozo_exception}")
            return []

        for entry in feed.entries[:limit]:
            try:
                article = self._parse_entry(entry, source)
                if article:
                    articles.append(article)
            except Exception as e:
                logger.warning(f"Failed to parse entry from {source.name}: {e}")
                continue

        return articles

    def _parse_entry(self, entry, source: RSSSource) -> Optional[Dict]:
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
        elif entry.get('updated'):
            try:
                # Atom format
                published_date = datetime.fromisoformat(entry.updated.replace('Z', '+00:00'))
            except Exception:
                pass

        # Get full text if available
        full_text = None
        if source.has_full_text and source.full_text_field:
            if source.full_text_field == 'content':
                # Atom feed content
                if entry.get('content'):
                    for content in entry.content:
                        if content.get('value'):
                            full_text = self._clean_html(content.value)
                            break
            else:
                # Custom field (like yandex_full-text)
                full_text = entry.get(source.full_text_field)
                if full_text:
                    full_text = self._clean_html(full_text)

        # Get image URL
        image_url = None
        if entry.get('enclosures'):
            for enc in entry.enclosures:
                if enc.get('type', '').startswith('image/'):
                    image_url = enc.get('href') or enc.get('url')
                    break
        # Atom feed media
        if not image_url and entry.get('media_content'):
            for media in entry.media_content:
                if media.get('medium') == 'image' or media.get('type', '').startswith('image/'):
                    image_url = media.get('url')
                    break

        return {
            'url': url,
            'title': title,
            'excerpt': self._clean_html(description) if description else None,
            'content': full_text,
            'published_date': published_date.isoformat() if published_date else None,
            'image_url': image_url,
            'source': source.name,
            'source_language': source.language,
            'source_category': source.category,
            'has_full_text': bool(full_text)
        }

    def get_article_content(self, url: str, source_name: str = None) -> Optional[Dict]:
        """Get full article content by URL"""
        # Try to find in cache first
        for name, feed in self.cache.items():
            if source_name and name != source_name:
                continue
            for entry in feed.entries:
                if entry.get('link') == url:
                    source = next((s for s in self.sources if s.name == name), None)
                    if source:
                        return self._extract_full_content(entry, source)

        logger.warning(f"Article not found in cache: {url}")
        return None

    def _extract_full_content(self, entry, source: RSSSource) -> Optional[Dict]:
        """Extract full content from RSS entry"""
        title = entry.get('title', '').strip()

        # Get full text
        full_text = None
        if source.has_full_text and source.full_text_field:
            if source.full_text_field == 'content':
                if entry.get('content'):
                    for content in entry.content:
                        if content.get('value'):
                            full_text = self._clean_html(content.value)
                            break
            else:
                full_text = entry.get(source.full_text_field)
                if full_text:
                    full_text = self._clean_html(full_text)

        # Fall back to summary
        if not full_text:
            full_text = entry.get('summary', '') or entry.get('description', '')
            full_text = self._clean_html(full_text)

        if not full_text or len(full_text) < 50:
            return None

        # Parse date
        published_at = None
        if entry.get('published'):
            try:
                published_at = parsedate_to_datetime(entry.published)
            except Exception:
                published_at = datetime.now()
        elif entry.get('updated'):
            try:
                published_at = datetime.fromisoformat(entry.updated.replace('Z', '+00:00'))
            except Exception:
                published_at = datetime.now()
        else:
            published_at = datetime.now()

        # Create excerpt
        excerpt = full_text[:200].rsplit(' ', 1)[0] + '...' if len(full_text) > 200 else full_text

        return {
            'title': title,
            'content': full_text,
            'excerpt': excerpt,
            'url': entry.get('link'),
            'published_at': published_at.isoformat(),
            'source': source.name
        }

    def _clean_html(self, html_content: str) -> str:
        """Remove HTML tags and clean up text"""
        if not html_content:
            return ''

        soup = BeautifulSoup(html_content, 'html.parser')

        # Remove unwanted elements
        for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            element.decompose()

        # Get text
        text = soup.get_text(separator='\n')

        # Clean up whitespace
        lines = []
        for line in text.split('\n'):
            line = line.strip()
            if line and len(line) > 15:
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

        return slug[:100]  # Limit slug length

    def list_sources(self) -> List[Dict]:
        """List all configured sources"""
        return [
            {
                'name': s.name,
                'url': s.url,
                'language': s.language,
                'category': s.category,
                'has_full_text': s.has_full_text
            }
            for s in self.sources
        ]


def test_all_feeds():
    """Test all configured RSS feeds"""
    parser = MultiRSSParser()

    print("=" * 60)
    print("Testing all RSS feeds")
    print("=" * 60)

    for source in parser.sources:
        print(f"\n--- {source.name} ({source.language}) ---")
        print(f"URL: {source.url}")

        try:
            articles = parser._fetch_source(source, limit=2)
            print(f"Status: OK - {len(articles)} articles")

            for i, article in enumerate(articles, 1):
                print(f"  {i}. {article['title'][:60]}...")
                print(f"     Has full text: {article['has_full_text']}")
                if article['content']:
                    print(f"     Content length: {len(article['content'])} chars")

        except Exception as e:
            print(f"Status: FAILED - {e}")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    test_all_feeds()
