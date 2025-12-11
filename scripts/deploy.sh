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

# Шаг 7: Docker rebuild (если используется)
if ssh -i "$SSH_KEY" "$SERVER" "test -f $REMOTE_PATH/docker-compose.yml"; then
    echo -e "\n${YELLOW}🐳 Перезапуск Docker...${NC}"
    ssh -i "$SSH_KEY" "$SERVER" "cd $REMOTE_PATH && docker-compose up -d --build app 2>&1 | tail -5"
    sleep 5
    echo -e "${GREEN}✓ Docker перезапущен${NC}"
fi

# Шаг 8: Smoke-тесты
echo -e "\n${YELLOW}🧪 Smoke-тесты...${NC}"
ERRORS=0

# Тест 1: Сайт доступен
if curl -sf "https://housler.ru/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Сайт доступен${NC}"
else
    echo -e "${RED}✗ Сайт недоступен${NC}"
    ERRORS=$((ERRORS+1))
fi

# Тест 2: Блог работает
if curl -sf "https://housler.ru/blog" | grep -q "blog-entry"; then
    echo -e "${GREEN}✓ Блог работает${NC}"
else
    echo -e "${RED}✗ Блог не работает${NC}"
    ERRORS=$((ERRORS+1))
fi

# Тест 3: База данных доступна на запись
if ssh -i "$SSH_KEY" "$SERVER" "docker exec housler-app python3 -c \"from blog_database import BlogDatabase; db = BlogDatabase(); print('DB OK')\"" 2>/dev/null | grep -q "DB OK"; then
    echo -e "${GREEN}✓ База данных доступна${NC}"
else
    echo -e "${RED}✗ Проблема с базой данных${NC}"
    ERRORS=$((ERRORS+1))
fi

# Тест 4: Обложки примонтированы
COVERS_HOST=$(ssh -i "$SSH_KEY" "$SERVER" "ls /var/www/housler/static/blog/covers/*.png 2>/dev/null | wc -l")
COVERS_CONTAINER=$(ssh -i "$SSH_KEY" "$SERVER" "docker exec housler-app ls /app/static/blog/covers/*.png 2>/dev/null | wc -l")
if [ "$COVERS_HOST" = "$COVERS_CONTAINER" ] && [ "$COVERS_HOST" -gt "0" ]; then
    echo -e "${GREEN}✓ Обложки синхронизированы ($COVERS_HOST файлов)${NC}"
else
    echo -e "${RED}✗ Обложки не синхронизированы (host: $COVERS_HOST, container: $COVERS_CONTAINER)${NC}"
    ERRORS=$((ERRORS+1))
fi

if [ $ERRORS -gt 0 ]; then
    echo -e "\n${RED}⚠️  Обнаружено $ERRORS проблем! Проверьте логи.${NC}"
else
    echo -e "\n${GREEN}✅ Все тесты пройдены!${NC}"
fi
