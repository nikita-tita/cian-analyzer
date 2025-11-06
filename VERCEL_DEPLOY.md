# Vercel Deployment Guide

Пошаговое руководство по деплою Cian Analyzer на Vercel.

## 🚀 Быстрый старт

### Deploy через Vercel Dashboard

1. Перейдите на https://vercel.com
2. Нажмите "New Project"
3. Импортируйте репозиторий `nikita-tita/cian-analyzer`
4. Vercel автоматически определит настройки
5. Нажмите "Deploy"

### Deploy через CLI

```bash
npm install -g vercel
vercel login
cd /path/to/cian-analyzer
vercel --prod
```

## ⚙️ Environment Variables (опционально)

### Redis (Upstash) - для сессий

1. Создайте Redis на https://upstash.com
2. Добавьте в Vercel:
   - REDIS_URL=your_redis_url
   - REDIS_PASSWORD=your_password

### PostgreSQL (Supabase) - для истории

1. Создайте БД на https://supabase.com
2. Добавьте в Vercel:
   - DATABASE_URL=your_postgres_url
   - POSTGRES_PASSWORD=your_password

## 🔍 Проверка

После деплоя:

```bash
curl https://your-app.vercel.app/api/vercel-health
curl https://your-app.vercel.app/api/info
```

## 📊 Особенности Vercel версии

✅ Работает: Redis, PostgreSQL, SimpleParser
❌ Не работает: Playwright (слишком большой)

## 🆘 Troubleshooting

Проблемы? Проверьте:
- `vercel logs`
- `/api/vercel-health`
- Environment Variables

Подробная документация: см. полную версию этого файла
