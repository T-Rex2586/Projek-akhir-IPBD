"""
Gold Layer Processor.

Periodically computes high-value business aggregated metrics (Gold layer)
by consolidating Silver layer tables (prices, sentiment, anomalies)
into clean hourly buckets.
"""
import time
import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Ensure root folder is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from storage.db_utils import calculate_and_save_gold_hourly_metrics
from monitoring.logger import get_logger, metrics

load_dotenv()
logger = get_logger(__name__)

SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT"]
PROCESS_INTERVAL_SECONDS = 300  # Run every 5 minutes


class GoldLayerProcessor:
    """Processor to build and maintain the Gold Layer."""

    def __init__(self, symbols=None):
        self.symbols = symbols or SYMBOLS
        logger.info("gold_processor_initialized", symbols=self.symbols)

    def run_cycle(self):
        """Run a single consolidation cycle for the last 6 hours."""
        logger.info("gold_processing_cycle_started")
        now = datetime.utcnow()
        
        # Round to current hour start
        current_hour_start = now.replace(minute=0, second=0, microsecond=0)
        
        # Consolidate for the past 6 hours to catch any late or backfilled data
        windows_to_process = [
            current_hour_start - timedelta(hours=i) for i in range(6)
        ]
        
        processed_count = 0
        success_count = 0
        
        for window in windows_to_process:
            for symbol in self.symbols:
                processed_count += 1
                success = calculate_and_save_gold_hourly_metrics(symbol, window)
                if success:
                    success_count += 1
                    
        logger.info("gold_processing_cycle_completed", 
                    total_attempted=processed_count, 
                    successful=success_count)
        metrics.increment("gold_runs")

    def start_loop(self):
        """Continuously run the consolidation processor."""
        logger.info("gold_processor_continuous_loop_started", interval=PROCESS_INTERVAL_SECONDS)
        while True:
            try:
                self.run_cycle()
                time.sleep(PROCESS_INTERVAL_SECONDS)
            except KeyboardInterrupt:
                logger.info("gold_processor_stopped_by_user")
                break
            except Exception as e:
                logger.error("gold_processor_error", error=str(e))
                time.sleep(60)  # Back off on error


if __name__ == "__main__":
    # Ensure tables are initialized
    from storage.db_models import init_db
    init_db()

    processor = GoldLayerProcessor()
    processor.start_loop()
