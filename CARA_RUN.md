# Cara Menjalankan Proyek secara Lengkap (Lokal / PC)

Panduan ini ditujukan bagi Anda yang ingin menjalankan **PRO_TERMINAL Crypto Pipeline** di komputer lokal (Windows/Mac/Linux) untuk keperluan *development* atau presentasi (sidang).

Jika Anda ingin mendeploy ke server produksi/VPS yang berjalan 24/7, silakan ikuti panduan di `DEPLOY_VPS.md`.

---

## 1. Persiapan Kebutuhan Sistem (Prerequisites)
Pastikan aplikasi berikut sudah terinstal di komputer Anda:
1. **Python 3.10+**
2. **Node.js** (Minimal versi 18.x)
3. **Docker Desktop** (untuk Windows/Mac) atau **Docker Engine & Docker Compose** (untuk Linux)
4. **Git**

---

## 2. Persiapan Environment
Semua kunci rahasia disimpan di file `.env`.

1. Duplikat file `.env.example` dan ubah namanya menjadi `.env`.
  ```bash
  cp .env.example .env
  ```
2. Buka file `.env` dan isi token Telegram Anda (wajib untuk fitur Alert & Chatbot):
  ```ini
  TELEGRAM_BOT_TOKEN="123456789:ABCDefghIJKLmnopQRSTuvwxyz"
  TELEGRAM_CHAT_ID="ID_TELEGRAM_ANDA"
  ADMIN_TELEGRAM_CHAT_ID="ID_TELEGRAM_ANDA" # Untuk notif error Airflow
  ```

---

## 3. Menjalankan Infrastruktur Data (Docker)
Proyek ini mengandalkan beberapa *service* (PostgreSQL, Kafka, Zookeeper, MinIO, MongoDB, dan Grafana).

1. Buka terminal/Command Prompt di root folder proyek Anda.
2. Jalankan perintah berikut untuk mengunduh dan menyalakan semua kontainer:
  ```bash
  docker-compose up -d
  ```
3. Pastikan semuanya berjalan tanpa *error* dengan mengecek statusnya:
  ```bash
  docker-compose ps
  ```

---

## 4. Setup Python Environment & Database
Kita perlu menginstal semua library Python dan membuat kerangka tabel di database.

1. Buat Virtual Environment:
  ```bash
  python -m venv venv
  ```
2. Aktifkan Virtual Environment:
  - **Windows**: `venv\Scripts\activate`
  - **Mac/Linux**: `source venv/bin/activate`
3. Install Library/Dependencies:
  ```bash
  pip install -r requirements.txt
  ```
4. Inisialisasi Tabel Database:
  ```bash
  python -c "from storage.db_models import init_db; init_db()"
  ```

---

## 5. Menjalankan Pipeline Python
Anda dapat menjalankan komponen utama secara terpusat menggunakan skrip otomatis yang telah disediakan.

1. Buka terminal (pastikan virtual environment `venv` sudah aktif).
2. Eksekusi skrip produksi utama:
  ```bash
  python scripts/start_production.py
  ```
  *(Skrip ini akan mengecek Docker, menginisialisasi database, dan secara otomatis membuka terminal/window baru untuk menjalankan API Server dan WebSocket Binance).*

3. (Opsional) Untuk mengaktifkan Bot Telegram, buka tab terminal baru (aktifkan `venv` lagi), lalu jalankan:
  ```bash
  python scripts/start_telegram_bot.py
  ```

4. (Opsional) Untuk memproses Lapisan Emas (Gold Layer) yang mengakumulasi agregasi secara periodik, buka tab terminal baru dan jalankan:
  ```bash
  python processing/gold_processor.py
  ```

---

## 6. Menjalankan Airflow (Batch Processing)
Airflow digunakan untuk mengambil berita (news), memproses sentimennya, dan mengirim laporan ringkasan harian.

Kini Airflow berjalan secara otomatis di dalam kontainer Docker bersama dengan infrastruktur data lainnya.

1. Pastikan Anda telah menjalankan perintah `docker-compose up -d` (seperti pada Langkah 3).
2. Airflow Webserver dapat diakses secara lokal melalui browser.
3. Buka **http://localhost:8080**
4. Login menggunakan *username*: `admin` dan *password*: `admin`.
5. Cari DAG bernama `news_batch_pipeline` lalu aktifkan (toggle ke posisi *On*).

---

## 7. Menjalankan Dashboard (UI React)
Dashboard berfungsi memvisualisasikan seluruh data yang ada di database.

1. Buka Terminal baru, arahkan ke folder `dashboard`:
  ```bash
  cd dashboard
  ```
2. Install library JavaScript:
  ```bash
  npm install
  ```
3. Jalankan server React:
  ```bash
  npm run dev
  ```
4. Buka browser Anda dan akses: **`http://localhost:5173`**

---

## 8. Mengakses Grafana (Monitoring System)
Grafana sudah diatur agar otomatis terhubung ke PostgreSQL.
1. Buka browser dan masuk ke **`http://localhost:3000`**
2. Login dengan kredensial:
  - **Username**: `admin`
  - **Password**: `admin`
3. Masuk ke menu `Dashboards` -> `New Dashboard` untuk mulai membuat grafik memonitor performa server atau database.

---

## Cara Mematikan Sistem
Jika Anda sudah selesai melakukan presentasi / pengetesan:
1. Hentikan semua proses Python & React di terminal Anda dengan menekan **`Ctrl + C`**.
2. Matikan kontainer infrastruktur Docker:
  ```bash
  docker-compose down
  ```
