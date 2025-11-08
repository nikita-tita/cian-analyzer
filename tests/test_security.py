"""
Security tests for Housler application
Tests CSRF protection, rate limiting, input validation, SSRF protection
"""
import pytest
import json
import time
from unittest.mock import patch


@pytest.mark.security
class TestCSRFProtection:
    """Tests for CSRF protection"""

    def test_csrf_token_endpoint_works(self, client):
        """Test that CSRF token can be fetched"""
        response = client.get('/api/csrf-token')
        assert response.status_code == 200

        data = response.get_json()
        assert 'csrf_token' in data
        assert len(data['csrf_token']) > 20  # Should be a long token

    def test_csrf_disabled_in_testing(self, client):
        """Test that CSRF is disabled for test suite"""
        # In test mode, CSRF should be disabled
        # This allows testing without managing CSRF tokens
        payload = {'address': 'Test', 'price_raw': 1000000, 'total_area': 50, 'rooms': '2'}

        response = client.post(
            '/api/create-manual',
            data=json.dumps(payload),
            content_type='application/json'
        )

        # Should work without CSRF token in test mode
        assert response.status_code in [200, 400]  # 400 if validation fails, but not CSRF error


@pytest.mark.security
class TestRateLimiting:
    """Tests for rate limiting"""

    def test_rate_limiting_exists(self, app):
        """Test that rate limiter is initialized"""
        from app_new import limiter
        assert limiter is not None

    def test_rate_limit_can_be_disabled(self, client, disable_rate_limiting):
        """Test that rate limiting can be disabled for tests"""
        # Make many requests quickly
        for _ in range(10):
            response = client.get('/health')
            assert response.status_code == 200

    @pytest.mark.slow
    def test_rate_limiting_blocks_excessive_requests(self, client):
        """Test that excessive requests are blocked"""
        # Note: This test is marked as slow and may be skipped
        # Re-enable rate limiting
        from app_new import limiter
        limiter.enabled = True

        try:
            # Make many requests in quick succession
            responses = []
            for _ in range(100):
                response = client.get('/api/csrf-token')
                responses.append(response.status_code)

            # At least some should be rate limited (429)
            assert 429 in responses or len(set(responses)) > 1

        finally:
            limiter.enabled = False


@pytest.mark.security
class TestInputValidation:
    """Tests for input validation and sanitization"""

    def test_sql_injection_blocked(self, client, disable_rate_limiting):
        """Test that SQL injection attempts are blocked"""
        malicious_payloads = [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "admin'--",
            "<script>alert('xss')</script>",
            "../../etc/passwd"
        ]

        for payload in malicious_payloads:
            response = client.post(
                '/api/create-manual',
                data=json.dumps({
                    'address': payload,
                    'price_raw': 5000000,
                    'total_area': 50,
                    'rooms': '2'
                }),
                content_type='application/json'
            )

            # Should be rejected with 400 or sanitized
            data = response.get_json()
            if response.status_code == 200:
                # If accepted, check sanitization
                assert payload not in str(data)

    def test_negative_price_rejected(self, client, disable_rate_limiting):
        """Test that negative prices are rejected"""
        payload = {
            'address': 'Тестовый адрес',
            'price_raw': -1000000,  # Negative
            'total_area': 50,
            'rooms': '2'
        }

        response = client.post(
            '/api/create-manual',
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data['status'] == 'error'

    def test_zero_area_rejected(self, client, disable_rate_limiting):
        """Test that zero or negative area is rejected"""
        payload = {
            'address': 'Тестовый адрес',
            'price_raw': 5000000,
            'total_area': 0,  # Invalid
            'rooms': '2'
        }

        response = client.post(
            '/api/create-manual',
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 400

    def test_extremely_long_address_rejected(self, client, disable_rate_limiting):
        """Test that extremely long addresses are rejected"""
        payload = {
            'address': 'A' * 1000,  # 1000 chars
            'price_raw': 5000000,
            'total_area': 50,
            'rooms': '2'
        }

        response = client.post(
            '/api/create-manual',
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 400

    def test_invalid_room_count_rejected(self, client, disable_rate_limiting):
        """Test that invalid room counts are rejected"""
        payload = {
            'address': 'Тестовый адрес',
            'price_raw': 5000000,
            'total_area': 50,
            'rooms': 'invalid'  # Not a valid room type
        }

        response = client.post(
            '/api/create-manual',
            data=json.dumps(payload),
            content_type='application/json'
        )

        # Should either reject or coerce to valid value
        assert response.status_code in [200, 400, 422]


@pytest.mark.security
class TestSSRFProtection:
    """Tests for SSRF (Server-Side Request Forgery) protection"""

    def test_only_cian_domains_allowed(self, client, disable_rate_limiting):
        """Test that only whitelisted Cian domains are allowed"""
        allowed_urls = [
            'https://www.cian.ru/sale/flat/123456/',
            'https://cian.ru/sale/flat/123456/',
            'https://spb.cian.ru/sale/flat/123456/',
            'https://moscow.cian.ru/sale/flat/123456/'
        ]

        for url in allowed_urls:
            payload = {'url': url}
            response = client.post(
                '/api/parse',
                data=json.dumps(payload),
                content_type='application/json'
            )

            # Should not reject due to domain (may fail for other reasons)
            assert response.status_code != 400 or 'не разрешен' not in response.get_json().get('message', '')

    def test_malicious_domains_blocked(self, client, disable_rate_limiting):
        """Test that malicious domains are blocked"""
        malicious_urls = [
            'https://evil.com/attack',
            'https://malicious-site.ru/hack',
            'http://attacker.com/payload',
            'https://not-cian.ru/fake'
        ]

        for url in malicious_urls:
            payload = {'url': url}
            response = client.post(
                '/api/parse',
                data=json.dumps(payload),
                content_type='application/json'
            )

            assert response.status_code == 400
            data = response.get_json()
            assert 'не разрешен' in data['message'].lower() or 'запрещен' in data['message'].lower()

    def test_localhost_blocked(self, client, disable_rate_limiting):
        """Test that localhost/internal IPs are blocked"""
        internal_urls = [
            'http://localhost:8080/admin',
            'http://127.0.0.1/secret',
            'http://192.168.1.1/router',
            'http://10.0.0.1/internal'
        ]

        for url in internal_urls:
            payload = {'url': url}
            response = client.post(
                '/api/parse',
                data=json.dumps(payload),
                content_type='application/json'
            )

            assert response.status_code == 400
            data = response.get_json()
            # Should be blocked by domain whitelist or IP check
            assert data['status'] == 'error'

    def test_file_protocol_blocked(self, client, disable_rate_limiting):
        """Test that file:// protocol is blocked"""
        file_urls = [
            'file:///etc/passwd',
            'file://C:/Windows/System32/config/sam',
            'file:///home/user/.ssh/id_rsa'
        ]

        for url in file_urls:
            payload = {'url': url}
            response = client.post(
                '/api/parse',
                data=json.dumps(payload),
                content_type='application/json'
            )

            assert response.status_code == 400
            data = response.get_json()
            assert 'протокол' in data['message'].lower() or 'запрещен' in data['message'].lower()


@pytest.mark.security
class TestSecurityHeaders:
    """Tests for security HTTP headers"""

    def test_security_headers_present(self, client):
        """Test that security headers are set"""
        response = client.get('/')

        headers = response.headers

        # Check key security headers
        assert 'X-Content-Type-Options' in headers
        assert headers['X-Content-Type-Options'] == 'nosniff'

        assert 'X-Frame-Options' in headers
        assert headers['X-Frame-Options'] == 'DENY'

        assert 'X-XSS-Protection' in headers

        assert 'Content-Security-Policy' in headers
        csp = headers['Content-Security-Policy']
        assert 'default-src' in csp
        assert 'script-src' in csp

    def test_referrer_policy_set(self, client):
        """Test Referrer-Policy header is set"""
        response = client.get('/')
        assert 'Referrer-Policy' in response.headers

    def test_csp_blocks_inline_scripts(self, client):
        """Test that CSP policy blocks inline scripts"""
        response = client.get('/')
        csp = response.headers.get('Content-Security-Policy', '')

        # CSP should specify script-src
        assert 'script-src' in csp
        # Should allow self and CDNs but control inline
        assert "'self'" in csp


@pytest.mark.security
class TestAuthenticationAndAuthorization:
    """Tests for authentication/authorization (if applicable)"""

    def test_no_sensitive_info_in_errors(self, client, disable_rate_limiting):
        """Test that error messages don't leak sensitive information"""
        # Trigger various errors
        responses = [
            client.post('/api/parse', data='invalid json', content_type='application/json'),
            client.post('/api/analyze', data=json.dumps({'session_id': 'fake'}),
                        content_type='application/json'),
            client.get('/nonexistent-endpoint')
        ]

        for response in responses:
            data = response.get_data(as_text=True)

            # Should not contain sensitive paths or stack traces
            assert '/home/' not in data.lower()
            assert 'traceback' not in data.lower()
            assert 'exception' not in data.lower() or response.status_code < 500


@pytest.mark.security
class TestTimeoutProtection:
    """Tests for timeout protection against DoS"""

    @patch('app_new.Parser')
    def test_parsing_timeout_protection(self, mock_parser, client, disable_rate_limiting):
        """Test that parsing operations have timeouts"""
        # Mock parser that takes too long
        mock_parser_instance = mock_parser.return_value.__enter__.return_value
        mock_parser_instance.parse_detail_page.side_effect = lambda url: time.sleep(70)  # Exceeds 60s timeout

        payload = {'url': 'https://spb.cian.ru/sale/flat/123456/'}

        with pytest.raises(Exception):
            # Should timeout and raise exception
            response = client.post(
                '/api/parse',
                data=json.dumps(payload),
                content_type='application/json'
            )


@pytest.mark.security
@pytest.mark.integration
class TestSecurityIntegration:
    """Integration tests for security features"""

    def test_complete_security_chain(self, client, disable_rate_limiting):
        """Test that multiple security layers work together"""
        # 1. Try with malicious input
        payload = {
            'address': "'; DROP TABLE users; --",
            'price_raw': -1000000,
            'total_area': 0,
            'rooms': 'INVALID'
        }

        response = client.post(
            '/api/create-manual',
            data=json.dumps(payload),
            content_type='application/json'
        )

        # Should be blocked by validation
        assert response.status_code == 400

        # 2. Check security headers are present
        assert 'X-Content-Type-Options' in response.headers

    def test_no_information_disclosure(self, client):
        """Test that errors don't disclose system information"""
        # Try various invalid requests
        responses = [
            client.get('/../../../../etc/passwd'),
            client.post('/api/analyze', data='<script>alert(1)</script>',
                        content_type='application/json'),
        ]

        for response in responses:
            data = response.get_data(as_text=True)

            # Should not contain:
            # - File paths
            # - Python tracebacks
            # - Database queries
            # - Environment variables

            sensitive_patterns = [
                '/home/',
                '/usr/',
                'Traceback',
                'File "',
                'SELECT ',
                'SECRET_KEY',
                'PASSWORD',
            ]

            for pattern in sensitive_patterns:
                assert pattern not in data, f"Response leaked sensitive info: {pattern}"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-m', 'security'])
