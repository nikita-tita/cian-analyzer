# 🚀 ПЛАН ДЕПЛОЯ HOUSLER V2.0 (PRODUCTION-READY)

## 📋 ИСПОЛНИТЕЛЬНОЕ РЕЗЮМЕ

**Версия:** 2.0.0 (Security Hardened)
**Дата последнего обновления:** 2025-11-08
**Статус готовности:** ✅ **READY FOR PRODUCTION** (после выполнения чеклиста)

**Критические исправления в этом релизе:**
- ✅ CSP заголовки (защита от XSS)
- ✅ URL валидация (защита от SSRF)
- ✅ Timeout для парсинга (защита от DoS)
- ✅ Input validation (Pydantic)
- ✅ SECRET_KEY из .env
- ✅ Удален мертвый код (-8739 строк)

**Security Score:** 7/10 (было 3/10)

---

## 🎯 ПРЕДВАРИТЕЛЬНЫЕ ТРЕБОВАНИЯ

### 1. Серверные требования

**Минимальные:**
- CPU: 2 cores
- RAM: 4 GB
- Storage: 20 GB SSD
- OS: Ubuntu 20.04+ / Debian 11+

**Рекомендуемые (для production):**
- CPU: 4 cores
- RAM: 8 GB
- Storage: 50 GB SSD
- OS: Ubuntu 22.04 LTS

### 2. Software Stack

| Компонент | Версия | Назначение |
|-----------|--------|-----------|
| Python | 3.11+ | Runtime |
| Docker | 24.0+ | Containerization |
| Docker Compose | 2.20+ | Orchestration |
| Redis | 7.0+ | Cache + Sessions + Rate limiting |
| Nginx | 1.24+ | Reverse proxy + SSL |
| Let's Encrypt | - | SSL certificates |

### 3. Доменное имя и DNS

- Зарегистрированный домен (например: `housler.ru`)
- DNS записи:
  ```
  A     @         123.45.67.89
  A     www       123.45.67.89
  ```

---

## 📦 ШАГИ ДЕПЛОЯ

### ЭТАП 1: Подготовка сервера (30 мин)

#### 1.1. Подключение к серверу

```bash
# SSH подключение
ssh root@YOUR_SERVER_IP

# Создание пользователя для приложения
adduser housler
usermod -aG sudo housler
usermod -aG docker housler

# Переключение на нового пользователя
su - housler
```

#### 1.2. Установка зависимостей

```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка базовых утилит
sudo apt install -y git curl wget htop vim

# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo systemctl enable docker
sudo systemctl start docker

# Установка Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Проверка установки
docker --version
docker-compose --version
```

#### 1.3. Клонирование репозитория

```bash
# Создание директории для проекта
mkdir -p ~/apps
cd ~/apps

# Клонирование
git clone https://github.com/nikita-tita/cian-analyzer.git
cd cian-analyzer

# Checkout production ветки
git checkout claude/code-review-architecture-011CUvJKazXuQRKVZUYaj2H9

# Проверка последних изменений
git log --oneline -5
```

---

### ЭТАП 2: Конфигурация (15 мин)

#### 2.1. Создание .env файла

```bash
# Копирование шаблона
cp .env.example .env

# Редактирование
nano .env
```

**Обязательные параметры:**

```bash
# Flask
FLASK_ENV=production
FLASK_DEBUG=false
SECRET_KEY=<СГЕНЕРИРОВАТЬ!>  # См. ниже

# Redis (обязательно для production!)
REDIS_ENABLED=true
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=<СЛУЧАЙНЫЙ_ПАРОЛЬ>
REDIS_NAMESPACE=housler

# Gunicorn
WORKERS=4
WORKER_CLASS=sync
TIMEOUT=300
BIND=0.0.0.0:5000

# Parser
DEFAULT_REGION=spb
PARSER_HEADLESS=true
PARSER_DELAY=1.0
MAX_CONCURRENT_PARSING=5

# Rate Limiting
RATELIMIT_ENABLED=true
RATELIMIT_DEFAULT=200 per day, 50 per hour
RATELIMIT_PARSE=10 per minute
RATELIMIT_SEARCH=15 per minute
RATELIMIT_ANALYZE=20 per minute
```

#### 2.2. Генерация SECRET_KEY

```bash
# КРИТИЧНО! Генерируем случайный ключ
openssl rand -hex 32

# Вставляем результат в .env:
# SECRET_KEY=abcd1234...generated_hex_string...5678efgh
```

#### 2.3. Генерация Redis пароля

```bash
# Генерируем случайный пароль для Redis
openssl rand -base64 32

# Вставляем в .env:
# REDIS_PASSWORD=<generated_password>
```

#### 2.4. Настройка Nginx (опционально, для SSL)

Если используете Nginx на хосте (не в Docker):

```bash
sudo nano /etc/nginx/sites-available/housler.conf
```

Конфигурация:

```nginx
server {
    listen 80;
    server_name housler.ru www.housler.ru;

    # Redirect to HTTPS
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name housler.ru www.housler.ru;

    # SSL certificates (Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/housler.ru/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/housler.ru/privkey.pem;

    # SSL settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Security headers (additional to app's CSP)
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Proxy to Docker container
    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout 300;
        proxy_send_timeout 300;
        proxy_read_timeout 300;
    }

    # Static files (optional optimization)
    location /static/ {
        alias /home/housler/apps/cian-analyzer/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

Активация:

```bash
sudo ln -s /etc/nginx/sites-available/housler.conf /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

### ЭТАП 3: SSL Сертификаты (10 мин)

#### 3.1. Установка Certbot

```bash
sudo apt install -y certbot python3-certbot-nginx
```

#### 3.2. Получение сертификатов

```bash
# Остановка Nginx на время
sudo systemctl stop nginx

# Получение сертификата
sudo certbot certonly --standalone -d housler.ru -d www.housler.ru

# Запуск Nginx
sudo systemctl start nginx
```

#### 3.3. Автообновление сертификатов

```bash
# Проверка автообновления
sudo certbot renew --dry-run

# Настройка cron для автообновления (если нужно)
sudo crontab -e

# Добавить строку:
0 3 * * * certbot renew --quiet --post-hook "systemctl reload nginx"
```

---

### ЭТАП 4: Запуск приложения (5 мин)

#### 4.1. Production режим

```bash
cd ~/apps/cian-analyzer

# Сборка и запуск всех сервисов
docker-compose --profile production up -d --build

# Проверка статуса
docker-compose ps

# Ожидаемый вывод:
# NAME                    SERVICE     STATUS
# cian-analyzer-app-1     app         running
# cian-analyzer-redis-1   redis       running
# cian-analyzer-nginx-1   nginx       running (optional)
```

#### 4.2. Проверка логов

```bash
# Логи приложения
docker-compose logs -f app

# Должно быть:
# ✓ Redis connected
# ✓ Rate limiting initialized
# ✓ Running on http://0.0.0.0:5000
```

#### 4.3. Health Check

```bash
# Проверка health endpoint
curl http://localhost:5000/health

# Ожидаемый ответ:
{
  "status": "healthy",
  "version": "2.0.0",
  "components": {
    "redis_cache": {"status": "healthy"},
    "session_storage": {"status": "healthy"},
    "parser": {"status": "healthy"}
  }
}

# Проверка через внешний домен
curl https://housler.ru/health
```

---

### ЭТАП 5: Мониторинг (опционально, 15 мин)

#### 5.1. Запуск с Prometheus + Grafana

```bash
# Запуск с мониторингом
docker-compose --profile monitoring --profile production up -d

# Сервисы:
# - App: http://localhost:5000
# - Prometheus: http://localhost:9090
# - Grafana: http://localhost:3000 (admin/admin)
```

#### 5.2. Настройка Grafana

1. Открыть http://YOUR_SERVER_IP:3000
2. Логин: `admin` / `admin` (сменить пароль!)
3. Add Data Source → Prometheus
   - URL: `http://prometheus:9090`
   - Save & Test
4. Import Dashboard:
   - Dashboard ID: 1860 (Node Exporter Full)
   - Или создать кастомный для Housler metrics

---

### ЭТАП 6: Тестирование (10 мин)

#### 6.1. Функциональное тестирование

```bash
# Тест 1: Landing page
curl -I https://housler.ru/
# Expected: HTTP/2 200 + Security headers

# Тест 2: Calculator page
curl -I https://housler.ru/calculator
# Expected: HTTP/2 200

# Тест 3: API парсинг (с валидным URL)
curl -X POST https://housler.ru/api/parse \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.cian.ru/sale/flat/315831388/"}'
# Expected: {"status": "success", ...}

# Тест 4: API парсинг (с невалидным URL - должен блокироваться)
curl -X POST https://housler.ru/api/parse \
  -H "Content-Type: application/json" \
  -d '{"url": "http://localhost:6379/"}'
# Expected: {"status": "error", "message": "Домен localhost не разрешен"}

# Тест 5: Rate limiting
for i in {1..15}; do
  curl -X POST https://housler.ru/api/parse \
    -H "Content-Type: application/json" \
    -d '{"url": "https://www.cian.ru/sale/flat/123/"}'
done
# Expected: После 10 запросов - 429 Too Many Requests
```

#### 6.2. Security тестирование

```bash
# Тест XSS (должен блокироваться CSP)
curl https://housler.ru/ -I | grep -i content-security-policy
# Expected: Content-Security-Policy: default-src 'self'; ...

# Тест SSRF (должен блокироваться)
curl -X POST https://housler.ru/api/parse \
  -H "Content-Type: application/json" \
  -d '{"url": "http://169.254.169.254/latest/meta-data/"}'
# Expected: {"status": "error", "message": "Запрещен доступ к internal IP"}

# Тест clickjacking (должен блокироваться)
curl https://housler.ru/ -I | grep -i x-frame-options
# Expected: X-Frame-Options: DENY
```

#### 6.3. Performance тестирование

```bash
# Установка Apache Bench
sudo apt install -y apache2-utils

# Тест нагрузки (100 запросов, 10 одновременных)
ab -n 100 -c 10 https://housler.ru/

# Ожидаемые результаты:
# - Requests per second: > 50
# - Time per request: < 200ms
# - Failed requests: 0
```

---

## 🔧 POST-DEPLOYMENT CHECKLIST

### Безопасность

- [ ] SECRET_KEY установлен (64 hex символа)
- [ ] REDIS_PASSWORD установлен
- [ ] SSL сертификаты установлены и работают
- [ ] CSP заголовки включены (проверить в браузере DevTools)
- [ ] Rate limiting работает (протестировать)
- [ ] SSRF защита работает (попробовать localhost)
- [ ] Firewall настроен (только 80, 443, 22)

### Производительность

- [ ] Redis работает и доступен
- [ ] Health check возвращает "healthy"
- [ ] Prometheus собирает метрики
- [ ] Логи пишутся без ошибок
- [ ] Memory usage < 1GB на worker
- [ ] CPU usage < 50% в idle

### Мониторинг

- [ ] Grafana dashboard настроен
- [ ] Alerts настроены (опционально)
- [ ] Log rotation настроен

```bash
# Настройка logrotate
sudo nano /etc/logrotate.d/housler

# Содержимое:
/home/housler/apps/cian-analyzer/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0644 housler housler
    sharedscripts
    postrotate
        docker-compose -f /home/housler/apps/cian-analyzer/docker-compose.yml restart app > /dev/null
    endscript
}
```

### Backup

- [ ] Database backup настроен (если используется)
- [ ] .env файл в безопасном месте
- [ ] SSL сертификаты забэкаплены

```bash
# Создание backup script
nano ~/backup.sh

#!/bin/bash
BACKUP_DIR=~/backups
DATE=$(date +%Y%m%d_%H%M%S)

# Создаем директорию
mkdir -p $BACKUP_DIR

# Backup .env
cp ~/apps/cian-analyzer/.env $BACKUP_DIR/.env_$DATE

# Backup Redis data (если персистентность включена)
docker exec cian-analyzer-redis-1 redis-cli SAVE
cp ~/apps/cian-analyzer/redis_data/dump.rdb $BACKUP_DIR/redis_$DATE.rdb

# Cleanup old backups (старше 30 дней)
find $BACKUP_DIR -name "*.rdb" -mtime +30 -delete

echo "Backup completed: $DATE"

# Делаем исполняемым
chmod +x ~/backup.sh

# Добавляем в cron (ежедневно в 2:00)
crontab -e
0 2 * * * /home/housler/backup.sh >> /home/housler/backup.log 2>&1
```

---

## 🔄 ОБНОВЛЕНИЕ ПРИЛОЖЕНИЯ

### Обновление кода

```bash
cd ~/apps/cian-analyzer

# Останавливаем приложение
docker-compose down

# Получаем обновления
git fetch origin
git checkout <new-branch-or-tag>

# Rebuild и перезапуск
docker-compose --profile production up -d --build

# Проверяем
docker-compose logs -f app
curl http://localhost:5000/health
```

### Rolling update (zero downtime)

```bash
# Если используется Docker Swarm или Kubernetes
docker service update --image housler:2.0.0 housler_app

# Или для docker-compose (manual rolling update):
docker-compose up -d --no-deps --scale app=2 app
sleep 30  # Ждем запуска нового контейнера
docker-compose up -d --no-deps --scale app=1 app
```

---

## 🚨 TROUBLESHOOTING

### Проблема: App не запускается

```bash
# Проверяем логи
docker-compose logs app

# Типичные ошибки:
# 1. "SECRET_KEY must be set in production"
#    → Добавить SECRET_KEY в .env

# 2. "Redis connection refused"
#    → Проверить: docker-compose ps redis
#    → Проверить: REDIS_HOST=redis в .env

# 3. "Permission denied"
#    → sudo chown -R housler:housler ~/apps/cian-analyzer
```

### Проблема: High memory usage

```bash
# Проверяем использование памяти
docker stats

# Если app использует > 2GB:
# 1. Уменьшить WORKERS в .env (например, с 4 до 2)
# 2. Добавить memory limits в docker-compose.yml:
#    deploy:
#      resources:
#        limits:
#          memory: 1G
```

### Проблема: Slow parsing

```bash
# Проверяем Redis cache hit rate
curl http://localhost:5000/api/cache/stats

# Если hit_rate < 50%:
# 1. Увеличить Redis memory:
#    maxmemory 1gb в redis.conf
# 2. Проверить TTL кэша (24h по умолчанию)
```

### Проблема: SSL ошибки

```bash
# Проверяем сертификаты
sudo certbot certificates

# Обновляем вручную
sudo certbot renew --force-renewal

# Проверяем Nginx конфигурацию
sudo nginx -t
```

---

## 📊 МЕТРИКИ И МОНИТОРИНГ

### Prometheus Metrics

Доступны на `http://localhost:9090/metrics`:

```
# Application metrics
housler_up                     # 1 if app is running
housler_cache_hit_rate         # Cache hit rate percentage
housler_cache_keys_total       # Total cached keys

# System metrics (via Node Exporter)
node_cpu_seconds_total
node_memory_MemAvailable_bytes
node_disk_io_time_seconds_total
```

### Key Performance Indicators (KPIs)

| Метрика | Целевое значение | Критичное |
|---------|------------------|-----------|
| Uptime | > 99.9% | < 99% |
| Response time (p95) | < 500ms | > 2s |
| Cache hit rate | > 70% | < 30% |
| Error rate | < 0.1% | > 1% |
| Memory usage per worker | < 500MB | > 1GB |
| CPU usage (avg) | < 40% | > 80% |

### Alerting (опционально)

Настройка alerts в Prometheus:

```yaml
# /home/housler/apps/cian-analyzer/monitoring/alerts.yml
groups:
  - name: housler_alerts
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        annotations:
          summary: "High error rate detected"

      - alert: HighMemoryUsage
        expr: container_memory_usage_bytes{name="cian-analyzer-app-1"} > 1e9
        for: 10m
        annotations:
          summary: "App using > 1GB memory"

      - alert: LowCacheHitRate
        expr: housler_cache_hit_rate < 30
        for: 15m
        annotations:
          summary: "Cache hit rate below 30%"
```

---

## 🔐 SECURITY BEST PRACTICES

### 1. Firewall Configuration

```bash
# UFW (Ubuntu)
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable

# Проверка
sudo ufw status
```

### 2. SSH Hardening

```bash
# Отключаем root login
sudo nano /etc/ssh/sshd_config

# Изменить:
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes

# Перезапуск SSH
sudo systemctl restart sshd
```

### 3. Regular Updates

```bash
# Автоматические обновления безопасности
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades

# Проверка доступных обновлений
sudo apt update
sudo apt list --upgradable
```

### 4. Secrets Management

```bash
# НЕ коммитить .env в git!
echo ".env" >> .gitignore

# Использовать secrets manager для production:
# - AWS Secrets Manager
# - HashiCorp Vault
# - Docker Secrets (if using Swarm)
```

---

## 📈 SCALING GUIDELINES

### Horizontal Scaling (Multiple Servers)

1. **Setup Load Balancer** (Nginx, HAProxy, AWS ALB)

```nginx
upstream housler_backend {
    least_conn;
    server 10.0.1.10:5000 weight=1;
    server 10.0.1.11:5000 weight=1;
    server 10.0.1.12:5000 weight=1;
}

server {
    listen 443 ssl http2;
    server_name housler.ru;

    location / {
        proxy_pass http://housler_backend;
    }
}
```

2. **Shared Redis** (все серверы используют один Redis)

```bash
# На сервере Redis
REDIS_HOST=redis.internal.domain.com
REDIS_PORT=6379
```

3. **Shared Storage** (для session persistence)
   - NFS
   - AWS EFS
   - GlusterFS

### Vertical Scaling (More Resources)

| Concurrent Users | CPU | RAM | Workers |
|------------------|-----|-----|---------|
| < 100 | 2 cores | 4 GB | 2 |
| 100-500 | 4 cores | 8 GB | 4 |
| 500-2000 | 8 cores | 16 GB | 8 |
| > 2000 | Horizontal scaling | | |

---

## 📞 SUPPORT & MAINTENANCE

### Log Locations

```bash
# Application logs
~/apps/cian-analyzer/logs/app.log

# Docker logs
docker-compose logs app
docker-compose logs redis

# Nginx logs (if on host)
/var/log/nginx/access.log
/var/log/nginx/error.log

# System logs
journalctl -u docker
```

### Common Maintenance Tasks

```bash
# Очистка Docker images
docker system prune -a

# Очистка Redis cache
docker exec cian-analyzer-redis-1 redis-cli FLUSHDB

# Restart приложения
docker-compose restart app

# Полный restart всех сервисов
docker-compose down && docker-compose --profile production up -d
```

---

## ✅ DEPLOYMENT CHECKLIST (FINAL)

### Pre-Deployment

- [ ] .env файл создан и заполнен
- [ ] SECRET_KEY сгенерирован (64 chars)
- [ ] REDIS_PASSWORD установлен
- [ ] DNS записи настроены
- [ ] Сервер обновлен (apt update && upgrade)
- [ ] Docker и Docker Compose установлены
- [ ] Firewall настроен (22, 80, 443)

### Deployment

- [ ] Репозиторий склонирован
- [ ] .env файл на месте
- [ ] docker-compose up -d успешно
- [ ] Health check возвращает 200 OK
- [ ] SSL сертификаты получены
- [ ] Nginx настроен и работает

### Post-Deployment

- [ ] Все тесты пройдены (функциональные, security, performance)
- [ ] Мониторинг настроен (Prometheus + Grafana)
- [ ] Alerts настроены (опционально)
- [ ] Backup script настроен
- [ ] Logrotate настроен
- [ ] Документация обновлена

### Production Ready

- [ ] Security headers проверены в браузере
- [ ] Rate limiting работает
- [ ] SSRF защита протестирована
- [ ] CSP policy валидна
- [ ] Uptime monitoring настроен
- [ ] Support контакты обновлены

---

## 🎉 ПОЗДРАВЛЯЕМ!

Ваше приложение Housler v2.0 успешно развернуто в production!

**Что дальше?**

1. Мониторинг первых 24 часов
2. Настройка дополнительных alerts
3. Оптимизация на основе реальной нагрузки
4. Сбор обратной связи от пользователей

**Полезные ссылки:**

- Health Check: https://housler.ru/health
- Prometheus: https://housler.ru:9090 (если открыт)
- Grafana: https://housler.ru:3000 (если открыт)

---

**Вопросы или проблемы?**

Проверьте секцию Troubleshooting или создайте issue в GitHub.

**Версия документа:** 1.0.0
**Последнее обновление:** 2025-11-08
