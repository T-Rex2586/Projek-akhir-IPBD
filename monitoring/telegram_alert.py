"""
Telegram Bot alert system for the crypto pipeline.

Sends real-time anomaly alerts (price spikes, sentiment crashes, pipeline errors)
to a Telegram chat or group using the Telegram Bot API.

Setup:
1. Create a bot via @BotFather on Telegram
2. Get the bot token
3. Get your chat_id (message @userinfobot or @RawDataBot)
4. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env
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

load_dotenv()
logger = get_logger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# Rate limiting: minimum seconds between identical alerts
_last_alert_times = {}
ALERT_COOLDOWN_SECONDS = 60


def _is_configured() -> bool:
    """Check if Telegram credentials are configured."""
    return bool(TELEGRAM_BOT_TOKEN) and bool(TELEGRAM_CHAT_ID)


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
            logger.info("telegram_alert_sent", chat_id=TELEGRAM_CHAT_ID)
            return True
        else:
            logger.warning("telegram_api_error", response=result)
            return False

    except Exception as e:
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

    severity = anomaly.get("severity", "medium")
    severity_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(severity, "⚪")

    text = (
        f"{severity_emoji} <b>ANOMALY DETECTED</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>Type:</b> {event_type}\n"
        f"💎 <b>Symbol:</b> {symbol}\n"
        f"📝 <b>Detail:</b> {anomaly.get('description', '-')}\n"
        f"📊 <b>Value:</b> {anomaly.get('value', '-')}\n"
        f"⚡ <b>Threshold:</b> {anomaly.get('threshold', '-')}\n"
        f"🔥 <b>Severity:</b> {severity.upper()}\n"
        f"🕐 <b>Time:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
    )

    _send_async(text)


def send_price_spike_alert(symbol: str, price_change_pct: float, current_price: float):
    """Alert for a significant price spike."""
    alert_key = f"price_spike_{symbol}"
    if not _should_send(alert_key):
        return

    direction = "📈" if price_change_pct > 0 else "📉"

    text = (
        f"{direction} <b>PRICE SPIKE</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💎 <b>Symbol:</b> {symbol}\n"
        f"💰 <b>Price:</b> ${current_price:,.2f}\n"
        f"📊 <b>Change:</b> {price_change_pct:+.2f}%\n"
        f"🕐 <b>Time:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
    )

    _send_async(text)


def send_sentiment_alert(subreddit: str, compound_score: float, title: str):
    """Alert for extreme negative sentiment on Reddit."""
    alert_key = f"sentiment_{subreddit}"
    if not _should_send(alert_key):
        return

    text = (
        f"😱 <b>SENTIMENT CRASH</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📡 <b>Subreddit:</b> r/{subreddit}\n"
        f"📊 <b>Score:</b> {compound_score:.3f}\n"
        f"📝 <b>Post:</b> {title[:120]}\n"
        f"🕐 <b>Time:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
    )

    _send_async(text)


def send_pipeline_error_alert(component: str, error_msg: str):
    """Alert for a critical pipeline failure."""
    alert_key = f"error_{component}"
    if not _should_send(alert_key):
        return

    text = (
        f"⛔ <b>PIPELINE ERROR</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔧 <b>Component:</b> {component}\n"
        f"❌ <b>Error:</b> {error_msg[:300]}\n"
        f"🕐 <b>Time:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
    )

    _send_async(text)


def send_daily_summary(
    total_prices: int,
    total_reddit: int,
    total_news: int,
    total_anomalies: int,
    avg_sentiment: float,
):
    """Send a daily pipeline health summary."""
    sentiment_emoji = "🟢" if avg_sentiment > 0.05 else "🔴" if avg_sentiment < -0.05 else "⚪"

    text = (
        f"📊 <b>DAILY PIPELINE SUMMARY</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>Price Records:</b> {total_prices:,}\n"
        f"💬 <b>Reddit Posts:</b> {total_reddit:,}\n"
        f"📰 <b>News Articles:</b> {total_news:,}\n"
        f"🚨 <b>Anomalies:</b> {total_anomalies}\n"
        f"{sentiment_emoji} <b>Avg Sentiment:</b> {avg_sentiment:+.3f}\n"
        f"🕐 <b>Report Time:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
    )

    _send_async(text)


def send_startup_notification():
    """Send a notification when the pipeline starts."""
    text = (
        f"🚀 <b>PIPELINE STARTED</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"✅ Crypto Sentiment & Price Analytics Pipeline is now running.\n"
        f"🕐 <b>Time:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
    )

    _send_async(text)


# ──────────────────────────────────────────────────────────────────────
# Self-test
# ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if _is_configured():
        print("Sending test alert to Telegram...")
        from datetime import timezone
        now_utc = datetime.now(timezone.utc)
        success = _send_message(
            "🧪 <b>TEST ALERT</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "If you see this, Telegram alerts are working!\n"
            f"🕐 {now_utc.strftime('%Y-%m-%d %H:%M:%S')} UTC"
        )
        # Avoid emojis in Windows print to prevent UnicodeEncodeError
        print(f"Result: {'Success' if success else 'Failed'}")
    else:
        print("X TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set in .env")
        print("   Set them first, then run this script again.")
