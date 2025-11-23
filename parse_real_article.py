#!/usr/bin/env python3
"""
Парсинг реальной статьи с RBC и добавление на сайт
"""

import os
import sys
from dotenv import load_dotenv
from pathlib import Path
from rbc_realty_parser import RBCRealtyParser
from blog_database import BlogDatabase
import logging

env_path = Path(__file__).parent / '.env'
if env_path.exists():
    load_dotenv(env_path)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Реальная статья с RBC
ARTICLE_URL = "https://realty.rbc.ru/news/6920690f9a79470a0a50d8f1"

def main():
    logger.info("Парсинг реальной статьи с RBC Realty...")
    logger.info(f"URL: {ARTICLE_URL}")

    parser = RBCRealtyParser(headless=True)
    db = BlogDatabase()

    # Парсим статью
    article = parser.parse_article_content(ARTICLE_URL)

    if not article:
        logger.error("Не удалось спарсить статью")
        return

    logger.info(f"✓ Спарсено: {article['title']}")
    logger.info(f"  Контент: {len(article['content'])} символов")

    # Создаем slug
    slug = parser.create_slug(article['title'])

    # Проверяем существование
    if db.post_exists(slug):
        logger.warning(f"Статья уже существует: {slug}")
        return

    # Сохраняем (без рерайта, так как Yandex GPT дает 403)
    post_id = db.create_post(
        slug=slug,
        title=article['title'],
        content=article['content'],
        excerpt=article['excerpt'],
        original_url=ARTICLE_URL,
        original_title=article['title'],
        published_at=article['published_at']
    )

    logger.info(f"✓ Статья добавлена в базу (ID: {post_id})")
    logger.info(f"  HOUSLER URL: https://housler.ru/blog/{slug}")
    logger.info(f"  RBC URL: {ARTICLE_URL}")

    return {
        'housler_url': f"https://housler.ru/blog/{slug}",
        'original_url': ARTICLE_URL,
        'title': article['title']
    }

if __name__ == '__main__':
    result = main()
    if result:
        print("\n" + "="*80)
        print("РЕАЛЬНАЯ СТАТЬЯ ДОБАВЛЕНА:")
        print(f"  Заголовок: {result['title']}")
        print(f"  📍 HOUSLER: {result['housler_url']}")
        print(f"  📌 RBC ОРИГИНАЛ: {result['original_url']}")
        print("="*80)
