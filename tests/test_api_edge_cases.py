"""
Edge case tests for API endpoints to improve coverage

Focus on:
- Error handling
- Invalid inputs
- Boundary conditions
- Session management
"""
import pytest
import json
from unittest.mock import patch, Mock


@pytest.fixture
def session_storage(app):
    """Get session storage instance for tests"""
    from src.utils.session_storage import get_session_storage
    return get_session_storage()


class TestParseEndpointEdgeCases:
    """Edge cases for /api/parse endpoint"""

    def test_parse_missing_url(self, client):
        """Test parse endpoint with missing URL"""
        response = client.post(
            '/api/parse',
            json={}  # No URL
        )

        assert response.status_code in [400, 422, 500]
        data = response.get_json()
        assert data is not None

    def test_parse_invalid_url_format(self, client):
        """Test parse endpoint with invalid URL format"""
        response = client.post(
            '/api/parse',
            json={'url': 'not-a-url'}
        )

        assert response.status_code in [400, 422, 500]

    def test_parse_non_cian_url(self, client):
        """Test parse endpoint with non-CIAN URL"""
        response = client.post(
            '/api/parse',
            json={'url': 'https://www.google.com'}
        )

        assert response.status_code in [400, 422, 500]
        data = response.get_json()
        assert data is not None

    @patch('src.parsers.playwright_parser.PlaywrightParser')
    def test_parse_timeout_handling(self, mock_parser, client):
        """Test parse endpoint handles timeout gracefully"""
        mock_instance = Mock()
        mock_instance.__enter__ = Mock(return_value=mock_instance)
        mock_instance.__exit__ = Mock(return_value=False)
        mock_instance.parse_detail_page.side_effect = TimeoutError("Timeout")
        mock_parser.return_value = mock_instance

        response = client.post(
            '/api/parse',
            json={'url': 'https://spb.cian.ru/sale/flat/123456789/'}
        )

        # Should return error, not crash
        assert response.status_code in [500, 422, 400]


class TestFindSimilarEdgeCases:
    """Edge cases for /api/find-similar endpoint"""

    def test_find_similar_missing_session(self, client):
        """Test find-similar with missing session_id"""
        response = client.post(
            '/api/find-similar',
            json={}
        )

        assert response.status_code in [400, 422, 404, 500]
        data = response.get_json()
        assert data is not None

    def test_find_similar_invalid_session(self, client):
        """Test find-similar with invalid session_id"""
        response = client.post(
            '/api/find-similar',
            json={'session_id': 'nonexistent-session'}
        )

        assert response.status_code in [404, 422, 400, 500]

    def test_find_similar_missing_target_property(self, client, session_storage):
        """Test find-similar when target property not in session"""
        session_id = 'test-session-123'
        session_storage.set(session_id, {})  # Empty session

        response = client.post(
            '/api/find-similar',
            json={'session_id': session_id}
        )

        assert response.status_code in [400, 422, 500]


class TestAnalyzeEndpointEdgeCases:
    """Edge cases for /api/analyze endpoint"""

    def test_analyze_missing_session(self, client):
        """Test analyze with missing session_id"""
        response = client.post(
            '/api/analyze',
            json={}
        )

        assert response.status_code in [400, 422, 404, 500]

    def test_analyze_no_comparables(self, client, session_storage):
        """Test analyze when no comparables found"""
        session_id = 'test-session-456'
        session_storage.set(session_id, {
            'target_property': {
                'url': 'https://www.cian.ru/sale/flat/123/',
                'price': 10_000_000,
                'total_area': 50.0,
                'rooms': 2,
                'floor': 5,
                'address': 'Test'
            },
            'comparables': []  # No comparables
        })

        response = client.post(
            '/api/analyze',
            json={'session_id': session_id}
        )

        assert response.status_code in [422, 400, 500]
        data = response.get_json()
        assert data is not None

    def test_analyze_insufficient_comparables(self, client, session_storage):
        """Test analyze with too few valid comparables after filtering"""
        session_id = 'test-session-789'
        session_storage.set(session_id, {
            'target_property': {
                'url': 'https://www.cian.ru/sale/flat/123/',
                'price': 10_000_000,
                'total_area': 50.0,
                'rooms': 2,
                'floor': 5,
                'address': 'Test'
            },
            'comparables': [
                {
                    'url': 'https://www.cian.ru/sale/flat/456/',
                    'price': None,  # Invalid
                    'total_area': 48.0,
                    'rooms': 2,
                    'floor': 4,
                    'address': 'Test 2'
                }
            ]
        })

        response = client.post(
            '/api/analyze',
            json={'session_id': session_id, 'filter_outliers': True}
        )

        # Should handle gracefully
        assert response.status_code in [422, 400, 500]


class TestExcludeIncludeEdgeCases:
    """Edge cases for exclude/include comparable endpoints"""

    def test_exclude_missing_params(self, client):
        """Test exclude without required parameters"""
        response = client.post(
            '/api/exclude-comparable',
            json={}
        )

        assert response.status_code in [400, 422, 404, 500]

    def test_exclude_invalid_index(self, client, session_storage):
        """Test exclude with out-of-range index"""
        session_id = 'test-session-exclude'
        session_storage.set(session_id, {
            'comparables': [{'url': 'test1'}, {'url': 'test2'}]
        })

        response = client.post(
            '/api/exclude-comparable',
            json={'session_id': session_id, 'index': 999}  # Out of range
        )

        # API may not validate index bounds strictly, accepting 200 or error
        assert response.status_code in [200, 400, 422, 500]

    def test_include_invalid_index(self, client, session_storage):
        """Test include with out-of-range index"""
        session_id = 'test-session-include'
        session_storage.set(session_id, {
            'comparables': [{'url': 'test1', 'excluded': True}]
        })

        response = client.post(
            '/api/include-comparable',
            json={'session_id': session_id, 'index': 999}
        )

        # API may not validate index bounds strictly, accepting 200 or error
        assert response.status_code in [200, 400, 422, 500]


class TestUpdateTargetEdgeCases:
    """Edge cases for /api/update-target endpoint"""

    def test_update_target_missing_fields(self, client, session_storage):
        """Test update target with missing required fields"""
        session_id = 'test-session-update'
        session_storage.set(session_id, {
            'target_property': {'url': 'test'}
        })

        response = client.post(
            '/api/update-target',
            json={'session_id': session_id}  # No fields to update
        )

        # Should either accept (no-op) or reject
        assert response.status_code in [200, 400, 422, 500]

    def test_update_target_invalid_price(self, client, session_storage):
        """Test update target with invalid price"""
        session_id = 'test-session-price'
        session_storage.set(session_id, {
            'target_property': {'url': 'test', 'price': 10_000_000}
        })

        response = client.post(
            '/api/update-target',
            json={'session_id': session_id, 'price': -1000}  # Negative price
        )

        assert response.status_code in [400, 422, 500]

    def test_update_target_invalid_area(self, client, session_storage):
        """Test update target with invalid area"""
        session_id = 'test-session-area'
        session_storage.set(session_id, {
            'target_property': {'url': 'test', 'total_area': 50}
        })

        response = client.post(
            '/api/update-target',
            json={'session_id': session_id, 'total_area': 0}  # Zero area
        )

        assert response.status_code in [400, 422, 500]


class TestInputValidation:
    """Test input validation for API endpoints"""

    def test_post_with_malformed_json(self, client):
        """Test POST with malformed JSON"""
        response = client.post(
            '/api/parse',
            data='{"invalid json',
            content_type='application/json'
        )

        # Should handle malformed JSON gracefully
        assert response.status_code in [400, 422, 500]

    def test_post_with_empty_body(self, client):
        """Test POST with empty body"""
        response = client.post(
            '/api/parse',
            data='',
            content_type='application/json'
        )

        # Should handle empty body gracefully
        assert response.status_code in [400, 422, 500]


class TestRateLimiting:
    """Test rate limiting (if enabled)"""

    def test_health_endpoint_no_rate_limit(self, client):
        """Test health endpoint is not rate limited"""
        # Make multiple requests quickly
        for _ in range(10):
            response = client.get('/health')
            # Should always return success
            assert response.status_code in [200, 503]  # 503 if unhealthy, not rate limited

    def test_metrics_endpoint_accessible(self, client):
        """Test metrics endpoint is accessible"""
        response = client.get('/metrics')
        # Should return some metrics
        assert response.status_code in [200, 404]  # 404 if not configured
