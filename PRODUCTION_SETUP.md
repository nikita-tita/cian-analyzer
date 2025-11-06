# Production Setup Guide

Руководство по настройке production-ready инфраструктуры для Cian Real Estate Analyzer.

## 🎯 Обзор улучшений

### Что было добавлено:

1. **Redis** - для хранения сессий пользователей
2. **PostgreSQL** - для исторических данных и аналитики
3. **Система логирования** - структурированное логирование с метриками
4. **Кэширование** - многоуровневое кэширование (Memory → Redis → PostgreSQL)
5. **Асинхронный парсинг** - параллельный парсинг для ускорения

---

## 📦 Установка зависимостей

### 1. Базовые зависимости

```bash
pip install -r requirements.txt
```

### 2. Playwright (для парсинга)

```bash
playwright install
```

---

## 🔧 Настройка инфраструктуры

### Redis (Session Storage)

#### Установка на Ubuntu/Debian:

```bash
sudo apt-get update
sudo apt-get install redis-server

# Запуск Redis
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Проверка
redis-cli ping
# Должно вернуть: PONG
```

#### Установка на macOS:

```bash
brew install redis

# Запуск
brew services start redis

# Проверка
redis-cli ping
```

#### Установка на Windows:

```bash
# Используйте WSL2 или Docker
docker run -d -p 6379:6379 redis:latest
```

#### Конфигурация Redis (.env):

```env
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0
REDIS_TTL=3600
```

---

### PostgreSQL (Historical Data)

#### Установка на Ubuntu/Debian:

```bash
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib

# Запуск PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

#### Создание базы данных:

```bash
# Подключаемся к PostgreSQL
sudo -u postgres psql

# Создаем пользователя и базу
CREATE USER cian_user WITH PASSWORD 'your_secure_password';
CREATE DATABASE cian_analyzer OWNER cian_user;
GRANT ALL PRIVILEGES ON DATABASE cian_analyzer TO cian_user;

# Выход
\q
```

#### Конфигурация PostgreSQL (.env):

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=cian_analyzer
POSTGRES_USER=cian_user
POSTGRES_PASSWORD=your_secure_password
```

#### Автоматическая инициализация схемы:

При первом запуске приложения схема БД создастся автоматически.

Проверить можно так:

```bash
psql -U cian_user -d cian_analyzer -c "\dt"
```

Должны быть таблицы:
- `analyses`
- `market_data`
- `parsed_properties`

---

## 🚀 Запуск приложения

### Режим разработки:

```bash
# Создайте .env файл из примера
cp .env.example .env

# Отредактируйте .env под ваши настройки
nano .env

# Запустите приложение
python app_production.py
```

### Режим production с Gunicorn:

```bash
# Установка Gunicorn
pip install gunicorn

# Запуск с 4 воркерами
gunicorn -w 4 -b 0.0.0.0:5002 app_production:app

# С логированием
gunicorn -w 4 -b 0.0.0.0:5002 \
  --access-logfile logs/access.log \
  --error-logfile logs/error.log \
  app_production:app
```

### Docker Compose (рекомендуется):

Создайте `docker-compose.yml`:

```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "5002:5002"
    environment:
      - REDIS_HOST=redis
      - POSTGRES_HOST=postgres
      - POSTGRES_PASSWORD=secure_password
    depends_on:
      - redis
      - postgres
    volumes:
      - ./logs:/app/logs

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=cian_analyzer
      - POSTGRES_USER=cian_user
      - POSTGRES_PASSWORD=secure_password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  redis_data:
  postgres_data:
```

Запуск:

```bash
docker-compose up -d
```

---

## 🔍 Мониторинг

### Health Check Endpoint

```bash
curl http://localhost:5002/health
```

Ответ:

```json
{
  "status": "healthy",
  "timestamp": "2025-01-15T10:30:00",
  "services": {
    "redis": true,
    "postgres": true,
    "cache": true
  }
}
```

### Метрики производительности

```bash
curl http://localhost:5002/api/metrics
```

Ответ:

```json
{
  "status": "success",
  "performance_metrics": {
    "api.parse_url.duration": {
      "count": 150,
      "avg": 2.5,
      "min": 1.2,
      "max": 5.8
    },
    "parser.playwright.success": {
      "count": 145,
      "total": 145
    }
  },
  "storage_stats": {
    "session_manager": {
      "redis_available": true,
      "active_sessions": 23
    },
    "postgres_manager": {
      "total_analyses": 1250,
      "analyses_24h": 45
    },
    "cache_manager": {
      "memory_cache_size": 85,
      "memory_max_size": 100
    }
  }
}
```

---

## ⚡ Производительность

### Сравнение синхронного и асинхронного парсинга:

**Синхронный парсинг (старый):**
- 20 объектов: ~60 секунд
- 1 объект/сек

**Асинхронный парсинг (новый):**
- 20 объектов: ~12 секунд (max_concurrent=5)
- 1.6 объектов/сек
- **Ускорение: 5x**

### Настройка производительности (.env):

```env
# Увеличить параллелизм (требует больше ресурсов)
ASYNC_MAX_CONCURRENT=10

# Увеличить размер in-memory кэша
CACHE_MEMORY_MAX_SIZE=500

# Увеличить TTL для кэширования объектов
CACHE_DEFAULT_TTL=7200
```

---

## 📊 Структура БД

### Таблица `analyses`

Хранит все выполненные анализы:

```sql
SELECT
    id,
    session_id,
    target_url,
    target_price,
    fair_price,
    recommendations_count,
    created_at
FROM analyses
ORDER BY created_at DESC
LIMIT 10;
```

### Таблица `market_data`

Историческая статистика рынка:

```sql
SELECT
    city,
    district,
    rooms,
    median_price_per_sqm,
    recorded_at
FROM market_data
WHERE city = 'Санкт-Петербург'
  AND recorded_at >= NOW() - INTERVAL '30 days'
ORDER BY recorded_at DESC;
```

### Таблица `parsed_properties`

Кэш парсированных объектов:

```sql
-- Очистка истекшего кэша
DELETE FROM parsed_properties
WHERE expires_at < NOW();
```

---

## 🐛 Troubleshooting

### Redis недоступен

**Симптом:** В логах `⚠️ Redis недоступен, использую in-memory fallback`

**Решение:**

```bash
# Проверьте статус Redis
sudo systemctl status redis-server

# Перезапустите Redis
sudo systemctl restart redis-server

# Проверьте подключение
redis-cli ping
```

### PostgreSQL недоступен

**Симптом:** В логах `⚠️ PostgreSQL initialization failed`

**Решение:**

```bash
# Проверьте статус PostgreSQL
sudo systemctl status postgresql

# Проверьте подключение
psql -U cian_user -d cian_analyzer -c "SELECT 1"

# Проверьте права доступа
# В /etc/postgresql/.../pg_hba.conf должна быть строка:
# host    all             all             127.0.0.1/32            md5
```

### Playwright ошибки

**Симптом:** `playwright._impl._api_types.Error: Browser closed`

**Решение:**

```bash
# Переустановите Playwright
playwright install

# Для headless режима на серверах нужны дополнительные пакеты
sudo apt-get install -y \
  libnss3 \
  libnspr4 \
  libatk1.0-0 \
  libatk-bridge2.0-0 \
  libcups2 \
  libdrm2 \
  libxkbcommon0 \
  libxcomposite1 \
  libxdamage1 \
  libxfixes3 \
  libxrandr2 \
  libgbm1 \
  libpango-1.0-0 \
  libcairo2 \
  libasound2
```

### Медленный парсинг

**Решение:**

1. Увеличьте `ASYNC_MAX_CONCURRENT` в .env
2. Используйте кэширование (по умолчанию включено)
3. Проверьте скорость сети до cian.ru

---

## 📈 Масштабирование

### Горизонтальное масштабирование

1. **Используйте внешний Redis** (AWS ElastiCache, Redis Cloud)
2. **Используйте внешний PostgreSQL** (AWS RDS, Heroku Postgres)
3. **Несколько инстансов приложения** за load balancer (Nginx, HAProxy)

Пример Nginx конфигурации:

```nginx
upstream cian_analyzer {
    server app1:5002;
    server app2:5002;
    server app3:5002;
}

server {
    listen 80;
    server_name analyzer.example.com;

    location / {
        proxy_pass http://cian_analyzer;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Вертикальное масштабирование

Увеличьте ресурсы:

```yaml
# docker-compose.yml
services:
  app:
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G
```

---

## 🔐 Безопасность

### Рекомендации:

1. **Используйте сильные пароли** для Redis и PostgreSQL
2. **Не коммитьте .env файл** в git
3. **Используйте SSL/TLS** для production
4. **Ограничьте доступ** к Redis и PostgreSQL по IP
5. **Регулярно обновляйте зависимости**

### Пример безопасной конфигурации Redis:

```bash
# /etc/redis/redis.conf
bind 127.0.0.1
requirepass your_very_strong_password
maxmemory 2gb
maxmemory-policy allkeys-lru
```

---

## 📝 Логирование

### Структура логов:

```
logs/
  ├── cian_analyzer.log       # Основные логи
  ├── access.log              # HTTP access логи (Gunicorn)
  └── error.log               # Error логи (Gunicorn)
```

### Ротация логов (logrotate):

```bash
# /etc/logrotate.d/cian-analyzer
/path/to/cian-analyzer/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 www-data www-data
    sharedscripts
    postrotate
        systemctl reload gunicorn
    endscript
}
```

---

## 🎓 Дополнительные ресурсы

- **Redis документация:** https://redis.io/docs/
- **PostgreSQL документация:** https://www.postgresql.org/docs/
- **Playwright документация:** https://playwright.dev/python/
- **Flask Production Guide:** https://flask.palletsprojects.com/en/latest/deploying/

---

## 📞 Поддержка

При возникновении проблем:

1. Проверьте логи: `tail -f logs/cian_analyzer.log`
2. Проверьте health endpoint: `curl http://localhost:5002/health`
3. Проверьте метрики: `curl http://localhost:5002/api/metrics`

---

**Версия:** 2.0
**Дата обновления:** 2025-01-15
