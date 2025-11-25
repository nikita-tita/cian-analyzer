#!/bin/bash

#############################################
# Удаление всех статей из блога
# Использовать ОСТОРОЖНО!
#############################################

# Цвета
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

# Конфигурация
SERVER_USER="root"
SERVER_IP="91.229.8.221"
SSH_KEY="$HOME/.ssh/id_housler"

echo ""
echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${RED}  ⚠️  УДАЛЕНИЕ ВСЕХ СТАТЕЙ ИЗ БЛОГА${NC}"
echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Проверяем сколько статей сейчас
echo -e "${CYAN}Проверка текущих статей...${NC}"

CURRENT_POSTS=$(ssh -i "$SSH_KEY" "$SERVER_USER@$SERVER_IP" bash << 'ENDSSH'
cd /var/www/housler
source venv/bin/activate
python3 -c "from blog_database import BlogDatabase; db = BlogDatabase(); print(len(db.get_all_posts()))"
ENDSSH
)

if [ "$CURRENT_POSTS" = "0" ]; then
    echo -e "${YELLOW}База блога уже пустая. Удалять нечего.${NC}"
    exit 0
fi

echo -e "${YELLOW}В базе сейчас: ${RED}$CURRENT_POSTS статей${NC}"
echo ""
echo -e "${RED}ВСЕ ЭТИ СТАТЬИ БУДУТ БЕЗВОЗВРАТНО УДАЛЕНЫ!${NC}"
echo ""

# Двойное подтверждение
read -p "Вы уверены? Введите 'DELETE' для подтверждения: " CONFIRM

if [ "$CONFIRM" != "DELETE" ]; then
    echo -e "${YELLOW}⚠️  Отменено${NC}"
    exit 0
fi

echo ""
read -p "Последнее предупреждение! Введите 'YES' для окончательного удаления: " FINAL_CONFIRM

if [ "$FINAL_CONFIRM" != "YES" ]; then
    echo -e "${YELLOW}⚠️  Отменено${NC}"
    exit 0
fi

echo ""
echo -e "${CYAN}Создаю резервную копию базы данных...${NC}"

# Создаём бэкап
BACKUP_NAME="blog_backup_$(date +%Y%m%d_%H%M%S).db"

ssh -i "$SSH_KEY" "$SERVER_USER@$SERVER_IP" bash << ENDSSH
mkdir -p /var/www/housler/backups
cp /var/www/housler/blog.db /var/www/housler/backups/$BACKUP_NAME
echo "✅ Бэкап сохранён: /var/www/housler/backups/$BACKUP_NAME"
ENDSSH

echo -e "${GREEN}✅ Резервная копия создана${NC}"
echo ""

echo -e "${CYAN}Удаление всех статей...${NC}"

ssh -i "$SSH_KEY" "$SERVER_USER@$SERVER_IP" bash << 'ENDSSH'
cd /var/www/housler
sqlite3 blog.db "DELETE FROM blog_posts;"
sqlite3 blog.db "DELETE FROM sqlite_sequence WHERE name='blog_posts';"
echo "✅ Все статьи удалены"
ENDSSH

# Проверяем результат
NEW_COUNT=$(ssh -i "$SSH_KEY" "$SERVER_USER@$SERVER_IP" bash << 'ENDSSH'
cd /var/www/housler
source venv/bin/activate
python3 -c "from blog_database import BlogDatabase; db = BlogDatabase(); print(len(db.get_all_posts()))"
ENDSSH
)

echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

if [ "$NEW_COUNT" = "0" ]; then
    echo -e "${GREEN}✅ Успешно! База блога очищена${NC}"
    echo ""
    echo -e "${YELLOW}Статистика:${NC}"
    echo -e "   Удалено статей: ${RED}$CURRENT_POSTS${NC}"
    echo -e "   Осталось статей: ${GREEN}0${NC}"
    echo ""
    echo -e "${CYAN}📦 Бэкап сохранён на сервере:${NC}"
    echo -e "   /var/www/housler/backups/$BACKUP_NAME"
    echo ""
    echo -e "${YELLOW}Восстановить из бэкапа:${NC}"
    echo -e "   ssh -i $SSH_KEY $SERVER_USER@$SERVER_IP 'cp /var/www/housler/backups/$BACKUP_NAME /var/www/housler/blog.db'"
else
    echo -e "${RED}❌ Ошибка! Осталось статей: $NEW_COUNT${NC}"
fi

echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
