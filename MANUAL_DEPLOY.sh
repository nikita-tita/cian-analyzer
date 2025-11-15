#!/bin/bash
# Ручной деплой на housler.ru
# Запустить: bash MANUAL_DEPLOY.sh

set -e

echo "🚀 РУЧНОЙ ДЕПЛОЙ НА HOUSLER.RU"
echo "================================"
echo ""

# Проверка SSH ключа
if [ ! -f ~/.ssh/id_ed25519 ] && [ ! -f ~/.ssh/id_rsa ]; then
    echo "❌ SSH ключ не найден!"
    echo ""
    echo "Создай SSH ключ:"
    echo "  ssh-keygen -t ed25519 -C \"deploy-housler\""
    echo ""
    echo "Добавь публичный ключ на сервер:"
    echo "  ssh-copy-id root@91.229.8.221"
    echo ""
    exit 1
fi

echo "📡 Подключение к серверу..."
echo ""

ssh root@91.229.8.221 << 'ENDSSH'
set -e

echo "📂 Переход в директорию проекта..."
cd /var/www/housler || cd ~/housler || { echo "❌ Директория не найдена"; exit 1; }

echo ""
echo "📥 Получение последних изменений..."
git fetch origin
git checkout main
git pull origin main

echo ""
echo "📋 Текущий коммит:"
git log -1 --oneline --color=always

echo ""
echo "📦 Проверка зависимостей..."
if git diff HEAD~1 HEAD --name-only | grep -q "requirements.txt"; then
    echo "Обнаружены изменения в requirements.txt, обновляем..."
    source venv/bin/activate || { echo "❌ venv не найден"; exit 1; }
    pip install -r requirements.txt
else
    echo "Зависимости не изменились"
fi

echo ""
echo "🔄 Перезапуск сервиса..."
systemctl restart housler

echo ""
echo "⏳ Ожидание запуска (5 сек)..."
sleep 5

echo ""
echo "🔍 Проверка статуса..."
if systemctl is-active --quiet housler; then
    echo "✅ Сервис запущен успешно!"
else
    echo "❌ Ошибка запуска сервиса!"
    systemctl status housler --no-pager -l
    exit 1
fi

echo ""
echo "📋 Последние 15 строк логов:"
journalctl -u housler -n 15 --no-pager

echo ""
echo "✅ ДЕПЛОЙ ЗАВЕРШЕН!"
ENDSSH

echo ""
echo "================================"
echo "✅ УСПЕШНО ЗАДЕПЛОЕНО НА HOUSLER.RU"
echo "================================"
echo ""
echo "🌐 Проверь сайт: https://housler.ru"
echo ""
echo "📋 Проверь калькулятор:"
echo "  1. Шаг 1: Парсинг объекта"
echo "  2. Шаг 2: Поиск аналогов (должны найтись!)"
echo "  3. Шаг 3: Анализ (должен работать!)"
echo ""
