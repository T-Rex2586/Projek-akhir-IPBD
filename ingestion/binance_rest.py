"""
Binance REST API data ingestion.

Uses Binance public API endpoints (no API key required).
Fetches 24h ticker statistics and kline/candlestick data via polling,
saves raw responses to Bronze (MinIO) and parsed data to Silver (PostgreSQL).
"""
import time
import os
import sys
from datetime import datetime
from typing import List, Dict, Optional
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Add project root to path for direct execution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from monitoring.logger import get_logger, metrics
from storage.db_utils import save_price_data, save_kline_data
from dotenv import load_dotenv

load_dotenv()

logger = get_logger(__name__)

# Public Binance API — no key required
BASE_URL = "https://api.binance.com"
SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT"]
POLL_INTERVAL = 30  # seconds between polling cycles


class BinanceRestClient:
    """Client for Binance public REST API with retry logic."""

    def __init__(self, symbols: List[str] = None):
        self.symbols = symbols or SYMBOLS
        self.base_url = BASE_URL

        # Session with automatic retry on transient errors
        self.session = Session()
        retries = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retries))

        logger.info("binance_rest_client_initialized", symbols=self.symbols)

    # ──────────────────────────────────────────────────────────────────
    # Ticker (24h stats)
    # ──────────────────────────────────────────────────────────────────

    def fetch_ticker_24hr(self, symbol: str) -> Optional[Dict]:
        """Fetch 24-hour ticker statistics for a symbol."""
        try:
            resp = self.session.get(
                f"{self.base_url}/api/v3/ticker/24hr",
                params={"symbol": symbol},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

            # Save raw response to Bronze (MinIO)
            try:
                from storage.minio_utils import save_to_bronze
                save_to_bronze(
                    "binance_rest_ticker",
                    data,
                    identifier=f"{symbol}_{data.get('closeTime', '')}",
                )
            except Exception as e:
                logger.debug("bronze_ticker_save_skipped", error=str(e))

            metrics.increment("api_calls")

            return {
                "symbol": data["symbol"],
                "price": float(data["lastPrice"]),
                "volume": float(data["volume"]),
                "high_24h": float(data["highPrice"]),
                "low_24h": float(data["lowPrice"]),
                "change_24h": float(data["priceChangePercent"]),
                "timestamp": datetime.utcnow(),
            }

        except Exception as e:
            logger.error("fetch_ticker_failed", symbol=symbol, error=str(e))
            metrics.increment("errors")
            return None

    # ──────────────────────────────────────────────────────────────────
    # Kline / Candlestick
    # ──────────────────────────────────────────────────────────────────

    def fetch_klines(
        self, symbol: str, interval: str = "1m", limit: int = 10
    ) -> List[Dict]:
        """Fetch candlestick/kline data for a symbol."""
        try:
            resp = self.session.get(
                f"{self.base_url}/api/v3/klines",
                params={"symbol": symbol, "interval": interval, "limit": limit},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

            # Save raw response to Bronze (MinIO)
            try:
                from storage.minio_utils import save_to_bronze
                save_to_bronze(
                    "binance_rest_klines",
                    data,
                    identifier=f"{symbol}_{interval}_limit{limit}",
                )
            except Exception as e:
                logger.debug("bronze_klines_save_skipped", error=str(e))

            metrics.increment("api_calls")

            klines = []
            for k in data:
                klines.append({
                    "symbol": symbol,
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5]),
                    "open_time": int(k[0]),
                    "close_time": int(k[6]),
                    "interval": interval,
                })

            return klines

        except Exception as e:
            logger.error("fetch_klines_failed", symbol=symbol, error=str(e))
            metrics.increment("errors")
            return []

    # ──────────────────────────────────────────────────────────────────
    # Polling
    # ──────────────────────────────────────────────────────────────────

    def poll_all_symbols(self):
        """Poll ticker and latest kline data for all symbols."""
        logger.info("polling_started", symbols=self.symbols)

        for symbol in self.symbols:
            # 1. Fetch and save 24h ticker
            ticker = self.fetch_ticker_24hr(symbol)
            if ticker:
                save_price_data(ticker)
                metrics.increment("records_processed")
                logger.info(
                    "ticker_saved",
                    symbol=symbol,
                    price=ticker["price"],
                    change=ticker["change_24h"],
                )

            # 2. Fetch and save latest kline batch
            klines = self.fetch_klines(symbol, interval="1m", limit=5)
            saved = 0
            for kl in klines:
                if save_kline_data(kl):
                    saved += 1
            if saved:
                metrics.increment("records_processed", saved)
                logger.info("klines_saved", symbol=symbol, count=saved)

            time.sleep(0.5)  # Rate limiting between symbols

        logger.info("polling_completed", symbols_count=len(self.symbols))


def run_continuous_polling():
    """Run continuous polling loop with error recovery."""
    client = BinanceRestClient()
    logger.info("continuous_polling_started", interval=POLL_INTERVAL)

    consecutive_errors = 0

    while True:
        try:
            client.poll_all_symbols()
            consecutive_errors = 0
            logger.debug("sleeping", seconds=POLL_INTERVAL)
            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            logger.info("polling_stopped_by_user")
            break
        except Exception as e:
            consecutive_errors += 1
            backoff = min(POLL_INTERVAL * consecutive_errors, 300)
            logger.error(
                "polling_error",
                error=str(e),
                consecutive_errors=consecutive_errors,
                backoff_seconds=backoff,
            )
            metrics.increment("errors")

            # Alert on repeated failures
            if consecutive_errors >= 3:
                from monitoring.telegram_alert import send_pipeline_error_alert
                send_pipeline_error_alert(
                    component="binance_rest_poller",
                    error_msg=f"{consecutive_errors} consecutive failures: {str(e)}",
                )

            time.sleep(backoff)


if __name__ == "__main__":
    sys.path.insert(0, ".")

    # Initialize database
    from storage.db_models import init_db
    init_db()

    # Run polling
    run_continuous_polling()
