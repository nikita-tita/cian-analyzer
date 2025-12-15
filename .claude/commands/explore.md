# Исследование кодовой базы

Вопрос: $ARGUMENTS

## Инструкции

Исследуй кодовую базу чтобы ответить на вопрос. Используй ТОЛЬКО read-only операции.

### Разрешённые действия
- `Glob` — поиск файлов по паттерну
- `Grep` — поиск по содержимому
- `Read` — чтение файлов
- `git log`, `git status`, `git diff` — история изменений

### Запрещённые действия
- Создание файлов
- Редактирование файлов
- Удаление файлов
- Запуск команд изменяющих систему

## Структура проекта Cian Analyzer (справка)

```
cian/
├── api/              # FastAPI endpoints
├── parsers/          # Парсеры Cian (selenium, etc.)
├── models/           # SQLAlchemy models
├── tasks/            # Celery tasks
├── analytics/        # Аналитика данных
├── utils/            # Утилиты
├── templates/        # Jinja2 templates
├── static/           # Static files
├── tests/            # Pytest тесты
└── alembic/          # Database migrations
```

## Формат ответа

```markdown
## Ответ
[Краткий ответ на вопрос]

## Найденные файлы
- `path/to/file.py:line` — описание
- `path/to/file2.py:line` — описание

## Детали
[Подробное объяснение с примерами кода]

## Связанные файлы
[Другие файлы которые могут быть полезны]
```
