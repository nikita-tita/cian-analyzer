#!/usr/bin/env python3
"""
Blog Management CLI
Parse articles from CIAN magazine and publish to blog
"""

import argparse
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Lazy imports to avoid loading playwright for RSS-only usage
from yandex_gpt import YandexGPT
from blog_database import BlogDatabase
from telegram_publisher import TelegramPublisher

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_and_publish(limit: int = 5, force: bool = False):
    """Parse articles from CIAN and publish to blog"""
    from blog_parser_playwright import CianMagazineParserPlaywright

    logger.info(f"Starting to parse {limit} articles from CIAN magazine...")

    parser = CianMagazineParserPlaywright(headless=True)
    gpt = YandexGPT()
    db = BlogDatabase()
    telegram = TelegramPublisher()

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

            # Публикуем в Telegram
            telegram.publish_post(
                title=rewritten['title'],
                content=rewritten['content'],
                slug=slug
            )

            published_count += 1

        except Exception as e:
            logger.error(f"Failed to process article: {e}")
            continue

    logger.info(f"Done! Published {published_count} articles")


def parse_yandex_news(limit: int = 5, force: bool = False):
    """Parse news from Yandex Realty Journal and publish to blog"""
    from yandex_journal_parser import YandexJournalParser

    logger.info(f"Starting to parse {limit} news from Yandex Realty Journal...")

    parser = YandexJournalParser()
    gpt = YandexGPT()
    db = BlogDatabase()
    telegram = TelegramPublisher()

    # Get list of articles
    articles = parser.get_recent_articles(limit=limit * 2)
    logger.info(f"Found {len(articles)} articles")

    published_count = 0

    for article_preview in articles:
        if published_count >= limit:
            break

        try:
            url = article_preview['url']
            logger.info(f"Processing: {article_preview['title']}")

            # Create slug
            slug = parser.create_slug(article_preview['title'])

            # Check if exists
            if db.post_exists(slug) and not force:
                logger.info(f"Article already exists: {slug}")
                continue

            # Parse full content
            full_article = parser.parse_article_content(url)
            if not full_article:
                logger.warning(f"Failed to parse article content: {url}")
                continue

            # Rewrite with Yandex GPT
            logger.info("Rewriting article with Yandex GPT...")
            rewritten = gpt.rewrite_article(
                original_title=full_article['title'],
                original_content=full_article['content'],
                original_excerpt=article_preview.get('excerpt')
            )

            # Save to DB
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

            # Публикуем в Telegram
            telegram.publish_post(
                title=rewritten['title'],
                content=rewritten['content'],
                slug=slug
            )

            published_count += 1

        except Exception as e:
            logger.error(f"Failed to process article: {e}")
            continue

    logger.info(f"Done! Published {published_count} articles from Yandex")


def parse_cian_rss(limit: int = 5, force: bool = False):
    """Parse news from CIAN RSS feed and publish to blog"""
    from cian_rss_parser import CianRSSParser

    logger.info(f"Starting to parse {limit} news from CIAN RSS feed...")

    parser = CianRSSParser()
    gpt = YandexGPT()
    db = BlogDatabase()
    telegram = TelegramPublisher()

    # Get list of articles from RSS
    articles = parser.get_recent_articles(limit=limit * 2)
    logger.info(f"Found {len(articles)} articles in RSS feed")

    published_count = 0

    for article_preview in articles:
        if published_count >= limit:
            break

        try:
            url = article_preview['url']
            logger.info(f"Processing: {article_preview['title']}")

            # Create slug
            slug = parser.create_slug(article_preview['title'])

            # Check if exists
            if db.post_exists(slug) and not force:
                logger.info(f"Article already exists: {slug}")
                continue

            # Get full content from RSS
            full_article = parser.parse_article_content(url)
            if not full_article:
                logger.warning(f"Failed to get article content: {url}")
                continue

            # Rewrite with Yandex GPT
            logger.info("Rewriting article with Yandex GPT...")
            rewritten = gpt.rewrite_article(
                original_title=full_article['title'],
                original_content=full_article['content'],
                original_excerpt=article_preview.get('excerpt')
            )

            # Save to DB
            post_id = db.create_post(
                slug=slug,
                title=rewritten['title'],
                content=rewritten['content'],
                excerpt=rewritten['excerpt'],
                original_url=url,
                original_title=full_article['title'],
                published_at=full_article['published_at']
            )

            logger.info(f"Published: {rewritten['title']} (ID: {post_id})")

            # Publish to Telegram
            telegram.publish_post(
                title=rewritten['title'],
                content=rewritten['content'],
                slug=slug
            )

            published_count += 1

        except Exception as e:
            logger.error(f"Failed to process article: {e}")
            continue

    logger.info(f"Done! Published {published_count} articles from CIAN RSS")


def parse_multi_rss(limit_per_source: int = 3, force: bool = False, language: str = None):
    """Parse news from multiple RSS sources and publish to blog"""
    from multi_rss_parser import MultiRSSParser

    logger.info(f"Starting multi-source RSS parsing (limit={limit_per_source} per source)...")

    parser = MultiRSSParser()
    gpt = YandexGPT()
    db = BlogDatabase()
    telegram = TelegramPublisher()

    # Get articles based on language filter
    if language == 'ru':
        articles = parser.get_russian_articles(limit_per_source)
    elif language == 'en':
        articles = parser.get_international_articles(limit_per_source)
    else:
        articles = parser.get_all_articles(limit_per_source)

    logger.info(f"Found {len(articles)} articles from all sources")

    # Filter to only articles with full text
    articles_with_content = [a for a in articles if a.get('has_full_text') and a.get('content')]
    logger.info(f"Articles with full text: {len(articles_with_content)}")

    published_count = 0

    for article in articles_with_content:
        try:
            logger.info(f"Processing [{article['source']}]: {article['title']}")

            # Create slug
            slug = parser.create_slug(article['title'])

            # Check if exists
            if db.post_exists(slug) and not force:
                logger.info(f"Article already exists: {slug}")
                continue

            # Rewrite with Yandex GPT
            logger.info("Rewriting article with Yandex GPT...")
            rewritten = gpt.rewrite_article(
                original_title=article['title'],
                original_content=article['content'],
                original_excerpt=article.get('excerpt')
            )

            # Save to DB
            post_id = db.create_post(
                slug=slug,
                title=rewritten['title'],
                content=rewritten['content'],
                excerpt=rewritten['excerpt'],
                original_url=article['url'],
                original_title=article['title'],
                published_at=article.get('published_date') or datetime.now().isoformat()
            )

            logger.info(f"Published: {rewritten['title']} (ID: {post_id})")

            # Publish to Telegram
            telegram.publish_post(
                title=rewritten['title'],
                content=rewritten['content'],
                slug=slug
            )

            published_count += 1

        except Exception as e:
            logger.error(f"Failed to process article: {e}")
            continue

    logger.info(f"Done! Published {published_count} articles from multiple sources")


def list_sources():
    """List all configured RSS sources"""
    from multi_rss_parser import MultiRSSParser

    parser = MultiRSSParser()
    sources = parser.list_sources()

    print(f"\nConfigured RSS sources: {len(sources)}\n")
    for s in sources:
        full_text = "full text" if s['has_full_text'] else "headlines only"
        print(f"[{s['language'].upper()}] {s['name']}")
        print(f"    URL: {s['url']}")
        print(f"    Category: {s['category']} | {full_text}")
        print()


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

    # Parse command (CIAN Magazine)
    parse_parser = subparsers.add_parser('parse', help='Parse and publish articles from CIAN Magazine')
    parse_parser.add_argument('-n', '--limit', type=int, default=5, help='Number of articles to parse')
    parse_parser.add_argument('-f', '--force', action='store_true', help='Force republish existing articles')

    # Parse Yandex command
    yandex_parser = subparsers.add_parser('yandex', help='Parse and publish news from Yandex Realty Journal')
    yandex_parser.add_argument('-n', '--limit', type=int, default=5, help='Number of news to parse')
    yandex_parser.add_argument('-f', '--force', action='store_true', help='Force republish existing articles')

    # Parse CIAN RSS command
    rss_parser = subparsers.add_parser('rss', help='Parse and publish news from CIAN RSS feed (no captcha)')
    rss_parser.add_argument('-n', '--limit', type=int, default=5, help='Number of news to parse')
    rss_parser.add_argument('-f', '--force', action='store_true', help='Force republish existing articles')

    # Parse multi-source RSS command
    multi_parser = subparsers.add_parser('rss-all', help='Parse news from ALL RSS sources (CIAN, Vedomosti, RIA, World Property Journal)')
    multi_parser.add_argument('-n', '--limit', type=int, default=3, help='Number of news per source')
    multi_parser.add_argument('-f', '--force', action='store_true', help='Force republish existing articles')
    multi_parser.add_argument('--lang', choices=['ru', 'en'], help='Filter by language (ru/en)')

    # List sources command
    sources_parser = subparsers.add_parser('sources', help='List all configured RSS sources')

    # List command
    list_parser = subparsers.add_parser('list', help='List all posts')

    args = parser.parse_args()

    if args.command == 'parse':
        parse_and_publish(limit=args.limit, force=args.force)
    elif args.command == 'yandex':
        parse_yandex_news(limit=args.limit, force=args.force)
    elif args.command == 'rss':
        parse_cian_rss(limit=args.limit, force=args.force)
    elif args.command == 'rss-all':
        parse_multi_rss(limit_per_source=args.limit, force=args.force, language=args.lang)
    elif args.command == 'sources':
        list_sources()
    elif args.command == 'list':
        list_posts()
    else:
        parser.print_help()
