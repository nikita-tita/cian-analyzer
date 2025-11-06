#!/bin/bash

# Скрипт для запуска веб-приложения Cian Parser

echo "=================================="
echo "🚀 Запуск Cian Parser Web App"
echo "=================================="
echo ""

# Активируем виртуальное окружение
source venv/bin/activate

# Проверяем Flask
if ! python -c "import flask" 2>/dev/null; then
    echo "📦 Установка Flask..."
    pip install flask --quiet
fi

# Проверяем Playwright
if ! python -c "import playwright" 2>/dev/null; then
    echo "📦 Установка Playwright..."
    pip install playwright --quiet
    playwright install chromium
fi

echo ""
echo "✅ Все зависимости установлены"
echo ""
echo "🌐 Запуск веб-сервера..."
echo ""
echo "Откройте в браузере: http://127.0.0.1:5000"
echo ""
echo "Для остановки нажмите Ctrl+C"
echo ""

# Запускаем приложение
cd webapp
python app.py
