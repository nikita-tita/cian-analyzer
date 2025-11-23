"""
CIAN Magazine Parser with Playwright
Parses articles from https://spb.cian.ru/magazine using browser automation
"""

from playwright.sync_api import sync_playwright, Page, Browser
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from datetime import datetime
import re
import logging
import time

logger = logging.getLogger(__name__)


class CianMagazineParserPlaywright:
    def __init__(self, headless: bool = True):
        self.base_url = "https://spb.cian.ru"
        self.magazine_url = f"{self.base_url}/magazine"
        self.headless = headless

    def get_recent_articles(self, limit: int = 10) -> List[Dict]:
        """Get recent articles from magazine main page"""
        articles = []

        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=self.headless)
                page = browser.new_page()

                logger.info(f"Navigating to {self.magazine_url}")
                page.goto(self.magazine_url, wait_until='networkidle', timeout=30000)

                # Даем странице время на загрузку JS-контента
                time.sleep(3)

                # Получаем HTML после рендеринга
                html = page.content()
                soup = BeautifulSoup(html, 'html.parser')

                # Ищем статьи по различным селекторам
                article_links = []

                # Вариант 1: ссылки на статьи в magazine
                for link in soup.find_all('a', href=re.compile(r'/magazine/[^/]+/?$')):
                    href = link.get('href')
                    if href and '/magazine/' in href:
                        full_url = href if href.startswith('http') else f"{self.base_url}{href}"
                        article_links.append({
                            'url': full_url,
                            'element': link
                        })

                # Убираем дубликаты
                seen_urls = set()
                unique_articles = []
                for item in article_links:
                    if item['url'] not in seen_urls:
                        seen_urls.add(item['url'])
                        unique_articles.append(item)

                logger.info(f"Found {len(unique_articles)} unique article links")

                # Парсим каждую статью
                for item in unique_articles[:limit]:
                    try:
                        article = self._parse_article_from_link(item)
                        if article:
                            articles.append(article)
                    except Exception as e:
                        logger.warning(f"Failed to parse article {item['url']}: {e}")
                        continue

                browser.close()

            except Exception as e:
                logger.error(f"Failed to fetch articles: {e}")

        return articles

    def _parse_article_from_link(self, item: Dict) -> Optional[Dict]:
        """Parse article metadata from link element"""
        element = item['element']
        url = item['url']

        # Получаем заголовок из текста ссылки или дочерних элементов
        title = element.get_text(strip=True)

        # Ищем заголовок в родительском контейнере
        parent = element.parent
        if parent:
            title_elem = parent.find(['h2', 'h3', 'h4'])
            if title_elem:
                title = title_elem.get_text(strip=True)

        if not title or len(title) < 10:
            return None

        # Ищем описание
        excerpt = None
        if parent:
            excerpt_elem = parent.find('p')
            if excerpt_elem:
                excerpt = excerpt_elem.get_text(strip=True)

        return {
            'url': url,
            'title': title,
            'excerpt': excerpt
        }

    def parse_article_content(self, url: str) -> Optional[Dict]:
        """Parse full article content from article page"""
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=self.headless)
                page = browser.new_page()

                logger.info(f"Parsing article: {url}")
                page.goto(url, wait_until='networkidle', timeout=30000)
                time.sleep(2)

                html = page.content()
                soup = BeautifulSoup(html, 'html.parser')

                # Ищем заголовок
                title_elem = soup.find('h1')
                title = title_elem.get_text(strip=True) if title_elem else None

                # Ищем контент статьи - пробуем разные селекторы
                content_elem = (
                    soup.find('article') or
                    soup.find('div', class_=re.compile(r'article|content|text|body', re.I)) or
                    soup.find('main')
                )

                if not content_elem:
                    logger.warning(f"No content found for {url}")
                    browser.close()
                    return None

                # Извлекаем параграфы
                paragraphs = content_elem.find_all('p')
                content_parts = []

                for p in paragraphs:
                    text = p.get_text(strip=True)
                    # Фильтруем короткие и служебные тексты
                    if text and len(text) > 30:
                        content_parts.append(text)

                content = '\n\n'.join(content_parts)

                if not content or len(content) < 100:
                    logger.warning(f"Content too short for {url}")
                    browser.close()
                    return None

                # Ищем дату
                date_elem = soup.find('time') or soup.find(class_=re.compile(r'date|time', re.I))
                published_date = None
                if date_elem:
                    date_text = date_elem.get('datetime') or date_elem.get_text(strip=True)
                    try:
                        # Пробуем разные форматы
                        if 'T' in date_text or '-' in date_text:
                            published_date = datetime.fromisoformat(date_text.replace('Z', '+00:00'))
                        else:
                            # Пробуем парсить русский формат
                            published_date = datetime.now()
                    except:
                        published_date = datetime.now()

                # Создаем краткое описание из первого параграфа
                excerpt = content_parts[0][:200] + '...' if content_parts else None

                browser.close()

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
