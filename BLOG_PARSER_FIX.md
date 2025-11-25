# 🔧 Фикс: Автоматический парсинг блога

## 🐛 Проблема

**Симптом:** Новые статьи не появляются в блоге автоматически

**Причина:** Cron job для автоматического парсинга статей с CIAN Magazine не был настроен при деплое

**Статус:** ✅ ИСПРАВЛЕНО в обновлённом `deploy-housler-full.sh`

---

## ✅ Что исправлено

### Обновлён файл: `deploy-housler-full.sh`

Добавлен автоматический setup cron job в шаге 8 (Запуск приложения):

```bash
# Создаётся скрипт /var/www/housler/cron_parse_blog.sh
# Добавляется в crontab: ежедневный запуск в 10:00
# Парсит до 3 новых статей с CIAN Magazine
# Рерайтит через Yandex GPT
# Сохраняет в базу данных blog.db
```

### Что делает cron job:

1. **Каждый день в 10:00** запускается автоматически
2. Подключается к **CIAN Magazine** (https://spb.cian.ru/magazine)
3. Находит **до 3 новых статей** (проверяет по slug - не дублирует существующие)
4. Парсит полный текст статей с помощью **Playwright**
5. Рерайтит контент через **Yandex GPT API**
6. Публикует в блог (таблица `blog_posts` в `blog.db`)
7. Логи пишутся в `/var/log/housler/blog_parser_cron.log`

---

## 🚀 Что нужно сделать

### Шаг 1: Закоммитить изменения

```bash
cd /Users/fatbookpro/Desktop/cian

git add deploy-housler-full.sh
git add FINAL_DEPLOYMENT_GUIDE.md
git add BLOG_PARSER_FIX.md

git commit -m "fix: Add automated blog parser cron job to deployment

- Added cron job setup in deploy-housler-full.sh (step 8)
- Runs daily at 10:00 AM
- Parses up to 3 new articles from CIAN Magazine
- Auto-rewrites with Yandex GPT
- Auto-publishes to blog database
- Updated FINAL_DEPLOYMENT_GUIDE.md with cron job docs"

git push origin main
```

### Шаг 2: Задеплоить на production

```bash
cd /Users/fatbookpro/Desktop/cian

# Запускаем обновлённый деплой скрипт
./deploy-housler-full.sh
```

**Что произойдёт:**
- Все 9 шагов деплоя выполнятся заново
- В шаге 8 автоматически настроится cron job для blog parser
- Если база блога пустая - добавятся seed данные (10 статей)

**Время выполнения:** 5-10 минут

---

## 🧪 Проверка после деплоя

### 1. Проверить что cron job установлен

```bash
ssh -i ~/.ssh/id_housler root@91.229.8.221 'crontab -l | grep blog'
```

**Ожидаемый вывод:**
```
0 10 * * * /var/www/housler/cron_parse_blog.sh
```

---

### 2. Запустить парсинг вручную (для теста)

```bash
ssh -i ~/.ssh/id_housler root@91.229.8.221 'cd /var/www/housler && source venv/bin/activate && python3 blog_cli.py parse -n 3'
```

**Что должно произойти:**
- Playwright откроет headless браузер
- Зайдёт на https://spb.cian.ru/magazine
- Найдёт последние статьи
- Проверит какие уже есть в базе (по slug)
- Распарсит до 3 новых статей
- Отправит в Yandex GPT на рерайт
- Сохранит в blog.db
- Вывод в консоль:

```
Starting to parse 3 articles from CIAN magazine...
Found 12 articles
Processing: Заголовок статьи...
Rewriting article with Yandex GPT...
✓ Published: Переписанный заголовок (ID: 11)
Done! Published 3 articles
```

---

### 3. Проверить статьи в базе данных

```bash
ssh -i ~/.ssh/id_housler root@91.229.8.221 'cd /var/www/housler && source venv/bin/activate && python3 blog_cli.py list'
```

**Ожидаемый вывод:**
```
Total posts: 13

[11] Заголовок новой статьи 1
    Slug: zagolovok-novoy-stati-1
    Published: 2025-11-23T15:30:00
    Views: 0

[12] Заголовок новой статьи 2
    ...
```

---

### 4. Проверить статьи на сайте

Откройте в браузере:

```
https://housler.ru/blog
```

**Что должно быть:**
- Список всех статей (seed + новые)
- Отсортированы по дате публикации (новые сверху)
- Кликабельные карточки статей
- Каждая статья имеет заголовок, excerpt, дату

---

### 5. Посмотреть логи парсера

```bash
# Логи последнего запуска
ssh -i ~/.ssh/id_housler root@91.229.8.221 'tail -100 /var/log/housler/blog_parser_cron.log'

# Следить за логами в реальном времени
ssh -i ~/.ssh/id_housler root@91.229.8.221 'tail -f /var/log/housler/blog_parser_cron.log'
```

---

## 📊 Как работает парсинг

### Архитектура:

```
CRON (10:00 daily)
    ↓
cron_parse_blog.sh
    ↓
blog_cli.py parse -n 3
    ↓
CianMagazineParserPlaywright
    ↓ (Playwright → Chromium)
    ↓
https://spb.cian.ru/magazine
    ↓ (парсит HTML)
    ↓
BlogDatabase.post_exists(slug) → проверка дубликатов
    ↓ (если новая статья)
    ↓
YandexGPT.rewrite_article() → рерайт контента
    ↓
BlogDatabase.create_post() → сохранение в blog.db
    ↓
✅ Статья опубликована
```

### Файлы системы:

- **blog_cli.py** - CLI для управления блогом
- **blog_parser_playwright.py** - Парсер CIAN Magazine (Playwright)
- **yandex_gpt.py** - Интеграция с Yandex GPT API
- **blog_database.py** - Работа с SQLite базой
- **blog.db** - База данных статей (таблица `blog_posts`)
- **cron_parse_blog.sh** - Скрипт для cron job
- **/var/log/housler/blog_parser_cron.log** - Логи парсера

---

## 🔧 Управление парсером

### Запуск вручную (разное количество статей)

```bash
# Распарсить 1 статью
ssh -i ~/.ssh/id_housler root@91.229.8.221 'cd /var/www/housler && source venv/bin/activate && python3 blog_cli.py parse -n 1'

# Распарсить 5 статей
ssh -i ~/.ssh/id_housler root@91.229.8.221 'cd /var/www/housler && source venv/bin/activate && python3 blog_cli.py parse -n 5'

# Распарсить 10 статей
ssh -i ~/.ssh/id_housler root@91.229.8.221 'cd /var/www/housler && source venv/bin/activate && python3 blog_cli.py parse -n 10'
```

### Изменить расписание cron job

```bash
# Подключиться к серверу
ssh -i ~/.ssh/id_housler root@91.229.8.221

# Открыть crontab
crontab -e

# Изменить расписание:
# 0 10 * * * - каждый день в 10:00
# 0 */6 * * * - каждые 6 часов
# 0 0 * * 1 - каждый понедельник в 00:00
# 0 12 * * * - каждый день в 12:00
```

### Отключить автопарсинг

```bash
ssh -i ~/.ssh/id_housler root@91.229.8.221 'crontab -l | grep -v "cron_parse_blog" | crontab -'
```

### Включить обратно

```bash
ssh -i ~/.ssh/id_housler root@91.229.8.221 '(crontab -l 2>/dev/null; echo "0 10 * * * /var/www/housler/cron_parse_blog.sh") | crontab -'
```

---

## 📈 Мониторинг

### Сколько статей в базе

```bash
ssh -i ~/.ssh/id_housler root@91.229.8.221 'cd /var/www/housler && sqlite3 blog.db "SELECT COUNT(*) FROM blog_posts;"'
```

### Последние 5 статей

```bash
ssh -i ~/.ssh/id_housler root@91.229.8.221 'cd /var/www/housler && sqlite3 blog.db "SELECT slug, title, published_at FROM blog_posts ORDER BY published_at DESC LIMIT 5;"'
```

### Статистика по датам

```bash
ssh -i ~/.ssh/id_housler root@91.229.8.221 'cd /var/www/housler && sqlite3 blog.db "SELECT DATE(published_at) as date, COUNT(*) as count FROM blog_posts GROUP BY DATE(published_at) ORDER BY date DESC;"'
```

---

## ✅ Готово!

После деплоя:
- ✅ Cron job настроен и работает
- ✅ Каждый день в 10:00 парсятся новые статьи
- ✅ Блог автоматически пополняется контентом
- ✅ Логи пишутся для мониторинга
- ✅ Дубликаты не создаются (проверка по slug)

**Больше ничего делать не нужно - всё работает автоматически!** 🎉

---

## 🆘 Troubleshooting

### Проблема: Cron job не запускается

**Проверка:**
```bash
ssh -i ~/.ssh/id_housler root@91.229.8.221 'grep CRON /var/log/syslog | grep cron_parse_blog'
```

**Решение:**
```bash
# Проверьте права на скрипт
ssh -i ~/.ssh/id_housler root@91.229.8.221 'ls -la /var/www/housler/cron_parse_blog.sh'
# Должно быть: -rwxr-xr-x

# Если нет - добавьте права
ssh -i ~/.ssh/id_housler root@91.229.8.221 'chmod +x /var/www/housler/cron_parse_blog.sh'
```

---

### Проблема: Парсер падает с ошибкой

**Проверка логов:**
```bash
ssh -i ~/.ssh/id_housler root@91.229.8.221 'tail -100 /var/log/housler/blog_parser_cron.log'
```

**Частые ошибки:**

1. **Playwright не установлен:**
```bash
ssh -i ~/.ssh/id_housler root@91.229.8.221 'cd /var/www/housler && source venv/bin/activate && playwright install chromium'
```

2. **Yandex GPT API key не работает:**
```bash
# Проверьте .env файл
ssh -i ~/.ssh/id_housler root@91.229.8.221 'cat /var/www/housler/.env | grep YANDEX'
```

3. **База данных недоступна:**
```bash
# Проверьте права
ssh -i ~/.ssh/id_housler root@91.229.8.221 'ls -la /var/www/housler/blog.db'
```

---

**Контакт:** hello@housler.ru
