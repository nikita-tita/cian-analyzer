# Инструкция по добавлению Redis в Railway

## Проблема
Приложение использует in-memory хранилище для сессий, которое не работает корректно при множественных инстансах Railway.

## Решение: Добавить Redis

### Шаг 1: Откройте Railway Dashboard
URL: https://railway.com/project/7a53c03f-45e5-4795-a9fb-2badeaf9ee16

### Шаг 2: Добавьте Redis
1. Нажмите кнопку **"+ New"** (правый верхний угол)
2. Выберите **"Database"**
3. Выберите **"Add Redis"**
4. Redis автоматически создастся и добавит переменную `REDIS_URL`

### Шаг 3: Перезапустите приложение
Railway автоматически перезапустит `cian-analyzer` после добавления Redis.

## Что произойдет после добавления Redis

### До (текущее состояние):
- ✅ `/api/parse` - работает
- ❌ `/api/find-similar` - не находит сессию
- ❌ `/api/analyze` - не находит сессию
- **Причина**: Разные инстансы используют разную память

### После добавления Redis:
- ✅ `/api/parse` - работает
- ✅ `/api/find-similar` - работает (сессии в Redis)
- ✅ `/api/analyze` - работает (сессии в Redis)
- ✅ Сессии сохраняются между инстансами
- ✅ Сессии живут 1 час (TTL)

## Проверка работы

После добавления Redis выполните тест:

```bash
# 1. Создать сессию
SESSION_ID=$(curl -s -X POST 'https://cian-analyzer-production.up.railway.app/api/parse' \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://www.cian.ru/sale/flat/123456/"}' | \
  python3 -c "import sys, json; print(json.load(sys.stdin)['session_id'])")

echo "Session: $SESSION_ID"

# 2. Найти аналоги
curl -s -X POST 'https://cian-analyzer-production.up.railway.app/api/find-similar' \
  -H 'Content-Type: application/json' \
  -d "{\"session_id\":\"$SESSION_ID\"}" | \
  python3 -c "import sys, json; d=json.load(sys.stdin); print('Status:', d['status'], '- Comparables:', len(d.get('comparables', [])))"

# 3. Запустить анализ
curl -s -X POST 'https://cian-analyzer-production.up.railway.app/api/analyze' \
  -H 'Content-Type: application/json' \
  -d "{\"session_id\":\"$SESSION_ID\"}" | \
  python3 -c "import sys, json; print('Analysis status:', json.load(sys.stdin)['status'])"
```

Ожидаемый результат:
```
Session: <uuid>
Status: success - Comparables: 5
Analysis status: success
```

## Альтернатива (если не хотите Redis)

Можно настроить Railway на использование только 1 инстанса:
1. Railway Dashboard → Settings → Replicas
2. Установите "1 Replica" (вместо auto-scaling)

Но это не рекомендуется для production - лучше использовать Redis.
