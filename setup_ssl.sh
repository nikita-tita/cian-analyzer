#!/bin/bash

# ========================================
# Housler SSL Setup Script
# ========================================

set -e

# Colors
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

print_header() {
    echo ""
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# ========================================
# Main script
# ========================================

print_header "Housler SSL Setup"

# Проверка прав root
if [ "$EUID" -ne 0 ]; then
    print_error "Этот скрипт требует прав root. Запустите с sudo."
    exit 1
fi

# Домен
DOMAIN="housler.ru"
WWW_DOMAIN="www.housler.ru"

echo "Настройка SSL для домена: $DOMAIN"
echo ""

# ========================================
# 1. Установка Certbot
# ========================================

print_header "Установка Certbot"

if ! command -v certbot &> /dev/null; then
    echo "Устанавливаем Certbot..."
    apt-get update
    apt-get install -y certbot python3-certbot-nginx
    print_success "Certbot установлен"
else
    print_success "Certbot уже установлен"
fi

# ========================================
# 2. Остановка сервисов на портах 80/443
# ========================================

print_header "Подготовка портов"

echo "Останавливаем Docker сервисы (если запущены)..."
if docker-compose ps | grep -q "Up"; then
    docker-compose down
    print_success "Docker сервисы остановлены"
fi

# ========================================
# 3. Получение сертификата
# ========================================

print_header "Получение SSL сертификата"

if [ -d "/etc/letsencrypt/live/$DOMAIN" ]; then
    print_warning "Сертификат уже существует. Хотите обновить?"
    read -p "Обновить? [y/N] " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        certbot renew --force-renewal
        print_success "Сертификат обновлён"
    else
        print_success "Используем существующий сертификат"
    fi
else
    echo "Получаем новый сертификат..."
    certbot certonly --standalone \
        -d $DOMAIN \
        -d $WWW_DOMAIN \
        --non-interactive \
        --agree-tos \
        --email hello@housler.ru

    print_success "Сертификат получен"
fi

# ========================================
# 4. Копирование сертификатов
# ========================================

print_header "Копирование сертификатов"

mkdir -p ./nginx/ssl

cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem ./nginx/ssl/
cp /etc/letsencrypt/live/$DOMAIN/privkey.pem ./nginx/ssl/
chmod 644 ./nginx/ssl/*.pem

print_success "Сертификаты скопированы в ./nginx/ssl/"

# ========================================
# 5. Обновление nginx.conf
# ========================================

print_header "Обновление конфигурации Nginx"

NGINX_CONF="./nginx/nginx.conf"

if grep -q "# return 301 https" "$NGINX_CONF"; then
    print_warning "HTTPS редирект закомментирован. Активировать?"
    read -p "Активировать HTTPS? [Y/n] " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        # Раскомментируем редирект
        sed -i 's/# return 301 https/return 301 https/g' "$NGINX_CONF"

        # Раскомментируем HTTPS server block
        sed -i 's/# server {/server {/g' "$NGINX_CONF"
        sed -i 's/#     /    /g' "$NGINX_CONF"

        print_success "HTTPS активирован в nginx.conf"
    fi
else
    print_success "nginx.conf уже настроен для HTTPS"
fi

# ========================================
# 6. Запуск сервисов
# ========================================

print_header "Запуск сервисов"

echo "Запускаем Docker с production профилем..."
docker-compose --profile production up -d --build

print_success "Сервисы запущены"

# ========================================
# 7. Проверка
# ========================================

print_header "Проверка"

echo "Ждём запуска сервисов (30 сек)..."
sleep 30

echo "Проверяем HTTP..."
if curl -s -o /dev/null -w "%{http_code}" http://$DOMAIN/health | grep -q "200\|301"; then
    print_success "HTTP работает"
else
    print_warning "HTTP не отвечает"
fi

echo "Проверяем HTTPS..."
if curl -s -k -o /dev/null -w "%{http_code}" https://$DOMAIN/health | grep -q "200"; then
    print_success "HTTPS работает"
else
    print_warning "HTTPS не отвечает"
fi

# ========================================
# 8. Настройка автообновления
# ========================================

print_header "Автообновление сертификатов"

CRON_JOB="0 3 * * 1 certbot renew --quiet && cp /etc/letsencrypt/live/$DOMAIN/*.pem $(pwd)/nginx/ssl/ && docker-compose restart nginx"

if ! crontab -l 2>/dev/null | grep -q "certbot renew"; then
    echo "Добавляем задачу в cron..."
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
    print_success "Автообновление настроено (каждый понедельник в 3:00)"
else
    print_success "Автообновление уже настроено"
fi

# ========================================
# Summary
# ========================================

print_header "Установка завершена!"

echo -e "${GREEN}SSL настроен для:${NC}"
echo -e "  - https://$DOMAIN"
echo -e "  - https://$WWW_DOMAIN"
echo ""
echo -e "${CYAN}Проверьте сайт:${NC}"
echo -e "  ${GREEN}Калькулятор:${NC} https://$DOMAIN/calculator"
echo -e "  ${GREEN}Health:${NC} https://$DOMAIN/health"
echo -e "  ${GREEN}API Docs:${NC} https://$DOMAIN (см. API_DOCS.md)"
echo ""
echo -e "${CYAN}Полезные команды:${NC}"
echo -e "  ${GREEN}Проверка SSL:${NC} openssl s_client -connect $DOMAIN:443 -servername $DOMAIN"
echo -e "  ${GREEN}Обновление SSL:${NC} sudo certbot renew"
echo -e "  ${GREEN}Логи:${NC} docker-compose logs -f nginx"
echo ""
print_success "Готово! 🚀"
