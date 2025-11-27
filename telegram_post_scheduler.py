#!/usr/bin/env python3
"""
Telegram Post Scheduler
Публикует одну статью в Telegram канал
Запускается через cron каждые 30 минут
"""

import os
import sys
import logging
from pathlib import Path

# Загружаем переменные окружения из .env
from dotenv import load_dotenv
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    load_dotenv(env_path)

# Настраиваем логирование
log_dir = Path("/var/www/housler/logs")
log_dir.mkdir(exist_ok=True)

log_file = log_dir / "telegram_scheduler.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def publish_one_post():
    """Публикует одну непубликованную статью в Telegram"""
    from blog_database import BlogDatabase
    from telegram_publisher import TelegramPublisher

    db = BlogDatabase()
    tg = TelegramPublisher()

    # Получаем одну непубликованную статью
    posts = db.get_unpublished_telegram(limit=1)

    if not posts:
        logger.info("No posts to publish to Telegram")
        return False

    post = posts[0]
    logger.info(f"Publishing to Telegram: {post['title']}")

    try:
        success = tg.publish_post(
            title=post['title'],
            content=post['content'],
            slug=post['slug'],
            excerpt=post.get('excerpt')
        )

        if success:
            db.mark_telegram_published(post['id'])
            remaining = db.count_unpublished_telegram()
            logger.info(f"✓ Published: {post['title']} (remaining: {remaining})")
            return True
        else:
            logger.error(f"Failed to publish: {post['title']}")
            return False

    except Exception as e:
        logger.error(f"Error publishing to Telegram: {e}")
        return False


if __name__ == '__main__':
    publish_one_post()
