# Исправление деплоя на Railway

## Проблема

Из логов видно, что в Railway запускается старая версия приложения, которая пытается подключиться к Redis и PostgreSQL на localhost. Текущая версия приложения (`app_new.py`) использует in-memory хранилище и **не требует** Redis или PostgreSQL.

## Решение

### Шаг 1: Удалить Redis сервис из Railway

1. Откройте [Railway Dashboard](https://railway.app/dashboard)
2. Найдите ваш проект
3. Удалите сервис **"responsible-elegance"** (Redis) - он не нужен для текущей версии
4. Удалите PostgreSQL сервис, если он есть

### Шаг 2: Очистить кэш и пересобрать проект

В Railway:

1. Откройте ваш **Web Service** (приложение)
2. Перейдите в **Settings**
3. Найдите раздел **Danger Zone**
4. Нажмите **"Clear Build Cache"**
5. Нажмите **"Redeploy"**

### Шаг 3: Проверить переменные окружения

В Railway Dashboard:

1. Откройте ваш проект
2. Перейдите в **Variables**
3. Убедитесь, что нет переменных связанных с Redis/PostgreSQL:
   - Удалите `REDIS_URL`, `REDIS_HOST`, `REDIS_PORT` (если есть)
   - Удалите `DATABASE_URL`, `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD` (если есть)
4. Оставьте только:
   - `PORT` (автоматически создается Railway)
   - `FLASK_ENV=production` (опционально)

### Шаг 4: Проверить, что используется правильная ветка

1. В Railway Dashboard откройте ваш проект
2. Перейдите в **Settings → Source**
3. Убедитесь, что используется правильная ветка: `claude/fix-project-deployment-011CUrhFtfy5rawguigGdbYL`
4. Или используйте `main` ветку после того, как изменения будут смержены

## Что было исправлено в коде

1. **Procfile** - уменьшил количество workers до 1 и добавил debug логирование
2. **railway.toml** - добавил переменные окружения `FLASK_ENV` и `PYTHONUNBUFFERED`

## Текущая архитектура приложения

```
app_new.py (Flask)
  ├── in-memory sessions_storage {}
  ├── PlaywrightParser (парсинг Cian)
  └── RealEstateAnalyzer (анализ данных)
```

**Важно:** Приложение **НЕ требует** внешних баз данных. Все данные хранятся в памяти процесса.

## Проверка после деплоя

После успешного деплоя вы должны увидеть в логах:

```
[INFO] Starting gunicorn
[INFO] Listening at: http://0.0.0.0:8080
[INFO] Using worker: sync
[INFO] Booting worker with pid: X
```

Без ошибок подключения к Redis или PostgreSQL.

## Ограничения in-memory хранилища

При использовании in-memory хранилища:
- Сессии теряются при перезапуске приложения
- Несколько workers не могут делить данные
- Поэтому используется только 1 worker

Для production с высокой нагрузкой потребуется добавить Redis для хранения сессий.
