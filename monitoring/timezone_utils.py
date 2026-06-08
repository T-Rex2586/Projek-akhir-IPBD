"""
Timezone utility for converting UTC to WIB (Indonesia)
"""
from datetime import datetime, timezone, timedelta

# WIB = UTC+7
WIB = timezone(timedelta(hours=7))

def now_wib() -> datetime:
    """Get current time in WIB (Indonesia)"""
    return datetime.now(WIB)

def utc_to_wib(dt: datetime) -> datetime:
    """Convert UTC datetime to WIB"""
    if dt.tzinfo is None:
        # Assume UTC if naive
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(WIB)

def convert_utc_to_wib(dt: datetime) -> datetime:
    """Convert UTC datetime to WIB, return naive datetime for API responses"""
    if dt is None:
        return dt
    
    if dt.tzinfo is None:
        # Assume UTC if naive
        dt = dt.replace(tzinfo=timezone.utc)
    
    # Convert to WIB and return naive datetime
    wib_dt = dt.astimezone(WIB)
    return wib_dt.replace(tzinfo=None)

def format_wib(dt: datetime, include_timezone: bool = True) -> str:
    """Format datetime in WIB"""
    wib_dt = utc_to_wib(dt) if dt.tzinfo != WIB else dt
    if include_timezone:
        return wib_dt.strftime('%Y-%m-%d %H:%M:%S WIB')
    return wib_dt.strftime('%Y-%m-%d %H:%M:%S')

def format_wib_short(dt: datetime) -> str:
    """Format datetime in short WIB format (time only)"""
    wib_dt = utc_to_wib(dt) if dt.tzinfo != WIB else dt
    return wib_dt.strftime('%H:%M:%S WIB')
