"""
Reddit scraping for sentiment analysis — powered by YARS.

Uses YARS (Yet Another Reddit Scraper) to fetch posts from crypto subreddits
without requiring Reddit API keys. Posts are analyzed for sentiment and stored
in the database.
"""
import time
import random
import os
import sys
from datetime import datetime

# Add project root to path for direct execution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from monitoring.logger import get_logger, metrics
from storage.db_utils import save_reddit_post
from ml.models.sentiment_vader import analyze_sentiment_vader

logger = get_logger(__name__)

SUBREDDITS = ["cryptocurrency", "bitcoin", "ethereum", "CryptoMarkets"]

# Scraping settings
POSTS_PER_FETCH = 25          # posts to fetch per subreddit per cycle
POLL_INTERVAL_SECONDS = 120   # seconds between polling cycles
CATEGORY = "new"              # fetch newest posts for near-real-time sentiment


class RedditStreamProcessor:
    """
    Poll-based Reddit processor using YARS.

    Instead of using PRAW's streaming API (which requires OAuth credentials),
    this class periodically fetches the latest posts from target subreddits
    using Reddit's public .json endpoints via YARS.
    """

    def __init__(self, subreddits: list = None, poll_interval: int = POLL_INTERVAL_SECONDS):
        self.subreddits = subreddits or SUBREDDITS
        self.poll_interval = poll_interval
        self.seen_ids = set()  # track already-processed post IDs

        # Import YARS from the local embedded module
        from ingestion.yars import YARS
        self.scraper = YARS(timeout=15)

        logger.info("reddit_yars_processor_initialized",
                     subreddits=self.subreddits,
                     poll_interval=self.poll_interval)

    def stream_posts(self):
        """
        Continuously poll subreddits for new posts.

        Mimics a stream by fetching the latest posts every poll_interval seconds
        and only processing posts that haven't been seen before.
        """
        logger.info("reddit_polling_started", subreddits=self.subreddits)

        while True:
            try:
                for subreddit in self.subreddits:
                    self._fetch_and_process(subreddit)
                    # Small delay between subreddits to be polite
                    time.sleep(random.uniform(2, 4))

                logger.info("reddit_poll_cycle_complete",
                            seen_total=len(self.seen_ids))

                # Prevent memory leak from growing seen_ids indefinitely
                if len(self.seen_ids) > 10000:
                    self.seen_ids = set(list(self.seen_ids)[-5000:])

                time.sleep(self.poll_interval)

            except KeyboardInterrupt:
                logger.info("reddit_polling_stopped_by_user")
                break
            except Exception as e:
                logger.error("reddit_poll_cycle_error", error=str(e))
                metrics.increment("errors")
                time.sleep(30)  # back off on error

    def _fetch_and_process(self, subreddit: str):
        """Fetch latest posts from a single subreddit and process new ones."""
        try:
            posts = self.scraper.fetch_subreddit_posts(
                subreddit,
                limit=POSTS_PER_FETCH,
                category=CATEGORY,
                time_filter="all",
            )

            # Save raw data to MinIO Bronze
            from storage.minio_utils import save_to_bronze
            save_to_bronze("reddit_scraper", posts, identifier=f"r_{subreddit}")

            new_count = 0
            for post in posts:
                post_id = post.get("id", "")
                if not post_id or post_id in self.seen_ids:
                    continue

                self.seen_ids.add(post_id)
                self.process_post(post)
                new_count += 1

            if new_count > 0:
                logger.info("reddit_new_posts_fetched",
                            subreddit=subreddit,
                            new_count=new_count,
                            total_fetched=len(posts))
                metrics.increment("api_calls")

        except Exception as e:
            logger.error("reddit_fetch_failed",
                         subreddit=subreddit,
                         error=str(e))
            metrics.increment("errors")

    def process_post(self, post: dict):
        """Process a single Reddit post: analyze sentiment, save to DB."""
        try:
            # Build the data dict matching what save_reddit_post expects
            post_data = {
                "post_id": post.get("id", ""),
                "subreddit": post.get("subreddit", "unknown"),
                "title": post.get("title", ""),
                "content": post.get("selftext", ""),
                "author": post.get("author", "[deleted]"),
                "score": post.get("score", 0),
                "num_comments": post.get("num_comments", 0),
                "created_at": post.get("created_utc", datetime.utcnow().timestamp()),
            }

            # Analyze sentiment on title + body
            text = f"{post_data['title']} {post_data['content']}"
            sentiment = analyze_sentiment_vader(text)

            post_data["sentiment_score"] = sentiment["compound"]
            post_data["sentiment_label"] = sentiment["label"]

            # Save to database
            if save_reddit_post(post_data):
                metrics.increment("records_processed")
                logger.info("reddit_post_processed",
                            subreddit=post_data["subreddit"],
                            sentiment=sentiment["label"],
                            score=sentiment["compound"])

            # Check for sentiment anomaly
            if sentiment["compound"] < -0.6:
                from storage.db_utils import save_anomaly_event
                anomaly = {
                    "event_type": "sentiment_crash",
                    "description": (
                        f"Negative sentiment spike in r/{post_data['subreddit']}: "
                        f"{post_data['title'][:100]}"
                    ),
                    "severity": "high",
                    "value": sentiment["compound"],
                    "threshold": -0.6,
                }
                save_anomaly_event(anomaly)
                metrics.increment("anomalies_detected")
                logger.warning("reddit_sentiment_anomaly",
                               subreddit=post_data["subreddit"],
                               compound=sentiment["compound"])

                # Send Telegram sentiment alert
                from monitoring.telegram_alert import send_sentiment_alert
                send_sentiment_alert(
                    subreddit=post_data["subreddit"],
                    compound_score=sentiment["compound"],
                    title=post_data["title"]
                )

        except Exception as e:
            logger.error("reddit_post_processing_failed", error=str(e))
            metrics.increment("errors")

    def search_crypto_topics(self, query: str, limit: int = 10) -> list:
        """
        One-off search across Reddit for crypto-related topics.

        Useful for batch analysis or ad-hoc investigation.
        """
        try:
            results = self.scraper.search_reddit(query, limit=limit)
            logger.info("reddit_search_complete", query=query, results=len(results))
            return results
        except Exception as e:
            logger.error("reddit_search_failed", query=query, error=str(e))
            return []

    def fetch_subreddit_top(self, subreddit: str, limit: int = 50,
                            time_filter: str = "day") -> list:
        """
        Fetch top posts from a subreddit for batch sentiment analysis.

        Returns raw post list from YARS (useful for batch processing pipeline).
        """
        try:
            posts = self.scraper.fetch_subreddit_posts(
                subreddit,
                limit=limit,
                category="top",
                time_filter=time_filter,
            )
            logger.info("reddit_top_posts_fetched",
                         subreddit=subreddit,
                         count=len(posts))
            return posts
        except Exception as e:
            logger.error("reddit_top_fetch_failed",
                         subreddit=subreddit,
                         error=str(e))
            return []


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")

    # Initialize database
    from storage.db_models import init_db
    init_db()

    # Run Reddit polling loop
    processor = RedditStreamProcessor()
    processor.stream_posts()
