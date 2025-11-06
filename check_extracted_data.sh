#!/bin/bash

echo "🔍 Проверка извлеченных данных"
echo "================================"
echo ""

# Создаем сессию и парсим
session_cookie=$(curl -s -c - http://localhost:5002/ | grep session | awk '{print $7}')

echo "📥 Отправляем запрос на парсинг..."
response=$(curl -s -X POST http://localhost:5002/api/parse \
  -H "Content-Type: application/json" \
  -H "Cookie: session=$session_cookie" \
  -d '{"url":"https://www.cian.ru/sale/flat/319271562/"}')

echo "✓ Ответ получен"
echo ""

# Сохраняем ответ для отладки
echo "$response" > /tmp/api_response.json

# Извлекаем данные
echo "📊 ИЗВЛЕЧЕННЫЕ ДАННЫЕ:"
echo "====================="
echo ""

title=$(echo "$response" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('parsed_data',{}).get('title','НЕТ'))" 2>/dev/null || echo "ОШИБКА")
area=$(echo "$response" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('parsed_data',{}).get('area','НЕТ'))" 2>/dev/null || echo "ОШИБКА")
rooms=$(echo "$response" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('parsed_data',{}).get('rooms','НЕТ'))" 2>/dev/null || echo "ОШИБКА")
floor=$(echo "$response" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('parsed_data',{}).get('floor','НЕТ'))" 2>/dev/null || echo "ОШИБКА")
price=$(echo "$response" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('parsed_data',{}).get('price','НЕТ'))" 2>/dev/null || echo "ОШИБКА")
address=$(echo "$response" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('parsed_data',{}).get('address','НЕТ'))" 2>/dev/null || echo "ОШИБКА")
zhk=$(echo "$response" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('parsed_data',{}).get('residential_complex','НЕТ'))" 2>/dev/null || echo "ОШИБКА")

echo "Заголовок: $title"
echo "Площадь:   $area м²"
echo "Комнат:    $rooms"
echo "Этаж:      $floor"
echo "Цена:      $price"
echo "Адрес:     $address"
echo "ЖК:        $zhk"
echo ""

# Проверяем характеристики
echo "📋 ХАРАКТЕРИСТИКИ:"
echo "=================="
char_count=$(echo "$response" | python3 -c "import sys, json; d=json.load(sys.stdin); print(len(d.get('parsed_data',{}).get('characteristics',{})))" 2>/dev/null || echo "0")
echo "Всего характеристик: $char_count"
echo ""

# Проверяем key characteristics
ceiling=$(echo "$response" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('parsed_data',{}).get('characteristics',{}).get('Высота потолков','НЕТ'))" 2>/dev/null || echo "ОШИБКА")
year=$(echo "$response" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('parsed_data',{}).get('characteristics',{}).get('Год постройки','НЕТ'))" 2>/dev/null || echo "ОШИБКА")
area_char=$(echo "$response" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('parsed_data',{}).get('characteristics',{}).get('Общая площадь','НЕТ'))" 2>/dev/null || echo "ОШИБКА")
floor_char=$(echo "$response" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('parsed_data',{}).get('characteristics',{}).get('Этаж','НЕТ'))" 2>/dev/null || echo "ОШИБКА")

echo "Высота потолков: $ceiling"
echo "Год постройки:   $year"
echo "Общая площадь:   $area_char"
echo "Этаж:            $floor_char"
echo ""

echo "🎯 ПРОВЕРКА РЕЗУЛЬТАТА:"
echo "======================="

# Ожидаемые значения
expected_area="180.4"
expected_rooms="3"
expected_floor="6"

errors=0

if [ "$area" != "$expected_area" ]; then
    echo "❌ Площадь: ожидалось $expected_area, получено $area"
    errors=$((errors+1))
else
    echo "✅ Площадь: $area м²"
fi

if [ "$rooms" != "$expected_rooms" ]; then
    echo "❌ Комнат: ожидалось $expected_rooms, получено $rooms"
    errors=$((errors+1))
else
    echo "✅ Комнат: $rooms"
fi

if [ "$floor" != "$expected_floor" ]; then
    echo "❌ Этаж: ожидалось $expected_floor, получено $floor"
    errors=$((errors+1))
else
    echo "✅ Этаж: $floor"
fi

echo ""
if [ $errors -eq 0 ]; then
    echo "🎉 Все ключевые поля извлечены правильно!"
else
    echo "⚠️  Обнаружено ошибок: $errors"
    echo ""
    echo "Полный ответ сохранен в /tmp/api_response.json"
fi
