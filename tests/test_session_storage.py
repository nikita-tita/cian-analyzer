"""
Tests for Session Storage with TTL and LRU eviction
"""
import pytest
import time
import threading
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from src.utils.session_storage import SessionStorage, get_session_storage


class TestSessionStorageBasics:
    """Basic functionality tests for SessionStorage"""

    @pytest.fixture
    def storage(self):
        """Create fresh storage instance for each test"""
        return SessionStorage(max_memory_sessions=5, cleanup_interval=1)

    def test_storage_initialization(self, storage):
        """Test storage initializes correctly"""
        assert storage.redis_client is None  # No Redis in tests
        assert len(storage.memory_storage) == 0
        assert storage.max_memory_sessions == 5
        assert storage.cleanup_interval == 1
        assert storage.stats['hits'] == 0
        assert storage.stats['misses'] == 0

    def test_set_and_get(self, storage):
        """Test basic set and get operations"""
        data = {'user': 'test', 'value': 123}
        result = storage.set('test-session', data)

        assert result is True
        assert storage.get('test-session') == data

    def test_get_nonexistent_session(self, storage):
        """Test getting non-existent session returns None"""
        assert storage.get('nonexistent') is None
        assert storage.stats['misses'] == 1

    def test_exists(self, storage):
        """Test exists() method"""
        storage.set('test-session', {'data': 'value'})

        assert storage.exists('test-session') is True
        assert storage.exists('nonexistent') is False

    def test_delete(self, storage):
        """Test deleting sessions"""
        storage.set('test-session', {'data': 'value'})
        assert storage.exists('test-session') is True

        result = storage.delete('test-session')
        assert result is True
        assert storage.exists('test-session') is False

    def test_delete_nonexistent(self, storage):
        """Test deleting non-existent session"""
        result = storage.delete('nonexistent')
        assert result is False

    def test_update(self, storage):
        """Test updating session data"""
        storage.set('test-session', {'counter': 0, 'name': 'test'})

        result = storage.update('test-session', {'counter': 1})
        assert result is True

        data = storage.get('test-session')
        assert data['counter'] == 1
        assert data['name'] == 'test'  # Preserved

    def test_update_nonexistent(self, storage):
        """Test updating non-existent session fails"""
        result = storage.update('nonexistent', {'data': 'value'})
        assert result is False


class TestSessionStorageTTL:
    """Tests for Time-To-Live (TTL) functionality"""

    @pytest.fixture
    def storage(self):
        """Create storage with short TTL for testing"""
        return SessionStorage(max_memory_sessions=10, cleanup_interval=1)

    def test_session_expires_after_ttl(self, storage):
        """Test that sessions expire after TTL"""
        # Set with 1 second TTL
        storage.set('temp-session', {'data': 'value'}, ttl=1)

        # Should exist immediately
        assert storage.exists('temp-session') is True

        # Wait for expiration
        time.sleep(1.1)

        # Should be expired
        assert storage.exists('temp-session') is False
        assert storage.stats['expirations'] >= 1

    def test_default_ttl(self, storage):
        """Test default TTL of 24 hours"""
        storage.set('long-session', {'data': 'value'})  # Default TTL

        # Check expiration time was set
        _, expires_at = storage.memory_storage['long-session']
        expected_expiry = datetime.now() + timedelta(seconds=86400)

        # Should expire approximately 24 hours from now (within 10 seconds tolerance)
        time_diff = abs((expires_at - expected_expiry).total_seconds())
        assert time_diff < 10

    def test_custom_ttl(self, storage):
        """Test custom TTL values"""
        storage.set('short-session', {'data': 'value'}, ttl=2)

        _, expires_at = storage.memory_storage['short-session']
        expected_expiry = datetime.now() + timedelta(seconds=2)

        time_diff = abs((expires_at - expected_expiry).total_seconds())
        assert time_diff < 1

    def test_get_expired_session_returns_none(self, storage):
        """Test that getting expired session returns None"""
        storage.set('temp-session', {'data': 'value'}, ttl=1)

        # Wait for expiration
        time.sleep(1.1)

        result = storage.get('temp-session')
        assert result is None
        assert 'temp-session' not in storage.memory_storage  # Cleaned up


class TestSessionStorageLRU:
    """Tests for LRU (Least Recently Used) eviction"""

    @pytest.fixture
    def storage(self):
        """Create storage with small capacity for testing LRU"""
        return SessionStorage(max_memory_sessions=3, cleanup_interval=10)

    def test_lru_eviction_on_capacity(self, storage):
        """Test that LRU eviction occurs when capacity is reached"""
        # Fill to capacity
        storage.set('session1', {'id': 1})
        storage.set('session2', {'id': 2})
        storage.set('session3', {'id': 3})

        assert len(storage.memory_storage) == 3
        assert storage.stats['evictions'] == 0

        # Add one more - should evict session1 (oldest)
        storage.set('session4', {'id': 4})

        assert len(storage.memory_storage) == 3
        assert storage.stats['evictions'] == 1
        assert storage.exists('session1') is False  # Evicted
        assert storage.exists('session4') is True   # New one

    def test_lru_order_updated_on_get(self, storage):
        """Test that get() updates LRU order"""
        storage.set('session1', {'id': 1})
        storage.set('session2', {'id': 2})
        storage.set('session3', {'id': 3})

        # Access session1 (makes it most recently used)
        storage.get('session1')

        # Add session4 - should evict session2 (now oldest)
        storage.set('session4', {'id': 4})

        assert storage.exists('session1') is True   # Kept (recently accessed)
        assert storage.exists('session2') is False  # Evicted (oldest)
        assert storage.exists('session3') is True
        assert storage.exists('session4') is True

    def test_lru_order_maintained_on_set(self, storage):
        """Test that set() moves item to end (most recent)"""
        storage.set('session1', {'id': 1})
        storage.set('session2', {'id': 2})

        # Update session1
        storage.set('session1', {'id': 1, 'updated': True})

        # Add two more
        storage.set('session3', {'id': 3})
        storage.set('session4', {'id': 4})

        # session2 should be evicted (oldest), session1 kept (updated recently)
        assert storage.exists('session1') is True
        assert storage.exists('session2') is False


class TestSessionStorageCleanup:
    """Tests for automatic cleanup thread"""

    @pytest.fixture
    def storage(self):
        """Create storage with frequent cleanup"""
        return SessionStorage(max_memory_sessions=10, cleanup_interval=1)

    def test_cleanup_thread_starts(self, storage):
        """Test that cleanup thread starts automatically"""
        # Check thread is running
        threads = threading.enumerate()
        thread_names = [t.name for t in threads]
        assert 'SessionCleanup' in thread_names

    def test_cleanup_removes_expired_sessions(self, storage):
        """Test that cleanup thread removes expired sessions"""
        # Add multiple sessions with short TTL
        storage.set('temp1', {'id': 1}, ttl=1)
        storage.set('temp2', {'id': 2}, ttl=1)
        storage.set('permanent', {'id': 3}, ttl=3600)

        assert len(storage.memory_storage) == 3

        # Wait for cleanup to run
        time.sleep(2.5)

        # Expired sessions should be cleaned up
        assert len(storage.memory_storage) == 1
        assert storage.exists('permanent') is True
        assert storage.stats['expirations'] >= 2


class TestSessionStorageStats:
    """Tests for statistics tracking"""

    @pytest.fixture
    def storage(self):
        """Create storage for stats testing"""
        return SessionStorage(max_memory_sessions=5, cleanup_interval=10)

    def test_hit_stats(self, storage):
        """Test that hits are tracked correctly"""
        storage.set('test', {'data': 'value'})

        assert storage.stats['hits'] == 0

        storage.get('test')
        assert storage.stats['hits'] == 1

        storage.get('test')
        assert storage.stats['hits'] == 2

    def test_miss_stats(self, storage):
        """Test that misses are tracked correctly"""
        assert storage.stats['misses'] == 0

        storage.get('nonexistent')
        assert storage.stats['misses'] == 1

        storage.get('another-nonexistent')
        assert storage.stats['misses'] == 2

    def test_eviction_stats(self, storage):
        """Test that evictions are tracked"""
        # Fill to capacity + 1
        for i in range(6):
            storage.set(f'session{i}', {'id': i})

        assert storage.stats['evictions'] == 1

    def test_expiration_stats(self, storage):
        """Test that expirations are tracked"""
        storage.set('temp', {'data': 'value'}, ttl=1)
        time.sleep(1.1)

        # Access to trigger expiration check
        storage.get('temp')

        assert storage.stats['expirations'] >= 1

    def test_get_stats_method(self, storage):
        """Test get_stats() returns correct statistics"""
        storage.set('test1', {'id': 1})
        storage.set('test2', {'id': 2})
        storage.get('test1')  # Hit
        storage.get('nonexistent')  # Miss

        stats = storage.get_stats()

        assert stats['backend'] == 'memory'
        assert stats['total_sessions'] == 2
        assert stats['max_sessions'] == 5
        assert stats['hits'] == 1
        assert stats['misses'] == 1
        assert stats['hit_rate_percent'] == 50.0
        assert 'evictions' in stats
        assert 'expirations' in stats


class TestSessionStorageThreadSafety:
    """Tests for thread-safety"""

    @pytest.fixture
    def storage(self):
        """Create storage for concurrency testing"""
        return SessionStorage(max_memory_sessions=100, cleanup_interval=10)

    def test_concurrent_writes(self, storage):
        """Test concurrent writes don't corrupt data"""
        errors = []

        def write_sessions(start, count):
            try:
                for i in range(start, start + count):
                    storage.set(f'session{i}', {'id': i, 'value': i * 2})
            except Exception as e:
                errors.append(e)

        # Launch 10 threads writing 10 sessions each
        threads = []
        for i in range(10):
            t = threading.Thread(target=write_sessions, args=(i * 10, 10))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # No errors
        assert len(errors) == 0

        # All sessions created
        assert len(storage.memory_storage) == 100

    def test_concurrent_reads_and_writes(self, storage):
        """Test concurrent reads and writes"""
        # Pre-populate
        for i in range(20):
            storage.set(f'session{i}', {'id': i})

        read_results = []
        write_count = [0]
        errors = []

        def reader():
            try:
                for i in range(50):
                    result = storage.get(f'session{i % 20}')
                    read_results.append(result)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        def writer():
            try:
                for i in range(20, 40):
                    storage.set(f'session{i}', {'id': i})
                    write_count[0] += 1
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        # Launch readers and writers
        threads = []
        for _ in range(3):
            threads.append(threading.Thread(target=reader))
        for _ in range(2):
            threads.append(threading.Thread(target=writer))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No errors
        assert len(errors) == 0
        assert write_count[0] == 40


class TestSessionStorageSingleton:
    """Tests for global singleton pattern"""

    def test_get_session_storage_returns_singleton(self):
        """Test that get_session_storage returns same instance"""
        storage1 = get_session_storage()
        storage2 = get_session_storage()

        assert storage1 is storage2

    def test_singleton_persists_data(self):
        """Test that data persists across get_session_storage calls"""
        storage1 = get_session_storage()
        storage1.set('test', {'value': 123})

        storage2 = get_session_storage()
        data = storage2.get('test')

        assert data == {'value': 123}


@pytest.mark.integration
class TestSessionStorageWithRedis:
    """Integration tests with Redis (if available)"""

    @pytest.fixture
    def redis_storage(self):
        """Create storage with Redis if available"""
        with patch.dict('os.environ', {'REDIS_URL': 'redis://localhost:6380/1'}):
            try:
                storage = SessionStorage()
                if storage.redis_client:
                    # Clean up test keys
                    storage.redis_client.flushdb()
                    return storage
                else:
                    pytest.skip("Redis not available")
            except:
                pytest.skip("Redis not available")

    def test_redis_set_and_get(self, redis_storage):
        """Test Redis operations"""
        data = {'user': 'test', 'value': 123}
        redis_storage.set('test-session', data)

        result = redis_storage.get('test-session')
        assert result == data

    def test_redis_ttl(self, redis_storage):
        """Test Redis TTL functionality"""
        redis_storage.set('temp-session', {'data': 'value'}, ttl=2)

        # Should exist
        assert redis_storage.exists('temp-session') is True

        # Wait for expiration
        time.sleep(2.1)

        # Should be expired
        assert redis_storage.exists('temp-session') is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
