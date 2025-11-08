"""
Tests for Browser Pool resource management
"""
import pytest
import time
import threading
from unittest.mock import Mock, patch, MagicMock

# Skip all browser pool tests if Playwright is not available
pytest.importorskip("playwright")

from src.parsers.browser_pool import BrowserPool, BrowserInstance


class TestBrowserInstance:
    """Tests for BrowserInstance dataclass"""

    def test_browser_instance_creation(self):
        """Test creating a browser instance"""
        mock_browser = Mock()
        mock_context = Mock()

        instance = BrowserInstance(
            browser=mock_browser,
            context=mock_context
        )

        assert instance.browser == mock_browser
        assert instance.context == mock_context
        assert instance.in_use is False
        assert instance.use_count == 0
        assert instance.max_uses == 50

    def test_browser_instance_defaults(self):
        """Test default values for BrowserInstance"""
        mock_browser = Mock()
        instance = BrowserInstance(browser=mock_browser)

        assert instance.context is None
        assert instance.in_use is False
        assert instance.use_count == 0
        assert instance.created_at is not None
        assert instance.last_used is not None


@pytest.mark.browser
class TestBrowserPool:
    """Tests for BrowserPool class"""

    @pytest.fixture
    def mock_playwright(self):
        """Mock Playwright for testing without real browsers"""
        with patch('src.parsers.browser_pool.sync_playwright') as mock:
            playwright_instance = MagicMock()
            mock.return_value.start.return_value = playwright_instance

            # Mock browser
            browser_mock = MagicMock()
            playwright_instance.chromium.launch.return_value = browser_mock

            # Mock context
            context_mock = MagicMock()
            browser_mock.new_context.return_value = context_mock

            yield mock

    def test_pool_initialization(self, mock_playwright):
        """Test browser pool initialization"""
        pool = BrowserPool(max_browsers=3, headless=True)

        assert pool.max_browsers == 3
        assert pool.headless is True
        assert pool.playwright is None  # Not started yet
        assert len(pool.browsers) == 0
        assert pool.total_created == 0
        assert pool.total_destroyed == 0

    def test_pool_start(self, mock_playwright):
        """Test starting the browser pool"""
        pool = BrowserPool(max_browsers=2)
        pool.start()

        assert pool.playwright is not None
        mock_playwright.return_value.start.assert_called_once()

    def test_pool_start_idempotent(self, mock_playwright):
        """Test that starting pool multiple times is safe"""
        pool = BrowserPool(max_browsers=2)
        pool.start()
        pool.start()  # Should not crash

        # Should only start once
        assert mock_playwright.return_value.start.call_count == 1

    def test_acquire_creates_browser_on_demand(self, mock_playwright):
        """Test that acquire() creates browser when pool is empty"""
        pool = BrowserPool(max_browsers=2)
        pool.start()

        browser, context = pool.acquire(timeout=5.0)

        assert browser is not None
        assert context is not None
        assert len(pool.browsers) == 1
        assert pool.total_created == 1
        assert pool.total_acquisitions == 1

    def test_acquire_reuses_browser(self, mock_playwright):
        """Test that acquire() reuses released browsers"""
        pool = BrowserPool(max_browsers=2)
        pool.start()

        # First acquisition
        browser1, context1 = pool.acquire()
        assert pool.total_created == 1

        # Release it
        pool.release(browser1)

        # Second acquisition should reuse
        browser2, context2 = pool.acquire()
        assert browser1 == browser2
        assert pool.total_created == 1  # Still 1, not 2

    def test_acquire_respects_max_browsers(self, mock_playwright):
        """Test that pool respects max_browsers limit"""
        pool = BrowserPool(max_browsers=2)
        pool.start()

        # Acquire both browsers
        browser1, _ = pool.acquire()
        browser2, _ = pool.acquire()

        assert len(pool.browsers) == 2
        assert pool.browsers[0].in_use is True
        assert pool.browsers[1].in_use is True

        # Third acquisition should timeout
        with pytest.raises(TimeoutError):
            pool.acquire(timeout=1.0)

    def test_release_marks_browser_free(self, mock_playwright):
        """Test that release() marks browser as free"""
        pool = BrowserPool(max_browsers=2)
        pool.start()

        browser, _ = pool.acquire()
        assert pool.browsers[0].in_use is True

        pool.release(browser)
        assert pool.browsers[0].in_use is False
        assert pool.total_releases == 1

    def test_browser_stale_by_age(self, mock_playwright):
        """Test that browsers are marked stale after max age"""
        pool = BrowserPool(max_browsers=2, max_age_seconds=1)
        pool.start()

        browser, _ = pool.acquire()
        instance = pool.browsers[0]

        # Fresh browser
        assert not pool._is_browser_stale(instance)

        # Wait for it to age
        time.sleep(1.1)
        assert pool._is_browser_stale(instance)

    def test_browser_stale_by_use_count(self, mock_playwright):
        """Test that browsers are marked stale after max uses"""
        pool = BrowserPool(max_browsers=2)
        pool.start()

        browser, _ = pool.acquire()
        instance = pool.browsers[0]
        instance.max_uses = 3

        # Use it multiple times
        instance.use_count = 2
        assert not pool._is_browser_stale(instance)

        instance.use_count = 3
        assert pool._is_browser_stale(instance)

    def test_evict_lru_on_acquire(self, mock_playwright):
        """Test that stale browsers are evicted when acquiring"""
        pool = BrowserPool(max_browsers=2, max_age_seconds=1)
        pool.start()

        # Create and release a browser
        browser1, _ = pool.acquire()
        pool.release(browser1)

        # Wait for it to become stale
        time.sleep(1.1)

        # Acquire again - should evict stale and create new
        browser2, _ = pool.acquire()

        # Should have destroyed the stale one
        assert pool.total_destroyed >= 1

    def test_concurrent_acquisitions(self, mock_playwright):
        """Test thread-safe concurrent browser acquisitions"""
        pool = BrowserPool(max_browsers=5)
        pool.start()

        acquired = []
        errors = []

        def acquire_and_release():
            try:
                browser, context = pool.acquire(timeout=5.0)
                acquired.append(browser)
                time.sleep(0.1)
                pool.release(browser)
            except Exception as e:
                errors.append(e)

        # Launch 10 concurrent threads (pool size is 5)
        threads = [threading.Thread(target=acquire_and_release) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All should succeed
        assert len(errors) == 0
        assert len(acquired) == 10

    def test_get_stats(self, mock_playwright):
        """Test getting pool statistics"""
        pool = BrowserPool(max_browsers=3)
        pool.start()

        # Acquire and release
        browser1, _ = pool.acquire()
        browser2, _ = pool.acquire()
        pool.release(browser1)

        stats = pool.get_stats()

        assert stats['pool_size'] == 2
        assert stats['max_browsers'] == 3
        assert stats['browsers_in_use'] == 1
        assert stats['browsers_free'] == 1
        assert stats['total_created'] == 2
        assert stats['total_acquisitions'] == 2
        assert stats['total_releases'] == 1
        assert len(stats['browsers']) == 2

    def test_shutdown_closes_all_browsers(self, mock_playwright):
        """Test that shutdown closes all browsers"""
        pool = BrowserPool(max_browsers=2)
        pool.start()

        # Create some browsers
        browser1, _ = pool.acquire()
        browser2, _ = pool.acquire()

        assert len(pool.browsers) == 2

        # Shutdown
        pool.shutdown()

        assert len(pool.browsers) == 0
        assert pool.playwright is None
        assert pool.total_destroyed == 2

    def test_context_manager_support(self, mock_playwright):
        """Test using pool as context manager"""
        with BrowserPool(max_browsers=2) as pool:
            assert pool.playwright is not None

            browser, _ = pool.acquire()
            assert browser is not None

        # After context exit, pool should be shut down
        assert pool.playwright is None
        assert len(pool.browsers) == 0


@pytest.mark.integration
class TestBrowserPoolIntegration:
    """Integration tests for browser pool with parser"""

    def test_parser_with_pool(self, mock_playwright):
        """Test PlaywrightParser integration with browser pool"""
        from src.parsers.playwright_parser import PlaywrightParser

        pool = BrowserPool(max_browsers=2)
        pool.start()

        try:
            # Create parser with pool
            with PlaywrightParser(browser_pool=pool, region='spb') as parser:
                assert parser.using_pool is True
                assert parser.browser is not None

            # Browser should be returned to pool
            assert pool.browsers[0].in_use is False

        finally:
            pool.shutdown()

    def test_multiple_parsers_share_pool(self, mock_playwright):
        """Test multiple parsers sharing the same pool"""
        from src.parsers.playwright_parser import PlaywrightParser

        pool = BrowserPool(max_browsers=2)
        pool.start()

        try:
            # First parser
            with PlaywrightParser(browser_pool=pool) as parser1:
                browser1 = parser1.browser
                assert pool.browsers_in_use == 1

            # Browser returned to pool
            assert pool.browsers[0].in_use is False

            # Second parser reuses
            with PlaywrightParser(browser_pool=pool) as parser2:
                browser2 = parser2.browser
                # Should reuse the same browser instance
                assert browser1 == browser2

        finally:
            pool.shutdown()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
