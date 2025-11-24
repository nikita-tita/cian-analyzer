# Async Task Queue - Быстрый старт

## Что это?

Система асинхронных задач для выполнения долгих операций (парсинг, поиск аналогов) в фоне, не блокируя UI.

## Локальная разработка

### 1. Установить зависимости

```bash
pip install -r requirements.txt
```

### 2. Запустить Redis

```bash
# Docker (рекомендуется)
docker run -d -p 6379:6379 --name redis redis:7-alpine

# Или Homebrew на macOS
brew install redis
brew services start redis
```

### 3. Запустить RQ воркер (в отдельном терминале)

```bash
python worker.py
```

Вы должны увидеть:
```
✅ Connected to Redis
🚀 Worker started, waiting for tasks...
```

### 4. Запустить Flask приложение

```bash
flask run
```

## Тестирование

### Поставить задачу в очередь

```bash
curl -X POST http://localhost:5000/api/tasks/parse \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://spb.cian.ru/sale/flat/12345/",
    "session_id": "test-123"
  }'
```

Ответ:
```json
{
  "job_id": "f0e4a8b6-1234-5678...",
  "status": "queued",
  "poll_url": "/api/tasks/status/f0e4a8b6-1234-5678..."
}
```

### Проверить статус

```bash
curl http://localhost:5000/api/tasks/status/f0e4a8b6-1234-5678...
```

### Статистика очереди

```bash
curl http://localhost:5000/api/tasks/queue-stats
```

## Production деплой

См. [TASK_QUEUE_GUIDE.md](./TASK_QUEUE_GUIDE.md) для подробной инструкции.

### Быстрая настройка с systemd

```bash
# 1. Скопировать service файл
sudo cp housler-worker.service /etc/systemd/system/

# 2. Изменить пути в файле
sudo nano /etc/systemd/system/housler-worker.service

# 3. Включить и запустить
sudo systemctl daemon-reload
sudo systemctl enable housler-worker
sudo systemctl start housler-worker

# 4. Проверить статус
sudo systemctl status housler-worker
```

## Архитектура

```
┌──────────┐  enqueue    ┌────────┐  fetch    ┌──────────┐
│  Flask   │────────────▶│ Redis  │◀──────────│ Worker   │
│  App     │             │ Queue  │           │ Process  │
└────┬─────┘             └────────┘           └─────┬────┘
     │                                               │
     │ poll status                                   │
     │◀──────────────────────────────────────────────┘
     │ get result
```

## Troubleshooting

**Worker не запускается:**
```bash
# Проверить Redis
redis-cli ping  # должен ответить PONG

# Проверить логи
python worker.py  # смотреть вывод
```

**Задачи не выполняются:**
```bash
# Проверить, что worker запущен
ps aux | grep worker.py

# Проверить очередь
curl http://localhost:5000/api/tasks/queue-stats
```

**Redis недоступен в production:**
```bash
# Проверить systemd service
sudo systemctl status redis

# Проверить подключение
redis-cli -h localhost -p 6379 ping
```

## Интеграция с Frontend

```javascript
// Пример: асинхронный парсинг с прогресс-баром
async function parseAsync(url, sessionId) {
    // Поставить в очередь
    const res = await fetch('/api/tasks/parse', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({url, session_id: sessionId})
    });
    const {job_id} = await res.json();

    // Показать loader
    pixelLoader.show('parsing');

    // Опрос статуса
    const result = await pollTaskStatus(job_id);

    // Скрыть loader
    pixelLoader.hide();

    return result;
}

async function pollTaskStatus(jobId) {
    while (true) {
        const res = await fetch(`/api/tasks/status/${jobId}`);
        const status = await res.json();

        // Обновить прогресс
        if (status.progress) {
            pixelLoader.updateProgress(status.progress);
        }

        // Проверить завершение
        if (status.status === 'finished') {
            return status.result;
        } else if (status.status === 'failed') {
            throw new Error(status.error);
        }

        // Подождать 2 секунды
        await new Promise(r => setTimeout(r, 2000));
    }
}
```

## Полезные команды

```bash
# Просмотр логов worker (systemd)
sudo journalctl -u housler-worker -f

# Перезапуск worker
sudo systemctl restart housler-worker

# Очистка Redis очереди
redis-cli FLUSHDB

# Просмотр задач в Redis
redis-cli KEYS "rq:job:*"
```

## Что дальше?

✅ Система готова к использованию!

Следующие шаги:
1. Обновить app_new.py для использования task API
2. Интегрировать с frontend wizard.js
3. Добавить мониторинг (опционально)
4. Настроить масштабирование воркеров (опционально)

См. [TASK_QUEUE_GUIDE.md](./TASK_QUEUE_GUIDE.md) для деталей.
