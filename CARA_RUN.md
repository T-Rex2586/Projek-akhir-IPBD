# 🚀 Cara Menjalankan Bitcoin Analytics Pipeline

Pipeline real-time untuk analisis Bitcoin dengan WebSocket, sentiment analysis, dan dashboard interaktif.

---

## 📋 Kebutuhan Sistem

```bash
# Python packages
pip install -r requirements.txt

# Docker untuk services
docker --version
docker-compose --version
```

---

## ⚡ Quick Start (Real-time Mode)

### 1. Setup Environment
```bash
# Copy dan edit environment
cp .env.example .env

# Edit .env file - WAJIB isi:
# TELEGRAM_BOT_TOKEN=bot_token_dari_botfather
# TELEGRAM_CHAT_ID=chat_id_anda
```

**Setup Telegram Bot (Untuk Alerts & Commands):**
1. Buka Telegram, cari @BotFather
2. Kirim `/newbot` dan ikuti instruksi
3. Copy bot token yang diberikan
4. Cari @userinfobot, kirim pesan untuk dapat chat ID
5. Masukkan ke file `.env`

### 2. Start Infrastructure
```bash
# Start PostgreSQL, Kafka, MinIO
docker-compose up -d

# Wait for services to be ready (30 seconds)
```

### 3. Initialize Database
```bash
# Create tables
python -c "from storage.db_models import init_db; init_db()"
```

### 4. Start Real-time Data Ingestion
```bash
# Terminal 1: WebSocket real-time data (WAJIB untuk dashboard)
python ingestion/binance_websocket.py
# Biarkan berjalan terus - ini sumber data real-time Bitcoin

# Terminal 2: API Server (WAJIB untuk dashboard)  
python -m api.main
# API akan berjalan di http://localhost:8001
```

### 5. Start Dashboard (Real-time 1-detik refresh!)
```bash
# Terminal 3: Dashboard real-time
streamlit run dashboard/app.py
# Dashboard: http://localhost:8501
# Refresh otomatis setiap 1 detik!
```

### 6. Start Telegram Bot (OPSIONAL tapi RECOMMENDED!)
```bash
# Terminal 4: Telegram Bot untuk commands
python start_telegram_bot.py
# Bot akan listen untuk commands:
# /predict - AI trading signal (BUY/SELL/HOLD)
# /status - System status
# /help - Daftar commands
```

---

## 📊 Dashboard Features

- **Real-time refresh**: 1 detik 
- **Bitcoin focused**: BTCUSDT only
- **Fixed timeframe**: Always 24 hours data
- **Live charts**: Price, volume, candlestick (WIB timezone)
- **Timezone**: WIB Indonesia (sudah fix!)
- **Clickable news links**: Link langsung ke artikel
- **Anomaly detection**: Real-time alerts
- **No distractions**: Full-width, no sidebar!

## 🤖 Telegram Bot Features

**Commands yang bisa digunakan:**
- `/predict` atau `/predict BTCUSDT` - Dapatkan sinyal trading AI (BUY/SELL/HOLD)
- `/status` - Status sistem dan statistik
- `/help` - Daftar semua commands

**Auto-Alerts (otomatis kirim ke Telegram):**
- 🟢 Berita positif (sentiment > 0.5)
- 🔴 Berita negatif (sentiment < -0.5)
- 💹 Price spike alerts
- 📊 Volume surge alerts
- 🚨 Anomaly detections

---

## 🔧 Components Optional

### News Scraping (Opsional)
```bash
# Manual news fetch
python ingestion/rss_batch.py

# Atau setup cron job untuk otomatis setiap jam
```

### ML Training (Opsional)
```bash
# Train LSTM model untuk prediksi harga
python ml/training/train_lstm_model.py --symbol BTCUSDT --days 7 --epochs 50

# Get predictions
python ml/inference/lstm_inference.py --symbol BTCUSDT
```

---

## 🚨 Troubleshooting

### Dashboard Tidak Menampilkan Data
```bash
# 1. Cek WebSocket berjalan
# Pastikan terminal python ingestion/binance_websocket.py masih aktif
# Harus ada output: "kline_received" setiap menit

# 2. Cek API server
curl http://localhost:8001/health

# 3. Test data flow
python test_realtime_flow.py

# 4. Reset database jika perlu
python reset_database.py
```

### Timezone Tidak Sesuai
- Timestamp sudah dalam format yang benar
- Tidak perlu konversi manual
- Dashboard akan display sesuai data dari API

### Data Tidak Real-time
- Pastikan `python ingestion/binance_websocket.py` aktif
- Dashboard refresh 1 detik otomatis
- Jangan pause atau close browser tab

### Binance API Timeout
```bash
# Gunakan VPN jika ISP block Binance
# Atau ganti network (hotspot HP, WiFi lain)
# Script sudah ada fallback ke multiple endpoints
```

---

## 📋 Urutan Operasional Harian

```bash
# 1. Start services
docker-compose up -d

# 2. Start data ingestion (WAJIB - jangan dimatikan)
python ingestion/binance_websocket.py &

# 3. Start API server (WAJIB untuk dashboard)  
python api/main.py &

# 4. Start dashboard
streamlit run dashboard/app.py

# 5. Start Telegram Bot (RECOMMENDED!)
python start_telegram_bot.py &

# 6. Optional: News scraping dengan auto-alerts
python ingestion/rss_batch.py --mode continuous
```

---

## 🌐 URLs

- **Dashboard**: http://localhost:8501
- **API Docs**: http://localhost:8001/docs  
- **Health Check**: http://localhost:8001/health
- **API Base**: http://localhost:8001

---

## 💡 Tips

- **Real-time**: WebSocket + API + Dashboard = refresh 1 detik
- **Bitcoin only**: Fokus pada crypto #1
- **Timezone**: Sudah fix di WIB untuk candlestick dan semua charts!
- **News**: Link clickable langsung ke artikel + auto-alert ke Telegram
- **Telegram Bot**: Minta prediksi kapan saja dengan `/predict`
- **Performance**: Optimized untuk 1-detik refresh

## 🤖 Telegram Bot Tips

**Cara pakai:**
1. Pastikan bot sudah jalan: `python start_telegram_bot.py`
2. Buka Telegram, cari bot anda
3. Kirim `/help` untuk daftar commands
4. Kirim `/predict` untuk sinyal trading
5. Bot akan auto-alert untuk berita penting!

**Sinyal Trading:**
- 🟢 BUY = Harga diprediksi naik
- 🔴 SELL = Harga diprediksi turun  
- 🟡 HOLD = Harga stabil

⚠️ **Disclaimer**: Bukan financial advice - DYOR!

---

## 📞 Detail Lengkap

Untuk setup lengkap, ML training, dan troubleshooting detail:
- **Main Documentation**: `README.md`

Untuk bantuan: periksa logs di folder `logs/`

---

**₿ Happy Bitcoin Monitoring! 🚀**
