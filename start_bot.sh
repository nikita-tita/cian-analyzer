#!/bin/bash

# ================================================
# Housler Telegram Bot Starter
# ================================================

set -e

echo "🤖 Starting Housler Telegram Bot..."
echo ""

# Проверяем наличие .env файла
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "📝 Please create .env file from .env.example"
    exit 1
fi

# Проверяем наличие TELEGRAM_BOT_TOKEN
if ! grep -q "TELEGRAM_BOT_TOKEN" .env; then
    echo "❌ Error: TELEGRAM_BOT_TOKEN not found in .env!"
    echo "📝 Please add your Telegram bot token to .env"
    exit 1
fi

# Проверяем, установлены ли зависимости
echo "📦 Checking dependencies..."
if ! python3 -c "import telegram" 2>/dev/null; then
    echo "📥 Installing bot dependencies..."
    pip3 install -r requirements_bot.txt
fi

# Проверяем Redis
echo "🔍 Checking Redis connection..."
if command -v redis-cli &> /dev/null; then
    if redis-cli ping > /dev/null 2>&1; then
        echo "✅ Redis is running"
    else
        echo "⚠️  Redis is not running. Starting Redis..."
        if command -v brew &> /dev/null; then
            brew services start redis
        else
            echo "❌ Please start Redis manually: sudo systemctl start redis"
        fi
    fi
else
    echo "⚠️  Redis not installed. Bot will use in-memory storage."
    echo "   For production, install Redis: brew install redis"
fi

# Запускаем бота
echo ""
echo "🚀 Starting bot..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python3 telegram_bot.py
