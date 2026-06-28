"""
Skrip Inisialisasi Produksi Pipa Data Analitik Mata Uang Kripto.
Melakukan eksekusi berurutan untuk infrastruktur pendukung:
1. Validasi eksistensi kontainer Docker.
2. Inisialisasi matriks basis data.
3. Menjalankan penyerapan data sinkronisasi (WebSocket).
4. Mengeksekusi antarmuka layanan web (API).
"""
import os
import sys
import subprocess
import time
import requests
import io
from datetime import datetime

# Paksa stdout dan stderr menggunakan UTF-8 agar emoji dapat dirender di Windows
if sys.stdout.encoding.lower() != 'utf-8':
  sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
if sys.stderr.encoding.lower() != 'utf-8':
  sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from monitoring.timezone_utils import now_wib, format_wib

def print_header(text):
  print(f"\n{'='*70}")
  print(f" {text}")
  print('='*70)

def print_step(step, message):
  print(f"\n{'─'*70}")
  print(f"LANGKAH {step}: {message}")
  print('─'*70)

def check_docker():
  print_step(1, "Verifikasi Layanan Kontainer Docker")
  try:
    result = subprocess.run(['docker', 'compose', 'ps'], capture_output=True, text=True, timeout=10)
    
    if 'postgres' in result.stdout and 'Up' in result.stdout:
      print(" PostgreSQL telah beroperasi secara optimal")
    else:
      print(" PostgreSQL gagal terdeteksi")
      print("\n Inisialisasi layanan Docker:")
      print("  docker-compose up -d")
      return False
      
    if 'kafka' in result.stdout and 'Up' in result.stdout:
      print(" Kafka beroperasi dengan normal")
    else:
      print(" Kafka tidak aktif (opsional untuk skema waktu nyata)")
      
    if 'minio' in result.stdout and 'Up' in result.stdout:
      print(" MinIO beroperasi secara stabil")
    else:
      print(" MinIO tidak aktif (opsional untuk Lapisan Perunggu)")
    
    return True
  except subprocess.TimeoutExpired:
    print(" Terjadi kehabisan waktu pada eksekusi Docker (Timeout)")
    return False
  except FileNotFoundError:
    print(" Docker tidak ditemukan. Pastikan instalasi Docker pada sistem Anda.")
    return False
  except Exception as e:
    print(f" Kesalahan validasi Docker: {e}")
    return False

def initialize_database():
  print_step(2, "Inisialisasi Skema Basis Data")
  try:
    from storage.db_models import init_db
    init_db()
    print(" Basis data berhasil distrukturisasi")
    return True
  except Exception as e:
    print(f" Kegagalan inisialisasi basis data: {e}")
    return False

def start_websocket():
  print_step(3, "Inisiasi Aliran Data WebSocket")
  try:
    if os.name == 'nt':
      process = subprocess.Popen(
        [sys.executable, 'ingestion/binance_websocket.py'],
        creationflags=subprocess.CREATE_NEW_CONSOLE
      )
    else:
      process = subprocess.Popen(
        [sys.executable, 'ingestion/binance_websocket.py'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
      )
    
    time.sleep(3)
    
    if process.poll() is None:
      print(" Penyerapan data WebSocket berhasil dijalankan")
      print("  Aliran data Bitcoin sinkronus sedang direkam...")
      return True
    else:
      print(" WebSocket gagal memulai rutinitas")
      return False
  except Exception as e:
    print(f" Kesalahan inisiasi WebSocket: {e}")
    return False

def start_api():
  print_step(4, "Eksekusi Layanan Web API")
  try:
    if os.name == 'nt':
      process = subprocess.Popen(
        [sys.executable, 'api/main.py'],
        creationflags=subprocess.CREATE_NEW_CONSOLE
      )
    else:
      process = subprocess.Popen(
        [sys.executable, 'api/main.py'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
      )
    
    print(" Menunggu verifikasi respons API...")
    api_url = os.getenv("API_BASE_URL", "http://134.209.208.11:8001")
    
    for attempt in range(15):
      try:
        time.sleep(2)
        response = requests.get(f"{api_url}/health", timeout=5)
        if response.status_code == 200:
          print(f" Layanan API terhubung pada {api_url}")
          return True
      except requests.exceptions.ConnectionError:
        if attempt < 14:
          print(f"  Eksperimen ke-{attempt + 1}/15...")
        continue
      except Exception:
        continue
    
    print(" Tautan API tidak memberikan respons (No Response)")
    return False
  except Exception as e:
    print(f" Kesalahan pemanggilan API: {e}")
    return False

def start_telegram_bot():
  print_step(5, "Eksekusi Bot Telegram")
  try:
    if os.name == 'nt':
      process = subprocess.Popen(
        [sys.executable, 'scripts/start_telegram_bot.py'],
        creationflags=subprocess.CREATE_NEW_CONSOLE
      )
    else:
      process = subprocess.Popen(
        [sys.executable, 'scripts/start_telegram_bot.py'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
      )
    print(" Bot Telegram berhasil diinisialisasi")
    return True
  except Exception as e:
    print(f" Kesalahan eksekusi Bot Telegram: {e}")
    return False

def start_gold_processor():
  print_step(6, "Eksekusi Pemrosesan Gold Layer")
  try:
    if os.name == 'nt':
      process = subprocess.Popen(
        [sys.executable, 'processing/gold_processor.py'],
        creationflags=subprocess.CREATE_NEW_CONSOLE
      )
    else:
      process = subprocess.Popen(
        [sys.executable, 'processing/gold_processor.py'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
      )
    print(" Gold Processor berhasil diinisialisasi")
    return True
  except Exception as e:
    print(f" Kesalahan eksekusi Gold Processor: {e}")
    return False

def wait_for_data():
  print_step(7, "Verifikasi Agregasi Data Perdana")
  print(" Menghimpun kuotasi historis Bitcoin...")
  print("  Dibutuhkan sekitar 2-3 menit untuk membentuk struktur kardinal")
  
  from storage.db_models import get_session, KlineData
  
  for attempt in range(30):
    time.sleep(2)
    session = get_session()
    try:
      count = session.query(KlineData).count()
      if count > 0:
        print(f" Ditemukan {count} entitas data Kline pada basis penyimpanan")
        return True
      else:
        if attempt % 5 == 0:
          print(f"  Menunggu... ({attempt * 2}d)")
    except Exception:
      pass
    finally:
      session.close()
  
  print(" Data belum terhimpun - dasbor representasi visual berpotensi nir-informasi pada tahap inisial")
  return True

def show_instructions():
  print_header(" INSTALASI PRODUKSI BERHASIL DILAKSANAKAN!")
  
  current_wib = now_wib()
  
  print(f"\n⏰ Waktu Inisiasi: {format_wib(current_wib)}")
  print("\n INSTRUMEN VISUAL (DASHBOARD):")
  print("  Jalankan formulasi di bawah ini pada instansi terminal baru:")
  print("  ")
  print("  cd dashboard && npm run dev")
  print("  ")
  print("  Selanjutnya akses alamat URL: http://134.209.208.11:5173")
  
  print("\n INTERFACE LAYANAN (API):")
  print("  Dokumentasi API: http://134.209.208.11:8001/docs")
  print("  Metrik Status: http://134.209.208.11:8001/health")
  print("  Alamat Sentral: http://134.209.208.11:8001")
  
  print("\n FITUR TERINTEGRASI:")
  print("  Penilaian presisi waktu nyata 1 detik")
  print("  Transmisi harga Bitcoin seketika")
  print("  Estimasi sentimen analitis berita")
  print("  Indentifikasi penyimpangan (anomali)")
  
  print("\n TERMINASI PROSES:")
  print("  Tutup terminal eksklusif pengolah WebSocket dan API")
  print("  Alternatif: eksekusi 'docker-compose down'")
  
  print("\n MODUL OPSIONAL:")
  print("  Agregasi korpus berita: python ingestion/rss_batch.py")
  print("  Optimalisasi kerangka LSTM: python ml/training/train_lstm_model.py")
  print("\n" + "="*70)

def main():
  print_header(" PIPA DATA ANALITIK BITCOIN - EKSEKUSI PRODUKSI")
  print(f"\nJadwal Operasional: {format_wib(now_wib())}")
  
  if not check_docker():
    print("\n KEGAGALAN: Layanan Docker terdisrupsi")
    return False
  
  if not initialize_database():
    print("\n KEGAGALAN: Kegagalan skematisasi basis data")
    return False
  
  if not start_websocket():
    print("\n KEGAGALAN: Defisiensi inisiasi modul WebSocket")
    return False
  
  if not start_api():
    print("\n KEGAGALAN: Layanan API tak beroperasi selayaknya")
    return False
  
  start_telegram_bot()
  start_gold_processor()
  
  wait_for_data()
  show_instructions()
  return True

if __name__ == "__main__":
  try:
    if main():
      print("\n Konfigurasi sempurna. Sistem siap mendeteksi dinamika pasar!")
    else:
      print("\n Terdapat malfungsi sistem. Evaluasi jejak rekam (logs) di atas.")
      sys.exit(1)
  except KeyboardInterrupt:
    print("\n\n Pembatalan sinkronisasi secara manual")
    sys.exit(1)
  except Exception as e:
    print(f"\n Terjadi disrupsi sistematis yang fatal: {e}")
    sys.exit(1)
