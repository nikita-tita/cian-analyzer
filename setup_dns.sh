#!/bin/bash

# ═══════════════════════════════════════════════════════════════════════════
# DNS Setup Script for housler.ru via Reg.ru API
# ═══════════════════════════════════════════════════════════════════════════

set -e

# Цвета
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Конфигурация
DOMAIN="housler.ru"
SERVER_IP="91.229.8.221"
API_URL="https://api.reg.ru/api/regru2"

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}DNS Setup for $DOMAIN${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Запросить учетные данные
read -p "Введите ваш логин на Reg.ru: " REG_LOGIN
read -sp "Введите ваш пароль на Reg.ru: " REG_PASSWORD
echo ""
echo ""

echo -e "${YELLOW}Проверка текущих DNS записей...${NC}"
curl -s "$API_URL/zone/get_resource_records" \
  -d "username=$REG_LOGIN" \
  -d "password=$REG_PASSWORD" \
  -d "domain_name=$DOMAIN" | jq '.'

echo ""
echo -e "${YELLOW}Удаление старых A записей (если есть)...${NC}"
# Удалим старые записи @
curl -s "$API_URL/zone/remove_record" \
  -d "username=$REG_LOGIN" \
  -d "password=$REG_PASSWORD" \
  -d "domain_name=$DOMAIN" \
  -d "subdomain=@" \
  -d "record_type=A" | jq '.'

# Удалим старые записи www
curl -s "$API_URL/zone/remove_record" \
  -d "username=$REG_LOGIN" \
  -d "password=$REG_PASSWORD" \
  -d "domain_name=$DOMAIN" \
  -d "subdomain=www" \
  -d "record_type=A" | jq '.'

echo ""
echo -e "${YELLOW}Добавление новых A записей...${NC}"

# Добавить A запись для @
echo "Добавляем запись: @ -> $SERVER_IP"
curl -s "$API_URL/zone/add_alias" \
  -d "username=$REG_LOGIN" \
  -d "password=$REG_PASSWORD" \
  -d "domain_name=$DOMAIN" \
  -d "subdomain=@" \
  -d "ipaddr=$SERVER_IP" | jq '.'

# Добавить A запись для www
echo "Добавляем запись: www -> $SERVER_IP"
curl -s "$API_URL/zone/add_alias" \
  -d "username=$REG_LOGIN" \
  -d "password=$REG_PASSWORD" \
  -d "domain_name=$DOMAIN" \
  -d "subdomain=www" \
  -d "ipaddr=$SERVER_IP" | jq '.'

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}DNS записи добавлены!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${YELLOW}Проверка DNS (может занять 5-30 минут):${NC}"
echo "  dig $DOMAIN"
echo "  dig www.$DOMAIN"
echo ""
echo -e "${YELLOW}После распространения DNS, сайт будет доступен:${NC}"
echo "  http://$DOMAIN"
echo "  http://www.$DOMAIN"
echo ""
