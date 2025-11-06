"""
Redis Session Manager для Railway deployment
Управляет сессиями через Redis для работы с multiple workers
"""

import json
import logging
import os
from typing import Dict, Optional, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not available, using in-memory fallback")


class RedisSessionManager:
    """Менеджер сессий с Redis backend"""

    def __init__(self):
        self.redis_url = os.getenv('REDIS_URL')
        self.redis_client = None
        self.fallback_storage = {}  # Fallback для локальной разработки

        if REDIS_AVAILABLE and self.redis_url:
            try:
                self.redis_client = redis.from_url(
                    self.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
                # Проверяем подключение
                self.redis_client.ping()
                logger.info("✅ Redis подключен успешно")
            except Exception as e:
                logger.error(f"❌ Ошибка подключения к Redis: {e}")
                logger.warning("⚠️ Использую in-memory fallback")
                self.redis_client = None
        else:
            logger.warning("⚠️ Redis URL не найден, использую in-memory fallback")

    def _get_key(self, session_id: str) -> str:
        """Генерирует ключ для Redis"""
        return f"session:{session_id}"

    def create_session(self, session_id: str, data: Dict[str, Any], ttl: int = 3600) -> bool:
        """
        Создает новую сессию

        Args:
            session_id: ID сессии
            data: Данные сессии
            ttl: Time to live в секундах (по умолчанию 1 час)
        """
        try:
            # Добавляем timestamp
            data['created_at'] = datetime.now().isoformat()
            data['updated_at'] = datetime.now().isoformat()

            if self.redis_client:
                key = self._get_key(session_id)
                json_data = json.dumps(data, default=str)
                self.redis_client.setex(key, ttl, json_data)
                logger.info(f"✅ Сессия {session_id} создана в Redis (TTL: {ttl}s)")
            else:
                # Fallback
                self.fallback_storage[session_id] = data
                logger.info(f"✅ Сессия {session_id} создана в памяти")

            return True
        except Exception as e:
            logger.error(f"❌ Ошибка создания сессии {session_id}: {e}")
            return False

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Получает данные сессии"""
        try:
            if self.redis_client:
                key = self._get_key(session_id)
                data = self.redis_client.get(key)

                if data:
                    logger.info(f"✅ Сессия {session_id} найдена в Redis")
                    return json.loads(data)
                else:
                    logger.warning(f"⚠️ Сессия {session_id} не найдена в Redis")
                    return None
            else:
                # Fallback
                data = self.fallback_storage.get(session_id)
                if data:
                    logger.info(f"✅ Сессия {session_id} найдена в памяти")
                else:
                    logger.warning(f"⚠️ Сессия {session_id} не найдена в памяти")
                return data
        except Exception as e:
            logger.error(f"❌ Ошибка получения сессии {session_id}: {e}")
            return None

    def update_session(self, session_id: str, data: Dict[str, Any], ttl: int = 3600) -> bool:
        """Обновляет данные сессии"""
        try:
            # Получаем существующую сессию
            existing = self.get_session(session_id)

            if existing is None:
                logger.error(f"❌ Сессия {session_id} не найдена для обновления")
                return False

            # Обновляем данные
            existing.update(data)
            existing['updated_at'] = datetime.now().isoformat()

            if self.redis_client:
                key = self._get_key(session_id)
                json_data = json.dumps(existing, default=str)
                self.redis_client.setex(key, ttl, json_data)
                logger.info(f"✅ Сессия {session_id} обновлена в Redis")
            else:
                # Fallback
                self.fallback_storage[session_id] = existing
                logger.info(f"✅ Сессия {session_id} обновлена в памяти")

            return True
        except Exception as e:
            logger.error(f"❌ Ошибка обновления сессии {session_id}: {e}")
            return False

    def delete_session(self, session_id: str) -> bool:
        """Удаляет сессию"""
        try:
            if self.redis_client:
                key = self._get_key(session_id)
                self.redis_client.delete(key)
                logger.info(f"✅ Сессия {session_id} удалена из Redis")
            else:
                # Fallback
                if session_id in self.fallback_storage:
                    del self.fallback_storage[session_id]
                    logger.info(f"✅ Сессия {session_id} удалена из памяти")

            return True
        except Exception as e:
            logger.error(f"❌ Ошибка удаления сессии {session_id}: {e}")
            return False

    def session_exists(self, session_id: str) -> bool:
        """Проверяет существование сессии"""
        if self.redis_client:
            key = self._get_key(session_id)
            return self.redis_client.exists(key) > 0
        else:
            return session_id in self.fallback_storage

    def get_all_sessions(self) -> int:
        """Возвращает количество активных сессий"""
        try:
            if self.redis_client:
                pattern = self._get_key("*")
                keys = self.redis_client.keys(pattern)
                return len(keys)
            else:
                return len(self.fallback_storage)
        except Exception as e:
            logger.error(f"❌ Ошибка подсчета сессий: {e}")
            return 0

    def is_redis_connected(self) -> bool:
        """Проверяет подключение к Redis"""
        return self.redis_client is not None
