#!/bin/bash

#############################################
# Быстрый деплой только фронтенда
# - CSS
# - HTML templates
# - Без перезапуска приложения
#############################################

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

SERVER_USER="root"
SERVER_IP="91.229.8.221"
SSH_KEY="$HOME/.ssh/id_housler"

echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}  🎨 Деплой фронтенда (CSS + HTML)${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

echo -e "${CYAN}[1/3] Загрузка unified-minimal.css...${NC}"
scp -i "$SSH_KEY" static/css/unified-minimal.css "$SERVER_USER@$SERVER_IP:/var/www/housler/static/css/"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ CSS загружен${NC}"
else
    echo -e "${YELLOW}⚠️  Ошибка загрузки CSS${NC}"
fi
echo ""

echo -e "${CYAN}[2/3] Загрузка HTML templates...${NC}"
scp -i "$SSH_KEY" templates/*.html "$SERVER_USER@$SERVER_IP:/var/www/housler/templates/"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Templates загружены${NC}"
else
    echo -e "${YELLOW}⚠️  Ошибка загрузки templates${NC}"
fi
echo ""

echo -e "${CYAN}[3/3] Проверка на сервере...${NC}"
ssh -i "$SSH_KEY" "$SERVER_USER@$SERVER_IP" bash << 'ENDSSH'
ls -lh /var/www/housler/static/css/unified-minimal.css
echo "Templates:"
ls -1 /var/www/housler/templates/*.html | wc -l | xargs echo "Загружено файлов:"
ENDSSH

echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ Фронтенд обновлен!${NC}"
echo ""
echo -e "${YELLOW}Проверить:${NC}"
echo -e "   ${CYAN}https://housler.ru${NC}"
echo -e "   ${CYAN}https://housler.ru/blog${NC}"
echo ""
echo -e "${YELLOW}Примечание:${NC} Перезапуск приложения не требуется."
echo -e "Если стили не обновились - очистите кэш браузера (Cmd+Shift+R)"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
