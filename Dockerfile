# Multi-stage build для оптимизации размера образа
FROM python:3.11-slim as builder

# Установка системных зависимостей для компиляции
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements и устанавливаем Python зависимости
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt


# Production stage
FROM python:3.11-slim

# Метаданные
LABEL maintainer="Housler <info@housler.ru>"
LABEL version="2.0.0"
LABEL description="Housler - Intelligent Real Estate Analytics"

# Установка Playwright зависимостей
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Playwright dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libatspi2.0-0 \
    # Fonts
    fonts-liberation \
    fonts-noto-color-emoji \
    # Utils
    curl \
    && rm -rf /var/lib/apt/lists/*

# Создаем пользователя для безопасности (не root)
RUN useradd -m -u 1000 housler && \
    mkdir -p /app /data && \
    chown -R housler:housler /app /data

# Копируем Python packages из builder
COPY --from=builder /root/.local /home/housler/.local

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем код приложения
COPY --chown=housler:housler . .

# Переключаемся на непривилегированного пользователя
USER housler

# Добавляем local bin в PATH
ENV PATH=/home/housler/.local/bin:$PATH

# Устанавливаем Playwright браузеры
RUN playwright install chromium

# Переменные окружения
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FLASK_APP=app_new.py \
    # Redis настройки (можно переопределить)
    REDIS_HOST=redis \
    REDIS_PORT=6380 \
    REDIS_DB=0 \
    REDIS_ENABLED=true \
    REDIS_NAMESPACE=housler \
    # Gunicorn настройки
    WORKERS=4 \
    WORKER_CLASS=sync \
    TIMEOUT=300 \
    BIND=0.0.0.0:5000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Expose порт
EXPOSE 5000

# Запуск через Gunicorn
CMD gunicorn app_new:app \
    --workers $WORKERS \
    --worker-class $WORKER_CLASS \
    --timeout $TIMEOUT \
    --bind $BIND \
    --access-logfile - \
    --error-logfile - \
    --log-level info
