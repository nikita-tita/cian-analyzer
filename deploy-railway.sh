#!/bin/bash

# Автоматический деплой на Railway через API
# Использование: ./deploy-railway.sh YOUR_RAILWAY_TOKEN

set -e

RAILWAY_TOKEN="$1"

if [ -z "$RAILWAY_TOKEN" ]; then
    echo "❌ Ошибка: Railway token не указан"
    echo ""
    echo "Использование:"
    echo "  ./deploy-railway.sh YOUR_RAILWAY_TOKEN"
    echo ""
    echo "Как получить token:"
    echo "  1. Откройте https://railway.app"
    echo "  2. Account Settings → Tokens → Create Token"
    echo "  3. Скопируйте токен и используйте его здесь"
    exit 1
fi

echo "=========================================="
echo "🚀 Railway Auto Deploy"
echo "=========================================="
echo ""

# GraphQL API endpoint
API_URL="https://backboard.railway.app/graphql/v2"

echo "📋 Шаг 1: Получаем информацию о пользователе..."

# Get user info
USER_INFO=$(curl -s "$API_URL" \
  -H "Authorization: Bearer $RAILWAY_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "query { me { id name email } }"
  }')

USER_ID=$(echo "$USER_INFO" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)

if [ -z "$USER_ID" ]; then
    echo "❌ Ошибка авторизации. Проверьте токен."
    echo "Response: $USER_INFO"
    exit 1
fi

echo "✅ Авторизация успешна"
echo ""

echo "📋 Шаг 2: Создаём проект..."

# Create project
PROJECT_DATA=$(curl -s "$API_URL" \
  -H "Authorization: Bearer $RAILWAY_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "mutation { projectCreate(input: { name: \"cian-analyzer\" }) { id name } }"
  }')

PROJECT_ID=$(echo "$PROJECT_DATA" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)

if [ -z "$PROJECT_ID" ]; then
    echo "❌ Ошибка создания проекта"
    echo "Response: $PROJECT_DATA"
    exit 1
fi

echo "✅ Проект создан: $PROJECT_ID"
echo ""

echo "📋 Шаг 3: Подключаем GitHub репозиторий..."

# Connect GitHub repo
REPO_DATA=$(curl -s "$API_URL" \
  -H "Authorization: Bearer $RAILWAY_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"query\": \"mutation { serviceCreate(input: { projectId: \\\"$PROJECT_ID\\\", name: \\\"cian-analyzer\\\", source: { repo: \\\"nikita-tita/cian-analyzer\\\", branch: \\\"claude/review-project-011CUrTS5jNGPrP8p61s7prx\\\" } }) { id name } }\"
  }")

SERVICE_ID=$(echo "$REPO_DATA" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)

if [ -z "$SERVICE_ID" ]; then
    echo "❌ Ошибка подключения репозитория"
    echo "Response: $REPO_DATA"
    exit 1
fi

echo "✅ Репозиторий подключён: $SERVICE_ID"
echo ""

echo "📋 Шаг 4: Добавляем Redis..."

REDIS_DATA=$(curl -s "$API_URL" \
  -H "Authorization: Bearer $RAILWAY_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"query\": \"mutation { pluginCreate(input: { projectId: \\\"$PROJECT_ID\\\", type: REDIS }) { id } }\"
  }")

echo "✅ Redis добавлен"
echo ""

echo "📋 Шаг 5: Добавляем PostgreSQL..."

POSTGRES_DATA=$(curl -s "$API_URL" \
  -H "Authorization: Bearer $RAILWAY_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"query\": \"mutation { pluginCreate(input: { projectId: \\\"$PROJECT_ID\\\", type: POSTGRESQL }) { id } }\"
  }")

echo "✅ PostgreSQL добавлен"
echo ""

echo "=========================================="
echo "🎉 Деплой запущен!"
echo "=========================================="
echo ""
echo "Project ID: $PROJECT_ID"
echo "Service ID: $SERVICE_ID"
echo ""
echo "Railway сейчас деплоит приложение (~3-4 минуты)"
echo ""
echo "Откройте Railway Dashboard чтобы посмотреть прогресс:"
echo "https://railway.app/project/$PROJECT_ID"
echo ""
echo "После завершения деплоя:"
echo "1. Откройте Settings → Networking"
echo "2. Нажмите 'Generate Domain'"
echo "3. Получите URL вашего приложения"
echo ""

