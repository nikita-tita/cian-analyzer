# ⚡ Быстрая настройка calendar.housler.ru (20 минут)

**Цель:** Перенести веб-приложение календаря на поддомен `calendar.housler.ru`

---

## 🎯 Что получим:
- ✅ Профессиональный домен: `https://calendar.housler.ru`
- ✅ HTTPS с Let's Encrypt
- ✅ Telegram Web App на своём домене
- ✅ TODO и Calendar работают в веб-приложении

---

## 📋 Шаг 1: DNS запись (2 минуты + 5-10 мин propagation)

### Добавьте A-запись в панели управления доменом:

**Где:** Панель управления доменом `housler.ru` (REG.RU или где зарегистрирован)

**Параметры:**
```
Тип:     A
Имя:     calendar
Значение: 91.229.8.221
TTL:     3600
```

### Проверка DNS (подождите 5-10 минут):
```bash
# Должно вернуть: 91.229.8.221
dig calendar.housler.ru +short

# Или
nslookup calendar.housler.ru
```

⏰ **Пока DNS propagates, SSH разблокируется и можно будет продолжить!**

---

## 🔧 Шаг 2: Настройка сервера (15 минут)

### 2.1. Подключитесь к серверу:
```bash
ssh root@91.229.8.221
```

### 2.2. Установите Nginx и Certbot (если не установлены):
```bash
apt update
apt install -y nginx certbot python3-certbot-nginx
```

### 2.3. Скопируйте Nginx конфигурацию:

**На вашей локальной машине:**
```bash
# Скопируйте nginx-housler.conf на сервер
scp nginx-housler.conf root@91.229.8.221:/tmp/
```

**На сервере:**
```bash
# Переместите конфиг в Nginx
cp /tmp/nginx-housler.conf /etc/nginx/sites-available/calendar.housler.ru

# Создайте symlink
ln -s /etc/nginx/sites-available/calendar.housler.ru /etc/nginx/sites-enabled/

# Проверьте конфигурацию
nginx -t

# Если OK - перезагрузите Nginx
systemctl reload nginx
```

### 2.4. Получите SSL сертификат:
```bash
certbot --nginx -d calendar.housler.ru

# Согласитесь на все вопросы:
# - Email: ваш email
# - Terms of Service: Yes
# - Redirect HTTP to HTTPS: Yes (рекомендуется)
```

✅ **Certbot автоматически:**
- Получит SSL сертификат от Let's Encrypt
- Обновит Nginx конфигурацию
- Настроит автообновление (cron job)

### 2.5. Обновите .env файл:
```bash
cd /root/ai-calendar-assistant/ai-calendar-assistant
nano .env

# Обновите или добавьте:
WEBAPP_DOMAIN=calendar.housler.ru
WEBAPP_URL=https://calendar.housler.ru

# Сохраните: Ctrl+O, Enter, Ctrl+X
```

### 2.6. Перезапустите контейнеры:
```bash
docker-compose restart ai-calendar-assistant
docker-compose restart telegram-bot-polling
```

### 2.7. Проверьте что всё работает:
```bash
# API health check
curl -I https://calendar.housler.ru/health
# Ожидаем: HTTP/2 200

# Веб-приложение
curl -I https://calendar.housler.ru/
# Ожидаем: HTTP/2 200

# API endpoint
curl -s https://calendar.housler.ru/health
# Ожидаем: {"status":"ok","version":"0.1.0"}
```

---

## 🤖 Шаг 3: Обновите Telegram Menu Button

### 3.1. Получите токен бота:
```bash
grep TELEGRAM_BOT_TOKEN .env
```

### 3.2. Обновите Menu Button через Telegram API:

**Вариант А: Через curl на сервере:**
```bash
BOT_TOKEN="ваш_токен_из_.env"

curl -X POST "https://api.telegram.org/bot${BOT_TOKEN}/setChatMenuButton" \
  -H "Content-Type: application/json" \
  -d '{
    "menu_button": {
      "type": "web_app",
      "text": "🗓 Календарь",
      "web_app": {
        "url": "https://calendar.housler.ru"
      }
    }
  }'
```

**Вариант Б: Через BotFather:**
1. Откройте Telegram → @BotFather
2. `/mybots` → Выберите вашего бота
3. `Bot Settings` → `Menu Button`
4. `Configure menu button`
5. Введите URL: `https://calendar.housler.ru`
6. Введите текст кнопки: `🗓 Календарь`

---

## 📱 Шаг 4: Деплой веб-приложения (2 минуты)

### 4.1. Настройте SSH ключ (если ещё не настроен):

**На локальной машине:**
```bash
# Добавьте SSH ключ на сервер (введите пароль один раз)
ssh-copy-id -i ~/.ssh/calendar_deploy.pub root@91.229.8.221

# Проверьте:
ssh -i ~/.ssh/calendar_deploy root@91.229.8.221 'echo "✅ Works!"'
```

### 4.2. Запустите автодеплой:
```bash
cd ~/Desktop/AI-Calendar-Project/ai-calendar-assistant
./deploy_updates.sh
```

**Скрипт автоматически:**
- Скопирует все обновлённые файлы (включая `app/static/index.html`)
- Перезапустит контейнеры
- Проверит что всё работает

---

## ✅ Проверка результата (5 минут)

### 1. **DNS:**
```bash
dig calendar.housler.ru +short
# Должно вернуть: 91.229.8.221
```

### 2. **SSL:**
```bash
curl -I https://calendar.housler.ru/health
# Должно быть: HTTP/2 200
# Без ошибок сертификата
```

### 3. **Веб-приложение в браузере:**
Откройте: `https://calendar.housler.ru`
- ✅ Страница загружается
- ✅ Показывается **текущая дата** (не 30 октября)
- ✅ TODO задачи работают (можно создать/удалить)
- ✅ Календарь показывает события

### 4. **Telegram бот:**
1. Откройте бота в Telegram
2. Нажмите кнопку `🗓 Календарь` (внизу рядом с полем ввода)
3. Должно открыться: `https://calendar.housler.ru`
4. Попробуйте:
   - Создать событие
   - Создать TODO задачу
   - Посмотреть расписание

### 5. **Проверьте логи:**
```bash
ssh root@91.229.8.221
docker logs ai-calendar-assistant --tail 50
# Не должно быть ошибок
```

---

## 🐛 Troubleshooting

### DNS не propagates (прошло >10 минут):
```bash
# Проверьте через разные DNS серверы:
dig @8.8.8.8 calendar.housler.ru +short  # Google DNS
dig @1.1.1.1 calendar.housler.ru +short  # Cloudflare DNS

# Очистите кеш DNS на Mac:
sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder
```

### SSL сертификат не получается:
```bash
# Проверьте что порт 80 открыт:
curl -I http://calendar.housler.ru

# Проверьте Nginx слушает на 80:
netstat -tuln | grep :80

# Попробуйте вручную:
certbot certonly --nginx -d calendar.housler.ru

# Если не работает - используйте standalone:
systemctl stop nginx
certbot certonly --standalone -d calendar.housler.ru
systemctl start nginx
```

### Веб-приложение показывает 502 Bad Gateway:
```bash
# Проверьте что контейнер запущен:
docker ps | grep ai-calendar-assistant

# Проверьте что API отвечает:
curl http://localhost:8000/health

# Проверьте логи Nginx:
tail -50 /var/log/nginx/calendar.housler.ru.error.log
```

### TODO не работает в веб-апе:
```bash
# Убедитесь что app/static/index.html обновлён:
docker exec ai-calendar-assistant ls -lh /app/app/static/index.html

# Деплойте веб-апп:
./deploy_updates.sh
```

---

## ⏱️ Итого:
- **DNS:** 2 мин + 5-10 мин propagation
- **Nginx + SSL:** 10 минут
- **Telegram Menu:** 2 минуты
- **Деплой веб-апа:** 2 минуты

**Всего: ~20-30 минут**

---

## 📚 Дополнительно:

### Автообновление SSL:
Certbot автоматически настраивает cron job для обновления сертификатов.

Проверка:
```bash
systemctl status certbot.timer
certbot renew --dry-run
```

### Мониторинг:
```bash
# Логи Nginx:
tail -f /var/log/nginx/calendar.housler.ru.access.log

# Логи приложения:
docker logs -f ai-calendar-assistant
```

### Бэкапы:
```bash
# Бэкап Nginx конфига:
cp /etc/nginx/sites-available/calendar.housler.ru ~/backups/nginx-calendar-$(date +%Y%m%d).conf
```

---

**Готово!** 🎉

Теперь веб-приложение доступно по адресу: `https://calendar.housler.ru`
