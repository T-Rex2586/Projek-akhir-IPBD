"""
Centralized logging configuration for the pipeline.
"""
import logging
import structlog
from datetime import datetime
import os

# Create logs directory if not exists
os.makedirs("logs", exist_ok=True)

# Configure standard logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(f"logs/pipeline_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler()
    ]
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

# Metrics tracking
class MetricsCollector:
    """Simple metrics collector for monitoring."""
    
    def __init__(self):
        self.metrics = {
            "records_processed": 0,
            "errors": 0,
            "anomalies_detected": 0,
            "api_calls": 0,
            "gold_runs": 0,
            "telegram_alerts_sent": 0,
        }
        self.logger = get_logger("metrics")
    
    def increment(self, metric: str, value: int = 1):
        """Increment a metric counter."""
        if metric in self.metrics:
            self.metrics[metric] += value
            self.logger.debug(f"metric_updated", metric=metric, value=self.metrics[metric])
    
    def get_metrics(self) -> dict:
        """Get current metrics."""
        return self.metrics.copy()
    
    def reset(self):
        """Reset all metrics."""
        self.metrics = {k: 0 for k in self.metrics}
        self.logger.info("metrics_reset")

# Global metrics instance
metrics = MetricsCollector()
