"""
Batch Processor — Pandas-based batch data processing.

Performs periodic bulk operations:
1. Data quality checks (null detection, outlier flagging)
2. Re-score articles/posts that are missing sentiment
3. Compute daily aggregate statistics
4. Record pipeline metadata for audit trail
"""
import os
import sys
import uuid
from datetime import datetime, timedelta
from typing import Dict, List

import pandas as pd

# Add project root to path for direct execution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from monitoring.logger import get_logger, metrics
from storage.db_models import (
    get_session, PriceData, KlineData, NewsArticle,
    AnomalyEvent, PipelineMetadata,
)
from storage.db_utils import save_pipeline_metadata, update_pipeline_metadata
from dotenv import load_dotenv

load_dotenv()
logger = get_logger(__name__)


class BatchProcessor:
    """
    Batch data processor for scheduled analytics and data quality.

    Designed to be called by Airflow DAGs or run as a standalone script.
    """

    def __init__(self):
        self.run_id = f"batch_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        logger.info("batch_processor_initialized", run_id=self.run_id)

    # ── Data Quality ─────────────────────────────────────────────────

    def run_data_quality_checks(self) -> Dict:
        """
        Run data quality checks across all tables.

        Returns a summary dict with counts and quality metrics.
        """
        logger.info("data_quality_check_started")
        session = get_session()
        report = {}

        try:
            # 1. Price data: check for nulls and extreme outliers
            total_prices = session.query(PriceData).count()
            null_prices = session.query(PriceData).filter(
                PriceData.price == None  # noqa: E711
            ).count()
            zero_prices = session.query(PriceData).filter(
                PriceData.price <= 0
            ).count()

            report["price_data"] = {
                "total_records": total_prices,
                "null_prices": null_prices,
                "zero_or_negative_prices": zero_prices,
                "quality_score": round(
                    1 - (null_prices + zero_prices) / max(total_prices, 1), 4
                ),
            }

            # 2. News articles: check for missing sentiment
            total_news = session.query(NewsArticle).count()
            unscored_news = session.query(NewsArticle).filter(
                NewsArticle.sentiment_score == None  # noqa: E711
            ).count()

            report["news_articles"] = {
                "total_records": total_news,
                "unscored_articles": unscored_news,
                "quality_score": round(
                    1 - unscored_news / max(total_news, 1), 4
                ),
            }

            # Overall quality
            scores = [v["quality_score"] for v in report.values()]
            report["overall_quality_score"] = round(
                sum(scores) / len(scores) if scores else 0, 4
            )

            logger.info("data_quality_check_completed", report=report)
            return report

        except Exception as e:
            logger.error("data_quality_check_failed", error=str(e))
            return {"error": str(e)}
        finally:
            session.close()

    # ── Sentiment Re-Scoring ─────────────────────────────────────────

    def rescore_unscored_articles(self) -> int:
        """
        Find news articles without sentiment scores and score them.

        Returns the count of newly scored articles.
        """
        logger.info("rescore_articles_started")
        session = get_session()
        scored_count = 0

        try:
            from ml.models.sentiment_vader import analyze_sentiment_vader

            unscored = session.query(NewsArticle).filter(
                NewsArticle.sentiment_score == None  # noqa: E711
            ).limit(500).all()

            for article in unscored:
                text = f"{article.title or ''} {article.content or ''}"
                if not text.strip():
                    continue

                sentiment = analyze_sentiment_vader(text)
                article.sentiment_score = sentiment["compound"]
                article.sentiment_label = sentiment["label"]
                scored_count += 1

            session.commit()
            logger.info("rescore_articles_completed", scored=scored_count)
            return scored_count

        except Exception as e:
            session.rollback()
            logger.error("rescore_articles_failed", error=str(e))
            return 0
        finally:
            session.close()

    # ── Daily Aggregation ────────────────────────────────────────────

    def compute_daily_statistics(self, target_date: datetime = None) -> Dict:
        """
        Compute daily aggregate statistics for reporting.

        Parameters
        ----------
        target_date : datetime, optional
            The date to aggregate. Defaults to yesterday.
        """
        if target_date is None:
            target_date = datetime.utcnow().replace(
                hour=0, minute=0, second=0, microsecond=0
            ) - timedelta(days=1)

        day_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        logger.info("daily_statistics_started", date=day_start.strftime("%Y-%m-%d"))
        session = get_session()

        try:
            from sqlalchemy import func

            # Price summary
            price_stats = session.query(
                func.count(PriceData.id).label("count"),
                func.avg(PriceData.price).label("avg"),
                func.min(PriceData.price).label("min"),
                func.max(PriceData.price).label("max"),
            ).filter(
                PriceData.timestamp >= day_start,
                PriceData.timestamp < day_end,
            ).first()

            # Kline count
            kline_count = session.query(func.count(KlineData.id)).filter(
                KlineData.open_time >= day_start,
                KlineData.open_time < day_end,
            ).scalar() or 0

            # News summary
            news_stats = session.query(
                func.count(NewsArticle.id).label("count"),
                func.avg(NewsArticle.sentiment_score).label("avg_sentiment"),
            ).filter(
                NewsArticle.published_at >= day_start,
                NewsArticle.published_at < day_end,
            ).first()

            # Anomalies
            anomaly_count = session.query(func.count(AnomalyEvent.id)).filter(
                AnomalyEvent.detected_at >= day_start,
                AnomalyEvent.detected_at < day_end,
            ).scalar() or 0

            summary = {
                "date": day_start.strftime("%Y-%m-%d"),
                "price_records": price_stats.count or 0,
                "kline_records": kline_count,
                "avg_price": round(price_stats.avg or 0, 2),
                "min_price": round(price_stats.min or 0, 2),
                "max_price": round(price_stats.max or 0, 2),
                "news_articles": news_stats.count or 0,
                "news_avg_sentiment": round(news_stats.avg_sentiment or 0, 4),
                "anomalies_detected": anomaly_count,
            }

            logger.info("daily_statistics_completed", summary=summary)

            # Send Telegram daily summary
            try:
                from monitoring.telegram_alert import send_daily_summary
                send_daily_summary(
                    total_prices=summary["price_records"],
                    total_news=summary["news_articles"],
                    total_anomalies=summary["anomalies_detected"],
                    avg_sentiment=summary["news_avg_sentiment"],
                )
            except Exception as tg_err:
                logger.warning("telegram_daily_summary_failed", error=str(tg_err))

            return summary

        except Exception as e:
            logger.error("daily_statistics_failed", error=str(e))
            return {"error": str(e)}
        finally:
            session.close()

    # ── Full batch run ───────────────────────────────────────────────

    def run_full_batch(self) -> Dict:
        """
        Execute the complete batch processing cycle:
        1. Data quality checks
        2. Re-score missing sentiments
        3. Daily statistics
        4. Record pipeline metadata
        """
        started_at = datetime.utcnow()
        logger.info("full_batch_started", run_id=self.run_id)

        # Record pipeline start
        save_pipeline_metadata({
            "pipeline_name": "batch_processor",
            "run_id": self.run_id,
            "status": "running",
            "started_at": started_at,
        })

        total_errors = 0
        total_processed = 0
        results = {}

        # Step 1: Data quality
        try:
            results["data_quality"] = self.run_data_quality_checks()
        except Exception as e:
            total_errors += 1
            results["data_quality"] = {"error": str(e)}

        # Step 2: Re-score sentiments
        try:
            articles_scored = self.rescore_unscored_articles()
            total_processed += articles_scored
            results["rescored"] = {
                "articles": articles_scored,
            }
        except Exception as e:
            total_errors += 1
            results["rescored"] = {"error": str(e)}

        # Step 3: Daily statistics
        try:
            results["daily_stats"] = self.compute_daily_statistics()
        except Exception as e:
            total_errors += 1
            results["daily_stats"] = {"error": str(e)}

        # Record pipeline completion
        completed_at = datetime.utcnow()
        update_pipeline_metadata(
            self.run_id,
            status="completed" if total_errors == 0 else "completed_with_errors",
            records_processed=total_processed,
            errors=total_errors,
            completed_at=completed_at,
            run_details=str(results),
        )

        metrics.increment("records_processed", total_processed)
        logger.info("full_batch_completed",
                     run_id=self.run_id,
                     duration_sec=(completed_at - started_at).total_seconds(),
                     processed=total_processed,
                     errors=total_errors)

        return results


if __name__ == "__main__":
    from storage.db_models import init_db
    init_db()

    processor = BatchProcessor()
    results = processor.run_full_batch()
    print(f"\nBatch results: {results}")
