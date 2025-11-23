"""
Парсер для Cian Magazine
Парсит статьи с https://spb.cian.ru/magazine/ и других регионов
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime
import re
from playwright.sync_api import sync_playwright, Page, Browser
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class CianMagazineParser:
    """Парсер статей Cian Magazine"""

    def __init__(self, headless: bool = True):
        """
        Args:
            headless: Запускать браузер в headless режиме
        """
        self.headless = headless
        self.base_urls = {
            'spb': 'https://spb.cian.ru/magazine/',
            'msk': 'https://www.cian.ru/magazine/',
        }

    def parse_article_list(self, region: str = 'spb', limit: int = 15) -> List[Dict]:
        """
        Парсит список статей с главной страницы журнала

        Args:
            region: Регион (spb, msk)
            limit: Максимальное количество статей

        Returns:
            Список словарей с данными статей
        """
        url = self.base_urls.get(region, self.base_urls['spb'])

        logger.info(f"Парсинг списка статей: {url}")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            page = browser.new_page()

            try:
                # Переходим на страницу
                page.goto(url, wait_until='networkidle', timeout=30000)

                # Ждем загрузки статей
                page.wait_for_selector('article, [data-name="Article"]', timeout=10000)

                # Скроллим вниз чтобы загрузить больше статей
                for _ in range(3):
                    page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                    page.wait_for_timeout(1000)

                # Получаем HTML
                html = page.content()
                soup = BeautifulSoup(html, 'html.parser')

                articles = []

                # Ищем статьи по различным селекторам
                article_selectors = [
                    'article',
                    '[data-name="Article"]',
                    '[data-testid="article-card"]',
                    '.article-card',
                    '[class*="article"]'
                ]

                article_elements = []
                for selector in article_selectors:
                    found = soup.select(selector)
                    if found:
                        article_elements = found
                        logger.info(f"Найдено {len(found)} статей по селектору: {selector}")
                        break

                for article_elem in article_elements[:limit]:
                    try:
                        article_data = self._parse_article_preview(article_elem)
                        if article_data and article_data.get('url'):
                            articles.append(article_data)
                    except Exception as e:
                        logger.warning(f"Ошибка парсинга превью статьи: {e}")
                        continue

                logger.info(f"Спарсено {len(articles)} статей")
                return articles

            finally:
                browser.close()

    def _parse_article_preview(self, element) -> Optional[Dict]:
        """Парсит превью статьи из элемента списка"""

        # Ищем ссылку
        link_elem = element.find('a', href=True)
        if not link_elem:
            return None

        url = link_elem.get('href', '')
        if not url.startswith('http'):
            # Относительная ссылка
            if url.startswith('/'):
                url = 'https://www.cian.ru' + url
            else:
                return None

        # Ищем заголовок
        title = None
        title_selectors = ['h1', 'h2', 'h3', '[data-name="Title"]', '.title', '[class*="title"]']
        for selector in title_selectors:
            title_elem = element.select_one(selector)
            if title_elem:
                title = title_elem.get_text(strip=True)
                break

        if not title:
            title = link_elem.get_text(strip=True)

        # Ищем изображение
        image = None
        img_elem = element.find('img')
        if img_elem:
            image = img_elem.get('src') or img_elem.get('data-src')

        # Ищем описание/excerpt
        excerpt = None
        desc_selectors = ['p', '.description', '[class*="description"]', '[class*="excerpt"]']
        for selector in desc_selectors:
            desc_elem = element.select_one(selector)
            if desc_elem:
                excerpt = desc_elem.get_text(strip=True)
                if len(excerpt) > 50:  # Минимальная длина для описания
                    break

        # Ищем категорию
        category = "Недвижимость"
        cat_selectors = ['.category', '[class*="category"]', '[data-name="Category"]']
        for selector in cat_selectors:
            cat_elem = element.select_one(selector)
            if cat_elem:
                category = cat_elem.get_text(strip=True)
                break

        return {
            'url': url,
            'title': title,
            'excerpt': excerpt,
            'cover_image': image,
            'category': category,
        }

    def parse_article_content(self, url: str) -> Optional[Dict]:
        """
        Парсит полный контент статьи

        Args:
            url: URL статьи

        Returns:
            Словарь с полными данными статьи
        """
        logger.info(f"Парсинг статьи: {url}")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            page = browser.new_page()

            try:
                # Переходим на страницу статьи
                page.goto(url, wait_until='networkidle', timeout=30000)

                # Ждем загрузки контента
                page.wait_for_timeout(2000)

                # Получаем HTML
                html = page.content()
                soup = BeautifulSoup(html, 'html.parser')

                # Парсим заголовок
                title = self._extract_title(soup)

                # Парсим контент
                content = self._extract_content(soup)

                # Парсим изображения
                images = self._extract_images(soup)

                # Парсим мета-информацию
                meta_description = self._extract_meta_description(soup)

                # Парсим дату
                published_date = self._extract_date(soup)

                # Парсим категорию и теги
                category, tags = self._extract_category_tags(soup)

                return {
                    'url': url,
                    'title': title,
                    'content': content,
                    'images': images,
                    'cover_image': images[0] if images else None,
                    'meta_description': meta_description,
                    'published_date': published_date,
                    'category': category or "Недвижимость",
                    'tags': tags,
                }

            except Exception as e:
                logger.error(f"Ошибка парсинга статьи {url}: {e}")
                return None
            finally:
                browser.close()

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Извлекает заголовок статьи"""
        # Пробуем различные селекторы
        selectors = ['h1', '[data-name="ArticleTitle"]', 'article h1']

        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                return elem.get_text(strip=True)

        # Fallback на title страницы
        title_elem = soup.find('title')
        if title_elem:
            return title_elem.get_text(strip=True).split('|')[0].strip()

        return "Без заголовка"

    def _extract_content(self, soup: BeautifulSoup) -> str:
        """Извлекает основной контент статьи с HTML разметкой"""

        # Ищем контейнер с контентом
        content_selectors = [
            'article',
            '[data-name="ArticleContent"]',
            '.article-content',
            '[class*="article-content"]',
            '.content',
            'main article'
        ]

        content_container = None
        for selector in content_selectors:
            content_container = soup.select_one(selector)
            if content_container:
                break

        if not content_container:
            # Fallback - берем все параграфы
            paragraphs = soup.find_all('p')
            if paragraphs:
                content_html = ''.join([str(p) for p in paragraphs])
                return content_html

        # Удаляем ненужные элементы
        for elem in content_container.select('script, style, nav, header, footer, aside, .comments, .share'):
            elem.decompose()

        # Находим все параграфы, заголовки, списки
        content_elements = content_container.find_all(['p', 'h2', 'h3', 'h4', 'ul', 'ol', 'blockquote'])

        # Собираем HTML
        content_html = ''
        for elem in content_elements:
            content_html += str(elem) + '\n'

        # Если контента мало, берем весь текст контейнера
        if len(content_html) < 200:
            content_html = str(content_container)

        return content_html.strip()

    def _extract_images(self, soup: BeautifulSoup) -> List[str]:
        """Извлекает изображения из статьи"""
        images = []

        # Ищем все изображения в контенте
        img_elements = soup.find_all('img')

        for img in img_elements:
            src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
            if src and src.startswith('http'):
                # Фильтруем маленькие иконки и рекламу
                if 'icon' not in src.lower() and 'logo' not in src.lower():
                    images.append(src)

        return images[:10]  # Максимум 10 изображений

    def _extract_meta_description(self, soup: BeautifulSoup) -> Optional[str]:
        """Извлекает meta description"""
        meta = soup.find('meta', attrs={'name': 'description'})
        if meta:
            return meta.get('content', '').strip()

        # Fallback - OG description
        og_desc = soup.find('meta', attrs={'property': 'og:description'})
        if og_desc:
            return og_desc.get('content', '').strip()

        return None

    def _extract_date(self, soup: BeautifulSoup) -> Optional[datetime]:
        """Извлекает дату публикации"""

        # Ищем в meta-тегах
        date_metas = [
            'article:published_time',
            'datePublished',
            'date',
        ]

        for meta_name in date_metas:
            meta = soup.find('meta', attrs={'property': meta_name}) or \
                   soup.find('meta', attrs={'name': meta_name})
            if meta:
                date_str = meta.get('content', '')
                try:
                    return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                except:
                    pass

        # Ищем в тексте
        time_elem = soup.find('time')
        if time_elem:
            datetime_attr = time_elem.get('datetime')
            if datetime_attr:
                try:
                    return datetime.fromisoformat(datetime_attr.replace('Z', '+00:00'))
                except:
                    pass

        # Возвращаем текущую дату как fallback
        return datetime.now()

    def _extract_category_tags(self, soup: BeautifulSoup) -> tuple[str, List[str]]:
        """Извлекает категорию и теги"""

        category = "Недвижимость"
        tags = []

        # Ищем категорию
        cat_selectors = ['.category', '[class*="category"]', '[data-name="Category"]']
        for selector in cat_selectors:
            cat_elem = soup.select_one(selector)
            if cat_elem:
                category = cat_elem.get_text(strip=True)
                break

        # Ищем теги
        tag_selectors = ['.tag', '[class*="tag"]', '.label']
        tag_elements = []
        for selector in tag_selectors:
            tag_elements = soup.select(selector)
            if tag_elements:
                break

        for tag_elem in tag_elements[:5]:  # Максимум 5 тегов
            tag_text = tag_elem.get_text(strip=True)
            if tag_text and len(tag_text) < 30:
                tags.append(tag_text)

        return category, tags


# Convenience функции для использования в других модулях

def parse_cian_magazine_articles(region: str = 'spb', limit: int = 15) -> List[Dict]:
    """
    Парсит список статей из Cian Magazine

    Args:
        region: Регион (spb, msk)
        limit: Максимальное количество статей

    Returns:
        Список словарей с данными статей
    """
    parser = CianMagazineParser()
    return parser.parse_article_list(region=region, limit=limit)


def parse_cian_magazine_article(url: str) -> Optional[Dict]:
    """
    Парсит полный контент статьи

    Args:
        url: URL статьи

    Returns:
        Словарь с полными данными статьи или None
    """
    parser = CianMagazineParser()
    return parser.parse_article_content(url)
