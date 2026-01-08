# 🚨 Быстрое исправление калькулятора на housler.ru

## Проблема
Калькулятор не работает на housler.ru из-за:
1. ❌ SSL сертификат не настроен
2. ❌ Nginx конфигурация отсутствовала
3. ❌ Статические файлы не отдаются

## ✅ Решение (3 минуты)

### Вариант А: Автоматическая установка

На VPS выполните:

```bash
# 1. Перейдите в директорию проекта
cd /path/to/housler

# 2. Загрузите обновления из Git
git pull origin main

# 3. Запустите скрипт установки SSL (от root)
sudo ./setup_ssl.sh
```

Готово! Калькулятор будет доступен на https://housler.ru/calculator

---

### Вариант Б: Ручная установка

#### Шаг 1: Установите SSL сертификат

```bash
sudo apt-get update
sudo apt-get install certbot

# Остановите Docker (временно)
docker-compose down

# Получите сертификат
sudo certbot certonly --standalone -d housler.ru -d www.housler.ru

# Скопируйте сертификаты
sudo mkdir -p nginx/ssl
sudo cp /etc/letsencrypt/live/housler.ru/fullchain.pem nginx/ssl/
sudo cp /etc/letsencrypt/live/housler.ru/privkey.pem nginx/ssl/
sudo chmod 644 nginx/ssl/*.pem
```

#### Шаг 2: Обновите nginx.conf

Откройте `nginx/nginx.conf` и раскомментируйте:

1. HTTPS server block (строки 76-139)
2. HTTP → HTTPS редирект (строка 72)

Или выполните:

```bash
# Автоматически раскомментировать
sed -i 's/# server {/server {/g' nginx/nginx.conf
sed -i 's/#     /    /g' nginx/nginx.conf
sed -i 's/# return 301 https/return 301 https/g' nginx/nginx.conf
```

#### Шаг 3: Запустите с production профилем

```bash
docker-compose --profile production up -d --build
```

#### Шаг 4: Проверьте

```bash
curl https://housler.ru/health
# Должно вернуть: {"status":"healthy",...}

# Откройте в браузере:
# https://housler.ru/calculator
```

---

## 🔍 Проверка работы

### 1. Health Check
```bash
curl https://housler.ru/health
```
Ожидаемый результат: `{"status":"healthy","version":"2.0.0",...}`

### 2. Статические файлы
```bash
curl -I https://housler.ru/static/css/wizard.css
curl -I https://housler.ru/static/js/wizard.js
```
Оба должны вернуть `200 OK`

### 3. Калькулятор в браузере
Откройте: https://housler.ru/calculator

Должны видеть:
- ✅ 3-step wizard интерфейс
- ✅ Шаг 1: Поле ввода URL
- ✅ Кнопка "Спарсить объект"
- ✅ Progress bar вверху

### 4. Тест API
```bash
curl -X POST https://housler.ru/api/parse \
  -H "Content-Type: application/json" \
  -d '{"url":"https://spb.cian.ru/sale/flat/315831388/"}'
```

Должен вернуть JSON с данными объекта.

---

## 🐛 Если что-то не работает

### Проблема: "SSL certificate problem"

```bash
# Проверьте, что сертификаты на месте
sudo ls -la /etc/letsencrypt/live/housler.ru/
ls -la nginx/ssl/

# Если нет - получите заново
sudo certbot certonly --standalone -d housler.ru -d www.housler.ru
```

### Проблема: "404 Not Found" на статические файлы

```bash
# Проверьте, что файлы существуют
ls -la static/css/
ls -la static/js/

# Проверьте, что они смонтированы в nginx
docker exec housler-nginx ls -la /usr/share/nginx/html/static/

# Если нет - перезапустите
docker-compose --profile production restart
```

### Проблема: "502 Bad Gateway"

```bash
# Проверьте логи
docker-compose logs app
docker-compose logs nginx

# Проверьте, что app запущен
docker-compose ps

# Перезапустите всё
docker-compose --profile production down
docker-compose --profile production up -d
```

### Проблема: Кнопки в калькуляторе не работают

1. Откройте DevTools (F12) → Console
2. Ищите JavaScript ошибки
3. Проверьте Network tab - все ли файлы загружаются:
   - `/static/css/wizard.css` → 200 OK
   - `/static/js/wizard.js` → 200 OK
   - Bootstrap CDN файлы → 200 OK

Если wizard.js не загружается (404):
```bash
# Проверьте путь к файлу
ls -la static/js/wizard.js

# Проверьте права
chmod 644 static/js/wizard.js

# Перезапустите nginx
docker-compose restart nginx
```

---

## 📋 Чеклист после установки

- [ ] `curl https://housler.ru/health` → 200 OK
- [ ] `curl -I https://housler.ru/static/css/wizard.css` → 200 OK
- [ ] `curl -I https://housler.ru/static/js/wizard.js` → 200 OK
- [ ] https://housler.ru → лендинг загружается
- [ ] https://housler.ru/calculator → wizard интерфейс загружается
- [ ] Кнопка "Спарсить объект" работает
- [ ] API endpoints отвечают
- [ ] SSL сертификат валиден (зелёный замок в браузере)
- [ ] Нет ошибок в DevTools Console

---

## 📞 Если нужна помощь

Соберите информацию для диагностики:

```bash
# Версия Docker
docker --version

# Статус контейнеров
docker-compose ps

# Логи за последние 50 строк
docker-compose logs --tail=50 app
docker-compose logs --tail=50 nginx

# Проверка портов
sudo netstat -tlnp | grep -E ':(80|443|5000)'

# SSL сертификат
sudo certbot certificates
```

Отправьте вывод команд в поддержку.

---

## 📚 Дополнительная документация

- [PRODUCTION_SETUP.md](PRODUCTION_SETUP.md) - полное руководство по production setup
- [DEPLOYMENT.md](DEPLOYMENT.md) - документация по деплою
- [API_DOCS.md](API_DOCS.md) - описание API endpoints
- [README.md](README.md) - основная документация проекта
