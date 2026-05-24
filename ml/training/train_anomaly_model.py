"""
Train Anomaly Detection Model (Isolation Forest).

Fetches historical price data from PostgreSQL, engineers features,
trains an Isolation Forest model, and serializes it to disk.

Usage:
    python ml/training/train_anomaly_model.py
    # or scheduled weekly via Airflow
"""
import os
import sys
import time
from datetime import datetime

import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import IsolationForest
from sklearn.metrics import classification_report

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from monitoring.logger import get_logger
from storage.db_models import get_session, PriceData, KlineData
from dotenv import load_dotenv

load_dotenv()
logger = get_logger(__name__)

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "models")
MODEL_PATH = os.path.join(MODEL_DIR, "anomaly_detector.joblib")
METADATA_PATH = os.path.join(MODEL_DIR, "anomaly_detector_meta.joblib")


def fetch_training_data(hours: int = 168) -> pd.DataFrame:
    """
    Fetch historical price data for training.

    Parameters
    ----------
    hours : int
        How many hours of history to fetch (default: 168 = 1 week).
    """
    session = get_session()
    try:
        from datetime import timedelta
        since = datetime.utcnow() - timedelta(hours=hours)

        # Try PriceData first
        prices = session.query(PriceData).filter(
            PriceData.timestamp >= since
        ).order_by(PriceData.timestamp.asc()).all()

        if len(prices) > 50:
            df = pd.DataFrame([{
                "symbol": p.symbol,
                "price": p.price,
                "volume": p.volume or 0,
                "timestamp": p.timestamp,
            } for p in prices])
            logger.info("training_data_fetched_from_price_data", rows=len(df))
            return df

        # Fallback to KlineData
        klines = session.query(KlineData).filter(
            KlineData.open_time >= since
        ).order_by(KlineData.open_time.asc()).all()

        if klines:
            df = pd.DataFrame([{
                "symbol": k.symbol,
                "price": k.close_price,
                "volume": k.volume,
                "timestamp": k.open_time,
            } for k in klines])
            logger.info("training_data_fetched_from_kline_data", rows=len(df))
            return df

        logger.warning("no_training_data_available")
        return pd.DataFrame()

    except Exception as e:
        logger.error("training_data_fetch_failed", error=str(e))
        return pd.DataFrame()
    finally:
        session.close()


def engineer_features(df: pd.DataFrame) -> np.ndarray:
    """
    Engineer features from price data.

    Features:
    - price
    - volume
    - price_change (%)
    - volume_change (%)
    - price_volatility (rolling std / rolling mean)
    """
    df = df.sort_values("timestamp").copy()

    # Percent changes
    df["price_change"] = df["price"].pct_change()
    df["volume_change"] = df["volume"].pct_change()

    # Rolling volatility (coefficient of variation over 10 periods)
    rolling_mean = df["price"].rolling(window=10).mean()
    rolling_std = df["price"].rolling(window=10).std()
    df["price_volatility"] = rolling_std / rolling_mean.replace(0, np.nan)

    # Fill NaN
    df = df.fillna(0)

    # Replace inf values
    df = df.replace([np.inf, -np.inf], 0)

    features = df[["price", "volume", "price_change", "volume_change", "price_volatility"]].values
    return features


def train_model(contamination: float = 0.05, hours: int = 168) -> dict:
    """
    Full training pipeline.

    Parameters
    ----------
    contamination : float
        Expected proportion of outliers.
    hours : int
        Hours of historical data to use.

    Returns
    -------
    dict
        Training summary with metrics.
    """
    start_time = time.time()
    logger.info("model_training_started", contamination=contamination, hours=hours)

    # 1. Fetch data
    df = fetch_training_data(hours=hours)
    if df.empty or len(df) < 50:
        msg = f"Insufficient training data: {len(df)} rows (minimum 50 required)"
        logger.warning("model_training_aborted", reason=msg)
        return {"status": "aborted", "reason": msg}

    # 2. Engineer features
    features = engineer_features(df)
    logger.info("features_engineered", shape=features.shape)

    # 3. Train model
    model = IsolationForest(
        contamination=contamination,
        random_state=42,
        n_estimators=100,
        n_jobs=-1,
    )
    model.fit(features)

    # 4. Evaluate on training data (for metrics)
    predictions = model.predict(features)
    anomaly_count = int((predictions == -1).sum())
    normal_count = int((predictions == 1).sum())
    anomaly_pct = anomaly_count / len(predictions) * 100

    # 5. Save model
    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(model, MODEL_PATH)

    # Save metadata
    metadata = {
        "trained_at": datetime.utcnow().isoformat(),
        "training_samples": len(features),
        "feature_count": features.shape[1],
        "contamination": contamination,
        "anomalies_detected": anomaly_count,
        "anomaly_percentage": round(anomaly_pct, 2),
        "training_hours": hours,
        "model_path": MODEL_PATH,
    }
    joblib.dump(metadata, METADATA_PATH)

    duration = time.time() - start_time

    summary = {
        "status": "completed",
        "duration_seconds": round(duration, 2),
        "training_samples": len(features),
        "anomalies_found": anomaly_count,
        "normal_found": normal_count,
        "anomaly_percentage": round(anomaly_pct, 2),
        "model_saved_to": MODEL_PATH,
    }

    logger.info("model_training_completed", **summary)
    return summary


if __name__ == "__main__":
    from storage.db_models import init_db
    init_db()

    result = train_model(contamination=0.05, hours=168)
    print(f"\nTraining result: {result}")
