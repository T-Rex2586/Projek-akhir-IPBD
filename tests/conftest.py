"""
Pytest fixtures shared across all tests.

Provides:
- In-memory SQLite test database
- FastAPI test client
- Sample mock data
"""
import os
import sys
import pytest

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Override DB env vars BEFORE any imports that read them
os.environ["DB_HOST"] = ""
os.environ["DB_PORT"] = ""
os.environ["DB_NAME"] = ""
os.environ["DB_USER"] = ""
os.environ["DB_PASSWORD"] = ""


from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from storage.db_models import Base
import storage.db_models as db_models_module


@pytest.fixture(autouse=True)
def test_db(monkeypatch):
    """
    Create an in-memory SQLite database for each test.

    Uses check_same_thread=False and StaticPool to allow
    cross-thread access (required by FastAPI TestClient).
    """
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Enable foreign keys in SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    # Reset module-level singletons so get_session() uses test DB
    monkeypatch.setattr(db_models_module, "_engine", engine)
    monkeypatch.setattr(db_models_module, "_SessionFactory", TestSession)

    yield engine

    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def session(test_db):
    """Provide a test database session."""
    from storage.db_models import get_session
    s = get_session()
    yield s
    s.close()


@pytest.fixture
def sample_price_data():
    """Sample price data dict for testing."""
    from datetime import datetime, timezone
    return {
        "symbol": "BTCUSDT",
        "price": 43250.50,
        "volume": 1500.0,
        "high_24h": 44000.0,
        "low_24h": 42500.0,
        "change_24h": 2.5,
        "timestamp": datetime.now(timezone.utc),
    }


@pytest.fixture
def sample_kline_data():
    """Sample kline data dict for testing."""
    return {
        "symbol": "ETHUSDT",
        "open": 2350.0,
        "high": 2380.0,
        "low": 2340.0,
        "close": 2370.0,
        "volume": 5000.0,
        "open_time": 1718452800000,  # epoch ms
        "close_time": 1718452860000,
        "interval": "1m",
    }


@pytest.fixture
def sample_news_data():
    """Sample news article dict for testing."""
    from datetime import datetime, timezone
    return {
        "title": "Bitcoin hits new all-time high",
        "content": "Bitcoin surged past $100k today amid institutional buying.",
        "url": "https://example.com/btc-ath",
        "source": "test_source",
        "published_at": datetime.now(timezone.utc),
        "sentiment_score": 0.85,
        "sentiment_label": "positive",
    }


@pytest.fixture
def sample_reddit_data():
    """Sample Reddit post dict for testing."""
    import time
    return {
        "post_id": "abc123",
        "subreddit": "cryptocurrency",
        "title": "BTC to the moon!",
        "content": "I think Bitcoin is going up today.",
        "author": "crypto_fan",
        "score": 42,
        "num_comments": 10,
        "created_at": time.time(),
        "sentiment_score": 0.6,
        "sentiment_label": "positive",
    }


@pytest.fixture
def sample_anomaly_data():
    """Sample anomaly event dict for testing."""
    return {
        "event_type": "price_spike",
        "symbol": "BTCUSDT",
        "description": "BTCUSDT surged 5% in 1 minute",
        "severity": "high",
        "value": 0.05,
        "threshold": 0.03,
    }
