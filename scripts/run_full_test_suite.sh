#!/bin/bash
# Скрипт для запуска полного набора тестов с красивым отчетом

set -e

echo "=============================================================="
echo "🧪 ЗАПУСК ПОЛНОГО НАБОРА ТЕСТОВ HOUSLER"
echo "=============================================================="
echo ""

# Цвета для вывода
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Переходим в директорию проекта
cd "$(dirname "$0")/.."

# Создаем директорию для отчетов
mkdir -p test_reports

# Timestamp для отчета
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
REPORT_FILE="test_reports/report_${TIMESTAMP}.txt"

echo "📋 Отчет будет сохранен в: $REPORT_FILE"
echo ""

# Функция для запуска тестов с отчетом
run_tests() {
    local test_name=$1
    local test_path=$2

    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}📦 $test_name${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""

    if python -m pytest "$test_path" -v --tb=short -s --color=yes 2>&1 | tee -a "$REPORT_FILE"; then
        echo -e "${GREEN}✅ $test_name PASSED${NC}"
        echo ""
        return 0
    else
        echo -e "${RED}❌ $test_name FAILED${NC}"
        echo ""
        return 1
    fi
}

# Счетчик ошибок
FAILED=0

# 1. Unit тесты
echo "🔬 UNIT ТЕСТЫ"
echo "=============================================================="

if run_tests "Session Storage Tests" "tests/test_session_storage.py"; then
    echo "✓ Session storage OK"
else
    FAILED=$((FAILED + 1))
fi

if run_tests "Fair Price Calculator Tests" "tests/test_fair_price_calculator.py"; then
    echo "✓ Fair price calculator OK"
else
    FAILED=$((FAILED + 1))
fi

if run_tests "Browser Pool Tests" "tests/test_browser_pool.py"; then
    echo "✓ Browser pool OK"
else
    FAILED=$((FAILED + 1))
fi

echo ""

# 2. API тесты
echo "🌐 API ТЕСТЫ"
echo "=============================================================="

if run_tests "API Tests" "tests/test_api.py"; then
    echo "✓ API OK"
else
    FAILED=$((FAILED + 1))
fi

echo ""

# 3. Security тесты
echo "🔒 SECURITY ТЕСТЫ"
echo "=============================================================="

if run_tests "Security Tests" "tests/test_security.py"; then
    echo "✓ Security OK"
else
    FAILED=$((FAILED + 1))
fi

echo ""

# 4. E2E тесты (критический путь)
echo "🎯 E2E ТЕСТЫ (критический путь пользователя)"
echo "=============================================================="

if run_tests "E2E Full Flow Tests" "tests/test_e2e_full_flow.py"; then
    echo "✓ E2E flow OK"
else
    FAILED=$((FAILED + 1))
fi

echo ""

# Итоговый отчет
echo "=============================================================="
echo "📊 ИТОГОВЫЙ ОТЧЕТ"
echo "=============================================================="
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!${NC}"
    echo ""
    echo "Детальный отчет сохранен в: $REPORT_FILE"
    echo ""
    exit 0
else
    echo -e "${RED}❌ ПРОВАЛЕНО ТЕСТОВ: $FAILED${NC}"
    echo ""
    echo "Детальный отчет сохранен в: $REPORT_FILE"
    echo ""
    echo "Проверьте отчет для деталей ошибок:"
    echo "  cat $REPORT_FILE"
    echo ""
    exit 1
fi
