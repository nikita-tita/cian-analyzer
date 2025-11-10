# 🚀 Быстрый гайд по деплою

## 3 способа деплоя из Claude Code

### 1️⃣ Самый простой - Slash-команда
```bash
/deploy
```
Выберите режим: 1, 2 или 3

---

### 2️⃣ Прямой запуск скрипта
```bash
bash scripts/auto-deploy.sh 1     # Development
bash scripts/auto-deploy.sh 2     # Production
bash scripts/auto-deploy.sh 3     # Full Stack
```

---

### 3️⃣ GitHub Actions (автоматически)
```bash
git push origin main              # Автодеплой!
```

---

## 📊 Проверка статуса

```bash
/status
# или
bash scripts/check-status.sh
```

---

## 🔄 Быстрый перезапуск

```bash
bash scripts/quick-restart.sh
```

---

## 📝 Логи

```bash
/logs
# или
docker-compose logs -f app
```

---

## 🛑 Остановка

```bash
/stop
# или
docker-compose down
```

---

## 🎯 Режимы деплоя

| Режим | Что включает | Когда использовать |
|-------|-------------|-------------------|
| **1. Development** | App + Redis | Разработка, тесты |
| **2. Production** | App + Redis + Nginx | Production без мониторинга |
| **3. Full Stack** | App + Redis + Prometheus + Grafana | Production с мониторингом |

---

## ✅ После деплоя проверьте:

```bash
# Health check
curl http://localhost:5000/health

# Статус контейнеров
docker-compose ps

# Логи
docker-compose logs -f app
```

---

## 🆘 Если что-то пошло не так:

```bash
# 1. Остановить все
docker-compose down

# 2. Очистить
docker system prune -a

# 3. Пересобрать
docker-compose build --no-cache

# 4. Запустить заново
bash scripts/auto-deploy.sh 1
```

---

**Полная документация:** [CLAUDE_CODE_DEPLOY.md](CLAUDE_CODE_DEPLOY.md)
