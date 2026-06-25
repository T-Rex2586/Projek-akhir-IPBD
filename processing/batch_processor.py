"""
Modul Pemrosesan Berkelompok (Batch Processor) berbasis Pandas.
Menjalankan operasi bulk terjadwal meliputi pemeriksaan kualitas data, 
penilaian ulang sentimen artikel, serta agregasi statistik harian.
"""
import os
import sys
import uuid
from datetime import datetime, timedelta
from typing import Dict, List

import pandas as pd

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
    """Mesin pemrosesan data historis berskala besar untuk analitik dan audit kualitas."""

    def __init__(self):
        self.run_id = f"batch_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        logger.info("batch_processor_initialized", run_id=self.run_id)

    def run_data_quality_checks(self) -> Dict:
        """Mengevaluasi kualitas dan integritas data pada keseluruhan tabel penyimpan."""
        logger.info("data_quality_check_started")
        session = get_session()
        report = {}

        try:
            total_prices = session.query(PriceData).count()
            null_prices = session.query(PriceData).filter(PriceData.price == None).count()
            zero_prices = session.query(PriceData).filter(PriceData.price <= 0).count()

            report["price_data"] = {
                "total_records": total_prices,
                "null_prices": null_prices,
                "zero_or_negative_prices": zero_prices,
                "quality_score": round(1 - (null_prices + zero_prices) / max(total_prices, 1), 4),
            }

            total_news = session.query(NewsArticle).count()
            unscored_news = session.query(NewsArticle).filter(NewsArticle.sentiment_score == None).count()

            report["news_articles"] = {
                "total_records": total_news,
                "unscored_articles": unscored_news,
                "quality_score": round(1 - unscored_news / max(total_news, 1), 4),
            }

            scores = [v["quality_score"] for v in report.values()]
            report["overall_quality_score"] = round(sum(scores) / len(scores) if scores else 0, 4)

            logger.info("data_quality_check_completed", report=report)
            return report

        except Exception as e:
            logger.error("data_quality_check_failed", error=str(e))
            return {"error": str(e)}
        finally:
            session.close()

    def rescore_unscored_articles(self) -> int:
        """Mengidentifikasi dan menilai ulang artikel yang belum memiliki skor sentimen."""
        logger.info("rescore_articles_started")
        session = get_session()
        scored_count = 0

        try:
            from ml.models.sentiment_vader import analyze_sentiment_vader

            unscored = session.query(NewsArticle).filter(NewsArticle.sentiment_score == None).limit(500).all()

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

    def compute_daily_statistics(self, target_date: datetime = None) -> Dict:
        """Mengkalkulasi agregat statistik harian guna keperluan laporan periodik."""
        if target_date is None:
            target_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)

        day_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        logger.info("daily_statistics_started", date=day_start.strftime("%Y-%m-%d"))
        session = get_session()

        try:
            from sqlalchemy import func

            price_stats = session.query(
                func.count(PriceData.id).label("count"),
                func.avg(PriceData.price).label("avg"),
                func.min(PriceData.price).label("min"),
                func.max(PriceData.price).label("max"),
            ).filter(PriceData.timestamp >= day_start, PriceData.timestamp < day_end).first()

            kline_count = session.query(func.count(KlineData.id)).filter(
                KlineData.open_time >= day_start, KlineData.open_time < day_end
            ).scalar() or 0

            news_stats = session.query(
                func.count(NewsArticle.id).label("count"),
                func.avg(NewsArticle.sentiment_score).label("avg_sentiment"),
            ).filter(NewsArticle.published_at >= day_start, NewsArticle.published_at < day_end).first()

            anomaly_count = session.query(func.count(AnomalyEvent.id)).filter(
                AnomalyEvent.detected_at >= day_start, AnomalyEvent.detected_at < day_end
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

    def run_full_batch(self) -> Dict:
        """Mengeksekusi seluruh siklus fungsionalitas pemrosesan batch."""
        started_at = datetime.utcnow()
        logger.info("full_batch_started", run_id=self.run_id)

        save_pipeline_metadata({
            "pipeline_name": "batch_processor",
            "run_id": self.run_id,
            "status": "running",
            "started_at": started_at,
        })

        total_errors = 0
        total_processed = 0
        results = {}

        try:
            results["data_quality"] = self.run_data_quality_checks()
        except Exception as e:
            total_errors += 1
            results["data_quality"] = {"error": str(e)}

        try:
            articles_scored = self.rescore_unscored_articles()
            total_processed += articles_scored
            results["rescored"] = {"articles": articles_scored}
        except Exception as e:
            total_errors += 1
            results["rescored"] = {"error": str(e)}

        try:
            results["daily_stats"] = self.compute_daily_statistics()
        except Exception as e:
            total_errors += 1
            results["daily_stats"] = {"error": str(e)}

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
    print(f"\nHasil eksekusi batch: {results}")
