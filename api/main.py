"""
FastAPI serving layer for the crypto pipeline.
"""
from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
import os
import traceback
from dotenv import load_dotenv

from storage.db_utils import (
    get_recent_prices,
    get_recent_anomalies,
    get_gold_hourly_metrics
)
from storage.db_models import get_session, NewsArticle, RedditPost, KlineData
from monitoring.logger import get_logger

load_dotenv()

logger = get_logger(__name__)

app = FastAPI(
    title="Crypto Sentiment & Price Analytics API",
    description="REST API for cryptocurrency price and sentiment data",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Key authentication
API_KEY = os.getenv("API_KEY", "dev-api-key")


def verify_api_key(x_api_key: str = Header(...)):
    """Verify API key from header."""
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return x_api_key


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch unhandled exceptions and return a structured error response."""
    logger.error(
        "unhandled_api_exception",
        path=str(request.url),
        method=request.method,
        error=str(exc),
        traceback=traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)},
    )


# ── Response models ─────────────────────────────────────────────────

class PriceResponse(BaseModel):
    symbol: str
    price: float
    volume: Optional[float] = None
    timestamp: datetime


class AnomalyResponse(BaseModel):
    event_type: str
    symbol: Optional[str] = None
    description: str
    severity: str
    detected_at: datetime


class NewsResponse(BaseModel):
    title: str
    source: str
    published_at: Optional[datetime] = None
    sentiment_score: Optional[float] = None
    sentiment_label: Optional[str] = None
    url: str


class GoldMetricsResponse(BaseModel):
    window_start: datetime
    symbol: str
    avg_price: float
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    avg_sentiment: Optional[float] = None
    sentiment_signal_count: int
    anomaly_event_count: int


class PipelineStatusResponse(BaseModel):
    status: str
    timestamp: datetime
    pipeline_metrics: dict
    database: str
    components: dict


# ── Endpoints ────────────────────────────────────────────────────────

@app.get("/")
def root():
    """Root endpoint."""
    return {
        "message": "Crypto Sentiment & Price Analytics API",
        "version": "2.0.0",
        "data_sources": {
            "binance": "Public API (no key)",
            "reddit": "YARS scraper (no key)",
            "news": "RSS feeds",
        },
        "architecture": "Medallion (Bronze → Silver → Gold)",
        "alerts": "Telegram Bot",
        "endpoints": [
            "/health",
            "/prices/{symbol}",
            "/klines/{symbol}",
            "/anomalies",
            "/news",
            "/sentiment/reddit",
            "/gold/metrics/{symbol}",
            "/pipeline/status",
        ],
    }


@app.get("/health")
def health_check():
    """Health check with pipeline metrics."""
    from monitoring.logger import metrics as pipeline_metrics
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "pipeline_metrics": pipeline_metrics.get_metrics(),
    }


@app.get("/prices/{symbol}", response_model=List[PriceResponse])
def get_prices(
    symbol: str,
    hours: int = 24,
    api_key: str = Depends(verify_api_key)
):
    """Get recent price data for a symbol."""
    try:
        prices = get_recent_prices(symbol.upper(), hours=hours)
        logger.info("prices_fetched", symbol=symbol, count=len(prices))
        return prices
    except Exception as e:
        logger.error("prices_fetch_failed", symbol=symbol, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/anomalies", response_model=List[AnomalyResponse])
def get_anomalies(
    hours: int = 24,
    api_key: str = Depends(verify_api_key)
):
    """Get recent anomaly events."""
    try:
        anomalies = get_recent_anomalies(hours=hours)
        logger.info("anomalies_fetched", count=len(anomalies))
        return anomalies
    except Exception as e:
        logger.error("anomalies_fetch_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/news", response_model=List[NewsResponse])
def get_news(
    limit: int = 50,
    api_key: str = Depends(verify_api_key)
):
    """Get recent news articles with sentiment."""
    session = get_session()
    try:
        articles = session.query(NewsArticle).order_by(
            NewsArticle.published_at.desc()
        ).limit(limit).all()

        result = [{
            "title": a.title,
            "source": a.source,
            "published_at": a.published_at,
            "sentiment_score": a.sentiment_score,
            "sentiment_label": a.sentiment_label,
            "url": a.url
        } for a in articles]

        logger.info("news_fetched", count=len(result))
        return result
    except Exception as e:
        session.rollback()
        logger.error("news_fetch_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@app.get("/sentiment/reddit")
def get_reddit_sentiment(
    subreddit: Optional[str] = None,
    hours: int = 24,
    api_key: str = Depends(verify_api_key)
):
    """Get Reddit sentiment data."""
    session = get_session()
    try:
        since = datetime.utcnow() - timedelta(hours=hours)

        query = session.query(RedditPost).filter(RedditPost.created_at >= since)
        if subreddit:
            query = query.filter(RedditPost.subreddit == subreddit)

        posts = query.order_by(RedditPost.created_at.desc()).limit(100).all()

        # Calculate average sentiment (only from posts with a valid score)
        if posts:
            scored_posts = [p for p in posts if p.sentiment_score is not None]
            avg_sentiment = (
                sum(p.sentiment_score for p in scored_posts) / len(scored_posts)
                if scored_posts else 0.0
            )
            positive = sum(1 for p in posts if p.sentiment_label == 'positive')
            negative = sum(1 for p in posts if p.sentiment_label == 'negative')
            neutral = sum(1 for p in posts if p.sentiment_label == 'neutral')
        else:
            avg_sentiment = 0.0
            positive = negative = neutral = 0

        result = {
            "subreddit": subreddit or "all",
            "hours": hours,
            "total_posts": len(posts),
            "avg_sentiment": round(avg_sentiment, 4),
            "positive": positive,
            "negative": negative,
            "neutral": neutral
        }

        logger.info("reddit_sentiment_fetched", subreddit=subreddit, posts=len(posts))
        return result
    except Exception as e:
        session.rollback()
        logger.error("reddit_sentiment_fetch_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@app.get("/klines/{symbol}")
def get_klines(
    symbol: str,
    limit: int = 100,
    api_key: str = Depends(verify_api_key)
):
    """Get candlestick/kline data."""
    session = get_session()
    try:
        klines = session.query(KlineData).filter(
            KlineData.symbol == symbol.upper()
        ).order_by(KlineData.close_time.desc()).limit(limit).all()

        result = [{
            "symbol": k.symbol,
            "open": k.open_price,
            "high": k.high_price,
            "low": k.low_price,
            "close": k.close_price,
            "volume": k.volume,
            "open_time": k.open_time,
            "close_time": k.close_time
        } for k in reversed(klines)]

        logger.info("klines_fetched", symbol=symbol, count=len(result))
        return result
    except Exception as e:
        session.rollback()
        logger.error("klines_fetch_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@app.get("/gold/metrics/{symbol}", response_model=List[GoldMetricsResponse])
def get_gold_metrics(
    symbol: str,
    hours: int = 24,
    api_key: str = Depends(verify_api_key)
):
    """Get highly-aggregated, consolidated business metrics (Gold Layer)."""
    try:
        metrics_list = get_gold_hourly_metrics(symbol.upper(), hours=hours)
        logger.info("gold_metrics_fetched", symbol=symbol, count=len(metrics_list))
        return metrics_list
    except Exception as e:
        logger.error("gold_metrics_fetch_failed", symbol=symbol, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/pipeline/status")
def get_pipeline_status(
    api_key: str = Depends(verify_api_key)
):
    """Get overall pipeline component status."""
    from monitoring.logger import metrics as pipeline_metrics

    # Test database connectivity
    db_status = "unknown"
    try:
        from sqlalchemy import text
        session = get_session()
        session.execute(text("SELECT 1"))
        db_status = "connected"
        session.close()
    except Exception:
        db_status = "disconnected"

    # Test MinIO connectivity
    minio_status = "unknown"
    try:
        from storage.minio_utils import get_minio_client
        client = get_minio_client()
        client.list_buckets()
        minio_status = "connected"
    except Exception:
        minio_status = "disconnected"

    return {
        "status": "running",
        "timestamp": datetime.utcnow(),
        "pipeline_metrics": pipeline_metrics.get_metrics(),
        "database": db_status,
        "components": {
            "postgresql": db_status,
            "minio": minio_status,
            "api": "running",
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
