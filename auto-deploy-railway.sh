#!/bin/bash

# Автоматический деплой на Railway через Template URL

echo "🚀 Автоматический деплой на Railway"
echo "===================================="

REPO_URL="https://github.com/nikita-tita/cian-analyzer"
BRANCH="claude/review-project-011CUrTS5jNGPrP8p61s7prx"

# Создаём Railway template URL
TEMPLATE_URL="https://railway.app/new?template=${REPO_URL}/tree/${BRANCH}"

echo ""
echo "✅ Создан автоматический деплой URL:"
echo ""
echo "$TEMPLATE_URL"
echo ""
echo "📋 Скопируйте ссылку выше и откройте в браузере."
echo "   Railway автоматически:"
echo "   - Создаст проект"
echo "   - Подключит репозиторий"
echo "   - Настроит все сервисы"
echo ""
echo "⏱️  Время деплоя: ~3 минуты"
echo ""

# Если есть xdg-open (Linux), попробуем открыть браузер
if command -v xdg-open &> /dev/null; then
    echo "🌐 Пытаюсь открыть браузер..."
    xdg-open "$TEMPLATE_URL" 2>/dev/null || true
fi

# Сохраняем URL в файл для удобства
echo "$TEMPLATE_URL" > /tmp/railway-deploy-url.txt
echo "💾 URL сохранён в: /tmp/railway-deploy-url.txt"
