# Упрощённый Dockerfile без Playwright (быстрее деплоится)
FROM python:3.11-slim

WORKDIR /app

# Копируем requirements
COPY requirements.txt .

# Устанавливаем только базовые зависимости (без playwright)
RUN pip install --no-cache-dir \
    Flask>=3.0.0 \
    pydantic>=2.5.0 \
    requests>=2.31.0 \
    beautifulsoup4>=4.12.0 \
    lxml>=4.9.0 \
    python-dotenv>=1.0.0 \
    fake-useragent>=1.4.0 \
    tenacity>=8.2.3 \
    numpy>=1.24.0 \
    scipy>=1.11.0 \
    redis>=5.0.0 \
    psycopg2-binary>=2.9.9

# Копируем приложение
COPY . .

# Создаём директорию для логов
RUN mkdir -p logs

# Expose порт
EXPOSE 5002

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5002/health')"

# Запуск (используем Vercel entry point без Playwright)
CMD ["python", "index.py"]
