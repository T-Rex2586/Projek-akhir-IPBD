"""
Reset database untuk fix timezone issue.

Script ini akan:
1. Drop semua data dari tabel KlineData dan PriceData
2. Biarkan struktur tabel tetap ada
3. WebSocket akan mulai insert data baru dengan UTC yang benar
"""
import sys
import os

sys.path.insert(0, '.')

from storage.db_models import get_session, KlineData, PriceData, NewsArticle, AnomalyEvent
from monitoring.timezone_utils import now_wib, format_wib

def reset_price_data():
    """Reset price and kline data (keep news and anomalies)."""
    print("\n🗑️  RESET DATABASE")
    print("=" * 60)
    print(f"Time: {format_wib(now_wib())}")
    print("\nThis will DELETE:")
    print("  ❌ All KlineData (candlestick data)")
    print("  ❌ All PriceData (price history)")
    print("\nThis will KEEP:")
    print("  ✅ NewsArticle (news data)")
    print("  ✅ AnomalyEvent (anomaly alerts)")
    print("  ✅ Database structure (tables)")
    
    session = get_session()
    try:
        # Count records
        kline_count = session.query(KlineData).count()
        price_count = session.query(PriceData).count()
        news_count = session.query(NewsArticle).count()
        anomaly_count = session.query(AnomalyEvent).count()
        
        print(f"\n📊 Current Database:")
        print(f"   • KlineData: {kline_count:,} records")
        print(f"   • PriceData: {price_count:,} records")
        print(f"   • NewsArticle: {news_count:,} records (will keep)")
        print(f"   • AnomalyEvent: {anomaly_count:,} records (will keep)")
        
        if kline_count == 0 and price_count == 0:
            print("\n✅ No price data to delete")
            return True
        
        # Confirm
        print("\n⚠️  WARNING: This action cannot be undone!")
        response = input("\nType 'yes' to proceed with reset: ")
        
        if response.lower() != 'yes':
            print("\n❌ Reset cancelled")
            return False
        
        print("\n🔄 Deleting data...")
        
        # Delete all klines
        deleted_klines = session.query(KlineData).delete()
        print(f"   ✅ Deleted {deleted_klines:,} KlineData records")
        
        # Delete all prices
        deleted_prices = session.query(PriceData).delete()
        print(f"   ✅ Deleted {deleted_prices:,} PriceData records")
        
        session.commit()
        
        print("\n🎉 DATABASE RESET SUCCESSFUL!")
        print("\n📋 Next Steps:")
        print("1. Start WebSocket ingestion:")
        print("   python ingestion/binance_websocket.py")
        print("\n2. Wait 2-3 minutes for fresh data with correct UTC timestamps")
        print("\n3. Restart API server:")
        print("   python api/main.py")
        print("\n4. Refresh dashboard - timestamps will be correct!")
        
        return True
        
    except Exception as e:
        session.rollback()
        print(f"\n❌ Error: {e}")
        return False
    finally:
        session.close()

def main():
    try:
        if reset_price_data():
            print("\n✅ Ready for fresh data!")
        else:
            print("\n❌ Reset failed or cancelled")
    except KeyboardInterrupt:
        print("\n\n❌ Cancelled by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")

if __name__ == "__main__":
    main()
