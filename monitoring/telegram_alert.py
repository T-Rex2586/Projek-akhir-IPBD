"""
Sistem notifikasi Telegram untuk pemantauan alur kerja data kripto.

Menyediakan fungsionalitas peringatan anomali waktu nyata, ringkasan harian/per jam,
serta perintah interaktif untuk memberikan sinyal perdagangan berbasis pembelajaran mesin.
"""

import os
import sys
import requests
import threading
import time
import argparse
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv
import html

# Konfigurasi path proyek
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from monitoring.logger import get_logger
from monitoring.timezone_utils import now_wib, format_wib, format_wib_short

load_dotenv()
logger = get_logger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
ADMIN_TELEGRAM_CHAT_ID = os.getenv("ADMIN_TELEGRAM_CHAT_ID", TELEGRAM_CHAT_ID)
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# Mekanisme pembatasan laju pengiriman (rate limiting)
_last_alert_times = {}
ALERT_COOLDOWN_SECONDS = 60

# Statistik pengiriman pesan
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
    """Memvalidasi konfigurasi kredensial API Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    if len(TELEGRAM_BOT_TOKEN) < 40 or not TELEGRAM_CHAT_ID.lstrip('-').isdigit():
        logger.warning("telegram_invalid_credentials")
        return False
    return True


def _send_message(text: str, parse_mode: str = "HTML") -> bool:
    """Mengirim pesan ke saluran Telegram yang telah dikonfigurasi."""
    if not _is_configured():
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
            logger.info("telegram_alert_sent", chat_id=TELEGRAM_CHAT_ID)
            return True
        else:
            _increment_alert_count("failed")
            return False

    except Exception as e:
        _increment_alert_count("failed")
        logger.error("telegram_send_failed", error=str(e))
        return False


def _send_async(text: str, parse_mode: str = "HTML"):
    """Mengirim pesan Telegram secara asinkron (fire-and-forget)."""
    thread = threading.Thread(target=_send_message, args=(text, parse_mode), daemon=True)
    thread.start()


def _send_admin_message(text: str, parse_mode: str = "HTML") -> bool:
    """Mengirim pesan khusus kepada administrator sistem."""
    if not _is_configured():
        return False
    chat_id = ADMIN_TELEGRAM_CHAT_ID or TELEGRAM_CHAT_ID
    try:
        response = requests.post(
            f"{TELEGRAM_API_URL}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode, "disable_web_page_preview": True},
            timeout=10,
        )
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error("telegram_send_admin_failed", error=str(e))
        return False


def _send_admin_async(text: str, parse_mode: str = "HTML"):
    thread = threading.Thread(target=_send_admin_message, args=(text, parse_mode), daemon=True)
    thread.start()


def _send_direct_message(chat_id: str, text: str, parse_mode: str = "HTML") -> bool:
    """Mengirim pesan langsung ke ID pengguna tertentu."""
    if not _is_configured():
        return False
    try:
        response = requests.post(
            f"{TELEGRAM_API_URL}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode, "disable_web_page_preview": True},
            timeout=10,
        )
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error("telegram_send_direct_failed", error=str(e), chat_id=chat_id)
        return False


def _should_send(alert_key: str) -> bool:
    """Mengevaluasi batas pengiriman pesan berdasarkan interval waktu pendinginan."""
    now = datetime.utcnow().timestamp()
    last = _last_alert_times.get(alert_key, 0)
    if now - last < ALERT_COOLDOWN_SECONDS:
        return False
    _last_alert_times[alert_key] = now
    return True


def _increment_alert_count(counter_name: str = "total_sent"):
    """Memperbarui statistik internal untuk pelaporan aktivitas peringatan."""
    global _alert_count_date
    today = datetime.utcnow().date()
    
    if today != _alert_count_date:
        for key in _alert_stats:
            if key != "last_alert_time":
                _alert_stats[key] = 0
        _alert_count_date = today
    
    if counter_name in _alert_stats:
        _alert_stats[counter_name] += 1


def get_alert_stats() -> dict:
    """Mengembalikan akumulasi statistik peringatan Telegram."""
    return {
        **_alert_stats,
        "date": str(_alert_count_date),
        "configured": _is_configured(),
        "bot_token_set": bool(TELEGRAM_BOT_TOKEN),
        "chat_id_set": bool(TELEGRAM_CHAT_ID),
        "last_alert": str(_alert_stats["last_alert_time"]) if _alert_stats["last_alert_time"] else "Tidak Ada",
    }


def _sanitize_error(msg: str, max_length: int = 300) -> str:
    """Membersihkan pesan kesalahan dari detail sistem yang bersifat sensitif."""
    sanitized = msg.replace("\\", "/")
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length] + "..."
    return sanitized


def send_anomaly_alert(anomaly: dict):
    """Mengirimkan peringatan jika terdeteksi adanya kejadian anomali pada data."""
    event_type = anomaly.get("event_type", "unknown")
    symbol = anomaly.get("symbol", "N/A")
    alert_key = f"anomaly_{event_type}_{symbol}"

    if not _should_send(alert_key):
        return

    _increment_alert_count("anomalies")
    
    severity = anomaly.get("severity", "medium")
    severity_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(severity, "⚪")
    
    event_display = {
        "price_spike": "💹 Lonjakan Harga",
        "stream_price_spike": "💹 Lonjakan Harga (Stream)",
        "volume_surge": "📊 Lonjakan Volume",
        "stream_volume_surge": "📊 Lonjakan Volume (Stream)",
        "sentiment_crash": "😱 Penurunan Sentimen",
        "stream_sentiment_crash": "😱 Penurunan Sentimen (Stream)",
        "volatility_spike": "⚡ Volatilitas Tinggi",
        "sudden_drop": "📉 Penurunan Tajam",
        "ml_anomaly": "🤖 Anomali ML",
        "batch_ml_anomaly": "🤖 Anomali ML (Batch)",
        "whale_trade": "🐋 Transaksi Skala Besar",
        "bearish_divergence": "⚠️ Divergensi Bearish",
        "bullish_divergence": "🚀 Divergensi Bullish"
    }.get(event_type, event_type.replace("_", " ").title())

    if "whale" in event_type:
        severity_emoji = "🐋"
    elif "bullish" in event_type:
        severity_emoji = "🚀"
    elif "bearish" in event_type:
        severity_emoji = "⚠️"

    text = (
        f"{severity_emoji} <b>DETEKSI ANOMALI</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>Tipe:</b> {event_display}\n"
        f"💎 <b>Simbol:</b> {symbol}\n"
        f"📝 <b>Detail:</b> {html.escape(str(anomaly.get('description', '-')))}\n"
        f"📊 <b>Nilai:</b> {anomaly.get('value', '-')}\n"
        f"⚡ <b>Ambang Batas:</b> {anomaly.get('threshold', '-')}\n"
        f"🔥 <b>Tingkat Keparahan:</b> {severity.upper()}\n"
        f"🕐 <b>Waktu:</b> {format_wib(now_wib())}\n"
        f"\n💡 <i>Periksa dasbor untuk informasi lebih lanjut.</i>"
    )

    _send_async(text)


def send_price_spike_alert(symbol: str, price_change_pct: float, current_price: float, previous_price: Optional[float] = None):
    """Menyiarkan peringatan ketika terdapat perubahan harga yang ekstrem."""
    alert_key = f"price_spike_{symbol}"
    if not _should_send(alert_key):
        return

    _increment_alert_count("price_spikes")
    
    direction = "📈" if price_change_pct > 0 else "📉"
    trend_word = "NAIK" if price_change_pct > 0 else "TURUN"
    
    prev_text = f"\n📌 <b>Sebelumnya:</b> ${previous_price:,.2f}" if previous_price else ""

    text = (
        f"{direction} <b>HARGA {trend_word}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💎 <b>Simbol:</b> {symbol}\n"
        f"💰 <b>Sekarang:</b> ${current_price:,.2f}{prev_text}\n"
        f"📊 <b>Perubahan:</b> {price_change_pct:+.2f}%\n"
        f"⏱️ <b>Rentang Waktu:</b> 5 menit\n"
        f"🕐 <b>Waktu:</b> {format_wib(now_wib())}"
    )

    _send_async(text)


def send_prediction_alert(symbol: str, current_price: float, predicted_price: float, signal: str, confidence: float):
    """Menginformasikan prediksi harga serta sinyal perdagangan dari model LSTM."""
    alert_key = f"prediction_{symbol}_{signal}"
    if not _should_send(alert_key):
        return

    _increment_alert_count("anomalies")

    signal_emoji = {'BUY': '🟢', 'SELL': '🔴', 'HOLD': '🟡'}.get(signal, '⚪')
    price_change_pct = ((predicted_price - current_price) / current_price) * 100
    
    text = (
        f"{signal_emoji} <b>SINYAL PREDIKSI LSTM</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💎 <b>Simbol:</b> {symbol}\n"
        f"📊 <b>Sinyal:</b> {signal}\n"
        f"🎯 <b>Tingkat Kepercayaan:</b> {confidence:.2%}\n"
        f"💰 <b>Sekarang:</b> ${current_price:,.2f}\n"
        f"🔮 <b>Prediksi:</b> ${predicted_price:,.2f} ({price_change_pct:+.2f}%)\n"
        f"🕐 <b>Waktu:</b> {format_wib(now_wib())}"
    )

    _send_async(text)


def send_volume_alert(symbol: str, current_volume: float, avg_volume: float, surge_multiplier: float):
    """Memberikan notifikasi terkait aktivitas volume perdagangan yang tidak wajar."""
    alert_key = f"volume_{symbol}"
    if not _should_send(alert_key):
        return
    
    _increment_alert_count("anomalies")

    text = (
        f"📊 <b>LONJAKAN VOLUME</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💎 <b>Simbol:</b> {symbol}\n"
        f"📈 <b>Volume Saat Ini:</b> {current_volume:,.0f}\n"
        f"📉 <b>Rata-rata Volume:</b> {avg_volume:,.0f}\n"
        f"⚡ <b>Pengali:</b> {surge_multiplier:.2f}x\n"
        f"🕐 <b>Waktu:</b> {format_wib(now_wib())}"
    )

    _send_async(text)


def send_news_sentiment_alert(source: str, sentiment_score: float, title: str):
    """Mengirim peringatan jika terdeteksi sentimen berita yang signifikan."""
    alert_key = f"news_{source}_{int(abs(sentiment_score)*100)}"
    if not _should_send(alert_key):
        return
    
    _increment_alert_count("news_alerts")
    
    if sentiment_score > 0.5:
        emoji = "🟢"
        label = "BERITA POSITIF"
    elif sentiment_score < -0.5:
        emoji = "🔴"
        label = "BERITA NEGATIF"
    else:
        return
    
    text = (
        f"{emoji} <b>{label}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📰 <b>Sumber:</b> {html.escape(source)}\n"
        f"📊 <b>Sentimen:</b> {sentiment_score:+.3f}\n"
        f"📝 <b>Judul Utama:</b> {html.escape(title[:150])}\n"
        f"🕐 <b>Waktu:</b> {format_wib(now_wib())}"
    )
    
    _send_async(text)


def send_pipeline_error_alert(component: str, error_msg: str):
    """Melaporkan kegagalan sistematis pada komponen infrastruktur data (Hanya ke Admin)."""
    alert_key = f"error_{component}"
    if not _should_send(alert_key):
        return

    _increment_alert_count("errors")
    safe_error = _sanitize_error(error_msg)

    text = (
        f"⛔ <b>KESALAHAN SISTEM</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔧 <b>Komponen:</b> {html.escape(component)}\n"
        f"❌ <b>Kesalahan:</b> <code>{html.escape(safe_error)}</code>\n"
        f"🕐 <b>Waktu:</b> {format_wib(now_wib())}\n"
        f"\n⚠️ <i>Diperlukan tinjauan segera.</i>"
    )

    _send_admin_async(text)


def send_pipeline_resolved_alert(component: str):
    """Memberitahukan bahwa komponen yang sebelumnya bermasalah telah pulih (Hanya ke Admin)."""
    alert_key = f"error_{component}"
    
    # Reset cooldown agar jika error terjadi lagi, ia tidak tertahan oleh rate limit
    if alert_key in _last_alert_times:
        del _last_alert_times[alert_key]

    text = (
        f"✅ <b>SISTEM PULIH</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔧 <b>Komponen:</b> {html.escape(component)}\n"
        f"✨ <b>Status:</b> Operasi kembali normal\n"
        f"🕐 <b>Waktu:</b> {format_wib(now_wib())}"
    )

    _send_admin_async(text)


def send_airflow_failure_alert(context: dict):
    """Menangani panggilan balik kegagalan fungsi pada alur DAG Airflow."""
    _increment_alert_count("errors")
    
    task_instance = context.get('task_instance')
    task_id = task_instance.task_id if task_instance else 'unknown_task'
    dag_id = task_instance.dag_id if task_instance else 'unknown_dag'
    exec_date = context.get('execution_date')
    exec_date_str = exec_date.strftime('%Y-%m-%d %H:%M:%S') if exec_date else 'unknown'
    exception = context.get('exception')
    
    safe_error = _sanitize_error(str(exception), max_length=500)

    text = (
        f"🚨 <b>KEGAGALAN TUGAS AIRFLOW</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🛠 <b>DAG:</b> {html.escape(dag_id)}\n"
        f"📌 <b>Tugas:</b> {html.escape(task_id)}\n"
        f"⏰ <b>Waktu Eksekusi:</b> {exec_date_str}\n"
        f"❌ <b>Kesalahan:</b> <code>{html.escape(safe_error)}</code>\n"
        f"🕐 <b>Waktu Laporan:</b> {format_wib(now_wib())}\n"
        f"\n⚠️ <i>Tinjau log Airflow terkait informasi selengkapnya.</i>"
    )

    _send_admin_async(text)


def send_daily_summary(
    total_prices: int,
    total_news: int,
    total_anomalies: int,
    avg_sentiment: float,
    top_symbol: Optional[str] = None,
    top_symbol_change: Optional[float] = None,
):
    """Menerbitkan ringkasan komprehensif atas operasi pemrosesan harian."""
    _increment_alert_count("summaries")
    
    sentiment_emoji = "🟢" if avg_sentiment > 0.05 else "🔴" if avg_sentiment < -0.05 else "⚪"
    sentiment_label = "Positif" if avg_sentiment > 0.05 else "Negatif" if avg_sentiment < -0.05 else "Netral"
    
    top_performer = ""
    if top_symbol and top_symbol_change is not None:
        perf_emoji = "📈" if top_symbol_change > 0 else "📉"
        top_performer = f"{perf_emoji} <b>Performa Tertinggi:</b> {top_symbol} ({top_symbol_change:+.2f}%)\n"

    text = (
        f"📊 <b>RINGKASAN SISTEM HARIAN</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📅 <b>Tanggal:</b> {now_wib().strftime('%Y-%m-%d')}\n"
        f"\n<b>📈 Data yang Diperoleh</b>\n"
        f"💰 Rekaman Harga: {total_prices:,}\n"
        f"📰 Artikel Berita: {total_news:,}\n"
        f"🚨 Kejadian Anomali: {total_anomalies}\n"
        f"\n<b>💭 Sentimen Pasar</b>\n"
        f"{sentiment_emoji} Rata-rata: {sentiment_label} ({avg_sentiment:+.3f})\n"
        f"\n<b>🏆 Kinerja Aset</b>\n"
        f"{top_performer}"
        f"📬 Peringatan Terkirim: {_alert_stats['total_sent']}\n"
        f"\n🕐 <b>Waktu Pelaporan:</b> {format_wib_short(now_wib())}"
    )

    _send_async(text)


def send_hourly_summary(symbol: str, avg_price: float, min_price: float, max_price: float, volume: float):
    """Menyediakan ringkasan pasar dalam skala per jam."""
    volatility = ((max_price - min_price) / avg_price * 100) if avg_price > 0 else 0
    
    text = (
        f"⏰ <b>RINGKASAN PER JAM</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💎 <b>Simbol:</b> {symbol}\n"
        f"💰 <b>Rata-rata Harga:</b> ${avg_price:,.2f}\n"
        f"📊 <b>Rentang:</b> ${min_price:,.2f} - ${max_price:,.2f}\n"
        f"⚡ <b>Volatilitas:</b> {volatility:.2f}%\n"
        f"📈 <b>Volume:</b> {volume:,.0f}\n"
        f"🕐 <b>Waktu:</b> {now_wib().strftime('%Y-%m-%d %H:00')} WIB"
    )
    
    _send_async(text)


def send_startup_notification():
    """Mengirim sinyal inisialisasi ketika pipeline mulai beroperasi."""
    text = (
        f"🚀 <b>INISIALISASI SISTEM</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"✅ Pipeline Analisis Sentimen & Harga Kripto telah diaktifkan.\n"
        f"\n<b>📡 Komponen Aktif:</b>\n"
        f"• Aliran Data Binance WebSocket\n"
        f"• Pengumpulan Berita RSS\n"
        f"• Analisis Sentimen (VADER)\n"
        f"• Deteksi Anomali Berbasis ML\n"
        f"• Modul Pemrosesan Lapisan Emas\n"
        f"\n🕐 <b>Waktu Mulai:</b> {format_wib(now_wib())}"
    )

    _send_async(text)


def send_shutdown_notification():
    """Mengirim pemberitahuan terminasi sistem."""
    text = (
        f"🛑 <b>TERMINASI SISTEM</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"Pipeline telah dimatikan secara prosedural.\n"
        f"\n📊 <b>Statistik Sesi:</b>\n"
        f"• Pesan Terkirim: {_alert_stats['total_sent']}\n"
        f"• Anomali: {_alert_stats['anomalies']}\n"
        f"• Kesalahan: {_alert_stats['errors']}\n"
        f"\n🕐 <b>Waktu Berhenti:</b> {format_wib(now_wib())}"
    )
    
    _send_async(text)


def handle_predict_command(chat_id: str = None, symbol: str = "BTCUSDT"):
    """Menanggapi perintah untuk melakukan prediksi harga berbasis model LSTM."""
    chat_id = chat_id or TELEGRAM_CHAT_ID
    try:
        from ml.inference.lstm_inference import fetch_recent_data
        from ml.models.lstm_price_predictor import LSTMPricePredictor
        
        predictor = LSTMPricePredictor(symbol=symbol)
        
        if not predictor.load_model():
            text = (
                f"⚠️ <b>Model Tidak Ditemukan</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"Model LSTM belum dilatih untuk instrumen {symbol}.\n"
                f"\n💡 <i>Harap jalankan pelatihan awal.</i>"
            )
            _send_direct_message(chat_id, text)
            return
        
        df = fetch_recent_data(symbol, hours=6)
        if df.empty or len(df) < predictor.lookback_window:
            text = (
                f"⚠️ <b>Kekurangan Data Historis</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"Membutuhkan sekurang-kurangnya {predictor.lookback_window} rekaman.\n"
                f"Data saat ini: {len(df)}\n"
            )
            _send_direct_message(chat_id, text)
            return
        
        prediction = predictor.predict_next(df)
        if 'error' in prediction:
            text = (
                f"❌ <b>Kesalahan Prediksi</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"<code>{prediction['error']}</code>"
            )
            _send_direct_message(chat_id, text)
            return
        
        signal_emoji = {'BUY': '🟢', 'SELL': '🔴', 'HOLD': '🟡'}.get(prediction['signal'], '⚪')
        signal_advice = {
            'BUY': '📈 Sinyal Beli - Proyeksi kenaikan harga teridentifikasi',
            'SELL': '📉 Sinyal Jual - Proyeksi penurunan harga teridentifikasi',
            'HOLD': '⏸️ Sinyal Tahan - Fluktuasi tidak signifikan'
        }.get(prediction['signal'], '')
        
        text = (
            f"{signal_emoji} <b>PROYEKSI HARGA LSTM</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💎 <b>Simbol:</b> {symbol}\n"
            f"💰 <b>Harga Aktul:</b> ${prediction['current_price']:,.2f}\n"
            f"🔮 <b>Harga Proyeksi:</b> ${prediction['predicted_price']:,.2f}\n"
            f"📊 <b>Ekspektasi Perubahan:</b> {prediction['price_change_pct']:+.2f}%\n"
            f"\n<b>🎯 SINYAL TRANSAKSI: {prediction['signal']}</b>\n"
            f"🎲 <b>Tingkat Kepercayaan:</b> {prediction['confidence']:.1%}\n"
            f"\n💡 {signal_advice}\n"
            f"🕐 <b>Waktu:</b> {format_wib(now_wib())}\n"
            f"\n⚠️ <i>Sistem ini ditujukan untuk eksperimen analitik akademis semata.</i>"
        )
        
        _send_direct_message(chat_id, text)
        logger.info("telegram_predict_command_handled", symbol=symbol, signal=prediction['signal'])
        
    except Exception as e:
        logger.error("telegram_predict_command_error", error=str(e))
        text = (
            f"❌ <b>Kesalahan Perintah</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<code>{_sanitize_error(str(e))}</code>"
        )
        _send_direct_message(chat_id, text)


def handle_status_command(chat_id: str = None):
    """Menanggapi permintaan diagnostik status dari pengguna."""
    chat_id = chat_id or TELEGRAM_CHAT_ID
    try:
        from storage.db_models import get_session, PriceData, NewsArticle, AnomalyEvent
        from monitoring.logger import metrics as pipeline_metrics
        
        session = get_session()
        try:
            price_count = session.query(PriceData).count()
            news_count = session.query(NewsArticle).count()
            anomaly_count = session.query(AnomalyEvent).count()
            
            latest_price = session.query(PriceData).order_by(PriceData.timestamp.desc()).first()
            price_info = ""
            if latest_price:
                price_info = (
                    f"\n<b>💰 Kuotasi Terakhir</b>\n"
                    f"• {latest_price.symbol}: ${latest_price.price:,.2f}\n"
                    f"• Diperbarui pada: {format_wib_short(latest_price.timestamp)}"
                )
            
            stats = get_alert_stats()
            metrics = pipeline_metrics.get_metrics()
            
            text = (
                f"📊 <b>DIAGNOSTIK SISTEM</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"✅ <b>Status:</b> Beroperasi\n"
                f"🕐 <b>Waktu:</b> {format_wib(now_wib())}\n"
                f"\n<b>📈 Akuisisi Data Basis Data</b>\n"
                f"• Volume Harga: {price_count:,}\n"
                f"• Volume Berita: {news_count:,}\n"
                f"• Indikasi Anomali: {anomaly_count}\n"
                f"{price_info}\n"
                f"\n<b>🔔 Rekapitulasi Peringatan (Harian)</b>\n"
                f"• Total Terkirim: {stats['total_sent']}\n"
                f"• Anomali Terdeteksi: {stats['anomalies']}\n"
                f"• Peringatan Berita: {stats['news_alerts']}\n"
                f"• Lonjakan Harga: {stats['price_spikes']}\n"
                f"\n<b>📡 Metrik Internal</b>\n"
                f"• Baris Diproses: {metrics.get('records_processed', 0):,}\n"
                f"• Kesalahan Teknis: {metrics.get('errors', 0)}\n"
            )
            
            _send_direct_message(chat_id, text)
        finally:
            session.close()
    except Exception as e:
        logger.error("telegram_status_command_error", error=str(e))
        text = f"❌ <b>Kesalahan Diagnostik</b>\n<code>{_sanitize_error(str(e))}</code>"
        _send_direct_message(chat_id, text)


def handle_help_command(chat_id: str = None):
    """Memberikan panduan penggunaan fitur interaktif Telegram."""
    chat_id = chat_id or TELEGRAM_CHAT_ID
    text = (
        f"ℹ️ <b>PANDUAN INSTRUKSI OPERASIONAL</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"\n<b>📊 Analitik Instan</b>\n"
        f"• <code>/predict</code> - Akses sinyal prediksi berbasis komputasi cerdas (LSTM)\n"
        f"• <code>/predict BTCUSDT</code> - Memilih instrumen secara kustom\n"
        f"\n<b>📈 Diagnostik Infrastruktur</b>\n"
        f"• <code>/status</code> - Menampilkan evaluasi kinerja sistem waktu nyata\n"
        f"• <code>/help</code> - Panduan bantuan interaktif\n"
        f"\n<b>🔔 Mekanisme Peringatan Otomatis</b>\n"
        f"Tersedia untuk indikasi terkait sentimen berita, fluktuasi harga ekstrem, dan anomali pasar kualitatif.\n"
        f"🕐 {format_wib_short(now_wib())}"
    )
    _send_direct_message(chat_id, text)


def start_bot_listener():
    """Menginisialisasi proses pendengar (polling) untuk mengevaluasi input perintah dari pengguna melalui platform Telegram."""
    if not _is_configured():
        logger.warning("telegram_bot_not_configured")
        print("Peringatan: API Token Telegram belum dikonfigurasi pada environment variable.")
        return
    
    logger.info("telegram_bot_listener_started")
    print("\n" + "="*60)
    print("Mekanisme pendengar Telegram telah terinisialisasi.")
    print("="*60)
    
    offset = None
    try:
        while True:
            try:
                params = {"timeout": 30, "allowed_updates": ["message"]}
                if offset:
                    params["offset"] = offset
                
                response = requests.get(f"{TELEGRAM_API_URL}/getUpdates", params=params, timeout=35)
                
                if response.status_code != 200:
                    continue
                
                data = response.json()
                if not data.get("ok"):
                    continue
                
                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    message = update.get("message")
                    if not message or "text" not in message:
                        continue
                    
                    text = message["text"].strip()
                    chat_id = str(message["chat"]["id"])
                    
                    if text.startswith("/predict"):
                        parts = text.split()
                        symbol = parts[1] if len(parts) > 1 else "BTCUSDT"
                        handle_predict_command(chat_id, symbol.upper())
                    elif text == "/status":
                        handle_status_command(chat_id)
                    elif text == "/help" or text == "/start":
                        handle_help_command(chat_id)
                    else:
                        _send_direct_message(chat_id, f"Instruksi tidak dikenali: <code>{text}</code>. Silakan gunakan /help.")
                        
            except requests.exceptions.Timeout:
                continue
            except requests.exceptions.RequestException as e:
                time.sleep(5)
            except Exception as e:
                time.sleep(5)
                
    except KeyboardInterrupt:
        logger.info("telegram_bot_listener_stopped")
        print("\nSistem pendengar dinonaktifkan secara manual.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Modul Interaksi Telegram")
    parser.add_argument("--test", action="store_true", help="Menginisiasi transmisi pesan uji coba")
    parser.add_argument("--listen", action="store_true", help="Mengaktifkan proses pendengar untuk interaksi dua arah")
    parser.add_argument("--predict", type=str, help="Menjalankan uji sintesis prediksi sinyal perdagangan")
    parser.add_argument("--status", action="store_true", help="Mengambil diagnostik status sistem")
    
    args = parser.parse_args()
    
    if not _is_configured():
        print("Variabel lingkungan Telegram (Token dan Chat ID) belum diatur. Harap evaluasi konfigurasi .env.")
        sys.exit(1)
    
    if args.listen:
        start_bot_listener()
    elif args.predict:
        handle_predict_command(symbol=args.predict.upper())
    elif args.status:
        handle_status_command()
    elif args.test:
        success = _send_message(
            "🧪 <b>UJI COBA SISTEM</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "Sistem peringatan Telegram telah berfungsi dengan optimal.\n"
            f"🕐 {format_wib(now_wib())}"
        )
        print(f"Hasil Eksekusi: {'Berhasil' if success else 'Gagal'}")
    else:
        print("Argumen tidak memadai. Harap jalankan menggunakan argumen seperti --listen, --test, --status, atau --predict.")
