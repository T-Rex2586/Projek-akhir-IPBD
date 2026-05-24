# 🚀 Cara Menjalankan Crypto Pipeline

Panduan lengkap step-by-step untuk menjalankan project Crypto Sentiment & Price Analytics Pipeline.

## 📋 Persiapan Awal

### 1. System Requirements

- **OS**: Windows 10/11, Linux, atau macOS
- **Python**: 3.9 atau lebih baru
- **RAM**: Minimal 8GB (recommended 16GB)
- **Storage**: Minimal 10GB free space
- **Docker**: Docker Desktop (untuk Windows/Mac) atau Docker Engine (Linux)

### 2. Install Prerequisites

#### Windows:

```powershell
# Install Python dari python.org
# Download: https://www.python.org/downloads/

# Install Docker Desktop
# Download: https://www.docker.com/products/docker-desktop

# Verify installations
python --version
docker --version
docker-compose --version
```

#### Linux (Ubuntu/Debian):

```bash
# Install Python
sudo apt update
sudo apt install python3.9 python3-pip python3-venv

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo apt install docker-compose

# Verify
python3 --version
docker --version
docker-compose --version
```

## 🔧 Setup Project

### Step 1: Clone & Navigate

```bash
# Clone repository (ganti dengan URL repo Anda)
git clone https://github.com/your-username/crypto-pipeline.git
cd crypto-pipeline
```

### Step 2: Setup Environment Variables

```bash
# Copy template
cp .env.example .env
```

**Edit file `.env` dengan text editor:**

```bash
# Windows
notepad .env

# Linux/Mac
nano .env
```

**Isi kredensial yang diperlukan:**

```env
# Binance: TIDAK PERLU API key (menggunakan public endpoint)
# Reddit:  TIDAK PERLU API key (menggunakan YARS public scraper)

# Database (opsional, bisa pakai default)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=crypto_pipeline
DB_USER=postgres
DB_PASSWORD=postgres123

# API Security
API_KEY=my-secret-api-key-12345

# Telegram Bot (untuk alert real-time)
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIjKlMnOpQrStUvWxYz
TELEGRAM_CHAT_ID=987654321
```

#### 🤖 Cara Setup Telegram Bot untuk Alerting:

1. Buka **Telegram**, cari dan buka **@BotFather**
2. Ketik `/newbot` dan ikuti instruksinya:
   - Beri nama bot: `Crypto Pipeline Alert`
   - Beri username: `crypto_pipeline_alert_bot` (harus unik)
3. BotFather akan memberikan **token** — copy dan paste ke `TELEGRAM_BOT_TOKEN` di `.env`
4. Untuk mendapatkan **Chat ID**:
   - Buka **@userinfobot** atau **@RawDataBot** di Telegram
   - Ketik `/start` — bot akan menampilkan ID Anda
   - Copy dan paste ke `TELEGRAM_CHAT_ID` di `.env`
5. **Test alert** dengan menjalankan:
   ```bash
   python monitoring/telegram_alert.py
   ```
   Jika berhasil, Anda akan menerima pesan test di Telegram.

> **Tip**: Untuk mengirim alert ke **grup**, invite bot ke grup lalu gunakan Chat ID grup (biasanya bernilai negatif, contoh: `-1001234567890`).

*(Langkah pembuatan Reddit App / API Credentials **TIDAK PERLU DILAKUKAN** karena pipeline menggunakan YARS yang otomatis menggunakan public JSON scraping).*

### Step 3: Create Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

Setelah activate, prompt akan berubah jadi `(venv) ...`

### Step 4: Install Dependencies

```bash
# Upgrade pip
pip install --upgrade pip

# Install semua dependencies
pip install -r requirements.txt
```

**Proses ini akan memakan waktu 5-10 menit.**

Jika ada error saat install:
- **Windows**: Install Microsoft C++ Build Tools dari https://visualstudio.microsoft.com/visual-cpp-build-tools/
- **Linux**: `sudo apt install python3-dev build-essential`

## 🐳 Start Infrastructure Services

### Step 5: Start Docker Services

```bash
# Start PostgreSQL, MongoDB, Kafka, Redis
docker-compose up -d

# Check status
docker-compose ps
```

Output yang diharapkan:
```
NAME                  STATUS
crypto_postgres       Up
crypto_mongodb        Up
crypto_kafka          Up
crypto_zookeeper      Up
crypto_redis          Up
crypto_minio          Up
crypto_debezium       Up
```

**Tunggu 30 detik** agar semua services siap.

### Step 6: Initialize Database

```bash
# Create database tables
python -c "from storage.db_models import init_db; init_db()"
```

Output: `Tables created successfully` (atau tidak ada error)

### Step 6b: Register Debezium Postgres CDC Connector (Optional for CDC Ingestion)

Untuk mengaktifkan tracking CDC real-time dari database Silver ke Kafka, daftarkan connector Debezium via REST API:

```bash
# Windows (PowerShell)
Invoke-RestMethod -Uri "http://localhost:8083/connectors" -Method Post -ContentType "application/json" -InFile "storage/debezium_postgres_connector.json"

# Linux/Mac (curl)
curl -i -X POST -H "Accept:application/json" -H "Content-Type:application/json" http://localhost:8083/connectors/ -d @storage/debezium_postgres_connector.json
```

Untuk memverifikasi connector aktif:
```bash
curl http://localhost:8083/connectors/postgres-silver-connector/status
```

### Step 6c: Access MinIO Data Lake Console (Bronze Layer)

Anda dapat membuka web console MinIO di browser untuk melihat bucket raw files:
* **URL**: `http://localhost:9001`
* **Access Key**: `minioadmin`
* **Secret Key**: `minioadminpassword`
* **Bucket**: `bronze-crypto` (Raw data yang dipisahkan per folder sumber)

## ▶️ Menjalankan Pipeline

### Opsi A: Run Semua Komponen (Recommended)

Buka **4 terminal** terpisah (semua di folder project):

#### Terminal 1: Binance WebSocket (Real-time Price)

```bash
# Activate venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Run WebSocket stream
python ingestion/binance_websocket.py
```

Output yang diharapkan:
```
{"event": "websocket_streams_started", ...}
{"event": "kline_received", "symbol": "BTCUSDT", "close": 43250.5}
```

#### Terminal 2: Binance REST (Polling Ticker)

```bash
# Activate venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Run REST polling
python ingestion/binance_rest.py
```

Output:
```
{"event": "polling_started", ...}
{"event": "ticker_saved", "symbol": "BTCUSDT", "price": 43250.5}
```

#### Terminal 3: Reddit Stream (Sentiment)

```bash
# Activate venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Run Reddit stream
python ingestion/reddit_stream.py
```

Output:
```
{"event": "reddit_stream_started", ...}
{"event": "reddit_post_processed", "subreddit": "cryptocurrency", "sentiment": "positive"}
```

**Note**: Reddit scraper saat ini menggunakan YARS dengan metode polling interval (tiap 120 detik) agar aman dari rate limit. Anda tidak perlu setup kredensial apa pun untuk menjalankannya.

#### Terminal 4: FastAPI Server

```bash
# Activate venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Run API server
python api/main.py
```

Output:
```
INFO:     Started server process
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**Test API:**
```bash
# Windows PowerShell
Invoke-WebRequest -Uri "http://localhost:8000/health" -Headers @{"X-API-Key"="my-secret-api-key-12345"}

# Linux/Mac
curl -H "X-API-Key: my-secret-api-key-12345" http://localhost:8000/health
```

#### Terminal 5: Gold Layer Processor (Business Metrics Consolidation)

```bash
# Activate venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Run Gold Layer aggregator
python processing/gold_processor.py
```

Output:
```
{"event": "gold_processor_initialized", ...}
{"event": "gold_hourly_metrics_computed", "symbol": "BTCUSDT", ...}
```

### Step 7: Run Dashboard

Buka **terminal ke-6**:

```bash
# Activate venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Run Streamlit dashboard
streamlit run dashboard/app.py
```

Browser akan otomatis terbuka ke `http://localhost:8501`

**Dashboard akan menampilkan:**
- Real-time price chart
- Sentiment analysis
- Anomaly alerts
- News feed

## 🔄 Batch Processing (Optional)

### Manual Batch Run

```bash
# Run news batch processing
python ingestion/rss_batch.py
```

Output:
```
{"event": "batch_processing_started"}
{"event": "rss_feed_fetched", "source": "bbc", "articles_count": 50}
{"event": "batch_processing_completed", "total_saved": 45}
```

### Airflow Setup (Advanced)

```bash
# Set Airflow home
export AIRFLOW_HOME=$(pwd)/airflow  # Linux/Mac
set AIRFLOW_HOME=%cd%\airflow  # Windows

# Initialize Airflow DB
airflow db init

# Create admin user
airflow users create \
    --username admin \
    --password admin \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email admin@example.com

# Copy DAG files
mkdir -p $AIRFLOW_HOME/dags
cp dags/*.py $AIRFLOW_HOME/dags/

# Start webserver (terminal 1)
airflow webserver --port 8080

# Start scheduler (terminal 2)
airflow scheduler
```

Buka `http://localhost:8080` dan login dengan `admin/admin`

## ✅ Verifikasi

### Check Data Masuk ke Database

```bash
# Connect ke PostgreSQL
docker exec -it crypto_postgres psql -U postgres -d crypto_pipeline

# Query data
SELECT COUNT(*) FROM price_data;
SELECT COUNT(*) FROM kline_data;
SELECT COUNT(*) FROM news_articles;
SELECT COUNT(*) FROM reddit_posts;

# Exit
\q
```

### Check API Endpoints

```bash
# Get prices
curl -H "X-API-Key: my-secret-api-key-12345" \
  "http://localhost:8000/prices/BTCUSDT?hours=1"

# Get anomalies
curl -H "X-API-Key: my-secret-api-key-12345" \
  "http://localhost:8000/anomalies?hours=24"

# Get news
curl -H "X-API-Key: my-secret-api-key-12345" \
  "http://localhost:8000/news?limit=10"
```

## 🛑 Stop Pipeline

### Stop Python Processes

Di setiap terminal yang menjalankan Python script:
- Tekan `Ctrl+C`

### Stop Docker Services

```bash
# Stop semua containers
docker-compose down

# Stop dan hapus volumes (HATI-HATI: data akan hilang)
docker-compose down -v
```

## 🔧 Troubleshooting

### Problem: "ModuleNotFoundError"

**Solution:**
```bash
# Pastikan venv active
pip install -r requirements.txt
```

### Problem: "Connection refused" ke database

**Solution:**
```bash
# Check Docker services
docker-compose ps

# Restart services
docker-compose restart postgres
```

### Problem: Terkena Rate Limit Reddit (HTTP 429)

**Solution:**
- Secara default YARS membatasi polling tiap 120 detik.
- Jika masih terkena rate limit, naikkan `POLL_INTERVAL_SECONDS` di `ingestion/reddit_stream.py`.
- Untuk scraping skala besar, gunakan rotating proxy di inisialisasi `YARS(proxy="...")` di `reddit_stream.py`.

### Problem: "Rate limit exceeded" dari Binance

**Solution:**
- Kurangi polling frequency di `binance_rest.py`
- Gunakan WebSocket (lebih efisien)
- Tunggu beberapa menit

### Problem: Dashboard tidak menampilkan data

**Solution:**
1. Pastikan API server running (`http://localhost:8000/health`)
2. Check API_KEY di `.env` sama dengan yang di dashboard
3. Tunggu 1-2 menit sampai data masuk ke database

## 📊 Monitoring

### Check Logs

```bash
# View logs
tail -f logs/pipeline_*.log

# Search for errors
grep ERROR logs/pipeline_*.log
```

### Check Metrics

```bash
# Via API
curl -H "X-API-Key: my-secret-api-key-12345" \
  http://localhost:8000/health
```

## 🎯 Next Steps

Setelah pipeline berjalan:

1. **Customize Symbols**: Edit `SYMBOLS` di `ingestion/binance_*.py`
2. **Add More News Sources**: Edit `RSS_FEEDS` di `ingestion/rss_batch.py`
3. **Train ML Models**: Run `ml/models/anomaly_isolation_forest.py`
4. **Setup Alerts**: Implement email/Slack notifications
5. **Deploy to Production**: Use Docker, Kubernetes, atau cloud services

## 📞 Support

Jika ada masalah:
1. Check logs di folder `logs/`
2. Baca error message dengan teliti
3. Search error di Google/Stack Overflow
4. Buka issue di GitHub repository

---

**Happy Coding! 🚀**
