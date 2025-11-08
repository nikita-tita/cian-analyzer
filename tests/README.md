# Housler Test Suite

Comprehensive test suite for the Housler real estate analysis application.

## 📁 Test Structure

```
tests/
├── __init__.py                   # Test package initialization
├── conftest.py                   # Pytest configuration and fixtures
├── test_browser_pool.py         # Browser pool resource management (85 tests)
├── test_session_storage.py      # Session storage TTL/LRU (65 tests)
├── test_api.py                  # API endpoint tests (45 tests)
└── test_security.py             # Security tests (35 tests)
```

**Total: ~230 tests**

## 🚀 Running Tests

### Basic Usage

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run with coverage report
pytest --cov

# Run specific test file
pytest tests/test_security.py
```

### By Marker

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run only security tests
pytest -m security

# Skip slow tests
pytest -m "not slow"

# Run browser-related tests
pytest -m browser
```

### Coverage Reports

```bash
# Generate HTML coverage report
pytest --cov --cov-report=html

# View report
open htmlcov/index.html

# Terminal coverage report
pytest --cov --cov-report=term-missing
```

## 📊 Test Categories

### Unit Tests (`@pytest.mark.unit`)
- Browser Pool initialization and lifecycle
- Session Storage set/get/delete operations
- Input validation
- LRU eviction logic
- TTL expiration

### Integration Tests (`@pytest.mark.integration`)
- Full API workflow (create → find similar → analyze)
- Parser with Browser Pool
- Multiple parsers sharing pool
- Session storage with Redis

### Security Tests (`@pytest.mark.security`)
- CSRF protection
- Rate limiting
- Input validation (SQL injection, XSS)
- SSRF protection (domain whitelist, localhost blocking)
- Security headers (CSP, X-Frame-Options, etc.)
- Timeout protection

### Slow Tests (`@pytest.mark.slow`)
- Tests that take >1 second
- Rate limiting stress tests
- Long-running integration tests

## 🔧 Test Configuration

### pytest.ini
```ini
[pytest]
testpaths = tests
addopts = -v --tb=short --cov=src --cov=app_new --cov-fail-under=70
```

### Environment Variables
Tests automatically set:
- `FLASK_ENV=testing`
- `SECRET_KEY=test-secret-key-for-testing-only`
- `REDIS_ENABLED=false`
- `WTF_CSRF_ENABLED=false`

## 📝 Writing New Tests

### Example Test

```python
import pytest

class TestMyFeature:
    """Tests for my new feature"""

    @pytest.mark.unit
    def test_basic_functionality(self, client):
        """Test basic functionality"""
        response = client.get('/my-endpoint')
        assert response.status_code == 200

    @pytest.mark.security
    def test_input_validation(self, client):
        """Test input is validated"""
        malicious_input = "'; DROP TABLE users; --"
        response = client.post('/api/endpoint', json={'input': malicious_input})
        assert response.status_code == 400
```

### Available Fixtures

- `app`: Flask application instance
- `client`: Flask test client
- `runner`: Flask CLI test runner
- `sample_property_data`: Mock property data
- `sample_session_data`: Mock session data
- `mock_playwright_parser`: Mocked parser (no real browser)
- `disable_rate_limiting`: Disable rate limits for testing

## 📈 Coverage Goals

| Component | Current | Target |
|-----------|---------|--------|
| Overall | - | 70%+ |
| Browser Pool | - | 90%+ |
| Session Storage | - | 85%+ |
| API Endpoints | - | 80%+ |
| Security | - | 95%+ |

## 🐛 Debugging Tests

### Run specific test
```bash
pytest tests/test_api.py::TestHealthEndpoint::test_health_check_success -v
```

### Show print statements
```bash
pytest -v -s
```

### Drop into debugger on failure
```bash
pytest --pdb
```

### Show local variables on failure
```bash
pytest --tb=long
```

## 🔐 Security Test Coverage

Security tests verify protection against:

- **CSRF**: Cross-Site Request Forgery token validation
- **XSS**: Input sanitization and CSP headers
- **SQL Injection**: Dangerous SQL patterns blocked
- **SSRF**: Server-Side Request Forgery via URL whitelist
- **DoS**: Rate limiting and timeout protection
- **Information Disclosure**: Error messages sanitized

## 📚 Test Data

Test fixtures provide realistic data:
- Property addresses with Cyrillic characters
- Valid price ranges (1M - 100M RUB)
- Standard Moscow/SPb layouts (1-4 rooms)
- Common repair levels and view types

## 🤝 Contributing

When adding new features:

1. Write tests **before** implementation (TDD)
2. Aim for 80%+ coverage on new code
3. Add security tests for user inputs
4. Use appropriate markers (`@pytest.mark.unit`, etc.)
5. Mock external services (Playwright, Redis)

## 🏃 CI/CD Integration

Tests are designed to run in CI/CD pipelines:

```yaml
# Example GitHub Actions
- name: Run tests
  run: |
    pip install -r requirements.txt
    pytest --cov --cov-fail-under=70
```

## 📞 Troubleshooting

### "Redis not available" warnings
- Expected in test environment
- Tests automatically fall back to in-memory storage

### "Playwright not installed" errors
- Install: `playwright install chromium`
- Or skip browser tests: `pytest -m "not browser"`

### ImportError for app_new
- Run from project root: `pytest` (not `cd tests && pytest`)

### Coverage too low
- Check which files need tests: `pytest --cov --cov-report=term-missing`
- Focus on untested modules
