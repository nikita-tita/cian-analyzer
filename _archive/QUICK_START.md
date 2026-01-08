# ⚡ QUICK START GUIDE - HOUSLER V2.0

## 🚀 Быстрый запуск за 5 минут

### 1. Подготовка (1 мин)

```bash
# Клонируем репозиторий
git clone https://github.com/nikita-tita/cian-analyzer.git
cd cian-analyzer

# Checkout production ветки
git checkout claude/code-review-architecture-011CUvJKazXuQRKVZUYaj2H9
```

### 2. Конфигурация (2 мин)

```bash
# Копируем шаблон .env
cp .env.example .env

# Генерируем SECRET_KEY
echo "SECRET_KEY=$(openssl rand -hex 32)" >> .env

# Генерируем Redis пароль  
echo "REDIS_PASSWORD=$(openssl rand -base64 32)" >> .env

# Включаем Redis
sed -i 's/REDIS_ENABLED=false/REDIS_ENABLED=true/g' .env
```

### 3. Запуск (2 мин)

```bash
# Запускаем все сервисы
docker-compose up -d --build

# Ждем запуска (30 сек)
sleep 30

# Проверяем health
curl http://localhost:5000/health
```

### 4. Проверка

Открываем в браузере: http://localhost:5000

---

## 📚 Дополнительная документация

- **Полный план деплоя:** DEPLOYMENT_PLAN.md
- **API документация:** API_DOCS.md

**Для production обязательно следуйте DEPLOYMENT_PLAN.md!**
