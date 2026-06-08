"""
🚀 PERFECT REAL-TIME CRYPTO ANALYTICS DASHBOARD

Features:
- ⚡ 1-second refresh for true real-time
- 🔄 Smart symbol switching with session persistence
- 🕐 WIB timezone throughout Indonesia
- 📊 Comprehensive metrics and analytics
- 🎨 Beautiful dark theme UI
- 📰 Clickable news with sentiment
- 🚨 Real-time anomaly detection
- 💹 Live price movements
"""

import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import os
import time
import sys

from dotenv import load_dotenv
load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.abspath('.'))
from monitoring.timezone_utils import now_wib

# ==================== CONFIGURATION ====================
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8001")
API_KEY = os.getenv("API_KEY", "dev-api-key")
HEADERS = {"X-API-Key": API_KEY}
REFRESH_INTERVAL = 1  # 1 second - TRUE REAL-TIME!

SYMBOLS = {
    "BTCUSDT": {"name": "Bitcoin", "emoji": "₿", "color": "#F7931A"},
    "ETHUSDT": {"name": "Ethereum", "emoji": "Ξ", "color": "#627EEA"},
    "BNBUSDT": {"name": "Binance Coin", "emoji": "🔸", "color": "#F3BA2F"},
    "SOLUSDT": {"name": "Solana", "emoji": "◎", "color": "#00FFA3"},
    "ADAUSDT": {"name": "Cardano", "emoji": "₳", "color": "#0033AD"}
}

# ==================== PAGE CONFIG ====================
st.set_page_config(
    page_title="🚀 Perfect Crypto Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== CUSTOM CSS ====================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    
    * { font-family: 'Inter', sans-serif; }
    
    .stApp {
        background: linear-gradient(135deg, #0a0a15 0%, #1a1a2e 50%, #16213e 100%);
    }
    
    h1 {
        background: linear-gradient(90deg, #60a5fa 0%, #a78bfa 50%, #ec4899 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.8rem !important;
        font-weight: 800 !important;
        margin-bottom: 0.5rem !important;
        letter-spacing: -0.02em;
    }
    
    .metric-card {
        background: linear-gradient(135deg, rgba(59, 130, 246, 0.15) 0%, rgba(139, 92, 246, 0.08) 100%);
        border: 1px solid rgba(59, 130, 246, 0.3);
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        transition: all 0.3s ease;
    }
    
    .metric-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 12px 48px rgba(59, 130, 246, 0.25);
        border-color: rgba(59, 130, 246, 0.5);
    }
    
    .status-badge {
        display: inline-block;
        padding: 8px 20px;
        border-radius: 24px;
        font-size: 0.85rem;
        font-weight: 700;
        letter-spacing: 0.5px;
        text-transform: uppercase;
        animation: pulse-border 2s infinite;
    }
    
    .status-live {
        background: rgba(16, 185, 129, 0.2);
        color: #10b981;
        border: 2px solid rgba(16, 185, 129, 0.6);
        box-shadow: 0 0 20px rgba(16, 185, 129, 0.3);
    }
    
    @keyframes pulse-border {
        0%, 100% { border-color: rgba(16, 185, 129, 0.6); }
        50% { border-color: rgba(16, 185, 129, 1); }
    }
    
    .info-card {
        background: rgba(15, 23, 42, 0.7);
        border: 1px solid rgba(59, 130, 246, 0.25);
        border-radius: 12px;
        padding: 16px;
        margin: 8px 0;
        backdrop-filter: blur(10px);
    }
    
    .news-card {
        background: rgba(15, 23, 42, 0.6);
        border-left: 3px solid rgba(59, 130, 246, 0.5);
        border-radius: 8px;
        padding: 12px 16px;
        margin: 8px 0;
        transition: all 0.2s ease;
    }
    
    .news-card:hover {
        background: rgba(15, 23, 42, 0.8);
        border-left-color: #3b82f6;
        transform: translateX(4px);
    }
    
    .price-up { color: #10b981; font-weight: 600; }
    .price-down { color: #ef4444; font-weight: 600; }
    
    div[data-testid="stMetricValue"] {
        font-size: 2.2rem;
        font-weight: 700;
    }
    
    .stTabs [data-baseweb="tab-list"] {
        gap: 12px;
        background: rgba(15, 23, 42, 0.5);
        padding: 10px;
        border-radius: 16px;
    }
    
    .stTabs [data-baseweb="tab"] {
        background: rgba(59, 130, 246, 0.1);
        border-radius: 10px;
        padding: 14px 28px;
        border: 1px solid rgba(59, 130, 246, 0.2);
        font-weight: 600;
        transition: all 0.2s ease;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        background: rgba(59, 130, 246, 0.15);
        border-color: rgba(59, 130, 246, 0.4);
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, rgba(59, 130, 246, 0.3), rgba(139, 92, 246, 0.25));
        border-color: #3b82f6;
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
    }
    
    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
        border-right: 1px solid rgba(59, 130, 246, 0.2);
    }
    
    /* Remove Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ==================== HELPER FUNCTIONS ====================

def fetch_api(endpoint, params=None):
    """Fetch data from API - NO CACHING for real-time"""
    try:
        response = requests.get(
            f"{API_BASE_URL}{endpoint}",
            headers=HEADERS,
            params=params,
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        st.error(f"⏱️ API timeout: {endpoint}")
        return None
    except requests.exceptions.ConnectionError:
        st.error(f"🔌 Cannot connect to API at {API_BASE_URL}")
        return None
    except Exception as e:
        st.error(f"❌ API Error: {str(e)}")
        return None

def calculate_stats(df, time_range_hours=24):
    """Calculate comprehensive statistics"""
    if df.empty:
        return {}
    
    current_price = df.iloc[-1]['price']
    price_start = df.iloc[0]['price']
    
    # Overall stats
    change_total = ((current_price - price_start) / price_start) * 100
    high_total = df['price'].max()
    low_total = df['price'].min()
    volume_total = df['volume'].sum() if 'volume' in df.columns else 0
    
    # 24H stats if we have enough data
    if len(df) > 288:  # ~24 hours of 5-min intervals
        df_24h = df.tail(288)
        price_24h_ago = df_24h.iloc[0]['price']
        change_24h = ((current_price - price_24h_ago) / price_24h_ago) * 100
        high_24h = df_24h['price'].max()
        low_24h = df_24h['price'].min()
        volume_24h = df_24h['volume'].sum() if 'volume' in df_24h.columns else 0
    else:
        change_24h = change_total
        high_24h = high_total
        low_24h = low_total
        volume_24h = volume_total
    
    # Volatility
    volatility = df['price'].pct_change().std() * 100 if len(df) > 1 else 0
    
    return {
        'current_price': current_price,
        'change_24h': change_24h,
        'high_24h': high_24h,
        'low_24h': low_24h,
        'volume_24h': volume_24h,
        'change_total': change_total,
        'high_total': high_total,
        'low_total': low_total,
        'volatility': volatility,
        'avg_price': df['price'].mean(),
        'total_volume': volume_total,
        'data_points': len(df)
    }

# ==================== SESSION STATE ====================

if 'initialized' not in st.session_state:
    st.session_state.initialized = True
    st.session_state.last_refresh = 0
    st.session_state.refresh_count = 0
    st.session_state.selected_symbol = "BTCUSDT"
    st.session_state.selected_time_range = "24H"
    st.session_state.last_interaction = 0

# ==================== AUTO-REFRESH LOGIC ====================

current_time = time.time()
user_interaction_timeout = 2

should_auto_refresh = (
    current_time - st.session_state.last_refresh > REFRESH_INTERVAL and
    current_time - st.session_state.get('last_interaction', 0) > user_interaction_timeout
)

if should_auto_refresh:
    st.session_state.last_refresh = current_time
    st.session_state.refresh_count += 1
    st.rerun()

# ==================== HEADER ====================

col_title, col_status = st.columns([4, 1])

with col_title:
    st.title("🚀 Crypto Analytics Dashboard")
    st.markdown("**Real-time monitoring with 1-second refresh** | Indonesia WIB Timezone")

with col_status:
    health = fetch_api("/health")
    if health:
        st.markdown('<div class="status-badge status-live">● LIVE</div>', unsafe_allow_html=True)
        st.caption(f"🔄 {st.session_state.refresh_count} refreshes")
    else:
        st.markdown('<div class="status-badge" style="background: rgba(239, 68, 68, 0.2); color: #ef4444; border-color: #ef4444;">● OFFLINE</div>', unsafe_allow_html=True)

st.divider()

# ==================== SIDEBAR ====================

st.sidebar.header("⚙️ Settings")

# Symbol selector
symbol_list = list(SYMBOLS.keys())
selected_symbol = st.sidebar.selectbox(
    "💎 Cryptocurrency",
    symbol_list,
    index=symbol_list.index(st.session_state.selected_symbol),
    format_func=lambda x: f"{SYMBOLS[x]['emoji']} {SYMBOLS[x]['name']} ({x})",
    key="symbol_selector"
)

# Time range selector
time_range = st.sidebar.select_slider(
    "📅 Time Range",
    options=["1H", "6H", "12H", "24H", "7D"],
    value=st.session_state.selected_time_range,
    key="time_range_selector"
)

# Update session state
if selected_symbol != st.session_state.selected_symbol:
    st.session_state.selected_symbol = selected_symbol
    st.session_state.last_interaction = time.time()

if time_range != st.session_state.selected_time_range:
    st.session_state.selected_time_range = time_range
    st.session_state.last_interaction = time.time()

# Convert time range to hours
time_range_hours = {
    "1H": 1, "6H": 6, "12H": 12, "24H": 24, "7D": 168
}.get(st.session_state.selected_time_range, 24)

st.sidebar.divider()

# Next refresh counter
time_since_refresh = int(current_time - st.session_state.last_refresh)
remaining = max(0, REFRESH_INTERVAL - time_since_refresh)
st.sidebar.metric("⏱️ Next Refresh", f"{remaining}s" if remaining > 0 else "Now!")

# System status
st.sidebar.subheader("📊 System Status")
if health:
    metrics = health.get('pipeline_metrics', {})
    st.sidebar.success("✅ API Connected")
    st.sidebar.metric("📈 Records", f"{metrics.get('records_processed', 0):,}")
    st.sidebar.metric("🚨 Anomalies", metrics.get('anomalies_detected', 0))
else:
    st.sidebar.error("❌ API Disconnected")

st.sidebar.divider()

# Current time display
current_wib = now_wib()
st.sidebar.info(f"🕐 **WIB Time**\n\n{current_wib.strftime('%Y-%m-%d %H:%M:%S')}")

# ==================== MAIN CONTENT ====================

# Use consistent variables
current_symbol = st.session_state.selected_symbol
current_time_range = st.session_state.selected_time_range

symbol_info = SYMBOLS[current_symbol]

# Fetch data
with st.spinner(f"Loading {symbol_info['name']} data..."):
    price_data = fetch_api(f"/prices/{current_symbol}", {"hours": time_range_hours})

if not price_data or len(price_data) == 0:
    st.error("⚠️ No data available")
    st.info("""
    **Quick Start:**
    1. Make sure Docker services are running: `docker compose up -d`
    2. Start WebSocket ingestion: `python ingestion/binance_websocket.py`
    3. Wait 2-3 minutes for data
    4. Refresh this dashboard
    """)
    st.stop()

# Process data
df = pd.DataFrame(price_data)

# Parse timestamps and convert UTC to WIB
try:
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    # Add 7 hours to convert UTC to WIB
    df['timestamp'] = df['timestamp'] + pd.Timedelta(hours=7)
except Exception as e:
    st.error(f"Timestamp error: {e}")

df = df.sort_values('timestamp')

# Calculate statistics
stats = calculate_stats(df, time_range_hours)

# ==================== OVERVIEW METRICS ====================

st.subheader(f"{symbol_info['emoji']} {symbol_info['name']} Overview — {current_time_range} — LIVE")

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric(
        "💰 Current Price",
        f"${stats['current_price']:,.2f}",
        f"{stats['change_24h']:+.2f}% (24H)",
        delta_color="normal"
    )

with col2:
    st.metric(
        "📈 24H High",
        f"${stats['high_24h']:,.2f}",
        f"Low: ${stats['low_24h']:,.2f}"
    )

with col3:
    st.metric(
        f"📊 {current_time_range} Change",
        f"{stats['change_total']:+.2f}%",
        f"High: ${stats['high_total']:,.2f}",
        delta_color="normal"
    )

with col4:
    st.metric(
        "💹 24H Volume",
        f"{stats['volume_24h']:,.0f}",
        "Trading Activity"
    )

with col5:
    st.metric(
        "⚡ Volatility",
        f"{stats['volatility']:.2f}%",
        "Price Std Dev"
    )

st.divider()

# ==================== TABS ====================

tab1, tab2, tab3, tab4 = st.tabs(["📊 Live Chart", "🕯️ Candlestick", "📰 News & Alerts", "📈 Analytics"])

# TAB 1: Live Price Chart
with tab1:
    col_chart, col_info = st.columns([3, 1])
    
    with col_chart:
        st.subheader(f"💹 {symbol_info['name']} Price — {current_time_range} — Real-time")
        
        # Create figure
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=[0.7, 0.3],
            subplot_titles=(f'{current_symbol} Price (USD)', 'Volume')
        )
        
        # Price line
        fig.add_trace(
            go.Scatter(
                x=df['timestamp'],
                y=df['price'],
                mode='lines',
                name='Price',
                line=dict(color=symbol_info['color'], width=3),
                fill='tozeroy',
                fillcolor=f"rgba{tuple(list(int(symbol_info['color'][i:i+2], 16) for i in (1, 3, 5)) + [0.1])}",
                hovertemplate='<b>$%{y:,.2f}</b><br>%{x}<extra></extra>'
            ),
            row=1, col=1
        )
        
        # Moving average
        if len(df) > 20:
            df['ma'] = df['price'].rolling(window=20).mean()
            fig.add_trace(
                go.Scatter(
                    x=df['timestamp'],
                    y=df['ma'],
                    mode='lines',
                    name='MA 20',
                    line=dict(color='#f59e0b', width=2, dash='dash'),
                    hovertemplate='<b>MA: $%{y:,.2f}</b><extra></extra>'
                ),
                row=1, col=1
            )
        
        # Volume bars
        colors = ['#10b981' if i > 0 and df.iloc[i]['price'] >= df.iloc[i-1]['price'] else '#ef4444' 
                 for i in range(len(df))]
        
        fig.add_trace(
            go.Bar(
                x=df['timestamp'],
                y=df['volume'],
                name='Volume',
                marker_color=colors,
                opacity=0.6,
                hovertemplate='<b>%{y:,.0f}</b><extra></extra>'
            ),
            row=2, col=1
        )
        
        fig.update_layout(
            height=600,
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(15,15,26,0.8)",
            hovermode='x unified',
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(59, 130, 246, 0.1)')
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(59, 130, 246, 0.1)')
        
        st.plotly_chart(fig, use_container_width=True)
    
    with col_info:
        st.subheader("📊 Quick Stats")
        
        st.markdown(f"""
        <div class="info-card">
            <h4 style="color: {symbol_info['color']};">Price Range</h4>
            <p><b>24H:</b> ${stats['low_24h']:,.2f} - ${stats['high_24h']:,.2f}</p>
            <p><b>{current_time_range}:</b> ${stats['low_total']:,.2f} - ${stats['high_total']:,.2f}</p>
        </div>
        
        <div class="info-card">
            <h4>Performance</h4>
            <p class="{'price-up' if stats['change_24h'] >= 0 else 'price-down'}">
                <b>24H:</b> {stats['change_24h']:+.2f}%
            </p>
            <p class="{'price-up' if stats['change_total'] >= 0 else 'price-down'}">
                <b>{current_time_range}:</b> {stats['change_total']:+.2f}%
            </p>
        </div>
        
        <div class="info-card">
            <h4>Trading</h4>
            <p><b>Avg Price:</b> ${stats['avg_price']:,.2f}</p>
            <p><b>Total Vol:</b> {stats['total_volume']:,.0f}</p>
            <p><b>Volatility:</b> {stats['volatility']:.2f}%</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.caption(f"📅 Last: {df.iloc[-1]['timestamp'].strftime('%H:%M:%S')} WIB")
        st.caption(f"📊 Points: {stats['data_points']:,}")

# TAB 2: Candlestick
with tab2:
    st.subheader("🕯️ Candlestick Chart")
    
    kline_data = fetch_api(f"/klines/{current_symbol}", {"limit": 168})
    
    if kline_data and len(kline_data) > 0:
        df_kline = pd.DataFrame(kline_data)
        
        # Parse timestamps and convert UTC to WIB
        try:
            df_kline['close_time'] = pd.to_datetime(df_kline['close_time'])
            df_kline['close_time'] = df_kline['close_time'] + pd.Timedelta(hours=7)
        except Exception as e:
            st.error(f"Timestamp error: {e}")
        
        df_kline = df_kline.sort_values('close_time')
        
        fig_candle = go.Figure(data=[go.Candlestick(
            x=df_kline['close_time'],
            open=df_kline['open'],
            high=df_kline['high'],
            low=df_kline['low'],
            close=df_kline['close'],
            increasing_line_color='#10b981',
            decreasing_line_color='#ef4444',
            increasing_fillcolor='#10b981',
            decreasing_fillcolor='#ef4444',
        )])
        
        fig_candle.update_layout(
            height=500,
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(15,15,26,0.8)",
            xaxis_rangeslider_visible=False,
            hovermode='x'
        )
        
        st.plotly_chart(fig_candle, use_container_width=True)
    else:
        st.info("💡 No candlestick data. Start WebSocket ingestion first.")

# TAB 3: News & Alerts
with tab3:
    col_news, col_anomaly = st.columns(2)
    
    with col_news:
        st.subheader("📰 Latest Crypto News")
        news = fetch_api("/news", {"limit": 10})
        
        if news and len(news) > 0:
            for article in news[:8]:
                sentiment = article.get('sentiment_label', 'neutral')
                score = article.get('sentiment_score', 0) or 0
                url = article.get('url', '#')
                
                emoji = '🟢' if sentiment == 'positive' else '🔴' if sentiment == 'negative' else '⚪'
                color = '#10b981' if sentiment == 'positive' else '#ef4444' if sentiment == 'negative' else '#6b7280'
                
                st.markdown(f"""
                <div class="news-card">
                    {emoji} <b>{article['title']}</b><br>
                    <small style="color: {color};">{article['source']} • {sentiment.upper()} ({score:+.2f})</small><br>
                    <small><a href="{url}" target="_blank" style="color: #3b82f6; text-decoration: none;">🔗 Read article →</a></small>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("💡 No news. Run: `python ingestion/rss_batch.py`")
    
    with col_anomaly:
        st.subheader("🚨 Anomaly Alerts")
        anomalies = fetch_api("/anomalies", {"hours": 24})
        
        if anomalies and len(anomalies) > 0:
            for anomaly in anomalies[:8]:
                severity = anomaly.get('severity', 'medium')
                emoji = '🔴' if severity == 'high' else '🟡' if severity == 'medium' else '🟢'
                
                st.markdown(f"""
                <div class="info-card">
                    {emoji} <b>{anomaly['event_type'].replace('_', ' ').title()}</b><br>
                    <small>{anomaly.get('symbol', 'N/A')} • {anomaly['description']}</small>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.success("✅ No anomalies in last 24 hours")

# TAB 4: Analytics
with tab4:
    st.subheader("📈 Advanced Analytics")
    
    col_a1, col_a2 = st.columns(2)
    
    with col_a1:
        # Price distribution
        fig_dist = go.Figure(data=[go.Histogram(
            x=df['price'],
            nbinsx=50,
            marker_color=symbol_info['color'],
            opacity=0.7,
            name='Price Distribution'
        )])
        
        fig_dist.update_layout(
            title="Price Distribution",
            height=300,
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(15,15,26,0.8)",
        )
        
        st.plotly_chart(fig_dist, use_container_width=True)
    
    with col_a2:
        # Hourly volume
        df_hourly = df.set_index('timestamp').resample('1h').agg({'volume': 'sum'}).reset_index()
        
        fig_vol = go.Figure(data=[go.Bar(
            x=df_hourly['timestamp'],
            y=df_hourly['volume'],
            marker_color='#a78bfa',
            name='Hourly Volume'
        )])
        
        fig_vol.update_layout(
            title="Hourly Volume Trend",
            height=300,
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(15,15,26,0.8)",
        )
        
        st.plotly_chart(fig_vol, use_container_width=True)

# ==================== FOOTER ====================

st.divider()

col_f1, col_f2, col_f3, col_f4 = st.columns(4)

with col_f1:
    last_data_time = df.iloc[-1]['timestamp']
    st.caption(f"📊 Last Data: {last_data_time.strftime('%Y-%m-%d %H:%M:%S')} WIB")

with col_f2:
    st.caption(f"🕐 Dashboard: {current_wib.strftime('%Y-%m-%d %H:%M:%S')} WIB")

with col_f3:
    st.caption(f"🔄 Auto-refresh: {REFRESH_INTERVAL}s")

with col_f4:
    st.caption(f"📈 Refreshes: {st.session_state.refresh_count:,}")

# Add subtle watermark
st.markdown("""
<div style="text-align: center; opacity: 0.5; margin-top: 20px; font-size: 0.8rem;">
    🚀 Perfect Real-time Crypto Analytics Dashboard | Powered by Streamlit
</div>
""", unsafe_allow_html=True)
