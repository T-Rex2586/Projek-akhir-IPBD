"""
Tests for the FastAPI serving layer.

Uses FastAPI's TestClient with the in-memory test database.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from api.main import app, API_KEY


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Valid auth headers."""
    return {"X-API-Key": API_KEY}


class TestRootEndpoint:
    """Tests for the root / endpoint."""

    def test_root_returns_200(self, client):
        """Root endpoint should be publicly accessible."""
        response = client.get("/")
        assert response.status_code == 200

    def test_root_contains_info(self, client):
        """Root should contain API info."""
        data = client.get("/").json()
        assert "message" in data
        assert "endpoints" in data
        assert "version" in data


class TestHealthEndpoint:
    """Tests for the /health endpoint."""

    def test_health_returns_200(self, client):
        """Health endpoint should be publicly accessible."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_contains_status(self, client):
        """Health should return status and metrics."""
        data = client.get("/health").json()
        assert data["status"] == "healthy"
        assert "pipeline_metrics" in data
        assert "timestamp" in data


class TestAuthentication:
    """Tests for API key authentication."""

    def test_missing_api_key_returns_422(self, client):
        """Missing API key header should return 422 (validation error)."""
        response = client.get("/prices/BTCUSDT")
        assert response.status_code == 422

    def test_invalid_api_key_returns_403(self, client):
        """Invalid API key should return 403."""
        response = client.get(
            "/prices/BTCUSDT",
            headers={"X-API-Key": "wrong-key"}
        )
        assert response.status_code == 403

    def test_valid_api_key_accepted(self, client, auth_headers):
        """Valid API key should be accepted."""
        response = client.get("/prices/BTCUSDT", headers=auth_headers)
        assert response.status_code == 200


class TestPricesEndpoint:
    """Tests for the /prices/{symbol} endpoint."""

    def test_prices_empty(self, client, auth_headers):
        """Should return empty list if no data."""
        response = client.get("/prices/BTCUSDT", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_prices_with_data(self, client, auth_headers, sample_price_data):
        """Should return price data after insertion."""
        from storage.db_utils import save_price_data
        save_price_data(sample_price_data)

        response = client.get(
            "/prices/BTCUSDT",
            headers=auth_headers,
            params={"hours": 9999}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["symbol"] == "BTCUSDT"

    def test_prices_hours_filter(self, client, auth_headers):
        """Hours parameter should filter results."""
        response = client.get(
            "/prices/BTCUSDT",
            headers=auth_headers,
            params={"hours": 1}
        )
        assert response.status_code == 200


class TestAnomaliesEndpoint:
    """Tests for the /anomalies endpoint."""

    def test_anomalies_empty(self, client, auth_headers):
        """Should return empty list if no anomalies."""
        response = client.get("/anomalies", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []


class TestNewsEndpoint:
    """Tests for the /news endpoint."""

    def test_news_empty(self, client, auth_headers):
        """Should return empty list if no news."""
        response = client.get("/news", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_news_with_data(self, client, auth_headers, sample_news_data):
        """Should return news after insertion."""
        from storage.db_utils import save_news_article
        save_news_article(sample_news_data)

        response = client.get("/news", headers=auth_headers, params={"limit": 10})
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "Bitcoin hits new all-time high"


class TestKlinesEndpoint:
    """Tests for the /klines/{symbol} endpoint."""

    def test_klines_empty(self, client, auth_headers):
        """Should return empty list if no klines."""
        response = client.get("/klines/BTCUSDT", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_klines_with_data(self, client, auth_headers, sample_kline_data):
        """Should return kline data after insertion."""
        from storage.db_utils import save_kline_data
        save_kline_data(sample_kline_data)

        response = client.get("/klines/ETHUSDT", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["symbol"] == "ETHUSDT"
        assert data[0]["open"] == 2350.0


class TestGoldMetricsEndpoint:
    """Tests for the /gold/metrics/{symbol} endpoint."""

    def test_gold_metrics_empty(self, client, auth_headers):
        """Should return empty list if no gold metrics."""
        response = client.get("/gold/metrics/BTCUSDT", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []
