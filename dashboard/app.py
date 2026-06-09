"""
🚀 PERFECT REAL-TIME CRYPTO ANALYTICS DASHBOARD

Features:
- ⚡ Smooth auto-refresh (NO page reload, NO black flash)
- 🔄 Uses st.fragment for partial updates only
- 🕐 WIB timezone throughout
- 📊 Comprehensive metrics and analytics
- 🎨 Beautiful dark glassmorphism UI
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
import sys

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.abspath('.'))
from monitoring.timezone_utils import now_wib

# ==================== CONFIGURATION ====================
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8001")
API_KEY = os.getenv("API_KEY", "dev-api-key")
HEADERS = {"X-API-Key": API_KEY}
REFRESH_SECONDS = 2

SYMBOLS = {
    "BTCUSDT": {"name": "Bitcoin", "emoji": "₿", "color": "#F7931A"},
}
SELECTED_SYMBOL = "BTCUSDT"
TIME_RANGE_HOURS = 24

# ==================== PAGE CONFIG (runs once) ====================
st.set_page_config(
    page_title="₿ Bitcoin Real-time Analytics",
    page_icon="₿",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ==================== CSS (static, never re-renders) ====================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    * { font-family: 'Inter', sans-serif; }

    .stApp {
        background: radial-gradient(circle at top right, #1a1a2e 0%, #0a0a15 60%, #05050f 100%) !important;
    }

    /* Hide ALL Streamlit chrome */
    #MainMenu, footer, header,
    div[data-testid="stStatusWidget"],
    .stDeployButton,
    section[data-testid="stSidebar"],
    button[kind="header"] {
        display: none !important;
    }

    .main .block-container {
        max-width: 100% !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
    }

    h1 {
        background: linear-gradient(90deg, #38bdf8 0%, #818cf8 50%, #e879f9 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.8rem !important;
        font-weight: 800 !important;
        margin-bottom: 0.5rem !important;
        letter-spacing: -0.03em;
    }

    div[data-testid="stMetric"] {
        background: rgba(15, 23, 42, 0.45);
        border: 1px solid rgba(56, 189, 248, 0.2);
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-6px);
        box-shadow: 0 16px 48px rgba(56, 189, 248, 0.25);
        border-color: rgba(56, 189, 248, 0.5);
        background: rgba(15, 23, 42, 0.65);
    }
    div[data-testid="stMetricValue"] {
        font-size: 2.4rem;
        font-weight: 800;
        letter-spacing: -0.02em;
    }

    .status-badge {
        display: inline-block;
        padding: 8px 20px;
        border-radius: 24px;
        font-size: 0.85rem;
        font-weight: 800;
        letter-spacing: 0.5px;
        text-transform: uppercase;
        backdrop-filter: blur(10px);
    }
    .status-live {
        background: rgba(16, 185, 129, 0.15);
        color: #34d399;
        border: 2px solid rgba(16, 185, 129, 0.6);
        box-shadow: 0 0 20px rgba(16, 185, 129, 0.2);
        animation: pulse-border 2s infinite;
    }
    @keyframes pulse-border {
        0%, 100% { border-color: rgba(16, 185, 129, 0.4); }
        50% { border-color: rgba(16, 185, 129, 1); box-shadow: 0 0 25px rgba(16, 185, 129, 0.4); }
    }

    .info-card {
        background: rgba(15, 23, 42, 0.4);
        border: 1px solid rgba(148, 163, 184, 0.15);
        border-radius: 16px;
        padding: 20px;
        margin: 10px 0;
        backdrop-filter: blur(12px);
        box-shadow: 0 4px 20px rgba(0,0,0,0.2);
        transition: all 0.3s ease;
    }
    .info-card:hover {
        border-color: rgba(56, 189, 248, 0.3);
        transform: scale(1.02);
    }

    .news-card {
        background: rgba(30, 41, 59, 0.5);
        border-left: 4px solid #3b82f6;
        border-radius: 12px;
        padding: 16px 20px;
        margin: 12px 0;
        backdrop-filter: blur(10px);
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    .news-card:hover {
        background: rgba(30, 41, 59, 0.8);
        border-left-color: #60a5fa;
        transform: translateX(6px);
    }

    .price-up { color: #34d399; font-weight: 600; }
    .price-down { color: #f87171; font-weight: 600; }

    .stTabs [data-baseweb="tab-list"] {
        gap: 12px;
        background: rgba(15, 23, 42, 0.4);
        padding: 10px;
        border-radius: 16px;
        backdrop-filter: blur(10px);
    }
    .stTabs [data-baseweb="tab"] {
        background: rgba(56, 189, 248, 0.05);
        border-radius: 10px;
        padding: 14px 28px;
        border: 1px solid rgba(56, 189, 248, 0.1);
        font-weight: 600;
        color: #cbd5e1;
        transition: all 0.3s ease;
    }
    .stTabs [data-baseweb="tab"]:hover {
        background: rgba(56, 189, 248, 0.15);
        border-color: rgba(56, 189, 248, 0.3);
        color: #fff;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, rgba(56, 189, 248, 0.3), rgba(129, 140, 248, 0.25));
        border-color: #38bdf8;
        color: #fff;
        box-shadow: 0 4px 15px rgba(56, 189, 248, 0.25);
    }
</style>
""", unsafe_allow_html=True)

# ==================== STATIC HEADER (never re-renders) ====================
st.title("₿ Bitcoin Real-time Analytics")
st.markdown("**Live monitoring** | 24H Data | WIB Timezone | Smooth Auto-refresh")

# ==================== HELPER FUNCTIONS ====================

def fetch_api(endpoint, params=None):
    """Fetch data from API"""
    try:
        resp = requests.get(
            f"{API_BASE_URL}{endpoint}",
            headers=HEADERS,
            params=params,
            timeout=10
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def calculate_stats(df):
    """Calculate comprehensive statistics"""
    if df.empty:
        return {}

    current_price = df.iloc[-1]['price']
    price_start = df.iloc[0]['price']

    change_total = ((current_price - price_start) / price_start) * 100
    high_total = df['price'].max()
    low_total = df['price'].min()
    volume_total = df['volume'].sum() if 'volume' in df.columns else 0

    if len(df) > 288:
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
        'data_points': len(df),
    }


# ==================== SESSION STATE ====================
if 'refresh_count' not in st.session_state:
    st.session_state.refresh_count = 0


# ══════════════════════════════════════════════════════════
#  FRAGMENT: Only this part re-runs every N seconds.
#  The rest of the page (CSS, title) stays untouched
#  → NO black flash, NO full-page reload.
# ══════════════════════════════════════════════════════════

@st.fragment(run_every=REFRESH_SECONDS)
def live_data():
    st.session_state.refresh_count += 1
    symbol_info = SYMBOLS[SELECTED_SYMBOL]

    # --- status row ---
    scol1, scol2 = st.columns([5, 1])
    with scol1:
        st.divider()
    with scol2:
        health = fetch_api("/health")
        if health:
            st.markdown('<div class="status-badge status-live">● LIVE</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="status-badge" style="background:rgba(239,68,68,0.2);color:#ef4444;border:2px solid #ef4444;">● OFFLINE</div>', unsafe_allow_html=True)

    # --- fetch price data ---
    price_data = fetch_api(f"/prices/{SELECTED_SYMBOL}", {"hours": TIME_RANGE_HOURS})

    if not price_data or len(price_data) == 0:
        st.error("⚠️ No data available")
        st.info("Start WebSocket ingestion: `python ingestion/binance_websocket.py`")
        return

    df = pd.DataFrame(price_data)
    try:
        df['timestamp'] = pd.to_datetime(df['timestamp']) + pd.Timedelta(hours=7)
    except Exception as e:
        st.error(f"Timestamp error: {e}")
        return

    df = df.sort_values('timestamp')
    stats = calculate_stats(df)

    # ==================== OVERVIEW METRICS ====================
    st.subheader(f"{symbol_info['emoji']} {symbol_info['name']} Overview — 24 Hours — LIVE")

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("💰 Current Price", f"${stats['current_price']:,.2f}",
                   f"{stats['change_24h']:+.2f}% (24H)", delta_color="normal")
    with c2:
        st.metric("📈 24H High", f"${stats['high_24h']:,.2f}",
                   f"Low: ${stats['low_24h']:,.2f}")
    with c3:
        st.metric("📊 24H Change", f"{stats['change_total']:+.2f}%",
                   f"High: ${stats['high_total']:,.2f}", delta_color="normal")
    with c4:
        st.metric("💹 24H Volume", f"{stats['volume_24h']:,.0f}", "Trading Activity")
    with c5:
        st.metric("⚡ Volatility", f"{stats['volatility']:.2f}%", "Price Std Dev")

    st.divider()

    # ==================== TABS ====================
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Live Chart", "🕯️ Candlestick", "📰 News & Alerts", "📈 Analytics"
    ])

    # --- TAB 1: Live Price Chart ---
    with tab1:
        col_chart, col_info = st.columns([3, 1])

        with col_chart:
            st.subheader(f"💹 {symbol_info['name']} Price — 24H Real-time")

            fig = make_subplots(
                rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03,
                row_heights=[0.7, 0.3],
                subplot_titles=(f'{SELECTED_SYMBOL} Price (USD)', 'Volume')
            )

            fig.add_trace(go.Scatter(
                x=df['timestamp'], y=df['price'], mode='lines', name='Price',
                line=dict(color=symbol_info['color'], width=3),
                fill='tozeroy',
                fillcolor=f"rgba{tuple(list(int(symbol_info['color'][i:i+2], 16) for i in (1,3,5))+[0.1])}",
                hovertemplate='<b>$%{y:,.2f}</b><br>%{x}<extra></extra>'
            ), row=1, col=1)

            if len(df) > 20:
                df['ma'] = df['price'].rolling(window=20).mean()
                fig.add_trace(go.Scatter(
                    x=df['timestamp'], y=df['ma'], mode='lines', name='MA 20',
                    line=dict(color='#f59e0b', width=2, dash='dash'),
                    hovertemplate='<b>MA: $%{y:,.2f}</b><extra></extra>'
                ), row=1, col=1)

            bar_colors = [
                '#10b981' if i > 0 and df.iloc[i]['price'] >= df.iloc[i-1]['price'] else '#ef4444'
                for i in range(len(df))
            ]
            fig.add_trace(go.Bar(
                x=df['timestamp'], y=df['volume'], name='Volume',
                marker_color=bar_colors, opacity=0.6,
                hovertemplate='<b>%{y:,.0f}</b><extra></extra>'
            ), row=2, col=1)

            fig.update_layout(
                height=600, template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(15,15,26,0.8)",
                hovermode='x unified', showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(59,130,246,0.1)')
            fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(59,130,246,0.1)')

            st.plotly_chart(fig, use_container_width=True)

        with col_info:
            st.subheader("📊 Quick Stats")
            st.markdown(f"""
            <div class="info-card">
                <h4 style="color:{symbol_info['color']};">Price Range</h4>
                <p><b>24H:</b> ${stats['low_24h']:,.2f} – ${stats['high_24h']:,.2f}</p>
                <p><b>Total:</b> ${stats['low_total']:,.2f} – ${stats['high_total']:,.2f}</p>
            </div>
            <div class="info-card">
                <h4>Performance</h4>
                <p class="{'price-up' if stats['change_24h']>=0 else 'price-down'}">
                    <b>24H:</b> {stats['change_24h']:+.2f}%</p>
                <p class="{'price-up' if stats['change_total']>=0 else 'price-down'}">
                    <b>Total:</b> {stats['change_total']:+.2f}%</p>
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

    # --- TAB 2: Candlestick ---
    with tab2:
        st.subheader("🕯️ Candlestick Chart — 24 Hours")
        kline_data = fetch_api(f"/klines/{SELECTED_SYMBOL}", {"limit": 168})

        if kline_data and len(kline_data) > 0:
            df_k = pd.DataFrame(kline_data)
            try:
                df_k['open_time'] = pd.to_datetime(df_k['open_time']) + pd.Timedelta(hours=7)
                df_k['close_time'] = pd.to_datetime(df_k['close_time']) + pd.Timedelta(hours=7)
            except Exception as e:
                st.error(f"Timestamp error: {e}")

            df_k = df_k.sort_values('close_time')

            fig_c = go.Figure(data=[go.Candlestick(
                x=df_k['close_time'],
                open=df_k['open'], high=df_k['high'],
                low=df_k['low'], close=df_k['close'],
                increasing_line_color='#10b981', decreasing_line_color='#ef4444',
                increasing_fillcolor='#10b981', decreasing_fillcolor='#ef4444',
            )])
            fig_c.update_layout(
                height=500, template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(15,15,26,0.8)",
                xaxis_rangeslider_visible=False, hovermode='x'
            )
            st.plotly_chart(fig_c, use_container_width=True)
        else:
            st.info("💡 No candlestick data. Start WebSocket ingestion first.")

    # --- TAB 3: News & Alerts ---
    with tab3:
        col_news, col_anom = st.columns(2)

        with col_news:
            st.subheader("📰 Latest Crypto News")
            news = fetch_api("/news", {"limit": 10})
            if news and len(news) > 0:
                for art in news[:8]:
                    sent = art.get('sentiment_label', 'neutral')
                    score = art.get('sentiment_score', 0) or 0
                    url = art.get('url', '#')
                    emo = '🟢' if sent == 'positive' else '🔴' if sent == 'negative' else '⚪'
                    clr = '#10b981' if sent == 'positive' else '#ef4444' if sent == 'negative' else '#6b7280'
                    st.markdown(f"""
                    <div class="news-card">
                        {emo} <b>{art['title']}</b><br>
                        <small style="color:{clr};">{art['source']} • {sent.upper()} ({score:+.2f})</small><br>
                        <small><a href="{url}" target="_blank" style="color:#3b82f6;text-decoration:none;">🔗 Read →</a></small>
                    </div>""", unsafe_allow_html=True)
            else:
                st.info("💡 No news. Run: `python ingestion/rss_batch.py`")

        with col_anom:
            st.subheader("🚨 Anomaly Alerts")
            anomalies = fetch_api("/anomalies", {"hours": 24})
            if anomalies and len(anomalies) > 0:
                for a in anomalies[:8]:
                    sev = a.get('severity', 'medium')
                    emo = '🔴' if sev == 'high' else '🟡' if sev == 'medium' else '🟢'
                    st.markdown(f"""
                    <div class="info-card">
                        {emo} <b>{a['event_type'].replace('_',' ').title()}</b><br>
                        <small>{a.get('symbol','N/A')} • {a['description']}</small>
                    </div>""", unsafe_allow_html=True)
            else:
                st.success("✅ No anomalies in last 24 hours")

    # --- TAB 4: Analytics ---
    with tab4:
        st.subheader("📈 Advanced Analytics")
        ca1, ca2 = st.columns(2)

        with ca1:
            fig_d = go.Figure(data=[go.Histogram(
                x=df['price'], nbinsx=50,
                marker_color=symbol_info['color'], opacity=0.7, name='Price Distribution'
            )])
            fig_d.update_layout(
                title="Price Distribution", height=300, template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(15,15,26,0.8)")
            st.plotly_chart(fig_d, use_container_width=True)

        with ca2:
            df_h = df.set_index('timestamp').resample('1h').agg({'volume': 'sum'}).reset_index()
            fig_v = go.Figure(data=[go.Bar(
                x=df_h['timestamp'], y=df_h['volume'],
                marker_color='#a78bfa', name='Hourly Volume'
            )])
            fig_v.update_layout(
                title="Hourly Volume Trend", height=300, template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(15,15,26,0.8)")
            st.plotly_chart(fig_v, use_container_width=True)

    # --- Footer ---
    st.divider()
    f1, f2, f3, f4 = st.columns(4)
    with f1:
        st.caption(f"📊 Last Data: {df.iloc[-1]['timestamp'].strftime('%Y-%m-%d %H:%M:%S')} WIB")
    with f2:
        st.caption(f"🕐 Dashboard: {now_wib().strftime('%Y-%m-%d %H:%M:%S')} WIB")
    with f3:
        st.caption(f"🔄 Auto-refresh: {REFRESH_SECONDS}s")
    with f4:
        st.caption(f"📈 Refreshes: {st.session_state.refresh_count:,}")

    st.markdown("""
    <div style="text-align:center;opacity:0.5;margin-top:20px;font-size:0.8rem;">
        🚀 Perfect Real-time Crypto Analytics Dashboard | Powered by Streamlit
    </div>""", unsafe_allow_html=True)


# ==================== CALL THE FRAGMENT ====================
# Only the content inside live_data() re-renders every 2 seconds.
# The CSS, title, and page config above NEVER re-render → NO black flash.
live_data()
