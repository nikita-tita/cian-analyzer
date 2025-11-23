# Housler Monitoring

Система мониторинга для отслеживания здоровья и производительности Housler.

## Компоненты

### 1. Health Check Script (`check_health.sh`)

Bash-скрипт для автоматической проверки работоспособности всех компонентов системы.

**Проверяет:**
- ✅ Главная страница (HTTP 200)
- ✅ `/health` API endpoint
- ✅ `/api/tasks/queue-stats` - статистика очереди
- ✅ `/metrics` - Prometheus metrics
- ✅ Systemd services (housler, housler-worker, redis, nginx)

**Использование:**

```bash
# Ручной запуск
chmod +x monitoring/check_health.sh
./monitoring/check_health.sh

# С кастомным URL
SITE_URL=https://housler.ru ./monitoring/check_health.sh

# Настройка cron (каждые 5 минут)
crontab -e
# Добавить:
*/5 * * * * /var/www/housler/monitoring/check_health.sh >> /var/log/housler/health.log 2>&1
```

**Алерты:**

Если настроена почта, скрипт отправляет email при падении:

```bash
ALERT_EMAIL=admin@housler.ru ./monitoring/check_health.sh
```

### 2. Monitoring Dashboard (`dashboard.html`)

Веб-интерфейс для визуального мониторинга в реальном времени.

**Показывает:**
- 🏥 System Health (статус компонентов)
- ⚙️ Task Queue (очередь задач)
- 💾 Redis Cache (кеш статистика)

**Автообновление:** каждые 30 секунд

**Запуск:**

```bash
# Способ 1: Через Python HTTP server
cd /var/www/housler/monitoring
python3 -m http.server 8080

# Открыть: http://localhost:8080/dashboard.html
```

```bash
# Способ 2: Добавить роут в app_new.py
@app.route('/monitoring')
def monitoring_dashboard():
    return send_file('monitoring/dashboard.html')

# Открыть: https://housler.ru/monitoring
```

## Установка на продакшен

### 1. Создать директорию для логов

```bash
sudo mkdir -p /var/log/housler
sudo chown housler:www-data /var/log/housler
```

### 2. Скопировать скрипт

```bash
sudo cp monitoring/check_health.sh /var/www/housler/monitoring/
sudo chmod +x /var/www/housler/monitoring/check_health.sh
```

### 3. Настроить cron

```bash
sudo -u housler crontab -e
```

Добавить:
```
# Housler health check (каждые 5 минут)
*/5 * * * * /var/www/housler/monitoring/check_health.sh >> /var/log/housler/health.log 2>&1

# Очистка старых логов (раз в неделю)
0 0 * * 0 find /var/log/housler -name "health.log" -mtime +30 -delete
```

### 4. Добавить dashboard route (опционально)

В `app_new.py` добавить:

```python
from flask import send_file

@app.route('/monitoring')
def monitoring_dashboard():
    """Monitoring dashboard"""
    return send_file('monitoring/dashboard.html')
```

Перезапустить:
```bash
sudo systemctl restart housler
```

Открыть: https://housler.ru/monitoring

### 5. Nginx Basic Auth (опционально)

Для защиты dashboard паролем:

```bash
# Создать пароль
sudo htpasswd -c /etc/nginx/.htpasswd admin
```

В nginx config добавить:
```nginx
location /monitoring {
    auth_basic "Housler Monitoring";
    auth_basic_user_file /etc/nginx/.htpasswd;
    proxy_pass http://127.0.0.1:8001;
}
```

```bash
sudo nginx -t && sudo systemctl reload nginx
```

## Метрики

### Доступные endpoints:

#### 1. `/health` - System Health

```bash
curl https://housler.ru/health | jq .
```

**Ответ:**
```json
{
  "status": "healthy",
  "timestamp": "2025-11-23T20:00:00",
  "components": {
    "parser": {"status": "healthy"},
    "redis_cache": {"status": "healthy"},
    "session_storage": {"status": "healthy"},
    "browser_pool": {"status": "healthy"}
  }
}
```

#### 2. `/api/tasks/queue-stats` - Task Queue

```bash
curl https://housler.ru/api/tasks/queue-stats | jq .
```

**Ответ:**
```json
{
  "queued_jobs": 3,
  "started_jobs": 1,
  "finished_jobs": 245,
  "failed_jobs": 2,
  "deferred_jobs": 0,
  "scheduled_jobs": 0
}
```

#### 3. `/api/cache/stats` - Cache Statistics

```bash
curl https://housler.ru/api/cache/stats | jq .
```

**Ответ:**
```json
{
  "available": true,
  "stats": {
    "keyspace_hits": 1234,
    "keyspace_misses": 456,
    "hit_rate": 72.99
  }
}
```

#### 4. `/metrics` - Prometheus Metrics

```bash
curl https://housler.ru/metrics
```

**Формат:** Plain text (Prometheus exposition format)

## Интеграция с Prometheus (опционально)

### 1. Установить Prometheus

```bash
wget https://github.com/prometheus/prometheus/releases/download/v2.45.0/prometheus-2.45.0.linux-amd64.tar.gz
tar xvfz prometheus-*.tar.gz
cd prometheus-*
```

### 2. Конфигурация `prometheus.yml`

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'housler'
    static_configs:
      - targets: ['localhost:8001']
    metrics_path: /metrics
```

### 3. Запуск

```bash
./prometheus --config.file=prometheus.yml
```

Открыть: http://localhost:9090

### 4. Grafana Dashboard (опционально)

```bash
docker run -d -p 3000:3000 grafana/grafana
```

Открыть: http://localhost:3000 (admin/admin)

Добавить Prometheus data source: http://localhost:9090

## Алерты

### Настройка email алертов через Prometheus Alertmanager

**alertmanager.yml:**
```yaml
route:
  receiver: 'email'

receivers:
  - name: 'email'
    email_configs:
      - to: 'admin@housler.ru'
        from: 'alerts@housler.ru'
        smarthost: 'smtp.gmail.com:587'
        auth_username: 'alerts@housler.ru'
        auth_password: '<password>'
```

**alert_rules.yml:**
```yaml
groups:
  - name: housler_alerts
    rules:
      - alert: HighFailedTasks
        expr: failed_jobs > 10
        for: 5m
        annotations:
          summary: "High number of failed tasks"

      - alert: ServiceDown
        expr: up{job="housler"} == 0
        for: 1m
        annotations:
          summary: "Housler service is down"
```

## Troubleshooting

### Проблема: Health check падает

```bash
# Проверить логи
tail -f /var/log/housler/health.log

# Проверить cron
sudo -u housler crontab -l

# Проверить права
ls -la /var/www/housler/monitoring/check_health.sh
```

### Проблема: Dashboard не отображает данные

```bash
# Проверить API endpoints
curl https://housler.ru/health
curl https://housler.ru/api/tasks/queue-stats

# Проверить CORS (если dashboard на другом домене)
# В app_new.py добавить:
from flask_cors import CORS
CORS(app)
```

### Проблема: Метрики не собираются

```bash
# Проверить endpoint
curl https://housler.ru/metrics

# Проверить Prometheus targets
# Открыть: http://localhost:9090/targets
```

## Best Practices

1. **Регулярный мониторинг:** Проверяйте dashboard минимум раз в день
2. **Логи:** Храните логи минимум 30 дней
3. **Алерты:** Настройте уведомления для критичных метрик
4. **Резервное копирование:** Бэкапьте метрики Prometheus
5. **Документация:** Обновляйте runbook при изменениях

## Links

- **Dashboard:** https://housler.ru/monitoring (после настройки)
- **Prometheus:** http://localhost:9090
- **Grafana:** http://localhost:3000

---

**Автор:** Generated with Claude Code
**Дата:** 2025-11-23
