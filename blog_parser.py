"""
CIAN Magazine Parser
Parses articles from https://spb.cian.ru/magazine
"""

import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from datetime import datetime
import re
from urllib.parse import urljoin
import logging

logger = logging.getLogger(__name__)


class CianMagazineParser:
    def __init__(self):
        self.base_url = "https://spb.cian.ru"
        self.magazine_url = f"{self.base_url}/magazine"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }

    def get_recent_articles(self, limit: int = 10) -> List[Dict]:
        """Get recent articles from magazine main page"""
        try:
            response = requests.get(self.magazine_url, headers=self.headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            articles = []

            # ЦИАН magazine использует разные структуры, ищем статьи
            article_elements = soup.find_all('article') or soup.find_all('a', class_=re.compile('article|card'))

            for element in article_elements[:limit]:
                try:
                    article = self._parse_article_element(element)
                    if article:
                        articles.append(article)
                except Exception as e:
                    logger.warning(f"Failed to parse article element: {e}")
                    continue

            return articles

        except Exception as e:
            logger.error(f"Failed to fetch articles: {e}")
            return []

    def _parse_article_element(self, element) -> Optional[Dict]:
        """Parse single article element"""
        # Получаем ссылку
        link = element.find('a') if element.name != 'a' else element
        if not link or not link.get('href'):
            return None

        url = urljoin(self.base_url, link['href'])

        # Получаем заголовок
        title_elem = element.find(['h2', 'h3', 'h4']) or link
        title = title_elem.get_text(strip=True) if title_elem else None

        if not title:
            return None

        # Получаем краткое описание если есть
        excerpt_elem = element.find('p')
        excerpt = excerpt_elem.get_text(strip=True) if excerpt_elem else None

        return {
            'url': url,
            'title': title,
            'excerpt': excerpt
        }

    def parse_article_content(self, url: str) -> Optional[Dict]:
        """Parse full article content from article page"""
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # Ищем заголовок
            title_elem = soup.find('h1')
            title = title_elem.get_text(strip=True) if title_elem else None

            # Ищем контент статьи
            content_elem = soup.find('article') or soup.find('div', class_=re.compile('content|article|text'))
            if not content_elem:
                return None

            # Извлекаем текстовый контент
            paragraphs = content_elem.find_all('p')
            content = '\n\n'.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])

            if not content:
                return None

            # Ищем дату публикации
            date_elem = soup.find('time') or soup.find(class_=re.compile('date|time'))
            published_date = None
            if date_elem:
                date_text = date_elem.get('datetime') or date_elem.get_text(strip=True)
                try:
                    published_date = datetime.fromisoformat(date_text.replace('Z', '+00:00'))
                except:
                    pass

            return {
                'title': title,
                'content': content,
                'url': url,
                'published_at': published_date.isoformat() if published_date else datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to parse article content from {url}: {e}")
            return None

    def create_slug(self, title: str) -> str:
        """Create URL-friendly slug from title"""
        # Транслитерация
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

        # Убираем всё кроме букв, цифр и дефисов
        slug = re.sub(r'[^a-z0-9]+', '-', slug)
        slug = slug.strip('-')

        return slug
