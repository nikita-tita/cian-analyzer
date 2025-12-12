"""
Database for Blog Posts
SQLite storage for parsed and rewritten articles
Includes article_queue for scheduled publishing
"""

import os
import re
import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from pathlib import Path


# === Utility functions ===

def create_slug(title: str) -> str:
    """
    Create URL-friendly slug from title (translit ru->en)
    Centralized function to avoid duplication across parsers
    """
    translit_map = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
    }
    slug = title.lower()
    for ru, en in translit_map.items():
        slug = slug.replace(ru, en)
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    slug = slug.strip('-')
    return slug[:100]  # Limit length

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
                view_count INTEGER DEFAULT 0,
                telegram_published INTEGER DEFAULT 0
            )
        ''')

        # Add telegram_published column if it doesn't exist (migration)
        try:
            c.execute('ALTER TABLE blog_posts ADD COLUMN telegram_published INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Add telegram_post_type column if it doesn't exist (migration)
        try:
            c.execute('ALTER TABLE blog_posts ADD COLUMN telegram_post_type TEXT DEFAULT "full_summary"')
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Add cover_image column if it doesn't exist (migration)
        try:
            c.execute('ALTER TABLE blog_posts ADD COLUMN cover_image TEXT DEFAULT NULL')
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Add gallery_images column if it doesn't exist (migration)
        # Stores JSON array of image paths: ["/static/blog/images/slug/1.jpg", ...]
        try:
            c.execute('ALTER TABLE blog_posts ADD COLUMN gallery_images TEXT DEFAULT NULL')
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Add telegram_content column if it doesn't exist (migration)
        # Stores pre-generated shortened content for Telegram (1200-1500 chars)
        try:
            c.execute('ALTER TABLE blog_posts ADD COLUMN telegram_content TEXT DEFAULT NULL')
        except sqlite3.OperationalError:
            pass  # Column already exists

        # === Article Queue table ===
        # Queue for articles waiting to be processed and published
        c.execute('''
            CREATE TABLE IF NOT EXISTS article_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                source TEXT NOT NULL,
                excerpt TEXT,
                priority INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                error_message TEXT,
                attempts INTEGER DEFAULT 0,
                last_attempt_at TEXT
            )
        ''')

        # Create index for faster queue queries
        c.execute('''
            CREATE INDEX IF NOT EXISTS idx_queue_status_priority
            ON article_queue(status, priority DESC, created_at ASC)
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
        published_at: Optional[str] = None,
        telegram_post_type: Optional[str] = None,
        cover_image: Optional[str] = None,
        gallery_images: Optional[List[str]] = None,
        telegram_content: Optional[str] = None
    ) -> int:
        """Create new blog post"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        now = datetime.now().isoformat()
        if not published_at:
            published_at = now

        # Set default telegram_post_type if not provided
        if telegram_post_type is None:
            telegram_post_type = "full_summary"

        # Serialize gallery_images to JSON
        gallery_json = json.dumps(gallery_images) if gallery_images else None

        c.execute('''
            INSERT INTO blog_posts
            (slug, title, excerpt, content, original_url, original_title,
             published_at, created_at, updated_at, telegram_post_type, cover_image, gallery_images, telegram_content)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (slug, title, excerpt, content, original_url, original_title,
              published_at, now, now, telegram_post_type, cover_image, gallery_json, telegram_content))

        post_id = c.lastrowid
        conn.commit()
        conn.close()

        return post_id

    def _deserialize_post(self, row: sqlite3.Row) -> Dict:
        """Convert row to dict and deserialize JSON fields"""
        post = dict(row)
        # Deserialize gallery_images from JSON
        if post.get('gallery_images'):
            try:
                post['gallery_images'] = json.loads(post['gallery_images'])
            except (json.JSONDecodeError, TypeError):
                post['gallery_images'] = []
        else:
            post['gallery_images'] = []
        return post

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
            return self._deserialize_post(row)
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

        # Validate and sanitize limit/offset to prevent SQL injection
        params = []
        if limit is not None:
            limit = int(limit)  # Ensure integer
            offset = int(offset)  # Ensure integer
            query = '''
                SELECT * FROM blog_posts
                WHERE is_published = 1
                ORDER BY published_at DESC
                LIMIT ? OFFSET ?
            '''
            params = [limit, offset]
        else:
            query = '''
                SELECT * FROM blog_posts
                WHERE is_published = 1
                ORDER BY published_at DESC
            '''

        c.execute(query, params)
        rows = c.fetchall()
        conn.close()

        return [self._deserialize_post(row) for row in rows]

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

    def get_unpublished_telegram(self, limit: int = 1) -> List[Dict]:
        """Get posts not yet published to Telegram (only with cover image)"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute('''
            SELECT * FROM blog_posts
            WHERE is_published = 1
              AND telegram_published = 0
              AND cover_image IS NOT NULL
              AND cover_image != ''
            ORDER BY created_at ASC
            LIMIT ?
        ''', (limit,))

        rows = c.fetchall()
        conn.close()

        return [self._deserialize_post(row) for row in rows]

    def mark_telegram_published(self, post_id: int):
        """Mark post as published to Telegram"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute('''
            UPDATE blog_posts
            SET telegram_published = 1
            WHERE id = ?
        ''', (post_id,))

        conn.commit()
        conn.close()

    def count_unpublished_telegram(self) -> int:
        """Count posts not yet published to Telegram (only with cover image)"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute('''
            SELECT COUNT(*) FROM blog_posts
            WHERE is_published = 1
              AND telegram_published = 0
              AND cover_image IS NOT NULL
              AND cover_image != ''
        ''')
        count = c.fetchone()[0]
        conn.close()

        return count

    def count_posts_without_cover(self) -> int:
        """Count posts without cover image (waiting for YandexART)"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute('''
            SELECT COUNT(*) FROM blog_posts
            WHERE is_published = 1
              AND (cover_image IS NULL OR cover_image = '')
        ''')
        count = c.fetchone()[0]
        conn.close()

        return count

    def update_cover_image(self, post_id: int, cover_image: str):
        """Update cover image for existing post"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute('''
            UPDATE blog_posts
            SET cover_image = ?, updated_at = ?
            WHERE id = ?
        ''', (cover_image, datetime.now().isoformat(), post_id))

        conn.commit()
        conn.close()

    def get_posts_without_cover(self, limit: int = 10) -> List[Dict]:
        """Get posts that don't have cover images"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute('''
            SELECT * FROM blog_posts
            WHERE is_published = 1 AND (cover_image IS NULL OR cover_image = '')
            ORDER BY created_at DESC
            LIMIT ?
        ''', (limit,))

        rows = c.fetchall()
        conn.close()

        return [self._deserialize_post(row) for row in rows]

    # =========================================
    # Article Queue Methods
    # =========================================

    def add_to_queue(
        self,
        url: str,
        title: str,
        source: str,
        excerpt: Optional[str] = None,
        priority: int = 0
    ) -> Optional[int]:
        """
        Add article to processing queue

        Args:
            url: Original article URL (unique)
            title: Original article title
            source: Source identifier (e.g., 'cian_rss', 'rbc', 'yandex')
            excerpt: Optional excerpt/description
            priority: Higher priority = processed first (default 0)

        Returns:
            Queue item ID or None if already exists
        """
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        try:
            c.execute('''
                INSERT INTO article_queue (url, title, source, excerpt, priority, created_at, status)
                VALUES (?, ?, ?, ?, ?, ?, 'pending')
            ''', (url, title, source, excerpt, priority, datetime.now().isoformat()))

            queue_id = c.lastrowid
            conn.commit()
            return queue_id

        except sqlite3.IntegrityError:
            # URL already in queue
            return None
        finally:
            conn.close()

    def get_next_from_queue(self) -> Optional[Dict]:
        """
        Get next article from queue for processing

        Returns highest priority pending article (FIFO within same priority)
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute('''
            SELECT * FROM article_queue
            WHERE status = 'pending'
            ORDER BY priority DESC, created_at ASC
            LIMIT 1
        ''')

        row = c.fetchone()
        conn.close()

        return dict(row) if row else None

    def mark_queue_processing(self, queue_id: int):
        """Mark queue item as currently being processed"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute('''
            UPDATE article_queue
            SET status = 'processing', last_attempt_at = ?, attempts = attempts + 1
            WHERE id = ?
        ''', (datetime.now().isoformat(), queue_id))

        conn.commit()
        conn.close()

    def mark_queue_done(self, queue_id: int):
        """Remove successfully processed item from queue"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute('DELETE FROM article_queue WHERE id = ?', (queue_id,))

        conn.commit()
        conn.close()

    def mark_queue_failed(self, queue_id: int, error: str, max_attempts: int = 3):
        """
        Mark queue item as failed

        If attempts < max_attempts: reset to pending for retry
        If attempts >= max_attempts: mark as failed permanently
        """
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # Get current attempts
        c.execute('SELECT attempts FROM article_queue WHERE id = ?', (queue_id,))
        row = c.fetchone()

        if row and row[0] >= max_attempts:
            # Max retries reached - mark as failed
            c.execute('''
                UPDATE article_queue
                SET status = 'failed', error_message = ?, last_attempt_at = ?
                WHERE id = ?
            ''', (error[:500], datetime.now().isoformat(), queue_id))
        else:
            # Retry later - reset to pending
            c.execute('''
                UPDATE article_queue
                SET status = 'pending', error_message = ?, last_attempt_at = ?
                WHERE id = ?
            ''', (error[:500], datetime.now().isoformat(), queue_id))

        conn.commit()
        conn.close()

    def is_url_in_queue(self, url: str) -> bool:
        """Check if URL is already in queue"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute('SELECT id FROM article_queue WHERE url = ?', (url,))
        result = c.fetchone()
        conn.close()

        return result is not None

    def is_url_published(self, url: str) -> bool:
        """Check if URL was already published (by original_url)"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute('SELECT id FROM blog_posts WHERE original_url = ?', (url,))
        result = c.fetchone()
        conn.close()

        return result is not None

    def get_queue_stats(self) -> Dict:
        """Get queue statistics"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        stats = {'pending': 0, 'processing': 0, 'failed': 0, 'total': 0}

        c.execute('''
            SELECT status, COUNT(*) FROM article_queue GROUP BY status
        ''')

        for row in c.fetchall():
            stats[row[0]] = row[1]

        stats['total'] = sum(stats.values())
        conn.close()

        return stats

    def cleanup_old_queue_items(self, days: int = 7):
        """Remove failed items older than specified days"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        c.execute('''
            DELETE FROM article_queue
            WHERE status = 'failed' AND created_at < ?
        ''', (cutoff,))

        deleted = c.rowcount
        conn.commit()
        conn.close()

        return deleted

    def get_queue_items(self, status: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """Get queue items for inspection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        if status:
            c.execute('''
                SELECT * FROM article_queue
                WHERE status = ?
                ORDER BY priority DESC, created_at ASC
                LIMIT ?
            ''', (status, limit))
        else:
            c.execute('''
                SELECT * FROM article_queue
                ORDER BY priority DESC, created_at ASC
                LIMIT ?
            ''', (limit,))

        rows = c.fetchall()
        conn.close()

        return [dict(row) for row in rows]
