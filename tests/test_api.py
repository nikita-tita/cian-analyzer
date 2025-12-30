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
        assert 'text/plain' in response.content_type

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

    @patch('app_new.get_parser_for_url')
    def test_parse_url_success(self, mock_get_parser, client, disable_rate_limiting):
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
        mock_get_parser.return_value = mock_parser_instance

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
        """Test parsing with invalid URL fails (forbidden domain returns 403)"""
        payload = {'url': 'https://malicious-site.com/attack'}

        response = client.post(
            '/api/parse',
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 403  # SSRFError returns 403 Forbidden
        data = response.get_json()
        assert data['status'] == 'error'
        assert 'не разрешён' in data['message'].lower() or 'не разрешен' in data['message'].lower()

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
                'url': 'https://spb.cian.ru/sale/flat/test123/',
                'address': 'Тестовый адрес, Санкт-Петербург',
                'price_raw': 5000000,
                'total_area': 50.0,
                'rooms': '2'
            },
            'comparables': [
                {
                    'url': 'https://spb.cian.ru/sale/flat/test124/',
                    'address': 'Аналог 1',
                    'price': 5100000,
                    'price_raw': 5100000,
                    'total_area': 51.0,
                    'rooms': '2',
                    'excluded': False
                },
                {
                    'url': 'https://spb.cian.ru/sale/flat/test125/',
                    'address': 'Аналог 2',
                    'price': 4900000,
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
        assert 'market_statistics' in data['analysis']
        assert 'fair_price_analysis' in data['analysis']

    def test_analyze_insufficient_comparables(self, client, disable_rate_limiting):
        """Test error when not enough comparables"""
        from src.utils.session_storage import get_session_storage
        storage = get_session_storage()

        session_id = 'test-insufficient'
        session_data = {
            'target_property': {
                'url': 'https://spb.cian.ru/sale/flat/test456/',
                'address': 'Тестовый адрес',
                'price_raw': 5000000,
                'total_area': 50.0,
                'rooms': '2'
            },
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
            {
                'url': 'https://spb.cian.ru/sale/flat/comp1/',
                'address': 'Аналог 1',
                'price': 5100000,
                'price_raw': 5100000,
                'total_area': 51.0,
                'rooms': '2',
                'excluded': False
            },
            {
                'url': 'https://spb.cian.ru/sale/flat/comp2/',
                'address': 'Аналог 2',
                'price': 4900000,
                'price_raw': 4900000,
                'total_area': 49.0,
                'rooms': '2',
                'excluded': False
            },
            {
                'url': 'https://spb.cian.ru/sale/flat/comp3/',
                'address': 'Аналог 3',
                'price': 5200000,
                'price_raw': 5200000,
                'total_area': 52.0,
                'rooms': '2',
                'excluded': False
            }
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
        assert 'market_statistics' in data['analysis']
        assert 'fair_price_analysis' in data['analysis']


class TestExportReportEndpoint:
    """Tests for /api/export-report/<session_id> endpoint"""

    def test_export_report_success(self, client, disable_rate_limiting, mock_session_with_analysis):
        """Test successful report export"""
        session_id = mock_session_with_analysis['session_id']

        response = client.get(f'/api/export-report/{session_id}')

        assert response.status_code == 200
        assert response.content_type == 'text/markdown; charset=utf-8'
        assert 'Content-Disposition' in response.headers
        assert 'attachment' in response.headers['Content-Disposition']
        assert 'housler_report_' in response.headers['Content-Disposition']
        assert '.md' in response.headers['Content-Disposition']

        # Проверяем содержимое отчета
        content = response.get_data(as_text=True)
        assert len(content) > 0
        # Проверяем ключевые разделы (без жесткой привязки к эмодзи)
        assert 'Отчет по объекту недвижимости' in content or 'Отчёт по объекту недвижимости' in content
        assert 'Информация об объекте' in content
        assert 'объект' in content.lower()
        assert 'цена' in content.lower()

    def test_export_report_session_not_found(self, client):
        """Test export fails when session doesn't exist"""
        response = client.get('/api/export-report/nonexistent-session-id')

        assert response.status_code == 404
        data = response.get_json()
        assert data['status'] == 'error'
        assert 'не найдена' in data['message'].lower()

    def test_export_report_no_analysis(self, client, disable_rate_limiting, mock_session_without_analysis):
        """Test export fails when analysis hasn't been run"""
        session_id = mock_session_without_analysis['session_id']

        response = client.get(f'/api/export-report/{session_id}')

        assert response.status_code == 400
        data = response.get_json()
        assert data['status'] == 'error'
        assert 'анализ не выполнен' in data['message'].lower()

    def test_export_report_content_structure(self, client, disable_rate_limiting, mock_session_with_analysis):
        """Test exported report contains all expected sections"""
        session_id = mock_session_with_analysis['session_id']

        response = client.get(f'/api/export-report/{session_id}')
        content = response.get_data(as_text=True)

        # Проверяем основные секции отчета (без жесткой привязки к эмодзи)
        assert 'Информация об объекте' in content or 'информация об объекте' in content.lower()
        assert 'аналог' in content.lower()
        assert 'статистика' in content.lower()
        assert 'справедливой цены' in content.lower() or 'справедливая цена' in content.lower()
        assert 'методология' in content.lower() or 'анализ' in content.lower()

        # Проверяем что есть секции (markdown заголовки)
        assert '##' in content

    def test_export_report_markdown_format(self, client, disable_rate_limiting, mock_session_with_analysis):
        """Test report is valid markdown"""
        session_id = mock_session_with_analysis['session_id']

        response = client.get(f'/api/export-report/{session_id}')
        content = response.get_data(as_text=True)

        # Проверяем markdown элементы
        assert content.count('##') >= 5  # Должно быть несколько заголовков
        assert '**' in content  # Жирный текст
        assert '- **' in content  # Списки с жирным текстом
        assert '₽' in content  # Валюта
        assert content.count('---') >= 1  # Разделители


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
