"""
Tests for Gold Layer Processor computation logic.

Uses the in-memory SQLite test database from conftest.py.
"""
import pytest
from datetime import datetime, timedelta, timezone


class TestGoldHourlyMetrics:
    """Test Gold Layer hourly metrics computation."""

    def test_compute_with_price_data(self, session, sample_price_data):
        """Test Gold metrics computation when price data exists."""
        from storage.db_utils import save_price_data, calculate_and_save_gold_hourly_metrics
        from storage.db_models import GoldHourlyMetrics

        # Insert price data for the current hour
        now = datetime.now(timezone.utc)
        current_hour = now.replace(minute=0, second=0, microsecond=0)

        for i in range(5):
            data = sample_price_data.copy()
            data["price"] = 43000.0 + i * 100
            data["timestamp"] = current_hour + timedelta(minutes=i * 10)
            save_price_data(data)

        # Compute Gold metrics
        result = calculate_and_save_gold_hourly_metrics("BTCUSDT", current_hour)

        assert result is True

        # Verify the record was created
        gold = session.query(GoldHourlyMetrics).filter_by(
            symbol="BTCUSDT",
            window_start=current_hour
        ).first()

        assert gold is not None
        assert gold.avg_price > 0
        assert gold.min_price <= gold.avg_price <= gold.max_price

    def test_compute_without_data_returns_false(self):
        """Test that computation returns False when no data exists."""
        from storage.db_utils import calculate_and_save_gold_hourly_metrics

        far_past = datetime(2020, 1, 1)
        result = calculate_and_save_gold_hourly_metrics("BTCUSDT", far_past)

        assert result is False

    def test_compute_updates_existing_record(self, session, sample_price_data):
        """Test that re-computing updates existing Gold metrics."""
        from storage.db_utils import save_price_data, calculate_and_save_gold_hourly_metrics
        from storage.db_models import GoldHourlyMetrics

        now = datetime.now(timezone.utc)
        current_hour = now.replace(minute=0, second=0, microsecond=0)

        # Insert initial data
        data = sample_price_data.copy()
        data["price"] = 40000.0
        data["timestamp"] = current_hour + timedelta(minutes=5)
        save_price_data(data)

        # First computation
        calculate_and_save_gold_hourly_metrics("BTCUSDT", current_hour)

        # Insert more data
        data2 = sample_price_data.copy()
        data2["price"] = 50000.0
        data2["timestamp"] = current_hour + timedelta(minutes=30)
        save_price_data(data2)

        # Re-compute
        result = calculate_and_save_gold_hourly_metrics("BTCUSDT", current_hour)

        assert result is True

        # Should still have only 1 record (upsert)
        count = session.query(GoldHourlyMetrics).filter_by(
            symbol="BTCUSDT",
            window_start=current_hour
        ).count()
        assert count == 1

    def test_get_gold_hourly_metrics(self, session, sample_price_data):
        """Test retrieving Gold metrics via the query helper."""
        from storage.db_utils import (
            save_price_data,
            calculate_and_save_gold_hourly_metrics,
            get_gold_hourly_metrics,
        )

        now = datetime.now(timezone.utc)
        current_hour = now.replace(minute=0, second=0, microsecond=0)

        # Insert data and compute
        data = sample_price_data.copy()
        data["timestamp"] = current_hour + timedelta(minutes=5)
        save_price_data(data)
        calculate_and_save_gold_hourly_metrics("BTCUSDT", current_hour)

        # Query
        results = get_gold_hourly_metrics("BTCUSDT", hours=24)

        assert len(results) >= 1
        assert results[0]["symbol"] == "BTCUSDT"
        assert "avg_price" in results[0]
        assert "avg_sentiment" in results[0]
        assert "anomaly_event_count" in results[0]
