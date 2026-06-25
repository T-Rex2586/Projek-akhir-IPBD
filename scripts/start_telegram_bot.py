"""
Agen Pendengar (Bot Listener) Telegram.
Menjalankan layanan pengawasan komunikasi bot untuk interaksi fungsionalitas analitik.
"""
import sys
import os
import io

# Paksa stdout dan stderr menggunakan UTF-8 agar emoji dapat dirender di Windows
if sys.stdout.encoding.lower() != 'utf-8':
  sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
if sys.stderr.encoding.lower() != 'utf-8':
  sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from monitoring.telegram_alert import start_bot_listener, _is_configured

def main():
  print("\n" + "="*70)
  print("  Bot Telegram untuk Analitik Pipa Data Kripto")
  print("="*70)
  
  if not _is_configured():
    print("\n Parameter bot Telegram belum dikonfigurasi!")
    print("\n Instruksi Persiapan Integrasi:")
    print("1. Inisialisasi bot melalui interaksi dengan @BotFather pada platform Telegram")
    print("2. Dapatkan identifikasi numerik profil pengguna melalui @userinfobot")
    print("3. Tambahkan ke entitas .env root direktori proyek:")
    print("  TELEGRAM_BOT_TOKEN=token_bot_anda")
    print("  TELEGRAM_CHAT_ID=identifikasi_obrolan_anda")
    print("\n Selanjutnya, silakan eksekusi ulang utilitas sinkronisasi ini.")
    return False
  
  print("\n Integrasi variabel lingkungan diverifikasi secara sukses!")
  print("\n Perintah Interaktif:")
  print("  /predict - Ekstraksi prediktif sinyal valuta kripto")
  print("  /status - Penilaian keandalan subsistem arsitektur")
  print("  /help - Deskripsi utilitas operasional yang tersedia")
  print("\n Persistensi Pemberitahuan Automatis:")
  print("  Tinjauan polaritas sentimen berita fundamental")
  print("  Laporan volatilitas ekstrem")
  print("  Identifikasi presisi anomali multidimensional")
  print("\n Transmisikan 'Ctrl+C' untuk mematikan layanan bot")
  print("="*70 + "\n")
  
  try:
    start_bot_listener()
  except KeyboardInterrupt:
    print("\n\n Sesi bot dihentikan secara sepihak oleh sistem administrator")
    return True
  except Exception as e:
    print(f"\n Interupsi fatal pada layanan bot: {e}")
    return False

if __name__ == "__main__":
  success = main()
  sys.exit(0 if success else 1)
