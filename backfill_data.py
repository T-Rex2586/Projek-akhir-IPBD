"""
Quick Data Backfill Script
Populates database with 7 days of historical data from Binance
Uses REST API with multiple endpoints for reliability
"""
import requests
import time
from datetime import datetime, timedelta
from storage.db_models import init_db
from storage.db_utils import save_price_data, save_kline_data
from monitoring.logger import get_logger

logger = get_logger(__name__)

SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT"]

# Multiple Binance API endpoints to try
BASE_URLS = [
    "https://api.binance.com",
    "https://api1.binance.com",
    "https://api2.binance.com",
    "https://api3.binance.com",
]

def fetch_historical_klines(symbol, interval="5m", days=7):
    """Fetch historical kline data from Binance with multiple endpoint fallback"""
    end_time = int(datetime.now().timestamp() * 1000)
    start_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
    
    params = {
        'symbol': symbol,
        'interval': interval,
        'startTime': start_time,
        'endTime': end_time,
        'limit': 1000
    }
    
    # Try each endpoint
    for base_url in BASE_URLS:
        url = f"{base_url}/api/v3/klines"
        try:
            print(f"  🔗 Trying {base_url}...")
            response = requests.get(url, params=params, timeout=20)
            response.raise_for_status()
            print(f"  ✅ Connected to {base_url}")
            return response.json()
        except requests.exceptions.Timeout:
            logger.error(f"timeout", url=base_url, symbol=symbol)
            print(f"  ⏰ Timeout on {base_url}")
            continue
        except requests.exceptions.ConnectionError as e:
            logger.error(f"connection_error", url=base_url, symbol=symbol, error=str(e))
            print(f"  ❌ Connection error on {base_url}")
            continue
        except Exception as e:
            logger.error(f"fetch_failed", url=base_url, symbol=symbol, error=str(e))
            print(f"  ❌ Error on {base_url}: {str(e)}")
            continue
    
    # All endpoints failed
    print(f"  💥 All endpoints failed for {symbol}")
    return []

def backfill_symbol(symbol, days=7):
    """Backfill data for a single symbol"""
    print(f"\n📊 Backfilling {symbol}...")
    
    klines = fetch_historical_klines(symbol, interval="5m", days=days)
    
    if not klines:
        print(f"❌ No data received for {symbol}")
        return 0
    
    count = 0
    for kline in klines:
        # kline format: [open_time, open, high, low, close, volume, ...]
        try:
            # Save as price data
            price_data = {
                'symbol': symbol,
                'price': float(kline[4]),  # close price
                'volume': float(kline[5]),
                'high_24h': float(kline[2]),
                'low_24h': float(kline[3]),
                'timestamp': datetime.fromtimestamp(kline[0] / 1000)
            }
            save_price_data(price_data)
            
            # Save as kline data
            kline_data = {
                'symbol': symbol,
                'open': float(kline[1]),
                'high': float(kline[2]),
                'low': float(kline[3]),
                'close': float(kline[4]),
                'volume': float(kline[5]),
                'open_time': kline[0],
                'close_time': kline[6],
                'interval': '5m'
            }
            save_kline_data(kline_data)
            
            count += 1
        except Exception as e:
            logger.error(f"save_failed", symbol=symbol, error=str(e))
            continue
    
    print(f"✅ Saved {count} data points for {symbol}")
    return count

def main():
    """Run backfill for all symbols"""
    print("\n" + "="*60)
    print("🚀 Starting Data Backfill (7 Days Historical)")
    print("="*60)
    
    # Check network connectivity first
    print("\n🔍 Testing Binance API connectivity...")
    test_passed = False
    for base_url in BASE_URLS:
        try:
            response = requests.get(f"{base_url}/api/v3/ping", timeout=10)
            if response.status_code == 200:
                print(f"✅ {base_url} is reachable")
                test_passed = True
                break
            else:
                print(f"⚠️ {base_url} returned status {response.status_code}")
        except Exception as e:
            print(f"❌ {base_url} is not reachable: {str(e)}")
    
    if not test_passed:
        print("\n" + "="*60)
        print("⚠️  NETWORK ISSUE DETECTED")
        print("="*60)
        print("\n❌ Cannot reach any Binance API endpoint.")
        print("\n🔧 Possible solutions:")
        print("   1. Use VPN (recommended): Connect to VPN and try again")
        print("   2. Check firewall: Make sure ports 443 is open")
        print("   3. Check DNS: Try changing DNS to 8.8.8.8 (Google)")
        print("   4. Check ISP: Your ISP might be blocking Binance")
        print("\n💡 Alternative:")
        print("   - Use different crypto exchange API (Coinbase, Kraken, etc)")
        print("   - Run from different network/location")
        print()
        return
    
    # Initialize database
    print("\n📦 Initializing database...")
    init_db()
    print("✅ Database ready\n")
    
    # Backfill each symbol
    total = 0
    for symbol in SYMBOLS:
        count = backfill_symbol(symbol, days=7)
        total += count
        time.sleep(2)  # Rate limiting
    
    print("\n" + "="*60)
    if total > 0:
        print(f"🎉 Backfill Complete!")
        print(f"📊 Total data points saved: {total}")
        print("\n💡 Now you can:")
        print("   1. Open dashboard: streamlit run dashboard/app.py")
        print("   2. Check API: python -m api.main")
    else:
        print("❌ No data was saved")
        print("\n🔧 Troubleshooting:")
        print("   - Check if Docker PostgreSQL is running: docker ps")
        print("   - Check network/VPN connection")
        print("   - Try running backfill_data.py again")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
