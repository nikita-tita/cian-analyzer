#!/bin/bash

# Быстрый запуск unified dashboard
# Использование: bash QUICK_RUN.sh

echo "═══════════════════════════════════════════════════════"
echo "  Unified Real Estate Dashboard v2.0"
echo "  Быстрый запуск"
echo "═══════════════════════════════════════════════════════"
echo ""

# Проверка Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 не найден. Установите Python 3.8+"
    exit 1
fi

echo "✓ Python найден: $(python3 --version)"

# Проверка зависимостей
echo ""
echo "Проверка зависимостей..."
python3 -c "import flask" 2>/dev/null && echo "✓ Flask установлен" || echo "❌ Flask не установлен (pip install flask)"
python3 -c "import pydantic" 2>/dev/null && echo "✓ Pydantic установлен" || echo "❌ Pydantic не установлен (pip install pydantic)"

echo ""
echo "═══════════════════════════════════════════════════════"
echo "Запуск сервера..."
echo "═══════════════════════════════════════════════════════"
echo ""

cd src && python3 web_dashboard_unified.py
