"""
Database models for PostgreSQL using SQLAlchemy.

Uses a singleton engine + session factory to avoid creating
a new engine on every call. Includes connection retry logic
for resilience during container startup.
"""
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, Boolean, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session
from datetime import datetime
import os
import time
from dotenv import load_dotenv

load_dotenv()

Base = declarative_base()


class PriceData(Base):
    """Store cryptocurrency price data."""
    __tablename__ = 'price_data'

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    price = Column(Float, nullable=False)
    volume = Column(Float)
    high_24h = Column(Float)
    low_24h = Column(Float)
    change_24h = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    source = Column(String(50), default='binance')

    def __repr__(self):
        return f"<PriceData({self.symbol}, ${self.price}, {self.timestamp})>"


class KlineData(Base):
    """Store candlestick/kline data."""
    __tablename__ = 'kline_data'

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    open_price = Column(Float, nullable=False)
    high_price = Column(Float, nullable=False)
    low_price = Column(Float, nullable=False)
    close_price = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    open_time = Column(DateTime, nullable=False, index=True)
    close_time = Column(DateTime, nullable=False)
    interval = Column(String(10), default='1m')

    def __repr__(self):
        return f"<KlineData({self.symbol}, O={self.open_price}, C={self.close_price}, {self.close_time})>"


class NewsArticle(Base):
    """Store news articles from RSS feeds."""
    __tablename__ = 'news_articles'

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    content = Column(Text)
    url = Column(String(1000), unique=True)
    source = Column(String(100), nullable=False)
    published_at = Column(DateTime, index=True)
    fetched_at = Column(DateTime, default=datetime.utcnow)
    sentiment_score = Column(Float)
    sentiment_label = Column(String(20))

    def __repr__(self):
        return f"<NewsArticle({self.source}: {self.title[:50] if self.title else '?'})>"


class AnomalyEvent(Base):
    """Store detected anomalies."""
    __tablename__ = 'anomaly_events'

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(50), nullable=False)
    symbol = Column(String(20), index=True)
    description = Column(Text)
    severity = Column(String(20))
    value = Column(Float)
    threshold = Column(Float)
    detected_at = Column(DateTime, default=datetime.utcnow, index=True)
    resolved = Column(Boolean, default=False)

    def __repr__(self):
        return f"<AnomalyEvent({self.event_type}, {self.symbol}, {self.severity})>"


class PipelineMetadata(Base):
    """Store pipeline run metadata."""
    __tablename__ = 'pipeline_metadata'

    id = Column(Integer, primary_key=True, autoincrement=True)
    pipeline_name = Column(String(100), nullable=False)
    run_id = Column(String(100), unique=True)
    status = Column(String(20))
    records_processed = Column(Integer)
    errors = Column(Integer)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    run_details = Column(Text)

    def __repr__(self):
        return f"<PipelineMetadata({self.pipeline_name}, {self.status})>"


class GoldHourlyMetrics(Base):
    """
    Store highly-aggregated, refined business-level metrics (Gold Layer).
    Combines price analytics, sentiment scores, and anomaly counts into 1-hour windows.
    """
    __tablename__ = 'gold_hourly_metrics'

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    avg_price = Column(Float, nullable=False)
    min_price = Column(Float)
    max_price = Column(Float)
    avg_sentiment = Column(Float)
    sentiment_signal_count = Column(Integer, default=0)
    anomaly_event_count = Column(Integer, default=0)
    window_start = Column(DateTime, nullable=False, index=True)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('symbol', 'window_start', name='uq_gold_symbol_window'),
    )

    def __repr__(self):
        return f"<GoldHourlyMetrics({self.symbol}, {self.window_start}, avg=${self.avg_price:.2f})>"


# ── Singleton engine & session factory ──────────────────────────────

_engine = None
_SessionFactory = None


def get_db_url() -> str:
    """Build the database URL from environment variables."""
    user = os.getenv('DB_USER', 'postgres')
    password = os.getenv('DB_PASSWORD', 'postgres')
    host = os.getenv('DB_HOST', 'localhost')
    port = os.getenv('DB_PORT', '5432')
    name = os.getenv('DB_NAME', 'crypto_pipeline')
    return f"postgresql://{user}:{password}@{host}:{port}/{name}"


def get_db_engine(max_retries: int = 5, retry_delay: float = 3.0):
    """Return the singleton database engine (created once, reused).

    Retries connection on failure to handle container startup delays.
    """
    global _engine
    if _engine is None:
        url = get_db_url()
        for attempt in range(1, max_retries + 1):
            try:
                _engine = create_engine(
                    url,
                    echo=False,
                    pool_size=5,
                    max_overflow=10,
                    pool_pre_ping=True,  # auto-reconnect on stale connections
                )
                # Test the connection
                from sqlalchemy import text as sa_text
                with _engine.connect() as conn:
                    conn.execute(sa_text('SELECT 1'))
                break
            except Exception as e:
                if attempt == max_retries:
                    raise
                print(f"DB connection attempt {attempt}/{max_retries} failed: {e}. Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
    return _engine


def init_db():
    """Initialize database tables."""
    engine = get_db_engine()
    Base.metadata.create_all(engine)
    return engine


def get_session():
    """
    Get a database session from the shared session factory.

    Usage:
        session = get_session()
        try:
            ...
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    """
    global _SessionFactory
    if _SessionFactory is None:
        engine = get_db_engine()
        _SessionFactory = sessionmaker(bind=engine)
    return _SessionFactory()
