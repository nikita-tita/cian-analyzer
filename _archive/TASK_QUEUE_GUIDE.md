# Руководство по асинхронной очереди задач

## Обзор

Housler использует **RQ (Redis Queue)** для выполнения долгих задач в фоне:
- Парсинг URL недвижимости (10-30 сек)
- Поиск аналогов (30-60 сек)
- Генерация отчетов

## Архитектура

```
┌─────────────┐         ┌──────────┐         ┌─────────────┐
│   Flask     │  POST   │  Redis   │  GET    │  RQ Worker  │
│   App       ├────────▶│  Queue   │◀────────┤  Process    │
└─────────────┘         └──────────┘         └─────────────┘
      │                      │                       │
      │ Poll /api/tasks/     │                       │
      │    status/{job_id}   │                       │
      │◀─────────────────────┘                       │
      │                                               │
      │ GET result                                    │
      │◀──────────────────────────────────────────────┘
```

## Быстрый старт

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 2. Запуск Redis (если не запущен)

```bash
# Docker
docker run -d -p 6380:6380 redis:7-alpine

# Или через brew на macOS
brew services start redis
```

### 3. Запуск RQ воркера

```bash
# В отдельном терминале
python worker.py

# Или с явным указанием Redis
REDIS_URL=redis://localhost:6380/0 python worker.py
```

### 4. Запуск Flask приложения

```bash
flask run
```

## Использование API

### Поставить задачу парсинга в очередь

**Request:**
```bash
POST /api/tasks/parse
Content-Type: application/json

{
  "url": "https://spb.cian.ru/sale/flat/12345/",
  "session_id": "abc-123-def"
}
```

**Response (202 Accepted):**
```json
{
  "job_id": "f0e4a8b6-1234-5678-9abc-def012345678",
  "status": "queued",
  "message": "Task queued successfully",
  "poll_url": "/api/tasks/status/f0e4a8b6-1234-5678-9abc-def012345678"
}
```

### Проверить статус задачи

**Request:**
```bash
GET /api/tasks/status/f0e4a8b6-1234-5678-9abc-def012345678
```

**Response (задача в процессе):**
```json
{
  "job_id": "f0e4a8b6-1234-5678-9abc-def012345678",
  "status": "started",
  "created_at": "2024-01-15T10:00:00",
  "started_at": "2024-01-15T10:00:05",
  "progress": 60,
  "message": "Извлечение данных..."
}
```

**Response (задача выполнена):**
```json
{
  "job_id": "f0e4a8b6-1234-5678-9abc-def012345678",
  "status": "finished",
  "created_at": "2024-01-15T10:00:00",
  "started_at": "2024-01-15T10:00:05",
  "ended_at": "2024-01-15T10:00:35",
  "result": {
    "success": true,
    "data": { /* parsed property data */ },
    "session_id": "abc-123-def"
  }
}
```

**Response (задача провалилась):**
```json
{
  "job_id": "f0e4a8b6-1234-5678-9abc-def012345678",
  "status": "failed",
  "error": "Failed to parse property: timeout"
}
```

### Поставить задачу поиска аналогов

**Request:**
```bash
POST /api/tasks/find-similar
Content-Type: application/json

{
  "session_id": "abc-123-def",
  "target_property": {
    "price": 10000000,
    "total_area": 50,
    "rooms": 2
  },
  "limit": 20,
  "search_strategy": "citywide"
}
```

### Статистика очереди

**Request:**
```bash
GET /api/tasks/queue-stats
```

**Response:**
```json
{
  "queued_jobs": 3,
  "started_jobs": 1,
  "finished_jobs": 45,
  "failed_jobs": 2,
  "deferred_jobs": 0
}
```

## Frontend интеграция

### JavaScript пример с опросом статуса

```javascript
async function parsePropertyAsync(url, sessionId) {
    // Ставим задачу в очередь
    const response = await fetch('/api/tasks/parse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, session_id: sessionId })
    });

    const { job_id } = await response.json();

    // Опрашиваем статус каждые 2 секунды
    return new Promise((resolve, reject) => {
        const pollInterval = setInterval(async () => {
            const statusResponse = await fetch(`/api/tasks/status/${job_id}`);
            const status = await statusResponse.json();

            // Обновляем UI прогресс
            if (status.progress) {
                pixelLoader.updateProgress(status.progress);
                pixelLoader.showMessage(status.message || 'Обработка...');
            }

            // Проверяем завершение
            if (status.status === 'finished') {
                clearInterval(pollInterval);
                resolve(status.result);
            } else if (status.status === 'failed') {
                clearInterval(pollInterval);
                reject(new Error(status.error));
            }
        }, 2000);
    });
}

// Использование
try {
    const result = await parsePropertyAsync(url, sessionId);
    console.log('Парсинг завершен:', result);
} catch (error) {
    console.error('Ошибка парсинга:', error);
}
```

## Конфигурация

### Переменные окружения

```bash
# Redis URL для очереди задач
REDIS_URL=redis://localhost:6380/0

# Таймаут задач (секунды)
RQ_JOB_TIMEOUT=300  # 5 минут

# TTL результатов (секунды)
RQ_RESULT_TTL=3600  # 1 час
```

### app_new.py интеграция

В `app_new.py` добавить:

```python
from src.tasks import init_task_queue
from src.api import task_api

# Инициализация очереди
task_queue = init_task_queue()

# Регистрация blueprint
app.register_blueprint(task_api)
```

## Продакшен деплой

### Systemd service для воркера

Создать `/etc/systemd/system/housler-worker.service`:

```ini
[Unit]
Description=Housler RQ Worker
After=network.target redis.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/housler
Environment="REDIS_URL=redis://localhost:6380/0"
Environment="PYTHONPATH=/var/www/housler"
ExecStart=/var/www/housler/venv/bin/python worker.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Запуск:
```bash
sudo systemctl enable housler-worker
sudo systemctl start housler-worker
sudo systemctl status housler-worker
```

### Масштабирование воркеров

Для обработки большего количества задач, запустите несколько воркеров:

```bash
# Запустить 4 воркера
for i in {1..4}; do
    python worker.py &
done
```

Или через systemd с несколькими инстансами:

```bash
# /etc/systemd/system/housler-worker@.service
# (добавить %i в имя процесса)

sudo systemctl start housler-worker@{1..4}
```

## Мониторинг

### RQ Dashboard (опционально)

```bash
pip install rq-dashboard
rq-dashboard --redis-url redis://localhost:6380/0
```

Откройте http://localhost:9181 для просмотра:
- Количество задач в очереди
- Статус воркеров
- Историю выполнения
- Failed задачи

### Логирование

Воркер пишет логи в stdout:

```bash
# Просмотр логов systemd
sudo journalctl -u housler-worker -f

# Перенаправление в файл
python worker.py >> /var/log/housler/worker.log 2>&1
```

## Troubleshooting

### Воркер не запускается

```bash
# Проверить подключение к Redis
redis-cli ping

# Проверить очередь
redis-cli
> KEYS housler-tasks:*
```

### Задачи не выполняются

1. Проверить, что воркер запущен: `ps aux | grep worker.py`
2. Проверить логи воркера
3. Проверить, что Redis доступен
4. Проверить, что в очереди есть задачи: `GET /api/tasks/queue-stats`

### Failed задачи

```python
# Получить информацию о провалившейся задаче
from rq import Queue
from redis import Redis

redis_conn = Redis.from_url('redis://localhost:6380/0')
queue = Queue('housler-tasks', connection=redis_conn)

# Получить failed jobs
failed_jobs = queue.failed_job_registry.get_job_ids()
for job_id in failed_jobs:
    job = queue.fetch_job(job_id)
    print(f"Job {job_id}: {job.exc_info}")
```

## Преимущества

✅ **Не блокирует UI** - пользователь может продолжать работу пока идет парсинг
✅ **Масштабируемость** - запускайте столько воркеров, сколько нужно
✅ **Надежность** - задачи сохраняются в Redis даже при падении воркера
✅ **Мониторинг** - отслеживание прогресса и статистики
✅ **Fallback** - автоматический переход на синхронное выполнение если Redis недоступен

## Следующие шаги

- [ ] Добавить приоритеты задач (high/normal/low)
- [ ] Реализовать webhook для уведомления о завершении
- [ ] Добавить retry механизм для failed задач
- [ ] Интегрировать с frontend wizard UI
- [ ] Настроить мониторинг с Prometheus
