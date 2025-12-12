#!/usr/bin/env python3
"""
Cover Regeneration Script
Генерирует обложки для статей, у которых их нет
Запускается через cron каждые 3 часа
"""

import os
import sys
import logging
import fcntl
from pathlib import Path

# Загружаем переменные окружения из .env
from dotenv import load_dotenv
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    load_dotenv(env_path)

# Настраиваем логирование
log_dir = Path("/var/www/housler/logs")
log_dir.mkdir(exist_ok=True)

log_file = log_dir / "cover_regeneration.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def regenerate_covers(limit: int = 10):
    """
    Генерирует обложки для статей без них

    Args:
        limit: Максимум статей за один запуск (чтобы не перегружать API)

    Returns:
        tuple: (успешно, неудачно)
    """
    from blog_database import BlogDatabase
    from yandex_art import YandexART
    from alert_bot import send_cover_alert, send_covers_regenerated_report

    db = BlogDatabase()
    art = YandexART()

    # Проверяем, включён ли YandexART
    if not art.enabled:
        logger.warning("YandexART disabled, skipping regeneration")
        return 0, 0

    # Получаем статьи без обложек
    posts = db.get_posts_without_cover(limit=limit)

    if not posts:
        logger.info("No posts without covers found")
        return 0, 0

    logger.info(f"Found {len(posts)} posts without covers")

    success_count = 0
    failed_count = 0
    regenerated_titles = []

    for post in posts:
        post_id = post['id']
        title = post['title']
        slug = post['slug']

        logger.info(f"Generating cover for: {title[:50]}...")

        try:
            cover_image = art.generate_cover(title=title, slug=slug)

            if cover_image:
                # Обновляем БД
                db.update_cover_image(post_id, cover_image)
                success_count += 1
                regenerated_titles.append(title)
                logger.info(f"Cover generated: {cover_image}")
            else:
                # YandexART вернул None (API ошибка или disabled)
                failed_count += 1
                error_msg = "YandexART returned None"
                logger.warning(f"Cover generation failed: {error_msg}")
                send_cover_alert(title, slug, error_msg)

        except Exception as e:
            failed_count += 1
            logger.error(f"Cover generation error: {e}")
            send_cover_alert(title, slug, str(e))

    # Итоговый отчёт
    remaining = db.count_posts_without_cover()
    logger.info(f"Regeneration complete: {success_count} success, {failed_count} failed, {remaining} remaining")

    # Отправляем алерт если что-то сгенерировали
    if success_count > 0:
        send_covers_regenerated_report(
            success_count=success_count,
            failed_count=failed_count,
            remaining=remaining,
            titles=regenerated_titles
        )

    return success_count, failed_count


def run_with_lock():
    """Запустить с file locking для предотвращения concurrent execution"""
    lock_file = '/tmp/cover_regeneration.lock'

    try:
        with open(lock_file, 'w') as f:
            # Пытаемся получить exclusive lock
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            logger.info("=" * 60)
            logger.info("Cover regeneration started")

            success, failed = regenerate_covers()

            logger.info("Cover regeneration finished")
            logger.info("=" * 60)
            return success > 0

    except IOError:
        logger.info("Another regeneration instance is running, skipping")
        return False
    except Exception as e:
        logger.error(f"Failed to acquire lock: {e}")
        return False


if __name__ == '__main__':
    run_with_lock()
