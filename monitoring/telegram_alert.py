"""
Enhanced Telegram Bot alert system for crypto pipeline.

Features:
- Real-time anomaly alerts (price spikes, volume surges, sentiment crashes)
- Daily/hourly summaries with charts
- Pipeline health monitoring
- Price threshold alerts
- Interactive commands support (/predict, /status, /help)
- Auto-alerts for news sentiment (positive & negative)
- Trading signals (BUY/SELL/HOLD) with ML predictions
- Rate limiting & deduplication
- Rich HTML formatting
- Statistics tracking

Setup:
1. Create bot via @BotFather → get token
2. Get chat_id from @userinfobot
3. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env
4. Start bot listener: python monitoring/telegram_alert.py
"""
import os
import sys
import requests
import threading
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv
import html

# Add project root to path for direct execution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from monitoring.logger import get_logger
from monitoring.timezone_utils import now_wib, format_wib, format_wib_short

load_dotenv()
logger = get_logger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# Rate limiting: minimum seconds between identical alerts
_last_alert_times = {}
ALERT_COOLDOWN_SECONDS = 60

# Alert statistics with more detail
_alert_stats = {
    "total_sent": 0,
    "anomalies": 0,
    "price_spikes": 0,
    "news_alerts": 0,
    "errors": 0,
    "summaries": 0,
    "failed": 0,
    "last_alert_time": None,
}
_alert_count_date = datetime.utcnow().date()


def _is_configured() -> bool:
    """Check if Telegram credentials are configured."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    # Basic validation
    if len(TELEGRAM_BOT_TOKEN) < 40 or not TELEGRAM_CHAT_ID.lstrip('-').isdigit():
        logger.warning("telegram_invalid_credentials")
        return False
    return True


def _send_message(text: str, parse_mode: str = "HTML") -> bool:
    """
    Send a message to the configured Telegram chat.

    Parameters
    ----------
    text : str
        Message body (supports HTML formatting).
    parse_mode : str
        Telegram parse mode: 'HTML' or 'Markdown'.
    """
    if not _is_configured():
        logger.debug("telegram_not_configured_skipping_alert")
        return False

    try:
        response = requests.post(
            f"{TELEGRAM_API_URL}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        response.raise_for_status()
        result = response.json()

        if result.get("ok"):
            _increment_alert_count("total_sent")
            _alert_stats["last_alert_time"] = datetime.utcnow()
            logger.info("telegram_alert_sent", chat_id=TELEGRAM_CHAT_ID, message_id=result.get("result", {}).get("message_id"))
            return True
        else:
            _increment_alert_count("failed")
            logger.warning("telegram_api_error", response=result)
            return False

    except requests.exceptions.Timeout:
        _increment_alert_count("failed")
        logger.error("telegram_timeout", timeout=10)
        return False
    except requests.exceptions.RequestException as e:
        _increment_alert_count("failed")
        logger.error("telegram_network_error", error=str(e))
        return False
    except Exception as e:
        _increment_alert_count("failed")
        logger.error("telegram_send_failed", error=str(e))
        return False


def _send_async(text: str, parse_mode: str = "HTML"):
    """Fire-and-forget: send alert without blocking the pipeline."""
    thread = threading.Thread(target=_send_message, args=(text, parse_mode), daemon=True)
    thread.start()


def _should_send(alert_key: str) -> bool:
    """Rate-limit check: avoid spamming the same alert type."""
    now = datetime.utcnow().timestamp()
    last = _last_alert_times.get(alert_key, 0)
    if now - last < ALERT_COOLDOWN_SECONDS:
        return False
    _last_alert_times[alert_key] = now
    return True


def _increment_alert_count(counter_name: str = "total_sent"):
    """Track alert statistics."""
    global _alert_count_date
    today = datetime.utcnow().date()
    
    # Reset daily counters at midnight
    if today != _alert_count_date:
        logger.info("telegram_stats_reset", date=str(today))
        for key in _alert_stats:
            if key not in ["last_alert_time"]:
                _alert_stats[key] = 0
        _alert_count_date = today
    
    if counter_name in _alert_stats:
        _alert_stats[counter_name] += 1


def get_alert_stats() -> dict:
    """Return comprehensive alerting statistics."""
    return {
        **_alert_stats,
        "date": str(_alert_count_date),
        "configured": _is_configured(),
        "bot_token_set": bool(TELEGRAM_BOT_TOKEN),
        "chat_id_set": bool(TELEGRAM_CHAT_ID),
        "last_alert": str(_alert_stats["last_alert_time"]) if _alert_stats["last_alert_time"] else "Never",
    }


def _sanitize_error(msg: str, max_length: int = 300) -> str:
    """Sanitize error messages: truncate and remove sensitive info."""
    # Remove file paths that might leak system info
    sanitized = msg.replace("\\", "/")
    # Truncate
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length] + "..."
    return sanitized


# ──────────────────────────────────────────────────────────────────────
# High-level alert functions called by the pipeline
# ──────────────────────────────────────────────────────────────────────

def send_anomaly_alert(anomaly: dict):
    """
    Send an alert for a detected anomaly event.

    Parameters
    ----------
    anomaly : dict
        Must contain keys: event_type, description, severity.
        Optional: symbol, value, threshold.
    """
    event_type = anomaly.get("event_type", "unknown")
    symbol = anomaly.get("symbol", "N/A")
    alert_key = f"anomaly_{event_type}_{symbol}"

    if not _should_send(alert_key):
        return

    _increment_alert_count("anomalies")
    
    severity = anomaly.get("severity", "medium")
    severity_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(severity, "⚪")
    
    # Enhanced event type display
    event_display = {
        "price_spike": "💹 Price Spike",
        "stream_price_spike": "💹 Price Spike (Stream)",
        "volume_surge": "📊 Volume Surge",
        "stream_volume_surge": "📊 Volume Surge (Stream)",
        "sentiment_crash": "😱 Sentiment Crash",
        "stream_sentiment_crash": "😱 Sentiment Crash (Stream)",
        "volatility_spike": "⚡ High Volatility",
        "sudden_drop": "📉 Sudden Drop",
        "ml_anomaly": "🤖 ML Anomaly",
        "batch_ml_anomaly": "🤖 ML Anomaly (Batch)"
    }.get(event_type, event_type.replace("_", " ").title())

    text = (
        f"{severity_emoji} <b>ANOMALY DETECTED</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>Type:</b> {event_display}\n"
        f"💎 <b>Symbol:</b> {symbol}\n"
        f"📝 <b>Detail:</b> {html.escape(str(anomaly.get('description', '-')))}\n"
        f"📊 <b>Value:</b> {anomaly.get('value', '-')}\n"
        f"⚡ <b>Threshold:</b> {anomaly.get('threshold', '-')}\n"
        f"🔥 <b>Severity:</b> {severity.upper()}\n"
        f"🕐 <b>Time:</b> {format_wib(now_wib())}\n"
        f"\n💡 <i>Check dashboard for more details</i>"
    )

    _send_async(text)


def send_price_spike_alert(symbol: str, price_change_pct: float, current_price: float, previous_price: Optional[float] = None):
    """Alert for a significant price spike."""
    alert_key = f"price_spike_{symbol}"
    if not _should_send(alert_key):
        return

    _increment_alert_count("price_spikes")
    
    direction = "📈" if price_change_pct > 0 else "📉"
    trend_word = "SURGE" if price_change_pct > 0 else "DROP"
    
    prev_text = f"\n📌 <b>Previous:</b> ${previous_price:,.2f}" if previous_price else ""

    text = (
        f"{direction} <b>PRICE {trend_word}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💎 <b>Symbol:</b> {symbol}\n"
        f"💰 <b>Current:</b> ${current_price:,.2f}{prev_text}\n"
        f"📊 <b>Change:</b> {price_change_pct:+.2f}%\n"
        f"⏱️ <b>Window:</b> 5 minutes\n"
        f"🕐 <b>Time:</b> {format_wib(now_wib())}\n"
        f"\n💡 <i>{'🚀 To the moon!' if price_change_pct > 0 else '⚠️ Watch out!'}</i>"
    )

    _send_async(text)


def send_prediction_alert(symbol: str, current_price: float, predicted_price: float, signal: str, confidence: float):
    """Alert for ML price prediction and trading signal."""
    alert_key = f"prediction_{symbol}_{signal}"
    if not _should_send(alert_key):
        return

    _increment_alert_count("anomalies")

    signal_emoji = {
        'BUY': '🟢',
        'SELL': '🔴',
        'HOLD': '🟡'
    }.get(signal, '⚪')
    
    price_change_pct = ((predicted_price - current_price) / current_price) * 100
    
    text = (
        f"{signal_emoji} <b>LSTM PREDICTION SIGNAL</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💎 <b>Symbol:</b> {symbol}\n"
        f"📊 <b>Signal:</b> {signal}\n"
        f"🎯 <b>Confidence:</b> {confidence:.2%}\n"
        f"💰 <b>Current:</b> ${current_price:,.2f}\n"
        f"🔮 <b>Predicted:</b> ${predicted_price:,.2f} ({price_change_pct:+.2f}%)\n"
        f"🕐 <b>Time:</b> {format_wib(now_wib())}\n"
        f"\n💡 <i>Automated AI Trading Signal</i>"
    )

    _send_async(text)


def send_volume_alert(symbol: str, current_volume: float, avg_volume: float, surge_multiplier: float):
    """Alert for unusual volume activity."""
    alert_key = f"volume_{symbol}"
    if not _should_send(alert_key):
        return
    
    _increment_alert_count("anomalies")

    text = (
        f"📊 <b>VOLUME SURGE</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💎 <b>Symbol:</b> {symbol}\n"
        f"📈 <b>Current Vol:</b> {current_volume:,.0f}\n"
        f"📉 <b>Avg Vol:</b> {avg_volume:,.0f}\n"
        f"⚡ <b>Multiplier:</b> {surge_multiplier:.2f}x\n"
        f"🕐 <b>Time:</b> {format_wib(now_wib())}\n"
        f"\n💡 <i>High trading activity detected!</i>"
    )

    _send_async(text)


def send_news_sentiment_alert(source: str, sentiment_score: float, title: str):
    """Alert for significant news sentiment (very positive or very negative)."""
    alert_key = f"news_{source}_{int(abs(sentiment_score)*100)}"
    if not _should_send(alert_key):
        return
    
    _increment_alert_count("news_alerts")
    
    if sentiment_score > 0.5:
        emoji = "🟢"
        label = "POSITIVE NEWS"
    elif sentiment_score < -0.5:
        emoji = "🔴"
        label = "NEGATIVE NEWS"
    else:
        return  # Skip neutral news
    
    text = (
        f"{emoji} <b>{label}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📰 <b>Source:</b> {html.escape(source)}\n"
        f"📊 <b>Sentiment:</b> {sentiment_score:+.3f}\n"
        f"📝 <b>Headline:</b> {html.escape(title[:150])}\n"
        f"🕐 <b>Time:</b> {format_wib(now_wib())}\n"
        f"\n💡 <i>{'📈 Bullish signal!' if sentiment_score > 0 else '📉 Bearish signal!'}</i>"
    )
    
    _send_async(text)


def send_pipeline_error_alert(component: str, error_msg: str):
    """Alert for a critical pipeline failure."""
    alert_key = f"error_{component}"
    if not _should_send(alert_key):
        return

    _increment_alert_count("errors")
    
    safe_error = _sanitize_error(error_msg)

    text = (
        f"⛔ <b>PIPELINE ERROR</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔧 <b>Component:</b> {html.escape(component)}\n"
        f"❌ <b>Error:</b> <code>{html.escape(safe_error)}</code>\n"
        f"🕐 <b>Time:</b> {format_wib(now_wib())}\n"
        f"\n⚠️ <i>Action required! Check logs immediately.</i>"
    )

    _send_async(text)


def send_daily_summary(
    total_prices: int,
    total_news: int,
    total_anomalies: int,
    avg_sentiment: float,
    top_symbol: Optional[str] = None,
    top_symbol_change: Optional[float] = None,
):
    """Send a comprehensive daily pipeline health summary."""
    _increment_alert_count("summaries")
    
    sentiment_emoji = "🟢" if avg_sentiment > 0.05 else "🔴" if avg_sentiment < -0.05 else "⚪"
    sentiment_label = "Positive" if avg_sentiment > 0.05 else "Negative" if avg_sentiment < -0.05 else "Neutral"
    
    top_performer = ""
    if top_symbol and top_symbol_change is not None:
        perf_emoji = "📈" if top_symbol_change > 0 else "📉"
        top_performer = f"{perf_emoji} <b>Top Performer:</b> {top_symbol} ({top_symbol_change:+.2f}%)\n"

    text = (
        f"📊 <b>DAILY PIPELINE SUMMARY</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📅 <b>Date:</b> {now_wib().strftime('%Y-%m-%d')}\n"
        f"\n<b>📈 Data Collected</b>\n"
        f"💰 Price Records: {total_prices:,}\n"
        f"📰 News Articles: {total_news:,}\n"
        f"🚨 Anomalies: {total_anomalies}\n"
        f"\n<b>💭 Market Sentiment</b>\n"
        f"{sentiment_emoji} Overall: {sentiment_label} ({avg_sentiment:+.3f})\n"
        f"\n<b>🏆 Performance</b>\n"
        f"{top_performer}"
        f"📬 Alerts Sent: {_alert_stats['total_sent']}\n"
        f"\n🕐 <b>Report Time:</b> {format_wib_short(now_wib())}\n"
        f"\n✅ <i>Pipeline running smoothly!</i>"
    )

    _send_async(text)


def send_hourly_summary(symbol: str, avg_price: float, min_price: float, max_price: float, volume: float):
    """Send hourly summary for a specific symbol."""
    volatility = ((max_price - min_price) / avg_price * 100) if avg_price > 0 else 0
    
    text = (
        f"⏰ <b>HOURLY SUMMARY</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💎 <b>Symbol:</b> {symbol}\n"
        f"💰 <b>Avg Price:</b> ${avg_price:,.2f}\n"
        f"📊 <b>Range:</b> ${min_price:,.2f} - ${max_price:,.2f}\n"
        f"⚡ <b>Volatility:</b> {volatility:.2f}%\n"
        f"📈 <b>Volume:</b> {volume:,.0f}\n"
        f"🕐 <b>Time:</b> {now_wib().strftime('%Y-%m-%d %H:00')} WIB"
    )
    
    _send_async(text)


def send_startup_notification():
    """Send a notification when the pipeline starts."""
    text = (
        f"🚀 <b>PIPELINE STARTED</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"✅ Crypto Sentiment & Price Analytics Pipeline is now running.\n"
        f"\n<b>📡 Active Components:</b>\n"
        f"• Binance WebSocket (Real-time)\n"
        f"• News Scraper (7 sources)\n"
        f"• Sentiment Analysis (VADER)\n"
        f"• Anomaly Detection (ML)\n"
        f"• Gold Layer Processor\n"
        f"\n🕐 <b>Start Time:</b> {format_wib(now_wib())}\n"
        f"\n💡 <i>All systems operational!</i>"
    )

    _send_async(text)


def send_shutdown_notification():
    """Send a notification when pipeline stops."""
    text = (
        f"🛑 <b>PIPELINE STOPPED</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"Pipeline has been shut down gracefully.\n"
        f"\n📊 <b>Session Stats:</b>\n"
        f"• Alerts Sent: {_alert_stats['total_sent']}\n"
        f"• Anomalies: {_alert_stats['anomalies']}\n"
        f"• Errors: {_alert_stats['errors']}\n"
        f"\n🕐 <b>Stop Time:</b> {format_wib(now_wib())}"
    )
    
    _send_async(text)


# ──────────────────────────────────────────────────────────────────────
# Interactive Bot Commands
# ──────────────────────────────────────────────────────────────────────

def handle_predict_command(symbol: str = "BTCUSDT"):
    """Handle /predict command - get ML trading signal."""
    try:
        from ml.inference.lstm_inference import fetch_recent_data
        from ml.models.lstm_price_predictor import LSTMPricePredictor
        
        # Initialize predictor
        predictor = LSTMPricePredictor(symbol=symbol)
        
        # Load model
        if not predictor.load_model():
            text = (
                f"⚠️ <b>Model Not Found</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"No trained LSTM model for {symbol}.\n"
                f"\n💡 <i>Train model first:\n"
                f"python ml/training/train_lstm_model.py --symbol {symbol}</i>"
            )
            _send_message(text)
            return
        
        # Fetch recent data
        df = fetch_recent_data(symbol, hours=6)
        
        if df.empty or len(df) < predictor.lookback_window:
            text = (
                f"⚠️ <b>Insufficient Data</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"Need at least {predictor.lookback_window} records.\n"
                f"Currently have: {len(df)}\n"
                f"\n💡 <i>Wait for WebSocket to collect more data</i>"
            )
            _send_message(text)
            return
        
        # Make prediction
        prediction = predictor.predict_next(df)
        
        if 'error' in prediction:
            text = (
                f"❌ <b>Prediction Error</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"<code>{prediction['error']}</code>"
            )
            _send_message(text)
            return
        
        # Send prediction alert
        signal_emoji = {
            'BUY': '🟢',
            'SELL': '🔴',
            'HOLD': '🟡'
        }.get(prediction['signal'], '⚪')
        
        signal_advice = {
            'BUY': '📈 Consider buying - price expected to rise',
            'SELL': '📉 Consider selling - price expected to fall',
            'HOLD': '⏸️ Hold position - minimal movement expected'
        }.get(prediction['signal'], '')
        
        text = (
            f"{signal_emoji} <b>LSTM PREDICTION</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💎 <b>Symbol:</b> {symbol}\n"
            f"💰 <b>Current Price:</b> ${prediction['current_price']:,.2f}\n"
            f"🔮 <b>Predicted Price:</b> ${prediction['predicted_price']:,.2f}\n"
            f"📊 <b>Expected Change:</b> {prediction['price_change_pct']:+.2f}%\n"
            f"\n<b>🎯 TRADING SIGNAL: {prediction['signal']}</b>\n"
            f"🎲 <b>Confidence:</b> {prediction['confidence']:.1%}\n"
            f"\n💡 {signal_advice}\n"
            f"🕐 <b>Time:</b> {format_wib(now_wib())}\n"
            f"\n⚠️ <i>Not financial advice - DYOR!</i>"
        )
        
        _send_message(text)
        logger.info("telegram_predict_command_handled", symbol=symbol, signal=prediction['signal'])
        
    except Exception as e:
        logger.error("telegram_predict_command_error", error=str(e))
        text = (
            f"❌ <b>Command Error</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<code>{_sanitize_error(str(e))}</code>\n"
            f"\n💡 <i>Check logs for details</i>"
        )
        _send_message(text)


def handle_status_command():
    """Handle /status command - get system status."""
    try:
        from storage.db_models import get_session, PriceData, NewsArticle, AnomalyEvent
        from monitoring.logger import metrics as pipeline_metrics
        
        session = get_session()
        
        try:
            # Count records
            price_count = session.query(PriceData).count()
            news_count = session.query(NewsArticle).count()
            anomaly_count = session.query(AnomalyEvent).count()
            
            # Get latest price
            latest_price = session.query(PriceData).order_by(
                PriceData.timestamp.desc()
            ).first()
            
            price_info = ""
            if latest_price:
                price_info = (
                    f"\n<b>💰 Latest Price</b>\n"
                    f"• {latest_price.symbol}: ${latest_price.price:,.2f}\n"
                    f"• Updated: {format_wib_short(latest_price.timestamp)}"
                )
            
            stats = get_alert_stats()
            metrics = pipeline_metrics.get_metrics()
            
            text = (
                f"📊 <b>SYSTEM STATUS</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"✅ <b>Pipeline:</b> Running\n"
                f"🕐 <b>Time:</b> {format_wib(now_wib())}\n"
                f"\n<b>📈 Database Records</b>\n"
                f"• Price Data: {price_count:,}\n"
                f"• News Articles: {news_count:,}\n"
                f"• Anomalies: {anomaly_count}\n"
                f"{price_info}\n"
                f"\n<b>🔔 Alert Stats (Today)</b>\n"
                f"• Total Sent: {stats['total_sent']}\n"
                f"• Anomalies: {stats['anomalies']}\n"
                f"• News Alerts: {stats['news_alerts']}\n"
                f"• Price Spikes: {stats['price_spikes']}\n"
                f"\n<b>📡 Pipeline Metrics</b>\n"
                f"• Records Processed: {metrics.get('records_processed', 0):,}\n"
                f"• Anomalies Detected: {metrics.get('anomalies_detected', 0)}\n"
                f"• Errors: {metrics.get('errors', 0)}\n"
                f"\n💡 <i>All systems operational!</i>"
            )
            
            _send_message(text)
            
        finally:
            session.close()
            
    except Exception as e:
        logger.error("telegram_status_command_error", error=str(e))
        text = (
            f"❌ <b>Status Check Error</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<code>{_sanitize_error(str(e))}</code>"
        )
        _send_message(text)


def handle_help_command():
    """Handle /help command - show available commands."""
    text = (
        f"ℹ️ <b>AVAILABLE COMMANDS</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"\n<b>📊 Trading & Analysis</b>\n"
        f"• <code>/predict</code> - Get AI trading signal (BUY/SELL/HOLD)\n"
        f"• <code>/predict BTCUSDT</code> - Predict specific symbol\n"
        f"\n<b>📈 System Info</b>\n"
        f"• <code>/status</code> - Pipeline status & stats\n"
        f"• <code>/help</code> - Show this help message\n"
        f"\n<b>🔔 Auto Alerts</b>\n"
        f"You will automatically receive:\n"
        f"• 🟢 Positive news alerts\n"
        f"• 🔴 Negative news alerts\n"
        f"• 💹 Price spike alerts\n"
        f"• 📊 Volume surge alerts\n"
        f"• 🚨 Anomaly detections\n"
        f"\n💡 <i>Bot running 24/7!</i>\n"
        f"🕐 {format_wib_short(now_wib())}"
    )
    
    _send_message(text)


def start_bot_listener():
    """
    Start listening for Telegram commands.
    Polls Telegram API for updates and handles commands.
    Run this in background: python monitoring/telegram_alert.py
    """
    if not _is_configured():
        logger.warning("telegram_bot_not_configured")
        print("⚠️  Telegram bot not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")
        return
    
    logger.info("telegram_bot_listener_started")
    print("\n" + "="*60)
    print("🤖 Telegram Bot Listener Started")
    print("="*60)
    print(f"Bot Token: {TELEGRAM_BOT_TOKEN[:10]}...{TELEGRAM_BOT_TOKEN[-5:]}")
    print(f"Chat ID: {TELEGRAM_CHAT_ID}")
    print("\n📱 Available Commands:")
    print("  /predict - Get AI trading signal")
    print("  /status - System status")
    print("  /help - Show help")
    print("\n🔔 Auto-alerts enabled for news sentiment!")
    print("\n⏹️  Press Ctrl+C to stop")
    print("="*60 + "\n")
    
    offset = None
    
    try:
        while True:
            try:
                # Poll for updates
                params = {"timeout": 30, "allowed_updates": ["message"]}
                if offset:
                    params["offset"] = offset
                
                response = requests.get(
                    f"{TELEGRAM_API_URL}/getUpdates",
                    params=params,
                    timeout=35
                )
                
                if response.status_code != 200:
                    logger.warning("telegram_poll_failed", status=response.status_code)
                    continue
                
                data = response.json()
                
                if not data.get("ok"):
                    continue
                
                updates = data.get("result", [])
                
                for update in updates:
                    offset = update["update_id"] + 1
                    
                    message = update.get("message")
                    if not message or "text" not in message:
                        continue
                    
                    text = message["text"].strip()
                    chat_id = str(message["chat"]["id"])
                    
                    # Only respond to configured chat
                    if chat_id != TELEGRAM_CHAT_ID:
                        continue
                    
                    logger.info("telegram_command_received", command=text)
                    print(f"📨 Command: {text}")
                    
                    # Handle commands
                    if text.startswith("/predict"):
                        parts = text.split()
                        symbol = parts[1] if len(parts) > 1 else "BTCUSDT"
                        handle_predict_command(symbol.upper())
                    elif text == "/status":
                        handle_status_command()
                    elif text == "/help" or text == "/start":
                        handle_help_command()
                    else:
                        # Unknown command
                        _send_message(
                            f"❓ Unknown command: <code>{text}</code>\n\n"
                            f"Use /help to see available commands."
                        )
                
            except requests.exceptions.Timeout:
                # Normal timeout, continue polling
                continue
            except requests.exceptions.RequestException as e:
                logger.error("telegram_poll_error", error=str(e))
                time.sleep(5)
                continue
            except Exception as e:
                logger.error("telegram_listener_error", error=str(e))
                time.sleep(5)
                
    except KeyboardInterrupt:
        logger.info("telegram_bot_listener_stopped")
        print("\n🛑 Bot listener stopped")


import time

# ──────────────────────────────────────────────────────────────────────
# Self-test
# ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Telegram Bot for Crypto Pipeline")
    parser.add_argument("--test", action="store_true", help="Send test message")
    parser.add_argument("--listen", action="store_true", help="Start bot listener for commands")
    parser.add_argument("--predict", type=str, help="Test predict command for symbol")
    parser.add_argument("--status", action="store_true", help="Test status command")
    
    args = parser.parse_args()
    
    if not _is_configured():
        print("❌ TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set in .env")
        print("   Set them first, then run this script again.")
        sys.exit(1)
    
    if args.listen:
        # Start bot listener
        start_bot_listener()
    elif args.predict:
        # Test predict command
        handle_predict_command(args.predict.upper())
    elif args.status:
        # Test status command
        handle_status_command()
    elif args.test:
        # Send test message
        print("Sending test alert to Telegram...")
        success = _send_message(
            "🧪 <b>TEST ALERT</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "If you see this, Telegram alerts are working!\n"
            f"🕐 {format_wib(now_wib())}\n"
            f"\n💡 Try commands:\n"
            f"• /predict - Get trading signal\n"
            f"• /status - System status\n"
            f"• /help - Show help"
        )
        print(f"Result: {'✅ Success' if success else '❌ Failed'}")
    else:
        # Show usage
        print("\n🤖 Telegram Bot for Crypto Pipeline\n")
        print("Usage:")
        print("  python monitoring/telegram_alert.py --test      # Test connection")
        print("  python monitoring/telegram_alert.py --listen    # Start bot listener")
        print("  python monitoring/telegram_alert.py --predict BTCUSDT  # Test predict")
        print("  python monitoring/telegram_alert.py --status    # Test status")
        print("\nMake sure TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are set in .env")

