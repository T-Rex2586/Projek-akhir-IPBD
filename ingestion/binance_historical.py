"""
Binance Historical Data Fetcher - Backfill 7 days data

Fetch historical kline data dari Binance untuk training LSTM models.
Setelah backfill selesai, bisa langsung train models.

Usage:
    python ingestion/binance_historical.py --days 7
"""
import sys
import os
import requests
import time
from datetime import datetime, timedelta
from typing import List, Dict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from storage.db_utils import save_kline_data
from storage.db_models import get_session, KlineData
from monitoring.logger import get_logger

logger = get_logger(__name__)

# Binance API endpoints
BINANCE_BASE_URL = "https://api.binance.com"
KLINES_ENDPOINT = "/api/v3/klines"

# Symbols to fetch
SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'ADAUSDT']

# Kline interval
INTERVAL = '1m'  # 1-minute candles


class BinanceHistoricalFetcher:
    """Fetch historical kline data from Binance."""
    
    def __init__(self, symbols: List[str] = None, interval: str = '1m'):
        """
        Initialize fetcher.
        
        Parameters
        ----------
        symbols : List[str]
            List of trading pairs to fetch
        interval : str
            Kline interval (1m, 5m, 15m, 1h, etc.)
        """
        self.symbols = symbols or SYMBOLS
        self.interval = interval
        self.session = requests.Session()
        
        logger.info("historical_fetcher_initialized", symbols=self.symbols, interval=interval)
    
    def fetch_klines(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime = None,
        limit: int = 1000
    ) -> List[Dict]:
        """
        Fetch kline data from Binance API.
        
        Parameters
        ----------
        symbol : str
            Trading pair (e.g., BTCUSDT)
        start_time : datetime
            Start time for historical data
        end_time : datetime, optional
            End time (default: now)
        limit : int
            Max number of candles per request (max 1000)
        
        Returns
        -------
        List[Dict]
            List of kline data dictionaries
        """
        if end_time is None:
            end_time = datetime.utcnow()
        
        start_ms = int(start_time.timestamp() * 1000)
        end_ms = int(end_time.timestamp() * 1000)
        
        url = f"{BINANCE_BASE_URL}{KLINES_ENDPOINT}"
        params = {
            'symbol': symbol,
            'interval': self.interval,
            'startTime': start_ms,
            'endTime': end_ms,
            'limit': limit
        }
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            klines = response.json()
            
            result = []
            for kline in klines:
                result.append({
                    'symbol': symbol,
                    'open_time': datetime.fromtimestamp(kline[0] / 1000),
                    'open_price': float(kline[1]),
                    'high_price': float(kline[2]),
                    'low_price': float(kline[3]),
                    'close_price': float(kline[4]),
                    'volume': float(kline[5]),
                    'close_time': datetime.fromtimestamp(kline[6] / 1000),
                    'interval': self.interval
                })
            
            logger.info(
                "klines_fetched",
                symbol=symbol,
                count=len(result),
                start=start_time.isoformat(),
                end=end_time.isoformat()
            )
            
            return result
        
        except requests.exceptions.RequestException as e:
            logger.error("klines_fetch_failed", symbol=symbol, error=str(e))
            return []
    
    def backfill_symbol(self, symbol: str, days: int = 7) -> int:
        """
        Backfill historical data for a symbol.
        
        Parameters
        ----------
        symbol : str
            Trading pair
        days : int
            Number of days to backfill
        
        Returns
        -------
        int
            Total records saved
        """
        print(f"\n📊 Backfilling {symbol} - Last {days} days")
        print("="*60)
        
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days)
        
        total_saved = 0
        current_start = start_time
        
        # Binance API limit: 1000 candles per request
        # For 1m interval: 1000 minutes = ~16.7 hours per request
        max_minutes_per_request = 1000
        
        request_count = 0
        
        while current_start < end_time:
            current_end = min(
                current_start + timedelta(minutes=max_minutes_per_request),
                end_time
            )
            
            request_count += 1
            print(f"\n  Request #{request_count}")
            print(f"  Period: {current_start.strftime('%Y-%m-%d %H:%M')} to {current_end.strftime('%Y-%m-%d %H:%M')}")
            
            # Fetch klines
            klines = self.fetch_klines(symbol, current_start, current_end)
            
            if not klines:
                print(f"  ⚠️  No data received, skipping...")
                current_start = current_end
                continue
            
            # Save to database
            saved_count = 0
            for kline_data in klines:
                if save_kline_data(kline_data):
                    saved_count += 1
            
            total_saved += saved_count
            print(f"  ✅ Saved {saved_count}/{len(klines)} records")
            
            # Move to next batch
            current_start = current_end
            
            # Rate limiting: Sleep 100ms between requests
            time.sleep(0.1)
        
        print(f"\n{'='*60}")
        print(f"  ✅ {symbol} Backfill Complete!")
        print(f"  Total saved: {total_saved} records")
        print(f"{'='*60}")
        
        return total_saved
    
    def backfill_all(self, days: int = 7):
        """
        Backfill historical data for all symbols.
        
        Parameters
        ----------
        days : int
            Number of days to backfill
        """
        print(f"\n{'='*60}")
        print(f"  Binance Historical Data Backfill")
        print(f"{'='*60}")
        print(f"  Symbols: {', '.join(self.symbols)}")
        print(f"  Period: Last {days} days")
        print(f"  Interval: {self.interval}")
        print(f"{'='*60}\n")
        
        total_all = 0
        
        for i, symbol in enumerate(self.symbols, 1):
            print(f"\n[{i}/{len(self.symbols)}] Processing {symbol}...")
            
            saved = self.backfill_symbol(symbol, days)
            total_all += saved
            
            # Sleep between symbols
            if i < len(self.symbols):
                print(f"\n⏳ Waiting 2 seconds before next symbol...")
                time.sleep(2)
        
        print(f"\n\n{'='*60}")
        print(f"  🎉 BACKFILL COMPLETE!")
        print(f"{'='*60}")
        print(f"  Total records saved: {total_all}")
        print(f"  Symbols processed: {len(self.symbols)}")
        print(f"{'='*60}\n")
        
        # Show data summary
        self.show_data_summary()
    
    def show_data_summary(self):
        """Show database data summary after backfill."""
        session = get_session()
        
        try:
            print("\n📊 Database Summary:")
            print("="*60)
            
            for symbol in self.symbols:
                count = session.query(KlineData).filter(
                    KlineData.symbol == symbol
                ).count()
                
                if count > 0:
                    latest = session.query(KlineData).filter(
                        KlineData.symbol == symbol
                    ).order_by(KlineData.close_time.desc()).first()
                    
                    oldest = session.query(KlineData).filter(
                        KlineData.symbol == symbol
                    ).order_by(KlineData.close_time.asc()).first()
                    
                    print(f"\n  {symbol}:")
                    print(f"    Records: {count}")
                    print(f"    From: {oldest.close_time}")
                    print(f"    To: {latest.close_time}")
            
            print(f"\n{'='*60}")
            print(f"\n✅ Data ready for training!")
            print(f"   Run: .\\make.bat train-all\n")
        
        finally:
            session.close()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Backfill historical data from Binance for LSTM training"
    )
    parser.add_argument(
        '--days',
        type=int,
        default=7,
        help='Number of days to backfill (default: 7)'
    )
    parser.add_argument(
        '--symbols',
        type=str,
        default=','.join(SYMBOLS),
        help=f'Comma-separated symbols (default: {",".join(SYMBOLS)})'
    )
    parser.add_argument(
        '--interval',
        type=str,
        default='1m',
        help='Kline interval (default: 1m)'
    )
    
    args = parser.parse_args()
    
    symbols = [s.strip().upper() for s in args.symbols.split(',')]
    
    fetcher = BinanceHistoricalFetcher(symbols=symbols, interval=args.interval)
    fetcher.backfill_all(days=args.days)


if __name__ == "__main__":
    main()
