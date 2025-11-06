# Railway Dockerfile для Cian Analyzer с Playwright
FROM python:3.11-slim

# Устанавливаем системные зависимости для Playwright
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libwayland-client0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    libu2f-udev \
    libvulkan1 \
    && rm -rf /var/lib/apt/lists/*

# Рабочая директория
WORKDIR /app

# Копируем requirements
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Устанавливаем Playwright и браузер Chromium
RUN pip install playwright && \
    playwright install chromium && \
    playwright install-deps chromium

# Копируем весь проект
COPY . .

# Переменные окружения
ENV PYTHONUNBUFFERED=1
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Порт
EXPOSE 8080

# Запуск
CMD gunicorn app_new:app --bind 0.0.0.0:$PORT --workers 2 --timeout 300 --log-level info --access-logfile - --error-logfile -
