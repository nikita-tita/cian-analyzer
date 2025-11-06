#!/bin/bash

echo "Тестирование API: проверка структуры данных"
echo "=========================================="

# Делаем запрос к API
response=$(curl -s -X POST http://localhost:5002/api/parse \
  -H "Content-Type: application/json" \
  -H "Cookie: session=$(curl -s http://localhost:5002/ | grep -o 'session=[^;]*' | cut -d= -f2)" \
  -d '{"url":"https://www.cian.ru/sale/flat/319271562/"}')

# Проверяем наличие ключевых полей
echo ""
echo "Проверка полей в корне данных:"
echo "------------------------------"

area=$(echo "$response" | python3 -c "import sys, json; data = json.load(sys.stdin); print(data.get('parsed_data', {}).get('area', 'НЕТ'))" 2>/dev/null)
rooms=$(echo "$response" | python3 -c "import sys, json; data = json.load(sys.stdin); print(data.get('parsed_data', {}).get('rooms', 'НЕТ'))" 2>/dev/null)
floor=$(echo "$response" | python3 -c "import sys, json; data = json.load(sys.stdin); print(data.get('parsed_data', {}).get('floor', 'НЕТ'))" 2>/dev/null)
title=$(echo "$response" | python3 -c "import sys, json; data = json.load(sys.stdin); print(data.get('parsed_data', {}).get('title', 'НЕТ'))" 2>/dev/null)

echo "title: $title"
echo "area: $area"
echo "rooms: $rooms"
echo "floor: $floor"

echo ""
echo "Результат:"
echo "----------"

if [ "$area" != "НЕТ" ] && [ "$rooms" != "НЕТ" ] && [ "$floor" != "НЕТ" ]; then
    echo "✅ Все ключевые поля извлечены!"
else
    echo "❌ Некоторые поля отсутствуют"
fi
