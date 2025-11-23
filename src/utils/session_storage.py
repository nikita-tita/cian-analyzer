"""
Session storage wrapper with Redis support
Falls back to in-memory storage if Redis is unavailable

Features:
- TTL (Time To Live) support for both Redis and in-memory
- LRU (Least Recently Used) eviction for in-memory storage
- Automatic cleanup of expired sessions
"""
import os
import json
import logging
import threading
import time
from typing import Dict, Any, Optional
from datetime import datetime, timedelta, date
from collections import OrderedDict

logger = logging.getLogger(__name__)


def serialize_for_json(obj):
    """Convert datetime and other non-JSON-serializable objects to strings"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [serialize_for_json(item) for item in obj]
    return obj


class SessionStorage:
    """Unified session storage interface with TTL and LRU support"""

    def __init__(self, max_memory_sessions: int = 1000, cleanup_interval: int = 300):
        """
        Args:
            max_memory_sessions: Maximum sessions in memory (LRU eviction)
            cleanup_interval: Cleanup expired sessions every N seconds
        """
        self.redis_client = None
        # OrderedDict для LRU: (session_id -> (data, expires_at))
        self.memory_storage: OrderedDict[str, tuple[Dict[str, Any], datetime]] = OrderedDict()
        self.max_memory_sessions = max_memory_sessions
        self.cleanup_interval = cleanup_interval
        self.lock = threading.Lock()  # Thread-safety

        # Метрики
        self.stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'expirations': 0
        }

        self._init_redis()

        # Запускаем фоновую очистку для in-memory storage
        if not self.redis_client:
            self._start_cleanup_thread()

    def _init_redis(self):
        """Try to initialize Redis connection"""
        redis_url = os.getenv('REDIS_URL')

        if not redis_url:
            logger.info("No REDIS_URL found, using in-memory storage with TTL/LRU")
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
            logger.warning("Redis library not installed, using in-memory storage with TTL/LRU")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}. Using in-memory storage with TTL/LRU")
            self.redis_client = None

    def _start_cleanup_thread(self):
        """Start background thread for cleaning up expired sessions"""
        def cleanup_loop():
            while True:
                try:
                    time.sleep(self.cleanup_interval)
                    self._cleanup_expired()
                except Exception as e:
                    logger.error(f"Error in cleanup thread: {e}")

        thread = threading.Thread(target=cleanup_loop, daemon=True, name="SessionCleanup")
        thread.start()
        logger.info(f"Session cleanup thread started (interval: {self.cleanup_interval}s)")

    def _cleanup_expired(self):
        """Remove expired sessions from memory storage"""
        with self.lock:
            now = datetime.now()
            expired_keys = []

            for session_id, (data, expires_at) in self.memory_storage.items():
                if now >= expires_at:
                    expired_keys.append(session_id)

            for key in expired_keys:
                del self.memory_storage[key]
                self.stats['expirations'] += 1

            if expired_keys:
                logger.info(f"Cleaned up {len(expired_keys)} expired sessions")

    def _evict_lru(self):
        """Evict least recently used session if over capacity"""
        if len(self.memory_storage) >= self.max_memory_sessions:
            # popitem(last=False) removes oldest (LRU)
            evicted_key, _ = self.memory_storage.popitem(last=False)
            self.stats['evictions'] += 1
            logger.debug(f"Evicted LRU session: {evicted_key}")

    def set(self, session_id: str, data: Dict[str, Any], ttl: int = 86400) -> bool:
        """
        Store session data

        Args:
            session_id: Session identifier
            data: Session data to store
            ttl: Time to live in seconds (default 24 hours)
        """
        try:
            if self.redis_client:
                # Serialize datetime objects before storing
                serialized_data = serialize_for_json(data)
                # Store in Redis with TTL
                self.redis_client.setex(
                    f"session:{session_id}",
                    ttl,
                    json.dumps(serialized_data, ensure_ascii=False)
                )
                return True
            else:
                # Store in memory with TTL and LRU
                with self.lock:
                    # Evict LRU if needed
                    self._evict_lru()

                    # Calculate expiration time
                    expires_at = datetime.now() + timedelta(seconds=ttl)

                    # Store data with expiration (no need to serialize for memory)
                    self.memory_storage[session_id] = (data, expires_at)

                    # Move to end (most recently used)
                    self.memory_storage.move_to_end(session_id)

                return True
        except Exception as e:
            logger.error(f"Error storing session {session_id}: {e}")
            return False

    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data (checks TTL for in-memory storage)"""
        try:
            if self.redis_client:
                # Get from Redis
                data = self.redis_client.get(f"session:{session_id}")
                if data:
                    self.stats['hits'] += 1
                    return json.loads(data)
                self.stats['misses'] += 1
                return None
            else:
                # Get from memory with TTL check
                with self.lock:
                    if session_id not in self.memory_storage:
                        self.stats['misses'] += 1
                        return None

                    data, expires_at = self.memory_storage[session_id]

                    # Check if expired
                    if datetime.now() >= expires_at:
                        # Expired - remove it
                        del self.memory_storage[session_id]
                        self.stats['expirations'] += 1
                        self.stats['misses'] += 1
                        return None

                    # Update LRU order (move to end)
                    self.memory_storage.move_to_end(session_id)
                    self.stats['hits'] += 1

                    return data
        except Exception as e:
            logger.error(f"Error getting session {session_id}: {e}")
            return None

    def exists(self, session_id: str) -> bool:
        """Check if session exists (respects TTL)"""
        # Use get() which checks TTL
        return self.get(session_id) is not None

    def delete(self, session_id: str) -> bool:
        """Delete session"""
        try:
            if self.redis_client:
                return bool(self.redis_client.delete(f"session:{session_id}"))
            else:
                with self.lock:
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

    def get_stats(self) -> dict:
        """Get storage statistics"""
        with self.lock if not self.redis_client else threading.Lock():
            hit_rate = 0
            if self.stats['hits'] + self.stats['misses'] > 0:
                hit_rate = self.stats['hits'] / (self.stats['hits'] + self.stats['misses']) * 100

            return {
                'backend': 'redis' if self.redis_client else 'memory',
                'total_sessions': len(self.memory_storage) if not self.redis_client else None,
                'max_sessions': self.max_memory_sessions if not self.redis_client else None,
                'hits': self.stats['hits'],
                'misses': self.stats['misses'],
                'hit_rate_percent': round(hit_rate, 2),
                'evictions': self.stats['evictions'],
                'expirations': self.stats['expirations']
            }


# Global session storage instance
_storage = None


def get_session_storage() -> SessionStorage:
    """Get global session storage instance"""
    global _storage
    if _storage is None:
        _storage = SessionStorage()
    return _storage
