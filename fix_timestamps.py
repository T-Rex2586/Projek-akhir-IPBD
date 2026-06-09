"""
Fix timezone timestamps in database.

This script fixes timestamps that were saved in local time (WIB) 
instead of UTC. It deletes existing PriceData and lets WebSocket
refill with correct UTC timestamps.

Usage: python fix_timestamps.py
"""
import sys
sys.path.insert(0, '.')

from storage.db_models import get_session, PriceData
from monitoring.logger import get_logger

logger = get_logger(__name__)

def fix_timestamps():
    """Delete PriceData with incorrect timestamps."""
    session = get_session()
    
    try:
        # Count existing records
        count = session.query(PriceData).count()
        print(f"\n📊 Found {count:,} PriceData records with potentially incorrect timestamps")
        
        if count == 0:
            print("✅ No records to fix")
            return
        
        # Ask for confirmation
        confirm = input(f"\n⚠️  Delete all {count:,} records? (yes/no): ").strip().lower()
        
        if confirm != 'yes':
            print("❌ Cancelled")
            return
        
        # Delete all PriceData
        deleted = session.query(PriceData).delete()
        session.commit()
        
        print(f"\n✅ Deleted {deleted:,} records")
        print("\n💡 Next steps:")
        print("   1. Make sure WebSocket is running: python ingestion/binance_websocket.py")
        print("   2. Wait 2-3 minutes for data to accumulate")
        print("   3. Check dashboard - timestamps should now be correct!")
        print("\n📝 Note: KlineData is not affected (already in UTC)")
        
        logger.info("price_data_timestamps_fixed", deleted=deleted)
        
    except Exception as e:
        session.rollback()
        logger.error("timestamp_fix_failed", error=str(e))
        print(f"\n❌ Error: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    print("\n" + "="*70)
    print("  🔧 Fix Timezone Timestamps")
    print("="*70)
    
    fix_timestamps()
    
    print("\n" + "="*70)
