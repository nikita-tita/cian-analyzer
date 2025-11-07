"""
Session storage wrapper with Redis support
Falls back to in-memory storage if Redis is unavailable
"""
import os
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class SessionStorage:
    """Unified session storage interface"""

    def __init__(self):
        self.redis_client = None
        self.memory_storage = {}
        self._init_redis()

    def _init_redis(self):
        """Try to initialize Redis connection"""
        redis_url = os.getenv('REDIS_URL')

        if not redis_url:
            logger.info("No REDIS_URL found, using in-memory storage")
            return

        try:
            import redis
            self.redis_client = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=5
            )
            # Test connection
            self.redis_client.ping()
            logger.info("✅ Connected to Redis successfully")
        except ImportError:
            logger.warning("Redis library not installed, using in-memory storage")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}. Using in-memory storage")
            self.redis_client = None

    def set(self, session_id: str, data: Dict[str, Any], ttl: int = 3600) -> bool:
        """
        Store session data

        Args:
            session_id: Session identifier
            data: Session data to store
            ttl: Time to live in seconds (default 1 hour)
        """
        try:
            if self.redis_client:
                # Store in Redis
                self.redis_client.setex(
                    f"session:{session_id}",
                    ttl,
                    json.dumps(data, ensure_ascii=False)
                )
                return True
            else:
                # Store in memory
                self.memory_storage[session_id] = data
                return True
        except Exception as e:
            logger.error(f"Error storing session {session_id}: {e}")
            return False

    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data"""
        try:
            if self.redis_client:
                # Get from Redis
                data = self.redis_client.get(f"session:{session_id}")
                if data:
                    return json.loads(data)
                return None
            else:
                # Get from memory
                return self.memory_storage.get(session_id)
        except Exception as e:
            logger.error(f"Error getting session {session_id}: {e}")
            return None

    def exists(self, session_id: str) -> bool:
        """Check if session exists"""
        try:
            if self.redis_client:
                return bool(self.redis_client.exists(f"session:{session_id}"))
            else:
                return session_id in self.memory_storage
        except Exception as e:
            logger.error(f"Error checking session {session_id}: {e}")
            return False

    def delete(self, session_id: str) -> bool:
        """Delete session"""
        try:
            if self.redis_client:
                return bool(self.redis_client.delete(f"session:{session_id}"))
            else:
                if session_id in self.memory_storage:
                    del self.memory_storage[session_id]
                    return True
                return False
        except Exception as e:
            logger.error(f"Error deleting session {session_id}: {e}")
            return False

    def update(self, session_id: str, updates: Dict[str, Any]) -> bool:
        """Update session data"""
        try:
            data = self.get(session_id)
            if data is None:
                return False

            data.update(updates)
            return self.set(session_id, data)
        except Exception as e:
            logger.error(f"Error updating session {session_id}: {e}")
            return False


# Global session storage instance
_storage = None

def get_session_storage() -> SessionStorage:
    """Get global session storage instance"""
    global _storage
    if _storage is None:
        _storage = SessionStorage()
    return _storage
