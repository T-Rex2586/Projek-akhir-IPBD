"""
Fix timezone data in database.

This script:
1. Deletes recent data with wrong timezone (last 24 hours)
2. Allows WebSocket to insert fresh data with correct UTC timestamps
"""
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, '.')

from storage.db_models import get_session, KlineData, PriceData
from monitoring.timezone_utils import now_wib, format_wib

def clean_recent_data():
    """Delete recent data to allow fresh ingestion with correct timezone."""
    print("\n🧹 Cleaning recent data with incorrect timezone...")
    
    session = get_session()
    try:
        # Delete last 24 hours of data
        since = datetime.utcnow() - timedelta(hours=24)
        
        # Count before delete
        kline_count = session.query(KlineData).filter(
            KlineData.close_time >= since
        ).count()
        
        price_count = session.query(PriceData).filter(
            PriceData.timestamp >= since
        ).count()
        
        print(f"📊 Found {kline_count} kline records and {price_count} price records from last 24h")
        
        if kline_count == 0 and price_count == 0:
            print("✅ No recent data to clean")
            return True
        
        # Ask for confirmation
        response = input("⚠️  Delete this data to allow fresh ingestion? (yes/no): ")
        if response.lower() != 'yes':
            print("❌ Cancelled")
            return False
        
        # Delete klines
        session.query(KlineData).filter(
            KlineData.close_time >= since
        ).delete()
        
        # Delete prices
        session.query(PriceData).filter(
            PriceData.timestamp >= since
        ).delete()
        
        session.commit()
        
        print(f"✅ Deleted {kline_count} kline records")
        print(f"✅ Deleted {price_count} price records")
        print("\n💡 Now restart WebSocket ingestion to get fresh data:")
        print("   python ingestion/binance_websocket.py")
        
        return True
        
    except Exception as e:
        session.rollback()
        print(f"❌ Error: {e}")
        return False
    finally:
        session.close()

def show_current_data():
    """Show current data timestamps for debugging."""
    print("\n🔍 Current Data Status")
    print("=" * 60)
    
    session = get_session()
    try:
        # Latest klines
        latest_klines = session.query(KlineData).order_by(
            KlineData.close_time.desc()
        ).limit(5).all()
        
        if latest_klines:
            print("\n📊 Latest KlineData:")
            for k in latest_klines:
                print(f"   {k.symbol}: {k.close_time} (UTC stored)")
        else:
            print("\n📊 No KlineData found")
        
        # Latest prices
        latest_prices = session.query(PriceData).order_by(
            PriceData.timestamp.desc()
        ).limit(5).all()
        
        if latest_prices:
            print("\n💰 Latest PriceData:")
            for p in latest_prices:
                print(f"   {p.symbol}: {p.timestamp} (UTC stored)")
        else:
            print("\n💰 No PriceData found")
        
        print(f"\n🕐 Current UTC: {datetime.utcnow()}")
        print(f"🕐 Current WIB: {format_wib(now_wib())}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        session.close()

def main():
    print("🔧 TIMEZONE DATA FIX TOOL")
    print("=" * 60)
    print(f"Time: {format_wib(now_wib())}")
    
    # Show current state
    show_current_data()
    
    # Clean data
    print("\n" + "=" * 60)
    if clean_recent_data():
        print("\n✅ SUCCESS!")
        print("\nNext steps:")
        print("1. Restart WebSocket: python ingestion/binance_websocket.py")
        print("2. Wait 2-3 minutes for fresh data")
        print("3. Restart API: python api/main.py")
        print("4. Restart Dashboard: streamlit run dashboard/app.py")
        print("\n💡 Fresh data will have correct UTC timestamps!")
    else:
        print("\n❌ Fix cancelled or failed")

if __name__ == "__main__":
    main()
