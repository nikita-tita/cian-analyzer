"""
Unit tests for market_rates.py - market rates service
"""

import json
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, mock_open
from src.utils.market_rates import MarketRatesService


class TestMarketRatesServiceInitialization:
    """Tests for MarketRatesService initialization"""

    def test_init_default_cache_path(self):
        """Test initialization with default cache path"""
        service = MarketRatesService()

        assert service.cache_path is not None
        assert isinstance(service.cache_path, Path)
        assert 'market_rates.json' in str(service.cache_path)

    def test_init_custom_cache_path(self, tmp_path):
        """Test initialization with custom cache path"""
        custom_path = tmp_path / "custom_rates.json"
        service = MarketRatesService(cache_path=custom_path)

        assert service.cache_path == custom_path

    def test_init_creates_cache_directory(self, tmp_path):
        """Test that cache directory is created"""
        cache_path = tmp_path / "cache" / "rates.json"
        service = MarketRatesService(cache_path=cache_path)

        assert cache_path.parent.exists()

    def test_init_custom_session(self):
        """Test initialization with custom session"""
        mock_session = Mock()
        service = MarketRatesService(session=mock_session)

        assert service.session == mock_session

    @patch('src.utils.market_rates.MarketRatesService._load_cache')
    def test_init_loads_cache(self, mock_load, tmp_path):
        """Test that cache is loaded during initialization"""
        cache_path = tmp_path / "rates.json"
        service = MarketRatesService(cache_path=cache_path)

        mock_load.assert_called_once()


class TestLoadCache:
    """Tests for _load_cache() method"""

    def test_load_cache_file_not_exists(self, tmp_path):
        """Test loading cache when file doesn't exist"""
        cache_path = tmp_path / "nonexistent.json"
        service = MarketRatesService(cache_path=cache_path)

        # Should initialize empty cache
        assert service._cache == {}

    def test_load_cache_valid_json(self, tmp_path):
        """Test loading cache with valid JSON"""
        cache_path = tmp_path / "rates.json"
        cache_data = {
            "key_rate_percent": 16.0,
            "source": "test_source",
            "timestamp": "2025-11-14T12:00:00"
        }
        cache_path.write_text(json.dumps(cache_data))

        service = MarketRatesService(cache_path=cache_path)

        assert service._cache == cache_data

    def test_load_cache_invalid_json(self, tmp_path):
        """Test loading cache with invalid JSON"""
        cache_path = tmp_path / "rates.json"
        cache_path.write_text("invalid json {")

        service = MarketRatesService(cache_path=cache_path)

        # Should fallback to empty cache
        assert service._cache == {}


class TestSaveCache:
    """Tests for _save_cache() method"""

    def test_save_cache_success(self, tmp_path):
        """Test successful cache save"""
        cache_path = tmp_path / "rates.json"
        service = MarketRatesService(cache_path=cache_path)

        service._cache = {
            "key_rate_percent": 16.0,
            "timestamp": "2025-11-14T12:00:00"
        }
        service._save_cache()

        # Verify file was created
        assert cache_path.exists()

        # Verify content
        saved_data = json.loads(cache_path.read_text())
        assert saved_data["key_rate_percent"] == 16.0

    def test_save_cache_with_unicode(self, tmp_path):
        """Test save cache with unicode characters"""
        cache_path = tmp_path / "rates.json"
        service = MarketRatesService(cache_path=cache_path)

        service._cache = {
            "key_rate_percent": 16.0,
            "note": "Ключевая ставка"
        }
        service._save_cache()

        saved_data = json.loads(cache_path.read_text())
        assert "Ключевая ставка" in saved_data["note"]


class TestIsCacheStale:
    """Tests for _is_cache_stale() method"""

    def test_cache_stale_no_timestamp(self, tmp_path):
        """Test cache is stale when no timestamp"""
        service = MarketRatesService(cache_path=tmp_path / "rates.json")
        service._cache = {"key_rate_percent": 16.0}

        assert service._is_cache_stale() is True

    def test_cache_stale_invalid_timestamp(self, tmp_path):
        """Test cache is stale with invalid timestamp"""
        service = MarketRatesService(cache_path=tmp_path / "rates.json")
        service._cache = {
            "key_rate_percent": 16.0,
            "timestamp": "invalid_date"
        }

        assert service._is_cache_stale() is True

    @patch('src.utils.market_rates.datetime')
    def test_cache_fresh(self, mock_datetime, tmp_path):
        """Test cache is fresh (updated recently)"""
        now = datetime(2025, 11, 14, 12, 0, 0)
        mock_datetime.utcnow.return_value = now
        mock_datetime.fromisoformat = datetime.fromisoformat

        service = MarketRatesService(cache_path=tmp_path / "rates.json")
        # Set timestamp to 1 hour ago (within 12 hour TTL)
        service._cache = {
            "key_rate_percent": 16.0,
            "timestamp": (now - timedelta(hours=1)).isoformat()
        }

        assert service._is_cache_stale() is False

    @patch('src.utils.market_rates.datetime')
    def test_cache_stale_old(self, mock_datetime, tmp_path):
        """Test cache is stale (older than TTL)"""
        now = datetime(2025, 11, 14, 12, 0, 0)
        mock_datetime.utcnow.return_value = now
        mock_datetime.fromisoformat = datetime.fromisoformat

        service = MarketRatesService(cache_path=tmp_path / "rates.json")
        # Set timestamp to 13 hours ago (beyond 12 hour TTL)
        service._cache = {
            "key_rate_percent": 16.0,
            "timestamp": (now - timedelta(hours=13)).isoformat()
        }

        assert service._is_cache_stale() is True


class TestFetchKeyRate:
    """Tests for _fetch_key_rate() method"""

    def test_fetch_key_rate_success(self, tmp_path):
        """Test successful key rate fetch"""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.json.return_value = {"KeyRate": 16.0}
        mock_session.get.return_value = mock_response

        service = MarketRatesService(cache_path=tmp_path / "rates.json", session=mock_session)
        rate = service._fetch_key_rate()

        assert rate == 16.0
        mock_session.get.assert_called_once_with(service.KEY_RATE_URL, timeout=5)
        mock_response.raise_for_status.assert_called_once()

    def test_fetch_key_rate_missing_key(self, tmp_path):
        """Test fetch when KeyRate is missing"""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.json.return_value = {}
        mock_session.get.return_value = mock_response

        service = MarketRatesService(cache_path=tmp_path / "rates.json", session=mock_session)
        rate = service._fetch_key_rate()

        assert rate is None

    def test_fetch_key_rate_invalid_value(self, tmp_path):
        """Test fetch with invalid key rate value"""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.json.return_value = {"KeyRate": "invalid"}
        mock_session.get.return_value = mock_response

        service = MarketRatesService(cache_path=tmp_path / "rates.json", session=mock_session)
        rate = service._fetch_key_rate()

        assert rate is None


class TestRefresh:
    """Tests for refresh() method"""

    @patch('src.utils.market_rates.datetime')
    def test_refresh_success(self, mock_datetime, tmp_path):
        """Test successful refresh"""
        now = datetime(2025, 11, 14, 12, 0, 0)
        mock_datetime.utcnow.return_value = now

        mock_session = Mock()
        mock_response = Mock()
        mock_response.json.return_value = {"KeyRate": 16.0}
        mock_session.get.return_value = mock_response

        service = MarketRatesService(cache_path=tmp_path / "rates.json", session=mock_session)
        service.refresh()

        assert service._cache["key_rate_percent"] == 16.0
        assert service._cache["source"] == service.KEY_RATE_URL
        assert service._cache["timestamp"] == now.isoformat()

    def test_refresh_network_error(self, tmp_path):
        """Test refresh with network error"""
        mock_session = Mock()
        mock_session.get.side_effect = Exception("Network error")

        service = MarketRatesService(cache_path=tmp_path / "rates.json", session=mock_session)
        old_cache = service._cache.copy()

        service.refresh()

        # Cache should remain unchanged
        assert service._cache == old_cache

    def test_refresh_none_rate(self, tmp_path):
        """Test refresh when rate is None"""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.json.return_value = {}
        mock_session.get.return_value = mock_response

        service = MarketRatesService(cache_path=tmp_path / "rates.json", session=mock_session)
        old_cache = service._cache.copy()

        service.refresh()

        # Cache should remain unchanged when rate is None
        assert service._cache == old_cache


class TestGetRates:
    """Tests for get_rates() method"""

    def test_get_rates_fresh_cache(self, tmp_path):
        """Test getting rates with fresh cache"""
        service = MarketRatesService(cache_path=tmp_path / "rates.json")
        service._cache = {
            "key_rate_percent": 16.0,
            "timestamp": datetime.utcnow().isoformat()
        }

        rates = service.get_rates()

        assert rates["key_rate_percent"] == 16.0
        assert "timestamp" in rates

    @patch.object(MarketRatesService, '_is_cache_stale')
    @patch.object(MarketRatesService, 'refresh')
    def test_get_rates_stale_cache(self, mock_refresh, mock_is_stale, tmp_path):
        """Test getting rates with stale cache"""
        mock_is_stale.return_value = True

        service = MarketRatesService(cache_path=tmp_path / "rates.json")
        service.get_rates()

        mock_refresh.assert_called_once()

    @patch.object(MarketRatesService, '_is_cache_stale')
    @patch.object(MarketRatesService, 'refresh')
    def test_get_rates_empty_cache(self, mock_refresh, mock_is_stale, tmp_path):
        """Test getting rates with empty cache"""
        service = MarketRatesService(cache_path=tmp_path / "rates.json")
        service._cache = {}

        service.get_rates()

        mock_refresh.assert_called_once()

    def test_get_rates_returns_copy(self, tmp_path):
        """Test that get_rates returns a copy"""
        service = MarketRatesService(cache_path=tmp_path / "rates.json")
        service._cache = {
            "key_rate_percent": 16.0,
            "timestamp": datetime.utcnow().isoformat()
        }

        rates = service.get_rates()
        rates["key_rate_percent"] = 20.0

        # Original cache should remain unchanged
        assert service._cache["key_rate_percent"] == 16.0


class TestGetOpportunityRate:
    """Tests for get_opportunity_rate() method"""

    def test_get_opportunity_rate_with_key_rate(self, tmp_path):
        """Test opportunity rate calculation with available key rate"""
        service = MarketRatesService(cache_path=tmp_path / "rates.json")
        service._cache = {
            "key_rate_percent": 16.0,
            "source": "test_source",
            "timestamp": "2025-11-14T12:00:00"
        }

        result = service.get_opportunity_rate(spread_percent=2.0)

        # (16 + 2) / 100 = 0.18
        assert result["rate"] == pytest.approx(0.18, abs=0.001)
        assert result["key_rate_percent"] == 16.0
        assert result["spread_percent"] == 2.0
        assert result["source"] == "test_source"
        assert result["timestamp"] == "2025-11-14T12:00:00"

    def test_get_opportunity_rate_custom_spread(self, tmp_path):
        """Test opportunity rate with custom spread"""
        service = MarketRatesService(cache_path=tmp_path / "rates.json")
        service._cache = {
            "key_rate_percent": 16.0,
            "timestamp": "2025-11-14T12:00:00"
        }

        result = service.get_opportunity_rate(spread_percent=3.5)

        # (16 + 3.5) / 100 = 0.195
        assert result["rate"] == pytest.approx(0.195, abs=0.001)
        assert result["spread_percent"] == 3.5

    def test_get_opportunity_rate_fallback(self, tmp_path):
        """Test opportunity rate fallback when key rate unavailable"""
        service = MarketRatesService(cache_path=tmp_path / "rates.json")
        service._cache = {}

        result = service.get_opportunity_rate()

        # Should use fallback rate of 8%
        assert result["rate"] == 0.08
        assert result["key_rate_percent"] is None
        assert result["source"] == "internal_default"
        assert result["timestamp"] is None

    def test_get_opportunity_rate_negative_spread(self, tmp_path):
        """Test that negative spread is clamped to 0"""
        service = MarketRatesService(cache_path=tmp_path / "rates.json")
        service._cache = {
            "key_rate_percent": 16.0,
            "timestamp": "2025-11-14T12:00:00"
        }

        result = service.get_opportunity_rate(spread_percent=-5.0)

        # Spread should be clamped to 0
        # (16 + 0) / 100 = 0.16
        assert result["rate"] == pytest.approx(0.16, abs=0.001)
        assert result["spread_percent"] == 0.0

    def test_get_opportunity_rate_zero_spread(self, tmp_path):
        """Test opportunity rate with zero spread"""
        service = MarketRatesService(cache_path=tmp_path / "rates.json")
        service._cache = {
            "key_rate_percent": 16.0,
            "timestamp": "2025-11-14T12:00:00"
        }

        result = service.get_opportunity_rate(spread_percent=0.0)

        # (16 + 0) / 100 = 0.16
        assert result["rate"] == pytest.approx(0.16, abs=0.001)
        assert result["spread_percent"] == 0.0

    @patch.object(MarketRatesService, 'get_rates')
    def test_get_opportunity_rate_calls_get_rates(self, mock_get_rates, tmp_path):
        """Test that get_opportunity_rate calls get_rates"""
        mock_get_rates.return_value = {
            "key_rate_percent": 16.0,
            "timestamp": "2025-11-14T12:00:00"
        }

        service = MarketRatesService(cache_path=tmp_path / "rates.json")
        service.get_opportunity_rate()

        mock_get_rates.assert_called_once()


class TestIntegration:
    """Integration tests for full workflow"""

    @patch('src.utils.market_rates.datetime')
    def test_full_workflow(self, mock_datetime, tmp_path):
        """Test complete workflow: fetch -> save -> load"""
        now = datetime(2025, 11, 14, 12, 0, 0)
        mock_datetime.utcnow.return_value = now
        mock_datetime.fromisoformat = datetime.fromisoformat

        # Create service with mock session
        mock_session = Mock()
        mock_response = Mock()
        mock_response.json.return_value = {"KeyRate": 16.0}
        mock_session.get.return_value = mock_response

        cache_path = tmp_path / "rates.json"
        service = MarketRatesService(cache_path=cache_path, session=mock_session)

        # Refresh to fetch data
        service.refresh()

        # Get rates
        rates = service.get_rates()
        assert rates["key_rate_percent"] == 16.0

        # Get opportunity rate
        opportunity = service.get_opportunity_rate(spread_percent=2.0)
        assert opportunity["rate"] == pytest.approx(0.18, abs=0.001)

        # Verify cache was saved
        assert cache_path.exists()

        # Create new service instance to test cache loading
        service2 = MarketRatesService(cache_path=cache_path, session=mock_session)
        rates2 = service2.get_rates()

        # Should load from cache without API call
        assert rates2["key_rate_percent"] == 16.0

    def test_cache_ttl_expiration(self, tmp_path):
        """Test cache TTL expiration"""
        # Create cache with old timestamp
        cache_path = tmp_path / "rates.json"
        old_timestamp = (datetime.utcnow() - timedelta(hours=13)).isoformat()
        cache_data = {
            "key_rate_percent": 15.0,
            "timestamp": old_timestamp
        }
        cache_path.write_text(json.dumps(cache_data))

        # Create service
        mock_session = Mock()
        mock_response = Mock()
        mock_response.json.return_value = {"KeyRate": 16.0}
        mock_session.get.return_value = mock_response

        service = MarketRatesService(cache_path=cache_path, session=mock_session)

        # Cache should be stale
        assert service._is_cache_stale() is True

        # get_rates should trigger refresh
        rates = service.get_rates()

        # Should have new rate
        mock_session.get.assert_called_once()
