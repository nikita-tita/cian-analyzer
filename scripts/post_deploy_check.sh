#!/bin/bash
# Скрипт для проверки после деплоя на продакшн
# Запускает критические smoke tests

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

BASE_URL="${BASE_URL:-https://housler.ru}"

echo "=============================================================="
echo "🔥 POST-DEPLOY SMOKE TESTS"
echo "=============================================================="
echo "Base URL: $BASE_URL"
echo ""

# Функция для проверки endpoint
check_endpoint() {
    local name=$1
    local url=$2
    local expected_status=$3

    echo -n "Checking $name... "

    status=$(curl -s -o /dev/null -w "%{http_code}" "$url" --max-time 10)

    if [ "$status" == "$expected_status" ]; then
        echo -e "${GREEN}✅ OK${NC} (HTTP $status)"
        return 0
    else
        echo -e "${RED}❌ FAIL${NC} (HTTP $status, expected $expected_status)"
        return 1
    fi
}

FAILED=0

# 1. Landing page
if ! check_endpoint "Landing page" "$BASE_URL" "200"; then
    FAILED=$((FAILED + 1))
fi

# 2. Calculator page
if ! check_endpoint "Calculator page" "$BASE_URL/calculator" "200"; then
    FAILED=$((FAILED + 1))
fi

# 3. Health check
if ! check_endpoint "Health check" "$BASE_URL/health" "200"; then
    FAILED=$((FAILED + 1))
fi

# 4. API parse endpoint (должен вернуть 400 без данных)
echo -n "Checking API parse endpoint... "
response=$(curl -s -X POST "$BASE_URL/api/parse" \
    -H "Content-Type: application/json" \
    -d '{}' \
    -o /dev/null -w "%{http_code}" --max-time 10)

if [ "$response" == "400" ] || [ "$response" == "422" ]; then
    echo -e "${GREEN}✅ OK${NC} (returns error for empty request)"
else
    echo -e "${RED}❌ FAIL${NC} (unexpected status: $response)"
    FAILED=$((FAILED + 1))
fi

# 5. Full E2E test (optional - takes time)
if [ "$RUN_FULL_E2E" == "true" ]; then
    echo ""
    echo "Running full E2E tests..."
    if python -m pytest tests/test_e2e_full_flow.py -v --tb=short; then
        echo -e "${GREEN}✅ E2E tests passed${NC}"
    else
        echo -e "${RED}❌ E2E tests failed${NC}"
        FAILED=$((FAILED + 1))
    fi
fi

echo ""
echo "=============================================================="
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ ALL POST-DEPLOY CHECKS PASSED${NC}"
    echo "=============================================================="
    exit 0
else
    echo -e "${RED}❌ FAILED CHECKS: $FAILED${NC}"
    echo "=============================================================="
    exit 1
fi
