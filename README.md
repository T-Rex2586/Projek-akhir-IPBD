# Crypto Sentiment & Price Analytics Pipeline

Big Data pipeline untuk memproses data harga cryptocurrency dan sentimen (berita + Reddit) secara real-time dan batch, dengan dashboard interaktif dan deteksi anomali.

## 🎯 Fitur Utama

- **Real-time Price Streaming**: WebSocket Binance untuk data harga live
- **Batch News Processing**: RSS feeds dari BBC dan TechCrunch
- **Reddit Sentiment Analysis**: Scraping dari subreddit crypto via YARS (tanpa API key)
- **Anomaly Detection**: ML-based (Isolation Forest) + rule-based price/volume/sentiment anomaly
- **Telegram Bot Alerts**: Notifikasi real-time ke Telegram untuk anomali, price spike, dan sentiment crash
- **Medallion Architecture**: Data lake 3 layer (Bronze/Silver/Gold) dengan MinIO & Debezium CDC
- **Interactive Dashboard**: Visualisasi dengan Streamlit (candlestick, line chart, sentiment pie)
- **REST API**: FastAPI untuk serving data dengan API Key authentication
- **Orchestration**: Apache Airflow untuk batch jobs
- **ML Pipeline**: Training, retraining, dan inference pipeline untuk Isolation Forest

## 🏗️ Arsitektur (Medallion Architecture)

```
Data Sources (Binance, Reddit, RSS)
    ↓
Ingestion Layer (WebSocket, REST, YARS)
    ↓
┌────────────────────────────┐
│  Bronze Layer (MinIO)      │  ← Raw data lake
│  Silver Layer (PostgreSQL) │  ← Cleaned & structured
│  Gold Layer (Aggregated)   │  ← Business-ready metrics
└────────────────────────────┘
    ↓
Processing (Stream Processor + Batch Processor + Gold Processor)
    ↓
ML Layer (VADER Sentiment + Isolation Forest Anomaly)
    ↓
Serving (FastAPI REST API)
    ↓
Dashboard (Streamlit)
    ↓
Alerting (Telegram Bot)
```

## 📋 Prerequisites

- Python 3.9+
- Docker & Docker Compose
- PostgreSQL 15+ (via Docker)
- MongoDB 7+ (via Docker)
- Kafka (via Docker, untuk streaming)

## 🚀 Quick Start

### 1. Clone Repository

```bash
git clone <repository-url>
cd crypto-pipeline
```

### 2. Setup Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env dan isi kredensial:
# - DB_PASSWORD
# - API_KEY
# - TELEGRAM_BOT_TOKEN (optional)
# - TELEGRAM_CHAT_ID (optional)
# (Reddit tidak perlu API key - menggunakan YARS)
```

### 3. Install Dependencies

```bash
# Buat virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Linux/Mac)
source venv/bin/activate

# Install packages
pip install -r requirements.txt
```

### 4. Start Infrastructure

```bash
# Start PostgreSQL, MongoDB, Kafka, MinIO, Airflow via Docker
docker-compose up -d

# Tunggu beberapa detik sampai services ready
docker-compose ps
```

### 5. Initialize Database

```bash
# Buat tables di PostgreSQL
python -c "from storage.db_models import init_db; init_db()"
```

### 6. Run Pipeline Components

Buka terminal terpisah untuk setiap komponen:

**Terminal 1 - Binance WebSocket Stream:**
```bash
python ingestion/binance_websocket.py
```

**Terminal 2 - Binance REST Polling:**
```bash
python ingestion/binance_rest.py
```

**Terminal 3 - Reddit Scraper (YARS):**
```bash
python ingestion/reddit_stream.py
```

**Terminal 4 - FastAPI Server:**
```bash
python api/main.py
```

**Terminal 5 - Gold Layer Processor:**
```bash
python processing/gold_processor.py
```

**Terminal 6 (optional) - Stream Processor:**
```bash
python processing/stream_processor.py
```

### 7. Run Dashboard

```bash
streamlit run dashboard/app.py
```

Dashboard akan terbuka di `http://localhost:8501`

## 📊 Dashboard Features

- **Candlestick Chart**: OHLCV candlestick chart real-time dari Binance kline data
- **Price History**: Grafik harga dan volume (line chart)
- **Gold Layer Analytics**: Korelasi harga vs sentimen (dual-axis chart)
- **Sentiment Analysis**: Analisis sentimen dari Reddit dan news
- **Anomaly Alerts**: Notifikasi anomali harga dan sentimen
- **News Feed**: Berita terbaru dengan sentiment score
- **Pipeline Status**: Monitoring health komponen pipeline
- **Multi-symbol Support**: BTC, ETH, BNB, SOL, ADA

## 🔄 Batch Processing

### Manual Run

```bash
# Run news batch processing
python ingestion/rss_batch.py

# Run full batch processor (quality check + rescore + daily stats)
python processing/batch_processor.py
```

### ML Model Training

```bash
# Train anomaly detection model
python ml/training/train_anomaly_model.py

# Run retrain pipeline (check + train + compare + swap)
python ml/training/retrain_pipeline.py

# Run batch inference
python ml/inference/batch_inference.py
```

### Airflow (Production)

```bash
# Airflow UI: http://localhost:8080
# Login: admin / admin

# Trigger DAG manually
airflow dags trigger news_batch_pipeline
```

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_sentiment.py -v
pytest tests/test_db_utils.py -v
pytest tests/test_api.py -v
```

## 📡 API Endpoints

Base URL: `http://localhost:8000`

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/` | GET | No | API info |
| `/health` | GET | No | Health check |
| `/prices/{symbol}` | GET | Yes | Get price history |
| `/klines/{symbol}` | GET | Yes | Get candlestick OHLCV data |
| `/anomalies` | GET | Yes | Get anomaly events |
| `/news` | GET | Yes | Get news articles with sentiment |
| `/sentiment/reddit` | GET | Yes | Get Reddit sentiment breakdown |
| `/gold/metrics/{symbol}` | GET | Yes | Get Gold Layer aggregated metrics |
| `/pipeline/status` | GET | Yes | Get pipeline component status |

**Authentication**: Endpoints with Auth=Yes require header `X-API-Key`

**Example:**
```bash
curl -H "X-API-Key: your-api-key" http://localhost:8000/prices/BTCUSDT?hours=24
curl -H "X-API-Key: your-api-key" http://localhost:8000/gold/metrics/BTCUSDT?hours=48
```

## 🔐 Security

- API Key authentication untuk semua data endpoints
- Kredensial disimpan di `.env` (tidak di-commit)
- Database connection menggunakan environment variables
- Input validation dengan Pydantic
- Global exception handler (tidak expose internal errors ke client)

## 📈 Monitoring

Logs disimpan di folder `logs/`:
- `pipeline_YYYYMMDD.log`: Structured logs (JSON format via structlog)

Metrics yang di-track:
- Records processed
- API calls
- Errors
- Anomalies detected
- Gold layer runs
- Telegram alerts sent

## 📁 Project Structure

```
crypto-pipeline/
├── ingestion/                 # Data ingestion modules
│   ├── binance_websocket.py   # WebSocket real-time price stream
│   ├── binance_rest.py        # REST polling (ticker, klines)
│   ├── reddit_stream.py       # YARS Reddit scraper
│   ├── rss_batch.py           # RSS news batch fetcher
│   └── yars/                  # Embedded YARS library
├── processing/                # Stream & batch processors
│   ├── stream_processor.py    # Kafka consumer + windowed anomaly detection
│   ├── batch_processor.py     # Data quality + rescore + daily stats
│   └── gold_processor.py      # Gold Layer hourly aggregator
├── ml/                        # Machine learning models
│   ├── models/
│   │   ├── sentiment_vader.py          # VADER sentiment scoring
│   │   └── anomaly_isolation_forest.py # Isolation Forest detector
│   ├── training/
│   │   ├── train_anomaly_model.py      # Model training script
│   │   └── retrain_pipeline.py         # Auto-retrain orchestrator
│   └── inference/
│       ├── stream_inference.py         # Real-time inference engine
│       └── batch_inference.py          # Bulk scoring engine
├── storage/                   # Database models & utilities
│   ├── db_models.py           # SQLAlchemy models (singleton engine)
│   ├── db_utils.py            # CRUD helpers with proper session mgmt
│   ├── minio_utils.py         # MinIO Bronze Layer utilities
│   └── debezium_postgres_connector.json
├── api/
│   └── main.py                # FastAPI serving layer
├── dashboard/
│   └── app.py                 # Streamlit dashboard
├── monitoring/
│   ├── logger.py              # Structured logging (structlog)
│   └── telegram_alert.py      # Telegram Bot alerting system
├── dags/
│   └── news_batch_dag.py      # Airflow DAG
├── tests/                     # Unit & integration tests
│   ├── conftest.py            # Shared fixtures (in-memory SQLite)
│   ├── test_sentiment.py      # VADER sentiment tests
│   ├── test_db_utils.py       # Database utility tests
│   └── test_api.py            # API endpoint tests
├── initdb/
│   └── 01_create_crypto_db.sql
├── docker-compose.yml         # Infrastructure (Postgres, Kafka, MinIO, Airflow, etc.)
├── requirements.txt           # Python dependencies
├── .env.example               # Environment variable template
├── .gitignore
├── CARA_RUN.md                # Panduan cara menjalankan (Bahasa Indonesia)
└── README.md                  # This file
```

## 🛠️ Troubleshooting

### Database Connection Error
```bash
docker ps | grep postgres
docker-compose restart postgres
```

### Reddit Scraping Error
YARS menggunakan public .json endpoint Reddit (tanpa API key):
- Jika terkena rate limit, naikkan `POLL_INTERVAL_SECONDS` di `reddit_stream.py`
- Pertimbangkan menggunakan rotating proxy

### MinIO Container Conflict
```bash
docker rm -f minio
docker-compose up -d
```

### Binance Rate Limit
- Kurangi polling frequency di `binance_rest.py`
- Gunakan WebSocket untuk data real-time (lebih efisien)

## 🤝 Contributing

1. Fork repository
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open Pull Request

## 📝 License

MIT License - see LICENSE file for details

## 🙏 Acknowledgments

- Binance API Documentation
- YARS (Yet Another Reddit Scraper) - https://github.com/datavorous/yars
- Apache Airflow Community
- Streamlit Team
