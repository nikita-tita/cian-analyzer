#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Автоматический деплой обновлений Housler на VPS
# ═══════════════════════════════════════════════════════════════

set -e

SERVER="91.229.8.221"
APP_DIR="/var/www/housler"
DEPLOY_USER="root"
SSH_KEY="$HOME/.ssh/id_housler"

echo "🚀 Деплой обновлений Housler на $SERVER"
echo "════════════════════════════════════════════════════════════"

# Проверка доступности сервера
echo "📡 Проверка доступности сервера..."
if ! ssh -i "$SSH_KEY" -o ConnectTimeout=10 "$DEPLOY_USER@$SERVER" "echo 'OK'" &>/dev/null; then
    echo "❌ Сервер недоступен!"
    echo "   Проверьте:"
    echo "   - Интернет соединение"
    echo "   - Доступность VPS в панели Reg.ru"
    echo "   - SSH подключение"
    exit 1
fi

echo "✅ Сервер доступен"
echo ""

# Обновление кода
echo "📥 Обновление кода из GitHub (main)..."
ssh -i "$SSH_KEY" "$DEPLOY_USER@$SERVER" << 'ENDSSH'
cd /var/www/housler

# Резервная копия текущего кода
echo "   📦 Создание резервной копии..."
BACKUP_DIR="/var/www/housler_backup_$(date +%Y%m%d_%H%M%S)"
cp -r /var/www/housler "$BACKUP_DIR"
echo "   ✅ Backup: $BACKUP_DIR"

# Git pull
echo "   🔄 Git pull origin main..."
git fetch origin
git reset --hard origin/main
git pull origin main

# Применяем критический фикс для flask-limiter
echo "   🔧 Применение фикса storage_uri..."
sed -i 's/limiter\.storage_uri/limiter._storage_uri/g' app_new.py

echo "   ✅ Код обновлён"
ENDSSH

echo ""

# Проверка requirements.txt
echo "📦 Обновление зависимостей..."
ssh -i "$SSH_KEY" "$DEPLOY_USER@$SERVER" << 'ENDSSH'
cd /var/www/housler
source venv/bin/activate

# Обновляем зависимости
if [ -f requirements.txt ]; then
    echo "   📥 Installing dependencies from requirements.txt..."
    pip install -r requirements.txt --quiet
else
    echo "   ⚠️  requirements.txt не найден, пропускаем"
fi

# Проверка критичных модулей
echo "   🔍 Проверка критичных модулей..."
python -c "import flask, playwright, bs4, redis" 2>/dev/null && echo "   ✅ Все модули на месте" || echo "   ⚠️  Некоторые модули отсутствуют"

deactivate
ENDSSH

echo ""

# Перезапуск сервиса
echo "🔄 Перезапуск Housler service..."
ssh -i "$SSH_KEY" "$DEPLOY_USER@$SERVER" << 'ENDSSH'
# Останавливаем
echo "   🛑 Остановка сервиса..."
systemctl stop housler

# Запускаем
echo "   ▶️  Запуск сервиса..."
systemctl start housler

# Ждём запуска
sleep 5

# Проверяем статус
if systemctl is-active --quiet housler; then
    echo "   ✅ Сервис запущен"
    systemctl status housler --no-pager | head -10
else
    echo "   ❌ Ошибка запуска!"
    systemctl status housler --no-pager
    journalctl -u housler -n 30 --no-pager
    exit 1
fi
ENDSSH

echo ""

# Проверка Nginx
echo "🌐 Проверка Nginx..."
ssh -i "$SSH_KEY" "$DEPLOY_USER@$SERVER" << 'ENDSSH'
if systemctl is-active --quiet nginx; then
    echo "   ✅ Nginx работает"
    nginx -t 2>&1 | grep -q "successful" && echo "   ✅ Конфигурация валидна" || echo "   ⚠️  Проверьте конфигурацию"
else
    echo "   ⚠️  Nginx не запущен, запускаю..."
    systemctl start nginx
fi
ENDSSH

echo ""

# Финальная проверка
echo "🔍 Финальная проверка доступности..."

# Проверка HTTP
echo "   📡 Проверка http://91.229.8.221..."
if curl -s -o /dev/null -w "%{http_code}" "http://91.229.8.221" --max-time 10 | grep -q "200\|301\|302"; then
    echo "   ✅ HTTP доступен"
else
    echo "   ⚠️  HTTP может быть недоступен"
fi

# Проверка HTTPS
echo "   📡 Проверка https://housler.ru..."
if curl -s -o /dev/null -w "%{http_code}" "https://housler.ru" --max-time 10 | grep -q "200\|301\|302"; then
    echo "   ✅ HTTPS доступен"
else
    echo "   ⚠️  HTTPS может быть недоступен"
fi

echo ""
echo "════════════════════════════════════════════════════════════"
echo "✅ ДЕПЛОЙ ЗАВЕРШЁН!"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "🌐 Сайт доступен:"
echo "   • https://housler.ru"
echo "   • http://91.229.8.221:8001"
echo ""
echo "📊 Проверьте работу:"
echo "   • Главная страница"
echo "   • Mobile swipe на лендинге"
echo "   • Manual input mode"
echo "   • Парсинг URL"
echo ""
echo "📝 Логи:"
echo "   journalctl -u housler -f"
echo ""
