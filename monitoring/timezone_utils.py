"""
Modul utilitas untuk manajemen dan konversi zona waktu dari UTC ke WIB.
"""
from datetime import datetime, timezone, timedelta

WIB = timezone(timedelta(hours=7))

def now_wib() -> datetime:
    """Mengambil waktu saat ini sesuai dengan Waktu Indonesia Barat (WIB)."""
    return datetime.now(WIB)

def utc_to_wib(dt: datetime) -> datetime:
    """Mengonversi instans datetime dari UTC ke WIB."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(WIB)

def convert_utc_to_wib(dt: datetime) -> datetime:
    """Mengonversi UTC ke WIB dan menghilangkan informasi zona waktu (naive) untuk keperluan API."""
    if dt is None:
        return dt
    
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    wib_dt = dt.astimezone(WIB)
    return wib_dt.replace(tzinfo=None)

def format_wib(dt: datetime, include_timezone: bool = True) -> str:
    """Memformat objek datetime ke dalam string standar WIB."""
    wib_dt = utc_to_wib(dt) if dt.tzinfo != WIB else dt
    if include_timezone:
        return wib_dt.strftime('%Y-%m-%d %H:%M:%S WIB')
    return wib_dt.strftime('%Y-%m-%d %H:%M:%S')

def format_wib_short(dt: datetime) -> str:
    """Memformat objek datetime menjadi representasi waktu singkat (Jam:Menit:Detik)."""
    wib_dt = utc_to_wib(dt) if dt.tzinfo != WIB else dt
    return wib_dt.strftime('%H:%M:%S WIB')
