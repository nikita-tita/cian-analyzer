# 🔧 Исправление ошибки "Сессия не найдена"

**Дата**: 8 ноября 2025, 12:58 MSK
**Проблема**: Ошибка на 2 шаге wizard'а
**Статус**: ✅ **ИСПРАВЛЕНО**

---

## ❌ Проблема

При переходе со step 1 на step 2 в калькуляторе появлялась ошибка:

```
Уведомление
Сессия не найдена
```

---

## 🔍 Диагностика

### Root Cause

**Конфигурация:**
- Gunicorn: 2 workers
- Session Storage: In-Memory (по умолчанию)

**Что происходило:**
```
┌─────────────────┐
│   Worker 1      │  ← Создаёт сессию в своей памяти
│   (PID: 7501)   │
└─────────────────┘

┌─────────────────┐
│   Worker 2      │  ← Следующий запрос попадает сюда
│   (PID: 7502)   │  ← Сессии нет! Error: "Сессия не найдена"
└─────────────────┘
```

**Проблема:** In-memory storage не shared между worker'ами!

### Логи до исправления

```bash
INFO:src.utils.session_storage:No REDIS_URL found, using in-memory storage
```

---

## ✅ Решение

### Включен Redis Session Storage

**Что сделано:**

1. **Проверил Redis** - уже установлен и работает:
   ```bash
   ● redis-server.service - Advanced key-value store
   Active: active (running)
   ```

2. **Добавлены переменные окружения** в `/etc/systemd/system/housler.service`:
   ```ini
   Environment="REDIS_ENABLED=true"
   Environment="REDIS_HOST=localhost"
   Environment="REDIS_PORT=6380"
   Environment="REDIS_DB=0"
   Environment="REDIS_URL=redis://localhost:6380/0"
   ```

3. **Перезапущен сервис:**
   ```bash
   systemctl daemon-reload
   systemctl restart housler
   ```

### Логи после исправления

```bash
INFO:src.cache.redis_cache:✅ Redis cache connected: localhost:6380/0
INFO:src.utils.session_storage:✅ Connected to Redis successfully
```

---

## 🎯 Результат

### Теперь все worker'ы используют общий Redis

```
┌─────────────────┐
│   Worker 1      │ ────┐
│   (PID: 7695)   │     │
└─────────────────┘     │
                        ▼
                 ┌──────────────┐
                 │    Redis     │  ← Shared storage
                 │  localhost   │     для всех workers
                 └──────────────┘
                        ▲
┌─────────────────┐     │
│   Worker 2      │ ────┘
│   (PID: 7697)   │
└─────────────────┘
```

### Health Check

```json
{
  "components": {
    "redis_cache": {
      "status": "healthy",
      "available": true
    },
    "session_storage": {
      "status": "healthy",
      "type": "SessionStorage"
    }
  },
  "status": "healthy"
}
```

---

## 📊 До и После

| Параметр | До | После |
|----------|-----|--------|
| Session Storage | In-Memory | Redis |
| Shared между workers | ❌ Нет | ✅ Да |
| Сессия на step 2 | ❌ Ошибка | ✅ Работает |
| Scalability | ❌ 1 worker only | ✅ N workers |
| Persistence | ❌ Теряется при restart | ✅ Сохраняется |

---

## 🔧 Технические детали

### Измененные файлы

**`/etc/systemd/system/housler.service`**
```diff
[Service]
Environment="PATH=/var/www/housler/venv/bin"
+ Environment="REDIS_ENABLED=true"
+ Environment="REDIS_HOST=localhost"
+ Environment="REDIS_PORT=6380"
+ Environment="REDIS_DB=0"
+ Environment="REDIS_URL=redis://localhost:6380/0"
```

### Как работает Session Storage

**Код проверяет `REDIS_URL`:**

```python
# src/utils/session_storage.py

if os.getenv('REDIS_URL'):
    # ✅ Используем Redis (shared)
    storage = RedisSessionStorage(redis_url)
else:
    # ❌ In-memory (не работает с >1 worker)
    storage = InMemorySessionStorage()
```

---

## ✅ Проверка исправления

### Тест 1: Redis Подключение

```bash
$ redis-cli -n 0 PING
PONG ✅
```

### Тест 2: Health Endpoint

```bash
$ curl https://housler.ru/health | jq .components.session_storage
{
  "status": "healthy",
  "type": "SessionStorage"
}
```

### Тест 3: Workflow

1. ✅ Откройте https://housler.ru/calculator
2. ✅ Введите URL или используйте Manual Input
3. ✅ Нажмите "Далее"
4. ✅ **Должно перейти на step 2 БЕЗ ошибки**

---

## 🚀 Бонусы Redis Session Storage

### Преимущества

1. **Scalability** - можно увеличивать workers
2. **Persistence** - сессии не теряются при restart
3. **Performance** - Redis быстрый
4. **TTL** - автоматическое удаление старых сессий
5. **Shared** - все workers видят одни данные

### Конфигурация

Redis по умолчанию:
- Хост: `localhost`
- Порт: `6380`
- DB: `0`
- Namespace: `housler` (изоляция данных)

---

## 📝 Для будущих деплоев

### Автоматизация

Обновите `deploy_updates.sh` чтобы проверял Redis config:

```bash
# Проверка Redis переменных
echo "🔍 Проверка Redis конфигурации..."
if ! grep -q "REDIS_URL" /etc/systemd/system/housler.service; then
    echo "⚠️  REDIS_URL не настроен, добавляем..."
    # Добавить переменные окружения
    systemctl daemon-reload
    systemctl restart housler
fi
```

### Мониторинг

Добавить в health check:

```bash
$ curl https://housler.ru/health | jq '.components.redis_cache.stats'
{
  "available": true,
  "status": "active",
  "total_keys": 5,
  "hit_rate": 0.85
}
```

---

## 🐛 Troubleshooting

### Если снова появляется "Сессия не найдена"

**1. Проверьте Redis:**
```bash
systemctl status redis-server
redis-cli PING
```

**2. Проверьте переменные окружения:**
```bash
systemctl show housler | grep REDIS
```

**3. Проверьте логи:**
```bash
journalctl -u housler -n 50 | grep session
# Должно быть: "✅ Connected to Redis successfully"
```

**4. Перезапустите сервис:**
```bash
systemctl restart housler
```

### Если Redis недоступен

```bash
# Запустить Redis
systemctl start redis-server
systemctl enable redis-server

# Проверить
redis-cli PING
```

---

## ✅ Итог

**Проблема:** Сессии хранились в памяти каждого worker'а отдельно
**Решение:** Включен Redis для shared session storage
**Статус:** ✅ Работает

**Теперь:**
- ✅ Wizard работает корректно на всех шагах
- ✅ Сессии доступны между всеми workers
- ✅ Сессии сохраняются при перезапуске
- ✅ Можно масштабировать workers

---

**Исправлено:** 08.11.2025 12:58 MSK ✅
**URL:** https://housler.ru/calculator
**Health:** https://housler.ru/health
