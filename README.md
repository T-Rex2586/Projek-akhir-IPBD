# 📈 Crypto Analytics Pipeline

Real-time cryptocurrency analytics dengan sentiment analysis dan anomaly detection.

## 🚀 Quick Start

### 1. Install
```bash
pip install -r requirements.txt
```

### 2. Setup Environment
```bash
cp .env.example .env
# Edit .env: set API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
```

### 3. Start Infrastructure (Docker)
Run the core infrastructure (PostgreSQL, Kafka, MinIO, MongoDB, Zookeeper) in Docker to keep your laptop light:
```bash
docker compose up -d
```

### 4. Initialize Database & Backfill Data
```bash
# Backfill 7 days historical data (Automatically initializes database tables)
python backfill_data.py
```

### 5. Run Application Components (Local)
Run the application services in separate terminals with your virtual environment activated:

**Terminal 1 - API:**
```bash
python -m api.main
```

**Terminal 2 - Dashboard:**
```bash
streamlit run dashboard/app.py
```

**Terminal 3 - Price Ingestion:**
```bash
python ingestion/binance_rest.py
```

**Terminal 4 - News Ingestion:**
```bash
python ingestion/rss_batch.py --mode continuous
```

## 📊 Access

- Dashboard: http://localhost:8501
- API Docs: http://localhost:8001/docs

## 🎯 Features

- Real-time price streaming (Binance)
- News sentiment analysis (7 sources)
- Anomaly detection (ML-based)
- LSTM price prediction
- Trading signals
- Telegram alerts
- Interactive dashboard
- REST API

## 🤖 ML Predictions (Optional)

Requires 2-3 days of data first.

### Train Model
```bash
python ml/training/train_lstm_model.py --symbol BTCUSDT
```

### Get Predictions
```bash
python ml/inference/lstm_inference.py --symbol BTCUSDT
```

## 📚 Documentation

See [CARA_RUN.md](CARA_RUN.md) for detailed Indonesian guide.

## 🛠️ Tech Stack

- Python 3.9+
- FastAPI
- Streamlit
- PostgreSQL
- Kafka
- MinIO
- Airflow
- TensorFlow/Keras
- scikit-learn

## 📝 License

MIT License

## ⚠️ Disclaimer

This is for educational purposes. ML predictions are not financial advice. Always DYOR!
