"""
🚀 Production Startup Script for Bitcoin Analytics Pipeline

This script starts all required components in the correct order:
1. Checks Docker services
2. Initializes database
3. Starts WebSocket ingestion
4. Starts API server  
5. Provides dashboard startup instructions

Usage: python start_production.py
"""
import os
import sys
import subprocess
import time
import requests
from datetime import datetime

sys.path.insert(0, '.')

from monitoring.timezone_utils import now_wib, format_wib

def print_header(text):
    """Print formatted header."""
    print(f"\n{'='*70}")
    print(f"  {text}")
    print('='*70)

def print_step(step, message):
    """Print formatted step message."""
    print(f"\n{'─'*70}")
    print(f"STEP {step}: {message}")
    print('─'*70)

def check_docker():
    """Check if Docker services are running."""
    print_step(1, "Checking Docker Services")
    
    try:
        result = subprocess.run(['docker', 'compose', 'ps'], 
                              capture_output=True, text=True, timeout=10)
        
        if 'postgres' in result.stdout and 'Up' in result.stdout:
            print("✅ PostgreSQL is running")
        else:
            print("❌ PostgreSQL not running")
            print("\n💡 Start Docker services:")
            print("   docker-compose up -d")
            return False
            
        if 'kafka' in result.stdout and 'Up' in result.stdout:
            print("✅ Kafka is running")
        else:
            print("⚠️  Kafka not running (optional for real-time features)")
            
        if 'minio' in result.stdout and 'Up' in result.stdout:
            print("✅ MinIO is running")
        else:
            print("⚠️  MinIO not running (optional for Bronze layer)")
        
        return True
        
    except subprocess.TimeoutExpired:
        print("❌ Docker command timeout")
        return False
    except FileNotFoundError:
        print("❌ Docker not found. Install Docker first.")
        return False
    except Exception as e:
        print(f"❌ Error checking Docker: {e}")
        return False

def initialize_database():
    """Initialize database tables."""
    print_step(2, "Initializing Database")
    
    try:
        from storage.db_models import init_db
        init_db()
        print("✅ Database initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False

def start_websocket():
    """Start WebSocket ingestion in background."""
    print_step(3, "Starting WebSocket Ingestion")
    
    try:
        # Start in new console window (Windows) or background (Linux/Mac)
        if os.name == 'nt':  # Windows
            process = subprocess.Popen(
                [sys.executable, 'ingestion/binance_websocket.py'],
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
        else:  # Linux/Mac
            process = subprocess.Popen(
                [sys.executable, 'ingestion/binance_websocket.py'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        
        time.sleep(3)
        
        if process.poll() is None:
            print("✅ WebSocket ingestion started")
            print("   Bitcoin real-time data streaming...")
            return True
        else:
            print("❌ WebSocket failed to start")
            return False
            
    except Exception as e:
        print(f"❌ Error starting WebSocket: {e}")
        return False

def start_api():
    """Start API server in background."""
    print_step(4, "Starting API Server")
    
    try:
        # Start in new console window (Windows) or background (Linux/Mac)
        if os.name == 'nt':  # Windows
            process = subprocess.Popen(
                [sys.executable, 'api/main.py'],
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
        else:  # Linux/Mac
            process = subprocess.Popen(
                [sys.executable, 'api/main.py'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        
        # Wait for API to be ready
        print("⏳ Waiting for API to start...")
        api_url = os.getenv("API_BASE_URL", "http://localhost:8001")
        
        for attempt in range(15):
            try:
                time.sleep(2)
                response = requests.get(f"{api_url}/health", timeout=5)
                if response.status_code == 200:
                    print(f"✅ API server running at {api_url}")
                    return True
            except requests.exceptions.ConnectionError:
                if attempt < 14:
                    print(f"   Attempt {attempt + 1}/15...")
                continue
            except Exception:
                continue
        
        print("❌ API server not responding")
        return False
        
    except Exception as e:
        print(f"❌ Error starting API: {e}")
        return False

def wait_for_data():
    """Wait for WebSocket to collect some data."""
    print_step(5, "Waiting for Initial Data")
    
    print("⏳ Collecting Bitcoin data...")
    print("   This takes 2-3 minutes for first candle to close")
    
    from storage.db_models import get_session, KlineData
    
    for attempt in range(30):  # Wait up to 60 seconds
        time.sleep(2)
        session = get_session()
        try:
            count = session.query(KlineData).count()
            if count > 0:
                print(f"✅ Found {count} kline records in database")
                return True
            else:
                if attempt % 5 == 0:  # Print every 10 seconds
                    print(f"   Waiting... ({attempt * 2}s)")
        except Exception:
            pass
        finally:
            session.close()
    
    print("⚠️  No data yet - dashboard may be empty initially")
    print("   Data will appear as WebSocket receives Bitcoin candles")
    return True

def show_instructions():
    """Show final instructions."""
    print_header("🎉 PRODUCTION SETUP COMPLETE!")
    
    current_wib = now_wib()
    
    print(f"\n⏰ Started at: {format_wib(current_wib)}")
    print("\n📊 DASHBOARD:")
    print("   Run this command in a NEW terminal:")
    print("   ")
    print("   streamlit run dashboard/app.py")
    print("   ")
    print("   Then open: http://localhost:8501")
    
    print("\n🌐 API:")
    print("   API Docs: http://localhost:8001/docs")
    print("   Health: http://localhost:8001/health")
    print("   Base URL: http://localhost:8001")
    
    print("\n⚡ FEATURES:")
    print("   • 1-second real-time refresh")
    print("   • Bitcoin live price tracking")
    print("   • News sentiment analysis")
    print("   • Anomaly detection alerts")
    print("   • Interactive charts")
    
    print("\n🛑 TO STOP:")
    print("   Close the WebSocket and API terminal windows")
    print("   Or: docker-compose down")
    
    print("\n💡 OPTIONAL:")
    print("   • Run news scraping: python ingestion/rss_batch.py")
    print("   • Train LSTM model: python ml/training/train_lstm_model.py")
    
    print("\n" + "="*70)

def main():
    """Main startup sequence."""
    print_header("₿ BITCOIN ANALYTICS PIPELINE - PRODUCTION STARTUP")
    print(f"\nTime: {format_wib(now_wib())}")
    
    # Step 1: Check Docker
    if not check_docker():
        print("\n❌ FAILED: Docker services not running")
        print("\n💡 Fix: docker-compose up -d")
        return False
    
    # Step 2: Initialize database
    if not initialize_database():
        print("\n❌ FAILED: Database initialization failed")
        return False
    
    # Step 3: Start WebSocket
    if not start_websocket():
        print("\n❌ FAILED: WebSocket ingestion failed")
        return False
    
    # Step 4: Start API
    if not start_api():
        print("\n❌ FAILED: API server failed")
        return False
    
    # Step 5: Wait for data
    wait_for_data()
    
    # Success!
    show_instructions()
    return True

if __name__ == "__main__":
    try:
        if main():
            print("\n✅ Ready for Bitcoin monitoring!")
        else:
            print("\n❌ Startup failed. Check errors above.")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Startup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)
