"""
Database models for PostgreSQL using SQLAlchemy.

Uses a singleton engine + session factory to avoid creating
a new engine on every call.
"""
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, Boolean, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session
from datetime import datetime
import os
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


class RedditPost(Base):
    """Store Reddit posts and comments."""
    __tablename__ = 'reddit_posts'

    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(String(50), unique=True, nullable=False)
    subreddit = Column(String(100), nullable=False, index=True)
    title = Column(String(500))
    content = Column(Text)
    author = Column(String(100))
    score = Column(Integer)
    num_comments = Column(Integer)
    created_at = Column(DateTime, index=True)
    fetched_at = Column(DateTime, default=datetime.utcnow)
    sentiment_score = Column(Float)
    sentiment_label = Column(String(20))


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


def get_db_engine():
    """Return the singleton database engine (created once, reused)."""
    global _engine
    if _engine is None:
        _engine = create_engine(
            get_db_url(),
            echo=False,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,  # auto-reconnect on stale connections
        )
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
