"""
Stream Processor — Kafka-based real-time data processing.

Consumes messages from Kafka topics (price_stream, sentiment_stream)
and applies windowed anomaly detection using the trained Isolation Forest model.

This module bridges the gap between raw ingestion and Silver layer persistence,
adding ML-powered anomaly detection in the stream processing path.
"""
import os
import sys
import json
import time
import signal
from datetime import datetime
from collections import deque
from typing import Dict, Optional

# Add project root to path for direct execution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from monitoring.logger import get_logger, metrics
from storage.db_utils import save_anomaly_event
from dotenv import load_dotenv

load_dotenv()
logger = get_logger(__name__)

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
PRICE_TOPIC = "price_stream"
SENTIMENT_TOPIC = "sentiment_stream"

# Sliding window settings
PRICE_WINDOW_SIZE = 300       # 5-minute window (seconds)
PRICE_CHANGE_THRESHOLD = 0.03  # 3% price change triggers anomaly
VOLUME_SPIKE_MULTIPLIER = 2.0  # 2x average volume triggers anomaly


class StreamProcessor:
    """
    Real-time stream processor with sliding-window anomaly detection.

    Maintains in-memory price windows per symbol and checks for:
    1. Price spikes (> 3% change in 5-minute window)
    2. Volume surges (> 2x average in 1-hour window)
    3. ML-based anomaly detection (Isolation Forest)
    """

    def __init__(self):
        # Sliding windows: symbol → deque of {price, volume, timestamp}
        self._price_windows: Dict[str, deque] = {}
        self._running = True
        self._model = None

        # Register graceful shutdown
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

        logger.info("stream_processor_initialized",
                     kafka=KAFKA_BOOTSTRAP,
                     price_topic=PRICE_TOPIC,
                     sentiment_topic=SENTIMENT_TOPIC)

    def _shutdown(self, signum, frame):
        """Handle graceful shutdown."""
        logger.info("stream_processor_shutting_down", signal=signum)
        self._running = False

    def _load_ml_model(self):
        """Load the trained Isolation Forest model if available."""
        try:
            from ml.inference.stream_inference import StreamAnomalyInference
            self._model = StreamAnomalyInference()
            if self._model._model is None:
                logger.info("ml_model_not_trained_yet", 
                          message="Train model with: python ml/training/train_anomaly_model.py")
                self._model = None
            else:
                logger.info("ml_model_loaded_for_streaming")
        except Exception as e:
            logger.info("ml_model_not_available", 
                       message="Anomaly detection will use rule-based only",
                       hint="Train model with: python ml/training/train_anomaly_model.py")
            self._model = None

    def _get_window(self, symbol: str) -> deque:
        """Get or create the sliding window for a symbol."""
        if symbol not in self._price_windows:
            self._price_windows[symbol] = deque(maxlen=1000)
        return self._price_windows[symbol]

    def _evict_old_entries(self, window: deque, max_age_seconds: int):
        """Remove entries older than max_age_seconds."""
        cutoff = time.time() - max_age_seconds
        while window and window[0].get("ts", 0) < cutoff:
            window.popleft()

    # ── Anomaly detection ────────────────────────────────────────────

    def check_price_anomaly(self, symbol: str, current_price: float, volume: float):
        """
        Sliding-window price anomaly detection.

        Checks if the price changed more than PRICE_CHANGE_THRESHOLD
        within the last PRICE_WINDOW_SIZE seconds.
        """
        window = self._get_window(symbol)
        now = time.time()

        # Add current data point
        window.append({"price": current_price, "volume": volume, "ts": now})

        # Evict stale entries
        self._evict_old_entries(window, PRICE_WINDOW_SIZE)

        if len(window) < 2:
            return  # Need at least 2 points

        oldest_price = window[0]["price"]
        if oldest_price == 0:
            return

        price_change = (current_price - oldest_price) / oldest_price

        if abs(price_change) > PRICE_CHANGE_THRESHOLD:
            direction = "surged" if price_change > 0 else "dropped"
            anomaly = {
                "event_type": "stream_price_spike",
                "symbol": symbol,
                "description": (
                    f"{symbol} {direction} {abs(price_change)*100:.2f}% "
                    f"in {PRICE_WINDOW_SIZE}s window "
                    f"(${oldest_price:,.2f} → ${current_price:,.2f})"
                ),
                "severity": "high" if abs(price_change) > 0.05 else "medium",
                "value": price_change,
                "threshold": PRICE_CHANGE_THRESHOLD,
            }
            save_anomaly_event(anomaly, send_alert=False)
            metrics.increment("anomalies_detected")
            logger.warning("stream_price_anomaly_detected",
                           symbol=symbol, change_pct=price_change * 100)

            # Telegram alert
            try:
                from monitoring.telegram_alert import send_price_spike_alert
                send_price_spike_alert(symbol, price_change * 100, current_price)
            except Exception:
                pass

        # Volume anomaly check
        if len(window) >= 10:
            avg_vol = sum(e["volume"] for e in window) / len(window)
            if avg_vol > 0 and volume > avg_vol * VOLUME_SPIKE_MULTIPLIER:
                anomaly = {
                    "event_type": "stream_volume_surge",
                    "symbol": symbol,
                    "description": (
                        f"{symbol} volume surge: {volume:,.0f} "
                        f"(avg: {avg_vol:,.0f}, {volume/avg_vol:.1f}x)"
                    ),
                    "severity": "medium",
                    "value": volume / avg_vol,
                    "threshold": VOLUME_SPIKE_MULTIPLIER,
                }
                save_anomaly_event(anomaly, send_alert=False)
                metrics.increment("anomalies_detected")

                # Telegram alert
                try:
                    from monitoring.telegram_alert import send_volume_alert
                    send_volume_alert(symbol, volume, avg_vol, volume / avg_vol)
                except Exception:
                    pass

    def check_ml_anomaly(self, price_data: dict):
        """Run ML-based anomaly detection if model is available."""
        if self._model is None:
            return

        try:
            is_anomaly = self._model.predict_single(price_data)
            if is_anomaly:
                anomaly = {
                    "event_type": "ml_anomaly",
                    "symbol": price_data.get("symbol", "N/A"),
                    "description": (
                        f"ML model detected anomaly: "
                        f"price=${price_data.get('price', 0):,.2f}, "
                        f"volume={price_data.get('volume', 0):,.0f}"
                    ),
                    "severity": "high",
                    "value": price_data.get("price", 0),
                    "threshold": 0,
                }
                save_anomaly_event(anomaly)
                metrics.increment("anomalies_detected")
        except Exception as e:
            logger.debug("ml_anomaly_check_failed", error=str(e))

    # ── Kafka consumer loop ──────────────────────────────────────────

    def process_price_message(self, message: dict):
        """Process a single price message from Kafka."""
        symbol = message.get("symbol", "")
        price = float(message.get("price", 0))
        volume = float(message.get("volume", 0))

        if not symbol or price <= 0:
            return

        self.check_price_anomaly(symbol, price, volume)
        self.check_ml_anomaly(message)
        metrics.increment("records_processed")

    def process_sentiment_message(self, message: dict):
        """Process a single sentiment message from Kafka."""
        compound = message.get("sentiment_score", 0)
        source = message.get("source", "unknown")

        if abs(compound) > 0.6:
            event_type = "stream_sentiment_crash" if compound < 0 else "stream_sentiment_surge"
            sentiment_type = "Negative" if compound < 0 else "Positive"
            anomaly = {
                "event_type": event_type,
                "description": (
                    f"{sentiment_type} sentiment spike from {source}: "
                    f"score={compound:.3f}, "
                    f"title={message.get('title', '')[:100]}"
                ),
                "severity": "high",
                "value": compound,
                "threshold": -0.6 if compound < 0 else 0.6,
            }
            save_anomaly_event(anomaly, send_alert=False)
            metrics.increment("anomalies_detected")

            # Telegram alert
            try:
                from monitoring.telegram_alert import send_news_sentiment_alert
                send_news_sentiment_alert(source, compound, message.get('title', ''))
            except Exception:
                pass

        metrics.increment("records_processed")

    def run(self):
        """
        Main consumer loop.

        Attempts to connect to Kafka; falls back to a polling stub
        if Kafka is not available.
        """
        self._load_ml_model()

        try:
            from kafka import KafkaConsumer

            consumer = KafkaConsumer(
                PRICE_TOPIC, SENTIMENT_TOPIC,
                bootstrap_servers=KAFKA_BOOTSTRAP,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                group_id="stream-processor-group",
                auto_offset_reset="latest",
                consumer_timeout_ms=5000,
            )
            logger.info("kafka_consumer_connected", topics=[PRICE_TOPIC, SENTIMENT_TOPIC])

            while self._running:
                messages = consumer.poll(timeout_ms=1000)
                for topic_partition, records in messages.items():
                    topic = topic_partition.topic
                    for record in records:
                        if topic == PRICE_TOPIC:
                            self.process_price_message(record.value)
                        elif topic == SENTIMENT_TOPIC:
                            self.process_sentiment_message(record.value)

            consumer.close()
            logger.info("kafka_consumer_closed")

        except ImportError:
            logger.warning("kafka_python_not_installed_running_standalone")
            self._run_standalone()
        except Exception as e:
            logger.warning("kafka_connection_failed_running_standalone", error=str(e))
            self._run_standalone()

    def _run_standalone(self):
        """
        Standalone mode: process data directly from the database
        when Kafka is not available.
        """
        from storage.db_utils import get_recent_prices

        logger.info("stream_processor_standalone_mode_started")
        SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT"]

        while self._running:
            try:
                for symbol in SYMBOLS:
                    prices = get_recent_prices(symbol, hours=1)
                    for p in prices[:5]:  # Process latest 5
                        self.process_price_message({
                            "symbol": p["symbol"],
                            "price": p["price"],
                            "volume": p.get("volume", 0),
                        })
                time.sleep(30)
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error("standalone_processing_error", error=str(e))
                time.sleep(10)

        logger.info("stream_processor_standalone_stopped")


if __name__ == "__main__":
    from storage.db_models import init_db
    init_db()

    processor = StreamProcessor()
    processor.run()
