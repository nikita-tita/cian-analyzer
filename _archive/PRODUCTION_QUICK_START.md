# ⚡ Production Quick Start - housler.ru

Быстрый старт для деплоя на production сервер.

---

## 🚀 Шаг 1: Настройка сервера (один раз)

```bash
# На локальном компьютере
SERVER_IP="YOUR_SERVER_IP"  # Замените на реальный IP

# Копируем скрипт
scp scripts/setup-production-server.sh root@$SERVER_IP:/tmp/

# Подключаемся и запускаем
ssh root@$SERVER_IP
cd /tmp && chmod +x setup-production-server.sh
export DOMAIN="housler.ru"
./setup-production-server.sh
```

Скрипт автоматически установит Docker, Nginx, настроит firewall и создаст все нужные конфигурации.

---

## 🌐 Шаг 2: DNS

В панели управления доменом создайте A-записи:

```
housler.ru     → YOUR_SERVER_IP
www.housler.ru → YOUR_SERVER_IP
```

Проверка: `dig housler.ru +short`

---

## 🔒 Шаг 3: SSL сертификат

```bash
# На сервере
sudo certbot certonly --nginx -d housler.ru -d www.housler.ru
sudo systemctl restart nginx
```

---

## 📦 Шаг 4: Первый деплой

```bash
# На сервере
cd /opt/housler
sudo -u housler bash scripts/deploy-production.sh main
sudo systemctl start housler
```

---

## 🤖 Шаг 5: GitHub Actions (автодеплой)

### Создайте SSH ключ:

```bash
# На локальном компьютере
ssh-keygen -t ed25519 -f ~/.ssh/housler_deploy
ssh-copy-id -i ~/.ssh/housler_deploy.pub housler@housler.ru
```

### Добавьте в GitHub Secrets:

```
Settings → Secrets and variables → Actions → New secret
```

Секреты:
- `SSH_HOST` = `housler.ru`
- `SSH_USERNAME` = `housler`
- `SSH_PRIVATE_KEY` = содержимое `~/.ssh/housler_deploy`
- `SSH_PORT` = `22`

### Теперь автодеплой при push:

```bash
git push origin main  # Автоматический деплой!
```

---

## ✅ Проверка

Откройте в браузере:
- https://housler.ru
- https://housler.ru/health

Должен вернуть `{"status":"healthy"}`

---

## 🔧 Полезные команды

```bash
# Статус
sudo systemctl status housler

# Перезапуск
sudo systemctl restart housler

# Логи
sudo docker compose -f /opt/housler/docker-compose.yml logs -f app

# Ручной деплой
cd /opt/housler
sudo -u housler bash scripts/deploy-production.sh main
```

---

## 📚 Полная документация

[PRODUCTION_SETUP.md](PRODUCTION_SETUP.md) - Детальное руководство по production

---

**Production ready за 5 шагов! 🚀**
