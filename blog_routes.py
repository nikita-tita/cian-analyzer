"""
Blog Routes for Flask App
"""

from flask import render_template, abort, Response
from blog_database import BlogDatabase
from datetime import datetime
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

    @app.route('/sitemap.xml')
    def sitemap():
        """Generate dynamic sitemap"""
        try:
            posts = blog_db.get_all_posts()

            xml = ['<?xml version="1.0" encoding="UTF-8"?>']
            xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')

            # Homepage
            xml.append('  <url>')
            xml.append('    <loc>https://housler.ru/</loc>')
            xml.append(f'    <lastmod>{datetime.now().date().isoformat()}</lastmod>')
            xml.append('    <changefreq>weekly</changefreq>')
            xml.append('    <priority>1.0</priority>')
            xml.append('  </url>')

            # Consent page
            xml.append('  <url>')
            xml.append('    <loc>https://housler.ru/consent</loc>')
            xml.append(f'    <lastmod>{datetime.now().date().isoformat()}</lastmod>')
            xml.append('    <changefreq>monthly</changefreq>')
            xml.append('    <priority>0.5</priority>')
            xml.append('  </url>')

            # Blog index
            xml.append('  <url>')
            xml.append('    <loc>https://housler.ru/blog</loc>')
            xml.append(f'    <lastmod>{datetime.now().date().isoformat()}</lastmod>')
            xml.append('    <changefreq>daily</changefreq>')
            xml.append('    <priority>0.9</priority>')
            xml.append('  </url>')

            # Blog posts
            for post in posts:
                xml.append('  <url>')
                xml.append(f'    <loc>https://housler.ru/blog/{post["slug"]}</loc>')
                # Parse published_at date
                try:
                    pub_date = datetime.fromisoformat(post['published_at']).date().isoformat()
                except:
                    pub_date = datetime.now().date().isoformat()
                xml.append(f'    <lastmod>{pub_date}</lastmod>')
                xml.append('    <changefreq>monthly</changefreq>')
                xml.append('    <priority>0.8</priority>')
                xml.append('  </url>')

            xml.append('</urlset>')

            return Response('\n'.join(xml), mimetype='application/xml')
        except Exception as e:
            logger.error(f"Error generating sitemap: {e}")
            abort(500)

    logger.info("Blog routes registered")
