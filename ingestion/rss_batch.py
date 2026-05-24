"""
RSS feed batch processing for news articles.
"""
import feedparser
import time
import os
import sys
from datetime import datetime
from typing import List, Dict

# Add project root to path for direct execution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from monitoring.logger import get_logger, metrics
from storage.db_utils import save_news_article
from ml.models.sentiment_vader import analyze_sentiment_vader
from dotenv import load_dotenv

load_dotenv()

logger = get_logger(__name__)

RSS_FEEDS = {
    "bbc": "https://feeds.bbci.co.uk/news/rss.xml",
    "techcrunch": "https://techcrunch.com/feed/"
}

class RSSBatchProcessor:
    """Batch processor for RSS news feeds."""
    
    def __init__(self, feeds: Dict[str, str] = RSS_FEEDS):
        self.feeds = feeds
        logger.info("rss_batch_processor_initialized", feeds=list(feeds.keys()))
    
    def fetch_feed(self, source: str, url: str) -> List[Dict]:
        """Fetch and parse RSS feed."""
        try:
            logger.info("fetching_rss_feed", source=source, url=url)
            
            # Fetch raw XML content
            import requests
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            
            # Save raw XML data to MinIO Bronze Layer
            from storage.minio_utils import save_to_bronze
            save_to_bronze("rss_feed", resp.content, identifier=source)
            
            feed = feedparser.parse(resp.content)
            
            articles = []
            for entry in feed.entries:
                article = {
                    "title": entry.get("title", ""),
                    "content": entry.get("summary", ""),
                    "url": entry.get("link", ""),
                    "source": source,
                    "published_at": self._parse_date(entry.get("published"))
                }
                articles.append(article)
            
            metrics.increment("api_calls")
            logger.info("rss_feed_fetched", source=source, articles_count=len(articles))
            return articles
        
        except Exception as e:
            logger.error("rss_fetch_failed", source=source, error=str(e))
            metrics.increment("errors")
            return []
    
    def _parse_date(self, date_str: str) -> datetime:
        """Parse date string to datetime."""
        try:
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(date_str)
        except:
            return datetime.utcnow()
    
    def process_articles(self, articles: List[Dict]) -> int:
        """Process articles: analyze sentiment and save to DB."""
        saved_count = 0
        
        for article in articles:
            try:
                # Analyze sentiment
                text = f"{article['title']} {article['content']}"
                sentiment = analyze_sentiment_vader(text)
                
                article['sentiment_score'] = sentiment['compound']
                article['sentiment_label'] = sentiment['label']
                
                # Save to database
                if save_news_article(article):
                    saved_count += 1
                    metrics.increment("records_processed")
                
            except Exception as e:
                logger.error("article_processing_failed", error=str(e))
                metrics.increment("errors")
        
        return saved_count
    
    def run_batch(self):
        """Run batch processing for all feeds."""
        logger.info("batch_processing_started")
        total_saved = 0
        
        for source, url in self.feeds.items():
            articles = self.fetch_feed(source, url)
            saved = self.process_articles(articles)
            total_saved += saved
            logger.info("feed_processed", source=source, saved=saved)
            time.sleep(1)  # Rate limiting
        
        logger.info("batch_processing_completed", total_saved=total_saved)
        return total_saved

if __name__ == "__main__":
    # Initialize database
    from storage.db_models import init_db
    init_db()
    
    # Run batch processing
    processor = RSSBatchProcessor()
    processor.run_batch()
