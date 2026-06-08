"""
Centralized logging configuration for the pipeline.

Features:
- Structured JSON logging via structlog
- Rotating file handler (max 10MB per file, 5 backups)
- Thread-safe metrics collector
- Environment-aware log labels (dev/staging/prod)
"""
import logging
import logging.handlers
import structlog
import threading
from datetime import datetime
import os

# Create logs directory if not exists
os.makedirs("logs", exist_ok=True)

# Environment label
LOG_ENV = os.getenv("PIPELINE_ENV", "development")

# Configure rotating file handler (10MB max, 5 backups)
_file_handler = logging.handlers.RotatingFileHandler(
    filename=f"logs/pipeline_{datetime.now().strftime('%Y%m%d')}.log",
    maxBytes=10 * 1024 * 1024,  # 10 MB
    backupCount=5,
    encoding="utf-8",
)
_file_handler.setLevel(logging.INFO)

_stream_handler = logging.StreamHandler()
_stream_handler.setLevel(logging.INFO)

_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
_file_handler.setFormatter(_formatter)
_stream_handler.setFormatter(_formatter)

# Configure standard logging
logging.basicConfig(
    level=logging.INFO,
    handlers=[_file_handler, _stream_handler],
)

# Configure structlog
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
    """Get a structured logger instance."""
    return structlog.get_logger(name)


class MetricsCollector:
    """
    Thread-safe metrics collector for pipeline monitoring.

    All counter operations are protected by a threading.Lock to prevent
    race conditions when multiple ingestion threads update simultaneously.
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
        """Increment a metric counter (thread-safe)."""
        with self._lock:
            if metric in self._metrics:
                self._metrics[metric] += value

    def get_metrics(self) -> dict:
        """Get a snapshot of current metrics (thread-safe)."""
        with self._lock:
            return self._metrics.copy()

    def reset(self):
        """Reset all metrics to zero (thread-safe)."""
        with self._lock:
            self._metrics = {k: 0 for k in self._metrics}
            self.logger.info("metrics_reset")


# Global metrics instance
metrics = MetricsCollector()
