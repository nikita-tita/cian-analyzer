# Production Setup Guide for Housler.ru

## Проблема: Калькулятор не работает на housler.ru

### Диагностика

Проверены следующие компоненты:
- ✅ Backend API endpoints в [app_new.py](app_new.py:201-756)
- ✅ Frontend JavaScript в [static/js/wizard.js](static/js/wizard.js:1-771)
- ✅ HTML templates ([wizard.html](templates/wizard.html:1-285), [index.html](templates/index.html:1-227))
- ✅ CSS файлы ([wizard.css](static/css/wizard.css:1-50+), [landing.css](static/css/landing.css))
- ❌ SSL сертификат не настроен
- ❌ Nginx конфигурация отсутствовала

### Причина проблемы

1. **SSL сертификат** не настроен для домена housler.ru
2. **Nginx** конфигурация отсутствовала
3. **Статические файлы** (CSS, JS) могут не отдаваться корректно

---

## Решение

### 1. Настройка SSL с Let's Encrypt

На VPS сервере выполните:

```bash
# Установите Certbot
sudo apt-get update
sudo apt-get install certbot python3-certbot-nginx

# Получите SSL сертификат для housler.ru
sudo certbot certonly --standalone -d housler.ru -d www.housler.ru

# Сертификаты будут сохранены в:
# /etc/letsencrypt/live/housler.ru/fullchain.pem
# /etc/letsencrypt/live/housler.ru/privkey.pem
```

### 2. Обновление docker-compose.yml

Добавьте volume для SSL сертификатов в nginx сервис:

```yaml
nginx:
  image: nginx:alpine
  container_name: housler-nginx
  restart: unless-stopped
  ports:
    - "80:80"
    - "443:443"
  volumes:
    - ./nginx/nginx.conf:/etc/nginx/nginx.conf
    - ./nginx/ssl:/etc/nginx/ssl  # Локальная папка
    - ./static:/usr/share/nginx/html/static
    # Или напрямую из Let's Encrypt:
    - /etc/letsencrypt/live/housler.ru:/etc/nginx/ssl:ro
  depends_on:
    - app
  networks:
    - housler-network
  profiles:
    - production
```

### 3. Копирование SSL сертификатов

Если используете локальную папку `nginx/ssl`:

```bash
# На VPS
sudo cp /etc/letsencrypt/live/housler.ru/fullchain.pem ./nginx/ssl/
sudo cp /etc/letsencrypt/live/housler.ru/privkey.pem ./nginx/ssl/
sudo chmod 644 ./nginx/ssl/*.pem
```

### 4. Активация HTTPS в nginx.conf

Раскомментируйте HTTPS server block в [nginx/nginx.conf](nginx/nginx.conf:76-139):

```nginx
server {
    listen 443 ssl http2;
    server_name housler.ru www.housler.ru;

    # SSL Certificates
    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;

    # ... остальная конфигурация
}
```

И раскомментируйте редирект с HTTP на HTTPS (строка 72):

```nginx
server {
    listen 80;
    server_name housler.ru www.housler.ru;

    # Редирект на HTTPS
    return 301 https://$server_name$request_uri;
}
```

### 5. Перезапуск сервисов

```bash
# Пересобрать и перезапустить
docker-compose --profile production down
docker-compose --profile production up -d --build

# Или через Makefile
make down
make build
make up-production
```

---

## Автоматическое обновление SSL сертификатов

Настройте автоматическое обновление через cron:

```bash
# Откройте crontab
sudo crontab -e

# Добавьте строку (обновление каждый понедельник в 3:00)
0 3 * * 1 certbot renew --quiet && cp /etc/letsencrypt/live/housler.ru/*.pem /path/to/housler/nginx/ssl/ && docker-compose -f /path/to/housler/docker-compose.yml restart nginx
```

Или используйте make команду:

```bash
0 3 * * 1 cd /path/to/housler && make ssl-renew
```

---

## Проверка после деплоя

### 1. Проверка health endpoint

```bash
curl http://housler.ru/health
# Должен вернуть: {"status":"healthy",...}

# После настройки SSL:
curl https://housler.ru/health
```

### 2. Проверка статических файлов

```bash
curl -I https://housler.ru/static/css/wizard.css
# Должен вернуть: 200 OK

curl -I https://housler.ru/static/js/wizard.js
# Должен вернуть: 200 OK
```

### 3. Проверка калькулятора

Откройте браузер:
```
https://housler.ru/calculator
```

Должен загрузиться 3-step wizard интерфейс с:
- Шаг 1: Парсинг URL
- Шаг 2: Подбор аналогов
- Шаг 3: Анализ и рекомендации

### 4. Проверка API endpoints

```bash
# Тест парсинга (замените URL на реальный)
curl -X POST https://housler.ru/api/parse \
  -H "Content-Type: application/json" \
  -d '{"url":"https://www.cian.ru/sale/flat/123456/"}'
```

---

## Troubleshooting

### Ошибка: SSL сертификат не найден

```bash
# Проверьте наличие сертификатов
sudo ls -la /etc/letsencrypt/live/housler.ru/

# Если их нет, получите заново
sudo certbot certonly --standalone -d housler.ru -d www.housler.ru
```

### Ошибка: Статические файлы не загружаются (404)

```bash
# Проверьте права доступа
ls -la static/
chmod -R 755 static/

# Проверьте, что файлы скопировались в контейнер
docker exec housler-nginx ls -la /usr/share/nginx/html/static/
```

### Ошибка: "Connection refused" или "502 Bad Gateway"

```bash
# Проверьте, что app контейнер запущен
docker-compose ps

# Проверьте логи
docker-compose logs app
docker-compose logs nginx

# Перезапустите сервисы
docker-compose restart app nginx
```

### Калькулятор загружается, но кнопки не работают

1. Откройте DevTools (F12) → Console
2. Проверьте наличие ошибок JavaScript
3. Проверьте Network tab - загружаются ли все файлы:
   - `/static/css/wizard.css`
   - `/static/js/wizard.js`
   - Bootstrap CSS и JS

Если файлы не загружаются (404):
```bash
# Убедитесь, что static файлы смонтированы в nginx
docker-compose exec nginx ls -la /usr/share/nginx/html/static/
```

---

## Быстрый старт для VPS

Если у вас чистый VPS:

```bash
# 1. Клонируйте репозиторий
git clone https://github.com/yourusername/housler.git
cd housler

# 2. Установите Docker и Docker Compose
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
sudo apt-get install docker-compose-plugin

# 3. Настройте SSL
sudo apt-get install certbot
sudo certbot certonly --standalone -d housler.ru -d www.housler.ru

# 4. Создайте .env из шаблона
cp .env.example .env
# Отредактируйте .env при необходимости

# 5. Скопируйте SSL сертификаты
sudo cp /etc/letsencrypt/live/housler.ru/fullchain.pem ./nginx/ssl/
sudo cp /etc/letsencrypt/live/housler.ru/privkey.pem ./nginx/ssl/
sudo chmod 644 ./nginx/ssl/*.pem

# 6. Раскомментируйте HTTPS в nginx.conf
nano nginx/nginx.conf
# Раскомментируйте server block для port 443

# 7. Запустите через deployment script
chmod +x deploy.sh
./deploy.sh
# Выберите: 2) Production (app + redis + nginx)

# 8. Проверьте
curl https://housler.ru/health
```

---

## Контакты для поддержки

- Email: hello@housler.ru
- Telegram: @housler_spb

## Дополнительные ресурсы

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)
- [Nginx Configuration Guide](https://nginx.org/en/docs/)
