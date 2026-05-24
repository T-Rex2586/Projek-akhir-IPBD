"""
Batch Inference — Bulk anomaly scoring and sentiment analysis.

Processes large datasets stored in the database:
1. Score all un-analyzed price data for anomalies
2. Bulk sentiment analysis for un-scored articles/posts
3. Write results back to the database

Usage:
    python ml/inference/batch_inference.py
"""
import os
import sys
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import joblib

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from monitoring.logger import get_logger, metrics
from storage.db_models import get_session, PriceData, NewsArticle, RedditPost
from storage.db_utils import save_anomaly_event
from dotenv import load_dotenv

load_dotenv()
logger = get_logger(__name__)

MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "anomaly_detector.joblib")


class BatchAnomalyInference:
    """Bulk anomaly scoring using the trained Isolation Forest."""

    def __init__(self):
        self._model = None
        self._load_model()

    def _load_model(self):
        """Load the trained model from disk."""
        if not os.path.exists(MODEL_PATH):
            logger.warning("batch_inference_model_not_found", path=MODEL_PATH)
            return

        try:
            self._model = joblib.load(MODEL_PATH)
            logger.info("batch_inference_model_loaded", path=MODEL_PATH)
        except Exception as e:
            logger.error("batch_inference_model_load_failed", error=str(e))

    def score_price_data(self, hours: int = 24) -> dict:
        """
        Score recent price data for anomalies.

        Parameters
        ----------
        hours : int
            Hours of data to score.

        Returns
        -------
        dict
            Summary of anomalies found.
        """
        if self._model is None:
            return {"status": "skipped", "reason": "model_not_loaded"}

        session = get_session()
        try:
            since = datetime.utcnow() - timedelta(hours=hours)
            prices = session.query(PriceData).filter(
                PriceData.timestamp >= since
            ).order_by(PriceData.timestamp.asc()).all()

            if len(prices) < 10:
                return {"status": "skipped", "reason": f"insufficient_data ({len(prices)} records)"}

            # Build DataFrame
            df = pd.DataFrame([{
                "price": p.price,
                "volume": p.volume or 0,
                "symbol": p.symbol,
                "timestamp": p.timestamp,
            } for p in prices])

            # Engineer features
            df["price_change"] = df["price"].pct_change().fillna(0)
            df["volume_change"] = df["volume"].pct_change().fillna(0)
            rolling_mean = df["price"].rolling(window=10).mean()
            rolling_std = df["price"].rolling(window=10).std()
            df["price_volatility"] = (rolling_std / rolling_mean.replace(0, np.nan)).fillna(0)
            df = df.replace([np.inf, -np.inf], 0)

            features = df[["price", "volume", "price_change", "volume_change", "price_volatility"]].values
            predictions = self._model.predict(features)

            # Report anomalies
            anomaly_indices = np.where(predictions == -1)[0]
            anomalies_saved = 0

            for idx in anomaly_indices:
                row = df.iloc[idx]
                anomaly = {
                    "event_type": "batch_ml_anomaly",
                    "symbol": row.get("symbol", "N/A"),
                    "description": (
                        f"Batch ML anomaly: price=${row['price']:,.2f}, "
                        f"volume={row['volume']:,.0f}, "
                        f"price_change={row['price_change']:.4f}"
                    ),
                    "severity": "medium",
                    "value": float(row["price"]),
                    "threshold": 0,
                }
                if save_anomaly_event(anomaly):
                    anomalies_saved += 1

            metrics.increment("anomalies_detected", anomalies_saved)

            summary = {
                "status": "completed",
                "total_scored": len(features),
                "anomalies_detected": len(anomaly_indices),
                "anomalies_saved": anomalies_saved,
                "anomaly_rate": round(len(anomaly_indices) / len(features) * 100, 2),
            }
            logger.info("batch_anomaly_scoring_completed", **summary)
            return summary

        except Exception as e:
            logger.error("batch_anomaly_scoring_failed", error=str(e))
            return {"status": "failed", "error": str(e)}
        finally:
            session.close()


class BatchSentimentInference:
    """Bulk sentiment scoring using VADER."""

    def score_unscored_news(self, limit: int = 500) -> dict:
        """Score news articles that don't have sentiment yet."""
        session = get_session()
        try:
            from ml.models.sentiment_vader import analyze_sentiment_vader

            unscored = session.query(NewsArticle).filter(
                NewsArticle.sentiment_score == None  # noqa: E711
            ).limit(limit).all()

            scored = 0
            for article in unscored:
                text = f"{article.title or ''} {article.content or ''}"
                if not text.strip():
                    continue

                result = analyze_sentiment_vader(text)
                article.sentiment_score = result["compound"]
                article.sentiment_label = result["label"]
                scored += 1

            session.commit()
            metrics.increment("records_processed", scored)

            summary = {"type": "news", "total_unscored": len(unscored), "scored": scored}
            logger.info("batch_sentiment_news_completed", **summary)
            return summary

        except Exception as e:
            session.rollback()
            logger.error("batch_sentiment_news_failed", error=str(e))
            return {"type": "news", "error": str(e)}
        finally:
            session.close()

    def score_unscored_reddit(self, limit: int = 500) -> dict:
        """Score Reddit posts that don't have sentiment yet."""
        session = get_session()
        try:
            from ml.models.sentiment_vader import analyze_sentiment_vader

            unscored = session.query(RedditPost).filter(
                RedditPost.sentiment_score == None  # noqa: E711
            ).limit(limit).all()

            scored = 0
            for post in unscored:
                text = f"{post.title or ''} {post.content or ''}"
                if not text.strip():
                    continue

                result = analyze_sentiment_vader(text)
                post.sentiment_score = result["compound"]
                post.sentiment_label = result["label"]
                scored += 1

            session.commit()
            metrics.increment("records_processed", scored)

            summary = {"type": "reddit", "total_unscored": len(unscored), "scored": scored}
            logger.info("batch_sentiment_reddit_completed", **summary)
            return summary

        except Exception as e:
            session.rollback()
            logger.error("batch_sentiment_reddit_failed", error=str(e))
            return {"type": "reddit", "error": str(e)}
        finally:
            session.close()


def run_batch_inference():
    """Run all batch inference tasks."""
    logger.info("batch_inference_pipeline_started")

    results = {}

    # Anomaly scoring
    anomaly_engine = BatchAnomalyInference()
    results["anomaly"] = anomaly_engine.score_price_data(hours=24)

    # Sentiment scoring
    sentiment_engine = BatchSentimentInference()
    results["sentiment_news"] = sentiment_engine.score_unscored_news()
    results["sentiment_reddit"] = sentiment_engine.score_unscored_reddit()

    logger.info("batch_inference_pipeline_completed", results=results)
    return results


if __name__ == "__main__":
    from storage.db_models import init_db
    init_db()

    results = run_batch_inference()
    print(f"\nBatch inference results: {results}")
