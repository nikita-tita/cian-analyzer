"""
Модели данных для блога
"""

from typing import Optional, List
from pydantic import BaseModel, Field, validator
from datetime import datetime
import re


class BlogArticle(BaseModel):
    """Модель статьи блога"""

    # Основные поля
    id: Optional[str] = None  # Автоматически генерируется
    title: str = Field(..., min_length=10, max_length=200)
    slug: Optional[str] = None  # URL-friendly версия заголовка

    # Контент
    original_content: Optional[str] = None  # Оригинальный текст (для архива)
    rewritten_content: str = Field(..., min_length=100)  # Рерайченный текст с HTML разметкой
    excerpt: Optional[str] = Field(None, max_length=300)  # Краткое описание

    # Метаданные
    author: str = "Housler Team"
    published_date: datetime = Field(default_factory=datetime.now)
    updated_date: Optional[datetime] = None

    # Изображения
    cover_image: Optional[str] = None  # URL главного изображения
    images: List[str] = []  # Дополнительные изображения

    # Источник
    source_url: Optional[str] = None  # Откуда спарсили
    source_name: str = "Cian Magazine"

    # SEO
    meta_description: Optional[str] = Field(None, max_length=160)
    meta_keywords: List[str] = []

    # Категории и теги
    category: str = "Недвижимость"  # Недвижимость, Ипотека, Новостройки, Советы, Рынок
    tags: List[str] = []

    # Статистика
    views: int = 0
    likes: int = 0

    # Статус публикации
    status: str = "published"  # draft, published, archived
    featured: bool = False  # Избранная статья

    @validator('slug', always=True)
    def generate_slug(cls, v, values):
        """Автоматическая генерация slug из заголовка"""
        if v:
            return v

        title = values.get('title', '')
        if not title:
            return None

        # Транслитерация русских букв
        translit_dict = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
            'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
            'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
            'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
            'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
        }

        slug = title.lower()

        # Транслитерация
        for ru, en in translit_dict.items():
            slug = slug.replace(ru, en)

        # Убираем все кроме букв, цифр, пробелов и дефисов
        slug = re.sub(r'[^a-z0-9\s-]', '', slug)

        # Заменяем пробелы на дефисы
        slug = re.sub(r'\s+', '-', slug)

        # Убираем множественные дефисы
        slug = re.sub(r'-+', '-', slug)

        # Убираем дефисы в начале и конце
        slug = slug.strip('-')

        # Ограничиваем длину
        slug = slug[:100]

        return slug

    @validator('excerpt', always=True)
    def generate_excerpt(cls, v, values):
        """Автоматическая генерация excerpt из контента если не указан"""
        if v:
            return v

        content = values.get('rewritten_content', '')
        if not content:
            return None

        # Убираем HTML теги
        clean_text = re.sub(r'<[^>]+>', '', content)

        # Берем первые 250 символов
        excerpt = clean_text[:250].strip()

        # Обрезаем по последнему предложению
        last_dot = excerpt.rfind('.')
        if last_dot > 100:  # Минимум 100 символов
            excerpt = excerpt[:last_dot + 1]
        else:
            excerpt += '...'

        return excerpt

    @validator('meta_description', always=True)
    def generate_meta_description(cls, v, values):
        """Автоматическая генерация meta description из excerpt"""
        if v:
            return v

        excerpt = values.get('excerpt')
        if excerpt:
            # Убираем многоточие для meta description
            return excerpt.replace('...', '').strip()[:160]

        return None

    class Config:
        validate_assignment = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class BlogArticleCreate(BaseModel):
    """Модель для создания статьи"""
    title: str
    original_content: str
    source_url: Optional[str] = None
    category: str = "Недвижимость"
    tags: List[str] = []
    cover_image: Optional[str] = None


class BlogArticleUpdate(BaseModel):
    """Модель для обновления статьи"""
    title: Optional[str] = None
    rewritten_content: Optional[str] = None
    excerpt: Optional[str] = None
    cover_image: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    status: Optional[str] = None
    featured: Optional[bool] = None


class BlogListResponse(BaseModel):
    """Ответ со списком статей"""
    articles: List[BlogArticle]
    total: int
    page: int
    per_page: int
    total_pages: int
