"""
Blog Routes for Flask App
"""

from flask import render_template, abort, Response, send_from_directory, request
from blog_database import BlogDatabase
import os
from datetime import datetime
import logging
import markdown2

logger = logging.getLogger(__name__)

# Initialize database
blog_db = BlogDatabase()


def register_blog_routes(app):
    """Register blog routes with Flask app"""

    @app.route('/blog')
    @app.route('/blog/page/<int:page>')
    def blog_index(page=1):
        """Blog index page with paginated posts"""
        try:
            per_page = 20  # Posts per page
            pagination = blog_db.get_posts_paginated(page=page, per_page=per_page)

            if page > pagination['total_pages'] and page > 1:
                abort(404)

            return render_template(
                'blog_index.html',
                posts=pagination['posts'],
                pagination=pagination
            )
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

            # Convert markdown to HTML
            if post.get('content'):
                post['content_html'] = markdown2.markdown(
                    post['content'],
                    extras=['fenced-code-blocks', 'tables', 'break-on-newline', 'target-blank-links']
                )

            # Get recent posts for sidebar
            recent_posts = blog_db.get_recent_posts(limit=5)

            return render_template('blog_post.html', post=post, recent_posts=recent_posts)
        except Exception as e:
            logger.error(f"Error loading blog post {slug}: {e}")
            abort(500)

    @app.route('/sitemap.xml')
    def sitemap_index():
        """Generate sitemap index for large sites"""
        try:
            posts = blog_db.get_all_posts()
            total_posts = len(posts)
            posts_per_sitemap = 1000  # Google recommends max 50,000 URLs per sitemap

            xml = ['<?xml version="1.0" encoding="UTF-8"?>']
            xml.append('<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')

            # Main sitemap (static pages)
            xml.append('  <sitemap>')
            xml.append('    <loc>https://housler.ru/sitemap-main.xml</loc>')
            xml.append(f'    <lastmod>{datetime.now().date().isoformat()}</lastmod>')
            xml.append('  </sitemap>')

            # Blog sitemaps (paginated)
            num_sitemaps = (total_posts + posts_per_sitemap - 1) // posts_per_sitemap
            for i in range(max(1, num_sitemaps)):
                xml.append('  <sitemap>')
                xml.append(f'    <loc>https://housler.ru/sitemap-blog-{i + 1}.xml</loc>')
                xml.append(f'    <lastmod>{datetime.now().date().isoformat()}</lastmod>')
                xml.append('  </sitemap>')

            xml.append('</sitemapindex>')

            return Response('\n'.join(xml), mimetype='application/xml')
        except Exception as e:
            logger.error(f"Error generating sitemap index: {e}")
            abort(500)

    @app.route('/sitemap-main.xml')
    def sitemap_main():
        """Static pages sitemap"""
        try:
            xml = ['<?xml version="1.0" encoding="UTF-8"?>']
            xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')

            # Homepage
            xml.append('  <url>')
            xml.append('    <loc>https://housler.ru/</loc>')
            xml.append(f'    <lastmod>{datetime.now().date().isoformat()}</lastmod>')
            xml.append('    <changefreq>weekly</changefreq>')
            xml.append('    <priority>1.0</priority>')
            xml.append('  </url>')

            # Blog index
            xml.append('  <url>')
            xml.append('    <loc>https://housler.ru/blog</loc>')
            xml.append(f'    <lastmod>{datetime.now().date().isoformat()}</lastmod>')
            xml.append('    <changefreq>daily</changefreq>')
            xml.append('    <priority>0.9</priority>')
            xml.append('  </url>')

            # Calculator
            xml.append('  <url>')
            xml.append('    <loc>https://housler.ru/calculator</loc>')
            xml.append(f'    <lastmod>{datetime.now().date().isoformat()}</lastmod>')
            xml.append('    <changefreq>monthly</changefreq>')
            xml.append('    <priority>0.8</priority>')
            xml.append('  </url>')

            # Consent page
            xml.append('  <url>')
            xml.append('    <loc>https://housler.ru/consent</loc>')
            xml.append(f'    <lastmod>{datetime.now().date().isoformat()}</lastmod>')
            xml.append('    <changefreq>monthly</changefreq>')
            xml.append('    <priority>0.5</priority>')
            xml.append('  </url>')

            # Privacy policy
            xml.append('  <url>')
            xml.append('    <loc>https://housler.ru/doc/clients/politiki/</loc>')
            xml.append(f'    <lastmod>{datetime.now().date().isoformat()}</lastmod>')
            xml.append('    <changefreq>monthly</changefreq>')
            xml.append('    <priority>0.5</priority>')
            xml.append('  </url>')

            xml.append('</urlset>')

            return Response('\n'.join(xml), mimetype='application/xml')
        except Exception as e:
            logger.error(f"Error generating main sitemap: {e}")
            abort(500)

    @app.route('/sitemap-blog-<int:page>.xml')
    def sitemap_blog(page):
        """Paginated blog sitemap"""
        try:
            posts_per_sitemap = 1000
            offset = (page - 1) * posts_per_sitemap

            posts = blog_db.get_all_posts()
            paginated_posts = posts[offset:offset + posts_per_sitemap]

            if not paginated_posts and page > 1:
                abort(404)

            xml = ['<?xml version="1.0" encoding="UTF-8"?>']
            xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')

            for post in paginated_posts:
                xml.append('  <url>')
                xml.append(f'    <loc>https://housler.ru/blog/{post["slug"]}</loc>')
                # Use updated_at if available, otherwise published_at
                try:
                    mod_date = post.get('updated_at') or post.get('published_at')
                    if mod_date:
                        mod_date = datetime.fromisoformat(mod_date.replace('Z', '+00:00')).date().isoformat()
                    else:
                        mod_date = datetime.now().date().isoformat()
                except:
                    mod_date = datetime.now().date().isoformat()
                xml.append(f'    <lastmod>{mod_date}</lastmod>')
                xml.append('    <changefreq>monthly</changefreq>')
                xml.append('    <priority>0.8</priority>')
                xml.append('  </url>')

            xml.append('</urlset>')

            return Response('\n'.join(xml), mimetype='application/xml')
        except Exception as e:
            logger.error(f"Error generating blog sitemap page {page}: {e}")
            abort(500)

    @app.route('/robots.txt')
    def robots_txt():
        """Serve robots.txt for SEO"""
        return send_from_directory('static', 'robots.txt', mimetype='text/plain')

    @app.route('/yandex_a22640ce66beb879.html')
    def yandex_verification():
        """Serve Yandex.Webmaster verification file"""
        return send_from_directory('static', 'yandex_a22640ce66beb879.html')

    @app.route('/yandex_9fef2cb7f5de280d.html')
    def yandex_verification_2():
        """Serve Yandex.Webmaster verification file"""
        return send_from_directory('static', 'yandex_9fef2cb7f5de280d.html')

    logger.info("Blog routes registered")
