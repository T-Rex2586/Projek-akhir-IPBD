# ₿ Bitcoin Real-time Analytics Pipeline

**Production-ready real-time Bitcoin analytics dashboard** dengan WebSocket streaming, sentiment analysis, dan anomaly detection.

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-red.svg)](https://streamlit.io/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 🎯 Features

### 📊 Real-time Dashboard (1-second refresh)
- Live Bitcoin price tracking via Binance WebSocket
- Interactive charts with volume analysis
- Candlestick OHLC visualization
- Fixed 24-hour timeframe for consistent monitoring
- WIB timezone for Indonesia market
- Full-width display without distractions

### 📰 News Sentiment Analysis
- RSS feed aggregation from 7+ crypto news sources
- VADER sentiment analysis
- Real-time sentiment tracking
- Clickable news links
- **Auto Telegram alerts** for positive/negative news

### 🤖 Telegram Bot Commands
- **/predict** - Get AI trading signal (BUY/SELL/HOLD) with LSTM prediction
- **/status** - System status and statistics
- **/help** - Show available commands
- **Auto-alerts** for news sentiment and anomalies

### 🚨 Anomaly Detection
- Price spike detection (>3% in 5 minutes)
- Volume surge alerts
- ML-based anomaly detection
- Telegram notifications

### 🏗️ Architecture
- **Real-time Streaming**: Binance WebSocket for live data
- **Silver Layer**: PostgreSQL for time-series data
- **API**: FastAPI with OpenAPI docs
- **Dashboard**: Streamlit with 1s refresh
- **Alerts**: Telegram notifications

## 🚀 Quick Start

### Prerequisites
```bash
- Python 3.9+
- Docker & Docker Compose
- 4GB RAM minimum
```

### Installation

1. **Clone & Setup**
```bash
git clone <your-repo-url>
cd bitcoin-analytics
cp .env.example .env
```

2. **Start Services**
```bash
docker-compose up -d
# Wait 30 seconds
```

3. **Run Production Startup**
```bash
python start_production.py
# This will:
# - Initialize database
# - Start WebSocket ingestion
# - Start API server
# - Wait for initial data
```

4. **Launch Dashboard**
```bash
streamlit run dashboard/app.py
# Open: http://localhost:8501
```

## 📊 Dashboard

The dashboard provides real-time monitoring:
- **Live Price**: Current Bitcoin price with 24H change
- **Interactive Charts**: Price history with moving averages
- **Volume Analysis**: Trading volume patterns
- **News Feed**: Latest crypto news with sentiment scores
- **Anomaly Alerts**: Unusual activity detection
- **Analytics**: Price distribution and trends

All data updates every 1 second for true real-time experience!

## 🗂️ Project Structure

```
bitcoin-analytics/
├── api/                    # FastAPI REST API
│   └── main.py
├── dashboard/              # Streamlit dashboard
│   └── app.py
├── ingestion/              # Data ingestion
│   ├── binance_websocket.py  # Real-time WebSocket
│   └── rss_batch.py          # News scraping
├── processing/             # Data processing
│   ├── stream_processor.py
│   └── batch_processor.py
├── ml/                     # Machine learning
│   ├── models/
│   ├── training/
│   └── inference/
├── storage/                # Data storage
│   ├── db_models.py
│   └── db_utils.py
├── monitoring/             # Logging & alerts
│   ├── telegram_alert.py
│   └── timezone_utils.py
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## 🔧 Configuration

### Environment Variables (.env)

```env
# Database
DB_HOST=localhost
DB_PORT=5435
DB_NAME=crypto_pipeline
DB_USER=postgres
DB_PASSWORD=postgres

# API
API_KEY=your-secure-api-key
API_PORT=8001

# Telegram Bot (Required for alerts & commands)
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id
```

### Setup Telegram Bot

1. **Create Bot**
   - Open Telegram and search for @BotFather
   - Send `/newbot` and follow instructions
   - Copy the bot token

2. **Get Chat ID**
   - Search for @userinfobot on Telegram
   - Send any message to get your chat ID

3. **Add to .env**
   ```env
   TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
   TELEGRAM_CHAT_ID=123456789
   ```

4. **Start Bot Listener**
   ```bash
   python start_telegram_bot.py
   ```

5. **Test Commands**
   - Send `/help` to your bot
   - Try `/predict` for trading signal
   - Use `/status` for system info

## 📡 API Endpoints

Base URL: `http://localhost:8001`

| Endpoint | Description |
|----------|-------------|
| `/health` | Health check with metrics |
| `/prices/BTCUSDT` | Real-time price history |
| `/klines/BTCUSDT` | Candlestick OHLC data |
| `/news` | News with sentiment |
| `/anomalies` | Detected anomalies |
| `/docs` | OpenAPI documentation |

## 🛠️ Usage

### Start Pipeline
```bash
# Option 1: Automated
python start_production.py

# Option 2: Manual
docker-compose up -d
python ingestion/binance_websocket.py  # Terminal 1
python api/main.py                     # Terminal 2
streamlit run dashboard/app.py         # Terminal 3
python start_telegram_bot.py           # Terminal 4 (Optional)
```

### Telegram Bot Commands
```bash
# In Telegram, send these commands to your bot:
/predict          # Get AI trading signal (BUY/SELL/HOLD)
/predict BTCUSDT  # Predict specific symbol
/status           # System status and stats
/help             # Show available commands
```

### News Scraping
```bash
# One-time scraping
python ingestion/rss_batch.py --mode batch

# Continuous (every 10 minutes)
python ingestion/rss_batch.py --mode continuous
```

### Reset Database
```bash
python reset_database.py
```

### Test Pipeline
```bash
python test_realtime_flow.py
```

## 📈 Performance

- **Dashboard Load**: <2 seconds
- **API Response**: <100ms
- **WebSocket Latency**: <500ms
- **Refresh Rate**: 1 second (real-time)

## 🔧 Troubleshooting

### No Data in Dashboard
```bash
# 1. Check WebSocket is running
# Terminal should show: "kline_received" messages

# 2. Test pipeline
python test_realtime_flow.py

# 3. Reset if needed
python reset_database.py
```

### Binance Connection Issues
- Use VPN if ISP blocks Binance
- Script has automatic fallback endpoints
- Check internet connection

## 📄 License

MIT License - see [LICENSE](LICENSE) file.

## ⚠️ Disclaimer

**Educational purposes only. Not financial advice.**
- Past performance ≠ future results
- Always DYOR (Do Your Own Research)
- Use proper risk management

## 🙏 Acknowledgments

- [Binance API](https://binance-docs.github.io/apidocs/)
- [Streamlit](https://streamlit.io/)
- [FastAPI](https://fastapi.tiangolo.com/)

---

**Made with ❤️ for Bitcoin community**

*Star ⭐ this repo if you find it useful!*

