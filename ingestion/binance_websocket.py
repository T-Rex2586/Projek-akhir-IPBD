"""
Modul akuisisi data waktu nyata melalui antarmuka Binance WebSocket.
Secara asinkron mengumpulkan data kandil (kline), mendeteksi anomali volume dan harga,
serta menyimpan data tersebut pada lapisan penyimpanan yang sesuai.
"""
import asyncio
import json
import time
import os
import sys
from datetime import datetime
import pytz
from typing import Dict
import websockets

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from monitoring.logger import get_logger, metrics
from storage.db_utils import save_kline_data
from dotenv import load_dotenv

load_dotenv()
logger = get_logger(__name__)

SYMBOLS = ["btcusdt"]
WS_BASE_URL = "wss://data-stream.binance.vision/ws"

MAX_RECONNECT_DELAY = 120
INITIAL_RECONNECT_DELAY = 2

class BinanceWebSocketClient:
    """Klien terpusat untuk mengelola koneksi WebSocket dengan mekanisme pemulihan otomatis (auto-reconnect)."""

    def __init__(self, symbols: list = None):
        self.symbols = [s.lower() for s in (symbols or SYMBOLS)]
        self.ws_url = WS_BASE_URL
        logger.info("binance_websocket_client_initialized", symbols=self.symbols)

    async def stream_kline(self, symbol: str, interval: str = "1s"):
        """Membuka aliran data kandil untuk suatu instrumen kripto."""
        url = f"{self.ws_url}/{symbol}@kline_{interval}"
        reconnect_delay = INITIAL_RECONNECT_DELAY

        while True:
            try:
                logger.info("kline_stream_connecting", symbol=symbol, interval=interval)
                async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                    logger.info("kline_stream_connected", symbol=symbol)
                    reconnect_delay = INITIAL_RECONNECT_DELAY

                    while True:
                        msg = await ws.recv()
                        data = json.loads(msg)

                        kline = data.get("k")
                        if not kline:
                            continue

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

                            try:
                                from storage.minio_utils import save_to_bronze
                                save_to_bronze(
                                    "binance_websocket",
                                    data,
                                    identifier=f"{symbol}_{kline_data['close_time']}",
                                )
                            except Exception as e:
                                logger.debug("bronze_save_skipped", error=str(e))

                            if save_kline_data(kline_data):
                                wib = pytz.timezone('Asia/Jakarta')
                                dt_utc = datetime.fromtimestamp(kline_data['close_time'] / 1000, tz=pytz.UTC)
                                dt_wib = dt_utc.astimezone(wib)

                                from storage.db_utils import save_price_data
                                price_data = {
                                    'symbol': kline_data['symbol'],
                                    'price': kline_data['close'],
                                    'volume': kline_data['volume'],
                                    'timestamp': dt_wib
                                }
                                save_price_data(price_data)
                                
                                metrics.increment("records_processed")

                            await self._check_price_anomaly(kline_data)

            except websockets.exceptions.ConnectionClosed as e:
                logger.warning("websocket_connection_closed", symbol=symbol, code=e.code, reason=str(e.reason))
            except asyncio.CancelledError:
                logger.info("kline_stream_cancelled", symbol=symbol)
                return
            except Exception as e:
                logger.error("kline_stream_error", symbol=symbol, error=str(e))
                metrics.increment("errors")

            logger.info("websocket_reconnecting", symbol=symbol, delay_seconds=reconnect_delay)
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, MAX_RECONNECT_DELAY)

    async def _check_price_anomaly(self, kline_data: Dict):
        """Mengevaluasi secara seketika keberadaan anomali harga atau transaksi dengan volume signifikan (Whale)."""
        try:
            open_price = kline_data["open"]
            close_price = kline_data["close"]
            if open_price == 0:
                return

            price_change = (close_price - open_price) / open_price
            abs_change = abs(price_change)
            PRICE_CHANGE_THRESHOLD = 0.03

            if abs_change > PRICE_CHANGE_THRESHOLD:
                from storage.db_utils import save_anomaly_event

                direction = "melonjak" if price_change > 0 else "anjlok"
                anomaly = {
                    "event_type": "price_spike",
                    "symbol": kline_data["symbol"],
                    "description": (
                        f"{kline_data['symbol']} {direction} "
                        f"{abs_change * 100:.2f}% dalam 1 detik "
                        f"(${open_price:,.2f} → ${close_price:,.2f})"
                    ),
                    "severity": "high" if abs_change > 0.05 else "medium",
                    "value": float(price_change * 100),
                    "threshold": PRICE_CHANGE_THRESHOLD,
                }

                save_anomaly_event(anomaly, send_alert=False)
                metrics.increment("anomalies_detected")
                logger.warning("price_anomaly_detected", symbol=kline_data["symbol"], change_pct=price_change * 100)
                
            volume = float(kline_data.get("volume", 0))
            notional_value = volume * close_price
            WHALE_THRESHOLD = 600000.0
            
            if notional_value > WHALE_THRESHOLD:
                from storage.db_utils import save_anomaly_event
                
                whale_anomaly = {
                    "event_type": "whale_trade",
                    "symbol": kline_data["symbol"],
                    "description": f"Transaksi masif terdeteksi! {volume:.2f} koin ditransaksikan (${notional_value:,.0f})",
                    "severity": "high" if notional_value > 1000000 else "medium",
                    "value": float(notional_value),
                    "threshold": WHALE_THRESHOLD,
                }
                save_anomaly_event(whale_anomaly, send_alert=True)
                metrics.increment("whale_trades_detected")
                logger.warning("whale_trade_detected", symbol=kline_data["symbol"], notional=notional_value)

                from monitoring.telegram_alert import send_price_spike_alert
                send_price_spike_alert(
                    symbol=kline_data["symbol"],
                    price_change_pct=price_change * 100,
                    current_price=close_price,
                )

        except Exception as e:
            logger.error("anomaly_check_failed", error=str(e))

    async def stream_all_symbols(self):
        """Memulai pengumpulan data secara paralel (concurrent) untuk seluruh instrumen."""
        tasks = [self.stream_kline(symbol) for symbol in self.symbols]
        await asyncio.gather(*tasks, return_exceptions=True)


async def run_websocket_streams():
    """Mengeksekusi aliran koneksi serta mengirimkan sinyal inisialisasi pada layanan pemantauan."""
    from monitoring.telegram_alert import send_startup_notification

    client = BinanceWebSocketClient()
    logger.info("websocket_streams_started", symbols=client.symbols)

    send_startup_notification()

    try:
        await client.stream_all_symbols()
    except KeyboardInterrupt:
        logger.info("websocket_streams_stopped_by_user")
    except Exception as e:
        logger.error("websocket_streams_error", error=str(e))


if __name__ == "__main__":
    from storage.db_models import init_db
    init_db()
    asyncio.run(run_websocket_streams())
