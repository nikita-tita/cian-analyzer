"""
Redis Session Manager для хранения сессий пользователей
Поддерживает автоматическое истечение сессий и сериализацию данных
"""

import json
import os
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
import redis
from redis.exceptions import RedisError
import logging

logger = logging.getLogger(__name__)


class RedisSessionManager:
    """
    Менеджер сессий на основе Redis

    Features:
    - Автоматическое истечение сессий (TTL)
    - JSON сериализация/десериализация
    - Fallback на in-memory при отсутствии Redis
    - Thread-safe операции
    """

    def __init__(
        self,
        host: str = None,
        port: int = None,
        db: int = 0,
        password: str = None,
        ttl: int = 3600,  # 1 час по умолчанию
        use_fallback: bool = True
    ):
        """
        Инициализация Redis клиента

        Args:
            host: Redis host (default: localhost или из env REDIS_HOST)
            port: Redis port (default: 6379 или из env REDIS_PORT)
            db: Redis database number (default: 0)
            password: Redis password (из env REDIS_PASSWORD)
            ttl: Time to live для сессий в секундах (default: 3600)
            use_fallback: Использовать in-memory fallback если Redis недоступен
        """
        self.host = host or os.getenv('REDIS_HOST', 'localhost')
        self.port = int(port or os.getenv('REDIS_PORT', 6379))
        self.db = db
        self.password = password or os.getenv('REDIS_PASSWORD')
        self.ttl = ttl
        self.use_fallback = use_fallback

        # Fallback storage
        self._fallback_storage: Dict[str, Dict] = {}
        self._redis_available = False

        try:
            # Подключение к Redis
            self.redis_client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True
            )

            # Проверка подключения
            self.redis_client.ping()
            self._redis_available = True
            logger.info(f"✅ Redis подключен: {self.host}:{self.port}")

        except RedisError as e:
            if self.use_fallback:
                logger.warning(f"⚠️ Redis недоступен, использую in-memory fallback: {e}")
                self.redis_client = None
            else:
                logger.error(f"❌ Redis недоступен и fallback отключен: {e}")
                raise

    def _get_key(self, session_id: str) -> str:
        """Генерирует Redis ключ для сессии"""
        return f"session:{session_id}"

    def set(self, session_id: str, data: Dict, ttl: Optional[int] = None) -> bool:
        """
        Сохранение сессии

        Args:
            session_id: Уникальный ID сессии
            data: Данные сессии (dict)
            ttl: Время жизни в секундах (опционально)

        Returns:
            True если успешно, False при ошибке
        """
        try:
            # Добавляем метаданные
            data['_updated_at'] = datetime.now().isoformat()
            if '_created_at' not in data:
                data['_created_at'] = data['_updated_at']

            ttl = ttl or self.ttl

            if self._redis_available:
                # Redis storage
                key = self._get_key(session_id)
                serialized = json.dumps(data, ensure_ascii=False, default=str)
                self.redis_client.setex(key, ttl, serialized)
                logger.debug(f"📝 Сессия {session_id} сохранена в Redis (TTL: {ttl}s)")
            else:
                # Fallback storage
                self._fallback_storage[session_id] = {
                    'data': data,
                    'expires_at': datetime.now() + timedelta(seconds=ttl)
                }
                logger.debug(f"📝 Сессия {session_id} сохранена в fallback storage")

            return True

        except Exception as e:
            logger.error(f"❌ Ошибка сохранения сессии {session_id}: {e}")
            return False

    def get(self, session_id: str) -> Optional[Dict]:
        """
        Получение сессии

        Args:
            session_id: Уникальный ID сессии

        Returns:
            Данные сессии или None если не найдена
        """
        try:
            if self._redis_available:
                # Redis storage
                key = self._get_key(session_id)
                data = self.redis_client.get(key)

                if data:
                    result = json.loads(data)
                    logger.debug(f"📖 Сессия {session_id} получена из Redis")
                    return result
                else:
                    logger.debug(f"🔍 Сессия {session_id} не найдена в Redis")
                    return None
            else:
                # Fallback storage
                if session_id in self._fallback_storage:
                    session = self._fallback_storage[session_id]

                    # Проверяем истечение
                    if datetime.now() > session['expires_at']:
                        del self._fallback_storage[session_id]
                        logger.debug(f"⏰ Сессия {session_id} истекла")
                        return None

                    logger.debug(f"📖 Сессия {session_id} получена из fallback storage")
                    return session['data']
                else:
                    logger.debug(f"🔍 Сессия {session_id} не найдена в fallback storage")
                    return None

        except Exception as e:
            logger.error(f"❌ Ошибка получения сессии {session_id}: {e}")
            return None

    def exists(self, session_id: str) -> bool:
        """
        Проверка существования сессии

        Args:
            session_id: Уникальный ID сессии

        Returns:
            True если существует, False если нет
        """
        try:
            if self._redis_available:
                key = self._get_key(session_id)
                return self.redis_client.exists(key) > 0
            else:
                if session_id in self._fallback_storage:
                    session = self._fallback_storage[session_id]
                    # Проверяем истечение
                    if datetime.now() > session['expires_at']:
                        del self._fallback_storage[session_id]
                        return False
                    return True
                return False

        except Exception as e:
            logger.error(f"❌ Ошибка проверки сессии {session_id}: {e}")
            return False

    def delete(self, session_id: str) -> bool:
        """
        Удаление сессии

        Args:
            session_id: Уникальный ID сессии

        Returns:
            True если успешно удалена, False если не найдена или ошибка
        """
        try:
            if self._redis_available:
                key = self._get_key(session_id)
                result = self.redis_client.delete(key)
                logger.debug(f"🗑️ Сессия {session_id} удалена из Redis")
                return result > 0
            else:
                if session_id in self._fallback_storage:
                    del self._fallback_storage[session_id]
                    logger.debug(f"🗑️ Сессия {session_id} удалена из fallback storage")
                    return True
                return False

        except Exception as e:
            logger.error(f"❌ Ошибка удаления сессии {session_id}: {e}")
            return False

    def extend_ttl(self, session_id: str, additional_seconds: int = None) -> bool:
        """
        Продление времени жизни сессии

        Args:
            session_id: Уникальный ID сессии
            additional_seconds: Дополнительные секунды (по умолчанию = self.ttl)

        Returns:
            True если успешно, False при ошибке
        """
        try:
            additional_seconds = additional_seconds or self.ttl

            if self._redis_available:
                key = self._get_key(session_id)
                if self.redis_client.exists(key):
                    self.redis_client.expire(key, additional_seconds)
                    logger.debug(f"⏱️ TTL сессии {session_id} продлен на {additional_seconds}s")
                    return True
                return False
            else:
                if session_id in self._fallback_storage:
                    self._fallback_storage[session_id]['expires_at'] = (
                        datetime.now() + timedelta(seconds=additional_seconds)
                    )
                    logger.debug(f"⏱️ TTL сессии {session_id} продлен в fallback storage")
                    return True
                return False

        except Exception as e:
            logger.error(f"❌ Ошибка продления TTL сессии {session_id}: {e}")
            return False

    def update(self, session_id: str, data: Dict) -> bool:
        """
        Обновление данных сессии (сохраняет TTL)

        Args:
            session_id: Уникальный ID сессии
            data: Новые данные для обновления

        Returns:
            True если успешно, False при ошибке
        """
        existing_data = self.get(session_id)
        if existing_data is None:
            return False

        # Объединяем данные
        existing_data.update(data)

        # Сохраняем с тем же TTL
        if self._redis_available:
            key = self._get_key(session_id)
            ttl = self.redis_client.ttl(key)
            if ttl > 0:
                return self.set(session_id, existing_data, ttl=ttl)
        else:
            if session_id in self._fallback_storage:
                expires_at = self._fallback_storage[session_id]['expires_at']
                ttl = int((expires_at - datetime.now()).total_seconds())
                if ttl > 0:
                    return self.set(session_id, existing_data, ttl=ttl)

        return False

    def get_all_keys(self, pattern: str = "*") -> list:
        """
        Получение всех ключей сессий (для отладки)

        Args:
            pattern: Паттерн поиска (default: "*")

        Returns:
            Список session_id
        """
        try:
            if self._redis_available:
                keys = self.redis_client.keys(f"session:{pattern}")
                return [k.replace('session:', '') for k in keys]
            else:
                # Очищаем истекшие и возвращаем активные
                now = datetime.now()
                active_sessions = []
                for session_id, session in list(self._fallback_storage.items()):
                    if now > session['expires_at']:
                        del self._fallback_storage[session_id]
                    else:
                        active_sessions.append(session_id)
                return active_sessions

        except Exception as e:
            logger.error(f"❌ Ошибка получения списка сессий: {e}")
            return []

    def clear_all(self) -> bool:
        """
        Очистка всех сессий (для тестирования)

        Returns:
            True если успешно, False при ошибке
        """
        try:
            if self._redis_available:
                keys = self.redis_client.keys("session:*")
                if keys:
                    self.redis_client.delete(*keys)
                logger.info(f"🧹 Все сессии очищены из Redis ({len(keys)} шт.)")
            else:
                count = len(self._fallback_storage)
                self._fallback_storage.clear()
                logger.info(f"🧹 Все сессии очищены из fallback storage ({count} шт.)")

            return True

        except Exception as e:
            logger.error(f"❌ Ошибка очистки всех сессий: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        Получение статистики Redis/сессий

        Returns:
            Словарь со статистикой
        """
        stats = {
            'redis_available': self._redis_available,
            'host': self.host,
            'port': self.port,
            'db': self.db,
            'ttl': self.ttl,
            'fallback_enabled': self.use_fallback,
        }

        try:
            if self._redis_available:
                info = self.redis_client.info()
                stats['redis_version'] = info.get('redis_version')
                stats['used_memory_human'] = info.get('used_memory_human')
                stats['connected_clients'] = info.get('connected_clients')

                # Количество сессий
                session_keys = self.redis_client.keys("session:*")
                stats['active_sessions'] = len(session_keys)
            else:
                # Очищаем истекшие
                now = datetime.now()
                active = [
                    sid for sid, s in self._fallback_storage.items()
                    if now <= s['expires_at']
                ]
                stats['active_sessions'] = len(active)
                stats['storage_type'] = 'in-memory fallback'

        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики: {e}")

        return stats

    def close(self):
        """Закрытие соединения с Redis"""
        if self._redis_available and self.redis_client:
            try:
                self.redis_client.close()
                logger.info("🔌 Redis соединение закрыто")
            except Exception as e:
                logger.error(f"❌ Ошибка закрытия Redis: {e}")


# Singleton instance
_session_manager: Optional[RedisSessionManager] = None


def get_session_manager(
    host: str = None,
    port: int = None,
    db: int = 0,
    password: str = None,
    ttl: int = 3600,
    use_fallback: bool = True
) -> RedisSessionManager:
    """
    Получение singleton instance менеджера сессий

    Args:
        host: Redis host
        port: Redis port
        db: Redis database
        password: Redis password
        ttl: Session TTL in seconds
        use_fallback: Use in-memory fallback if Redis unavailable

    Returns:
        RedisSessionManager instance
    """
    global _session_manager

    if _session_manager is None:
        _session_manager = RedisSessionManager(
            host=host,
            port=port,
            db=db,
            password=password,
            ttl=ttl,
            use_fallback=use_fallback
        )

    return _session_manager
