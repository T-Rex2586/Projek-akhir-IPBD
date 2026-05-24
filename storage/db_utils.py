"""
Database utility functions.

Every function follows the safe session pattern:
    session = get_session()
    try:
        ...
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
"""
from storage.db_models import (
    get_session, PriceData, KlineData, NewsArticle,
    RedditPost, AnomalyEvent, GoldHourlyMetrics,
)
from monitoring.logger import get_logger
from datetime import datetime, timedelta
from typing import List, Dict, Optional

logger = get_logger(__name__)


# ── Save helpers ─────────────────────────────────────────────────────

def save_price_data(data: Dict) -> bool:
    """Save price data to database."""
    session = get_session()
    try:
        price = PriceData(
            symbol=data['symbol'],
            price=data['price'],
            volume=data.get('volume'),
            high_24h=data.get('high_24h'),
            low_24h=data.get('low_24h'),
            change_24h=data.get('change_24h'),
            timestamp=data.get('timestamp', datetime.utcnow())
        )
        session.add(price)
        session.commit()
        logger.info("price_data_saved", symbol=data['symbol'])
        return True
    except Exception as e:
        session.rollback()
        logger.error("price_data_save_failed", error=str(e))
        return False
    finally:
        session.close()


def save_kline_data(data: Dict) -> bool:
    """Save kline/candlestick data to database."""
    session = get_session()
    try:
        kline = KlineData(
            symbol=data['symbol'],
            open_price=data['open'],
            high_price=data['high'],
            low_price=data['low'],
            close_price=data['close'],
            volume=data['volume'],
            open_time=datetime.fromtimestamp(data['open_time'] / 1000),
            close_time=datetime.fromtimestamp(data['close_time'] / 1000),
            interval=data.get('interval', '1m')
        )
        session.add(kline)
        session.commit()
        logger.info("kline_data_saved", symbol=data['symbol'])
        return True
    except Exception as e:
        session.rollback()
        logger.error("kline_data_save_failed", error=str(e))
        return False
    finally:
        session.close()


def save_news_article(data: Dict) -> bool:
    """Save news article to database."""
    session = get_session()
    try:
        # Check if article already exists
        existing = session.query(NewsArticle).filter_by(url=data['url']).first()
        if existing:
            logger.debug("article_already_exists", url=data['url'])
            return False

        article = NewsArticle(
            title=data['title'],
            content=data.get('content'),
            url=data['url'],
            source=data['source'],
            published_at=data.get('published_at'),
            sentiment_score=data.get('sentiment_score'),
            sentiment_label=data.get('sentiment_label')
        )
        session.add(article)
        session.commit()
        logger.info("news_article_saved", source=data['source'])
        return True
    except Exception as e:
        session.rollback()
        logger.error("news_article_save_failed", error=str(e))
        return False
    finally:
        session.close()


def save_reddit_post(data: Dict) -> bool:
    """Save Reddit post to database."""
    session = get_session()
    try:
        # Check if post already exists
        existing = session.query(RedditPost).filter_by(post_id=data['post_id']).first()
        if existing:
            return False

        post = RedditPost(
            post_id=data['post_id'],
            subreddit=data['subreddit'],
            title=data.get('title'),
            content=data.get('content'),
            author=data.get('author'),
            score=data.get('score'),
            num_comments=data.get('num_comments'),
            created_at=datetime.fromtimestamp(data['created_at']),
            sentiment_score=data.get('sentiment_score'),
            sentiment_label=data.get('sentiment_label')
        )
        session.add(post)
        session.commit()
        logger.info("reddit_post_saved", subreddit=data['subreddit'])
        return True
    except Exception as e:
        session.rollback()
        logger.error("reddit_post_save_failed", error=str(e))
        return False
    finally:
        session.close()


def save_anomaly_event(data: Dict) -> bool:
    """Save anomaly detection event and send Telegram alert."""
    session = get_session()
    try:
        anomaly = AnomalyEvent(
            event_type=data['event_type'],
            symbol=data.get('symbol'),
            description=data['description'],
            severity=data.get('severity', 'medium'),
            value=data.get('value'),
            threshold=data.get('threshold')
        )
        session.add(anomaly)
        session.commit()
        logger.warning("anomaly_detected", event_type=data['event_type'], symbol=data.get('symbol'))

        # Send Telegram alert (non-blocking)
        try:
            from monitoring.telegram_alert import send_anomaly_alert
            send_anomaly_alert(data)
        except Exception as alert_err:
            logger.warning("telegram_alert_dispatch_failed", error=str(alert_err))

        return True
    except Exception as e:
        session.rollback()
        logger.error("anomaly_save_failed", error=str(e))
        return False
    finally:
        session.close()


def save_pipeline_metadata(data: Dict) -> bool:
    """Save pipeline run metadata."""
    from storage.db_models import PipelineMetadata
    session = get_session()
    try:
        meta = PipelineMetadata(
            pipeline_name=data['pipeline_name'],
            run_id=data.get('run_id'),
            status=data.get('status', 'running'),
            records_processed=data.get('records_processed', 0),
            errors=data.get('errors', 0),
            started_at=data.get('started_at', datetime.utcnow()),
            completed_at=data.get('completed_at'),
            run_details=data.get('run_details'),
        )
        session.add(meta)
        session.commit()
        logger.info("pipeline_metadata_saved", pipeline=data['pipeline_name'])
        return True
    except Exception as e:
        session.rollback()
        logger.error("pipeline_metadata_save_failed", error=str(e))
        return False
    finally:
        session.close()


def update_pipeline_metadata(run_id: str, **kwargs) -> bool:
    """Update an existing pipeline metadata record."""
    from storage.db_models import PipelineMetadata
    session = get_session()
    try:
        meta = session.query(PipelineMetadata).filter_by(run_id=run_id).first()
        if not meta:
            return False
        for key, value in kwargs.items():
            if hasattr(meta, key):
                setattr(meta, key, value)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        logger.error("pipeline_metadata_update_failed", error=str(e))
        return False
    finally:
        session.close()


# ── Query helpers ────────────────────────────────────────────────────

def get_recent_prices(symbol: str, hours: int = 24) -> List[Dict]:
    """Get recent price data for a symbol."""
    session = get_session()
    try:
        since = datetime.utcnow() - timedelta(hours=hours)
        prices = session.query(PriceData).filter(
            PriceData.symbol == symbol,
            PriceData.timestamp >= since
        ).order_by(PriceData.timestamp.desc()).all()

        return [{
            'symbol': p.symbol,
            'price': p.price,
            'volume': p.volume,
            'timestamp': p.timestamp
        } for p in prices]
    except Exception as e:
        logger.error("get_recent_prices_failed", error=str(e))
        return []
    finally:
        session.close()


def get_recent_anomalies(hours: int = 24) -> List[Dict]:
    """Get recent anomaly events."""
    session = get_session()
    try:
        since = datetime.utcnow() - timedelta(hours=hours)
        anomalies = session.query(AnomalyEvent).filter(
            AnomalyEvent.detected_at >= since
        ).order_by(AnomalyEvent.detected_at.desc()).all()

        return [{
            'event_type': a.event_type,
            'symbol': a.symbol,
            'description': a.description,
            'severity': a.severity,
            'detected_at': a.detected_at
        } for a in anomalies]
    except Exception as e:
        logger.error("get_recent_anomalies_failed", error=str(e))
        return []
    finally:
        session.close()


# ── Gold Layer ───────────────────────────────────────────────────────

def calculate_and_save_gold_hourly_metrics(symbol: str, window_start: datetime) -> bool:
    """
    Calculate and persist high-value business aggregated metrics (Gold layer)
    for a specific symbol and 1-hour window.
    """
    from sqlalchemy import func, or_

    window_end = window_start + timedelta(hours=1)
    session = get_session()

    try:
        # 1. Price metrics
        price_stats = session.query(
            func.avg(PriceData.price).label('avg'),
            func.min(PriceData.price).label('min'),
            func.max(PriceData.price).label('max')
        ).filter(
            PriceData.symbol == symbol,
            PriceData.timestamp >= window_start,
            PriceData.timestamp < window_end
        ).first()

        if not price_stats or price_stats.avg is None:
            # Try KlineData as fallback if PriceData is empty
            kline_stats = session.query(
                func.avg(KlineData.close_price).label('avg'),
                func.min(KlineData.low_price).label('min'),
                func.max(KlineData.high_price).label('max')
            ).filter(
                KlineData.symbol == symbol,
                KlineData.open_time >= window_start,
                KlineData.open_time < window_end
            ).first()
            if kline_stats and kline_stats.avg is not None:
                price_stats = kline_stats
            else:
                return False

        # 2. Reddit sentiment metrics
        # Map crypto symbols to subreddits or keywords
        kw_map = {
            "BTCUSDT": ["bitcoin", "btc"],
            "ETHUSDT": ["ethereum", "eth"],
            "BNBUSDT": ["binance", "bnb"],
            "SOLUSDT": ["solana", "sol"],
            "ADAUSDT": ["cardano", "ada"]
        }
        kws = kw_map.get(symbol.upper(), [symbol.lower()])

        reddit_sentiment = session.query(
            func.avg(RedditPost.sentiment_score).label('avg'),
            func.count(RedditPost.id).label('count')
        ).filter(
            RedditPost.created_at >= window_start,
            RedditPost.created_at < window_end,
            or_(*[RedditPost.title.ilike(f'%{kw}%') for kw in kws])
        ).first()

        # 3. News sentiment metrics
        news_sentiment = session.query(
            func.avg(NewsArticle.sentiment_score).label('avg'),
            func.count(NewsArticle.id).label('count')
        ).filter(
            NewsArticle.published_at >= window_start,
            NewsArticle.published_at < window_end,
            or_(*[NewsArticle.title.ilike(f'%{kw}%') for kw in kws])
        ).first()

        # Combine sentiment
        total_signals = (reddit_sentiment.count or 0) + (news_sentiment.count or 0)
        avg_sentiment = 0.0
        if total_signals > 0:
            reddit_sum = (reddit_sentiment.avg or 0.0) * (reddit_sentiment.count or 0)
            news_sum = (news_sentiment.avg or 0.0) * (news_sentiment.count or 0)
            avg_sentiment = (reddit_sum + news_sum) / total_signals

        # 4. Anomalies
        anomalies_count = session.query(func.count(AnomalyEvent.id)).filter(
            AnomalyEvent.symbol == symbol,
            AnomalyEvent.detected_at >= window_start,
            AnomalyEvent.detected_at < window_end
        ).scalar() or 0

        # Save/update Gold Layer record
        gold = session.query(GoldHourlyMetrics).filter(
            GoldHourlyMetrics.symbol == symbol,
            GoldHourlyMetrics.window_start == window_start
        ).first()

        if not gold:
            gold = GoldHourlyMetrics(
                symbol=symbol,
                window_start=window_start,
                avg_price=price_stats.avg,
                min_price=price_stats.min,
                max_price=price_stats.max,
                avg_sentiment=avg_sentiment,
                sentiment_signal_count=total_signals,
                anomaly_event_count=anomalies_count
            )
            session.add(gold)
        else:
            gold.avg_price = price_stats.avg
            gold.min_price = price_stats.min
            gold.max_price = price_stats.max
            gold.avg_sentiment = avg_sentiment
            gold.sentiment_signal_count = total_signals
            gold.anomaly_event_count = anomalies_count

        session.commit()
        logger.info("gold_hourly_metrics_computed", symbol=symbol, window=window_start.isoformat())
        return True
    except Exception as e:
        session.rollback()
        logger.error("gold_hourly_metrics_computation_failed", symbol=symbol, error=str(e))
        return False
    finally:
        session.close()


def get_gold_hourly_metrics(symbol: str, hours: int = 24) -> List[Dict]:
    """Retrieve Gold Hourly Metrics for visual consumption."""
    session = get_session()
    try:
        since = datetime.utcnow() - timedelta(hours=hours)
        metrics_list = session.query(GoldHourlyMetrics).filter(
            GoldHourlyMetrics.symbol == symbol,
            GoldHourlyMetrics.window_start >= since
        ).order_by(GoldHourlyMetrics.window_start.asc()).all()

        return [{
            'window_start': m.window_start,  # return datetime, not string
            'symbol': m.symbol,
            'avg_price': m.avg_price,
            'min_price': m.min_price,
            'max_price': m.max_price,
            'avg_sentiment': m.avg_sentiment,
            'sentiment_signal_count': m.sentiment_signal_count,
            'anomaly_event_count': m.anomaly_event_count
        } for m in metrics_list]
    except Exception as e:
        logger.error("get_gold_hourly_metrics_failed", symbol=symbol, error=str(e))
        return []
    finally:
        session.close()
