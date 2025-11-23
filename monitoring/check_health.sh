#!/bin/bash
# Health Check Script для мониторинга Housler
# Запуск: ./check_health.sh
# Cron: */5 * * * * /var/www/housler/monitoring/check_health.sh >> /var/log/housler/health.log 2>&1

set -e

# Конфигурация
SITE_URL="${SITE_URL:-https://housler.ru}"
TIMEOUT=10
LOG_FILE="${LOG_FILE:-/var/log/housler/health.log}"
ALERT_EMAIL="${ALERT_EMAIL:-admin@housler.ru}"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Timestamp
timestamp() {
    date '+%Y-%m-%d %H:%M:%S'
}

log() {
    echo "[$(timestamp)] $1"
}

# Проверка HTTP endpoint
check_endpoint() {
    local url=$1
    local name=$2
    local expected_code=${3:-200}

    log "Checking $name: $url"

    response=$(curl -s -w "\n%{http_code}" --max-time $TIMEOUT "$url" 2>&1)
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n-1)

    if [ "$http_code" = "$expected_code" ]; then
        echo -e "${GREEN}✓${NC} $name: OK (HTTP $http_code)"
        return 0
    else
        echo -e "${RED}✗${NC} $name: FAILED (HTTP $http_code)"
        echo "Response: $body"
        return 1
    fi
}

# Проверка JSON endpoint
check_json_endpoint() {
    local url=$1
    local name=$2
    local json_key=$3

    log "Checking $name: $url"

    response=$(curl -s --max-time $TIMEOUT "$url" 2>&1)

    if echo "$response" | jq -e ".$json_key" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} $name: OK"
        echo "$response" | jq ".$json_key" 2>/dev/null || echo "$response"
        return 0
    else
        echo -e "${RED}✗${NC} $name: FAILED (invalid JSON or missing key)"
        echo "Response: $response"
        return 1
    fi
}

# Проверка systemd service
check_service() {
    local service=$1

    if systemctl is-active --quiet "$service"; then
        echo -e "${GREEN}✓${NC} Service $service: ACTIVE"
        return 0
    else
        echo -e "${RED}✗${NC} Service $service: INACTIVE"
        systemctl status "$service" --no-pager || true
        return 1
    fi
}

# Главная функция проверки
main() {
    log "========================================="
    log "Housler Health Check Started"
    log "========================================="

    errors=0

    # 1. Проверка главной страницы
    check_endpoint "$SITE_URL/" "Main Page" 200 || ((errors++))

    # 2. Проверка health endpoint
    check_json_endpoint "$SITE_URL/health" "Health API" "status" || ((errors++))

    # 3. Проверка task queue stats
    check_json_endpoint "$SITE_URL/api/tasks/queue-stats" "Task Queue" "queued_jobs" || ((errors++))

    # 4. Проверка metrics endpoint
    check_endpoint "$SITE_URL/metrics" "Metrics" 200 || ((errors++))

    # 5. Проверка systemd сервисов (только на production сервере)
    if [ -f /etc/systemd/system/housler.service ]; then
        log ""
        log "Checking systemd services..."
        check_service "housler.service" || ((errors++))
        check_service "housler-worker.service" || ((errors++))
        check_service "redis.service" || ((errors++))
        check_service "nginx.service" || ((errors++))
    fi

    # 6. Итоги
    log ""
    log "========================================="
    if [ $errors -eq 0 ]; then
        log "Status: ${GREEN}ALL CHECKS PASSED${NC}"
        log "========================================="
        exit 0
    else
        log "Status: ${RED}$errors CHECK(S) FAILED${NC}"
        log "========================================="

        # Отправка алерта (опционально)
        if command -v mail &> /dev/null && [ ! -z "$ALERT_EMAIL" ]; then
            log "Sending alert to $ALERT_EMAIL"
            echo "Housler health check failed with $errors error(s). Check logs: $LOG_FILE" | \
                mail -s "Housler Health Check Failed" "$ALERT_EMAIL"
        fi

        exit 1
    fi
}

# Запуск
main "$@"
