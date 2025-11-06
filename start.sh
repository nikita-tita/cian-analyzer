#!/bin/bash

echo "=========================================="
echo "🚀 Cian Analyzer - Автозапуск"
echo "=========================================="
echo ""

# Проверка Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не установлен!"
    echo "📥 Скачайте Docker: https://www.docker.com/get-started"
    exit 1
fi

echo "✅ Docker найден"
echo ""

# Проверка docker-compose
if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose не установлен!"
    echo "📥 Установите: https://docs.docker.com/compose/install/"
    exit 1
fi

echo "✅ docker-compose найден"
echo ""

# Создание .env если нет
if [ ! -f .env ]; then
    echo "📝 Создаю .env файл..."
    cat > .env << 'ENVEOF'
POSTGRES_PASSWORD=cian_secure_password_123
SECRET_KEY=super-secret-key-change-in-production
LOG_LEVEL=INFO
CACHE_ENABLED=true
ASYNC_MAX_CONCURRENT=5
ENVEOF
    echo "✅ .env создан"
fi

echo ""
echo "=========================================="
echo "🚀 Запускаю приложение..."
echo "=========================================="
echo ""
echo "Подождите 2-3 минуты пока всё запустится..."
echo ""

# Запуск
docker-compose up

