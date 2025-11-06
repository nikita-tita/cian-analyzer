# Деплой на Vercel

## Быстрый старт

### 1. Установка Vercel CLI (если еще нет)

```bash
npm install -g vercel
```

### 2. Вход в аккаунт Vercel

```bash
vercel login
```

### 3. Деплой проекта

```bash
cd /Users/fatbookpro/Desktop/cian
vercel
```

При первом деплое Vercel задаст вопросы:
- **Set up and deploy?** → Yes
- **Which scope?** → (выберите свой аккаунт)
- **Link to existing project?** → No
- **Project name?** → cian-analyzer (или любое имя)
- **In which directory is your code located?** → ./ (текущая директория)

### 4. Production деплой

```bash
vercel --prod
```

## Файлы конфигурации

### vercel.json
Конфигурация Vercel:
- Entry point: `index.py`
- Static files: `/src/static/`
- Memory: 1024 MB
- Timeout: 30 секунд

### requirements.txt
Зависимости Python для serverless:
- Flask (веб-фреймворк)
- Pydantic (валидация)
- BeautifulSoup (парсинг HTML)
- NumPy, SciPy (статистика)

**Важно:** Playwright не работает на Vercel serverless!

### .vercelignore
Файлы, которые не загружаются:
- Тесты (`test_*.py`)
- Debug скрипты (`debug_*.py`)
- Cache (`__pycache__/`)
- Environment (`.env`)

## Структура проекта для Vercel

```
cian/
├── index.py              # Entry point для Vercel
├── app_new.py            # Flask приложение
├── vercel.json           # Конфигурация Vercel
├── requirements.txt      # Python зависимости
├── .vercelignore         # Игнорируемые файлы
├── src/
│   ├── analytics/        # Аналитика
│   ├── models/           # Pydantic модели
│   ├── parsers/          # Парсеры (без Playwright!)
│   ├── templates/        # HTML шаблоны
│   └── static/           # CSS, JS, изображения
```

## Ограничения Vercel

1. **Serverless Functions:**
   - Max execution time: 10s (Hobby), 60s (Pro)
   - Max memory: 1024 MB (Hobby), 3008 MB (Pro)
   - Cold start: ~1-2 секунды

2. **Не работает:**
   - Playwright (требует браузер)
   - Selenium (требует браузер)
   - Долгие процессы (>30 секунд)

3. **Реализованные решения:**
   ✅ **SimpleParser** - автоматически используется на Vercel
   - `index.py` автоматически подменяет PlaywrightParser на SimpleParser
   - Использует requests + BeautifulSoup для базового парсинга
   - Для демо возвращает тестовые аналоги
   - ⚠️ **Для полноценной работы используйте локальную версию с Playwright**

## После деплоя

1. Vercel выдаст URL:
   - Preview: `https://cian-analyzer-xxx.vercel.app`
   - Production: `https://cian-analyzer.vercel.app`

2. Проверьте работу:
   ```bash
   curl https://cian-analyzer-xxx.vercel.app
   ```

3. Настройте домен (опционально):
   - Settings → Domains → Add Domain

## Отладка

### Логи
```bash
vercel logs
```

### Локальный dev сервер
```bash
vercel dev
```

### Пересоздать деплой
```bash
vercel --prod --force
```

## Environment Variables

Если нужны переменные окружения:

```bash
vercel env add SECRET_KEY
```

Или через Dashboard:
Settings → Environment Variables

## Проблемы и решения

### Ошибка: Module not found
- Проверьте `requirements.txt`
- Убедитесь что все импорты корректны

### Ошибка: Function timeout
- Уменьшите время выполнения
- Используйте кеширование
- Упростите логику

### Статика не грузится
- Проверьте пути в `vercel.json`
- Убедитесь что файлы в `/src/static/`

## Альтернатива: Railway.app или Heroku

Если нужен Playwright:
- Railway.app (поддерживает Docker)
- Heroku (с buildpack)
- DigitalOcean App Platform

## Дата
2025-11-06
