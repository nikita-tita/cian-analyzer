#!/bin/bash
# Диагностика проблем на housler.ru

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}🔍 Диагностика housler.ru${NC}"
echo "================================"

# 1. Проверка доступности
echo -e "\n${YELLOW}1. Проверка доступности сайта:${NC}"
if curl -s --max-time 5 https://housler.ru/ > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Сайт отвечает${NC}"
else
    echo -e "${RED}✗ Сайт не отвечает${NC}"
fi

# 2. Статус код и заголовки
echo -e "\n${YELLOW}2. HTTP статус и заголовки:${NC}"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" https://housler.ru/ 2>/dev/null)
echo "HTTP статус: $HTTP_CODE"

echo -e "\nОсновные заголовки:"
curl -sI https://housler.ru/ 2>&1 | grep -iE "server|cf-|x-powered|content-type|location" || true

# 3. Проверка через разные методы
echo -e "\n${YELLOW}3. Проверка разных endpoints:${NC}"

check_endpoint() {
    local endpoint=$1
    local status=$(curl -s -o /dev/null -w "%{http_code}" "https://housler.ru${endpoint}" 2>/dev/null)

    if [ "$status" == "200" ]; then
        echo -e "  ${GREEN}✓${NC} $endpoint → $status"
    elif [ "$status" == "403" ]; then
        echo -e "  ${RED}✗${NC} $endpoint → $status (Access Denied)"
    else
        echo -e "  ${YELLOW}⚠${NC} $endpoint → $status"
    fi
}

check_endpoint "/"
check_endpoint "/health"
check_endpoint "/calculator"
check_endpoint "/blog"
check_endpoint "/metrics"

# 4. Проверка DNS
echo -e "\n${YELLOW}4. DNS информация:${NC}"
dig +short housler.ru A 2>/dev/null || nslookup housler.ru 2>/dev/null | grep Address | tail -1

# 5. Проверка прокси/CDN
echo -e "\n${YELLOW}5. Определение прокси/CDN:${NC}"
RESPONSE_HEADERS=$(curl -sI https://housler.ru/ 2>&1)

if echo "$RESPONSE_HEADERS" | grep -qi "cloudflare"; then
    echo -e "${CYAN}→ Используется Cloudflare CDN${NC}"
    echo "  Возможные проблемы:"
    echo "  - Under Attack Mode включен"
    echo "  - WAF блокирует запросы"
    echo "  - IP заблокирован в Firewall Rules"
elif echo "$RESPONSE_HEADERS" | grep -qi "envoy"; then
    echo -e "${CYAN}→ Используется Envoy proxy${NC}"
    echo "  Это может быть Yandex Cloud, или другой облачный провайдер"
else
    echo -e "${CYAN}→ Стандартный сервер${NC}"
fi

# 6. Попытка обхода блокировки
echo -e "\n${YELLOW}6. Попытка с User-Agent браузера:${NC}"
BROWSER_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36" \
    https://housler.ru/ 2>/dev/null)

if [ "$BROWSER_STATUS" == "200" ]; then
    echo -e "${GREEN}✓ С User-Agent работает! (статус: $BROWSER_STATUS)${NC}"
    echo "  → Проблема: блокируются curl/боты"
elif [ "$BROWSER_STATUS" == "403" ]; then
    echo -e "${RED}✗ И с User-Agent не работает (статус: $BROWSER_STATUS)${NC}"
    echo "  → Проблема серьезнее: скорее всего WAF или IP блокировка"
fi

# 7. Рекомендации
echo -e "\n${CYAN}════════════════════════════════${NC}"
echo -e "${CYAN}📋 РЕКОМЕНДАЦИИ:${NC}"
echo -e "${CYAN}════════════════════════════════${NC}"

if [ "$HTTP_CODE" == "403" ]; then
    echo -e "\n${YELLOW}Проблема: HTTP 403 (Access Denied)${NC}"
    echo ""
    echo "Решения:"
    echo "  1. Проверьте Cloudflare Dashboard:"
    echo "     → Security → WAF → отключите 'Under Attack Mode'"
    echo "     → Security → Firewall Rules → проверьте блокировки"
    echo ""
    echo "  2. Если используете другой CDN/прокси:"
    echo "     → Проверьте настройки firewall"
    echo "     → Добавьте ваш IP в whitelist"
    echo ""
    echo "  3. Проверьте что на сервере запущено:"
    echo "     → ssh root@91.229.8.221 'systemctl status housler'"
    echo "     → ssh root@91.229.8.221 'journalctl -u housler -n 50'"
fi

echo -e "\n${GREEN}✅ Диагностика завершена${NC}"
echo -e "\nДля деплоя используйте: ${CYAN}bash scripts/deploy.sh${NC}"
