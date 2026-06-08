"""
Sync KlineData to PriceData for dashboard compatibility.

This script converts candlestick data from WebSocket ingestion
to simplified price data for dashboard consumption.
"""
import sys
import os
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from storage.db_models import get_session, KlineData, PriceData
from monitoring.logger import get_logger

logger = get_logger(__name__)


def sync_kline_to_price(symbol: str = None, hours: int = 1):
    """
    Convert recent KlineData to PriceData for dashboard compatibility.
    
    Args:
        symbol: Specific symbol to sync (e.g., 'BTCUSDT'), or None for all
        hours: How many hours back to sync
    """
    session = get_session()
    try:
        since = datetime.utcnow() - timedelta(hours=hours)
        
        # Get klines that don't have corresponding price data
        kline_query = session.query(KlineData).filter(
            KlineData.close_time >= since
        )
        
        if symbol:
            kline_query = kline_query.filter(KlineData.symbol == symbol.upper())
        
        klines = kline_query.order_by(KlineData.close_time.asc()).all()
        
        synced_count = 0
        for kline in klines:
            # Check if price data already exists
            existing = session.query(PriceData).filter(
                PriceData.symbol == kline.symbol,
                PriceData.timestamp == kline.close_time
            ).first()
            
            if not existing:
                price_data = PriceData(
                    symbol=kline.symbol,
                    price=kline.close_price,
                    volume=kline.volume,
                    high_24h=kline.high_price,  # Approximate
                    low_24h=kline.low_price,   # Approximate  
                    change_24h=None,           # Would need calculation
                    timestamp=kline.close_time
                )
                session.add(price_data)
                synced_count += 1
        
        session.commit()
        
        if synced_count > 0:
            logger.info("kline_to_price_sync_completed", 
                       symbol=symbol or "ALL", 
                       synced=synced_count, 
                       hours=hours)
        
        return synced_count
    
    except Exception as e:
        session.rollback()
        logger.error("kline_to_price_sync_failed", error=str(e))
        return 0
    finally:
        session.close()


def sync_all_symbols():
    """Sync all symbols from last hour."""
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT"]
    total_synced = 0
    
    for symbol in symbols:
        synced = sync_kline_to_price(symbol, hours=2)  # 2 hours for safety
        total_synced += synced
    
    logger.info("bulk_sync_completed", total_synced=total_synced)
    return total_synced


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Sync KlineData to PriceData")
    parser.add_argument("--symbol", help="Specific symbol to sync")
    parser.add_argument("--hours", type=int, default=1, help="Hours to look back")
    parser.add_argument("--all", action="store_true", help="Sync all symbols")
    
    args = parser.parse_args()
    
    if args.all:
        total = sync_all_symbols()
        print(f"✅ Synced {total} records across all symbols")
    else:
        synced = sync_kline_to_price(args.symbol, args.hours)
        symbol_str = args.symbol or "ALL"
        print(f"✅ Synced {synced} records for {symbol_str}")