"""
Tests for database utility functions.

Uses the in-memory SQLite test database from conftest.py.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from storage.db_utils import (
    save_price_data,
    save_kline_data,
    save_news_article,
    save_anomaly_event,
    get_recent_prices,
    get_recent_anomalies,
)
from storage.db_models import get_session, PriceData, NewsArticle


class TestSavePriceData:
    """Tests for save_price_data."""

    def test_save_price_data_success(self, sample_price_data):
        """Should save price data and return True."""
        result = save_price_data(sample_price_data)
        assert result is True

    def test_saved_price_is_queryable(self, sample_price_data):
        """Saved price should be retrievable from DB."""
        save_price_data(sample_price_data)
        prices = get_recent_prices("BTCUSDT", hours=9999)
        assert len(prices) == 1
        assert prices[0]["symbol"] == "BTCUSDT"
        assert prices[0]["price"] == 43250.50

    def test_save_multiple_prices(self, sample_price_data):
        """Should save multiple price records."""
        save_price_data(sample_price_data)
        sample_price_data["price"] = 43500.0
        save_price_data(sample_price_data)
        prices = get_recent_prices("BTCUSDT", hours=9999)
        assert len(prices) == 2


class TestSaveKlineData:
    """Tests for save_kline_data."""

    def test_save_kline_success(self, sample_kline_data):
        """Should save kline data and return True."""
        result = save_kline_data(sample_kline_data)
        assert result is True

    def test_kline_stores_ohlcv(self, sample_kline_data):
        """OHLCV values should be stored correctly."""
        save_kline_data(sample_kline_data)
        session = get_session()
        from storage.db_models import KlineData
        kline = session.query(KlineData).first()
        assert kline is not None
        assert kline.open_price == 2350.0
        assert kline.close_price == 2370.0
        assert kline.symbol == "ETHUSDT"
        session.close()


class TestSaveNewsArticle:
    """Tests for save_news_article."""

    def test_save_article_success(self, sample_news_data):
        """Should save news article and return True."""
        result = save_news_article(sample_news_data)
        assert result is True

    def test_duplicate_url_rejected(self, sample_news_data):
        """Articles with duplicate URLs should be rejected."""
        save_news_article(sample_news_data)
        result = save_news_article(sample_news_data)
        assert result is False

    def test_article_sentiment_stored(self, sample_news_data):
        """Sentiment score and label should be stored."""
        save_news_article(sample_news_data)
        session = get_session()
        article = session.query(NewsArticle).first()
        assert article.sentiment_score == 0.85
        assert article.sentiment_label == "positive"
        session.close()


class TestSaveAnomalyEvent:
    """Tests for save_anomaly_event."""

    def test_save_anomaly_success(self, sample_anomaly_data, monkeypatch):
        """Should save anomaly and return True."""
        # Mock telegram alert to avoid network call
        monkeypatch.setattr(
            "monitoring.telegram_alert.send_anomaly_alert",
            lambda x: None
        )
        result = save_anomaly_event(sample_anomaly_data)
        assert result is True

    def test_anomaly_is_queryable(self, sample_anomaly_data, monkeypatch):
        """Saved anomaly should be retrievable."""
        monkeypatch.setattr(
            "monitoring.telegram_alert.send_anomaly_alert",
            lambda x: None
        )
        save_anomaly_event(sample_anomaly_data)
        anomalies = get_recent_anomalies(hours=9999)
        assert len(anomalies) == 1
        assert anomalies[0]["event_type"] == "price_spike"
        assert anomalies[0]["severity"] == "high"


class TestGetRecentPrices:
    """Tests for get_recent_prices."""

    def test_empty_result(self):
        """Should return empty list if no data."""
        result = get_recent_prices("BTCUSDT", hours=24)
        assert result == []

    def test_filtered_by_symbol(self, sample_price_data):
        """Should only return prices for the requested symbol."""
        save_price_data(sample_price_data)
        sample_price_data["symbol"] = "ETHUSDT"
        sample_price_data["price"] = 2500.0
        save_price_data(sample_price_data)

        btc_prices = get_recent_prices("BTCUSDT", hours=9999)
        eth_prices = get_recent_prices("ETHUSDT", hours=9999)

        assert len(btc_prices) == 1
        assert len(eth_prices) == 1
        assert btc_prices[0]["price"] == 43250.50
        assert eth_prices[0]["price"] == 2500.0
