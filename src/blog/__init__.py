"""
Модуль для работы с блогом
"""

from .yandex_gpt_rewriter import rewrite_article, YandexGPTRewriter
from .blog_storage import BlogStorage

__all__ = ['rewrite_article', 'YandexGPTRewriter', 'BlogStorage']
