#!/usr/bin/env python3
"""
RSS Collector - collects articles from RSS sources into processing queue
Does NOT process articles, only fills the queue for unified_publisher.py

Run via cron every 4 hours:
    30 */4 * * * cd /var/www/housler && python3 rss_collector.py --source rss
"""

import os
import sys
import logging
import argparse
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

log_file = log_dir / "rss_collector.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def collect_from_rss(limit_per_source: int = 5) -> dict:
    """
    Collect articles from multi-source RSS feeds

    Only adds new articles that are:
    - Not already in article_queue
    - Not already published in blog_posts

    Returns dict with statistics
    """
    from multi_rss_parser import MultiRSSParser
    from blog_database import BlogDatabase, create_slug

    db = BlogDatabase()
    parser = MultiRSSParser()

    stats = {'found': 0, 'added': 0, 'skipped_in_queue': 0, 'skipped_published': 0}

    try:
        # Get Russian articles with full text only
        articles = parser.get_russian_articles(limit_per_source)
        articles_with_content = [a for a in articles if a.get('has_full_text')]
        stats['found'] = len(articles_with_content)

        logger.info(f"Found {stats['found']} articles with full text from RSS")

        for article in articles_with_content:
            url = article.get('url')
            title = article.get('title')
            source = article.get('source', 'rss')

            if not url or not title:
                continue

            # Check if already in queue
            if db.is_url_in_queue(url):
                stats['skipped_in_queue'] += 1
                logger.debug(f"Already in queue: {title[:50]}...")
                continue

            # Check if already published
            if db.is_url_published(url):
                stats['skipped_published'] += 1
                logger.debug(f"Already published: {title[:50]}...")
                continue

            # Also check by slug (in case URL differs slightly)
            slug = create_slug(title)
            if db.post_exists(slug):
                stats['skipped_published'] += 1
                logger.debug(f"Slug exists: {slug}")
                continue

            # Add to queue
            queue_id = db.add_to_queue(
                url=url,
                title=title,
                source=source,
                excerpt=article.get('excerpt'),
                priority=0
            )

            if queue_id:
                stats['added'] += 1
                logger.info(f"Added to queue: [{source}] {title[:60]}...")

    except Exception as e:
        logger.error(f"Error collecting from RSS: {e}", exc_info=True)

    return stats


def collect_from_yandex(limit: int = 5) -> dict:
    """
    Collect articles from Yandex Realty Journal

    Returns dict with statistics
    """
    from yandex_journal_parser import YandexJournalParser
    from blog_database import BlogDatabase, create_slug

    db = BlogDatabase()
    parser = YandexJournalParser()

    stats = {'found': 0, 'added': 0, 'skipped_in_queue': 0, 'skipped_published': 0}

    try:
        articles = parser.get_recent_articles(limit=limit * 2)
        stats['found'] = len(articles)

        logger.info(f"Found {stats['found']} articles from Yandex Journal")

        for article in articles[:limit]:
            url = article.get('url')
            title = article.get('title')

            if not url or not title:
                continue

            # Check if already in queue
            if db.is_url_in_queue(url):
                stats['skipped_in_queue'] += 1
                continue

            # Check if already published
            if db.is_url_published(url):
                stats['skipped_published'] += 1
                continue

            # Check by slug
            slug = create_slug(title)
            if db.post_exists(slug):
                stats['skipped_published'] += 1
                continue

            # Add to queue with lower priority (RSS sources preferred)
            queue_id = db.add_to_queue(
                url=url,
                title=title,
                source='yandex',
                excerpt=article.get('excerpt'),
                priority=-1  # Lower priority than RSS
            )

            if queue_id:
                stats['added'] += 1
                logger.info(f"Added to queue: [yandex] {title[:60]}...")

    except Exception as e:
        logger.error(f"Error collecting from Yandex: {e}", exc_info=True)

    return stats


def send_collector_report(source: str, stats: dict, queue_stats: dict):
    """Send report to Telegram about collection results"""
    from alert_bot import AlertBot

    bot = AlertBot()
    now = datetime.now().strftime("%d.%m.%Y %H:%M")

    if stats['added'] > 0:
        message = f"""📥 <b>RSS Collector: {source}</b>

📅 {now}

📊 <b>Результат:</b>
• Найдено: {stats['found']}
• Добавлено в очередь: {stats['added']}
• Уже в очереди: {stats['skipped_in_queue']}
• Уже опубликовано: {stats['skipped_published']}

📋 <b>Очередь:</b>
• Ожидают: {queue_stats.get('pending', 0)}
• В обработке: {queue_stats.get('processing', 0)}
• Ошибки: {queue_stats.get('failed', 0)}"""
    else:
        message = f"""📥 <b>RSS Collector: {source}</b>

📅 {now}

Новых статей не найдено.
Очередь: {queue_stats.get('pending', 0)} статей"""

    bot.send_alert(message)


def run_collector(source: str = 'rss', limit: int = 5, send_report: bool = True):
    """Run collector with specified source"""
    from blog_database import BlogDatabase

    db = BlogDatabase()

    logger.info("=" * 60)
    logger.info(f"RSS Collector started: source={source}")

    if source == 'rss':
        stats = collect_from_rss(limit_per_source=limit)
    elif source == 'yandex':
        stats = collect_from_yandex(limit=limit)
    elif source == 'all':
        stats_rss = collect_from_rss(limit_per_source=limit)
        stats_yandex = collect_from_yandex(limit=limit)
        stats = {
            'found': stats_rss['found'] + stats_yandex['found'],
            'added': stats_rss['added'] + stats_yandex['added'],
            'skipped_in_queue': stats_rss['skipped_in_queue'] + stats_yandex['skipped_in_queue'],
            'skipped_published': stats_rss['skipped_published'] + stats_yandex['skipped_published']
        }
    else:
        logger.error(f"Unknown source: {source}")
        return

    queue_stats = db.get_queue_stats()

    logger.info(f"Collection complete: added={stats['added']}, queue_pending={queue_stats.get('pending', 0)}")
    logger.info("=" * 60)

    if send_report and stats['added'] > 0:
        send_collector_report(source, stats, queue_stats)


def run_with_lock(source: str, limit: int):
    """Run collector with file locking to prevent concurrent execution"""
    lock_file = '/tmp/rss_collector.lock'

    try:
        with open(lock_file, 'w') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            run_collector(source=source, limit=limit)
    except IOError:
        logger.info("Another collector instance is running, skipping")
    except Exception as e:
        logger.error(f"Collector error: {e}", exc_info=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='RSS Collector - fills article queue')
    parser.add_argument(
        '--source',
        choices=['rss', 'yandex', 'all'],
        default='rss',
        help='Source to collect from (default: rss)'
    )
    parser.add_argument(
        '-n', '--limit',
        type=int,
        default=5,
        help='Max articles per source (default: 5)'
    )
    parser.add_argument(
        '--no-lock',
        action='store_true',
        help='Run without file locking (for testing)'
    )

    args = parser.parse_args()

    if args.no_lock:
        run_collector(source=args.source, limit=args.limit)
    else:
        run_with_lock(source=args.source, limit=args.limit)
