"""
FastAPI serving layer for the crypto pipeline.

Features:
- RESTful API with versioned endpoints
- API Key authentication
- CORS middleware with configurable origins
- Request logging middleware
- Global exception handler
- OpenAPI documentation with tags
"""
from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
import os
import time
import traceback
from dotenv import load_dotenv

from storage.db_utils import (
    get_recent_prices,
    get_recent_anomalies,
    get_gold_hourly_metrics
)
from storage.db_models import get_session, NewsArticle, KlineData
from monitoring.logger import get_logger

load_dotenv()

logger = get_logger(__name__)

# ── App Configuration ────────────────────────────────────────────────

API_VERSION = "2.1.0"
ALLOWED_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    # Startup
    logger.info("api_server_starting", version=API_VERSION)
    try:
        session = get_session()
        session.close()
        logger.info("database_connection_verified")
    except Exception as e:
        logger.warning("database_connection_check_failed", error=str(e))
    yield
    # Shutdown
    logger.info("api_server_shutting_down")


app = FastAPI(
    title="Crypto Sentiment & Price Analytics API",
    description=(
        "REST API for real-time cryptocurrency price monitoring, "
        "sentiment analysis, and anomaly detection.\n\n"
        "**Architecture**: Medallion (Bronze → Silver → Gold)\n\n"
        "**Data Sources**: Binance (public), RSS feeds (7 crypto news sources)"
    ),
    version=API_VERSION,
    contact={
        "name": "Crypto Pipeline Team",
        "url": "https://github.com/your-username/crypto-pipeline",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── Middleware ────────────────────────────────────────────────────────

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log request method, path, and response time."""
    start = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start) * 1000

    # Skip logging for health checks to reduce noise
    if request.url.path != "/health":
        logger.info(
            "http_request",
            method=request.method,
            path=str(request.url.path),
            status=response.status_code,
            duration_ms=round(duration_ms, 2),
        )

    return response


# ── Authentication ───────────────────────────────────────────────────

API_KEY = os.getenv("API_KEY", "dev-api-key")


def verify_api_key(x_api_key: str = Header(...)):
    """Verify API key from header."""
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return x_api_key


# ── Exception Handler ────────────────────────────────────────────────

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
        content={"detail": "Internal server error"},
    )


# ── Response Models ──────────────────────────────────────────────────

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

@app.get("/", tags=["General"])
def root():
    """Root endpoint — API information and available routes."""
    return {
        "message": "Crypto Sentiment & Price Analytics API",
        "version": API_VERSION,
        "data_sources": {
            "binance": "Public API (no key)",
            "news": "RSS feeds (7 sources)",
        },
        "architecture": "Medallion (Bronze → Silver → Gold)",
        "alerts": "Telegram Bot",
        "docs": "/docs",
        "endpoints": [
            "/health",
            "/prices/{symbol}",
            "/klines/{symbol}",
            "/anomalies",
            "/news",
            "/gold/metrics/{symbol}",
            "/pipeline/status",
        ],
    }


@app.get("/health", tags=["General"])
def health_check():
    """Health check with pipeline metrics — no authentication required."""
    from monitoring.logger import metrics as pipeline_metrics
    return {
        "status": "healthy",
        "version": API_VERSION,
        "timestamp": datetime.utcnow(),
        "pipeline_metrics": pipeline_metrics.get_metrics(),
    }


@app.get("/prices/{symbol}", response_model=List[PriceResponse], tags=["Market Data"])
def get_prices(
    symbol: str,
    hours: int = 24,
    api_key: str = Depends(verify_api_key)
):
    """Get recent price data for a cryptocurrency symbol."""
    try:
        # First try to get data from PriceData table
        prices = get_recent_prices(symbol.upper(), hours=hours)
        
        # If no data in PriceData, fallback to KlineData (WebSocket data)
        if not prices:
            session = get_session()
            try:
                since = datetime.utcnow() - timedelta(hours=hours)
                klines = session.query(KlineData).filter(
                    KlineData.symbol == symbol.upper(),
                    KlineData.close_time >= since
                ).order_by(KlineData.close_time.asc()).all()
                
                # Convert kline data to price format (timestamps in UTC)
                prices = [{
                    'symbol': k.symbol,
                    'price': k.close_price,
                    'volume': k.volume,
                    'timestamp': k.close_time  # Keep as UTC, dashboard will convert
                } for k in klines]
                
                logger.info("prices_from_klines", symbol=symbol, count=len(prices))
            except Exception as e:
                logger.error("kline_fallback_failed", error=str(e))
            finally:
                session.close()
        else:
            logger.info("prices_from_pricedata", symbol=symbol, count=len(prices))
        
        return prices
    except Exception as e:
        logger.error("prices_fetch_failed", symbol=symbol, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/anomalies", response_model=List[AnomalyResponse], tags=["Analytics"])
def get_anomalies(
    hours: int = 24,
    api_key: str = Depends(verify_api_key)
):
    """Get recent anomaly events detected by the pipeline."""
    try:
        anomalies = get_recent_anomalies(hours=hours)
        logger.info("anomalies_fetched", count=len(anomalies))
        return anomalies
    except Exception as e:
        logger.error("anomalies_fetch_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/news", response_model=List[NewsResponse], tags=["Sentiment"])
def get_news(
    limit: int = 50,
    api_key: str = Depends(verify_api_key)
):
    """Get recent news articles with sentiment scores."""
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


@app.get("/klines/{symbol}", tags=["Market Data"])
def get_klines(
    symbol: str,
    limit: int = 100,
    api_key: str = Depends(verify_api_key)
):
    """Get candlestick/kline OHLCV data for charting."""
    session = get_session()
    try:
        klines = session.query(KlineData).filter(
            KlineData.symbol == symbol.upper()
        ).order_by(KlineData.close_time.desc()).limit(limit).all()

        # Return timestamps in UTC, dashboard will convert to WIB
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


@app.get("/gold/metrics/{symbol}", response_model=List[GoldMetricsResponse], tags=["Analytics"])
def get_gold_metrics(
    symbol: str,
    hours: int = 24,
    api_key: str = Depends(verify_api_key)
):
    """Get Gold Layer aggregated business metrics (hourly windows)."""
    try:
        metrics_list = get_gold_hourly_metrics(symbol.upper(), hours=hours)
        logger.info("gold_metrics_fetched", symbol=symbol, count=len(metrics_list))
        return metrics_list
    except Exception as e:
        logger.error("gold_metrics_fetch_failed", symbol=symbol, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/pipeline/status", tags=["Monitoring"])
def get_pipeline_status(
    api_key: str = Depends(verify_api_key)
):
    """Get overall pipeline component status and health."""
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

    # Telegram alert stats
    telegram_stats = {}
    try:
        from monitoring.telegram_alert import get_alert_stats
        telegram_stats = get_alert_stats()
    except Exception:
        pass

    return {
        "status": "running",
        "version": API_VERSION,
        "timestamp": datetime.utcnow(),
        "pipeline_metrics": pipeline_metrics.get_metrics(),
        "database": db_status,
        "components": {
            "postgresql": db_status,
            "minio": minio_status,
            "api": "running",
        },
        "telegram": telegram_stats,
    }


@app.get("/predict/{symbol}", tags=["ML Predictions"])
def get_lstm_prediction(
    symbol: str,
    api_key: str = Depends(verify_api_key)
):
    """
    Get LSTM price prediction and trading signal.
    
    Returns predicted price, signal (BUY/HOLD/SELL), and confidence score.
    Requires trained LSTM model for the symbol.
    """
    try:
        from ml.inference.lstm_inference import fetch_recent_data
        from ml.models.lstm_price_predictor import LSTMPricePredictor
        
        # Initialize predictor
        predictor = LSTMPricePredictor(symbol=symbol)
        
        # Load model
        if not predictor.load_model():
            raise HTTPException(
                status_code=404,
                detail=f"No trained model found for {symbol}. Train model first using: python ml/training/train_lstm_model.py --symbol {symbol}"
            )
        
        # Fetch recent data
        df = fetch_recent_data(symbol, hours=6)
        
        if df.empty or len(df) < predictor.lookback_window:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient data for prediction. Need at least {predictor.lookback_window} records."
            )
        
        # Make prediction
        prediction = predictor.predict_next(df)
        
        if 'error' in prediction:
            raise HTTPException(status_code=500, detail=prediction['error'])
        
        logger.info("api_lstm_prediction", symbol=symbol, signal=prediction['signal'])
        
        return {
            "symbol": symbol,
            "current_price": prediction['current_price'],
            "predicted_price": prediction['predicted_price'],
            "price_change_pct": prediction['price_change_pct'],
            "signal": prediction['signal'],
            "confidence": prediction['confidence'],
            "timestamp": prediction['timestamp'],
            "model_version": "lstm_v1"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("lstm_prediction_api_error", symbol=symbol, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("API_PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port)
