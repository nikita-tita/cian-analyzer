#!/bin/bash

echo "🧪 Тест свежего парсинга"
echo "========================"
echo ""

# Получаем новую сессию
echo "1. Получаем новую сессию..."
session_cookie=$(curl -s -c - http://localhost:5002/ | grep session | awk '{print $7}')
echo "   Session: ${session_cookie:0:20}..."

# Парсим с новой сессией
echo ""
echo "2. Отправляем запрос на парсинг..."
response=$(curl -s -X POST http://localhost:5002/api/parse \
  -H "Content-Type: application/json" \
  -H "Cookie: session=$session_cookie" \
  -d '{"url":"https://www.cian.ru/sale/flat/319271562/"}')

echo "   ✓ Ответ получен"

# Извлекаем данные
echo ""
echo "3. Проверяем извлеченные данные:"
echo "   ================================"

floor=$(echo "$response" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('data',{}).get('floor','НЕТ'))" 2>/dev/null || echo "ОШИБКА")
area=$(echo "$response" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('data',{}).get('area','НЕТ'))" 2>/dev/null || echo "ОШИБКА")
rooms=$(echo "$response" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('data',{}).get('rooms','НЕТ'))" 2>/dev/null || echo "ОШИБКА")
title=$(echo "$response" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('data',{}).get('title','НЕТ'))" 2>/dev/null || echo "ОШИБКА")

echo "   Заголовок: $title"
echo "   Площадь:   $area м²"
echo "   Комнат:    $rooms"
echo "   Этаж:      $floor"

echo ""
echo "4. Результат:"
echo "   ==========="

if [ "$floor" = "6" ] && [ "$area" = "180.4" ] && [ "$rooms" = "3" ]; then
    echo "   ✅ Все поля корректны!"
    echo ""
    echo "   🌐 Откройте в браузере: http://localhost:5002"
    echo "   📝 Обновите страницу (F5) и заново введите URL"
else
    echo "   ❌ Есть проблемы:"
    [ "$floor" != "6" ] && echo "      - Этаж: ожидалось 6, получено $floor"
    [ "$area" != "180.4" ] && echo "      - Площадь: ожидалось 180.4, получено $area"
    [ "$rooms" != "3" ] && echo "      - Комнат: ожидалось 3, получено $rooms"
fi
