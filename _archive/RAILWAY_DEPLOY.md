# Деплой на Railway

Проект готов к деплою на Railway! Все необходимые конфигурационные файлы уже созданы и загружены в GitHub.

## Ваш токен Railway

```
e4132d4b-0614-4b49-a2dc-9c0fdb906158
```

## Способ 1: Деплой через Web UI (рекомендуется)

1. Откройте [Railway Dashboard](https://railway.app/dashboard)
2. Войдите в свой аккаунт
3. Нажмите **"New Project"**
4. Выберите **"Deploy from GitHub repo"**
5. Авторизуйте Railway для доступа к GitHub (если еще не сделали)
6. Выберите репозиторий: `nikita-tita/cian-analyzer`
7. Railway автоматически обнаружит:
   - `Procfile` - команду запуска
   - `requirements.txt` - зависимости Python
   - `railway.toml` - конфигурацию деплоя
8. Нажмите **"Deploy Now"**

### Настройки после деплоя

Railway автоматически:
- Установит все зависимости из `requirements.txt`
- Запустит приложение с помощью gunicorn
- Выделит публичный URL (например, `https://your-app.railway.app`)

## Способ 2: Деплой через CLI

```bash
# 1. Войдите в Railway (используйте браузер для авторизации)
railway login

# 2. Инициализируйте проект
railway init

# 3. Свяжите с существующим проектом или создайте новый
railway link

# 4. Задеплойте
railway up
```

## Созданные файлы конфигурации

### [Procfile](Procfile)
```
web: gunicorn app_new:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
```
Запускает Flask приложение через gunicorn с 2 воркерами и таймаутом 120 секунд.

### [railway.toml](railway.toml)
```toml
[build]
builder = "NIXPACKS"
buildCommand = "pip install -r requirements.txt"

[deploy]
startCommand = "gunicorn app_new:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120"
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 10
```

### [railway.json](railway.json)
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "numReplicas": 1,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

## Переменные окружения

После деплоя добавьте переменные окружения в Railway Dashboard:

1. Откройте ваш проект в Railway
2. Перейдите в **Variables**
3. Добавьте необходимые переменные (если есть):
   - `FLASK_ENV=production`
   - Другие переменные из `.env.example`

## Мониторинг

После деплоя вы можете:
- Смотреть логи в реальном времени в Railway Dashboard
- Проверить статус деплоя
- Получить публичный URL вашего приложения

## Проверка работы

После успешного деплоя откройте URL вашего приложения:
```
https://your-app.railway.app
```

Вы должны увидеть главную страницу Cian Real Estate Analyzer.

## Особенности деплоя

1. **SimpleParser**: Проект использует SimpleParser (без Playwright) для совместимости с serverless окружением
2. **Gunicorn**: Вместо встроенного Flask сервера используется production-ready gunicorn
3. **Таймауты**: Установлен таймаут 120 секунд для обработки длительных запросов парсинга
4. **Автоперезапуск**: При падении приложения Railway автоматически перезапустит его (до 10 попыток)

## Troubleshooting

### Проблема: Приложение не запускается
- Проверьте логи в Railway Dashboard
- Убедитесь, что все зависимости установлены
- Проверьте, что `PORT` правильно передается приложению

### Проблема: Таймауты при парсинге
- Увеличьте таймаут в `Procfile` и `railway.toml`
- Проверьте, что используется SimpleParser (а не PlaywrightParser)

### Проблема: 502 Bad Gateway
- Проверьте логи на ошибки Python
- Убедитесь, что приложение слушает на `0.0.0.0:$PORT`
- Проверьте, что gunicorn запущен корректно

## Дополнительные ресурсы

- [Railway Documentation](https://docs.railway.app/)
- [Railway Python Guide](https://docs.railway.app/guides/python)
- [Gunicorn Documentation](https://docs.gunicorn.org/)
