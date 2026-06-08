"""
Binance WebSocket streaming for real-time price data.

Uses Binance public WebSocket API (no API key required).
Streams kline (candlestick) data for configured symbols and stores
closed candles to Silver layer (PostgreSQL) and raw data to Bronze (MinIO).
Includes automatic reconnection with exponential backoff.
"""
import asyncio
import json
import time
import os
import sys
from datetime import datetime
from typing import Dict
import websockets

# Add project root to path for direct execution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from monitoring.logger import get_logger, metrics
from storage.db_utils import save_kline_data
from dotenv import load_dotenv

load_dotenv()

logger = get_logger(__name__)

# Public endpoints — no API key required
SYMBOLS = ["btcusdt", "ethusdt", "bnbusdt", "solusdt", "adausdt"]
WS_BASE_URL = "wss://stream.binance.com:9443/ws"

# Reconnection settings
MAX_RECONNECT_DELAY = 120   # max seconds between reconnect attempts
INITIAL_RECONNECT_DELAY = 2 # first reconnect delay


class BinanceWebSocketClient:
    """Client for Binance public WebSocket streams with auto-reconnect."""

    def __init__(self, symbols: list = None):
        self.symbols = [s.lower() for s in (symbols or SYMBOLS)]
        self.ws_url = WS_BASE_URL
        logger.info("binance_websocket_client_initialized", symbols=self.symbols)

    async def stream_kline(self, symbol: str, interval: str = "1m"):
        """Stream candlestick data for a symbol with auto-reconnect."""
        url = f"{self.ws_url}/{symbol}@kline_{interval}"
        reconnect_delay = INITIAL_RECONNECT_DELAY

        while True:
            try:
                logger.info("kline_stream_connecting", symbol=symbol, interval=interval)
                async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                    logger.info("kline_stream_connected", symbol=symbol)
                    reconnect_delay = INITIAL_RECONNECT_DELAY  # reset on success

                    while True:
                        msg = await ws.recv()
                        data = json.loads(msg)

                        kline = data.get("k")
                        if not kline:
                            continue

                        # Only process and persist CLOSED klines (x=True)
                        if kline.get("x"):
                            kline_data = {
                                "symbol": kline["s"],
                                "open": float(kline["o"]),
                                "high": float(kline["h"]),
                                "low": float(kline["l"]),
                                "close": float(kline["c"]),
                                "volume": float(kline["v"]),
                                "open_time": int(kline["t"]),
                                "close_time": int(kline["T"]),
                                "interval": interval,
                            }

                            # Save raw closed kline to Bronze (MinIO)
                            try:
                                from storage.minio_utils import save_to_bronze
                                save_to_bronze(
                                    "binance_websocket",
                                    data,
                                    identifier=f"{symbol}_{kline_data['close_time']}",
                                )
                            except Exception as e:
                                logger.debug("bronze_save_skipped", error=str(e))

                            # Save to Silver (PostgreSQL)
                            if save_kline_data(kline_data):
                                # Also save to PriceData for dashboard compatibility
                                from storage.db_utils import save_price_data
                                price_data = {
                                    'symbol': kline_data['symbol'],
                                    'price': kline_data['close'],
                                    'volume': kline_data['volume'],
                                    'timestamp': datetime.fromtimestamp(kline_data['close_time'] / 1000)
                                }
                                save_price_data(price_data)
                                
                                metrics.increment("records_processed")
                                logger.info(
                                    "kline_received",
                                    symbol=kline_data["symbol"],
                                    close=kline_data["close"],
                                    volume=kline_data["volume"],
                                )

                            # Check for anomalies
                            await self._check_price_anomaly(kline_data)

            except websockets.exceptions.ConnectionClosed as e:
                logger.warning(
                    "websocket_connection_closed",
                    symbol=symbol,
                    code=e.code,
                    reason=str(e.reason),
                )
            except asyncio.CancelledError:
                logger.info("kline_stream_cancelled", symbol=symbol)
                return
            except Exception as e:
                logger.error("kline_stream_error", symbol=symbol, error=str(e))
                metrics.increment("errors")

            # Reconnect with exponential backoff
            logger.info(
                "websocket_reconnecting",
                symbol=symbol,
                delay_seconds=reconnect_delay,
            )
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, MAX_RECONNECT_DELAY)

    async def _check_price_anomaly(self, kline_data: Dict):
        """Check for price anomalies within a single kline."""
        try:
            open_price = kline_data["open"]
            close_price = kline_data["close"]
            if open_price == 0:
                return

            price_change = (close_price - open_price) / open_price
            abs_change = abs(price_change)
            PRICE_CHANGE_THRESHOLD = 0.03  # 3%

            if abs_change > PRICE_CHANGE_THRESHOLD:
                from storage.db_utils import save_anomaly_event

                direction = "surged" if price_change > 0 else "dropped"
                anomaly = {
                    "event_type": "price_spike",
                    "symbol": kline_data["symbol"],
                    "description": (
                        f"{kline_data['symbol']} {direction} "
                        f"{abs_change * 100:.2f}% in 1 minute "
                        f"(${open_price:,.2f} → ${close_price:,.2f})"
                    ),
                    "severity": "high" if abs_change > 0.05 else "medium",
                    "value": price_change,
                    "threshold": PRICE_CHANGE_THRESHOLD,
                }

                save_anomaly_event(anomaly, send_alert=False)
                metrics.increment("anomalies_detected")
                logger.warning(
                    "price_anomaly_detected",
                    symbol=kline_data["symbol"],
                    change_pct=price_change * 100,
                )

                # Send Telegram price spike alert
                from monitoring.telegram_alert import send_price_spike_alert
                send_price_spike_alert(
                    symbol=kline_data["symbol"],
                    price_change_pct=price_change * 100,
                    current_price=close_price,
                )

        except Exception as e:
            logger.error("anomaly_check_failed", error=str(e))

    async def stream_all_symbols(self):
        """Stream klines for all symbols concurrently."""
        tasks = [self.stream_kline(symbol) for symbol in self.symbols]
        await asyncio.gather(*tasks, return_exceptions=True)


async def run_websocket_streams():
    """Run WebSocket streams with startup notification."""
    from monitoring.telegram_alert import send_startup_notification

    client = BinanceWebSocketClient()
    logger.info("websocket_streams_started", symbols=client.symbols)

    print(f"\n{'='*60}")
    print(f"  Binance WebSocket Streams")
    print(f"  Symbols: {', '.join(client.symbols)}")
    print(f"  WS URL: {WS_BASE_URL}")
    print(f"  Reconnect delay: {INITIAL_RECONNECT_DELAY}s (max {MAX_RECONNECT_DELAY}s)")
    print(f"{'='*60}\n")

    send_startup_notification()

    try:
        await client.stream_all_symbols()
    except KeyboardInterrupt:
        logger.info("websocket_streams_stopped_by_user")
    except Exception as e:
        logger.error("websocket_streams_error", error=str(e))


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")

    # Initialize database
    from storage.db_models import init_db
    init_db()

    # Run WebSocket streams
    asyncio.run(run_websocket_streams())
