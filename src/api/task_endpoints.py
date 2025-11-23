"""
API эндпоинты для работы с асинхронными задачами

Эти эндпоинты позволяют:
- Ставить задачи в очередь
- Проверять статус задач
- Получать результаты выполненных задач
"""
from flask import Blueprint, request, jsonify
import logging

from src.tasks import get_task_queue, get_task_status
from src.tasks.tasks import parse_property_task, find_similar_task
from src.tasks.queue import enqueue_task

logger = logging.getLogger(__name__)

# Создаем blueprint для task API
task_api = Blueprint('task_api', __name__, url_prefix='/api/tasks')


@task_api.route('/status/<job_id>', methods=['GET'])
def get_job_status(job_id: str):
    """
    Получить статус задачи

    GET /api/tasks/status/<job_id>

    Returns:
        JSON с информацией о статусе задачи
    """
    try:
        status = get_task_status(job_id)
        return jsonify(status), 200
    except Exception as e:
        logger.error(f"Error getting task status: {e}")
        return jsonify({'error': str(e)}), 500


@task_api.route('/parse', methods=['POST'])
def async_parse():
    """
    Поставить задачу парсинга в очередь

    POST /api/tasks/parse
    Body: {
        "url": "https://...",
        "session_id": "..."
    }

    Returns:
        JSON с job_id для отслеживания статуса
    """
    try:
        data = request.get_json()
        url = data.get('url')
        session_id = data.get('session_id')

        if not url or not session_id:
            return jsonify({'error': 'url and session_id are required'}), 400

        # Ставим задачу в очередь
        job = enqueue_task(parse_property_task, url, session_id)

        if job is None:
            # Очередь недоступна - выполняем синхронно
            return jsonify({
                'error': 'Task queue not available',
                'suggestion': 'Use /api/parse endpoint for synchronous parsing'
            }), 503

        return jsonify({
            'job_id': job.id,
            'status': 'queued',
            'message': 'Task queued successfully',
            'poll_url': f'/api/tasks/status/{job.id}'
        }), 202

    except Exception as e:
        logger.error(f"Error enqueueing parse task: {e}")
        return jsonify({'error': str(e)}), 500


@task_api.route('/find-similar', methods=['POST'])
def async_find_similar():
    """
    Поставить задачу поиска аналогов в очередь

    POST /api/tasks/find-similar
    Body: {
        "session_id": "...",
        "target_property": {...},
        "limit": 20,
        "search_strategy": "citywide"
    }

    Returns:
        JSON с job_id для отслеживания статуса
    """
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        target_property = data.get('target_property')
        limit = data.get('limit', 20)
        search_strategy = data.get('search_strategy', 'citywide')

        if not session_id or not target_property:
            return jsonify({
                'error': 'session_id and target_property are required'
            }), 400

        # Ставим задачу в очередь
        job = enqueue_task(
            find_similar_task,
            session_id,
            target_property,
            limit,
            search_strategy
        )

        if job is None:
            # Очередь недоступна
            return jsonify({
                'error': 'Task queue not available',
                'suggestion': 'Use /api/find-similar endpoint for synchronous search'
            }), 503

        return jsonify({
            'job_id': job.id,
            'status': 'queued',
            'message': 'Search task queued successfully',
            'poll_url': f'/api/tasks/status/{job.id}'
        }), 202

    except Exception as e:
        logger.error(f"Error enqueueing find similar task: {e}")
        return jsonify({'error': str(e)}), 500


@task_api.route('/queue-stats', methods=['GET'])
def queue_stats():
    """
    Получить статистику очереди задач

    GET /api/tasks/queue-stats

    Returns:
        JSON со статистикой очереди
    """
    try:
        queue = get_task_queue()

        if queue is None:
            return jsonify({
                'error': 'Task queue not available'
            }), 503

        # Получаем статистику
        stats = {
            'queued_jobs': len(queue),
            'started_jobs': len(queue.started_job_registry),
            'finished_jobs': len(queue.finished_job_registry),
            'failed_jobs': len(queue.failed_job_registry),
            'deferred_jobs': len(queue.deferred_job_registry),
            'scheduled_jobs': len(queue.scheduled_job_registry) if hasattr(queue, 'scheduled_job_registry') else 0,
        }

        return jsonify(stats), 200

    except Exception as e:
        logger.error(f"Error getting queue stats: {e}")
        return jsonify({'error': str(e)}), 500
