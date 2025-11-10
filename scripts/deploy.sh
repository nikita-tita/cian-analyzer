#!/bin/bash
# Скрипт быстрого деплоя на housler.ru

set -e  # Выход при ошибке

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Конфигурация
SSH_KEY="$HOME/.ssh/id_housler"
SERVER="root@91.229.8.221"
REMOTE_PATH="/var/www/housler"
SERVICE_NAME="housler"

echo -e "${GREEN}🚀 Деплой на housler.ru${NC}"
echo "================================"

# Шаг 1: Проверка изменений
echo -e "\n${YELLOW}📋 Проверка локальных изменений...${NC}"
if [[ -n $(git status -s) ]]; then
    echo -e "${RED}❌ Есть незакоммиченные изменения!${NC}"
    git status -s
    echo ""
    read -p "Закоммитить автоматически? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        read -p "Сообщение коммита: " commit_msg
        git add -A
        git commit -m "$commit_msg"
    else
        echo -e "${RED}Деплой отменен${NC}"
        exit 1
    fi
fi

# Шаг 2: Push в GitHub
echo -e "\n${YELLOW}📤 Push в GitHub...${NC}"
BRANCH=$(git branch --show-current)
git push origin "$BRANCH"
echo -e "${GREEN}✓ Запушено в $BRANCH${NC}"

# Шаг 3: Pull на сервере
echo -e "\n${YELLOW}📥 Pull на сервере...${NC}"
ssh -i "$SSH_KEY" "$SERVER" "cd $REMOTE_PATH && git fetch origin && git checkout $BRANCH && git pull origin $BRANCH"
echo -e "${GREEN}✓ Код обновлен на сервере${NC}"

# Шаг 4: Установка зависимостей (если нужно)
echo -e "\n${YELLOW}📦 Проверка зависимостей...${NC}"
if git diff HEAD~1 HEAD --name-only | grep -q "requirements.txt"; then
    echo "Обнаружены изменения в requirements.txt, обновляю зависимости..."
    ssh -i "$SSH_KEY" "$SERVER" "cd $REMOTE_PATH && source venv/bin/activate && pip install -r requirements.txt"
    echo -e "${GREEN}✓ Зависимости обновлены${NC}"
else
    echo "Зависимости не изменились"
fi

# Шаг 5: Перезапуск сервиса
echo -e "\n${YELLOW}🔄 Перезапуск сервиса...${NC}"
ssh -i "$SSH_KEY" "$SERVER" "systemctl restart $SERVICE_NAME"
sleep 2

# Шаг 6: Проверка статуса
echo -e "\n${YELLOW}🔍 Проверка статуса сервиса...${NC}"
if ssh -i "$SSH_KEY" "$SERVER" "systemctl is-active --quiet $SERVICE_NAME"; then
    echo -e "${GREEN}✓ Сервис запущен успешно${NC}"

    # Показываем последние логи
    echo -e "\n${YELLOW}📋 Последние 10 строк логов:${NC}"
    ssh -i "$SSH_KEY" "$SERVER" "journalctl -u $SERVICE_NAME -n 10 --no-pager"

    echo -e "\n${GREEN}✅ Деплой завершен успешно!${NC}"
    echo -e "🌐 Сайт: https://housler.ru"
else
    echo -e "${RED}❌ Ошибка запуска сервиса!${NC}"
    echo -e "\n${RED}Логи ошибок:${NC}"
    ssh -i "$SSH_KEY" "$SERVER" "journalctl -u $SERVICE_NAME -n 30 --no-pager"
    exit 1
fi
