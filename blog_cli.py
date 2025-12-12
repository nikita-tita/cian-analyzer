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
from alert_bot import send_cover_alert

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

            # Генерируем обложку (обязательна для публикации в Telegram)
            cover_image = None
            try:
                cover_image = art.generate_cover(
                    title=rewritten['title'],
                    slug=slug
                )
                if not cover_image:
                    logger.warning(f"Cover generation returned None for {slug}")
                    send_cover_alert(rewritten['title'], slug, "YandexART returned None")
            except Exception as e:
                logger.warning(f"Cover generation failed: {e}")
                send_cover_alert(rewritten['title'], slug, str(e))

            # Сохраняем в БД
            post_id = db.create_post(
                slug=slug,
                title=rewritten['title'],
                content=rewritten['content'],
                excerpt=rewritten['excerpt'],
                original_url=url,
                original_title=full_article['title'],
                published_at=full_article['published_at'],
                cover_image=cover_image,
                telegram_content=rewritten.get('telegram_content', '')
            )

            logger.info(f"Published to site: {rewritten['title']} (ID: {post_id})")

            # NOTE: Telegram publishing is now handled by unified_publisher.py

            published_count += 1

        except Exception as e:
            logger.error(f"Failed to process article: {e}")
            continue

    logger.info(f"Done! Published {published_count} articles to site")


def parse_yandex_news(limit: int = 5, force: bool = False):
    """Parse news from Yandex Realty Journal and publish to blog"""
    from yandex_journal_parser import YandexJournalParser
    from alert_bot import ParseResult, send_parse_report

    logger.info(f"Starting to parse {limit} news from Yandex Realty Journal...")

    # Result for reporting
    result = ParseResult(source="Yandex Realty Journal")

    try:
        parser = YandexJournalParser()
        gpt = YandexGPT()
        art = YandexART()
        db = BlogDatabase()

        # Get list of articles
        articles = parser.get_recent_articles(limit=limit * 2)
        result.articles_found = len(articles)
        logger.info(f"Found {len(articles)} articles")

        for article_preview in articles:
            if result.articles_published_site >= limit:
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
                    result.errors.append(f"Не удалось спарсить: {url[:30]}...")
                    continue

                result.articles_parsed += 1

                # Rewrite with Yandex GPT
                logger.info("Rewriting article with Yandex GPT...")
                rewritten = gpt.rewrite_article(
                    original_title=full_article['title'],
                    original_content=full_article['content'],
                    original_excerpt=article_preview.get('excerpt')
                )
                result.articles_rewritten += 1

                # Track token usage
                usage = rewritten.get('usage')
                if usage:
                    result.input_tokens += usage.input_tokens
                    result.output_tokens += usage.output_tokens

                # Generate cover (required for Telegram publishing)
                cover_image = None
                try:
                    cover_image = art.generate_cover(
                        title=rewritten['title'],
                        slug=slug
                    )
                    if not cover_image:
                        logger.warning(f"Cover generation returned None for {slug}")
                        send_cover_alert(rewritten['title'], slug, "YandexART returned None")
                except Exception as e:
                    logger.warning(f"Cover generation failed: {e}")
                    send_cover_alert(rewritten['title'], slug, str(e))

                # Save to DB
                post_id = db.create_post(
                    slug=slug,
                    title=rewritten['title'],
                    content=rewritten['content'],
                    excerpt=rewritten['excerpt'],
                    original_url=url,
                    original_title=full_article['title'],
                    published_at=full_article['published_at'],
                    cover_image=cover_image,
                    telegram_content=rewritten.get('telegram_content', '')
                )

                result.articles_published_site += 1
                result.published_titles.append(rewritten['title'])
                logger.info(f"Published to site: {rewritten['title']} (ID: {post_id})")

                # NOTE: Telegram publishing is now handled by unified_publisher.py

            except Exception as e:
                result.errors.append(f"Ошибка: {str(e)[:50]}")
                logger.error(f"Failed to process article: {e}")
                continue

        result.pending_telegram = db.count_unpublished_telegram()
        result.pending_without_cover = db.count_posts_without_cover()
        logger.info(f"Done! Published {result.articles_published_site} articles to site from Yandex")

    except Exception as e:
        result.errors.append(f"Критическая ошибка: {str(e)}")
        logger.error(f"Fatal error in Yandex parser: {e}")

    # Send report to Telegram
    send_parse_report(result)


def parse_cian_rss(limit: int = 5, force: bool = False):
    """Parse news from CIAN RSS feed and publish to blog"""
    from cian_rss_parser import CianRSSParser

    logger.info(f"Starting to parse {limit} news from CIAN RSS feed...")

    parser = CianRSSParser()
    gpt = YandexGPT()
    art = YandexART()
    db = BlogDatabase()

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

            # Generate cover (required for Telegram publishing)
            cover_image = None
            try:
                cover_image = art.generate_cover(
                    title=rewritten['title'],
                    slug=slug
                )
                if not cover_image:
                    logger.warning(f"Cover generation returned None for {slug}")
                    send_cover_alert(rewritten['title'], slug, "YandexART returned None")
            except Exception as e:
                logger.warning(f"Cover generation failed: {e}")
                send_cover_alert(rewritten['title'], slug, str(e))

            # Save to DB
            post_id = db.create_post(
                slug=slug,
                title=rewritten['title'],
                content=rewritten['content'],
                excerpt=rewritten['excerpt'],
                original_url=url,
                original_title=full_article['title'],
                published_at=full_article['published_at'],
                cover_image=cover_image,
                telegram_content=rewritten.get('telegram_content', '')
            )

            logger.info(f"Published to site: {rewritten['title']} (ID: {post_id})")

            # NOTE: Telegram publishing is now handled by unified_publisher.py

            published_count += 1

        except Exception as e:
            logger.error(f"Failed to process article: {e}")
            continue

    logger.info(f"Done! Published {published_count} articles to site from CIAN RSS")


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

                # Generate cover (required for Telegram publishing)
                cover_image = None
                try:
                    cover_image = art.generate_cover(
                        title=rewritten['title'],
                        slug=slug
                    )
                    if not cover_image:
                        logger.warning(f"Cover generation returned None for {slug}")
                        send_cover_alert(rewritten['title'], slug, "YandexART returned None")
                except Exception as e:
                    logger.warning(f"Cover generation failed: {e}")
                    send_cover_alert(rewritten['title'], slug, str(e))

                # Save to DB
                post_id = db.create_post(
                    slug=slug,
                    title=rewritten['title'],
                    content=rewritten['content'],
                    excerpt=rewritten['excerpt'],
                    original_url=article['url'],
                    original_title=article['title'],
                    published_at=article.get('published_date') or datetime.now().isoformat(),
                    cover_image=cover_image,
                    telegram_content=rewritten.get('telegram_content', '')
                )

                result.articles_published_site += 1
                result.published_titles.append(rewritten['title'])
                logger.info(f"Published to site: {rewritten['title']} (ID: {post_id})")

                # NOTE: Telegram publishing is now handled by unified_publisher.py
                # Posts without cover will be published after cover regeneration

            except Exception as e:
                result.errors.append(f"Ошибка обработки: {str(e)[:50]}")
                logger.error(f"Failed to process article: {e}")
                continue

        result.pending_telegram = db.count_unpublished_telegram()
        result.pending_without_cover = db.count_posts_without_cover()
        logger.info(f"Done! Published {result.articles_published_site} articles to site")

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


# =========================================
# Queue Management Functions
# =========================================

def queue_stats():
    """Show article queue statistics"""
    db = BlogDatabase()
    stats = db.get_queue_stats()

    print("\n=== Article Queue Stats ===")
    print(f"Pending:    {stats.get('pending', 0)}")
    print(f"Processing: {stats.get('processing', 0)}")
    print(f"Failed:     {stats.get('failed', 0)}")
    print(f"Total:      {stats.get('total', 0)}")
    print()


def queue_list(status: str = None, limit: int = 20):
    """List items in article queue"""
    db = BlogDatabase()
    items = db.get_queue_items(status=status, limit=limit)

    if not items:
        print("\nQueue is empty")
        return

    print(f"\n=== Article Queue ({len(items)} items) ===\n")
    for item in items:
        status_icon = {'pending': '⏳', 'processing': '⚙️', 'failed': '❌'}.get(item['status'], '?')
        print(f"{status_icon} [{item['id']}] {item['title'][:60]}...")
        print(f"   Source: {item['source']} | Status: {item['status']}")
        print(f"   URL: {item['url'][:80]}...")
        if item.get('error_message'):
            print(f"   Error: {item['error_message'][:60]}...")
        print()


def queue_clear(status: str = 'failed'):
    """Clear items from queue by status"""
    db = BlogDatabase()

    if status == 'all':
        # Clear all items
        items = db.get_queue_items(limit=1000)
        for item in items:
            db.mark_queue_done(item['id'])
        print(f"Cleared {len(items)} items from queue")
    else:
        # Clear by status
        items = db.get_queue_items(status=status, limit=1000)
        for item in items:
            db.mark_queue_done(item['id'])
        print(f"Cleared {len(items)} {status} items from queue")


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

    # Queue management commands
    queue_stats_parser = subparsers.add_parser('queue-stats', help='Show article queue statistics')

    queue_list_parser = subparsers.add_parser('queue-list', help='List items in article queue')
    queue_list_parser.add_argument('--status', choices=['pending', 'processing', 'failed'], help='Filter by status')
    queue_list_parser.add_argument('-n', '--limit', type=int, default=20, help='Max items to show')

    queue_clear_parser = subparsers.add_parser('queue-clear', help='Clear items from queue')
    queue_clear_parser.add_argument('--status', choices=['pending', 'processing', 'failed', 'all'], default='failed', help='Status to clear (default: failed)')

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
    elif args.command == 'queue-stats':
        queue_stats()
    elif args.command == 'queue-list':
        queue_list(status=args.status, limit=args.limit)
    elif args.command == 'queue-clear':
        queue_clear(status=args.status)
    else:
        parser.print_help()
