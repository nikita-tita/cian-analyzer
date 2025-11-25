#!/usr/bin/env python3
"""
Blog Management CLI
Parse articles from CIAN magazine and publish to blog
"""

import argparse
import logging
from dotenv import load_dotenv

load_dotenv()

from blog_parser_playwright import CianMagazineParserPlaywright
from yandex_gpt import YandexGPT
from blog_database import BlogDatabase

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_and_publish(limit: int = 5, force: bool = False):
    """Parse articles from CIAN and publish to blog"""
    logger.info(f"Starting to parse {limit} articles from CIAN magazine...")

    parser = CianMagazineParserPlaywright(headless=True)
    gpt = YandexGPT()
    db = BlogDatabase()

    # Получаем список статей
    articles = parser.get_recent_articles(limit=limit * 2)  # Берём с запасом
    logger.info(f"Found {len(articles)} articles")

    published_count = 0

    for article_preview in articles:
        if published_count >= limit:
            break

        try:
            url = article_preview['url']
            logger.info(f"Processing: {article_preview['title']}")

            # Создаём slug
            slug = parser.create_slug(article_preview['title'])

            # Проверяем существует ли уже
            if db.post_exists(slug) and not force:
                logger.info(f"Article already exists: {slug}")
                continue

            # Парсим полный контент
            full_article = parser.parse_article_content(url)
            if not full_article:
                logger.warning(f"Failed to parse article content: {url}")
                continue

            # Рерайтим через Yandex GPT
            logger.info("Rewriting article with Yandex GPT...")
            rewritten = gpt.rewrite_article(
                original_title=full_article['title'],
                original_content=full_article['content'],
                original_excerpt=article_preview.get('excerpt')
            )

            # Сохраняем в БД
            post_id = db.create_post(
                slug=slug,
                title=rewritten['title'],
                content=rewritten['content'],
                excerpt=rewritten['excerpt'],
                original_url=url,
                original_title=full_article['title'],
                published_at=full_article['published_at']
            )

            logger.info(f"✓ Published: {rewritten['title']} (ID: {post_id})")
            published_count += 1

        except Exception as e:
            logger.error(f"Failed to process article: {e}")
            continue

    logger.info(f"Done! Published {published_count} articles")


def list_posts():
    """List all published posts"""
    db = BlogDatabase()
    posts = db.get_all_posts()

    print(f"\nTotal posts: {len(posts)}\n")
    for post in posts:
        print(f"[{post['id']}] {post['title']}")
        print(f"    Slug: {post['slug']}")
        print(f"    Published: {post['published_at']}")
        print(f"    Views: {post['view_count']}")
        print()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Blog Management CLI')
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Parse command
    parse_parser = subparsers.add_parser('parse', help='Parse and publish articles')
    parse_parser.add_argument('-n', '--limit', type=int, default=5, help='Number of articles to parse')
    parse_parser.add_argument('-f', '--force', action='store_true', help='Force republish existing articles')

    # List command
    list_parser = subparsers.add_parser('list', help='List all posts')

    args = parser.parse_args()

    if args.command == 'parse':
        parse_and_publish(limit=args.limit, force=args.force)
    elif args.command == 'list':
        list_posts()
    else:
        parser.print_help()
