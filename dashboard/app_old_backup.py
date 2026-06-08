"""
Real-time Crypto Analytics Dashboard
- Loads 7 days historical data on start
- Auto-refresh every 10 seconds for real-time updates
- Comprehensive metrics and beautiful UI
"""
import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import os
import time

from dotenv import load_dotenv
load_dotenv()

# Import WIB timezone utils
import sys
sys.path.insert(0, os.path.abspath('.'))
from monitoring.timezone_utils import now_wib, format_wib_short

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8001")
API_KEY = os.getenv("API_KEY", "dev-api-key")
HEADERS = {"X-API-Key": API_KEY}
REFRESH_INTERVAL = 1  # Changed to 1 second for real-time updates!

# Page config
st.set_page_config(
    page_title="Crypto Real-time Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Enhanced Custom CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    
    * {
        font-family: 'Inter', sans-serif;
    }
    
    .stApp {
        background: linear-gradient(135deg, #0a0a15 0%, #1a1a2e 50%, #16213e 100%);
    }
    
    h1, h2, h3 {
        font-weight: 700;
        letter-spacing: -0.02em;
    }
    
    h1 {
        background: linear-gradient(90deg, #60a5fa 0%, #a78bfa 50%, #ec4899 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.5rem !important;
        margin-bottom: 0.5rem !important;
    }
    
    .metric-container {
        background: linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(139, 92, 246, 0.05) 100%);
        border: 1px solid rgba(59, 130, 246, 0.3);
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        transition: all 0.3s ease;
    }
    
    .metric-container:hover {
        transform: translateY(-4px);
        box-shadow: 0 12px 48px rgba(59, 130, 246, 0.2);
        border-color: rgba(59, 130, 246, 0.5);
    }
    
    .status-badge {
        display: inline-block;
        padding: 6px 16px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.5px;
        text-transform: uppercase;
    }
    
    .status-live {
        background: rgba(16, 185, 129, 0.15);
        color: #10b981;
        border: 2px solid rgba(16, 185, 129, 0.4);
        animation: pulse 2s infinite;
    }
    
    .status-loading {
        background: rgba(245, 158, 11, 0.15);
        color: #f59e0b;
        border: 2px solid rgba(245, 158, 11, 0.4);
    }
    
    .status-error {
        background: rgba(239, 68, 68, 0.15);
        color: #ef4444;
        border: 2px solid rgba(239, 68, 68, 0.4);
    }
    
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.6; }
    }
    
    .info-card {
        background: rgba(15, 23, 42, 0.6);
        border: 1px solid rgba(59, 130, 246, 0.2);
        border-radius: 12px;
        padding: 16px;
        margin: 8px 0;
    }
    
    .price-change-positive {
        color: #10b981;
        font-weight: 600;
    }
    
    .price-change-negative {
        color: #ef4444;
        font-weight: 600;
    }
    
    div[data-testid="stMetricValue"] {
        font-size: 2rem;
        font-weight: 700;
    }
    
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: rgba(15, 23, 42, 0.4);
        padding: 8px;
        border-radius: 12px;
    }
    
    .stTabs [data-baseweb="tab"] {
        background: rgba(59, 130, 246, 0.1);
        border-radius: 8px;
        padding: 12px 24px;
        border: 1px solid rgba(59, 130, 246, 0.2);
        font-weight: 600;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, rgba(59, 130, 246, 0.3), rgba(139, 92, 246, 0.2));
        border-color: #3b82f6;
    }
</style>
""", unsafe_allow_html=True)

# Helper Functions
@st.cache_data(ttl=0)  # NO CACHING for real-time data!
def fetch_data(endpoint, params=None):
    """Fetch data from API without caching for real-time updates"""
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
        st.error(f"API Error: {str(e)}")
        return None

def calculate_statistics(df, time_range_hours=24):
    """Calculate comprehensive statistics based on selected time range"""
    if df.empty:
        return {}
    
    current_price = df.iloc[-1]['price']
    
    # Calculate stats based on available data
    price_start = df.iloc[0]['price']
    change_total = ((current_price - price_start) / price_start) * 100
    high_total = df['price'].max()
    low_total = df['price'].min()
    volume_total = df['volume'].sum()
    
    # 24H stats (if we have enough data)
    if time_range_hours >= 24 and len(df) > 288:
        df_24h = df.tail(288)  # ~24 hours of 5-min data
        price_24h_ago = df_24h.iloc[0]['price']
        change_24h = ((current_price - price_24h_ago) / price_24h_ago) * 100
        high_24h = df_24h['price'].max()
        low_24h = df_24h['price'].min()
        volume_24h = df_24h['volume'].sum()
    else:
        # Use all available data
        change_24h = change_total
        high_24h = high_total
        low_24h = low_total
        volume_24h = volume_total
    
    # Volatility
    volatility = df['price'].pct_change().std() * 100
    
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
        'total_volume': df['volume'].sum(),
        'time_range_hours': time_range_hours
    }

# Initialize session state
if 'initialized' not in st.session_state:
    st.session_state.initialized = False
    st.session_state.last_refresh = 0
    st.session_state.refresh_count = 0
    st.session_state.selected_symbol = "BTCUSDT"  # Default symbol
    st.session_state.selected_time_range = "24H"   # Default time range

# Auto-refresh logic - only if no user interaction in last 2 seconds
current_time = time.time()
user_interaction_timeout = 2  # Reduced to 2 seconds for faster response

# Check if should auto-refresh
should_auto_refresh = (
    current_time - st.session_state.last_refresh > REFRESH_INTERVAL and
    current_time - st.session_state.get('last_interaction', 0) > user_interaction_timeout
)

if should_auto_refresh:
    st.session_state.last_refresh = current_time
    st.session_state.refresh_count += 1
    st.rerun()

# Header
col_title, col_status = st.columns([3, 1])

with col_title:
    st.title("📈 Crypto Analytics Dashboard")
    st.markdown("Real-time monitoring with 7-day historical analysis")

with col_status:
    health = fetch_data("/health")
    if health:
        st.markdown('<span class="status-badge status-live">● LIVE</span>', unsafe_allow_html=True)
        st.caption(f"🔄 Refreshed {st.session_state.refresh_count} times")
    else:
        st.markdown('<span class="status-badge status-error">● OFFLINE</span>', unsafe_allow_html=True)

st.divider()

# Sidebar
st.sidebar.header("⚙️ Configuration")

# Symbol selector with session state persistence
selected_symbol = st.sidebar.selectbox(
    "Cryptocurrency",
    ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT"],
    index=["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT"].index(st.session_state.selected_symbol),
    key="symbol_selector",
    help="Select cryptocurrency pair to monitor"
)

# Time range selector with session state persistence
time_range = st.sidebar.select_slider(
    "Time Range",
    options=["1H", "6H", "12H", "24H", "7D"],
    value=st.session_state.selected_time_range,
    key="time_range_selector"
)

# Update session state if user changed selections
if selected_symbol != st.session_state.selected_symbol:
    st.session_state.selected_symbol = selected_symbol
    st.session_state.last_interaction = time.time()

if time_range != st.session_state.selected_time_range:
    st.session_state.selected_time_range = time_range
    st.session_state.last_interaction = time.time()

# Convert time range to hours
time_range_hours = {
    "1H": 1,
    "6H": 6,
    "12H": 12,
    "24H": 24,
    "7D": 168
}.get(st.session_state.selected_time_range, 24)

st.sidebar.divider()

# Time remaining until next refresh
time_since_refresh = int(current_time - st.session_state.last_refresh)
remaining = REFRESH_INTERVAL - time_since_refresh
st.sidebar.metric("⏱️ Next Refresh", f"{remaining}s")

# System status
st.sidebar.subheader("📊 System Status")
if health:
    metrics = health.get('pipeline_metrics', {})
    st.sidebar.success("✅ API Connected")
    st.sidebar.metric("Records", f"{metrics.get('records_processed', 0):,}")
    st.sidebar.metric("Anomalies", metrics.get('anomalies_detected', 0))
else:
    st.sidebar.error("❌ API Disconnected")
    st.sidebar.caption(f"Check: {API_BASE_URL}")

# Main Content - Fetch data based on selected symbol and time range
# CRITICAL: Always use session state symbol for consistent data fetching
current_symbol = st.session_state.selected_symbol
current_time_range = st.session_state.selected_time_range

fetch_start = time.time()
with st.spinner(f"Loading {current_symbol} data ({current_time_range})..."):
    price_data = fetch_data(f"/prices/{current_symbol}", {"hours": time_range_hours})
fetch_duration = time.time() - fetch_start

# Debug info in sidebar with real-time status
st.sidebar.divider()
st.sidebar.caption(f"⏱️ API fetch: {fetch_duration:.3f}s")
st.sidebar.caption(f"⚡ Refresh: every {REFRESH_INTERVAL}s")
if price_data:
    st.sidebar.caption(f"📊 Data points: {len(price_data)}")
    st.sidebar.success("✅ Real-time data")
else:
    st.sidebar.error("⚠️ No data from API")

if price_data and len(price_data) > 0:
    df = pd.DataFrame(price_data)
    
    # Handle timestamp parsing
    # After database reset, timestamps are stored as UTC
    # API returns UTC, dashboard converts to WIB for display
    try:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        # Convert UTC to WIB (add 7 hours)
        df['timestamp'] = df['timestamp'] + pd.Timedelta(hours=7)
    except Exception as e:
        st.error(f"Timestamp error: {e}")
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    df = df.sort_values('timestamp')
    
    # Calculate statistics with time range
    stats = calculate_statistics(df, time_range_hours)
    
    # Top Metrics Row - Use current_symbol for consistency
    st.subheader(f"💰 {current_symbol} Overview ({current_time_range}) - Live")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric(
            "Current Price",
            f"${stats['current_price']:,.2f}",
            f"{stats['change_24h']:+.2f}% (24H)"
        )
    
    with col2:
        st.metric(
            "24H High",
            f"${stats['high_24h']:,.2f}",
            f"Low: ${stats['low_24h']:,.2f}"
        )
    
    with col3:
        st.metric(
            f"{st.session_state.selected_time_range} Change",
            f"{stats['change_total']:+.2f}%",
            f"High: ${stats['high_total']:,.2f}"
        )
    
    with col4:
        st.metric(
            "24H Volume",
            f"{stats['volume_24h']:,.0f}",
            "Trading Volume"
        )
    
    with col5:
        st.metric(
            "Volatility",
            f"{stats['volatility']:.2f}%",
            "Price Std Dev"
        )
    
    st.divider()
    
    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Price Chart", "🕯️ Candlestick", "📰 News & Anomalies", "📈 Analytics"])
    
    # Tab 1: Price Chart
    with tab1:
        col_chart, col_info = st.columns([3, 1])
        
        with col_chart:
            st.subheader(f"Price History ({current_time_range}) - Live Updates")
            
            # Create subplots
            fig = make_subplots(
                rows=2, cols=1,
                shared_xaxes=True,
                vertical_spacing=0.03,
                row_heights=[0.7, 0.3],
                subplot_titles=(f'{current_symbol} Price (USD)', 'Volume')
            )
            
            # Price line with gradient fill
            fig.add_trace(
                go.Scatter(
                    x=df['timestamp'],
                    y=df['price'],
                    mode='lines',
                    name='Price',
                    line=dict(color='#3b82f6', width=2.5),
                    fill='tozeroy',
                    fillcolor='rgba(59, 130, 246, 0.1)',
                    hovertemplate='<b>%{y:,.2f} USD</b><br>%{x}<extra></extra>'
                ),
                row=1, col=1
            )
            
            # Moving averages
            df['ma_24h'] = df['price'].rolling(window=288).mean()
            df['ma_7d'] = df['price'].rolling(window=2016).mean()
            
            fig.add_trace(
                go.Scatter(
                    x=df['timestamp'],
                    y=df['ma_24h'],
                    mode='lines',
                    name='MA 24H',
                    line=dict(color='#f59e0b', width=1.5, dash='dash'),
                    hovertemplate='<b>MA 24H: %{y:,.2f}</b><extra></extra>'
                ),
                row=1, col=1
            )
            
            # Volume bars
            colors = ['#10b981' if df.iloc[i]['price'] >= df.iloc[i-1]['price'] else '#ef4444' 
                     for i in range(1, len(df))]
            colors.insert(0, '#3b82f6')
            
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
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                )
            )
            
            fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(59, 130, 246, 0.1)')
            fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(59, 130, 246, 0.1)')
            
            st.plotly_chart(fig, use_container_width=True)
        
        with col_info:
            st.subheader("📊 Quick Stats")
            
            st.markdown(f"""
            <div class="info-card">
                <h4>Price Range</h4>
                <p><b>24H:</b> ${stats['low_24h']:,.2f} - ${stats['high_24h']:,.2f}</p>
                <p><b>{current_time_range}:</b> ${stats['low_total']:,.2f} - ${stats['high_total']:,.2f}</p>
            </div>
            
            <div class="info-card">
                <h4>Performance</h4>
                <p class="{'price-change-positive' if stats['change_24h'] >= 0 else 'price-change-negative'}">
                    <b>24H:</b> {stats['change_24h']:+.2f}%
                </p>
                <p class="{'price-change-positive' if stats['change_total'] >= 0 else 'price-change-negative'}">
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
            
            # Last update
            st.caption(f"📅 Last update: {df.iloc[-1]['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
            st.caption(f"📊 Data points: {len(df):,}")
    
    # Tab 2: Candlestick
    with tab2:
        st.subheader("🕯️ Candlestick Chart")
        
        kline_data = fetch_data(f"/klines/{current_symbol}", {"limit": 168})
        
        if kline_data and len(kline_data) > 0:
            df_kline = pd.DataFrame(kline_data)
            
            # Handle timestamp parsing
            # After database reset, timestamps are UTC, convert to WIB
            try:
                df_kline['close_time'] = pd.to_datetime(df_kline['close_time'])
                # Convert UTC to WIB (add 7 hours)
                df_kline['close_time'] = df_kline['close_time'] + pd.Timedelta(hours=7)
            except Exception as e:
                st.error(f"Candlestick timestamp error: {e}")
                df_kline['close_time'] = pd.to_datetime(df_kline['close_time'])
            
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
            st.info("No candlestick data available. Run Binance ingestion first.")
    
    # Tab 3: News & Anomalies
    with tab3:
        col_news, col_anomaly = st.columns(2)
        
        with col_news:
            st.subheader("📰 Latest News")
            news = fetch_data("/news", {"limit": 10})
            
            if news and len(news) > 0:
                for article in news[:8]:
                    sentiment = article.get('sentiment_label', 'neutral')
                    score = article.get('sentiment_score', 0) or 0
                    url = article.get('url', '#')
                    
                    badge_color = '#10b981' if sentiment == 'positive' else '#ef4444' if sentiment == 'negative' else '#6b7280'
                    badge_icon = '🟢' if sentiment == 'positive' else '🔴' if sentiment == 'negative' else '⚪'
                    
                    st.markdown(f"""
                    <div class="info-card" style="cursor: pointer;">
                        {badge_icon} <b>{article['title']}</b><br>
                        <small style="color: {badge_color};">{article['source']} • {sentiment.upper()} ({score:+.2f})</small><br>
                        <small style="color: #6b7280;">🔗 <a href="{url}" target="_blank" style="color: #3b82f6; text-decoration: none;">Read article →</a></small>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("No news available. Run `python ingestion/rss_batch.py`")
        
        with col_anomaly:
            st.subheader("🚨 Anomaly Alerts")
            anomalies = fetch_data("/anomalies", {"hours": 24})
            
            if anomalies and len(anomalies) > 0:
                for anomaly in anomalies[:8]:
                    severity = anomaly.get('severity', 'medium')
                    icon = '🔴' if severity == 'high' else '🟡' if severity == 'medium' else '🟢'
                    
                    st.markdown(f"""
                    <div class="info-card">
                        {icon} <b>{anomaly['event_type'].replace('_', ' ').title()}</b><br>
                        <small>{anomaly.get('symbol', 'N/A')} • {anomaly['description']}</small>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.success("✅ No anomalies detected in the last 24 hours")
    
    # Tab 4: Analytics
    with tab4:
        st.subheader("📈 Advanced Analytics")
        
        col_a1, col_a2 = st.columns(2)
        
        with col_a1:
            # Price distribution
            fig_dist = go.Figure(data=[go.Histogram(
                x=df['price'],
                nbinsx=50,
                marker_color='#3b82f6',
                opacity=0.7,
                name='Price Distribution'
            )])
            
            fig_dist.update_layout(
                title="Price Distribution",
                height=300,
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(15,15,26,0.8)",
                xaxis_title="Price (USD)",
                yaxis_title="Frequency"
            )
            
            st.plotly_chart(fig_dist, use_container_width=True)
        
        with col_a2:
            # Volume trend (fixed: use lowercase 'h')
            df_hourly = df.set_index('timestamp').resample('1h').agg({
                'volume': 'sum'
            }).reset_index()
            
            fig_vol_trend = go.Figure(data=[go.Bar(
                x=df_hourly['timestamp'],
                y=df_hourly['volume'],
                marker_color='#a78bfa',
                name='Hourly Volume'
            )])
            
            fig_vol_trend.update_layout(
                title="Hourly Volume Trend",
                height=300,
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(15,15,26,0.8)",
                xaxis_title="Time",
                yaxis_title="Volume"
            )
            
            st.plotly_chart(fig_vol_trend, use_container_width=True)
        
        # Price Movement Chart (Pergerakan Harga)
        st.subheader("📈 Price Movement Analysis")
        
        # Calculate price changes
        df_movement = df.copy()
        df_movement['price_change'] = df_movement['price'].diff()
        df_movement['price_change_pct'] = df_movement['price'].pct_change() * 100
        df_movement['color'] = df_movement['price_change'].apply(
            lambda x: '#10b981' if x >= 0 else '#ef4444'
        )
        
        # Resample to hourly for clearer view
        df_hourly_movement = df_movement.set_index('timestamp').resample('1h').agg({
            'price': 'last',
            'price_change': 'sum',
            'price_change_pct': 'sum'
        }).reset_index()
        df_hourly_movement['color'] = df_hourly_movement['price_change'].apply(
            lambda x: '#10b981' if x >= 0 else '#ef4444'
        )
        
        # Create movement chart
        fig_movement = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            row_heights=[0.6, 0.4],
            subplot_titles=('Price Trend', 'Hourly Price Change (%)')
        )
        
        # Price line
        fig_movement.add_trace(
            go.Scatter(
                x=df_hourly_movement['timestamp'],
                y=df_hourly_movement['price'],
                mode='lines+markers',
                name='Price',
                line=dict(color='#60a5fa', width=3),
                marker=dict(size=6, color='#60a5fa'),
                hovertemplate='<b>$%{y:,.2f}</b><br>%{x}<extra></extra>'
            ),
            row=1, col=1
        )
        
        # Price change bars
        fig_movement.add_trace(
            go.Bar(
                x=df_hourly_movement['timestamp'],
                y=df_hourly_movement['price_change_pct'],
                name='Change %',
                marker_color=df_hourly_movement['color'],
                hovertemplate='<b>%{y:+.2f}%</b><br>%{x}<extra></extra>'
            ),
            row=2, col=1
        )
        
        # Add zero line for reference
        fig_movement.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5, row=2, col=1)
        
        fig_movement.update_layout(
            height=600,
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(15,15,26,0.8)",
            showlegend=False,
            hovermode='x unified'
        )
        
        fig_movement.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(59, 130, 246, 0.1)')
        fig_movement.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(59, 130, 246, 0.1)')
        fig_movement.update_yaxes(title_text="Price (USD)", row=1, col=1)
        fig_movement.update_yaxes(title_text="Change (%)", row=2, col=1)
        
        st.plotly_chart(fig_movement, use_container_width=True)
        
        # Movement statistics
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        
        positive_moves = len(df_hourly_movement[df_hourly_movement['price_change'] > 0])
        negative_moves = len(df_hourly_movement[df_hourly_movement['price_change'] < 0])
        avg_positive = df_hourly_movement[df_hourly_movement['price_change'] > 0]['price_change_pct'].mean()
        avg_negative = df_hourly_movement[df_hourly_movement['price_change'] < 0]['price_change_pct'].mean()
        
        with col_m1:
            st.metric("📈 Positive Hours", f"{positive_moves}", f"{positive_moves/(positive_moves+negative_moves)*100:.1f}%")
        
        with col_m2:
            st.metric("📉 Negative Hours", f"{negative_moves}", f"{negative_moves/(positive_moves+negative_moves)*100:.1f}%")
        
        with col_m3:
            st.metric("🟢 Avg Gain", f"+{avg_positive:.2f}%" if not pd.isna(avg_positive) else "0%")
        
        with col_m4:
            st.metric("🔴 Avg Loss", f"{avg_negative:.2f}%" if not pd.isna(avg_negative) else "0%")

else:
    st.error("⚠️ No data available")
    st.info("""
    **To get started:**
    1. Make sure Docker services are running: `docker compose up -d`
    2. Start price ingestion: `python ingestion/binance_websocket.py`
    3. Wait a few minutes for data to accumulate
    4. Refresh this dashboard
    """)

# Footer
st.divider()
col_f1, col_f2, col_f3, col_f4 = st.columns(4)

with col_f1:
    if len(df) > 0:
        # Timestamp from dataframe (already WIB from API conversion)
        last_data_wib = df.iloc[-1]['timestamp']
        st.caption(f"📊 Last Data: {last_data_wib.strftime('%Y-%m-%d %H:%M:%S')} WIB")
    else:
        st.caption("📊 Last Data: No data")

with col_f2:
    # Current WIB time
    current_wib = now_wib()
    st.caption(f"� Dashboard: {current_wib.strftime('%Y-%m-%d %H:%M:%S')} WIB")

with col_f3:
    st.caption(f"� Auto-refresh: every {REFRESH_INTERVAL}s")

with col_f4:
    st.caption(f"📈 Total Refreshes: {st.session_state.refresh_count}")

