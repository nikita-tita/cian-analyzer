"""
Vercel entry point for the application
Использует совместимую версию без Playwright
"""

# Патчим импорты для Vercel (без Playwright)
import sys
from unittest.mock import MagicMock

# Создаем mock для playwright если его нет
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

# Vercel будет искать переменную 'app' или 'application'
application = app

if __name__ == "__main__":
    app.run()
