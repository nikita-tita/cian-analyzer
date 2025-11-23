"""
Blog Routes for Flask App
"""

from flask import render_template, abort
from blog_database import BlogDatabase
import logging

logger = logging.getLogger(__name__)

# Initialize database
blog_db = BlogDatabase()


def register_blog_routes(app):
    """Register blog routes with Flask app"""

    @app.route('/blog')
    def blog_index():
        """Blog index page with all posts"""
        try:
            posts = blog_db.get_all_posts()
            return render_template('blog_index.html', posts=posts)
        except Exception as e:
            logger.error(f"Error loading blog index: {e}")
            abort(500)

    @app.route('/blog/<slug>')
    def blog_post(slug):
        """Individual blog post page"""
        try:
            post = blog_db.get_post_by_slug(slug)
            if not post:
                abort(404)

            # Increment view count (fail silently if DB is readonly)
            try:
                blog_db.increment_view_count(slug)
            except Exception as e:
                logger.warning(f"Could not increment view count for {slug}: {e}")

            # Get recent posts for sidebar
            recent_posts = blog_db.get_recent_posts(limit=5)

            return render_template('blog_post.html', post=post, recent_posts=recent_posts)
        except Exception as e:
            logger.error(f"Error loading blog post {slug}: {e}")
            abort(500)

    logger.info("Blog routes registered")
