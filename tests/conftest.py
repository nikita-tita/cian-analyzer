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
    # Mock PLAYWRIGHT_AVAILABLE to use markdown fallback in tests
    # This prevents ERR_CONNECTION_REFUSED errors in PDF generation
    import app_new
    app_new.PLAYWRIGHT_AVAILABLE = False

    flask_app = app_new.app
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
    class MockBrowser:
        """Mock browser object"""
        pass

    class MockParser:
        def __init__(self, *args, **kwargs):
            self.headless = kwargs.get('headless', True)
            self.region = kwargs.get('region', 'spb')
            self.browser_pool = kwargs.get('browser_pool', None)
            self.using_pool = self.browser_pool is not None
            self.browser = MockBrowser()

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
    # Clean up BEFORE test to ensure fresh state
    from src.utils import session_storage
    import app_new

    # Reset session storage singleton
    session_storage._storage = None

    # Force app to use new session storage instance
    app_new.session_storage = session_storage.get_session_storage()

    yield

    # Also clean up AFTER test
    session_storage._storage = None
    app_new.session_storage = session_storage.get_session_storage()

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


@pytest.fixture
def mock_session_with_analysis(app):
    """Create a mock session with completed analysis for testing report export"""
    from src.utils.session_storage import get_session_storage

    session_storage = get_session_storage()
    session_id = 'test-session-with-analysis'

    session_data = {
        'target_property': {
            'url': 'https://spb.cian.ru/sale/flat/123456/',
            'address': 'Санкт-Петербург, Невский проспект, 1',
            'price': 10000000,
            'total_area': 50.0,
            'rooms': 2,
            'floor': 5,
            'total_floors': 10,
        },
        'comparables': [
            {
                'price': 9500000,
                'total_area': 48.0,
                'price_per_sqm': 197916.67,
                'address': 'Аналог 1',
                'url': 'https://spb.cian.ru/sale/flat/111/',
                'excluded': False
            },
            {
                'price': 10500000,
                'total_area': 52.0,
                'price_per_sqm': 201923.08,
                'address': 'Аналог 2',
                'url': 'https://spb.cian.ru/sale/flat/222/',
                'excluded': False
            },
        ],
        'analysis': {
            'market_statistics': {
                'median_price_per_sqm': 200000,
                'mean_price_per_sqm': 199919.88,
                'count': 2
            },
            'fair_price_analysis': {
                'fair_price_total': 9800000,
                'fair_price_per_sqm': 196000,
                'current_price': 10000000,
                'price_diff_percent': 2.0,
                'is_overpriced': True,
                'is_fair': False,
                'is_underpriced': False
            },
            'price_range': {
                'min_price': 9000000,
                'fair_price': 9800000,
                'recommended_listing': 10200000,
                'max_price': 11000000,
            },
            'attractiveness_index': {
                'total_index': 75,
                'category': 'Хорошая привлекательность',
                'category_emoji': '👍',
                'category_description': 'Объект имеет хорошую привлекательность',
            },
            'time_forecast': {
                'expected_time_months': 3.5,
                'time_range_description': '2-5 месяцев',
            },
            'price_sensitivity': [],
            'price_scenarios': [
                {
                    'name': 'Быстрая продажа',
                    'start_price': 9500000,
                    'expected_final_price': 9300000,
                    'time_months': 2
                }
            ],
            'metrics': {
                'calculation_time_ms': 123
            }
        }
    }

    session_storage.set(session_id, session_data)

    yield {'session_id': session_id, 'data': session_data}

    # Cleanup
    session_storage.delete(session_id)


@pytest.fixture
def mock_session_without_analysis(app):
    """Create a mock session without analysis for testing error cases"""
    from src.utils.session_storage import get_session_storage

    session_storage = get_session_storage()
    session_id = 'test-session-without-analysis'

    session_data = {
        'target_property': {
            'address': 'Тестовый адрес',
            'price': 5000000,
            'total_area': 45.0,
        },
        'comparables': []
    }

    session_storage.set(session_id, session_data)

    yield {'session_id': session_id, 'data': session_data}

    # Cleanup
    session_storage.delete(session_id)


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
