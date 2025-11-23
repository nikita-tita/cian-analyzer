#!/bin/bash
#
# Автоматический парсинг статей из CIAN Magazine
# Запускается через cron для регулярного обновления блога
#

set -e

# Переходим в рабочую директорию
cd /var/www/housler

# Активируем виртуальное окружение
source venv/bin/activate

# Логируем начало
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting blog auto-parse..."

# Запускаем парсер (добавляем до 3 новых статей)
python3 blog_cli.py parse -n 3 2>&1 | while IFS= read -r line; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $line"
done

# Проверяем количество статей в базе
TOTAL_POSTS=$(python3 -c "from blog_database import BlogDatabase; db = BlogDatabase(); print(len(db.get_all_posts()))")
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Total posts in database: $TOTAL_POSTS"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Blog auto-parse completed"
