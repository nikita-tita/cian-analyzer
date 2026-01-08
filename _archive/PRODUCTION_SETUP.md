# 🚀 Production Setup Guide для housler.ru

Полное руководство по развертыванию Housler на production сервере с доменом housler.ru.

---

## 📋 Содержание

1. [Требования](#требования)
2. [Быстрый старт](#быстрый-старт)
3. [GitHub Actions для auto-deploy](#github-actions)
4. [DNS и SSL](#dns-и-ssl)
5. [Мониторинг](#мониторинг)

---

## 🖥️ Требования

### Сервер (VPS)
- CPU: 2+ cores
- RAM: 4+ GB
- Disk: 20+ GB SSD
- OS: Ubuntu 20.04+ / Debian 11+

### Домен
- Домен: **housler.ru**
- Доступ к DNS управлению

---

## 🚀 Быстрый старт

### 1. Скопируйте скрипт на сервер

```bash
SERVER_IP="YOUR_SERVER_IP"
scp scripts/setup-production-server.sh root@$SERVER_IP:/tmp/
ssh root@$SERVER_IP
```

### 2. Запустите автоматическую настройку

```bash
export DOMAIN="housler.ru"
cd /tmp
chmod +x setup-production-server.sh
./setup-production-server.sh
```

Скрипт автоматически установит все необходимое.

### 3. Настройте DNS

В панели управления доменом:

```
A    housler.ru      YOUR_SERVER_IP
A    www.housler.ru  YOUR_SERVER_IP
```

### 4. Получите SSL сертификат

```bash
sudo certbot certonly --nginx -d housler.ru -d www.housler.ru
sudo systemctl restart nginx
```

### 5. Деплой

```bash
cd /opt/housler
sudo -u housler bash scripts/deploy-production.sh main
sudo systemctl start housler
```

### 6. Проверка

https://housler.ru/health

---

## 🤖 GitHub Actions

### Настройка SSH для auto-deploy

1. Создайте SSH ключ:

```bash
ssh-keygen -t ed25519 -C "github-actions" -f ~/.ssh/housler_deploy
ssh-copy-id -i ~/.ssh/housler_deploy.pub housler@housler.ru
```

2. Добавьте в GitHub Secrets (Settings → Secrets):

```
SSH_HOST        = housler.ru
SSH_USERNAME    = housler  
SSH_PRIVATE_KEY = [содержимое ~/.ssh/housler_deploy]
SSH_PORT        = 22
```

3. Автоматический деплой при push в main:

```bash
git push origin main
```

GitHub Actions автоматически задеплоит на production!

---

## 🌐 DNS и SSL

### Проверка DNS

```bash
dig housler.ru +short
```

### Автообновление SSL

Certbot автоматически обновляет сертификаты.

Проверка:
```bash
sudo certbot renew --dry-run
```

---

## 📊 Мониторинг

### Health Check

```bash
curl https://housler.ru/health
```

### Логи

```bash
# Application
sudo docker compose -f /opt/housler/docker-compose.yml logs -f app

# Nginx
sudo tail -f /var/log/nginx/housler_error.log

# System
sudo journalctl -u housler -f
```

### Backup

Автоматический backup каждый день в 3:00 AM

```bash
/opt/backups/housler/backup.sh
```

---

## 🔧 Полезные команды

```bash
# Статус
sudo systemctl status housler

# Перезапуск
sudo systemctl restart housler

# Обновление
cd /opt/housler
sudo -u housler bash scripts/deploy-production.sh main

# Логи
sudo docker compose logs -f
```

---

## ✅ Checklist

- [ ] Сервер настроен (setup-production-server.sh)
- [ ] DNS настроен
- [ ] SSL сертификат получен
- [ ] Приложение задеплоено
- [ ] Health check работает (https://housler.ru/health)
- [ ] GitHub Actions настроен
- [ ] Backup работает

---

**Production ready! 🚀**

Приложение доступно на **https://housler.ru**
