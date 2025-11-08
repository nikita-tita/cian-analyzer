# Housler Deployment Guide

Полное руководство по развертыванию Housler v2.0 в production.

---

## Содержание
1. [Требования](#требования)
2. [Docker Deployment](#docker-deployment)
3. [Production Setup](#production-setup)
4. [Мониторинг](#мониторинг)
5. [Troubleshooting](#troubleshooting)

---

## Требования

### Минимальные
- **CPU**: 2 cores
- **RAM**: 4 GB
- **Disk**: 20 GB SSD
- **OS**: Ubuntu 20.04+ / Debian 11+ / CentOS 8+
- **Docker**: 20.10+
- **Docker Compose**: 1.29+

### Рекомендуемые (Production)
- **CPU**: 4 cores
- **RAM**: 8 GB
- **Disk**: 50 GB SSD
- **Network**: 100 Mbps+

---

## Docker Deployment

### Быстрый старт (Development)

```bash
# 1. Клонируем репозиторий
git clone https://github.com/your-org/housler.git
cd housler

# 2. Создаем .env файл
cat > .env << EOF
REDIS_ENABLED=true
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
REDIS_NAMESPACE=housler
FLASK_ENV=production
EOF

# 3. Запускаем через Docker Compose
docker-compose up -d

# 4. Проверяем health
curl http://localhost:5000/health
```

**Результат:**
- ✅ App: http://localhost:5000
- ✅ Redis: localhost:6379
- ✅ Health: http://localhost:5000/health

---

### Production Deployment

#### 1. Подготовка сервера

```bash
# Обновляем систему
sudo apt update && sudo apt upgrade -y

# Устанавливаем Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Устанавливаем Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Проверяем
docker --version
docker-compose --version
```

#### 2. Конфигурация

Создаем production конфиг:

```bash
# .env.production
cat > .env.production << 'EOF'
# Redis
REDIS_ENABLED=true
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=CHANGE_ME_STRONG_PASSWORD
REDIS_NAMESPACE=housler_prod

# Flask
FLASK_ENV=production
FLASK_DEBUG=false

# Gunicorn
WORKERS=4
WORKER_CLASS=sync
TIMEOUT=300
BIND=0.0.0.0:5000

# Rate Limiting
RATELIMIT_STORAGE_URL=redis://redis:6379/1
EOF
```

**Security:**
```bash
# Генерируем strong password для Redis
openssl rand -base64 32
```

#### 3. Запуск с мониторингом

```bash
# Запускаем с Prometheus и Grafana
docker-compose --profile monitoring up -d

# Проверяем статус
docker-compose ps
```

**Доступ:**
- App: http://localhost:5000
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (admin/admin)

#### 4. Nginx Reverse Proxy (опционально)

Для production с SSL:

```bash
# nginx/nginx.conf
cat > nginx/nginx.conf << 'EOF'
user nginx;
worker_processes auto;

events {
    worker_connections 1024;
}

http {
    upstream housler_app {
        server app:5000;
    }

    server {
        listen 80;
        server_name housler.ru www.housler.ru;

        # Redirect HTTP to HTTPS
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name housler.ru www.housler.ru;

        # SSL certificates
        ssl_certificate /etc/nginx/ssl/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/privkey.pem;

        # SSL settings
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;
        ssl_prefer_server_ciphers on;

        # Security headers
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;

        # Proxy to Flask app
        location / {
            proxy_pass http://housler_app;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            # Timeouts
            proxy_connect_timeout 300s;
            proxy_send_timeout 300s;
            proxy_read_timeout 300s;
        }

        # Static files
        location /static/ {
            alias /usr/share/nginx/html/static/;
            expires 30d;
        }
    }
}
EOF
```

Запуск с Nginx:

```bash
# Получаем SSL сертификаты (Let's Encrypt)
sudo certbot certonly --standalone -d housler.ru -d www.housler.ru

# Копируем в nginx/ssl/
sudo cp /etc/letsencrypt/live/housler.ru/fullchain.pem nginx/ssl/
sudo cp /etc/letsencrypt/live/housler.ru/privkey.pem nginx/ssl/

# Запускаем с nginx profile
docker-compose --profile production up -d
```

---

## Production Setup

### 1. Database Backup (Redis)

Создаем cron job для автоматического бэкапа:

```bash
# backup-redis.sh
#!/bin/bash
BACKUP_DIR="/backups/redis"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR
docker exec housler-redis redis-cli BGSAVE
sleep 5
docker cp housler-redis:/data/dump.rdb $BACKUP_DIR/dump_$DATE.rdb

# Удаляем старые бэкапы (>7 дней)
find $BACKUP_DIR -name "dump_*.rdb" -mtime +7 -delete

echo "Backup completed: dump_$DATE.rdb"
```

Добавляем в crontab:

```bash
# Бэкап каждый день в 3:00 AM
0 3 * * * /opt/housler/backup-redis.sh >> /var/log/housler-backup.log 2>&1
```

### 2. Log Rotation

```bash
# /etc/logrotate.d/housler
/opt/housler/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 housler housler
    sharedscripts
    postrotate
        docker-compose -f /opt/housler/docker-compose.yml restart app
    endscript
}
```

### 3. System Service (systemd)

```bash
# /etc/systemd/system/housler.service
[Unit]
Description=Housler Real Estate Analytics
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/housler
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

Активация:

```bash
sudo systemctl enable housler
sudo systemctl start housler
sudo systemctl status housler
```

---

## Мониторинг

### Grafana Dashboards

#### 1. Импорт Housler Dashboard

```bash
# Заходим в Grafana
http://localhost:3000

# Login: admin / admin
# Add Data Source → Prometheus → http://prometheus:9090

# Import Dashboard:
# - Dashboard ID: создаем custom
# - Metrics: housler_*
```

#### 2. Основные метрики для отслеживания

**Application:**
- `housler_up` - Статус приложения
- `housler_cache_hit_rate` - Cache hit rate (%)
- `housler_cache_keys_total` - Количество ключей в кэше

**System:**
- CPU usage
- Memory usage
- Disk I/O
- Network traffic

**Redis:**
- Connected clients
- Used memory
- Evicted keys
- Commands processed

### Alerting

Prometheus alerts configuration:

```yaml
# monitoring/alerts.yml
groups:
  - name: housler_alerts
    interval: 30s
    rules:
      # Application down
      - alert: HouslerDown
        expr: housler_up == 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Housler application is down"
          description: "Housler has been down for more than 5 minutes"

      # Low cache hit rate
      - alert: LowCacheHitRate
        expr: housler_cache_hit_rate < 50
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "Low cache hit rate: {{ $value }}%"
          description: "Cache hit rate is below 50% for 15 minutes"

      # High memory usage
      - alert: HighMemoryUsage
        expr: container_memory_usage_bytes{name="housler-app"} / container_spec_memory_limit_bytes{name="housler-app"} > 0.9
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage: {{ $value | humanizePercentage }}"
```

---

## Troubleshooting

### Common Issues

#### 1. Application не стартует

**Симптомы:**
```bash
docker-compose ps
# housler-app: Exit 1
```

**Решение:**
```bash
# Проверяем логи
docker-compose logs app

# Частые причины:
# - Redis недоступен → проверить REDIS_HOST
# - Playwright не установлен → playwright install chromium
# - Порт занят → изменить BIND в .env
```

#### 2. High CPU usage

**Симптомы:**
- Медленные ответы API
- CPU > 80%

**Решение:**
```bash
# Увеличить количество workers
# в .env:
WORKERS=8  # вместо 4

# Или уменьшить concurrent parsing
# в коде: max_concurrent=3  # вместо 5
```

#### 3. Redis connection timeout

**Симптомы:**
```
redis.exceptions.ConnectionError: Error connecting to Redis
```

**Решение:**
```bash
# 1. Проверить Redis
docker-compose ps redis
docker-compose logs redis

# 2. Увеличить timeout
# в app_new.py:
storage_options={"socket_connect_timeout": 60}  # было 30

# 3. Restart Redis
docker-compose restart redis
```

#### 4. Rate limit ошибки

**Симптомы:**
```json
{
  "error": "429 Too Many Requests"
}
```

**Решение:**
```bash
# Временно увеличить лимиты
# в app_new.py:
default_limits=["500 per day", "100 per hour"]

# Или очистить rate limit storage
docker exec housler-redis redis-cli FLUSHDB
```

---

## Scaling

### Horizontal Scaling (Multiple instances)

```yaml
# docker-compose.scale.yml
version: '3.8'

services:
  app:
    deploy:
      replicas: 3  # 3 инстанса

  nginx:
    # Load balancer config
    volumes:
      - ./nginx/nginx-lb.conf:/etc/nginx/nginx.conf
```

Nginx load balancer:

```nginx
upstream housler_cluster {
    least_conn;
    server app_1:5000;
    server app_2:5000;
    server app_3:5000;
}
```

---

## Maintenance

### Updates

```bash
# 1. Pull latest
git pull origin main

# 2. Rebuild images
docker-compose build --no-cache

# 3. Zero-downtime restart
docker-compose up -d --force-recreate --no-deps app

# 4. Verify
curl http://localhost:5000/health
```

### Database migrations

```bash
# Redis не требует migrations
# Но при изменении схемы кэша:

# 1. Flush cache
docker exec housler-redis redis-cli FLUSHDB

# 2. Restart app
docker-compose restart app
```

---

## Security Checklist

- [ ] Изменен дефолтный Redis password
- [ ] Настроен firewall (allow только 80/443)
- [ ] SSL сертификаты установлены
- [ ] Rate limiting включен
- [ ] Security headers настроены
- [ ] Логи ротируются
- [ ] Бэкапы автоматизированы
- [ ] Мониторинг настроен
- [ ] Обновления автоматизированы

---

## Support

- **Documentation**: `/API_DOCS.md`
- **Issues**: GitHub Issues
- **Email**: support@housler.ru

---

**Housler v2.0** - Ready for Production 🚀
