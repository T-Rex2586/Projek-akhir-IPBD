# CLAUDE.md — Crypto Sentiment & Price Analytics Pipeline (Binance Edition)

> Dokumen ini adalah panduan konteks untuk Claude Code agar memahami arsitektur,
> tujuan, dan standar implementasi project ini secara menyeluruh.

---

## 🎯 Tujuan Project

Membangun **Big Data Pipeline end-to-end** untuk memproses data harga cryptocurrency
dan sentimen (berita + Reddit) secara real-time maupun terjadwal, lalu menyajikannya
dalam dashboard interaktif dengan kemampuan deteksi anomali dan integrasi model ML.

---

## 🏗️ 1. Perancangan Arsitektur Pipeline (10 poin)

Arsitektur mengikuti pola **Lambda Architecture**:

```
Data Source → Processing → Storage → Serving → Dashboard
```

### Alur Lengkap

```
┌──────────────────────────────────────────────────────────────┐
│                        DATA SOURCES                          │
│  Binance API   │ Reddit API │ BBC RSS │ TechCrunch RSS       │
└────────────────────────────┬─────────────────────────────────┘
                             │
              ┌──────────────┴──────────────┐
              ▼                             ▼
   ┌─────────────────────┐      ┌─────────────────────┐
   │   STREAMING LAYER   │      │    BATCH LAYER       │
   │  (Apache Kafka /    │      │  (Apache Spark /     │
   │   Spark Streaming)  │      │   Airflow DAG)       │
   │                     │      │                      │
   │ - Price stream      │      │ - News scraping      │
   │ - Reddit sentiment  │      │ - Sentiment analysis │
   │ - Anomaly detection │      │ - Daily summary      │
   └──────────┬──────────┘      └──────────┬───────────┘
              │                            │
              └──────────────┬─────────────┘
                             ▼
              ┌──────────────────────────────┐
              │           STORAGE            │
              │  PostgreSQL / MongoDB        │
              │  (raw + processed + metrics) │
              └──────────────┬───────────────┘
                             ▼
              ┌──────────────────────────────┐
              │       SERVING LAYER          │
              │  FastAPI / Flask REST API    │
              └──────────────┬───────────────┘
                             ▼
              ┌──────────────────────────────┐
              │         DASHBOARD            │
              │  Streamlit / Grafana         │
              └──────────────────────────────┘
```

### Komponen Utama

| Komponen | Teknologi | Keterangan |
|---|---|---|
| Ingestion | Python requests, YARS, websockets | Ambil data dari Binance API, Reddit & RSS |
| Stream Processing | Kafka + Spark Streaming | Real-time price & sentiment |
| Batch Processing | Apache Spark / Pandas | News & daily analytics |
| Storage | PostgreSQL + MongoDB | Structured & semi-structured |
| Orchestration | Apache Airflow | Scheduling batch jobs |
| Serving | FastAPI | REST endpoint ke dashboard |
| Dashboard | Streamlit | Visualisasi interaktif |

---

## 🔵 2. Batch Processing (10 poin)

Batch dijalankan via **Apache Airflow DAG** atau cron scheduler.

### Sumber Data Batch

- **BBC News RSS**: `https://feeds.bbci.co.uk/news/rss.xml`
- **TechCrunch RSS**: `https://techcrunch.com/feed/`

### Pipeline Batch

```
RSS Fetch → XML Parse → Text Cleaning → Sentiment Scoring
    → Store to DB → Topic Summarization → Daily Report
```

### Jadwal

| Job | Interval | Keterangan |
|---|---|---|
| News scraping | Tiap 1 jam | Ambil artikel baru |
| Sentiment batch | Tiap 6 jam | Proses sentimen artikel |
| Daily summary | 00:00 setiap hari | Agregasi harian |
| Model retraining | Mingguan | Update model sentimen |

### Perbedaan Batch vs Streaming

| Aspek | Batch | Streaming |
|---|---|---|
| Latensi | Menit–jam | Detik |
| Sumber | BBC, TechCrunch | Reddit, Binance |
| Tujuan | Analisis mendalam | Deteksi anomali |
| Volume | Besar, periodik | Kecil, kontinu |

### Implementasi

```python
# Contoh struktur DAG Airflow
# dags/news_batch_dag.py

from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

default_args = {
    "owner": "pipeline",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="news_batch_pipeline",
    schedule_interval="0 */6 * * *",  # setiap 6 jam
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args=default_args,
) as dag:
    fetch_news = PythonOperator(task_id="fetch_news", python_callable=fetch_rss)
    clean_text = PythonOperator(task_id="clean_text", python_callable=clean_articles)
    score_sentiment = PythonOperator(task_id="sentiment", python_callable=run_sentiment)
    store_db = PythonOperator(task_id="store", python_callable=save_to_db)

    fetch_news >> clean_text >> score_sentiment >> store_db
```

---

## 🟢 3. Stream Processing (15 poin)

Stream diproses menggunakan **Kafka + Spark Streaming** atau **Python asyncio + websockets**.

### Sumber Data Streaming

- **Binance API** — harga & trade data real-time via REST + WebSocket Stream
- **Reddit (YARS)** — post & komentar subreddit r/cryptocurrency, r/bitcoin (tanpa API key)

### Binance API — Endpoint yang Digunakan

| Tipe | Endpoint | Data | Interval |
|---|---|---|---|
| REST | `GET /api/v3/ticker/price` | Harga terkini semua simbol | Pull tiap 10–30 detik |
| REST | `GET /api/v3/ticker/24hr` | 24h stats: volume, high, low, % change | Pull tiap 1 menit |
| REST | `GET /api/v3/klines` | Candlestick OHLCV data | Pull tiap 1–5 menit |
| WebSocket | `wss://stream.binance.com:9443/ws/<symbol>@trade` | Trade tick real-time | Push per transaksi |
| WebSocket | `wss://stream.binance.com:9443/ws/<symbol>@kline_1m` | Kline/candlestick 1 menit | Push per menit |
| WebSocket | `wss://stream.binance.com:9443/ws/<symbol>@aggTrade` | Aggregated trade stream | Push real-time |

> **Base URL REST**: `https://api.binance.com`
> **Base URL WebSocket**: `wss://stream.binance.com:9443`
> **Symbol contoh**: `BTCUSDT`, `ETHUSDT`, `BNBUSDT`

### Autentikasi Binance API

Pipeline ini **hanya menggunakan public endpoint** Binance yang tidak memerlukan API key:

```python
# Public endpoints yang digunakan (TANPA API key):
# - GET /api/v3/ticker/24hr  → harga dan statistik 24 jam
# - GET /api/v3/klines       → candlestick/kline data
# - WSS stream.binance.com   → WebSocket real-time kline stream

import requests

BASE_URL = "https://api.binance.com"

# Contoh fetch harga — langsung request tanpa header auth
resp = requests.get(f"{BASE_URL}/api/v3/ticker/24hr", params={"symbol": "BTCUSDT"})
data = resp.json()
print(f"BTCUSDT: ${data['lastPrice']}")
```

> **Catatan**: API key Binance **tidak diperlukan** untuk pipeline ini.
> Semua data harga, ticker, dan kline tersedia via public endpoint tanpa autentikasi.


### Contoh Implementasi REST Pull

```python
# ingestion/binance_rest.py
import requests
import time

BASE_URL = "https://api.binance.com"
SYMBOLS  = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]

def fetch_ticker_24hr(symbol: str) -> dict:
    """Ambil statistik 24 jam: harga, volume, % change."""
    resp = requests.get(
        f"{BASE_URL}/api/v3/ticker/24hr",
        params={"symbol": symbol},
        timeout=10
    )
    resp.raise_for_status()
    return resp.json()

def fetch_klines(symbol: str, interval: str = "1m", limit: int = 10) -> list:
    """Ambil candlestick OHLCV terbaru."""
    resp = requests.get(
        f"{BASE_URL}/api/v3/klines",
        params={"symbol": symbol, "interval": interval, "limit": limit},
        timeout=10
    )
    resp.raise_for_status()
    return resp.json()
    # Returns: [[open_time, open, high, low, close, volume, ...], ...]
```

### Contoh Implementasi WebSocket Stream

```python
# ingestion/binance_websocket.py
import asyncio
import websockets
import json

async def stream_trades(symbol: str):
    """Stream setiap transaksi real-time dari Binance."""
    url = f"wss://stream.binance.com:9443/ws/{symbol.lower()}@aggTrade"
    async with websockets.connect(url) as ws:
        while True:
            msg = await ws.recv()
            data = json.loads(msg)
            # data keys: e (event), E (time), s (symbol),
            #            p (price), q (quantity), T (trade time)
            yield {
                "symbol":    data["s"],
                "price":     float(data["p"]),
                "quantity":  float(data["q"]),
                "timestamp": data["T"],
            }

async def stream_kline(symbol: str, interval: str = "1m"):
    """Stream candlestick 1 menit real-time."""
    url = f"wss://stream.binance.com:9443/ws/{symbol.lower()}@kline_{interval}"
    async with websockets.connect(url) as ws:
        while True:
            msg = await ws.recv()
            data = json.loads(msg)
            kline = data["k"]
            if kline["x"]:  # hanya proses kline yang sudah closed
                yield {
                    "symbol": kline["s"],
                    "open":   float(kline["o"]),
                    "high":   float(kline["h"]),
                    "low":    float(kline["l"]),
                    "close":  float(kline["c"]),
                    "volume": float(kline["v"]),
                    "close_time": kline["T"],
                }
```

### Pipeline Streaming

```
Binance WebSocket ──► Kafka Topic: price_stream    ──► Spark Streaming ──► Anomaly Detection ──► Telegram Bot
Binance REST Poll ──► Kafka Topic: ticker_stream   ──►                 ──► Dashboard Update
Reddit YARS       ──► Kafka Topic: sentiment_stream ──► NLP Processor  ──► Telegram Bot
```

### Logika Anomaly Detection

```python
# Trigger anomali jika:
# 1. Perubahan harga > 3% dalam window 5 menit (dari kline stream)
# 2. Volume trade > 200% rata-rata 1 jam (dari aggTrade stream)
# 3. Lonjakan sentimen negatif dalam window 10 menit (dari Reddit)

PRICE_CHANGE_THRESHOLD   = 0.03    # 3%
SENTIMENT_SPIKE_THRESHOLD = -0.6   # skor < -0.6 = negatif kuat
VOLUME_SPIKE_MULTIPLIER  = 2.0     # 2x rata-rata 1 jam
```

### Rate Limit Binance

| Tipe | Limit | Keterangan |
|---|---|---|
| REST Request Weight | 1200 weight/menit | `GET /api/v3/ticker/24hr` = 40 weight |
| REST Order | 100 order/10 detik | Tidak relevan (kita read-only) |
| WebSocket Connection | Max 1024 stream per koneksi | Gunakan combined stream untuk efisiensi |

```python
# Gunakan combined stream untuk efisiensi (hemat koneksi)
# wss://stream.binance.com:9443/stream?streams=btcusdt@kline_1m/ethusdt@kline_1m
```

### Perbedaan dengan Batch

- Streaming memproses **per event** (satu record sekaligus)
- Batch memproses **per chunk** (kumpulan record)
- Streaming menggunakan **windowing** (sliding window 5–10 menit)
- Batch menggunakan **full scan** pada rentang waktu tertentu

---

## 🤖 4. Integrasi dengan Machine Learning (15 poin)

### Model yang Digunakan

| Model | Tugas | Library |
|---|---|---|
| VADER / TextBlob | Sentiment scoring cepat (streaming) | `nltk`, `textblob` |
| FinBERT | Sentiment keuangan (batch, akurat) | `transformers` |
| Isolation Forest | Anomaly detection harga | `scikit-learn` |
| LSTM / Prophet | Price forecasting | `tensorflow`, `prophet` |

### Alur Training

```
Historical Data → Feature Engineering → Train Model → Evaluate
    → Serialize (joblib/pickle) → Deploy ke Inference API
```

### Alur Inference

```
# Streaming inference (real-time)
new_price_data → load model → predict anomaly → emit alert

# Batch inference (scheduled)
collected_articles → FinBERT → sentiment_score → store DB
```

### Struktur File ML

```
ml/
├── models/
│   ├── sentiment_vader.py
│   ├── sentiment_finbert.py
│   ├── anomaly_isolation_forest.py
│   └── forecasting_prophet.py
├── training/
│   ├── train_anomaly_model.py
│   └── retrain_pipeline.py
└── inference/
    ├── stream_inference.py
    └── batch_inference.py
```

---

## 📊 5. Visualisasi & Dashboard (10 poin)

Dashboard dibangun dengan **Streamlit** (utama) atau **Grafana** (monitoring ops).

### Konten Dashboard

- [ ] Grafik harga BTC/ETH real-time (line chart, candlestick dari kline stream)
- [ ] Sentiment score timeline (per jam & harian)
- [ ] Anomaly alert indicator (merah jika triggered)
- [ ] Top berita terbaru dengan label sentimen
- [ ] Volume & 24h % change chart (dari Binance ticker/24hr)
- [ ] Daily summary card

### Standar Visualisasi

- Informatif: setiap chart punya judul, label axis, dan legenda
- Relevan: data yang ditampilkan sesuai konteks crypto
- Mudah dipahami: gunakan warna konsisten (hijau = positif, merah = negatif)

---

## 🔍 6. Monitoring & Logging (10 poin)

Setiap komponen pipeline **wajib** memiliki logging terstruktur.

### Library

```python
import logging
import structlog  # structured logging
```

### Yang Harus Di-log

| Event | Level | Keterangan |
|---|---|---|
| Pipeline start/stop | INFO | Setiap run batch/stream |
| Data fetch success | INFO | Jumlah record yang diambil |
| Processing error | ERROR | Exception + stack trace |
| Anomaly detected | WARNING | Detail event anomali |
| Model inference time | DEBUG | Latency per prediksi |
| DB write success/fail | INFO / ERROR | Jumlah row, error detail |

### Monitoring Metrics

- Throughput (record/detik)
- Latency (ms per proses)
- Error rate (%)
- Queue lag (Kafka consumer lag)

---

## 🚨 7. Alerting System (10 poin)

### Kondisi Alert

```python
ALERT_CONDITIONS = {
    "price_spike":      {"threshold": 0.03,  "window_minutes": 5},
    "sentiment_crash":  {"threshold": -0.6,  "window_minutes": 10},
    "volume_surge":     {"threshold": 2.0,   "window_minutes": 60},
    "pipeline_failure": {"retries_exceeded": 3},
}
```

### Mekanisme Notifikasi

- **Console alert**: log WARNING ke stdout
- **Email alert**: via SMTP (opsional)
- **Dashboard badge**: indikator merah di UI Streamlit
- **Webhook**: kirim POST ke endpoint (Slack / Discord, opsional)

### Contoh Implementasi

```python
def send_alert(alert_type: str, detail: dict):
    message = f"[ALERT] {alert_type.upper()} | {detail}"
    logger.warning(message)
    # Tambahkan channel notifikasi lain di sini
```

---

## 🔒 8. Keamanan Data (10 poin)

### Authentication & Authorization

- API endpoint FastAPI menggunakan **JWT token** atau **API Key header**
- Role: `admin` (full access), `viewer` (read-only dashboard)

```python
# Contoh header API Key
headers = {"X-API-Key": os.getenv("API_KEY")}
```

### Data Protection

- Semua kredensial (API key, DB password) disimpan di **`.env`** — tidak pernah di-commit
- File `.env` masuk `.gitignore`
- Gunakan `python-dotenv` untuk load env vars

```bash
# .env (JANGAN di-commit)
# Binance: tidak perlu API key (menggunakan public endpoint)
# Reddit:  tidak perlu API key (menggunakan YARS)
DB_PASSWORD=xxx
API_SECRET_KEY=xxx
TELEGRAM_BOT_TOKEN=xxx
TELEGRAM_CHAT_ID=xxx
```

- Data sensitif di database dienkripsi saat rest (encryption at rest)
- Koneksi database menggunakan SSL

---

## 📋 9. Governance Big Data (5 poin)

### Data Quality

- Validasi schema saat data masuk (gunakan `pydantic` atau `Great Expectations`)
- Deteksi nilai null / outlier ekstrem sebelum disimpan
- Catat jumlah record valid vs rejected per run

### Metadata

Setiap dataset menyimpan metadata:

```json
{
  "source": "binance",
  "ingested_at": "2024-01-15T10:30:00Z",
  "schema_version": "1.2",
  "record_count": 1440,
  "quality_score": 0.98
}
```

### Audit Trail

- Setiap transformasi data dicatat: siapa (proses apa), kapan, input → output
- Log disimpan minimal 30 hari

### Compliance

- Tidak menyimpan data personal pengguna
- Data publik dari API digunakan sesuai Terms of Service masing-masing provider

---

## 📁 10. Dokumentasi & Reproducibility (5 poin)

### Struktur Project

```
crypto-pipeline/
├── CLAUDE.md                  # ← file ini
├── README.md                  # setup & cara menjalankan
├── .env.example               # template env vars
├── docker-compose.yml         # jalankan semua service
├── requirements.txt
│
├── ingestion/
│   ├── binance_websocket.py   # WebSocket stream real-time
│   ├── binance_rest.py        # REST polling (ticker, klines)
│   ├── reddit_stream.py       # YARS-based Reddit scraper
│   ├── rss_batch.py
│   └── yars/                  # Embedded YARS Reddit scraper library
│       ├── __init__.py
│       ├── agents.py
│       ├── sessions.py
│       └── yars.py
│
├── processing/
│   ├── gold_processor.py      # Gold Layer hourly aggregator
│   ├── stream_processor.py
│   └── batch_processor.py
│
├── ml/
│   ├── models/
│   ├── training/
│   └── inference/
│
├── storage/
│   ├── db_models.py
│   ├── db_utils.py
│   ├── minio_utils.py                      # MinIO Bronze Layer utilities
│   └── debezium_postgres_connector.json    # Debezium CDC connector config
│
├── api/
│   └── main.py                # FastAPI serving
│
├── dashboard/
│   └── app.py                 # Streamlit dashboard
│
├── monitoring/
│   ├── logger.py
│   └── telegram_alert.py      # Telegram Bot alerting system
│
├── dags/                      # Airflow DAGs
│   └── news_batch_dag.py
│
└── tests/
    ├── test_batch.py
    ├── test_stream.py
    └── test_ml.py
```

### Cara Menjalankan (Reproducibility)

```bash
# 1. Clone & setup environment
git clone <repo>
cd crypto-pipeline
cp .env.example .env
# isi .env dengan kredensial kamu

# 2. Install dependencies
pip install -r requirements.txt

# 3. Jalankan semua service via Docker
docker-compose up -d

# 4. Jalankan pipeline
python ingestion/binance_websocket.py &  # WebSocket stream real-time
python ingestion/binance_rest.py &       # REST polling ticker & klines
python ingestion/reddit_stream.py &      # YARS Reddit scraper
airflow dags trigger news_batch_pipeline # batch news

# 5. Buka dashboard
streamlit run dashboard/app.py
```

### Requirements Utama

```
# requirements.txt
# YARS (embedded, no pip install needed)
requests>=2.31.0
websockets>=12.0          # Binance WebSocket stream
feedparser>=6.0.10
pandas>=2.0.0
pyspark>=3.5.0
kafka-python>=2.0.2
transformers>=4.35.0
scikit-learn>=1.3.0
prophet>=1.1.4
fastapi>=0.104.0
streamlit>=1.28.0
sqlalchemy>=2.0.0
python-dotenv>=1.0.0
pydantic>=2.4.0
structlog>=23.2.0
apache-airflow>=2.7.0
python-binance>=1.0.19    # opsional: wrapper resmi Binance
```

---

## ✅ Checklist Penilaian

| No | Aspek | Poin | Status |
|---|---|---|---|
| 1 | Perancangan Arsitektur Pipeline | 10 | ☐ |
| 2 | Batch Processing | 10 | ☐ |
| 3 | Stream Processing | 15 | ☐ |
| 4 | Integrasi Machine Learning | 15 | ☐ |
| 5 | Visualisasi & Dashboard | 10 | ☐ |
| 6 | Monitoring & Logging | 10 | ☐ |
| 7 | Alerting System | 10 | ☐ |
| 8 | Keamanan Data | 10 | ☐ |
| 9 | Governance Big Data | 5 | ☐ |
| 10 | Dokumentasi & Reproducibility | 5 | ☐ |
| **Total** | | **100** | |

---

*Dokumen ini harus diperbarui setiap kali ada perubahan arsitektur atau keputusan teknis besar.*
