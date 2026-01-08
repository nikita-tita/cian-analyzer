# Инструкция для Claude Code: Cian Analyzer

> **Последнее обновление:** 2026-01-08

---

## Проект

**housler.ru** — Анализатор объявлений CIAN

### Основные функции

- Парсинг объявлений с CIAN
- Анализ цен и характеристик
- Сравнительный анализ объектов
- Экспорт данных (Markdown, TXT)

---

## Структура проекта

```
cian-analyzer/
├── app.py               # Flask приложение (главный файл)
├── parsers/             # Парсеры CIAN
│   ├── cian_parser.py   # Основной парсер
│   └── ...
├── templates/           # HTML шаблоны
├── static/              # CSS, JS, изображения
├── tests/               # Тесты
├── docker-compose.yml   # Docker конфиг
├── Dockerfile           # Образ приложения
├── requirements.txt     # Python зависимости
├── DEPLOY.md            # Инструкция по деплою
├── CLAUDE.md            # Этот файл
└── _archive/            # Устаревшая документация
```

---

## Design Guidelines

### No Emojis

Do NOT use emojis in the UI, templates, or CSS. Use typography and CSS styling instead.

Examples:
- Lists: use `—` (em-dash) or CSS bullets, NOT checkmarks or emojis
- Icons: use CSS or inline SVG, NOT emoji icons
- Buttons: text only, no emoji decorations

### CSS

- Use existing design system variables (--color-primary, --color-text, etc.)
- Reuse existing classes (service-card, btn, btn-primary) before creating new ones
- Minimalist design, no decorative elements

### Templates

- Jinja2 templates in /templates
- Cache-busting via query params: landing.css?v=YYYYMMDD

---

## Правила разработки

> **Полные правила:** [SHARED/DEVELOPMENT_RULES.md](../Desktop/housler_pervichka/docs/SHARED/DEVELOPMENT_RULES.md)

### Кратко

1. **Сначала читай, потом редактируй**
2. **Минимальные изменения**
3. **Не ломай работающее**

---

## Деплой

См. [DEPLOY.md](./DEPLOY.md)

### Быстрая команда

```bash
ssh root@95.163.227.26 "cd /root/cian-analyzer && git pull && docker compose up -d --build"
```

---

## Тестирование

```bash
# Локально
python -m pytest tests/

# Проверка парсера
python parsers/cian_parser.py --url "https://cian.ru/..."
```

---

## Важные файлы

| Файл | Описание |
|------|----------|
| `app.py` | Главное Flask приложение |
| `parsers/cian_parser.py` | Парсер объявлений CIAN |
| `templates/index.html` | Главная страница |
| `templates/result.html` | Результаты анализа |

---

## Известные особенности

1. **Playwright** — используется для парсинга динамического контента
2. **Redis** — кэширование результатов парсинга (порт 6380)
3. **Rate limiting** — защита от блокировки CIAN

---

## Документация

**Устаревшие файлы:** В проекте много старых .md файлов. Актуальные документы:
- `README.md` — описание проекта (если есть)
- `DEPLOY.md` — деплой
- `CLAUDE.md` — этот файл

Устаревшие файлы будут перемещены в `_archive/`.

---

## Экосистема Housler

Этот проект — часть экосистемы Housler. Общие сервисы:

| Сервис | Провайдер | Документация |
|--------|-----------|--------------|
| **SMS авторизация** | agent.housler.ru (SMS.RU) | [AUTH_API.md](../Desktop/housler_pervichka/docs/SHARED/AUTH_API.md) |
| **Email авторизация** | agent.housler.ru (Yandex SMTP) | [AUTH_API.md](../Desktop/housler_pervichka/docs/SHARED/AUTH_API.md) |
| **Сервер** | 95.163.227.26 (reg.ru) | [SERVER_ACCESS.md](../Desktop/housler_pervichka/docs/SHARED/SERVER_ACCESS.md) |

> **Примечание:** housler.ru не использует авторизацию (публичный анализатор).

---

## Связанные документы

- [housler_pervichka/DEPLOY.md](../Desktop/housler_pervichka/DEPLOY.md) — Главный гайд по серверу
- [SHARED/](../Desktop/housler_pervichka/docs/SHARED/) — Общая документация

---

*Обновлено: 2026-01-08*
