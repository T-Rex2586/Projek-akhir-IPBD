"""
Streamlit dashboard for crypto sentiment and price analytics.

Features:
- Real-time price metrics
- Candlestick chart (OHLCV)
- Price history line chart with volume
- Gold Layer correlation chart (Price vs Sentiment)
- News feed with sentiment
- Anomaly alerts
- Reddit sentiment breakdown
- Pipeline status monitoring
"""
import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "dev-api-key")
HEADERS = {"X-API-Key": API_KEY}

# Page config
st.set_page_config(
    page_title="Crypto Analytics Dashboard",
    page_icon="📈",
    layout="wide"
)

# Title
st.title("📈 Crypto Sentiment & Price Analytics Dashboard")
st.markdown("Real-time cryptocurrency price monitoring with sentiment analysis")


# Helper functions
def fetch_data(endpoint: str, params: dict = None):
    """Fetch data from API."""
    try:
        response = requests.get(
            f"{API_BASE_URL}{endpoint}",
            headers=HEADERS,
            params=params,
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error fetching data: {str(e)}")
        return None


# Sidebar
st.sidebar.header("⚙️ Settings")
selected_symbol = st.sidebar.selectbox(
    "Select Cryptocurrency",
    ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT"]
)
time_range = st.sidebar.slider("Time Range (hours)", 1, 168, 24)
kline_limit = st.sidebar.slider("Kline Candles", 20, 200, 100)
auto_refresh = st.sidebar.checkbox("Auto Refresh (30s)", value=False)

# Pipeline status in sidebar
st.sidebar.divider()
st.sidebar.header("🔗 Pipeline Status")
health = fetch_data("/health")
if health:
    st.sidebar.success(f"API: {health.get('status', 'unknown')}")
    pm = health.get("pipeline_metrics", {})
    st.sidebar.metric("Records Processed", pm.get("records_processed", 0))
    st.sidebar.metric("Anomalies Detected", pm.get("anomalies_detected", 0))
    st.sidebar.metric("Errors", pm.get("errors", 0))
else:
    st.sidebar.error("API Unreachable")


# ── Main content ─────────────────────────────────────────────────────

# Top metrics row
col1, col2, col3, col4 = st.columns(4)

# Fetch current price
prices = fetch_data(f"/prices/{selected_symbol}", {"hours": 1})
if prices and len(prices) > 0:
    current_price = prices[0]
    with col1:
        st.metric(
            label=f"💰 {selected_symbol} Price",
            value=f"${current_price['price']:,.2f}",
            delta=f"{current_price.get('volume', 0):,.0f} volume"
        )

# Fetch anomalies
anomalies = fetch_data("/anomalies", {"hours": time_range})
if anomalies is not None:
    with col2:
        st.metric(
            label="🚨 Anomalies",
            value=len(anomalies),
            delta=f"Last {time_range}h"
        )

# Fetch sentiment
reddit_sentiment = fetch_data("/sentiment/reddit", {"hours": time_range})
if reddit_sentiment:
    avg_sent = reddit_sentiment.get('avg_sentiment', 0)
    sentiment_label = "Positive" if avg_sent > 0.05 else "Negative" if avg_sent < -0.05 else "Neutral"
    with col3:
        st.metric(
            label="💬 Reddit Sentiment",
            value=sentiment_label,
            delta=f"{avg_sent:.3f}"
        )
    with col4:
        st.metric(
            label="📝 Total Posts",
            value=reddit_sentiment.get("total_posts", 0),
            delta=f"Last {time_range}h"
        )

st.divider()

# ── Candlestick Chart ────────────────────────────────────────────────

st.subheader(f"🕯️ {selected_symbol} Candlestick Chart")

kline_data = fetch_data(f"/klines/{selected_symbol}", {"limit": kline_limit})
if kline_data and len(kline_data) > 0:
    df_kline = pd.DataFrame(kline_data)
    df_kline['close_time'] = pd.to_datetime(df_kline['close_time'])
    if 'open_time' in df_kline.columns:
        df_kline['open_time'] = pd.to_datetime(df_kline['open_time'])
    df_kline = df_kline.sort_values('close_time')

    # Determine candle colors
    colors = ['#26a69a' if row['close'] >= row['open'] else '#ef5350' for _, row in df_kline.iterrows()]

    fig_candle = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        subplot_titles=('OHLC Candlestick', 'Volume'),
        row_heights=[0.75, 0.25]
    )

    # Candlestick trace
    fig_candle.add_trace(
        go.Candlestick(
            x=df_kline['close_time'],
            open=df_kline['open'],
            high=df_kline['high'],
            low=df_kline['low'],
            close=df_kline['close'],
            name='OHLC',
            increasing_line_color='#26a69a',
            decreasing_line_color='#ef5350',
        ),
        row=1, col=1
    )

    # Volume bars
    fig_candle.add_trace(
        go.Bar(
            x=df_kline['close_time'],
            y=df_kline['volume'],
            name='Volume',
            marker_color=colors,
            opacity=0.7,
        ),
        row=2, col=1
    )

    fig_candle.update_layout(
        height=550,
        showlegend=False,
        hovermode='x unified',
        template='plotly_dark',
        xaxis_rangeslider_visible=False,
    )
    fig_candle.update_xaxes(title_text="Time", row=2, col=1)
    fig_candle.update_yaxes(title_text="Price (USD)", row=1, col=1)
    fig_candle.update_yaxes(title_text="Volume", row=2, col=1)

    st.plotly_chart(fig_candle, use_container_width=True)
else:
    st.info("No kline data available. Run the Binance ingestion scripts first.")

st.divider()

# ── Price History Line Chart ─────────────────────────────────────────

st.subheader(f"💰 {selected_symbol} Price History")

price_data = fetch_data(f"/prices/{selected_symbol}", {"hours": time_range})
if price_data and len(price_data) > 0:
    df_price = pd.DataFrame(price_data)
    df_price['timestamp'] = pd.to_datetime(df_price['timestamp'])
    df_price = df_price.sort_values('timestamp')

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        subplot_titles=('Price', 'Volume'),
        row_heights=[0.7, 0.3]
    )

    # Price line
    fig.add_trace(
        go.Scatter(
            x=df_price['timestamp'],
            y=df_price['price'],
            mode='lines',
            name='Price',
            line=dict(color='#00e676', width=2)
        ),
        row=1, col=1
    )

    # Volume bars
    fig.add_trace(
        go.Bar(
            x=df_price['timestamp'],
            y=df_price['volume'],
            name='Volume',
            marker_color='#42a5f5',
            opacity=0.6,
        ),
        row=2, col=1
    )

    fig.update_layout(
        height=500,
        showlegend=True,
        hovermode='x unified',
        template='plotly_dark'
    )

    fig.update_xaxes(title_text="Time", row=2, col=1)
    fig.update_yaxes(title_text="Price (USD)", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)

    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No price data available")

st.divider()

# ── Gold Layer Section ───────────────────────────────────────────────

st.subheader("🏆 Gold Layer Consolidated Analytics")
st.markdown("Refined business-level metrics (Gold Layer) merging hourly average price, social sentiment, and anomalies.")

gold_data = fetch_data(f"/gold/metrics/{selected_symbol}", {"hours": time_range})
if gold_data and len(gold_data) > 0:
    df_gold = pd.DataFrame(gold_data)
    df_gold['window_start'] = pd.to_datetime(df_gold['window_start'])
    df_gold = df_gold.sort_values('window_start')

    # Dual-axis chart correlating Price and Sentiment
    fig_gold = make_subplots(specs=[[{"secondary_y": True}]])

    # Price Line (Primary Y)
    fig_gold.add_trace(
        go.Scatter(
            x=df_gold['window_start'],
            y=df_gold['avg_price'],
            name='Avg Price (USD)',
            line=dict(color='#ff9800', width=3)
        ),
        secondary_y=False
    )

    # Sentiment Score (Secondary Y)
    fig_gold.add_trace(
        go.Bar(
            x=df_gold['window_start'],
            y=df_gold['avg_sentiment'],
            name='Avg Sentiment',
            opacity=0.6,
            marker=dict(
                color=df_gold['avg_sentiment'],
                colorscale='RdYlGn',
                cmin=-0.8,
                cmax=0.8,
                showscale=False
            )
        ),
        secondary_y=True
    )

    fig_gold.update_layout(
        title=f"Price vs. Social Sentiment Correlation (1-Hour Windows) for {selected_symbol}",
        hovermode='x unified',
        template='plotly_dark',
        height=400,
        legend=dict(x=0.01, y=0.99)
    )

    fig_gold.update_xaxes(title_text="Time")
    fig_gold.update_yaxes(title_text="Price (USD)", secondary_y=False)
    fig_gold.update_yaxes(title_text="Sentiment Score (-1.0 to +1.0)", secondary_y=True)

    st.plotly_chart(fig_gold, use_container_width=True)
else:
    st.info("No Gold Layer aggregated metrics available yet. Compile them using the Gold Layer Processor!")

st.divider()

# ── News & Anomalies columns ────────────────────────────────────────

col_left, col_right = st.columns(2)

with col_left:
    st.subheader("📰 Recent News with Sentiment")
    news = fetch_data("/news", {"limit": 10})

    if news:
        for article in news:
            sentiment = article.get('sentiment_label', 'neutral')
            score = article.get('sentiment_score', 0) or 0

            # Color based on sentiment
            if sentiment == 'positive':
                color = "🟢"
            elif sentiment == 'negative':
                color = "🔴"
            else:
                color = "⚪"

            st.markdown(f"{color} **{article['title']}**")
            st.caption(f"{article['source']} | Sentiment: {sentiment} ({score:.2f})")
            st.markdown(f"[Read more]({article['url']})")
            st.divider()
    else:
        st.info("No news articles available")

with col_right:
    st.subheader("🚨 Recent Anomalies")

    if anomalies and len(anomalies) > 0:
        for anomaly in anomalies[:10]:
            severity = anomaly.get('severity', 'medium')

            # Color based on severity
            if severity == 'high':
                icon = "🔴"
            elif severity == 'medium':
                icon = "🟡"
            else:
                icon = "🟢"

            st.markdown(f"{icon} **{anomaly['event_type'].upper()}**")
            st.caption(f"{anomaly.get('symbol', 'N/A')} | {anomaly['detected_at']}")
            st.text(anomaly['description'])
            st.divider()
    else:
        st.success("No anomalies detected")

# ── Reddit Sentiment Breakdown ───────────────────────────────────────

st.divider()
st.subheader("💬 Reddit Sentiment Analysis")

if reddit_sentiment:
    col_a, col_b, col_c, col_d = st.columns(4)

    with col_a:
        st.metric("Total Posts", reddit_sentiment['total_posts'])
    with col_b:
        st.metric("Positive", reddit_sentiment['positive'], delta="🟢")
    with col_c:
        st.metric("Neutral", reddit_sentiment['neutral'], delta="⚪")
    with col_d:
        st.metric("Negative", reddit_sentiment['negative'], delta="🔴")

    # Sentiment pie chart
    fig_sentiment = go.Figure(data=[go.Pie(
        labels=['Positive', 'Neutral', 'Negative'],
        values=[
            reddit_sentiment['positive'],
            reddit_sentiment['neutral'],
            reddit_sentiment['negative']
        ],
        marker_colors=['#00e676', '#808080', '#ef5350'],
        hole=0.4,
    )])

    fig_sentiment.update_layout(
        title="Sentiment Distribution",
        template='plotly_dark',
        height=300
    )

    st.plotly_chart(fig_sentiment, use_container_width=True)

# ── Auto Refresh ─────────────────────────────────────────────────────

if auto_refresh:
    import time
    time.sleep(30)
    st.rerun()

# Footer
st.divider()
st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Powered by Medallion Architecture (Bronze → Silver → Gold)")
