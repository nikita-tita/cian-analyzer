"""
Хранилище для статей блога (JSON файл)
"""

import os
import json
import logging
from typing import List, Optional, Dict
from datetime import datetime
import uuid
from pathlib import Path

from src.models.blog import BlogArticle, BlogListResponse

logger = logging.getLogger(__name__)


class BlogStorage:
    """Хранилище статей блога в JSON файле"""

    def __init__(self, storage_path: str = "data/blog_articles.json"):
        """
        Args:
            storage_path: Путь к JSON файлу для хранения статей
        """
        self.storage_path = storage_path
        self._ensure_storage_exists()

    def _ensure_storage_exists(self):
        """Создает файл хранилища если его нет"""
        storage_dir = os.path.dirname(self.storage_path)
        if storage_dir and not os.path.exists(storage_dir):
            os.makedirs(storage_dir, exist_ok=True)

        if not os.path.exists(self.storage_path):
            self._save_articles([])

    def _load_articles(self) -> List[Dict]:
        """Загружает статьи из JSON файла"""
        try:
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Ошибка загрузки статей: {e}")
            return []

    def _save_articles(self, articles: List[Dict]):
        """Сохраняет статьи в JSON файл"""
        try:
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(articles, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"Ошибка сохранения статей: {e}")
            raise

    def create(self, article: BlogArticle) -> BlogArticle:
        """
        Создает новую статью

        Args:
            article: Объект статьи

        Returns:
            Созданная статья с ID
        """
        # Генерируем ID если его нет
        if not article.id:
            article.id = str(uuid.uuid4())

        # Устанавливаем дату публикации
        if not article.published_date:
            article.published_date = datetime.now()

        # Загружаем существующие статьи
        articles = self._load_articles()

        # Проверяем уникальность slug
        existing_slugs = [a.get('slug') for a in articles]
        original_slug = article.slug
        counter = 1
        while article.slug in existing_slugs:
            article.slug = f"{original_slug}-{counter}"
            counter += 1

        # Добавляем новую статью
        articles.append(article.dict())

        # Сохраняем
        self._save_articles(articles)

        logger.info(f"Создана статья: {article.id} - {article.title}")
        return article

    def get_by_id(self, article_id: str) -> Optional[BlogArticle]:
        """
        Получает статью по ID

        Args:
            article_id: ID статьи

        Returns:
            Статья или None
        """
        articles = self._load_articles()

        for article_data in articles:
            if article_data.get('id') == article_id:
                return BlogArticle(**article_data)

        return None

    def get_by_slug(self, slug: str) -> Optional[BlogArticle]:
        """
        Получает статью по slug

        Args:
            slug: Slug статьи

        Returns:
            Статья или None
        """
        articles = self._load_articles()

        for article_data in articles:
            if article_data.get('slug') == slug:
                return BlogArticle(**article_data)

        return None

    def get_all(
        self,
        status: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "published_date",
        order_desc: bool = True
    ) -> BlogListResponse:
        """
        Получает список статей с фильтрацией и пагинацией

        Args:
            status: Фильтр по статусу (published, draft, archived)
            category: Фильтр по категории
            limit: Количество статей на странице
            offset: Смещение для пагинации
            order_by: Поле для сортировки
            order_desc: Сортировать по убыванию

        Returns:
            BlogListResponse с списком статей и метаданными
        """
        articles = self._load_articles()

        # Фильтрация
        filtered = []
        for article_data in articles:
            # Фильтр по статусу
            if status and article_data.get('status') != status:
                continue

            # Фильтр по категории
            if category and article_data.get('category') != category:
                continue

            filtered.append(article_data)

        # Сортировка
        try:
            filtered.sort(
                key=lambda x: x.get(order_by, ''),
                reverse=order_desc
            )
        except Exception as e:
            logger.warning(f"Ошибка сортировки: {e}")

        # Пагинация
        total = len(filtered)
        paginated = filtered[offset:offset + limit]

        # Преобразуем в объекты BlogArticle
        article_objects = []
        for article_data in paginated:
            try:
                article_objects.append(BlogArticle(**article_data))
            except Exception as e:
                logger.warning(f"Ошибка преобразования статьи: {e}")
                continue

        # Вычисляем метаданные пагинации
        page = (offset // limit) + 1 if limit > 0 else 1
        total_pages = (total + limit - 1) // limit if limit > 0 else 1

        return BlogListResponse(
            articles=article_objects,
            total=total,
            page=page,
            per_page=limit,
            total_pages=total_pages
        )

    def update(self, article_id: str, updates: Dict) -> Optional[BlogArticle]:
        """
        Обновляет статью

        Args:
            article_id: ID статьи
            updates: Словарь с обновлениями

        Returns:
            Обновленная статья или None
        """
        articles = self._load_articles()

        for i, article_data in enumerate(articles):
            if article_data.get('id') == article_id:
                # Применяем обновления
                article_data.update(updates)
                article_data['updated_date'] = datetime.now().isoformat()

                # Сохраняем
                articles[i] = article_data
                self._save_articles(articles)

                logger.info(f"Обновлена статья: {article_id}")
                return BlogArticle(**article_data)

        return None

    def delete(self, article_id: str) -> bool:
        """
        Удаляет статью

        Args:
            article_id: ID статьи

        Returns:
            True если удалено, False если не найдено
        """
        articles = self._load_articles()

        filtered = [a for a in articles if a.get('id') != article_id]

        if len(filtered) < len(articles):
            self._save_articles(filtered)
            logger.info(f"Удалена статья: {article_id}")
            return True

        return False

    def increment_views(self, article_id: str):
        """Увеличивает счетчик просмотров статьи"""
        articles = self._load_articles()

        for i, article_data in enumerate(articles):
            if article_data.get('id') == article_id:
                article_data['views'] = article_data.get('views', 0) + 1
                articles[i] = article_data
                self._save_articles(articles)
                break

    def increment_likes(self, article_id: str):
        """Увеличивает счетчик лайков статьи"""
        articles = self._load_articles()

        for i, article_data in enumerate(articles):
            if article_data.get('id') == article_id:
                article_data['likes'] = article_data.get('likes', 0) + 1
                articles[i] = article_data
                self._save_articles(articles)
                break

    def get_featured(self, limit: int = 5) -> List[BlogArticle]:
        """
        Получает избранные статьи

        Args:
            limit: Максимальное количество

        Returns:
            Список избранных статей
        """
        articles = self._load_articles()

        featured = [
            BlogArticle(**a) for a in articles
            if a.get('featured') and a.get('status') == 'published'
        ]

        # Сортируем по дате публикации
        featured.sort(key=lambda x: x.published_date, reverse=True)

        return featured[:limit]

    def get_latest(self, limit: int = 10) -> List[BlogArticle]:
        """
        Получает последние опубликованные статьи

        Args:
            limit: Максимальное количество

        Returns:
            Список последних статей
        """
        response = self.get_all(
            status='published',
            limit=limit,
            order_by='published_date',
            order_desc=True
        )
        return response.articles

    def get_categories(self) -> List[Dict[str, any]]:
        """
        Получает список категорий с количеством статей

        Returns:
            Список словарей {"category": str, "count": int}
        """
        articles = self._load_articles()

        # Подсчитываем количество статей в каждой категории
        category_counts = {}
        for article_data in articles:
            if article_data.get('status') != 'published':
                continue

            category = article_data.get('category', 'Недвижимость')
            category_counts[category] = category_counts.get(category, 0) + 1

        # Преобразуем в список
        categories = [
            {"category": cat, "count": count}
            for cat, count in category_counts.items()
        ]

        # Сортируем по количеству статей
        categories.sort(key=lambda x: x['count'], reverse=True)

        return categories
