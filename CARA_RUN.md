# � Cara Menjalankan Crypto Analytics Pipeline

Pipeline real-time untuk analisis cryptocurrency dengan WebSocket, sentiment analysis, dan dashboard interaktif.

## � Kebutuhan Sistem

```bash
# Python packages
pip install -r requirements.txt

# Docker untuk services
docker --version
docker-compose --version
```

## ⚡ Quick Start (Real-time Mode)

### 1. Setup Environment
```bash
# Copy dan edit environment
cp .env.example .env
# Edit TELEGRAM_BOT_TOKEN dan TELEGRAM_CHAT_ID jika perlu
```

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
# Biarkan berjalan terus - ini sumber data real-time

# Terminal 2: API Server (WAJIB untuk dashboard)  
python api/main.py
# API akan berjalan di http://localhost:8001
```

### 5. Test Real-time Flow
```bash
# Test apakah semua komponen terhubung
python test_realtime_flow.py

# Jika ada masalah, sync manual:
python processing/kline_to_price_sync.py --all
```

### 6. Start Dashboard (Real-time 1-detik refresh!)
```bash
# Terminal 3: Dashboard real-time
streamlit run dashboard/app.py
# Dashboard: http://localhost:8501
# Refresh otomatis setiap 1 detik!
```

## 📊 Dashboard Features

- **Real-time refresh**: 1 detik 
- **Multi-symbol**: BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT
- **Time ranges**: 1H, 6H, 12H, 24H, 7D
- **Live charts**: Price, volume, candlestick
- **Timezone**: WIB Indonesia
- **Clickable news links**: Link langsung ke artikel
- **Anomaly detection**: Real-time alerts

## 🔧 Components Optional

### News Scraping (Opsional)
```bash
# Manual news fetch
python ingestion/rss_batch.py

# Atau setup cron job untuk otomatis setiap jam
```

### Backfill Data Historis (Opsional)  
```bash
# Isi data historis jika diperlukan
python backfill_data.py --symbol BTCUSDT --days 7
```

### ML Training (Opsional)
```bash
# Train LSTM model jika ingin prediksi
python ml/training/train_lstm_model.py --symbol BTCUSDT
```

## 🚨 Troubleshooting

### Dashboard Tidak Menampilkan Data
```bash
# 1. Cek WebSocket berjalan
# Pastikan terminal python ingestion/binance_websocket.py masih aktif

# 2. Cek API server
curl http://localhost:8001/health

# 3. Test data flow
python test_realtime_flow.py

# 4. Manual sync jika perlu
python processing/kline_to_price_sync.py --all
```

### Symbol Tidak Berganti di Dashboard
- Dashboard sudah diperbaiki dengan session state persistence
- Pilih symbol → tunggu 1-2 detik untuk refresh otomatis
- Data akan otomatis switch ke symbol yang dipilih

### Timezone Tidak Sesuai
- Semua waktu sudah dikonversi ke WIB
- WebSocket data → API → Dashboard semuanya WIB
- Telegram alerts juga menggunakan WIB

### Data Tidak Real-time
- Pastikan `python ingestion/binance_websocket.py` aktif
- Dashboard refresh 1 detik, bukan 10 detik lagi
- API menggunakan data dari WebSocket (KlineData table)

## 📋 Urutan Operasional Harian

```bash
# 1. Start services
docker-compose up -d

# 2. Start data ingestion (WAJIB - jangan dimatikan)
python ingestion/binance_websocket.py &

# 3. Start API server (WAJIB untuk dashboard)  
python -m api.main &

# 4. Start dashboard
streamlit run dashboard/app.py

# 5. Optional: News scraping
python ingestion/rss_batch.py
```

## 🌐 URLs

- **Dashboard**: http://localhost:8501
- **API Docs**: http://localhost:8001/docs  
- **Health Check**: http://localhost:8001/health

## 💡 Tips

- **Real-time**: WebSocket + API + Dashboard = refresh 1 detik
- **Symbols**: Semua crypto (BTC, ETH, BNB, SOL) real-time
- **Timezone**: Semua dalam WIB Indonesia  
- **News**: Link clickable langsung ke artikel
- **Performance**: Dashboard optimized untuk 1-detik refresh

## 📞 Detail Lengkap & Troubleshooting

Untuk setup lengkap, ML training, dan troubleshooting detail, lihat file dokumentasi lengkap di repository.

Untuk bantuan: periksa logs di folder `logs/`
