"""
Render entry point with full Playwright support
Без моков - используется полноценный парсинг
"""

import os
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)
logger.info("Starting Render app with full Playwright support...")

# Импортируем приложение напрямую без моков
from app_new import app

# Для gunicorn
application = app

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Running on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
