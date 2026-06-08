"""
Test API endpoint directly to debug dashboard issue
"""
import requests
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8001")
API_KEY = os.getenv("API_KEY", "dev-api-key")
HEADERS = {"X-API-Key": API_KEY}

def test_api():
    """Test API endpoints"""
    print("\n" + "="*60)
    print("🔌 API ENDPOINT TEST")
    print("="*60)
    
    # Test 1: Health check
    print("\n1️⃣  Health Check:")
    print("-" * 60)
    try:
        resp = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            print(f"  ✅ API is ONLINE")
            print(f"  Status: {data.get('status')}")
            print(f"  Timestamp: {data.get('timestamp')}")
            metrics = data.get('pipeline_metrics', {})
            print(f"  Records processed: {metrics.get('records_processed', 0)}")
        else:
            print(f"  ❌ HTTP {resp.status_code}")
    except Exception as e:
        print(f"  ❌ ERROR: {str(e)}")
        print(f"  Make sure API is running: python -m api.main")
        return
    
    # Test 2: Price data (168 hours = 7 days)
    print("\n2️⃣  Price Data (BTCUSDT - 168 hours):")
    print("-" * 60)
    try:
        resp = requests.get(
            f"{API_BASE_URL}/prices/BTCUSDT",
            headers=HEADERS,
            params={"hours": 168},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            print(f"  ✅ Received {len(data)} data points")
            
            if data:
                first = data[0]
                last = data[-1]
                print(f"  First: {first['timestamp']} | ${first['price']:,.2f}")
                print(f"  Last:  {last['timestamp']} | ${last['price']:,.2f}")
                
                # Calculate age
                last_time = datetime.fromisoformat(last['timestamp'].replace('Z', '+00:00'))
                age_seconds = (datetime.now(last_time.tzinfo) - last_time).total_seconds()
                
                print(f"\n  📊 Data Status:")
                if age_seconds < 60:
                    print(f"     ✅ REAL-TIME (last update {age_seconds:.0f}s ago)")
                elif age_seconds < 300:
                    print(f"     ⚠️  DELAYED (last update {age_seconds/60:.1f}m ago)")
                else:
                    print(f"     ❌ STALE (last update {age_seconds/3600:.1f}h ago)")
            else:
                print(f"  ⚠️  No data returned (empty array)")
        elif resp.status_code == 403:
            print(f"  ❌ Authentication failed - check API_KEY in .env")
        else:
            print(f"  ❌ HTTP {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"  ❌ ERROR: {str(e)}")
    
    # Test 3: All symbols
    print("\n3️⃣  All Symbols (Last 1 hour):")
    print("-" * 60)
    
    symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'ADAUSDT']
    for symbol in symbols:
        try:
            resp = requests.get(
                f"{API_BASE_URL}/prices/{symbol}",
                headers=HEADERS,
                params={"hours": 1},
                timeout=5
            )
            if resp.status_code == 200:
                data = resp.json()
                if data:
                    last = data[-1]
                    last_time = datetime.fromisoformat(last['timestamp'].replace('Z', '+00:00'))
                    age_minutes = (datetime.now(last_time.tzinfo) - last_time).total_seconds() / 60
                    status = "✅" if age_minutes < 5 else "⚠️" if age_minutes < 60 else "❌"
                    print(f"  {status} {symbol:10} | {len(data):>4} pts | ${last['price']:>10,.2f} | {age_minutes:.1f}m ago")
                else:
                    print(f"  ❌ {symbol:10} | No data")
            else:
                print(f"  ❌ {symbol:10} | HTTP {resp.status_code}")
        except Exception as e:
            print(f"  ❌ {symbol:10} | Error: {str(e)}")
    
    print("\n" + "="*60)
    print("💡 NEXT STEPS:")
    print("="*60)
    print("  1. If API returns stale data → Ingestion not running")
    print("     Fix: python ingestion/binance_rest.py")
    print()
    print("  2. If API returns no data → Database empty")
    print("     Fix: python backfill_data.py")
    print()
    print("  3. If API not responding → API not started")
    print("     Fix: python -m api.main")
    print()
    print("  4. If everything OK but dashboard stale → Clear browser cache")
    print("     Fix: Ctrl+Shift+R (hard refresh)")
    print()

if __name__ == "__main__":
    test_api()
