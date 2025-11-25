# 📰 Добавление дополнительных источников новостей

## 🎯 Зачем это нужно

Если **CIAN Magazine** не даёт достаточно новых статей (10 в день), можно подключить дополнительные источники.

---

## ✅ Уже встроенные источники

### 1️⃣ CIAN Magazine (основной)

**URL:** https://spb.cian.ru/magazine

**Статус:** ✅ Работает

**Использование:**
```bash
# Автоматически (cron job)
python3 blog_cli.py parse -n 10

# Или явно через daemon
python3 auto_blog_daemon.py --source cian
```

**Количество статей:**
- ~2-5 новых статей в неделю
- Категории: покупка, продажа, ипотека, инвестиции

---

### 2️⃣ RBC Realty (альтернативный)

**URL:** https://realty.rbc.ru/

**Статус:** ✅ Уже встроен в код

**Файл парсера:** [rbc_realty_parser.py](rbc_realty_parser.py)

**Использование:**
```bash
# Ручной запуск с RBC Realty
ssh -i ~/.ssh/id_housler root@91.229.8.221 'cd /var/www/housler && source venv/bin/activate && python3 auto_blog_daemon.py --source rbc'
```

**Количество статей:**
- ~5-10 новых статей в неделю
- Категории: аналитика, рынок недвижимости, новости

---

## 🔧 Настройка нескольких источников

### Вариант 1: Два cron job (CIAN + RBC)

Добавить второй cron job для RBC:

```bash
# Подключиться к серверу
ssh -i ~/.ssh/id_housler root@91.229.8.221

# Создать скрипт для RBC
cat > /var/www/housler/cron_parse_blog_rbc.sh << 'EOF'
#!/bin/bash
cd /var/www/housler
source venv/bin/activate
python3 auto_blog_daemon.py --source rbc >> /var/log/housler/blog_parser_rbc.log 2>&1
EOF

chmod +x /var/www/housler/cron_parse_blog_rbc.sh

# Добавить в crontab (каждый день в 14:00)
(crontab -l 2>/dev/null; echo "0 14 * * * /var/www/housler/cron_parse_blog_rbc.sh") | crontab -
```

**Результат:**
- **10:00** - парсит 10 статей с CIAN
- **14:00** - парсит статьи с RBC Realty

---

### Вариант 2: Комбинированный скрипт

Парсить оба источника в одном запуске:

```bash
# Создать комбинированный скрипт
cat > /var/www/housler/cron_parse_all_sources.sh << 'EOF'
#!/bin/bash
cd /var/www/housler
source venv/bin/activate

echo "=== Парсинг CIAN Magazine ==="
python3 blog_cli.py parse -n 10

echo "=== Парсинг RBC Realty ==="
python3 auto_blog_daemon.py --source rbc

echo "=== Готово ==="
EOF

chmod +x /var/www/housler/cron_parse_all_sources.sh

# Заменить в crontab
crontab -l | grep -v "cron_parse_blog.sh" | crontab -
(crontab -l 2>/dev/null; echo "0 10 * * * /var/www/housler/cron_parse_all_sources.sh") | crontab -
```

---

## 🆕 Добавление новых источников

### Список потенциальных источников:

| Источник | URL | Тип контента |
|----------|-----|--------------|
| **Циан Журнал** | https://journal.cian.ru/ | Статьи о недвижимости |
| **Лента.ру Недвижимость** | https://lenta.ru/rubrics/realty/ | Новости рынка |
| **Коммерсант Недвижимость** | https://www.kommersant.ru/realty | Аналитика и новости |
| **Forbes Недвижимость** | https://www.forbes.ru/forbeslife/nedvizhimost | Премиум контент |
| **ДомКлик Блог** | https://domclick.ru/blog | Советы покупателям |

---

### Как добавить новый источник:

#### Шаг 1: Создать парсер

Создайте файл `parser_SOURCE.py` по аналогии с [blog_parser_playwright.py](blog_parser_playwright.py):

```python
# parser_lenta.py
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from typing import List, Dict, Optional

class LentaRealtyParser:
    def __init__(self, headless: bool = True):
        self.base_url = "https://lenta.ru"
        self.realty_url = f"{self.base_url}/rubrics/realty/"
        self.headless = headless

    def get_recent_articles(self, limit: int = 10) -> List[Dict]:
        """Парсит последние статьи с Lenta.ru Недвижимость"""
        articles = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            page = browser.new_page()
            page.goto(self.realty_url, wait_until='domcontentloaded')

            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')

            # Ваша логика парсинга...
            # Найти заголовки, ссылки, даты

            browser.close()

        return articles

    def parse_article_content(self, url: str) -> Optional[Dict]:
        """Парсит полный текст статьи"""
        # Ваша логика парсинга полной статьи
        pass

    def create_slug(self, title: str) -> str:
        """Создаёт URL-friendly slug"""
        # Копировать из blog_parser_playwright.py
        pass
```

#### Шаг 2: Обновить auto_blog_daemon.py

Добавьте новый источник в daemon:

```python
# auto_blog_daemon.py
def main(source: str = 'cian'):
    # ... existing code ...

    if source.lower() == 'rbc':
        parser = RBCRealtyParser(headless=True)
        source_name = "RBC Realty"
    elif source.lower() == 'lenta':  # ← НОВОЕ
        from parser_lenta import LentaRealtyParser
        parser = LentaRealtyParser(headless=True)
        source_name = "Lenta.ru Realty"
    else:
        parser = CianMagazineParserPlaywright(headless=True)
        source_name = "CIAN Magazine"

    # ... rest of code ...
```

#### Шаг 3: Добавить в CLI

```bash
# Теперь можно запускать
python3 auto_blog_daemon.py --source lenta
```

---

## 🔄 Ротация источников

### Стратегия 1: По дням недели

```bash
# Понедельник, среда, пятница - CIAN
0 10 * * 1,3,5 /var/www/housler/cron_parse_blog.sh

# Вторник, четверг - RBC
0 10 * * 2,4 /var/www/housler/cron_parse_blog_rbc.sh

# Суббота - оба источника
0 10 * * 6 /var/www/housler/cron_parse_all_sources.sh
```

### Стратегия 2: Чередование в одном скрипте

```bash
#!/bin/bash
# cron_parse_rotating.sh

DAY_OF_WEEK=$(date +%u)  # 1=Mon, 7=Sun

if [ $DAY_OF_WEEK -le 3 ]; then
    # Пн-Ср: CIAN
    python3 blog_cli.py parse -n 10
elif [ $DAY_OF_WEEK -le 5 ]; then
    # Чт-Пт: RBC
    python3 auto_blog_daemon.py --source rbc
else
    # Сб-Вс: оба
    python3 blog_cli.py parse -n 5
    python3 auto_blog_daemon.py --source rbc
fi
```

---

## 📊 Мониторинг источников

### Сколько статей с каждого источника

```bash
ssh -i ~/.ssh/id_housler root@91.229.8.221 'cd /var/www/housler && sqlite3 blog.db "
SELECT
    CASE
        WHEN original_url LIKE '%cian.ru%' THEN \"CIAN\"
        WHEN original_url LIKE '%rbc.ru%' THEN \"RBC\"
        ELSE \"Other\"
    END as source,
    COUNT(*) as count
FROM blog_posts
GROUP BY source
ORDER BY count DESC;
"'
```

**Вывод:**
```
CIAN|45
RBC|23
Other|2
```

---

## 🎯 Рекомендации

### Для максимального охвата:

1. **Основной источник:** CIAN Magazine (10 статей/день)
2. **Дополнительный:** RBC Realty (включить если нужно больше)
3. **Резервный:** Добавить Lenta.ru или Коммерсант

### Оптимальное расписание:

```
Каждый день в 10:00:
- CIAN Magazine (10 статей)
- Если не хватает новых → RBC Realty (автофолбэк)

Итого: 10-15 новых статей в день
```

### Не перегружать:

- ⚠️ Yandex GPT API имеет лимиты (RPM, TPM)
- ⚠️ Playwright потребляет ресурсы сервера
- ⚠️ Сайты-источники могут банить за частые запросы

**Золотое правило:** 10-20 статей в день достаточно для регулярного обновления блога

---

## 🆘 Troubleshooting

### Проблема: RBC Realty парсер не работает

**Проверка:**
```bash
ssh -i ~/.ssh/id_housler root@91.229.8.221 'cd /var/www/housler && source venv/bin/activate && python3 -c "from rbc_realty_parser import RBCRealtyParser; print(\"OK\")"'
```

**Если ошибка:** парсер нужно доработать под текущую вёрстку RBC

---

### Проблема: Источник даёт мало статей

**Причины:**
1. Мало новых публикаций на источнике
2. Большинство статей уже были распарсены
3. Парсер не находит нужные селекторы

**Решение:**
- Увеличить `limit` в `get_recent_articles(limit=20)`
- Проверить селекторы в парсере (сайт мог изменить вёрстку)
- Добавить альтернативный источник

---

## 📚 Связанные документы

- [FINAL_DEPLOYMENT_GUIDE.md](FINAL_DEPLOYMENT_GUIDE.md) - Основной гайд по деплою
- [MANUAL_BLOG_PARSE.md](MANUAL_BLOG_PARSE.md) - Ручной запуск парсера
- [blog_parser_playwright.py](blog_parser_playwright.py) - Пример парсера CIAN
- [rbc_realty_parser.py](rbc_realty_parser.py) - Парсер RBC Realty

---

**Вопросы?** hello@housler.ru
