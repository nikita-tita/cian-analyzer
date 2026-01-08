# 🚀 Auto-Deploy из Claude Code

Система автоматического деплоя для Housler, интегрированная с Claude Code.

---

## 📋 Содержание

1. [Быстрый старт](#быстрый-старт)
2. [Slash-команды](#slash-команды)
3. [Скрипты деплоя](#скрипты-деплоя)
4. [GitHub Actions](#github-actions)
5. [Troubleshooting](#troubleshooting)

---

## 🚀 Быстрый старт

### Деплой через Claude Code

#### Вариант 1: Slash-команда
```bash
/deploy
```

Затем выберите режим:
- `1` - Development (App + Redis)
- `2` - Production (App + Redis + Nginx)
- `3` - Full Stack (App + Redis + Monitoring)

#### Вариант 2: Прямая команда
```bash
bash scripts/auto-deploy.sh 1  # Development
bash scripts/auto-deploy.sh 2  # Production
bash scripts/auto-deploy.sh 3  # Full Stack
```

#### Вариант 3: Пропустить тесты
```bash
bash scripts/auto-deploy.sh 1 true  # Деплой без запуска тестов
```

---

## 📝 Slash-команды

Все команды доступны в Claude Code через `/` префикс:

### `/deploy` - Деплой приложения
Запускает полный цикл деплоя:
- ✅ Проверка prerequisites
- ✅ Создание .env если отсутствует
- ✅ Build Docker images
- ✅ Запуск тестов
- ✅ Деплой сервисов
- ✅ Health checks

**Пример:**
```bash
/deploy
# Выбираете режим: 1, 2 или 3
```

### `/status` - Проверка статуса
Показывает текущее состояние:
- Запущенные контейнеры
- Health check приложения
- Информацию о последнем деплое
- Использование ресурсов

**Пример:**
```bash
/status
```

### `/logs` - Просмотр логов
Показывает логи приложения:
```bash
/logs
```

### `/stop` - Остановка сервисов
Останавливает все контейнеры:
```bash
/stop
```

---

## 🔧 Скрипты деплоя

### 1. Основной деплой - `scripts/auto-deploy.sh`

**Использование:**
```bash
bash scripts/auto-deploy.sh [MODE] [SKIP_TESTS]
```

**Параметры:**
- `MODE`:
  - `1`, `dev`, `development` - Development режим
  - `2`, `prod`, `production` - Production режим
  - `3`, `full`, `monitoring` - Full Stack с мониторингом
- `SKIP_TESTS`: `true` для пропуска тестов (по умолчанию: `false`)

**Примеры:**
```bash
# Development с тестами
bash scripts/auto-deploy.sh 1

# Production без тестов
bash scripts/auto-deploy.sh production true

# Full Stack с мониторингом
bash scripts/auto-deploy.sh 3
```

**Что делает скрипт:**
1. ✅ Проверяет наличие Docker и Docker Compose
2. ✅ Создает .env из .env.example если нужно
3. ✅ Останавливает существующие контейнеры
4. ✅ Собирает Docker images
5. ✅ Запускает тесты (если не пропущены)
6. ✅ Деплоит сервисы с выбранным профилем
7. ✅ Ждет готовности приложения
8. ✅ Проверяет health endpoint
9. ✅ Сохраняет информацию о деплое в `.last-deploy.json`

---

### 2. Проверка статуса - `scripts/check-status.sh`

**Использование:**
```bash
bash scripts/check-status.sh
```

**Показывает:**
- 📊 Список запущенных контейнеров
- ✅ Health status приложения
- 📅 Информацию о последнем деплое
- 💻 Использование CPU и памяти

---

### 3. Быстрый перезапуск - `scripts/quick-restart.sh`

**Использование:**
```bash
bash scripts/quick-restart.sh
```

**Что делает:**
- 🔄 Пересобирает только app контейнер
- 🚀 Перезапускает app без остановки других сервисов
- ✅ Проверяет health после перезапуска

**Когда использовать:**
- Изменили код приложения
- Нужен быстрый перезапуск без пересборки всего стека
- Zero-downtime обновление

---

## ⚙️ GitHub Actions

### Автоматический деплой при push

Workflow `.github/workflows/auto-deploy.yml` автоматически деплоит при push в `main` или `master`.

#### Что включает:

**Job 1: Test**
- Запуск unit тестов
- Code coverage
- Code quality проверки

**Job 2: Build**
- Сборка Docker image
- Тестирование образа

**Job 3: Deploy**
- SSH деплой на сервер (если настроен)
- Health check после деплоя
- Deployment summary

#### Настройка SSH деплоя:

Добавьте secrets в GitHub (Settings → Secrets → Actions):

```
SSH_HOST         = your.server.com
SSH_USERNAME     = deploy_user
SSH_PRIVATE_KEY  = -----BEGIN OPENSSH PRIVATE KEY-----
                   ваш приватный ключ...
                   -----END OPENSSH PRIVATE KEY-----
```

#### Ручной запуск:

```
1. Перейдите в Actions
2. Выберите "Auto Deploy on Push"
3. Нажмите "Run workflow"
4. Выберите environment (development/production/staging)
5. Нажмите "Run workflow"
```

---

## 🔍 Мониторинг деплоя

### После деплоя доступны:

#### Development режим:
- **Application:** http://localhost:5000
- **Health Check:** http://localhost:5000/health
- **Metrics:** http://localhost:5000/metrics
- **Redis:** localhost:6380

#### Production режим (+ Nginx):
- **Application:** http://localhost:80
- **Health Check:** http://localhost:80/health
- **Metrics:** http://localhost:80/metrics

#### Full Stack режим (+ Monitoring):
- **Prometheus:** http://localhost:9090
- **Grafana:** http://localhost:3000 (admin/admin)

### Полезные команды:

```bash
# Просмотр логов
docker-compose logs -f app

# Логи Redis
docker-compose logs -f redis

# Все логи
docker-compose logs -f

# Статус контейнеров
docker-compose ps

# Рестарт приложения
docker-compose restart app

# Полная остановка
docker-compose down

# Остановка с удалением volumes
docker-compose down -v
```

---

## 🐛 Troubleshooting

### Проблема: Порт 5000 занят

**Решение:**
```bash
# Найти процесс
lsof -i :5000

# Или
netstat -tunlp | grep 5000

# Остановить текущие контейнеры
docker-compose down
```

### Проблема: Docker build ошибка

**Решение:**
```bash
# Очистить Docker cache
docker system prune -a

# Пересобрать без cache
docker-compose build --no-cache
```

### Проблема: Health check failed

**Решение:**
```bash
# Проверить логи
docker-compose logs app | tail -50

# Проверить Redis
docker-compose logs redis

# Проверить вручную
curl http://localhost:5000/health

# Зайти в контейнер
docker-compose exec app /bin/bash
```

### Проблема: Тесты падают

**Решение:**
```bash
# Запустить тесты вручную
docker-compose up -d redis
docker-compose run --rm app python -m pytest tests/ -v

# Или деплоить без тестов
bash scripts/auto-deploy.sh 1 true
```

### Проблема: .env не найден

**Решение:**
```bash
# Создать из примера
cp .env.example .env

# Или скрипт создаст автоматически
bash scripts/auto-deploy.sh 1
```

---

## 📊 Информация о деплое

После каждого успешного деплоя создается файл `.last-deploy.json`:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "mode": "Production",
  "git_commit": "abc123def456",
  "git_branch": "main",
  "status": "success"
}
```

Просмотр:
```bash
cat .last-deploy.json | python3 -m json.tool
```

---

## 🎯 Workflow примеры

### Сценарий 1: Разработка нового фичи

```bash
# 1. Деплой Development режима
/deploy
# Выберите: 1

# 2. Работаете над кодом...

# 3. Быстрый перезапуск после изменений
bash scripts/quick-restart.sh

# 4. Проверяете статус
/status

# 5. Смотрите логи
/logs
```

### Сценарий 2: Production деплой

```bash
# 1. Коммитите изменения
git add .
git commit -m "feat: новая фича"
git push origin main

# 2. GitHub Actions автоматически деплоит

# 3. Или вручную:
bash scripts/auto-deploy.sh production

# 4. Проверяете
bash scripts/check-status.sh
```

### Сценарий 3: Полный стек с мониторингом

```bash
# 1. Деплой Full Stack
bash scripts/auto-deploy.sh 3

# 2. Открываете Grafana
# http://localhost:3000

# 3. Проверяете метрики в Prometheus
# http://localhost:9090

# 4. Мониторите приложение
docker stats
```

---

## 📚 Дополнительные ресурсы

- **API Documentation:** [API_DOCS.md](API_DOCS.md)
- **Deployment Guide:** [DEPLOYMENT.md](DEPLOYMENT.md)
- **Architecture:** [ARCHITECTURE_DIAGRAM.md](ARCHITECTURE_DIAGRAM.md)
- **Testing Guide:** [TESTING_GUIDE.md](TESTING_GUIDE.md)

---

## 🆘 Поддержка

Если что-то не работает:

1. Проверьте логи: `docker-compose logs -f`
2. Проверьте статус: `bash scripts/check-status.sh`
3. Пересоберите: `docker-compose build --no-cache`
4. Откройте issue на GitHub

---

**Готово к деплою! 🚀**
