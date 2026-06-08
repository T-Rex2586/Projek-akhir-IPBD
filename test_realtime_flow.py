"""
Test script to verify real-time data flow from WebSocket to Dashboard.

This script:
1. Checks if WebSocket data is being ingested
2. Verifies API endpoints are working
3. Tests dashboard data availability
4. Shows latest data timestamps
"""
import os
import sys
import time
from datetime import datetime, timedelta

sys.path.insert(0, '.')

from storage.db_models import get_session, KlineData, PriceData
from monitoring.timezone_utils import now_wib, format_wib
from dotenv import load_dotenv

load_dotenv()

def check_websocket_data():
    """Check if WebSocket is ingesting fresh data."""
    print("\n🔍 Checking WebSocket ingestion...")
    session = get_session()
    
    try:
        # Check for recent kline data (last 5 minutes)
        since = datetime.utcnow() - timedelta(minutes=5)
        recent_klines = session.query(KlineData).filter(
            KlineData.close_time >= since
        ).order_by(KlineData.close_time.desc()).limit(10).all()
        
        if recent_klines:
            print(f"✅ Found {len(recent_klines)} recent kline records")
            latest = recent_klines[0]
            print(f"   Latest: {latest.symbol} at ${latest.close_price:.2f} ({latest.close_time})")
            
            # Check symbols
            symbols = set([k.symbol for k in recent_klines])
            print(f"   Symbols: {', '.join(symbols)}")
            
            return True
        else:
            print("❌ No recent WebSocket data found")
            return False
            
    except Exception as e:
        print(f"❌ Error checking WebSocket data: {e}")
        return False
    finally:
        session.close()

def check_price_data_sync():
    """Check if KlineData is being synced to PriceData."""
    print("\n🔍 Checking PriceData sync...")
    session = get_session()
    
    try:
        # Check for recent price data
        since = datetime.utcnow() - timedelta(minutes=5)
        recent_prices = session.query(PriceData).filter(
            PriceData.timestamp >= since
        ).order_by(PriceData.timestamp.desc()).limit(10).all()
        
        if recent_prices:
            print(f"✅ Found {len(recent_prices)} recent price records")
            latest = recent_prices[0]
            print(f"   Latest: {latest.symbol} at ${latest.price:.2f} ({latest.timestamp})")
            return True
        else:
            print("⚠️  No recent PriceData found - running sync...")
            # Try to sync
            from processing.kline_to_price_sync import sync_all_symbols
            synced = sync_all_symbols()
            print(f"   Synced {synced} records")
            return synced > 0
            
    except Exception as e:
        print(f"❌ Error checking PriceData: {e}")
        return False
    finally:
        session.close()

def check_api_endpoints():
    """Test API endpoints."""
    print("\n🔍 Testing API endpoints...")
    
    import requests
    
    api_url = os.getenv("API_BASE_URL", "http://localhost:8001")
    api_key = os.getenv("API_KEY", "dev-api-key")
    headers = {"X-API-Key": api_key}
    
    try:
        # Test health endpoint
        response = requests.get(f"{api_url}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Health endpoint working")
        else:
            print(f"❌ Health endpoint failed: {response.status_code}")
            return False
        
        # Test prices endpoint
        response = requests.get(f"{api_url}/prices/BTCUSDT", headers=headers, params={"hours": 1}, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Prices endpoint working - {len(data)} records for BTCUSDT")
            if data:
                latest = data[-1]
                print(f"   Latest: ${latest['price']:.2f} at {latest['timestamp']}")
            return len(data) > 0
        else:
            print(f"❌ Prices endpoint failed: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to API at {api_url}")
        print("   Make sure API server is running: python api/main.py")
        return False
    except Exception as e:
        print(f"❌ API test error: {e}")
        return False

def check_dashboard_requirements():
    """Check if dashboard requirements are met."""
    print("\n🔍 Checking dashboard requirements...")
    
    try:
        import streamlit
        import plotly
        import pandas
        print("✅ Dashboard dependencies installed")
    except ImportError as e:
        print(f"❌ Missing dashboard dependency: {e}")
        return False
    
    # Check if timezone utils are working
    try:
        current_wib = now_wib()
        wib_formatted = format_wib(current_wib)
        print(f"✅ WIB timezone working: {wib_formatted}")
    except Exception as e:
        print(f"❌ WIB timezone error: {e}")
        return False
    
    return True

def show_data_summary():
    """Show summary of available data."""
    print("\n📊 Data Summary")
    print("=" * 50)
    
    session = get_session()
    try:
        # Kline data summary
        kline_count = session.query(KlineData).count()
        if kline_count > 0:
            latest_kline = session.query(KlineData).order_by(KlineData.close_time.desc()).first()
            oldest_kline = session.query(KlineData).order_by(KlineData.close_time.asc()).first()
            print(f"KlineData: {kline_count:,} records")
            print(f"  Range: {oldest_kline.close_time} to {latest_kline.close_time}")
            print(f"  Latest: {latest_kline.symbol} ${latest_kline.close_price:.2f}")
        else:
            print("KlineData: No records")
        
        # Price data summary  
        price_count = session.query(PriceData).count()
        if price_count > 0:
            latest_price = session.query(PriceData).order_by(PriceData.timestamp.desc()).first()
            oldest_price = session.query(PriceData).order_by(PriceData.timestamp.asc()).first()
            print(f"PriceData: {price_count:,} records")
            print(f"  Range: {oldest_price.timestamp} to {latest_price.timestamp}")
            print(f"  Latest: {latest_price.symbol} ${latest_price.price:.2f}")
        else:
            print("PriceData: No records")
            
    except Exception as e:
        print(f"Error getting summary: {e}")
    finally:
        session.close()

def main():
    """Run all checks."""
    print("🚀 Testing Real-time Data Flow")
    print("=" * 50)
    print(f"Time: {format_wib(now_wib())}")
    
    # Run all checks
    websocket_ok = check_websocket_data()
    price_sync_ok = check_price_data_sync()
    api_ok = check_api_endpoints()
    dashboard_ok = check_dashboard_requirements()
    
    # Show summary
    show_data_summary()
    
    # Final verdict
    print("\n🎯 Final Results")
    print("=" * 50)
    print(f"WebSocket Ingestion: {'✅' if websocket_ok else '❌'}")
    print(f"Price Data Sync: {'✅' if price_sync_ok else '❌'}")
    print(f"API Endpoints: {'✅' if api_ok else '❌'}")
    print(f"Dashboard Ready: {'✅' if dashboard_ok else '❌'}")
    
    all_good = all([websocket_ok, price_sync_ok, api_ok, dashboard_ok])
    
    if all_good:
        print("\n🎉 All systems working! Dashboard should show real-time data.")
        print("Start dashboard: streamlit run dashboard/app.py")
    else:
        print("\n⚠️  Some issues found. Fix them before running dashboard.")
        
        print("\n💡 Troubleshooting:")
        if not websocket_ok:
            print("   • Start WebSocket: python ingestion/binance_websocket.py")
        if not price_sync_ok:
            print("   • Sync data: python processing/kline_to_price_sync.py --all")
        if not api_ok:
            print("   • Start API: python api/main.py")
        if not dashboard_ok:
            print("   • Install deps: pip install streamlit plotly pandas")

if __name__ == "__main__":
    main()