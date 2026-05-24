"""
Airflow DAG for batch news processing.
"""
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ingestion.rss_batch import RSSBatchProcessor
from monitoring.logger import get_logger

logger = get_logger(__name__)

default_args = {
    "owner": "crypto-pipeline",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

def fetch_news():
    """Fetch news from RSS feeds."""
    logger.info("dag_task_started", task="fetch_news")
    processor = RSSBatchProcessor()
    count = processor.run_batch()
    logger.info("dag_task_completed", task="fetch_news", articles=count)
    return count

def process_sentiment():
    """Process sentiment for articles."""
    logger.info("dag_task_started", task="process_sentiment")
    # Sentiment is already processed in fetch_news
    logger.info("dag_task_completed", task="process_sentiment")

def generate_daily_summary():
    """Generate daily summary report and send Telegram digest."""
    logger.info("dag_task_started", task="generate_daily_summary")
    from storage.db_models import get_session, NewsArticle, RedditPost, PriceData, AnomalyEvent
    from datetime import datetime, timedelta
    
    session = get_session()
    yesterday = datetime.utcnow() - timedelta(days=1)
    
    articles = session.query(NewsArticle).filter(
        NewsArticle.published_at >= yesterday
    ).all()
    
    reddit_posts = session.query(RedditPost).filter(
        RedditPost.created_at >= yesterday
    ).all()
    
    price_count = session.query(PriceData).filter(
        PriceData.timestamp >= yesterday
    ).count()
    
    anomaly_count = session.query(AnomalyEvent).filter(
        AnomalyEvent.detected_at >= yesterday
    ).count()
    
    avg_sentiment = 0.0
    if articles:
        scored = [a.sentiment_score for a in articles if a.sentiment_score is not None]
        if scored:
            avg_sentiment = sum(scored) / len(scored)
        positive = sum(1 for a in articles if a.sentiment_label == 'positive')
        negative = sum(1 for a in articles if a.sentiment_label == 'negative')
        
        logger.info("daily_summary_generated",
                   total_articles=len(articles),
                   avg_sentiment=avg_sentiment,
                   positive=positive,
                   negative=negative)
    
    session.close()
    
    # Send Telegram daily summary
    try:
        from monitoring.telegram_alert import send_daily_summary
        send_daily_summary(
            total_prices=price_count,
            total_reddit=len(reddit_posts),
            total_news=len(articles),
            total_anomalies=anomaly_count,
            avg_sentiment=avg_sentiment,
        )
    except Exception as e:
        logger.warning("telegram_daily_summary_failed", error=str(e))
    
    logger.info("dag_task_completed", task="generate_daily_summary")

# Define DAG
with DAG(
    dag_id="news_batch_pipeline",
    default_args=default_args,
    description="Batch processing for news articles with sentiment analysis",
    schedule_interval="0 */6 * * *",  # Every 6 hours
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
    
    # Define task dependencies
    task_fetch_news >> task_process_sentiment >> task_daily_summary
