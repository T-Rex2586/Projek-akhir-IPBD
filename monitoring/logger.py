"""
Konfigurasi log terpusat untuk keseluruhan sistem (pipeline).
Menyediakan pencatatan tersetruktur dalam format JSON dan pengumpul metrik yang aman dari kondisi balapan (thread-safe).
"""
import logging
import logging.handlers
import structlog
import threading
from datetime import datetime
import os

os.makedirs("logs", exist_ok=True)

LOG_ENV = os.getenv("PIPELINE_ENV", "development")

_file_handler = logging.handlers.RotatingFileHandler(
    filename=f"logs/pipeline_{datetime.now().strftime('%Y%m%d')}.log",
    maxBytes=10 * 1024 * 1024,
    backupCount=5,
    encoding="utf-8",
)
_file_handler.setLevel(logging.INFO)

_stream_handler = logging.StreamHandler()
_stream_handler.setLevel(logging.INFO)

_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
_file_handler.setFormatter(_formatter)
_stream_handler.setFormatter(_formatter)

logging.basicConfig(
    level=logging.INFO,
    handlers=[_file_handler, _stream_handler],
)

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)


def get_logger(name: str):
    """Menghasilkan instans logger yang terstruktur."""
    return structlog.get_logger(name)


class MetricsCollector:
    """
    Sistem pengumpulan metrik dengan mekanisme penguncian (lock)
    guna menghindari anomali pada pemrosesan multithreading.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._metrics = {
            "records_processed": 0,
            "errors": 0,
            "anomalies_detected": 0,
            "api_calls": 0,
            "gold_runs": 0,
            "telegram_alerts_sent": 0,
        }
        self.logger = get_logger("metrics")

    def increment(self, metric: str, value: int = 1):
        """Meningkatkan nilai metrik secara atomik."""
        with self._lock:
            if metric in self._metrics:
                self._metrics[metric] += value

    def get_metrics(self) -> dict:
        """Mengembalikan salinan data metrik terkini."""
        with self._lock:
            return self._metrics.copy()

    def reset(self):
        """Mereset seluruh perhitungan metrik ke nilai nol."""
        with self._lock:
            self._metrics = {k: 0 for k in self._metrics}
            self.logger.info("metrics_reset")


metrics = MetricsCollector()
