#!/bin/bash

# Тест функционала "Поделиться"

echo "🧪 Тестирование функционала Поделиться"
echo "========================================"
echo ""

# 1. Получение CSRF токена
echo "1️⃣ Получение CSRF токена..."
CSRF_TOKEN=$(curl -s http://localhost:5002/api/csrf-token | grep -o '"csrf_token":"[^"]*"' | cut -d'"' -f4)
echo "   ✓ CSRF Token получен: ${CSRF_TOKEN:0:20}..."
echo ""

# 2. Создание мануальной сессии
echo "2️⃣ Создание тестовой сессии..."
RESPONSE=$(curl -s -X POST http://localhost:5002/api/create-manual \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: $CSRF_TOKEN" \
  -d '{
    "address": "Санкт-Петербург, Невский проспект, 1",
    "price": 15000000,
    "total_area": 75,
    "rooms": "2",
    "floor": "5/10"
  }')

SESSION_ID=$(echo "$RESPONSE" | grep -o '"session_id":"[^"]*"' | cut -d'"' -f4)

if [ -z "$SESSION_ID" ]; then
    echo "   ❌ Не удалось создать сессию"
    echo "   Response: $RESPONSE"
    exit 1
fi

echo "   ✓ Сессия создана: $SESSION_ID"
echo ""

# 3. Добавление мануальных аналогов
echo "3️⃣ Добавление тестовых аналогов..."
for i in 1 2 3; do
    PRICE=$((14000000 + $i * 500000))
    curl -s -X POST http://localhost:5002/api/add-comparable-manual \
      -H "Content-Type: application/json" \
      -H "X-CSRFToken: $CSRF_TOKEN" \
      -d "{
        \"session_id\": \"$SESSION_ID\",
        \"address\": \"Санкт-Петербург, Невский пр., $i\",
        \"price\": $PRICE,
        \"total_area\": 70,
        \"rooms\": \"2\"
      }" > /dev/null
    echo "   ✓ Аналог $i добавлен (цена: $PRICE₽)"
done
echo ""

# 4. Запуск анализа
echo "4️⃣ Запуск анализа..."
ANALYSIS=$(curl -s -X POST http://localhost:5002/api/analyze \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: $CSRF_TOKEN" \
  -d "{\"session_id\": \"$SESSION_ID\"}")

STATUS=$(echo "$ANALYSIS" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)

if [ "$STATUS" != "success" ]; then
    echo "   ❌ Анализ не выполнен"
    echo "   Response: $ANALYSIS"
    exit 1
fi

echo "   ✓ Анализ выполнен успешно"
echo ""

# 5. Проверка ссылки на отчет
echo "5️⃣ Проверка ссылки на отчет..."
REPORT_URL="http://localhost:5002/report/$SESSION_ID"
echo "   📍 URL отчета: $REPORT_URL"

# Проверяем что отчет доступен
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$REPORT_URL")
if [ "$HTTP_CODE" = "200" ]; then
    echo "   ✓ Отчет доступен по ссылке (HTTP $HTTP_CODE)"
else
    echo "   ❌ Отчет недоступен (HTTP $HTTP_CODE)"
fi
echo ""

# 6. Генерация Telegram ссылки
echo "6️⃣ Генерация Telegram ссылки..."
TG_RESPONSE=$(curl -s -X POST http://localhost:5002/api/telegram/generate-link \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: $CSRF_TOKEN" \
  -d "{\"session_id\": \"$SESSION_ID\"}")

BOT_LINK=$(echo "$TG_RESPONSE" | grep -o '"bot_link":"[^"]*"' | cut -d'"' -f4)
TG_TOKEN=$(echo "$TG_RESPONSE" | grep -o '"token":"[^"]*"' | cut -d'"' -f4)

if [ -z "$BOT_LINK" ]; then
    echo "   ❌ Не удалось создать Telegram ссылку"
    echo "   Response: $TG_RESPONSE"
else
    echo "   ✓ Telegram ссылка создана"
    echo "   📱 Bot link: $BOT_LINK"
    echo "   🔑 Token: ${TG_TOKEN:0:16}..."
fi
echo ""

# 7. Проверка API токена для бота
echo "7️⃣ Проверка API токена..."
TOKEN_DATA=$(curl -s "http://localhost:5002/api/telegram/report/$TG_TOKEN")

TG_STATUS=$(echo "$TOKEN_DATA" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
PDF_URL=$(echo "$TOKEN_DATA" | grep -o '"pdf_url":"[^"]*"' | cut -d'"' -f4)
WEB_URL=$(echo "$TOKEN_DATA" | grep -o '"web_url":"[^"]*"' | cut -d'"' -f4)

if [ "$TG_STATUS" = "success" ]; then
    echo "   ✓ Токен валидный"
    echo "   📄 PDF URL: $PDF_URL"
    echo "   🌐 Web URL: $WEB_URL"

    # Проверяем что web_url ведет на /report/
    if [[ "$WEB_URL" == *"/report/"* ]]; then
        echo "   ✅ Web URL правильный (ведет на /report/)"
    else
        echo "   ⚠️  Web URL ведет не на /report/ : $WEB_URL"
    fi
else
    echo "   ❌ Токен невалидный: $TOKEN_DATA"
fi
echo ""

# 8. Проверка что токен одноразовый
echo "8️⃣ Проверка одноразовости токена..."
REPEAT_RESPONSE=$(curl -s "http://localhost:5002/api/telegram/report/$TG_TOKEN")
REPEAT_STATUS=$(echo "$REPEAT_RESPONSE" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)

if [ "$REPEAT_STATUS" = "error" ]; then
    ERROR_MSG=$(echo "$REPEAT_RESPONSE" | grep -o '"message":"[^"]*"' | cut -d'"' -f4)
    echo "   ✓ Токен одноразовый (повторный запрос отклонен)"
    echo "   📝 Сообщение: $ERROR_MSG"
else
    echo "   ❌ Токен не одноразовый! Это проблема безопасности!"
fi
echo ""

# 9. Проверка Redis
echo "9️⃣ Проверка хранения токенов в Redis..."
REDIS_KEYS=$(redis-cli KEYS "housler:telegram_token:*" 2>/dev/null)
if [ -n "$REDIS_KEYS" ]; then
    echo "   ✓ Токены найдены в Redis:"
    echo "$REDIS_KEYS" | while read key; do
        TTL=$(redis-cli TTL "$key" 2>/dev/null)
        echo "     - $key (TTL: ${TTL}s)"
    done
else
    echo "   ℹ️  Токены не в Redis (используется in-memory fallback)"
fi
echo ""

# Итоговая сводка
echo "=========================================="
echo "✅ Тестирование завершено!"
echo ""
echo "📋 Итоговая информация:"
echo "  • Session ID: $SESSION_ID"
echo "  • Report URL: $REPORT_URL"
echo "  • Telegram Bot Link: $BOT_LINK"
echo ""
echo "🌐 Откройте в браузере для проверки UI:"
echo "  http://localhost:5002/wizard?session=$SESSION_ID"
echo ""
echo "💡 На шаге 3 нажмите 'Поделиться' для проверки:"
echo "  1. Скопировать ссылку → должна быть $REPORT_URL"
echo "  2. Получить в Telegram → должен открыться бот"
echo ""
