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
from yandex_art import YandexART
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
    art = YandexART()
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

            # Генерируем обложку (не блокирует публикацию при ошибке)
            cover_image = None
            try:
                cover_image = art.generate_cover(
                    title=rewritten['title'],
                    slug=slug
                )
            except Exception as e:
                logger.warning(f"Cover generation failed, continuing without cover: {e}")

            # Сохраняем в БД
            post_id = db.create_post(
                slug=slug,
                title=rewritten['title'],
                content=rewritten['content'],
                excerpt=rewritten['excerpt'],
                original_url=url,
                original_title=full_article['title'],
                published_at=full_article['published_at'],
                cover_image=cover_image
            )

            logger.info(f"✓ Published: {rewritten['title']} (ID: {post_id})")

            # Публикуем в Telegram с обложкой
            telegram.publish_post_with_image(
                title=rewritten['title'],
                content=rewritten['content'],
                slug=slug,
                cover_image=cover_image
            )
            # Mark as published to avoid duplicate from scheduler
            db.mark_telegram_published(post_id)

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
    art = YandexART()
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

            # Generate cover (doesn't block publishing on error)
            cover_image = None
            try:
                cover_image = art.generate_cover(
                    title=rewritten['title'],
                    slug=slug
                )
            except Exception as e:
                logger.warning(f"Cover generation failed, continuing without cover: {e}")

            # Save to DB
            post_id = db.create_post(
                slug=slug,
                title=rewritten['title'],
                content=rewritten['content'],
                excerpt=rewritten['excerpt'],
                original_url=url,
                original_title=full_article['title'],
                published_at=full_article['published_at'],
                cover_image=cover_image
            )

            logger.info(f"✓ Published: {rewritten['title']} (ID: {post_id})")

            # Publish to Telegram with cover
            telegram.publish_post_with_image(
                title=rewritten['title'],
                content=rewritten['content'],
                slug=slug,
                cover_image=cover_image
            )
            # Mark as published to avoid duplicate from scheduler
            db.mark_telegram_published(post_id)

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
    art = YandexART()
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

            # Generate cover (doesn't block publishing on error)
            cover_image = None
            try:
                cover_image = art.generate_cover(
                    title=rewritten['title'],
                    slug=slug
                )
            except Exception as e:
                logger.warning(f"Cover generation failed, continuing without cover: {e}")

            # Save to DB
            post_id = db.create_post(
                slug=slug,
                title=rewritten['title'],
                content=rewritten['content'],
                excerpt=rewritten['excerpt'],
                original_url=url,
                original_title=full_article['title'],
                published_at=full_article['published_at'],
                cover_image=cover_image
            )

            logger.info(f"Published: {rewritten['title']} (ID: {post_id})")

            # Publish to Telegram with cover
            telegram.publish_post_with_image(
                title=rewritten['title'],
                content=rewritten['content'],
                slug=slug,
                cover_image=cover_image
            )
            # Mark as published to avoid duplicate from scheduler
            db.mark_telegram_published(post_id)

            published_count += 1

        except Exception as e:
            logger.error(f"Failed to process article: {e}")
            continue

    logger.info(f"Done! Published {published_count} articles from CIAN RSS")


def parse_multi_rss(limit_per_source: int = 3, force: bool = False, language: str = None):
    """Parse news from multiple RSS sources and publish to blog"""
    from multi_rss_parser import MultiRSSParser
    from alert_bot import ParseResult, send_parse_report

    logger.info(f"Starting multi-source RSS parsing (limit={limit_per_source} per source)...")

    # Result for reporting
    result = ParseResult(source="RSS Multi-Source")

    try:
        parser = MultiRSSParser()
        gpt = YandexGPT()
        art = YandexART()
        db = BlogDatabase()
        telegram = TelegramPublisher()

        # Get articles based on language filter
        if language == 'ru':
            articles = parser.get_russian_articles(limit_per_source)
        elif language == 'en':
            articles = parser.get_international_articles(limit_per_source)
        else:
            articles = parser.get_all_articles(limit_per_source)

        result.articles_found = len(articles)
        logger.info(f"Found {len(articles)} articles from all sources")

        # Filter to only articles with full text
        articles_with_content = [a for a in articles if a.get('has_full_text') and a.get('content')]
        logger.info(f"Articles with full text: {len(articles_with_content)}")

        for article in articles_with_content:
            try:
                logger.info(f"Processing [{article['source']}]: {article['title']}")

                # Create slug
                slug = parser.create_slug(article['title'])

                # Check if exists
                if db.post_exists(slug) and not force:
                    logger.info(f"Article already exists: {slug}")
                    continue

                result.articles_parsed += 1

                # Rewrite with Yandex GPT
                logger.info("Rewriting article with Yandex GPT...")
                rewritten = gpt.rewrite_article(
                    original_title=article['title'],
                    original_content=article['content'],
                    original_excerpt=article.get('excerpt')
                )
                result.articles_rewritten += 1

                # Track token usage
                usage = rewritten.get('usage')
                if usage:
                    result.input_tokens += usage.input_tokens
                    result.output_tokens += usage.output_tokens

                # Generate cover (doesn't block publishing on error)
                cover_image = None
                try:
                    cover_image = art.generate_cover(
                        title=rewritten['title'],
                        slug=slug
                    )
                except Exception as e:
                    logger.warning(f"Cover generation failed, continuing without cover: {e}")

                # Save to DB
                post_id = db.create_post(
                    slug=slug,
                    title=rewritten['title'],
                    content=rewritten['content'],
                    excerpt=rewritten['excerpt'],
                    original_url=article['url'],
                    original_title=article['title'],
                    published_at=article.get('published_date') or datetime.now().isoformat(),
                    cover_image=cover_image
                )

                result.articles_published_site += 1
                result.published_titles.append(rewritten['title'])
                logger.info(f"Published: {rewritten['title']} (ID: {post_id})")

                # Publish to Telegram with cover
                telegram.publish_post_with_image(
                    title=rewritten['title'],
                    content=rewritten['content'],
                    slug=slug,
                    cover_image=cover_image
                )
                # Mark as published to avoid duplicate from scheduler
                db.mark_telegram_published(post_id)

            except Exception as e:
                result.errors.append(f"Ошибка обработки: {str(e)[:50]}")
                logger.error(f"Failed to process article: {e}")
                continue

        result.pending_telegram = db.count_unpublished_telegram()
        logger.info(f"Done! Published {result.articles_published_site} articles from multiple sources")

    except Exception as e:
        result.errors.append(f"Критическая ошибка: {str(e)}")
        logger.error(f"Fatal error in RSS parser: {e}")

    # Send report to Telegram
    send_parse_report(result)


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
        cover = post.get('cover_image') or 'No cover'
        print(f"    Cover: {cover}")
        print()


def generate_cover(slug: str, force: bool = False):
    """Generate cover for a specific post"""
    db = BlogDatabase()
    art = YandexART()

    post = db.get_post_by_slug(slug)
    if not post:
        logger.error(f"Post not found: {slug}")
        return

    # Check if cover exists
    if post.get('cover_image') and not force:
        logger.info(f"Cover already exists: {post['cover_image']}")
        return

    logger.info(f"Generating cover for: {post['title']}")

    try:
        cover_image = art.generate_cover(
            title=post['title'],
            slug=slug,
            force=force
        )

        if cover_image:
            db.update_cover_image(post['id'], cover_image)
            logger.info(f"Cover saved: {cover_image}")
        else:
            logger.error("Cover generation failed")

    except Exception as e:
        logger.error(f"Error generating cover: {e}")


def generate_all_covers(limit: int = 10, delay: int = 5):
    """Generate covers for posts without covers"""
    import time

    db = BlogDatabase()
    art = YandexART()

    posts = db.get_posts_without_cover(limit=limit)
    logger.info(f"Found {len(posts)} posts without covers")

    if not posts:
        logger.info("All posts have covers")
        return

    generated = 0
    for i, post in enumerate(posts):
        try:
            logger.info(f"[{i+1}/{len(posts)}] Generating cover for: {post['title'][:50]}...")

            cover_image = art.generate_cover(
                title=post['title'],
                slug=post['slug']
            )

            if cover_image:
                db.update_cover_image(post['id'], cover_image)
                generated += 1
                logger.info(f"Cover saved: {cover_image}")

                # Delay between generations (rate limiting)
                if i < len(posts) - 1:
                    logger.debug(f"Waiting {delay}s before next generation...")
                    time.sleep(delay)
            else:
                logger.warning(f"Failed to generate cover for: {post['slug']}")

        except Exception as e:
            logger.error(f"Error generating cover for {post['slug']}: {e}")
            continue

    logger.info(f"Done! Generated {generated}/{len(posts)} covers")


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

    # Generate cover for specific post
    cover_parser = subparsers.add_parser('generate-cover', help='Generate cover for a specific post')
    cover_parser.add_argument('slug', help='Post slug')
    cover_parser.add_argument('-f', '--force', action='store_true', help='Regenerate even if exists')

    # Generate covers for all posts without covers
    all_covers_parser = subparsers.add_parser('generate-all-covers', help='Generate covers for posts without covers')
    all_covers_parser.add_argument('-n', '--limit', type=int, default=10, help='Max posts to process')
    all_covers_parser.add_argument('--delay', type=int, default=5, help='Delay between generations (seconds)')

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
    elif args.command == 'generate-cover':
        generate_cover(slug=args.slug, force=args.force)
    elif args.command == 'generate-all-covers':
        generate_all_covers(limit=args.limit, delay=args.delay)
    else:
        parser.print_help()
