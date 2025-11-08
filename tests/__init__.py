"""
Housler Test Suite

Test organization:
- test_browser_pool.py: Browser pool resource management tests
- test_session_storage.py: Session storage TTL/LRU tests
- test_api.py: API endpoint tests
- test_security.py: Security tests (CSRF, rate limiting, validation, SSRF)

Run tests:
    pytest                    # Run all tests
    pytest -v                 # Verbose output
    pytest -m unit            # Run only unit tests
    pytest -m security        # Run only security tests
    pytest -m "not slow"      # Skip slow tests
    pytest --cov              # With coverage report

Test markers:
    @pytest.mark.unit         - Unit tests
    @pytest.mark.integration  - Integration tests
    @pytest.mark.security     - Security tests
    @pytest.mark.slow         - Slow tests (>1s)
    @pytest.mark.browser      - Tests requiring browser
"""

__version__ = '1.0.0'
