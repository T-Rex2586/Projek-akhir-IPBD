"""
Quick diagnostic script to check real-time data status
"""
from storage.db_models import get_session, PriceData, KlineData
from datetime import datetime, timedelta
from sqlalchemy import func, desc

def check_data_status():
    """Check what data is actually in the database"""
    session = get_session()
    
    print("\n" + "="*60)
    print("📊 DATABASE REAL-TIME CHECK")
    print("="*60)
    
    try:
        # Check PriceData
        print("\n1️⃣  PRICE DATA (Last 10 records):")
        print("-" * 60)
        
        latest_prices = session.query(PriceData).order_by(
            desc(PriceData.timestamp)
        ).limit(10).all()
        
        if latest_prices:
            for p in latest_prices:
                age_minutes = (datetime.utcnow() - p.timestamp).total_seconds() / 60
                print(f"  {p.symbol:10} | ${p.price:>10,.2f} | {p.timestamp} | {age_minutes:.1f}m ago")
        else:
            print("  ❌ NO PRICE DATA FOUND")
        
        # Statistics per symbol
        print("\n2️⃣  DATA COUNT PER SYMBOL:")
        print("-" * 60)
        
        symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'ADAUSDT']
        for symbol in symbols:
            count = session.query(func.count(PriceData.id)).filter(
                PriceData.symbol == symbol
            ).scalar()
            
            latest = session.query(PriceData).filter(
                PriceData.symbol == symbol
            ).order_by(desc(PriceData.timestamp)).first()
            
            if latest:
                age_hours = (datetime.utcnow() - latest.timestamp).total_seconds() / 3600
                status = "✅" if age_hours < 1 else "⚠️" if age_hours < 24 else "❌"
                print(f"  {status} {symbol:10} | Count: {count:>6} | Latest: {latest.timestamp} ({age_hours:.1f}h ago)")
            else:
                print(f"  ❌ {symbol:10} | Count: 0 | NO DATA")
        
        # Check last 24 hours
        print("\n3️⃣  LAST 24 HOURS DATA:")
        print("-" * 60)
        
        since_24h = datetime.utcnow() - timedelta(hours=24)
        for symbol in symbols:
            count_24h = session.query(func.count(PriceData.id)).filter(
                PriceData.symbol == symbol,
                PriceData.timestamp >= since_24h
            ).scalar()
            
            print(f"  {symbol:10} | {count_24h:>4} records in last 24h")
        
        # Check KlineData
        print("\n4️⃣  KLINE DATA (Last 5 records):")
        print("-" * 60)
        
        latest_klines = session.query(KlineData).order_by(
            desc(KlineData.close_time)
        ).limit(5).all()
        
        if latest_klines:
            for k in latest_klines:
                age_minutes = (datetime.utcnow() - k.close_time).total_seconds() / 60
                print(f"  {k.symbol:10} | Close: ${k.close_price:>10,.2f} | {k.close_time} | {age_minutes:.1f}m ago")
        else:
            print("  ⚠️  NO KLINE DATA FOUND")
        
        # Ingestion status check
        print("\n5️⃣  INGESTION STATUS:")
        print("-" * 60)
        
        # Check if data is flowing
        latest_any = session.query(PriceData).order_by(
            desc(PriceData.timestamp)
        ).first()
        
        if latest_any:
            age_seconds = (datetime.utcnow() - latest_any.timestamp).total_seconds()
            if age_seconds < 60:
                print(f"  ✅ REAL-TIME: Data flowing! (last update {age_seconds:.0f}s ago)")
            elif age_seconds < 300:
                print(f"  ⚠️  DELAYED: Last update {age_seconds/60:.1f}m ago")
            elif age_seconds < 3600:
                print(f"  ❌ STALE: Last update {age_seconds/60:.1f}m ago - Ingestion may be stopped")
            else:
                print(f"  ❌ OLD DATA: Last update {age_seconds/3600:.1f}h ago - Ingestion NOT running")
        else:
            print("  ❌ NO DATA: Database is empty - Run backfill_data.py first")
        
        print("\n" + "="*60)
        print("💡 RECOMMENDATIONS:")
        print("="*60)
        
        if not latest_prices:
            print("  1. Run: python backfill_data.py")
            print("  2. Then: python ingestion/binance_rest.py")
        elif latest_any and (datetime.utcnow() - latest_any.timestamp).total_seconds() > 300:
            print("  1. Check if ingestion is running:")
            print("     - python ingestion/binance_rest.py")
            print("     - python ingestion/binance_websocket.py")
            print("  2. Check network/VPN connection")
            print("  3. Check logs: tail -f logs/pipeline_*.log")
        else:
            print("  ✅ Everything looks good!")
            print("  Dashboard should show real-time data now")
        
        print()
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
    finally:
        session.close()

if __name__ == "__main__":
    check_data_status()
