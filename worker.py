#!/usr/bin/env python3
"""
RQ Worker для обработки асинхронных задач Housler

Запуск:
    python worker.py

Или с настройками:
    REDIS_URL=redis://localhost:6380/0 python worker.py

В продакшене запускается через systemd или supervisor:
    rq worker housler-tasks --url redis://localhost:6380/0
"""
import os
import sys
import logging
from pathlib import Path

# Добавляем текущую директорию в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

from redis import Redis
from rq import Worker, Queue

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Запуск RQ воркера"""
    # Получаем URL Redis из переменной окружения
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6380/0')

    logger.info(f"Starting RQ worker...")
    logger.info(f"Redis URL: {redis_url}")

    try:
        # Подключаемся к Redis
        redis_conn = Redis.from_url(redis_url, decode_responses=False)

        # Проверяем подключение
        redis_conn.ping()
        logger.info("✅ Connected to Redis")

        # Получаем очередь
        queues = [Queue('housler-tasks', connection=redis_conn)]

        logger.info(f"Listening to queues: {[q.name for q in queues]}")

        # Запускаем воркер
        worker = Worker(queues, connection=redis_conn)
        logger.info("🚀 Worker started, waiting for tasks...")
        worker.work()

    except KeyboardInterrupt:
        logger.info("\n⏹️  Worker stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Failed to start worker: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
