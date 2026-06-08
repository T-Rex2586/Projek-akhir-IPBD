import feedparser
import time
import os
import sys
import random
from datetime import datetime
from typing import List, Dict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from monitoring.logger import get_logger, metrics
from storage.db_utils import save_news_article
from ml.models.sentiment_vader import analyze_sentiment_vader
from dotenv import load_dotenv

load_dotenv()

logger = get_logger(__name__)

RSS_FEEDS = {
    "coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "cointelegraph": "https://cointelegraph.com/rss",
    "decrypt": "https://decrypt.co/feed",
    "bitcoinmagazine": "https://bitcoinmagazine.com/feed",
    "theblock": "https://www.theblock.co/rss.xml",
    "bbc": "https://feeds.bbci.co.uk/news/rss.xml",
    "techcrunch": "https://techcrunch.com/feed/",
}

POLL_INTERVAL_SECONDS = int(os.getenv("NEWS_POLL_INTERVAL", "600"))


class RSSBatchProcessor:

    def __init__(self, feeds: Dict[str, str] = None):
        self.feeds = feeds or RSS_FEEDS
        logger.info("rss_batch_processor_initialized", feeds=list(self.feeds.keys()))

    def fetch_feed(self, source: str, url: str) -> List[Dict]:
        try:
            logger.info("fetching_rss_feed", source=source, url=url)

            import requests
            resp = requests.get(url, timeout=15, headers={
                "User-Agent": "Mozilla/5.0 (CryptoPipeline/1.0; RSS Reader)"
            })
            resp.raise_for_status()

            try:
                from storage.minio_utils import save_to_bronze
                save_to_bronze("rss_feed", resp.content, identifier=source)
            except Exception as e:
                logger.debug("bronze_rss_save_skipped", error=str(e))

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
        try:
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(date_str)
        except:
            return datetime.utcnow()

    def process_articles(self, articles: List[Dict]) -> int:
        saved_count = 0

        for article in articles:
            try:
                text = f"{article['title']} {article['content']}"
                sentiment = analyze_sentiment_vader(text)

                article['sentiment_score'] = sentiment['compound']
                article['sentiment_label'] = sentiment['label']

                if save_news_article(article):
                    saved_count += 1
                    metrics.increment("records_processed")

            except Exception as e:
                logger.error("article_processing_failed", error=str(e))
                metrics.increment("errors")

        return saved_count

    def run_batch(self):
        logger.info("batch_processing_started")
        total_saved = 0

        for source, url in self.feeds.items():
            articles = self.fetch_feed(source, url)
            saved = self.process_articles(articles)
            total_saved += saved
            logger.info("feed_processed", source=source, saved=saved)
            time.sleep(1)

        logger.info("batch_processing_completed", total_saved=total_saved)
        return total_saved

    def run_continuous(self, poll_interval: int = None):
        interval = poll_interval or POLL_INTERVAL_SECONDS
        cycle_count = 0

        logger.info("news_continuous_polling_started",
                     feeds=list(self.feeds.keys()),
                     poll_interval_seconds=interval)

        print(f"\n{'='*60}")
        print(f"  RSS News Continuous Scraper")
        print(f"  Feeds: {', '.join(self.feeds.keys())}")
        print(f"  Poll interval: {interval}s ({interval // 60} min)")
        print(f"  Total feeds: {len(self.feeds)}")
        print(f"{'='*60}\n")

        while True:
            try:
                cycle_count += 1
                total_saved = 0

                for source, url in self.feeds.items():
                    articles = self.fetch_feed(source, url)
                    saved = self.process_articles(articles)
                    total_saved += saved
                    logger.info("feed_processed", source=source, saved=saved)
                    time.sleep(random.uniform(1, 3))

                logger.info("news_poll_cycle_complete",
                            cycle=cycle_count,
                            total_saved=total_saved)

                print(f"[Cycle {cycle_count}] Saved {total_saved} new articles. "
                      f"Next poll in {interval}s...")

                time.sleep(interval)

            except KeyboardInterrupt:
                logger.info("news_continuous_polling_stopped_by_user")
                print("\nNews scraper stopped.")
                break
            except Exception as e:
                logger.error("news_poll_cycle_error", error=str(e))
                metrics.increment("errors")
                time.sleep(30)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="RSS News Scraper")
    parser.add_argument(
        "--mode", choices=["batch", "continuous"], default="continuous",
        help="Run mode: 'batch' for one-shot, 'continuous' for polling loop (default)"
    )
    parser.add_argument(
        "--interval", type=int, default=POLL_INTERVAL_SECONDS,
        help=f"Poll interval in seconds for continuous mode (default: {POLL_INTERVAL_SECONDS})"
    )
    args = parser.parse_args()

    from storage.db_models import init_db
    init_db()

    processor = RSSBatchProcessor()

    if args.mode == "batch":
        processor.run_batch()
    else:
        processor.run_continuous(poll_interval=args.interval)
