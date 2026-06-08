"""
Quick start script untuk real-time crypto analytics pipeline.

Script ini akan:
1. Initialize database
2. Test API connectivity  
3. Start WebSocket ingestion dalam background
4. Start API server dalam background
5. Test data flow
6. Memberikan instruksi untuk dashboard

Usage: python start_realtime.py
"""
import os
import sys
import subprocess
import time
import requests
from datetime import datetime

sys.path.insert(0, '.')

from monitoring.timezone_utils import now_wib, format_wib

def print_step(step, message):
    """Print formatted step message."""
    print(f"\n{'='*60}")
    print(f"STEP {step}: {message}")
    print('='*60)

def check_docker_services():
    """Check if required Docker services are running."""
    print("🔍 Checking Docker services...")
    
    try:
        result = subprocess.run(['docker', 'compose', 'ps'], capture_output=True, text=True)
        if 'postgres' in result.stdout and 'Up' in result.stdout:
            print("✅ PostgreSQL is running")
            return True
        else:
            print("❌ PostgreSQL not running")
            print("Run: docker-compose up -d")
            return False
    except FileNotFoundError:
        print("❌ Docker not found. Install Docker first.")
        return False
    except Exception as e:
        print(f"❌ Error checking Docker: {e}")
        return False

def initialize_database():
    """Initialize database tables."""
    print("🗄️ Initializing database...")
    
    try:
        from storage.db_models import init_db
        init_db()
        print("✅ Database initialized")
        return True
    except Exception as e:
        print(f"❌ Database init failed: {e}")
        return False

def start_websocket_ingestion():
    """Start WebSocket ingestion in background."""
    print("🌐 Starting WebSocket ingestion...")
    
    try:
        # Start WebSocket in background
        process = subprocess.Popen(
            [sys.executable, 'ingestion/binance_websocket.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
        )
        
        # Give it a moment to start
        time.sleep(3)
        
        if process.poll() is None:  # Still running
            print("✅ WebSocket ingestion started in background")
            return process
        else:
            print("❌ WebSocket failed to start")
            return None
    except Exception as e:
        print(f"❌ Error starting WebSocket: {e}")
        return None

def start_api_server():
    """Start API server in background."""
    print("🔧 Starting API server...")
    
    try:
        # Start API in background
        process = subprocess.Popen(
            [sys.executable, 'api/main.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
        )
        
        # Give it a moment to start
        time.sleep(5)
        
        if process.poll() is None:  # Still running
            print("✅ API server started in background")
            return process
        else:
            print("❌ API server failed to start")
            return None
    except Exception as e:
        print(f"❌ Error starting API: {e}")
        return None

def test_api_connection():
    """Test if API is responding."""
    print("🧪 Testing API connection...")
    
    api_url = os.getenv("API_BASE_URL", "http://localhost:8001")
    
    # Wait a bit for API to be ready
    for attempt in range(10):
        try:
            response = requests.get(f"{api_url}/health", timeout=5)
            if response.status_code == 200:
                print("✅ API is responding")
                return True
        except requests.exceptions.ConnectionError:
            if attempt < 9:
                print(f"⏳ Waiting for API... (attempt {attempt + 1}/10)")
                time.sleep(2)
            else:
                print("❌ API not responding after 10 attempts")
                return False
        except Exception as e:
            print(f"❌ API test error: {e}")
            return False
    
    return False

def wait_for_data():
    """Wait for some WebSocket data to arrive."""
    print("⏳ Waiting for WebSocket data...")
    
    from storage.db_models import get_session, KlineData
    
    for attempt in range(15):  # Wait up to 30 seconds
        session = get_session()
        try:
            count = session.query(KlineData).count()
            if count > 0:
                print(f"✅ Found {count} data records")
                return True
            else:
                if attempt < 14:
                    print(f"⏳ Waiting for data... (attempt {attempt + 1}/15)")
                    time.sleep(2)
        except Exception as e:
            print(f"❌ Error checking data: {e}")
        finally:
            session.close()
    
    print("⚠️ No WebSocket data yet - dashboard may be empty initially")
    return False

def main():
    """Main startup sequence."""
    print(f"🚀 CRYPTO ANALYTICS REAL-TIME STARTUP")
    print(f"Time: {format_wib(now_wib())}")
    
    # Step 1: Check Docker
    print_step(1, "Check Docker Services")
    if not check_docker_services():
        print("\n❌ FAILED: Start Docker services first")
        print("Run: docker-compose up -d")
        return False
    
    # Step 2: Initialize DB
    print_step(2, "Initialize Database")
    if not initialize_database():
        print("\n❌ FAILED: Database initialization failed")
        return False
    
    # Step 3: Start WebSocket
    print_step(3, "Start WebSocket Ingestion")
    websocket_process = start_websocket_ingestion()
    if not websocket_process:
        print("\n❌ FAILED: WebSocket ingestion failed")
        return False
    
    # Step 4: Start API
    print_step(4, "Start API Server")
    api_process = start_api_server()
    if not api_process:
        print("\n❌ FAILED: API server failed")
        return False
    
    # Step 5: Test API
    print_step(5, "Test API Connection")
    if not test_api_connection():
        print("\n❌ FAILED: API not responding")
        return False
    
    # Step 6: Wait for data
    print_step(6, "Wait for Initial Data")
    wait_for_data()
    
    # Success!
    print(f"\n{'='*60}")
    print("🎉 REAL-TIME PIPELINE STARTED SUCCESSFULLY!")
    print('='*60)
    
    print("\n📊 DASHBOARD:")
    print("Run this command in a NEW terminal:")
    print("streamlit run dashboard/app.py")
    print("\nThen open: http://localhost:8501")
    
    print("\n🌐 API:")
    print("API Docs: http://localhost:8001/docs")
    print("Health: http://localhost:8001/health")
    
    print("\n⚡ REAL-TIME FEATURES:")
    print("• 1-second dashboard refresh")
    print("• Multi-symbol support (BTC, ETH, BNB, SOL)")
    print("• WIB timezone")
    print("• Clickable news links")
    print("• Real-time anomaly detection")
    
    print("\n🛑 TO STOP:")
    print("Close the WebSocket and API terminal windows")
    print("Or run: docker-compose down")
    
    print(f"\n✅ Started at: {format_wib(now_wib())}")
    
    return True

if __name__ == "__main__":
    if main():
        print("\n💡 TIP: Keep this terminal open to see status")
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            print("\n👋 Startup script stopped")
    else:
        print("\n❌ Startup failed. Check errors above.")
        sys.exit(1)