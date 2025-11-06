"""
Entry point for serverless deployments (Vercel, Render, etc.)
Использует совместимую версию без Playwright
"""

import sys
import os
from unittest.mock import MagicMock

# Создаем mock для playwright если его нет (для serverless окружений)
try:
    import playwright
except ImportError:
    sys.modules['playwright'] = MagicMock()
    sys.modules['playwright.sync_api'] = MagicMock()

# Патчим PlaywrightParser для использования SimpleParser
from src.parsers import simple_parser

# Заменяем PlaywrightParser на SimpleParser
sys.modules['src.parsers.playwright_parser'] = type(sys)('playwright_parser')
sys.modules['src.parsers.playwright_parser'].PlaywrightParser = simple_parser.SimpleParser

from app_new import app

# Для Vercel/Render
application = app

if __name__ == "__main__":
    # Для локального запуска или debug
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
