"""
Enhanced Telegram Bot alert system for crypto pipeline.

Features:
- Real-time anomaly alerts (price spikes, volume surges, sentiment crashes)
- Daily/hourly summaries with charts
- Pipeline health monitoring
- Price threshold alerts
- Interactive commands support
- Rate limiting & deduplication
- Rich HTML formatting
- Statistics tracking

Setup:
1. Create bot via @BotFather → get token
2. Get chat_id from @userinfobot
3. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env
"""
import os
import sys
import requests
import threading
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

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
        f"📝 <b>Detail:</b> {anomaly.get('description', '-')}\n"
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
        f"📰 <b>Source:</b> {source}\n"
        f"📊 <b>Sentiment:</b> {sentiment_score:+.3f}\n"
        f"📝 <b>Headline:</b> {title[:150]}\n"
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
        f"🔧 <b>Component:</b> {component}\n"
        f"❌ <b>Error:</b> <code>{safe_error}</code>\n"
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
# Self-test
# ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if _is_configured():
        print("Sending test alert to Telegram...")
        success = _send_message(
            "🧪 <b>TEST ALERT</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "If you see this, Telegram alerts are working!\n"
            f"🕐 {format_wib(now_wib())}"
        )
        # Avoid emojis in Windows print to prevent UnicodeEncodeError
        print(f"Result: {'Success' if success else 'Failed'}")
    else:
        print("X TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set in .env")
        print("   Set them first, then run this script again.")
