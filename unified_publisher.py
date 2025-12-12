#!/usr/bin/env python3
"""
Unified Publisher - processes ONE article from queue and publishes to site + Telegram
Runs every 30 minutes via cron to ensure consistent post spacing

Run via cron every 30 minutes:
    */30 * * * * cd /var/www/housler && python3 unified_publisher.py
"""

import os
import sys
import logging
import fcntl
from pathlib import Path
from datetime import datetime

# Load environment variables
from dotenv import load_dotenv
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    load_dotenv(env_path)

# Setup logging
log_dir = Path("/var/www/housler/logs")
if not log_dir.exists():
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

log_file = log_dir / "unified_publisher.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def fetch_article_content(url: str, source: str) -> dict:
    """
    Fetch full article content based on source type

    Returns dict with: title, content, excerpt, published_at
    """
    if source == 'yandex':
        from yandex_journal_parser import YandexJournalParser
        parser = YandexJournalParser()
        return parser.parse_article_content(url)

    elif source in ('CIAN Journal', 'cian_rss', 'RBC Realty', 'rbc'):
        from multi_rss_parser import MultiRSSParser
        parser = MultiRSSParser()
        # Reload feeds to get fresh content
        parser.get_all_articles(limit_per_source=20, language='ru')
        return parser.get_article_content(url)

    elif source == 'World Property Journal':
        from multi_rss_parser import MultiRSSParser
        parser = MultiRSSParser()
        parser.get_all_articles(limit_per_source=20, language='en')
        return parser.get_article_content(url)

    else:
        # Default: try multi_rss_parser
        from multi_rss_parser import MultiRSSParser
        parser = MultiRSSParser()
        parser.get_all_articles(limit_per_source=20)
        return parser.get_article_content(url)


def publish_one() -> dict:
    """
    Process and publish ONE article from queue

    Steps:
    1. Get next article from queue
    2. Fetch full content
    3. Rewrite with YandexGPT
    4. Generate cover with YandexART
    5. Save to blog_posts
    6. If cover exists - publish to Telegram
    7. Remove from queue

    Returns dict with result info
    """
    from blog_database import BlogDatabase, create_slug
    from yandex_gpt import YandexGPT
    from yandex_art import YandexART
    from telegram_publisher import TelegramPublisher
    from alert_bot import send_cover_alert

    db = BlogDatabase()
    result = {
        'success': False,
        'title': None,
        'error': None,
        'telegram_published': False,
        'queue_stats': {}
    }

    # Step 1: Get next article from queue
    queue_item = db.get_next_from_queue()

    if not queue_item:
        logger.info("Queue is empty, nothing to publish")
        result['queue_stats'] = db.get_queue_stats()
        return result

    queue_id = queue_item['id']
    url = queue_item['url']
    original_title = queue_item['title']
    source = queue_item['source']

    logger.info(f"Processing: [{source}] {original_title[:60]}...")

    # Mark as processing
    db.mark_queue_processing(queue_id)

    try:
        # Step 2: Fetch full content
        logger.info(f"Fetching content from: {url}")
        article = fetch_article_content(url, source)

        if not article or not article.get('content'):
            raise ValueError(f"Failed to fetch content from {url}")

        content = article['content']
        title = article.get('title') or original_title
        published_at = article.get('published_at') or datetime.now().isoformat()

        if len(content) < 100:
            raise ValueError(f"Content too short: {len(content)} chars")

        logger.info(f"Content fetched: {len(content)} chars")

        # Step 3: Rewrite with YandexGPT
        logger.info("Rewriting with YandexGPT...")
        gpt = YandexGPT()
        rewritten = gpt.rewrite_article(
            original_title=title,
            original_content=content,
            original_excerpt=article.get('excerpt')
        )

        result['title'] = rewritten['title']
        slug = create_slug(rewritten['title'])

        # Double-check slug doesn't exist
        if db.post_exists(slug):
            logger.warning(f"Slug already exists: {slug}")
            db.mark_queue_done(queue_id)
            result['error'] = 'Slug already exists'
            return result

        # Step 4: Generate cover with YandexART
        logger.info("Generating cover with YandexART...")
        art = YandexART()
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

        # Step 5: Save to blog_posts
        logger.info("Saving to database...")
        post_id = db.create_post(
            slug=slug,
            title=rewritten['title'],
            content=rewritten['content'],
            excerpt=rewritten['excerpt'],
            original_url=url,
            original_title=title,
            published_at=published_at,
            cover_image=cover_image,
            telegram_content=rewritten.get('telegram_content', '')
        )

        logger.info(f"Saved to database: ID={post_id}, slug={slug}")

        # Step 6: Publish to Telegram if cover exists
        if cover_image:
            logger.info("Publishing to Telegram...")
            telegram = TelegramPublisher()
            telegram.publish_post_with_image(
                title=rewritten['title'],
                content=rewritten['content'],
                slug=slug,
                cover_image=cover_image,
                telegram_content=rewritten.get('telegram_content', '')
            )
            db.mark_telegram_published(post_id)
            result['telegram_published'] = True
            logger.info("Published to Telegram")
        else:
            logger.info("Skipping Telegram (no cover) - will publish after cover regeneration")

        # Step 7: Remove from queue
        db.mark_queue_done(queue_id)

        result['success'] = True
        result['queue_stats'] = db.get_queue_stats()

        logger.info(f"Successfully published: {rewritten['title']}")

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to process article: {error_msg}", exc_info=True)
        db.mark_queue_failed(queue_id, error_msg)
        result['error'] = error_msg
        result['queue_stats'] = db.get_queue_stats()

    return result


def send_publisher_report(result: dict):
    """Send report to Telegram about publishing result"""
    from alert_bot import AlertBot

    bot = AlertBot()
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    queue_stats = result.get('queue_stats', {})

    if result['success']:
        tg_status = "Да" if result['telegram_published'] else "Нет (без обложки)"
        message = f"""📤 <b>Unified Publisher: успех</b>

📅 {now}

📝 <b>Опубликовано:</b>
{result['title']}

• Telegram: {tg_status}

📋 <b>Очередь:</b>
• Ожидают: {queue_stats.get('pending', 0)}
• Ошибки: {queue_stats.get('failed', 0)}"""
    else:
        if result['error']:
            message = f"""❌ <b>Unified Publisher: ошибка</b>

📅 {now}

❌ <b>Ошибка:</b>
{result['error'][:200]}

📋 <b>Очередь:</b>
• Ожидают: {queue_stats.get('pending', 0)}
• Ошибки: {queue_stats.get('failed', 0)}"""
        else:
            # Empty queue - don't send alert
            return

    bot.send_alert(message)


def run_publisher(send_report: bool = True):
    """Run unified publisher"""
    logger.info("=" * 60)
    logger.info("Unified Publisher started")

    result = publish_one()

    logger.info(f"Publisher complete: success={result['success']}")
    logger.info("=" * 60)

    if send_report and (result['success'] or result['error']):
        send_publisher_report(result)

    return result


def run_with_lock():
    """Run publisher with file locking to prevent concurrent execution"""
    lock_file = '/tmp/unified_publisher.lock'

    try:
        with open(lock_file, 'w') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return run_publisher()
    except IOError:
        logger.info("Another publisher instance is running, skipping")
        return {'success': False, 'error': 'Another instance running'}
    except Exception as e:
        logger.error(f"Publisher error: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Unified Publisher - processes one article')
    parser.add_argument(
        '--no-lock',
        action='store_true',
        help='Run without file locking (for testing)'
    )
    parser.add_argument(
        '--no-report',
        action='store_true',
        help='Do not send Telegram report'
    )

    args = parser.parse_args()

    if args.no_lock:
        run_publisher(send_report=not args.no_report)
    else:
        run_with_lock()
