"""
Modul Pemrosesan Aliran Data (Stream Processor) berbasis Kafka.
Mengonsumsi pesan dari pelbagai topik aliran Kafka untuk mengeksekusi
deteksi anomali seketika dengan pemanfaatan Isolation Forest dan regulasi statistikal.
"""
import os
import sys
import json
import time
import signal
from datetime import datetime
from collections import deque
from typing import Dict, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from monitoring.logger import get_logger, metrics
from storage.db_utils import save_anomaly_event
from dotenv import load_dotenv

load_dotenv()
logger = get_logger(__name__)

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
PRICE_TOPIC = "price_stream"
SENTIMENT_TOPIC = "sentiment_stream"

PRICE_WINDOW_SIZE = 300
PRICE_CHANGE_THRESHOLD = 0.03
VOLUME_SPIKE_MULTIPLIER = 2.0


class StreamProcessor:
    """Pemroses data real-time menggunakan mekanisme jendela geser (sliding window)."""

    def __init__(self):
        self._price_windows: Dict[str, deque] = {}
        self._running = True
        self._model = None

        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

        logger.info("stream_processor_initialized", kafka=KAFKA_BOOTSTRAP, price_topic=PRICE_TOPIC, sentiment_topic=SENTIMENT_TOPIC)

    def _shutdown(self, signum, frame):
        """Mematikan proses secara aman dan presisi."""
        logger.info("stream_processor_shutting_down", signal=signum)
        self._running = False

    def _load_ml_model(self):
        """Memuat model pembelajaran mesin untuk deteksi anomali apabila telah dilatih."""
        try:
            from ml.inference.stream_inference import StreamAnomalyInference
            self._model = StreamAnomalyInference()
            if self._model._model is None:
                logger.info("ml_model_not_trained_yet")
                self._model = None
            else:
                logger.info("ml_model_loaded_for_streaming")
        except Exception as e:
            logger.info("ml_model_not_available")
            self._model = None

    def _get_window(self, symbol: str) -> deque:
        if symbol not in self._price_windows:
            self._price_windows[symbol] = deque(maxlen=1000)
        return self._price_windows[symbol]

    def _evict_old_entries(self, window: deque, max_age_seconds: int):
        cutoff = time.time() - max_age_seconds
        while window and window[0].get("ts", 0) < cutoff:
            window.popleft()

    def check_price_anomaly(self, symbol: str, current_price: float, volume: float):
        """Menganalisis anomali pergerakan harga relatif terhadap jendela waktu observasi."""
        window = self._get_window(symbol)
        now = time.time()

        window.append({"price": current_price, "volume": volume, "ts": now})
        self._evict_old_entries(window, PRICE_WINDOW_SIZE)

        if len(window) < 2:
            return

        oldest_price = window[0]["price"]
        if oldest_price == 0:
            return

        price_change = (current_price - oldest_price) / oldest_price

        if abs(price_change) > PRICE_CHANGE_THRESHOLD:
            direction = "melonjak" if price_change > 0 else "anjlok"
            anomaly = {
                "event_type": "stream_price_spike",
                "symbol": symbol,
                "description": f"{symbol} {direction} {abs(price_change)*100:.2f}% dalam jendela {PRICE_WINDOW_SIZE}d (${oldest_price:,.2f} → ${current_price:,.2f})",
                "severity": "high" if abs(price_change) > 0.05 else "medium",
                "value": price_change,
                "threshold": PRICE_CHANGE_THRESHOLD,
            }
            save_anomaly_event(anomaly, send_alert=False)
            metrics.increment("anomalies_detected")
            logger.warning("stream_price_anomaly_detected", symbol=symbol, change_pct=price_change * 100)

            try:
                from monitoring.telegram_alert import send_price_spike_alert
                send_price_spike_alert(symbol, price_change * 100, current_price)
            except Exception:
                pass

        if len(window) >= 10:
            avg_vol = sum(e["volume"] for e in window) / len(window)
            if avg_vol > 0 and volume > avg_vol * VOLUME_SPIKE_MULTIPLIER:
                anomaly = {
                    "event_type": "stream_volume_surge",
                    "symbol": symbol,
                    "description": f"Lonjakan volume {symbol}: {volume:,.0f} (rata-rata: {avg_vol:,.0f}, {volume/avg_vol:.1f}x)",
                    "severity": "medium",
                    "value": volume / avg_vol,
                    "threshold": VOLUME_SPIKE_MULTIPLIER,
                }
                save_anomaly_event(anomaly, send_alert=False)
                metrics.increment("anomalies_detected")

                try:
                    from monitoring.telegram_alert import send_volume_alert
                    send_volume_alert(symbol, volume, avg_vol, volume / avg_vol)
                except Exception:
                    pass

    def check_ml_anomaly(self, price_data: dict):
        """Memanfaatkan model ML guna memprediksi keberadaan entitas harga yang anomali."""
        if self._model is None:
            return

        try:
            is_anomaly = self._model.predict_single(price_data)
            if is_anomaly:
                anomaly = {
                    "event_type": "ml_anomaly",
                    "symbol": price_data.get("symbol", "N/A"),
                    "description": f"Model ML mendeteksi anomali: harga=${price_data.get('price', 0):,.2f}, volume={price_data.get('volume', 0):,.0f}",
                    "severity": "high",
                    "value": price_data.get("price", 0),
                    "threshold": 0,
                }
                save_anomaly_event(anomaly)
                metrics.increment("anomalies_detected")
        except Exception as e:
            logger.debug("ml_anomaly_check_failed", error=str(e))

    def process_price_message(self, message: dict):
        """Memproses struktur muatan pesan tunggal mengenai kuotasi instrumen harga."""
        symbol = message.get("symbol", "")
        price = float(message.get("price", 0))
        volume = float(message.get("volume", 0))

        if not symbol or price <= 0:
            return

        self.check_price_anomaly(symbol, price, volume)
        self.check_ml_anomaly(message)
        metrics.increment("records_processed")

    def process_sentiment_message(self, message: dict):
        """Memproses muatan pesan tunggal perihal evaluasi komputasi sentimen."""
        compound = message.get("sentiment_score", 0)
        source = message.get("source", "unknown")

        if abs(compound) > 0.6:
            event_type = "stream_sentiment_crash" if compound < 0 else "stream_sentiment_surge"
            sentiment_type = "Negatif" if compound < 0 else "Positif"
            anomaly = {
                "event_type": event_type,
                "description": f"Lonjakan sentimen {sentiment_type} dari {source}: skor={compound:.3f}, judul={message.get('title', '')[:100]}",
                "severity": "high",
                "value": compound,
                "threshold": -0.6 if compound < 0 else 0.6,
            }
            save_anomaly_event(anomaly, send_alert=False)
            metrics.increment("anomalies_detected")

            try:
                from monitoring.telegram_alert import send_news_sentiment_alert
                send_news_sentiment_alert(source, compound, message.get('title', ''))
            except Exception:
                pass

        metrics.increment("records_processed")

    def run(self):
        """Simpul eksekusi (consumer loop) utama untuk pemantauan data streaming Kafka."""
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
        """Mode subsitusi mandiri untuk melakukan pemrosesan sekunder jika Kafka tak tersedia."""
        from storage.db_utils import get_recent_prices
        logger.info("stream_processor_standalone_mode_started")
        SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT"]

        while self._running:
            try:
                for symbol in SYMBOLS:
                    prices = get_recent_prices(symbol, hours=1)
                    for p in prices[:5]:
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
