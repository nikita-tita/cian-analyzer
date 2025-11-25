"""
Инициализация и управление очередью задач RQ
"""
import os
import logging
from typing import Optional, Dict, Any
from redis import Redis
from rq import Queue
from rq.job import Job

logger = logging.getLogger(__name__)

# Глобальная очередь задач
_task_queue: Optional[Queue] = None
_redis_conn: Optional[Redis] = None


def init_task_queue(redis_url: Optional[str] = None) -> Queue:
    """
    Инициализация очереди задач RQ

    Args:
        redis_url: URL подключения к Redis (если None, берется из env)

    Returns:
        Queue объект для постановки задач
    """
    global _task_queue, _redis_conn

    if _task_queue is not None:
        return _task_queue

    # Получаем URL Redis
    if redis_url is None:
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6380/0')

    try:
        # Подключаемся к Redis
        _redis_conn = Redis.from_url(redis_url, decode_responses=False)

        # Проверяем подключение
        _redis_conn.ping()

        # Создаем очередь
        _task_queue = Queue('housler-tasks', connection=_redis_conn)

        logger.info(f"✅ Task queue initialized: {redis_url}")
        return _task_queue

    except Exception as e:
        logger.error(f"❌ Failed to initialize task queue: {e}")
        logger.warning("⚠️ Running without async task queue")
        _task_queue = None
        _redis_conn = None
        return None


def get_task_queue() -> Optional[Queue]:
    """
    Получить глобальную очередь задач

    Returns:
        Queue объект или None если очередь не инициализирована
    """
    global _task_queue

    if _task_queue is None:
        return init_task_queue()

    return _task_queue


def enqueue_task(func, *args, **kwargs) -> Optional[Job]:
    """
    Поставить задачу в очередь

    Args:
        func: Функция для выполнения
        *args: Аргументы функции
        **kwargs: Именованные аргументы функции

    Returns:
        Job объект или None если очередь недоступна
    """
    queue = get_task_queue()

    if queue is None:
        logger.warning("Task queue not available, executing synchronously")
        # Fallback: выполняем синхронно
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error executing task synchronously: {e}")
            raise

    try:
        # Ставим в очередь с timeout 5 минут
        job = queue.enqueue(
            func,
            *args,
            **kwargs,
            job_timeout=300,  # 5 минут
            result_ttl=3600,  # Храним результат 1 час
            failure_ttl=3600  # Храним ошибки 1 час
        )
        logger.info(f"Task enqueued: {job.id} - {func.__name__}")
        return job
    except Exception as e:
        logger.error(f"Failed to enqueue task: {e}")
        raise


def get_task_status(job_id: str) -> Dict[str, Any]:
    """
    Получить статус задачи по ID

    Args:
        job_id: ID задачи

    Returns:
        Словарь со статусом задачи
    """
    queue = get_task_queue()

    if queue is None:
        return {
            'status': 'error',
            'error': 'Task queue not available'
        }

    try:
        job = Job.fetch(job_id, connection=queue.connection)

        # Базовая информация
        status_info = {
            'job_id': job.id,
            'status': job.get_status(),
            'created_at': job.created_at.isoformat() if job.created_at else None,
            'started_at': job.started_at.isoformat() if job.started_at else None,
            'ended_at': job.ended_at.isoformat() if job.ended_at else None,
        }

        # Добавляем результат или ошибку в зависимости от статуса
        if job.is_finished:
            status_info['result'] = job.result
        elif job.is_failed:
            status_info['error'] = str(job.exc_info) if job.exc_info else 'Unknown error'

        # Добавляем прогресс если есть
        if hasattr(job, 'meta') and job.meta:
            status_info['progress'] = job.meta.get('progress', 0)
            status_info['message'] = job.meta.get('message', '')

        return status_info

    except Exception as e:
        logger.error(f"Failed to get task status for {job_id}: {e}")
        return {
            'status': 'error',
            'error': f'Job not found or error: {str(e)}'
        }


def update_task_progress(job: Job, progress: int, message: str = ''):
    """
    Обновить прогресс задачи

    Args:
        job: Job объект
        progress: Прогресс в процентах (0-100)
        message: Сообщение о текущем статусе
    """
    try:
        job.meta['progress'] = progress
        job.meta['message'] = message
        job.save_meta()
        logger.debug(f"Task {job.id} progress: {progress}% - {message}")
    except Exception as e:
        logger.error(f"Failed to update task progress: {e}")
