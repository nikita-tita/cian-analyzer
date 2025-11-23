"""
Определения асинхронных задач

Эти функции выполняются в фоне RQ воркером
"""
import logging
from typing import Dict, Any, List
from rq import get_current_job

from src.parsers import get_global_registry
from src.cache import get_cache
from src.utils.session_storage import get_session_storage

logger = logging.getLogger(__name__)


def parse_property_task(url: str, session_id: str) -> Dict[str, Any]:
    """
    Асинхронная задача парсинга URL недвижимости

    Args:
        url: URL для парсинга
        session_id: ID сессии для сохранения результата

    Returns:
        Результат парсинга
    """
    job = get_current_job()
    logger.info(f"[Task {job.id}] Starting parse task for URL: {url}")

    try:
        # Обновляем прогресс
        if job:
            job.meta['progress'] = 10
            job.meta['message'] = 'Инициализация парсера...'
            job.save_meta()

        # Получаем парсер из реестра
        parser_registry = get_global_registry(cache=get_cache())

        if job:
            job.meta['progress'] = 20
            job.meta['message'] = 'Загрузка страницы...'
            job.save_meta()

        # Парсим URL
        parser = parser_registry.get_parser_by_url(url)
        if not parser:
            raise ValueError(f"No parser available for URL: {url}")

        if job:
            job.meta['progress'] = 40
            job.meta['message'] = 'Извлечение данных...'
            job.save_meta()

        data = parser.parse_detail_page(url)

        if not data:
            raise ValueError("Failed to parse property data")

        if job:
            job.meta['progress'] = 80
            job.meta['message'] = 'Сохранение результата...'
            job.save_meta()

        # Сохраняем в сессию
        session_storage = get_session_storage()
        session_data = session_storage.get(session_id) or {}

        session_data.update({
            'target_property': data,
            'url': url,
            'last_updated': str(datetime.now())
        })

        session_storage.set(session_id, session_data)

        if job:
            job.meta['progress'] = 100
            job.meta['message'] = 'Готово'
            job.save_meta()

        logger.info(f"[Task {job.id}] Parse task completed successfully")

        return {
            'success': True,
            'data': data,
            'session_id': session_id
        }

    except Exception as e:
        logger.error(f"[Task {job.id if job else 'unknown'}] Parse task failed: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def find_similar_task(
    session_id: str,
    target_property: Dict,
    limit: int = 20,
    search_strategy: str = 'citywide'
) -> Dict[str, Any]:
    """
    Асинхронная задача поиска аналогов

    Args:
        session_id: ID сессии
        target_property: Целевой объект для поиска
        limit: Максимальное количество аналогов
        search_strategy: Стратегия поиска

    Returns:
        Результат поиска
    """
    job = get_current_job()
    logger.info(f"[Task {job.id}] Starting find similar task")

    try:
        # Обновляем прогресс
        if job:
            job.meta['progress'] = 10
            job.meta['message'] = 'Подготовка поиска...'
            job.save_meta()

        # Получаем парсер
        parser_registry = get_global_registry(cache=get_cache())
        parser = parser_registry.get_parser(source_name='cian')

        if not parser:
            raise ValueError("Parser not available")

        if job:
            job.meta['progress'] = 20
            job.meta['message'] = f'Поиск аналогов ({search_strategy})...'
            job.save_meta()

        # Выполняем поиск
        comparables = parser.search_similar(
            target_property=target_property,
            limit=limit,
            strategy=search_strategy
        )

        if job:
            job.meta['progress'] = 70
            job.meta['message'] = f'Найдено {len(comparables)} объектов...'
            job.save_meta()

        # Сохраняем в сессию
        session_storage = get_session_storage()
        session_data = session_storage.get(session_id) or {}

        session_data.update({
            'comparables': comparables,
            'search_completed': True,
            'last_updated': str(datetime.now())
        })

        session_storage.set(session_id, session_data)

        if job:
            job.meta['progress'] = 100
            job.meta['message'] = 'Поиск завершен'
            job.save_meta()

        logger.info(f"[Task {job.id}] Find similar task completed: {len(comparables)} found")

        return {
            'success': True,
            'count': len(comparables),
            'comparables': comparables,
            'session_id': session_id
        }

    except Exception as e:
        logger.error(f"[Task {job.id if job else 'unknown'}] Find similar task failed: {e}")
        return {
            'success': False,
            'error': str(e)
        }


# Импорт datetime для timestamps
from datetime import datetime
