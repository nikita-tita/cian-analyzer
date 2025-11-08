"""
Pytest configuration and fixtures for Housler test suite
"""
import os
import sys
import pytest
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Set test environment variables BEFORE importing app
os.environ['FLASK_ENV'] = 'testing'
os.environ['SECRET_KEY'] = 'test-secret-key-for-testing-only-do-not-use-in-production'
os.environ['REDIS_ENABLED'] = 'false'
os.environ['WTF_CSRF_ENABLED'] = 'false'  # Disable CSRF for testing


@pytest.fixture
def app():
    """Create Flask app for testing"""
    from app_new import app as flask_app

    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False

    return flask_app


@pytest.fixture
def client(app):
    """Create Flask test client"""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create Flask CLI test runner"""
    return app.test_cli_runner()


@pytest.fixture
def sample_property_data():
    """Sample property data for testing"""
    return {
        'url': 'https://spb.cian.ru/sale/flat/123456/',
        'address': 'Санкт-Петербург, Невский проспект, 1',
        'price_raw': 10000000,
        'total_area': 50.0,
        'rooms': '2',
        'floor': '5',
        'total_floors': 10,
        'living_area': 30.0,
        'kitchen_area': 10.0,
        'repair_level': 'современная',
        'view_type': 'двор',
        'residential_complex': 'Тестовый ЖК'
    }


@pytest.fixture
def sample_session_data():
    """Sample session data for testing"""
    return {
        'session_id': 'test-session-123',
        'target_property': {
            'address': 'Тестовый адрес',
            'price_raw': 5000000,
            'total_area': 45.0,
            'rooms': '1'
        },
        'comparables': [],
        'created_at': datetime.now().isoformat()
    }


@pytest.fixture
def mock_playwright_parser(monkeypatch):
    """Mock Playwright parser to avoid browser operations in tests"""
    class MockParser:
        def __init__(self, *args, **kwargs):
            self.headless = kwargs.get('headless', True)
            self.region = kwargs.get('region', 'spb')

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def parse_detail_page(self, url):
            return {
                'url': url,
                'address': 'Мокированный адрес',
                'price_raw': 5000000,
                'total_area': 50.0,
                'rooms': '2',
                'floor': '5/10'
            }

        def search_similar(self, target, limit=10):
            return [
                {
                    'url': f'https://test.com/{i}',
                    'price_raw': 5000000 + i * 100000,
                    'total_area': 50.0 + i,
                    'rooms': '2'
                }
                for i in range(min(limit, 5))
            ]

        def search_similar_in_building(self, target, limit=10):
            return self.search_similar(target, limit)

    return MockParser


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton instances between tests"""
    yield

    # Reset session storage singleton
    from src.utils import session_storage
    session_storage._storage = None

    # Reset browser pool if exists
    try:
        from app_new import browser_pool
        if browser_pool:
            browser_pool.shutdown()
    except:
        pass


@pytest.fixture
def disable_rate_limiting(app):
    """Disable rate limiting for tests"""
    from app_new import limiter
    limiter.enabled = False
    yield
    limiter.enabled = True


# Pytest hooks
def pytest_configure(config):
    """Configure pytest with custom settings"""
    config.addinivalue_line(
        "markers", "unit: Unit tests for individual components"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests"
    )
    config.addinivalue_line(
        "markers", "security: Security tests"
    )
    config.addinivalue_line(
        "markers", "slow: Slow tests"
    )
    config.addinivalue_line(
        "markers", "browser: Tests requiring browser"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection"""
    for item in items:
        # Add 'unit' marker to all tests by default
        if not any(marker.name in ['integration', 'security', 'slow']
                   for marker in item.iter_markers()):
            item.add_marker(pytest.mark.unit)
