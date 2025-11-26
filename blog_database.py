"""
Database for Blog Posts
SQLite storage for parsed and rewritten articles
"""

import os
import sqlite3
import json
from datetime import datetime
from typing import List, Optional, Dict
from pathlib import Path

# Blog database path - use environment variable or default to protected location
# In production: /var/www/housler_data/blog.db (outside git repo)
# In development: ./blog.db (local)
DEFAULT_BLOG_DB_PATH = os.environ.get(
    'BLOG_DB_PATH',
    '/var/www/housler_data/blog.db' if os.path.exists('/var/www/housler_data') else 'blog.db'
)


class BlogDatabase:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or DEFAULT_BLOG_DB_PATH
        # Ensure directory exists
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        self.init_db()

    def init_db(self):
        """Initialize database with blog_posts table"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute('''
            CREATE TABLE IF NOT EXISTS blog_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                excerpt TEXT,
                content TEXT NOT NULL,
                original_url TEXT,
                original_title TEXT,
                published_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                is_published INTEGER DEFAULT 1,
                view_count INTEGER DEFAULT 0
            )
        ''')

        conn.commit()
        conn.close()

    def create_post(
        self,
        slug: str,
        title: str,
        content: str,
        excerpt: Optional[str] = None,
        original_url: Optional[str] = None,
        original_title: Optional[str] = None,
        published_at: Optional[str] = None
    ) -> int:
        """Create new blog post"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        now = datetime.now().isoformat()
        if not published_at:
            published_at = now

        c.execute('''
            INSERT INTO blog_posts
            (slug, title, excerpt, content, original_url, original_title,
             published_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (slug, title, excerpt, content, original_url, original_title,
              published_at, now, now))

        post_id = c.lastrowid
        conn.commit()
        conn.close()

        return post_id

    def get_post_by_slug(self, slug: str) -> Optional[Dict]:
        """Get single post by slug"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute('''
            SELECT * FROM blog_posts
            WHERE slug = ? AND is_published = 1
        ''', (slug,))

        row = c.fetchone()
        conn.close()

        if row:
            return dict(row)
        return None

    def get_all_posts(
        self,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Dict]:
        """Get all published posts"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        query = '''
            SELECT * FROM blog_posts
            WHERE is_published = 1
            ORDER BY published_at DESC
        '''

        if limit:
            query += f' LIMIT {limit} OFFSET {offset}'

        c.execute(query)
        rows = c.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_recent_posts(self, limit: int = 4) -> List[Dict]:
        """Get recent posts for homepage preview"""
        return self.get_all_posts(limit=limit)

    def increment_view_count(self, slug: str):
        """Increment view count for post"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute('''
            UPDATE blog_posts
            SET view_count = view_count + 1
            WHERE slug = ?
        ''', (slug,))

        conn.commit()
        conn.close()

    def post_exists(self, slug: str) -> bool:
        """Check if post with slug exists"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute('SELECT id FROM blog_posts WHERE slug = ?', (slug,))
        result = c.fetchone()
        conn.close()

        return result is not None

    def count_posts(self) -> int:
        """Count total published posts"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute('SELECT COUNT(*) FROM blog_posts WHERE is_published = 1')
        count = c.fetchone()[0]
        conn.close()

        return count

    def get_posts_paginated(self, page: int = 1, per_page: int = 20) -> Dict:
        """Get paginated posts with metadata"""
        total = self.count_posts()
        total_pages = (total + per_page - 1) // per_page if total > 0 else 1
        offset = (page - 1) * per_page

        posts = self.get_all_posts(limit=per_page, offset=offset)

        return {
            'posts': posts,
            'page': page,
            'per_page': per_page,
            'total': total,
            'total_pages': total_pages,
            'has_prev': page > 1,
            'has_next': page < total_pages
        }
