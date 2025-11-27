#!/usr/bin/env python3
"""
Автоматический парсер блога с логированием и алертами
Запускается через cron для регулярного пополнения контента
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path

# Загружаем переменные окружения из .env
from dotenv import load_dotenv
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    load_dotenv(env_path)

# Настраиваем логирование
log_dir = Path("/var/www/housler/logs")
log_dir.mkdir(exist_ok=True)

log_file = log_dir / "blog_parser.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def main(source: str = 'cian'):
    """
    Основная функция парсинга

    Args:
        source: Источник для парсинга ('cian', 'rbc' или 'yandex')
    """
    # Импорты
    from blog_parser_playwright import CianMagazineParserPlaywright
    from rbc_realty_parser import RBCRealtyParser
    from yandex_journal_parser import YandexJournalParser
    from yandex_gpt import YandexGPT
    from blog_database import BlogDatabase
    from alert_bot import ParseResult, send_parse_report

    # Результат для отчёта
    result = ParseResult(source=source.upper())

    try:
        logger.info("=" * 60)
        logger.info(f"Starting automated blog parsing from {source.upper()}")

        # Выбираем парсер в зависимости от источника
        if source.lower() == 'rbc':
            parser = RBCRealtyParser(headless=True)
            source_name = "RBC Realty"
        elif source.lower() == 'yandex':
            parser = YandexJournalParser(headless=True)
            source_name = "Yandex Realty Journal"
        else:
            parser = CianMagazineParserPlaywright(headless=True)
            source_name = "CIAN Magazine"

        result.source = source_name

        gpt = YandexGPT()
        db = BlogDatabase()

        # Текущее количество статей
        current_posts = db.get_all_posts()
        logger.info(f"Current posts in database: {len(current_posts)}")

        # Получаем статьи
        logger.info(f"Fetching articles from {source_name}...")
        articles = parser.get_recent_articles(limit=20)
        result.articles_found = len(articles)
        logger.info(f"Found {len(articles)} articles from {source_name}")

        if not articles:
            result.errors.append(f"Не найдено статей на {source_name}")
            logger.warning("No articles found, exiting")
            send_parse_report(result)
            return

        # Парсим и публикуем новые статьи
        target_count = 10

        for article_preview in articles:
            if result.articles_published_site >= target_count:
                break

            try:
                url = article_preview['url']
                title = article_preview['title']

                # Создаем slug
                slug = parser.create_slug(title)

                # Проверяем существует ли
                if db.post_exists(slug):
                    logger.info(f"Article already exists, skipping: {slug}")
                    continue

                logger.info(f"Processing new article: {title}")

                # Парсим полный контент
                full_article = parser.parse_article_content(url)
                if not full_article:
                    result.errors.append(f"Не удалось спарсить: {title[:50]}...")
                    logger.warning(f"Failed to parse content: {url}")
                    continue

                result.articles_parsed += 1

                # Рерайтим через Yandex GPT
                logger.info("Rewriting with Yandex GPT...")
                try:
                    rewritten = gpt.rewrite_article(
                        original_title=full_article['title'],
                        original_content=full_article['content'],
                        original_excerpt=full_article.get('excerpt')
                    )
                    result.articles_rewritten += 1
                except Exception as e:
                    result.errors.append(f"Ошибка GPT: {str(e)[:50]}")
                    logger.error(f"GPT rewrite failed: {e}")
                    continue

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

                result.articles_published_site += 1
                logger.info(f"✓ Published to site: {rewritten['title']} (ID: {post_id})")

            except Exception as e:
                result.errors.append(f"Ошибка обработки: {str(e)[:50]}")
                logger.error(f"Error processing article: {e}", exc_info=True)
                continue

        # Итоговая статистика
        final_posts = db.get_all_posts()
        result.pending_telegram = db.count_unpublished_telegram()
        logger.info(f"Published {result.articles_published_site} new articles to site")
        logger.info(f"Pending Telegram posts: {result.pending_telegram}")
        logger.info(f"Total posts in database: {len(final_posts)}")
        logger.info("Automated blog parsing completed")
        logger.info("=" * 60)

    except Exception as e:
        result.errors.append(f"Критическая ошибка: {str(e)}")
        logger.error(f"Fatal error in blog parser: {e}", exc_info=True)

    # Отправляем отчёт в Telegram
    send_parse_report(result)

    if not result.is_success and not result.is_partial_success:
        sys.exit(1)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Automated blog parser')
    parser.add_argument(
        '--source',
        choices=['cian', 'rbc', 'yandex'],
        default='cian',
        help='Source to parse articles from (default: cian)'
    )

    args = parser.parse_args()
    main(source=args.source)
