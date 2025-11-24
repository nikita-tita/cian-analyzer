#!/bin/bash
# Скрипт для деплоя на production сервер housler.ru
# Выполнить на production сервере!

set -e  # Остановка при ошибке

echo "═══════════════════════════════════════════════════════════════════"
echo "🚀 ДЕПЛОЙ НА PRODUCTION: housler.ru"
echo "═══════════════════════════════════════════════════════════════════"
echo ""
echo "Версия: faf15c7"
echo "Дата: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Проверка что мы на production сервере
echo "📍 Проверка окружения..."
if [ ! -f "/etc/systemd/system/housler.service" ] && [ ! -f "/etc/systemd/system/cian-analyzer.service" ]; then
    echo -e "${YELLOW}⚠️  Внимание: Системный сервис не найден${NC}"
    echo "   Убедитесь что вы на production сервере"
    read -p "   Продолжить? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${RED}❌ Деплой отменен${NC}"
        exit 1
    fi
fi

# 2. Определение рабочей директории
WORK_DIR="/var/www/housler"
if [ ! -d "$WORK_DIR" ]; then
    WORK_DIR="/root/cian-analyzer"
fi
if [ ! -d "$WORK_DIR" ]; then
    WORK_DIR="$(pwd)"
fi

echo "   Рабочая директория: $WORK_DIR"
cd "$WORK_DIR" || exit 1

# 3. Бэкап базы данных
echo ""
echo "💾 Создание бэкапа БД..."
BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="$WORK_DIR/backups"
mkdir -p "$BACKUP_DIR"

if [ -f "sessions.db" ]; then
    sqlite3 sessions.db ".backup $BACKUP_DIR/sessions_backup_$BACKUP_DATE.db"
    echo -e "${GREEN}✅ Бэкап создан: $BACKUP_DIR/sessions_backup_$BACKUP_DATE.db${NC}"
else
    echo -e "${YELLOW}⚠️  sessions.db не найден, пропускаем бэкап${NC}"
fi

# 4. Проверка текущей ветки
echo ""
echo "📌 Проверка git репозитория..."
CURRENT_BRANCH=$(git branch --show-current)
echo "   Текущая ветка: $CURRENT_BRANCH"

# 5. Подтягивание изменений
echo ""
echo "⬇️  Подтягивание изменений из main..."
git fetch origin main
git status

# Проверка на локальные изменения
if ! git diff-index --quiet HEAD --; then
    echo -e "${YELLOW}⚠️  Обнаружены локальные изменения!${NC}"
    git status --short
    read -p "   Stash локальные изменения? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git stash save "Pre-deploy stash $BACKUP_DATE"
        echo -e "${GREEN}✅ Изменения сохранены в stash${NC}"
    else
        echo -e "${RED}❌ Деплой отменен - сохраните или отмените локальные изменения${NC}"
        exit 1
    fi
fi

# 6. Переключение на main и pull
if [ "$CURRENT_BRANCH" != "main" ]; then
    echo "   Переключение на main..."
    git checkout main
fi

echo "   Обновление до последней версии..."
git pull origin main

# Проверка что у нас нужный коммит
CURRENT_COMMIT=$(git rev-parse --short HEAD)
echo ""
echo "📋 Текущий коммит: $CURRENT_COMMIT"
git log -1 --pretty=format:"%h - %s (%ar)" HEAD
echo ""

# 7. Обновление зависимостей
echo ""
echo "📦 Проверка зависимостей..."
if [ -f "requirements.txt" ]; then
    if [ -d "venv" ]; then
        echo "   Активация виртуального окружения..."
        source venv/bin/activate
        echo "   Обновление pip..."
        pip install --upgrade pip -q
        echo "   Установка зависимостей..."
        pip install -r requirements.txt -q
        echo -e "${GREEN}✅ Зависимости обновлены${NC}"
    else
        echo -e "${YELLOW}⚠️  venv не найден, пропускаем обновление зависимостей${NC}"
    fi
fi

# 8. Проверка конфигурации
echo ""
echo "🔧 Проверка конфигурации..."
if [ -f ".env" ]; then
    echo -e "${GREEN}✅ .env файл найден${NC}"
else
    echo -e "${RED}❌ .env файл не найден!${NC}"
    read -p "   Продолжить без .env? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 9. Рестарт приложения
echo ""
echo "🔄 Рестарт приложения..."

# Пробуем разные способы рестарта
if systemctl is-active --quiet housler; then
    echo "   Останавливаем сервис housler..."
    sudo systemctl stop housler
    sleep 2
    echo "   Запускаем сервис housler..."
    sudo systemctl start housler
    sleep 3
    if systemctl is-active --quiet housler; then
        echo -e "${GREEN}✅ Сервис housler перезапущен${NC}"
    else
        echo -e "${RED}❌ Не удалось запустить housler${NC}"
        sudo systemctl status housler
        exit 1
    fi
elif systemctl is-active --quiet cian-analyzer; then
    echo "   Останавливаем сервис cian-analyzer..."
    sudo systemctl stop cian-analyzer
    sleep 2
    echo "   Запускаем сервис cian-analyzer..."
    sudo systemctl start cian-analyzer
    sleep 3
    if systemctl is-active --quiet cian-analyzer; then
        echo -e "${GREEN}✅ Сервис cian-analyzer перезапущен${NC}"
    else
        echo -e "${RED}❌ Не удалось запустить cian-analyzer${NC}"
        sudo systemctl status cian-analyzer
        exit 1
    fi
elif [ -f "app_new.py" ]; then
    echo "   Останавливаем процесс app_new.py..."
    pkill -f "python.*app_new.py" || true
    sleep 2
    echo "   Запускаем app_new.py..."
    nohup python app_new.py > logs/app.log 2>&1 &
    sleep 3
    if pgrep -f "python.*app_new.py" > /dev/null; then
        echo -e "${GREEN}✅ app_new.py запущен${NC}"
    else
        echo -e "${RED}❌ Не удалось запустить app_new.py${NC}"
        tail -20 logs/app.log
        exit 1
    fi
else
    echo -e "${RED}❌ Не удалось определить способ запуска приложения${NC}"
    exit 1
fi

# 10. Проверка здоровья
echo ""
echo "🏥 Проверка здоровья приложения..."
sleep 5  # Даем время на запуск

for i in {1..10}; do
    HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5002/health || echo "000")
    if [ "$HTTP_STATUS" = "200" ]; then
        echo -e "${GREEN}✅ Приложение отвечает (HTTP $HTTP_STATUS)${NC}"
        break
    else
        if [ $i -eq 10 ]; then
            echo -e "${RED}❌ Приложение не отвечает после 10 попыток (HTTP $HTTP_STATUS)${NC}"
            echo "   Проверьте логи:"
            echo "   sudo journalctl -u housler -n 50"
            echo "   # или"
            echo "   tail -50 logs/app.log"
            exit 1
        fi
        echo "   Попытка $i/10: HTTP $HTTP_STATUS, ждем..."
        sleep 2
    fi
done

# 11. Проверка через домен
echo ""
echo "🌐 Проверка через домен..."
DOMAIN_STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://housler.ru/health --max-time 10 || echo "000")
if [ "$DOMAIN_STATUS" = "200" ]; then
    echo -e "${GREEN}✅ Сайт доступен через https://housler.ru (HTTP $DOMAIN_STATUS)${NC}"
else
    echo -e "${YELLOW}⚠️  Домен не отвечает (HTTP $DOMAIN_STATUS), но локально работает${NC}"
fi

# 12. Итоги
echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo -e "${GREEN}✅ ДЕПЛОЙ ЗАВЕРШЕН УСПЕШНО!${NC}"
echo "═══════════════════════════════════════════════════════════════════"
echo ""
echo "📋 Информация о деплое:"
echo "   Коммит: $CURRENT_COMMIT"
echo "   Время: $(date '+%Y-%m-%d %H:%M:%S')"
echo "   Бэкап БД: $BACKUP_DIR/sessions_backup_$BACKUP_DATE.db"
echo ""
echo "🔍 Проверьте:"
echo "   1. Логи: sudo journalctl -u housler -f"
echo "            # или: tail -f logs/app.log"
echo ""
echo "   2. Тест парсинга:"
echo "      curl -X POST https://housler.ru/api/parse \\"
echo "           -H 'Content-Type: application/json' \\"
echo "           -H 'X-CSRF-Token: YOUR_TOKEN' \\"
echo "           -d '{\"url\":\"https://www.cian.ru/sale/flat/VALID_ID/\"}'"
echo ""
echo "   3. Метрики: https://metrika.yandex.ru"
echo ""
echo "💡 Откат (если нужно):"
echo "   git revert HEAD"
echo "   sudo systemctl restart housler"
echo ""
echo "═══════════════════════════════════════════════════════════════════"
