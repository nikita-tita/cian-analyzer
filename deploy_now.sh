#!/bin/bash
# Быстрый деплой на production
# Использование: bash deploy_now.sh

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "═══════════════════════════════════════════════════════"
echo "🚀 PRODUCTION DEPLOYMENT - HOUSLER.RU"
echo "═══════════════════════════════════════════════════════"
echo -e "${NC}"

# Check we're in git repo
if [ ! -d .git ]; then
    echo -e "${RED}❌ Ошибка: Не git репозиторий${NC}"
    echo "Запустите скрипт из корня проекта cian-analyzer"
    exit 1
fi

echo -e "${YELLOW}📋 Проверка изменений...${NC}"
echo ""

# Show what will be deployed
WORK_BRANCH="claude/work-in-progress-01JZ3rDB2NcLvyGufzzNeFET"
CURRENT_BRANCH=$(git branch --show-current)

echo "Текущая ветка: $CURRENT_BRANCH"
echo "Ветка для деплоя: $WORK_BRANCH"
echo ""

# Fetch latest
echo -e "${YELLOW}🔄 Получение последних изменений...${NC}"
git fetch origin

# Show commits to be deployed
echo ""
echo -e "${GREEN}📦 Коммиты для деплоя:${NC}"
git log origin/main..origin/$WORK_BRANCH --oneline --color=always | head -10
echo ""

# Ask for confirmation
echo -e "${YELLOW}⚠️  Внимание!${NC}"
echo "Этот скрипт смержит изменения в main и запустит деплой."
echo ""
read -p "Продолжить? (yes/no): " -r
echo ""

if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo -e "${RED}❌ Деплой отменен${NC}"
    exit 1
fi

# Switch to main
echo -e "${YELLOW}📍 Переключение на main...${NC}"
git checkout main
git pull origin main

# Merge work branch
echo ""
echo -e "${YELLOW}🔀 Merge изменений...${NC}"
git merge origin/$WORK_BRANCH --no-ff -m "deploy: Production deployment $(date +%Y-%m-%d)

Deployed changes:
- Duplicate detection system
- Multi-source support (ЦИАН, Авито, Яндекс, ДомКлик)
- Fixed comparable addition bug
- Improved error handling
- Enhanced user messages

Branch: $WORK_BRANCH
Date: $(date -u)
"

echo -e "${GREEN}✅ Merge успешен${NC}"
echo ""

# Push to main
echo -e "${YELLOW}📤 Push в origin/main...${NC}"
git push origin main

echo ""
echo -e "${GREEN}✅ Код запушен в main${NC}"
echo ""

# Check if GitHub Actions is configured
echo -e "${YELLOW}🔍 Проверка автодеплоя...${NC}"
echo ""
echo "GitHub Actions должен автоматически запустить деплой:"
echo "  → https://github.com/nikita-tita/cian-analyzer/actions"
echo ""
echo "Если Actions настроен - деплой начнется автоматически через ~10 секунд"
echo "Если НЕ настроен - используйте ручной деплой на сервере"
echo ""

# Offer to open GitHub Actions
read -p "Открыть GitHub Actions в браузере? (y/n): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if command -v open &> /dev/null; then
        open "https://github.com/nikita-tita/cian-analyzer/actions"
    elif command -v xdg-open &> /dev/null; then
        xdg-open "https://github.com/nikita-tita/cian-analyzer/actions"
    else
        echo "Откройте вручную: https://github.com/nikita-tita/cian-analyzer/actions"
    fi
fi

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ ДЕПЛОЙ ЗАПУЩЕН${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo ""
echo "Следующие шаги:"
echo ""
echo "1. 🔍 Проверить GitHub Actions:"
echo "   https://github.com/nikita-tita/cian-analyzer/actions"
echo ""
echo "2. ⏱️  Дождаться завершения (~5 минут)"
echo ""
echo "3. 🌐 Проверить сайт:"
echo "   https://housler.ru"
echo ""
echo "4. ✅ Протестировать калькулятор:"
echo "   - Шаг 1: Парсинг объекта"
echo "   - Шаг 2: Подбор аналогов (должны найтись!)"
echo "   - Шаг 3: Анализ (должен работать без ошибок!)"
echo ""

# Offer manual deploy if needed
echo -e "${YELLOW}📖 Если автодеплой не работает:${NC}"
echo ""
echo "Ручной деплой на сервере:"
echo '```bash'
echo "ssh root@91.229.8.221"
echo "cd /var/www/housler"
echo "git pull origin main"
echo "systemctl restart housler"
echo "systemctl status housler"
echo '```'
echo ""

echo -e "${GREEN}🎉 Готово!${NC}"
