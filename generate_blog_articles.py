#!/usr/bin/env python3
"""
Скрипт для генерации первых статей блога

Парсит статьи с Cian Magazine, рерайтит через Яндекс GPT и сохраняет в блог
"""

import logging
import sys
from datetime import datetime

from src.parsers.cian_magazine_parser import CianMagazineParser
from src.blog import BlogStorage, YandexGPTRewriter
from src.models.blog import BlogArticle

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def generate_blog_articles(count: int = 5, region: str = 'spb'):
    """
    Генерирует статьи для блога

    Args:
        count: Количество статей для генерации
        region: Регион (spb, msk)
    """
    logger.info(f"=== Генерация {count} статей для блога ===")

    # Инициализация компонентов
    parser = CianMagazineParser(headless=True)
    storage = BlogStorage()
    rewriter = YandexGPTRewriter()

    # Проверка Яндекс GPT
    if not rewriter.api_key or not rewriter.folder_id:
        logger.warning(
            "⚠️ Яндекс GPT не настроен. Статьи будут сохранены с базовой обработкой.\n"
            "Для рерайтинга установите переменные окружения:\n"
            "  export YANDEX_API_KEY=your_api_key\n"
            "  export YANDEX_FOLDER_ID=your_folder_id"
        )

    try:
        # Шаг 1: Парсим список статей
        logger.info(f"📰 Парсинг списка статей из Cian Magazine ({region})...")
        article_previews = parser.parse_article_list(region=region, limit=count + 5)

        if not article_previews:
            logger.error("❌ Не удалось получить список статей")
            return

        logger.info(f"✓ Получено {len(article_previews)} превью статей")

        # Шаг 2: Обрабатываем статьи
        created_count = 0

        for i, preview in enumerate(article_previews):
            if created_count >= count:
                break

            url = preview.get('url')
            if not url:
                logger.warning(f"⚠️ Пропуск статьи без URL")
                continue

            logger.info(f"\n{'='*60}")
            logger.info(f"📄 [{i+1}/{count}] Обработка статьи:")
            logger.info(f"    URL: {url}")
            logger.info(f"    Заголовок: {preview.get('title', 'Без заголовка')}")

            try:
                # Парсим полный контент
                logger.info("    ⏳ Парсинг контента...")
                article_data = parser.parse_article_content(url)

                if not article_data:
                    logger.warning("    ⚠️ Не удалось спарсить контент, пропускаем")
                    continue

                logger.info(f"    ✓ Контент получен ({len(article_data.get('content', ''))} символов)")

                # Рерайтим контент
                logger.info("    ⏳ Рерайт через Яндекс GPT...")
                rewritten_content = rewriter.rewrite_article(
                    original_content=article_data['content'],
                    title=article_data['title']
                )

                logger.info(f"    ✓ Рерайт завершен ({len(rewritten_content)} символов)")

                # Создаем статью
                article = BlogArticle(
                    title=article_data['title'],
                    original_content=article_data['content'],
                    rewritten_content=rewritten_content,
                    cover_image=article_data.get('cover_image'),
                    images=article_data.get('images', []),
                    source_url=url,
                    category=article_data.get('category', 'Недвижимость'),
                    tags=article_data.get('tags', []),
                    meta_description=article_data.get('meta_description'),
                    published_date=article_data.get('published_date', datetime.now()),
                    featured=(i == 0),  # Первая статья - избранная
                    status='published'
                )

                # Сохраняем
                logger.info("    ⏳ Сохранение в блог...")
                saved_article = storage.create(article)

                logger.info(f"    ✅ Статья сохранена!")
                logger.info(f"       ID: {saved_article.id}")
                logger.info(f"       Slug: {saved_article.slug}")
                logger.info(f"       URL: /blog/{saved_article.slug}")

                created_count += 1

            except Exception as e:
                logger.error(f"    ❌ Ошибка обработки статьи: {e}", exc_info=True)
                continue

        # Итоги
        logger.info(f"\n{'='*60}")
        logger.info(f"✅ Генерация завершена!")
        logger.info(f"   Создано статей: {created_count}/{count}")
        logger.info(f"\n🌐 Откройте блог: http://localhost:5000/blog")
        logger.info(f"{'='*60}\n")

    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Генерация статей для блога')
    parser.add_argument(
        '--count',
        type=int,
        default=5,
        help='Количество статей для генерации (по умолчанию: 5)'
    )
    parser.add_argument(
        '--region',
        type=str,
        default='spb',
        choices=['spb', 'msk'],
        help='Регион для парсинга (spb или msk)'
    )

    args = parser.parse_args()

    generate_blog_articles(count=args.count, region=args.region)
