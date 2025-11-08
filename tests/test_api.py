"""
Tests for API endpoints
"""
import pytest
import json
from unittest.mock import patch, Mock


class TestHealthEndpoint:
    """Tests for /health endpoint"""

    def test_health_check_success(self, client):
        """Test health check returns 200 when healthy"""
        response = client.get('/health')

        assert response.status_code == 200
        data = response.get_json()

        assert data['status'] in ['healthy', 'degraded']
        assert 'timestamp' in data
        assert 'version' in data
        assert 'components' in data

    def test_health_check_components(self, client):
        """Test health check includes all components"""
        response = client.get('/health')
        data = response.get_json()

        components = data['components']
        assert 'redis_cache' in components
        assert 'session_storage' in components
        assert 'parser' in components

    def test_health_check_session_storage_details(self, client):
        """Test health check includes session storage stats"""
        response = client.get('/health')
        data = response.get_json()

        session_storage = data['components']['session_storage']
        assert 'backend' in session_storage
        assert 'total_sessions' in session_storage or session_storage['backend'] == 'redis'
        assert 'hit_rate_percent' in session_storage


class TestMetricsEndpoint:
    """Tests for /metrics endpoint"""

    def test_metrics_endpoint_exists(self, client):
        """Test metrics endpoint is accessible"""
        response = client.get('/metrics')

        assert response.status_code == 200
        assert response.content_type == 'text/plain; charset=utf-8'

    def test_metrics_format(self, client):
        """Test metrics are in Prometheus format"""
        response = client.get('/metrics')
        data = response.get_data(as_text=True)

        # Should contain Prometheus-style metrics
        assert 'housler_up' in data
        assert '# HELP' in data
        assert '# TYPE' in data


class TestCSRFTokenEndpoint:
    """Tests for /api/csrf-token endpoint"""

    def test_csrf_token_generation(self, client):
        """Test CSRF token can be generated"""
        response = client.get('/api/csrf-token')

        assert response.status_code == 200
        data = response.get_json()

        assert 'csrf_token' in data
        assert isinstance(data['csrf_token'], str)
        assert len(data['csrf_token']) > 0


class TestCreateManualEndpoint:
    """Tests for /api/create-manual endpoint"""

    def test_create_manual_property_success(self, client, disable_rate_limiting):
        """Test creating property manually"""
        payload = {
            'address': 'Тестовый адрес, д. 1',
            'price_raw': 5000000,
            'total_area': 45.5,
            'rooms': '2',
            'floor': '5',
            'living_area': 30.0,
            'kitchen_area': 10.0,
            'repair_level': 'современная',
            'view_type': 'двор'
        }

        response = client.post(
            '/api/create-manual',
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()

        assert data['status'] == 'success'
        assert 'session_id' in data
        assert 'data' in data
        assert data['data']['address'] == payload['address']
        assert data['data']['price_raw'] == payload['price_raw']

    def test_create_manual_validation_error(self, client, disable_rate_limiting):
        """Test validation catches invalid data"""
        payload = {
            'address': 'Test',  # Too short (min 5 chars)
            'price_raw': -1000,  # Negative price
            'total_area': 0,  # Invalid area
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

    def test_create_manual_missing_fields(self, client, disable_rate_limiting):
        """Test error when required fields are missing"""
        payload = {
            'address': 'Тестовый адрес',
            # Missing price_raw, total_area, rooms
        }

        response = client.post(
            '/api/create-manual',
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code in [400, 422]


class TestParseEndpoint:
    """Tests for /api/parse endpoint"""

    @patch('app_new.Parser')
    def test_parse_url_success(self, mock_parser, client, disable_rate_limiting):
        """Test parsing URL successfully"""
        # Mock parser
        mock_parser_instance = Mock()
        mock_parser_instance.__enter__ = Mock(return_value=mock_parser_instance)
        mock_parser_instance.__exit__ = Mock(return_value=None)
        mock_parser_instance.parse_detail_page = Mock(return_value={
            'url': 'https://spb.cian.ru/sale/flat/123456/',
            'address': 'Мокированный адрес',
            'price_raw': 5000000,
            'total_area': 50.0,
            'rooms': '2',
            'floor': '5/10'
        })
        mock_parser.return_value = mock_parser_instance

        payload = {'url': 'https://spb.cian.ru/sale/flat/123456/'}

        response = client.post(
            '/api/parse',
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()

        assert data['status'] == 'success'
        assert 'session_id' in data
        assert 'data' in data

    def test_parse_invalid_url(self, client, disable_rate_limiting):
        """Test parsing with invalid URL fails"""
        payload = {'url': 'https://malicious-site.com/attack'}

        response = client.post(
            '/api/parse',
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data['status'] == 'error'
        assert 'не разрешен' in data['message'].lower() or 'запрещен' in data['message'].lower()

    def test_parse_missing_url(self, client, disable_rate_limiting):
        """Test error when URL is missing"""
        payload = {}

        response = client.post(
            '/api/parse',
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 400


class TestUpdateTargetEndpoint:
    """Tests for /api/update-target endpoint"""

    def test_update_target_success(self, client, disable_rate_limiting, sample_session_data):
        """Test updating target property"""
        # First create a session
        from src.utils.session_storage import get_session_storage
        storage = get_session_storage()
        session_id = 'test-session-123'
        storage.set(session_id, sample_session_data)

        # Update target
        payload = {
            'session_id': session_id,
            'data': {
                'floor': '10',
                'total_floors': 20
            }
        }

        response = client.post(
            '/api/update-target',
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'success'

    def test_update_target_invalid_session(self, client, disable_rate_limiting):
        """Test error with invalid session ID"""
        payload = {
            'session_id': 'nonexistent-session',
            'data': {'floor': '10'}
        }

        response = client.post(
            '/api/update-target',
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code in [400, 404]


class TestAnalyzeEndpoint:
    """Tests for /api/analyze endpoint"""

    def test_analyze_success(self, client, disable_rate_limiting):
        """Test analysis endpoint"""
        from src.utils.session_storage import get_session_storage
        storage = get_session_storage()

        # Create session with target and comparables
        session_id = 'test-analysis-session'
        session_data = {
            'target_property': {
                'price_raw': 5000000,
                'total_area': 50.0,
                'rooms': '2'
            },
            'comparables': [
                {
                    'price_raw': 5100000,
                    'total_area': 51.0,
                    'rooms': '2',
                    'excluded': False
                },
                {
                    'price_raw': 4900000,
                    'total_area': 49.0,
                    'rooms': '2',
                    'excluded': False
                }
            ]
        }
        storage.set(session_id, session_data)

        payload = {
            'session_id': session_id,
            'filter_outliers': True,
            'use_median': True
        }

        response = client.post(
            '/api/analyze',
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()

        assert data['status'] == 'success'
        assert 'analysis' in data
        assert 'market_price' in data['analysis']

    def test_analyze_insufficient_comparables(self, client, disable_rate_limiting):
        """Test error when not enough comparables"""
        from src.utils.session_storage import get_session_storage
        storage = get_session_storage()

        session_id = 'test-insufficient'
        session_data = {
            'target_property': {'price_raw': 5000000, 'total_area': 50.0},
            'comparables': []  # Empty
        }
        storage.set(session_id, session_data)

        payload = {
            'session_id': session_id,
            'filter_outliers': True,
            'use_median': True
        }

        response = client.post(
            '/api/analyze',
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code in [400, 422]


class TestExcludeComparableEndpoint:
    """Tests for /api/exclude-comparable endpoint"""

    def test_exclude_comparable(self, client, disable_rate_limiting):
        """Test excluding a comparable"""
        from src.utils.session_storage import get_session_storage
        storage = get_session_storage()

        session_id = 'test-exclude'
        session_data = {
            'comparables': [
                {'price_raw': 5000000, 'excluded': False},
                {'price_raw': 6000000, 'excluded': False}
            ]
        }
        storage.set(session_id, session_data)

        payload = {
            'session_id': session_id,
            'index': 0
        }

        response = client.post(
            '/api/exclude-comparable',
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'success'

        # Verify it was excluded
        updated_session = storage.get(session_id)
        assert updated_session['comparables'][0]['excluded'] is True


class TestIncludeComparableEndpoint:
    """Tests for /api/include-comparable endpoint"""

    def test_include_comparable(self, client, disable_rate_limiting):
        """Test including (un-excluding) a comparable"""
        from src.utils.session_storage import get_session_storage
        storage = get_session_storage()

        session_id = 'test-include'
        session_data = {
            'comparables': [
                {'price_raw': 5000000, 'excluded': True},  # Previously excluded
                {'price_raw': 6000000, 'excluded': False}
            ]
        }
        storage.set(session_id, session_data)

        payload = {
            'session_id': session_id,
            'index': 0
        }

        response = client.post(
            '/api/include-comparable',
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'success'

        # Verify it was included
        updated_session = storage.get(session_id)
        assert updated_session['comparables'][0]['excluded'] is False


@pytest.mark.integration
class TestAPIEndpointsFlow:
    """Integration tests for full API flow"""

    def test_full_analysis_workflow(self, client, disable_rate_limiting):
        """Test complete workflow: create -> find similar -> analyze"""
        # 1. Create manual property
        create_payload = {
            'address': 'Тестовый адрес для интеграционного теста',
            'price_raw': 5000000,
            'total_area': 50.0,
            'rooms': '2',
            'floor': '5',
            'living_area': 30.0,
            'kitchen_area': 10.0
        }

        response = client.post(
            '/api/create-manual',
            data=json.dumps(create_payload),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        session_id = data['session_id']

        # 2. Update if needed
        update_payload = {
            'session_id': session_id,
            'data': {'repair_level': 'современная'}
        }

        response = client.post(
            '/api/update-target',
            data=json.dumps(update_payload),
            content_type='application/json'
        )
        assert response.status_code == 200

        # 3. Manually add some comparables to session for analysis
        from src.utils.session_storage import get_session_storage
        storage = get_session_storage()
        session_data = storage.get(session_id)
        session_data['comparables'] = [
            {'price_raw': 5100000, 'total_area': 51.0, 'rooms': '2', 'excluded': False},
            {'price_raw': 4900000, 'total_area': 49.0, 'rooms': '2', 'excluded': False},
            {'price_raw': 5200000, 'total_area': 52.0, 'rooms': '2', 'excluded': False}
        ]
        storage.set(session_id, session_data)

        # 4. Run analysis
        analyze_payload = {
            'session_id': session_id,
            'filter_outliers': True,
            'use_median': True
        }

        response = client.post(
            '/api/analyze',
            data=json.dumps(analyze_payload),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'success'
        assert 'analysis' in data
        assert 'market_price' in data['analysis']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
