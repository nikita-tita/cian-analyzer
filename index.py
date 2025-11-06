"""
Vercel Entry Point для Production версии
Использует SimpleParser и внешние сервисы (Redis Cloud, Supabase)
"""

import sys
import os
from unittest.mock import MagicMock

# ==========================================
# Патчинг для Vercel Serverless
# ==========================================

# Mock Playwright (слишком большой для Vercel)
try:
    import playwright
except ImportError:
    sys.modules['playwright'] = MagicMock()
    sys.modules['playwright.sync_api'] = MagicMock()
    sys.modules['playwright.async_api'] = MagicMock()

# Mock Playwright Parser - заменяем на SimpleParser
from src.parsers import simple_parser

# Создаем mock модуль для playwright_parser
playwright_parser_mock = type(sys)('playwright_parser')
playwright_parser_mock.PlaywrightParser = simple_parser.SimpleParser
sys.modules['src.parsers.playwright_parser'] = playwright_parser_mock

# Mock AsyncCianParser (требует Playwright)
async_parser_mock = type(sys)('async_parser')
async_parser_mock.AsyncCianParser = simple_parser.SimpleParser
async_parser_mock.parse_urls_sync = lambda urls, **kwargs: []
async_parser_mock.search_similar_async_sync = lambda target, **kwargs: []
sys.modules['src.parsers.async_parser'] = async_parser_mock

# ==========================================
# Environment Variables для Vercel
# ==========================================

# Redis настройки (используйте Upstash Redis или Redis Cloud)
# https://upstash.com/ или https://redis.com/
os.environ.setdefault('REDIS_HOST', os.getenv('REDIS_URL', 'localhost'))
os.environ.setdefault('REDIS_PORT', '6379')
os.environ.setdefault('REDIS_PASSWORD', os.getenv('REDIS_PASSWORD', ''))

# PostgreSQL настройки (используйте Supabase, Neon или Railway)
# https://supabase.com/ или https://neon.tech/
os.environ.setdefault('POSTGRES_HOST', os.getenv('DATABASE_URL', 'localhost').split('@')[1].split(':')[0] if '@' in os.getenv('DATABASE_URL', '') else 'localhost')
os.environ.setdefault('POSTGRES_PORT', '5432')
os.environ.setdefault('POSTGRES_DB', 'cian_analyzer')

# Логирование
os.environ.setdefault('LOG_LEVEL', 'INFO')
os.environ.setdefault('LOG_JSON', 'true')  # JSON для production

# Кэширование
os.environ.setdefault('CACHE_ENABLED', 'true')
os.environ.setdefault('CACHE_MEMORY_MAX_SIZE', '50')  # Меньше для Vercel

# Flask
os.environ.setdefault('FLASK_ENV', 'production')
os.environ.setdefault('FLASK_DEBUG', 'false')

# Vercel автоматически устанавливает SECRET_KEY если не указан
if not os.getenv('SECRET_KEY'):
    import secrets
    os.environ['SECRET_KEY'] = secrets.token_hex(32)

# ==========================================
# Import Production App
# ==========================================

from app_production import app

# Vercel ищет переменную 'app' или 'application'
application = app

# ==========================================
# Health Check для Vercel
# ==========================================

@app.route('/api/vercel-health')
def vercel_health():
    """Специальный health check для Vercel"""
    from flask import jsonify
    from datetime import datetime

    return jsonify({
        'status': 'healthy',
        'environment': 'vercel',
        'timestamp': datetime.now().isoformat(),
        'parser': 'SimpleParser',
        'services': {
            'redis': bool(os.getenv('REDIS_URL')),
            'postgres': bool(os.getenv('DATABASE_URL'))
        }
    })

# ==========================================
# Info Endpoint
# ==========================================

@app.route('/api/info')
def vercel_info():
    """Информация о deployment"""
    from flask import jsonify

    return jsonify({
        'version': '2.0.0',
        'environment': 'vercel',
        'parser': 'SimpleParser (Vercel-optimized)',
        'features': {
            'redis_cache': bool(os.getenv('REDIS_URL')),
            'postgres_history': bool(os.getenv('DATABASE_URL')),
            'async_parsing': False,  # Не поддерживается на Vercel
            'playwright': False  # Слишком большой для Vercel
        },
        'limitations': {
            'max_duration': '30 seconds',
            'max_memory': '1024 MB',
            'parser_type': 'SimpleParser (HTML-only)'
        },
        'external_services': {
            'redis': os.getenv('REDIS_URL', 'not_configured')[:20] + '...' if os.getenv('REDIS_URL') else None,
            'postgres': os.getenv('DATABASE_URL', 'not_configured')[:20] + '...' if os.getenv('DATABASE_URL') else None
        }
    })

# ==========================================
# Startup Log
# ==========================================

print("=" * 60)
print("🚀 Cian Analyzer v2.0 - Vercel Deployment")
print("=" * 60)
print(f"📊 Parser: SimpleParser (Vercel-optimized)")
print(f"📊 Redis: {'✅ Configured' if os.getenv('REDIS_URL') else '⚠️ Using fallback'}")
print(f"📊 PostgreSQL: {'✅ Configured' if os.getenv('DATABASE_URL') else '⚠️ Disabled'}")
print(f"📊 Cache: ✅ Enabled")
print("=" * 60)

if __name__ == "__main__":
    # Для локального тестирования
    app.run(debug=False, host='0.0.0.0', port=5002)
