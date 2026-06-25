"""
Alur Kerja Terarah Tak Siklik (DAG) Airflow untuk sinkronisasi berita historis.
Menjalankan otomatisasi pengumpulan, evaluasi sentimen, dan rekapan ringkasan metrik harian.
"""
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ingestion.rss_batch import RSSBatchProcessor
from monitoring.logger import get_logger
from dags.base_config import GLOBAL_DEFAULT_ARGS

logger = get_logger(__name__)

default_args = GLOBAL_DEFAULT_ARGS.copy()

def fetch_news():
    logger.info("dag_task_started", task="fetch_news")
    processor = RSSBatchProcessor()
    count = processor.run_batch()
    logger.info("dag_task_completed", task="fetch_news", articles=count)
    return count

def process_sentiment():
    logger.info("dag_task_started", task="process_sentiment")
    logger.info("dag_task_completed", task="process_sentiment")

def generate_daily_summary():
    logger.info("dag_task_started", task="generate_daily_summary")
    from storage.db_models import get_session, NewsArticle, PriceData, AnomalyEvent
    from datetime import datetime, timedelta, timezone
    
    session = get_session()
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    
    articles = session.query(NewsArticle).filter(NewsArticle.published_at >= yesterday).all()
    price_count = session.query(PriceData).filter(PriceData.timestamp >= yesterday).count()
    anomaly_count = session.query(AnomalyEvent).filter(AnomalyEvent.detected_at >= yesterday).count()
    
    avg_sentiment = 0.0
    if articles:
        scored = [a.sentiment_score for a in articles if a.sentiment_score is not None]
        if scored:
            avg_sentiment = sum(scored) / len(scored)
        positive = sum(1 for a in articles if a.sentiment_label == 'positive')
        negative = sum(1 for a in articles if a.sentiment_label == 'negative')
        
        logger.info("daily_summary_generated", total_articles=len(articles), avg_sentiment=avg_sentiment, positive=positive, negative=negative)
    
    session.close()
    
    try:
        from monitoring.telegram_alert import send_daily_summary
        send_daily_summary(
            total_prices=price_count,
            total_news=len(articles),
            total_anomalies=anomaly_count,
            avg_sentiment=avg_sentiment,
        )
    except Exception as e:
        logger.warning("telegram_daily_summary_failed", error=str(e))
    
    logger.info("dag_task_completed", task="generate_daily_summary")

with DAG(
    dag_id="news_batch_pipeline",
    default_args=default_args,
    description="Pemrosesan berkelompok analisis berita dan sentimen",
    schedule_interval="0 */6 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["crypto", "news", "batch"],
) as dag:
    
    task_fetch_news = PythonOperator(
        task_id="fetch_news",
        python_callable=fetch_news,
    )
    
    task_process_sentiment = PythonOperator(
        task_id="process_sentiment",
        python_callable=process_sentiment,
    )
    
    task_daily_summary = PythonOperator(
        task_id="generate_daily_summary",
        python_callable=generate_daily_summary,
    )
    
    task_fetch_news >> task_process_sentiment >> task_daily_summary
