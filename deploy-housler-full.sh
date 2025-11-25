#!/bin/bash
# ========================================
# Полный деплой Housler на production
# Домен: housler.ru (91.229.8.221)
# Компоненты: Лендинг + Блог + Аналитика
# ========================================

set -e

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Конфигурация
SERVER_IP="91.229.8.221"
SERVER_USER="root"
DOMAIN="housler.ru"
APP_DIR="/var/www/housler"
APP_PORT=5002

echo ""
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}🚀 HOUSLER PRODUCTION DEPLOYMENT${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""
echo "Домен: $DOMAIN"
echo "Сервер: $SERVER_IP"
echo "Порт приложения: $APP_PORT"
echo ""

# ========================================
# 1. Проверка подключения к серверу
# ========================================

echo -e "${CYAN}[1/9] Проверка подключения к серверу...${NC}"
if ! ssh -o ConnectTimeout=5 -i ~/.ssh/id_housler "$SERVER_USER@$SERVER_IP" "echo 'OK'" > /dev/null 2>&1; then
    echo -e "${RED}❌ Не удалось подключиться к серверу${NC}"
    echo "Проверьте SSH ключи и доступность сервера"
    exit 1
fi
echo -e "${GREEN}✅ Подключение к серверу установлено${NC}"

# ========================================
# 2. Создание директории и копирование файлов
# ========================================

echo ""
echo -e "${CYAN}[2/9] Копирование файлов на сервер...${NC}"

# Создаем директорию на сервере
ssh -i ~/.ssh/id_housler "$SERVER_USER@$SERVER_IP" "mkdir -p $APP_DIR/backups"

# Список файлов для деплоя (исключаем venv, cache, и т.д.)
rsync -avz --progress -e "ssh -i ~/.ssh/id_housler" \
    --exclude 'venv/' \
    --exclude 'venv_dashboard/' \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    --exclude '.git/' \
    --exclude 'htmlcov/' \
    --exclude 'test_*' \
    --exclude '*.log' \
    --exclude 'sessions.db' \
    --exclude '.env' \
    ./ "$SERVER_USER@$SERVER_IP:$APP_DIR/"

echo -e "${GREEN}✅ Файлы скопированы${NC}"

# ========================================
# 3. Установка зависимостей
# ========================================

echo ""
echo -e "${CYAN}[3/9] Установка зависимостей...${NC}"

ssh -i ~/.ssh/id_housler "$SERVER_USER@$SERVER_IP" bash << 'ENDSSH'
set -e
cd /var/www/housler

# Проверяем наличие Python
if ! command -v python3 &> /dev/null; then
    echo "Установка Python..."
    apt update
    apt install -y python3 python3-pip python3-venv
fi

# Создаем виртуальное окружение если его нет
if [ ! -d "venv" ]; then
    echo "Создание виртуального окружения..."
    python3 -m venv venv
fi

# Активируем venv и устанавливаем зависимости
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Устанавливаем Playwright browsers
playwright install chromium
playwright install-deps chromium || true

echo "✅ Зависимости установлены"
ENDSSH

echo -e "${GREEN}✅ Зависимости установлены${NC}"

# ========================================
# 4. Настройка .env файла
# ========================================

echo ""
echo -e "${CYAN}[4/9] Настройка окружения...${NC}"

# Проверяем есть ли .env локально
if [ -f ".env" ]; then
    echo "Копируем локальный .env файл..."
    scp -i ~/.ssh/id_housler .env "$SERVER_USER@$SERVER_IP:$APP_DIR/.env"
else
    echo "Создаем .env из .env.example..."
    ssh -i ~/.ssh/id_housler "$SERVER_USER@$SERVER_IP" bash << 'ENDSSH'
    cd /var/www/housler
    if [ ! -f ".env" ] && [ -f ".env.example" ]; then
        cp .env.example .env
        echo "FLASK_ENV=production" >> .env
        echo "FLASK_DEBUG=false" >> .env
        echo "⚠️  ВАЖНО: Отредактируйте .env файл с реальными настройками!"
    fi
ENDSSH
fi

echo -e "${GREEN}✅ Окружение настроено${NC}"

# ========================================
# 5. Настройка systemd сервиса
# ========================================

echo ""
echo -e "${CYAN}[5/9] Настройка systemd сервиса...${NC}"

ssh -i ~/.ssh/id_housler "$SERVER_USER@$SERVER_IP" bash << 'ENDSSH'
set -e

# Создаем systemd service файл
cat > /etc/systemd/system/housler.service << 'EOF'
[Unit]
Description=Housler Real Estate Analytics
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/var/www/housler
Environment="PATH=/var/www/housler/venv/bin"
ExecStart=/var/www/housler/venv/bin/python /var/www/housler/app_new.py
Restart=always
RestartSec=10
StandardOutput=append:/var/log/housler/app.log
StandardError=append:/var/log/housler/error.log

# Security
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

# Создаем директорию для логов
mkdir -p /var/log/housler

# Перезагружаем systemd
systemctl daemon-reload

echo "✅ Systemd сервис настроен"
ENDSSH

echo -e "${GREEN}✅ Systemd сервис настроен${NC}"

# ========================================
# 6. Настройка Nginx
# ========================================

echo ""
echo -e "${CYAN}[6/9] Настройка Nginx...${NC}"

# Копируем Nginx конфигурацию
scp -i ~/.ssh/id_housler nginx-housler-main.conf "$SERVER_USER@$SERVER_IP:/tmp/housler.ru.conf"

ssh -i ~/.ssh/id_housler "$SERVER_USER@$SERVER_IP" bash << 'ENDSSH'
set -e

# Устанавливаем Nginx если его нет
if ! command -v nginx &> /dev/null; then
    echo "Установка Nginx..."
    apt update
    apt install -y nginx
fi

# Копируем конфигурацию
cp /tmp/housler.ru.conf /etc/nginx/sites-available/housler.ru

# Создаем директорию для статики (если нужно обслуживать через Nginx)
mkdir -p /var/www/housler/static

# Удаляем старую ссылку если есть
rm -f /etc/nginx/sites-enabled/housler.ru
rm -f /etc/nginx/sites-enabled/default

# Создаем новую ссылку
ln -s /etc/nginx/sites-available/housler.ru /etc/nginx/sites-enabled/

# Проверяем конфигурацию
nginx -t

echo "✅ Nginx настроен"
ENDSSH

echo -e "${GREEN}✅ Nginx настроен${NC}"

# ========================================
# 7. Настройка SSL (Certbot)
# ========================================

echo ""
echo -e "${CYAN}[7/9] Настройка SSL сертификата...${NC}"

ssh -i ~/.ssh/id_housler "$SERVER_USER@$SERVER_IP" bash << ENDSSH
set -e

# Устанавливаем Certbot если его нет
if ! command -v certbot &> /dev/null; then
    echo "Установка Certbot..."
    apt update
    apt install -y certbot python3-certbot-nginx
fi

# Проверяем есть ли уже сертификат
if [ -d "/etc/letsencrypt/live/$DOMAIN" ]; then
    echo "✅ SSL сертификат уже существует"
else
    echo "Получение SSL сертификата..."
    echo "⚠️  Убедитесь что DNS записи для $DOMAIN указывают на $SERVER_IP"
    read -p "Продолжить получение сертификата? (y/n) " -n 1 -r
    echo
    if [[ \$REPLY =~ ^[Yy]$ ]]; then
        certbot --nginx -d $DOMAIN -d www.$DOMAIN --non-interactive --agree-tos --email admin@$DOMAIN || true
    else
        echo "⚠️  Пропускаем получение SSL сертификата"
        echo "   Выполните позже: certbot --nginx -d $DOMAIN -d www.$DOMAIN"
    fi
fi
ENDSSH

echo -e "${GREEN}✅ SSL настроен${NC}"

# ========================================
# 8. Запуск приложения
# ========================================

echo ""
echo -e "${CYAN}[8/9] Запуск приложения...${NC}"

ssh -i ~/.ssh/id_housler "$SERVER_USER@$SERVER_IP" bash << 'ENDSSH'
set -e

# Останавливаем старую версию
systemctl stop housler 2>/dev/null || true

# Запускаем новую версию
systemctl start housler

# Включаем автозапуск
systemctl enable housler

# Перезапускаем Nginx
systemctl reload nginx

sleep 3

# Проверяем статус
if systemctl is-active --quiet housler; then
    echo "✅ Приложение запущено"
else
    echo "❌ Не удалось запустить приложение"
    systemctl status housler
    exit 1
fi

# Настройка cron job для автоматического парсинга блога
echo "Настройка cron job для blog parser..."

# Создаём скрипт для cron
cat > /var/www/housler/cron_parse_blog.sh << 'CRONSCRIPT'
#!/bin/bash
cd /var/www/housler
source venv/bin/activate
python3 blog_cli.py parse -n 10 >> /var/log/housler/blog_parser_cron.log 2>&1
CRONSCRIPT

chmod +x /var/www/housler/cron_parse_blog.sh

# Добавляем в crontab (запуск каждый день в 10:00)
CRON_JOB="0 10 * * * /var/www/housler/cron_parse_blog.sh"

# Проверяем есть ли уже этот cron job
if ! crontab -l 2>/dev/null | grep -q "cron_parse_blog.sh"; then
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
    echo "✅ Cron job для blog parser добавлен (ежедневно в 10:00)"
else
    echo "✅ Cron job для blog parser уже существует"
fi

# Инициализируем блог seed данными если база пустая
cd /var/www/housler
POSTS_COUNT=$(source venv/bin/activate && python3 -c "from blog_database import BlogDatabase; db = BlogDatabase(); print(len(db.get_all_posts()))")
if [ "$POSTS_COUNT" = "0" ]; then
    echo "База блога пустая, добавляем seed данные..."
    source venv/bin/activate
    python3 seed_blog.py
    echo "✅ Seed данные добавлены"
else
    echo "✅ В базе блога уже есть $POSTS_COUNT статей"
fi

ENDSSH

echo -e "${GREEN}✅ Приложение запущено и blog parser настроен${NC}"

# ========================================
# 9. Проверка работоспособности
# ========================================

echo ""
echo -e "${CYAN}[9/9] Проверка работоспособности...${NC}"

# Проверяем health endpoint
echo "Проверка health endpoint..."
sleep 5

HEALTH_STATUS=$(ssh -i ~/.ssh/id_housler "$SERVER_USER@$SERVER_IP" "curl -s -o /dev/null -w '%{http_code}' http://localhost:$APP_PORT/health" || echo "000")

if [ "$HEALTH_STATUS" = "200" ]; then
    echo -e "${GREEN}✅ Health check: OK (HTTP $HEALTH_STATUS)${NC}"
else
    echo -e "${YELLOW}⚠️  Health check: HTTP $HEALTH_STATUS${NC}"
fi

# Проверяем домен
echo "Проверка через домен..."
DOMAIN_STATUS=$(curl -s -o /dev/null -w '%{http_code}' "https://$DOMAIN/" --max-time 10 || echo "000")

if [ "$DOMAIN_STATUS" = "200" ]; then
    echo -e "${GREEN}✅ Домен доступен: https://$DOMAIN (HTTP $DOMAIN_STATUS)${NC}"
else
    echo -e "${YELLOW}⚠️  Домен: HTTP $DOMAIN_STATUS${NC}"
fi

# ========================================
# Итоги
# ========================================

echo ""
echo -e "${CYAN}========================================${NC}"
echo -e "${GREEN}✅ ДЕПЛОЙ ЗАВЕРШЕН УСПЕШНО!${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""
echo "📋 Информация о деплое:"
echo "   Домен: https://$DOMAIN"
echo "   Сервер: $SERVER_IP"
echo "   Время: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""
echo "🔍 Проверьте компоненты:"
echo "   Лендинг:    https://$DOMAIN/"
echo "   Блог:       https://$DOMAIN/blog"
echo "   Калькулятор: https://$DOMAIN/calculator"
echo "   Health:     https://$DOMAIN/health"
echo "   Sitemap:    https://$DOMAIN/sitemap.xml"
echo ""
echo "📊 Мониторинг:"
echo "   Логи приложения: ssh $SERVER_USER@$SERVER_IP 'tail -f /var/log/housler/app.log'"
echo "   Логи Nginx:      ssh $SERVER_USER@$SERVER_IP 'tail -f /var/log/nginx/housler.ru.access.log'"
echo "   Статус сервиса:  ssh $SERVER_USER@$SERVER_IP 'systemctl status housler'"
echo ""
echo "🔧 Управление:"
echo "   Рестарт:  ssh $SERVER_USER@$SERVER_IP 'systemctl restart housler'"
echo "   Стоп:     ssh $SERVER_USER@$SERVER_IP 'systemctl stop housler'"
echo "   Логи:     ssh $SERVER_USER@$SERVER_IP 'journalctl -u housler -f'"
echo ""
echo -e "${GREEN}🎉 Все готово!${NC}"
