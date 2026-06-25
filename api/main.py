"""
Lapisan layanan (serving layer) FastAPI untuk alur kerja data kripto.
Menyediakan REST API untuk pemantauan harga seketika, analisis sentimen, dan deteksi anomali.
"""
from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
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

API_VERSION = "2.1.0"
ALLOWED_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Mengelola siklus hidup inisialisasi dan terminasi aplikasi."""
    logger.info("api_server_starting", version=API_VERSION)
    try:
        session = get_session()
        session.close()
        logger.info("database_connection_verified")
    except Exception as e:
        logger.warning("database_connection_check_failed", error=str(e))
    yield
    logger.info("api_server_shutting_down")


from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI(
    title="API Analitik Harga & Sentimen Kripto",
    description=(
        "REST API terpadu untuk pemantauan harga mata uang kripto waktu nyata, "
        "analisis sentimen pemberitaan, dan sistem deteksi anomali terdistribusi.\n\n"
        "**Arsitektur**: Medallion (Perunggu → Perak → Emas)\n\n"
        "**Sumber Data**: API Publik Binance, Sindikasi RSS Berita Kripto"
    ),
    version=API_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Instrumentasi Prometheus untuk mengukur metrik seperti latensi, tingkat kesalahan, dll.
Instrumentator().instrument(app).expose(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Mencatat metrik dan durasi setiap permintaan HTTP (kecuali /health)."""
    start = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start) * 1000

    if request.url.path != "/health":
        logger.info(
            "http_request",
            method=request.method,
            path=str(request.url.path),
            status=response.status_code,
            duration_ms=round(duration_ms, 2),
        )

    return response


API_KEY = os.getenv("API_KEY", "dev-api-key")

def verify_api_key(x_api_key: str = Header(...)):
    """Memverifikasi validitas kunci API yang diberikan dalam tajuk permintaan."""
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Kunci API tidak valid")
    return x_api_key


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Menangani kesalahan yang tidak tertangkap secara global dan merekam jejak kegagalan."""
    logger.error(
        "unhandled_api_exception",
        path=str(request.url),
        method=request.method,
        error=str(exc),
        traceback=traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Kesalahan server internal"},
    )


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


@app.get("/", tags=["Sistem Utama"])
def root():
    """Mengembalikan informasi arsitektur dasar dan indeks rute yang tersedia."""
    return {
        "message": "API Analitik Harga & Sentimen Kripto",
        "version": API_VERSION,
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


@app.get("/health", tags=["Sistem Utama"])
def health_check():
    """Menguji status vital sistem dan menyajikan metrik internal."""
    from monitoring.logger import metrics as pipeline_metrics
    return {
        "status": "sehat",
        "version": API_VERSION,
        "timestamp": datetime.utcnow(),
        "pipeline_metrics": pipeline_metrics.get_metrics(),
    }


@app.get("/prices/{symbol}", response_model=List[PriceResponse], tags=["Data Pasar"])
def get_prices(symbol: str, hours: int = 24, api_key: str = Depends(verify_api_key)):
    """Menyajikan rekaman historis data harga dalam rentang waktu tertentu."""
    try:
        prices = get_recent_prices(symbol.upper(), hours=hours)
        
        if not prices:
            session = get_session()
            try:
                since = datetime.utcnow() - timedelta(hours=hours)
                klines = session.query(KlineData).filter(
                    KlineData.symbol == symbol.upper(),
                    KlineData.close_time >= since
                ).order_by(KlineData.close_time.asc()).all()
                
                prices = [{
                    'symbol': k.symbol,
                    'price': k.close_price,
                    'volume': k.volume,
                    'timestamp': k.close_time
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


@app.get("/anomalies", response_model=List[AnomalyResponse], tags=["Analitik"])
def get_anomalies(hours: int = 24, api_key: str = Depends(verify_api_key)):
    """Mengembalikan daftar kejadian anomali yang terdeteksi oleh sistem."""
    try:
        anomalies = get_recent_anomalies(hours=hours)
        logger.info("anomalies_fetched", count=len(anomalies))
        return anomalies
    except Exception as e:
        logger.error("anomalies_fetch_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/news/topics", tags=["Sentimen"])
def get_news_topics(hours: int = 24, limit: int = 15, api_key: str = Depends(verify_api_key)):
    """Mengidentifikasi topik wacana naratif dominan dari pemberitaan terkini."""
    try:
        from ml.nlp.topic_extractor import extract_topics
        topics = extract_topics(hours=hours, top_n=limit)
        return topics
    except Exception as e:
        logger.error("news_topics_fetch_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/news", response_model=List[NewsResponse], tags=["Sentimen"])
def get_news(limit: int = 50, api_key: str = Depends(verify_api_key)):
    """Mengembalikan rincian artikel berita beserta skor komputasi sentimennya."""
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


@app.get("/klines/{symbol}", tags=["Data Pasar"])
def get_klines(symbol: str, limit: int = 100, api_key: str = Depends(verify_api_key)):
    """Menyajikan representasi data kandil (kline OHLCV) bagi instrumen visualisasi."""
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


@app.get("/gold/metrics/{symbol}", response_model=List[GoldMetricsResponse], tags=["Analitik"])
def get_gold_metrics(symbol: str, hours: int = 24, api_key: str = Depends(verify_api_key)):
    """Mengekstraksi metrik agregat lapisan Emas dalam blok waktu per jam."""
    try:
        metrics_list = get_gold_hourly_metrics(symbol.upper(), hours=hours)
        logger.info("gold_metrics_fetched", symbol=symbol, count=len(metrics_list))
        return metrics_list
    except Exception as e:
        logger.error("gold_metrics_fetch_failed", symbol=symbol, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics/divergence/{symbol}", tags=["Analitik"])
def get_divergence_gauge(symbol: str, api_key: str = Depends(verify_api_key)):
    """Mengkalkulasi divergensi kuantitatif antara tren sentimen dan perilaku harga aset."""
    try:
        metrics_list = get_gold_hourly_metrics(symbol.upper(), hours=24)
        if len(metrics_list) < 2:
            return {"symbol": symbol, "divergence": 0.0, "status": "neutral", "price_z": 0.0, "sentiment_z": 0.0}
            
        prices = [m['avg_price'] for m in metrics_list if m['avg_price'] is not None]
        sentiments = [m['avg_sentiment'] for m in metrics_list if m['avg_sentiment'] is not None]
        
        if not prices or not sentiments or len(prices) < 2:
            return {"symbol": symbol, "divergence": 0.0, "status": "neutral", "price_z": 0.0, "sentiment_z": 0.0}
            
        import numpy as np
        price_mean, price_std = np.mean(prices), np.std(prices)
        sent_mean, sent_std = np.mean(sentiments), np.std(sentiments)
        
        latest_price = prices[-1]
        latest_sent = sentiments[-1]
        
        price_z = (latest_price - price_mean) / price_std if price_std > 0 else 0
        sent_z = (latest_sent - sent_mean) / sent_std if sent_std > 0 else 0
        
        # Calculate divergence as sentiment relative to price
        # Positive divergence: Sentiment is better than price (Undervalued / Bullish)
        # Negative divergence: Sentiment is worse than price (Overvalued / Bearish)
        divergence = sent_z - price_z
        
        status = "neutral"
        if divergence > 1.5:
            status = "bullish_divergence"
        elif divergence < -1.5:
            status = "bearish_divergence"
            
        return {
            "symbol": symbol,
            "price_z": float(price_z),
            "sentiment_z": float(sent_z),
            "divergence": float(divergence),
            "status": status,
            "latest_price": latest_price,
            "latest_sentiment": latest_sent
        }
    except Exception as e:
        logger.error("divergence_calc_failed", symbol=symbol, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/pipeline/status", tags=["Pemantauan"])
def get_pipeline_status(api_key: str = Depends(verify_api_key)):
    """Memberikan ikhtisar komprehensif mengenai kesehatan seluruh komponen infrastruktur."""
    from monitoring.logger import metrics as pipeline_metrics

    db_status = "unknown"
    try:
        from sqlalchemy import text
        session = get_session()
        session.execute(text("SELECT 1"))
        db_status = "connected"
        session.close()
    except Exception:
        db_status = "disconnected"

    minio_status = "unknown"
    try:
        from storage.minio_utils import get_minio_client
        client = get_minio_client()
        client.list_buckets()
        minio_status = "connected"
    except Exception:
        minio_status = "disconnected"

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


@app.get("/predict/{symbol}", tags=["Prediksi ML"])
def get_lstm_prediction(symbol: str, api_key: str = Depends(verify_api_key)):
    """
    Menjalankan inferensi pada model LSTM dan mengembalikan estimasi harga serta sinyal perdagangan.
    """
    try:
        from ml.inference.lstm_inference import fetch_recent_data
        from ml.models.lstm_price_predictor import LSTMPricePredictor
        
        predictor = LSTMPricePredictor(symbol=symbol)
        
        if not predictor.load_model():
            raise HTTPException(
                status_code=404,
                detail=f"Model tidak ditemukan untuk {symbol}. Lakukan pelatihan model terlebih dahulu."
            )
        
        df = fetch_recent_data(symbol, hours=6)
        
        if df.empty or len(df) < predictor.lookback_window:
            raise HTTPException(
                status_code=400,
                detail=f"Volume data tidak memadai. Minimal {predictor.lookback_window} rekaman historis dibutuhkan."
            )
        
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
            "lower_bound": prediction.get('lower_bound'),
            "upper_bound": prediction.get('upper_bound'),
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
