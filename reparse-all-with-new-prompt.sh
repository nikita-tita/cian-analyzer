#!/bin/bash

#############################################
# Перепарсинг статей с НОВЫМ улучшенным промптом
# 1. Удаляет все старые статьи (с бэкапом)
# 2. Парсит заново с требованиями:
#    - 90% оригинальность
#    - Без упоминаний источников
#    - CTA в конце каждой статьи
#############################################

# Цвета
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Конфигурация
SERVER_USER="root"
SERVER_IP="91.229.8.221"
SSH_KEY="$HOME/.ssh/id_housler"

echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}  🔄 Перепарсинг с улучшенным промптом${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

echo -e "${YELLOW}Что будет сделано:${NC}"
echo "1. Создан бэкап текущей базы данных"
echo "2. Удалены все старые статьи"
echo "3. Загружен новый yandex_gpt.py с улучшенным промптом"
echo "4. Распарсено N новых статей с требованиями:"
echo "   ✓ Оригинальность 90%+"
echo "   ✓ Без упоминаний CIAN, RBC и др."
echo "   ✓ CTA в конце каждой статьи"
echo ""

# Запрашиваем количество статей
read -p "Сколько статей распарсить? [10]: " ARTICLES_COUNT
ARTICLES_COUNT=${ARTICLES_COUNT:-10}

echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}📊 Параметры:${NC}"
echo -e "   Статей: ${YELLOW}$ARTICLES_COUNT${NC}"
echo -e "   Сервер: ${YELLOW}$SERVER_IP${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Подтверждение
read -p "Начать перепарсинг? (y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}⚠️  Отменено${NC}"
    exit 0
fi

echo ""
echo -e "${CYAN}[1/5] Проверка подключения...${NC}"

if ! ssh -i "$SSH_KEY" -o ConnectTimeout=5 "$SERVER_USER@$SERVER_IP" 'echo "OK"' > /dev/null 2>&1; then
    echo -e "${RED}❌ Не удалось подключиться к серверу${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Подключение установлено${NC}"
echo ""

echo -e "${CYAN}[2/5] Создание бэкапа и очистка базы...${NC}"

BACKUP_NAME="blog_backup_before_reparse_$(date +%Y%m%d_%H%M%S).db"

CURRENT_POSTS=$(ssh -i "$SSH_KEY" "$SERVER_USER@$SERVER_IP" bash << ENDSSH
cd /var/www/housler

# Бэкап
mkdir -p backups
cp blog.db backups/$BACKUP_NAME
echo "Бэкап: backups/$BACKUP_NAME"

# Считаем текущие статьи
source venv/bin/activate
POSTS=\$(python3 -c "from blog_database import BlogDatabase; db = BlogDatabase(); print(len(db.get_all_posts()))")
echo "Текущих статей: \$POSTS"

# Удаляем все статьи
sqlite3 blog.db "DELETE FROM blog_posts;"
sqlite3 blog.db "DELETE FROM sqlite_sequence WHERE name='blog_posts';"
echo "Статьи удалены"

# Возвращаем количество
echo \$POSTS
ENDSSH
)

CURRENT_POSTS=$(echo "$CURRENT_POSTS" | tail -1)

echo -e "${GREEN}✅ Бэкап создан: $BACKUP_NAME${NC}"
echo -e "${GREEN}✅ Удалено статей: $CURRENT_POSTS${NC}"
echo ""

echo -e "${CYAN}[3/5] Загрузка нового yandex_gpt.py...${NC}"

# Копируем обновлённый файл
scp -i "$SSH_KEY" yandex_gpt.py "$SERVER_USER@$SERVER_IP:/var/www/housler/yandex_gpt.py"

echo -e "${GREEN}✅ Файл обновлён${NC}"
echo ""

echo -e "${CYAN}[4/5] Запуск парсера с новым промптом...${NC}"
echo -e "${YELLOW}⏳ Это займёт ~3-5 минут на статью (с новым промптом дольше, но качественнее)${NC}"
echo ""

ssh -i "$SSH_KEY" "$SERVER_USER@$SERVER_IP" bash << ENDSSH
cd /var/www/housler
source venv/bin/activate

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Парсинг $ARTICLES_COUNT статей с НОВЫМ промптом..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Требования:"
echo "✓ Оригинальность 90%+"
echo "✓ Без упоминаний источников"
echo "✓ CTA в конце"
echo ""

python3 blog_cli.py parse -n $ARTICLES_COUNT

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

ENDSSH

PARSE_EXIT_CODE=$?

echo ""
echo -e "${CYAN}[5/5] Проверка результатов...${NC}"

STATS=$(ssh -i "$SSH_KEY" "$SERVER_USER@$SERVER_IP" bash << 'ENDSSH'
cd /var/www/housler
source venv/bin/activate

# Количество статей
NEW_POSTS=$(python3 -c "from blog_database import BlogDatabase; db = BlogDatabase(); print(len(db.get_all_posts()))")
echo "NEW_POSTS=$NEW_POSTS"

# Последние 3 статьи
echo "RECENT_POSTS:"
python3 -c "
from blog_database import BlogDatabase
db = BlogDatabase()
posts = db.get_all_posts(limit=3)
for i, post in enumerate(posts, 1):
    print(f'{i}. {post[\"title\"]}')
    print(f'   https://housler.ru/blog/{post[\"slug\"]}')
"
ENDSSH
)

NEW_POSTS=$(echo "$STATS" | grep "NEW_POSTS=" | cut -d'=' -f2)

echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

if [ $PARSE_EXIT_CODE -eq 0 ] && [ "$NEW_POSTS" -gt 0 ]; then
    echo -e "${GREEN}✅ Перепарсинг завершён успешно!${NC}"
    echo ""
    echo -e "${YELLOW}📊 Статистика:${NC}"
    echo -e "   Было статей: ${RED}$CURRENT_POSTS${NC}"
    echo -e "   Стало статей: ${GREEN}$NEW_POSTS${NC}"
    echo ""
    echo -e "${YELLOW}📝 Последние статьи:${NC}"
    echo "$STATS" | sed -n '/RECENT_POSTS:/,$ p' | tail -n +2
    echo ""
    echo -e "${YELLOW}🌐 Проверить на сайте:${NC}"
    echo -e "   ${CYAN}https://housler.ru/blog${NC}"
    echo ""
    echo -e "${YELLOW}📦 Бэкап старой базы:${NC}"
    echo -e "   /var/www/housler/backups/$BACKUP_NAME"
else
    echo -e "${RED}❌ Ошибка при парсинге${NC}"
    echo ""
    echo -e "${YELLOW}Восстановить из бэкапа:${NC}"
    echo -e "   ssh -i $SSH_KEY $SERVER_USER@$SERVER_IP 'cp /var/www/housler/backups/$BACKUP_NAME /var/www/housler/blog.db'"
fi

echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
