"""
News-Based Trading Signal Analyzer

Menganalisa breaking news dan mengirim trading recommendation ke Telegram.
Menggabungkan:
- News sentiment (VADER)
- LSTM price prediction
- Trading signal logic

Features:
- Real-time news monitoring
- Automatic sentiment analysis
- Combined signal generation
- Telegram alerts dengan rekomendasi
"""
import sys
import os
import time
from datetime import datetime, timedelta
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from storage.db_models import get_session, NewsArticle, KlineData
from ml.models.lstm_price_predictor import LSTMPricePredictor
from monitoring.logger import get_logger
from monitoring.telegram_alert import _send_message, _is_configured

logger = get_logger(__name__)


class NewsSignalAnalyzer:
    """
    Analisa news dan generate trading signals dengan Telegram alerts.
    """
    
    def __init__(self, symbols=None, check_interval=60):
        """
        Initialize analyzer.
        
        Parameters
        ----------
        symbols : list
            List of symbols to monitor (default: BTC, ETH, BNB)
        check_interval : int
            Seconds between checks (default: 60)
        """
        self.symbols = symbols or ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
        self.check_interval = check_interval
        self.last_checked_news_id = {}
        
        # Load LSTM predictors
        self.predictors = {}
        for symbol in self.symbols:
            predictor = LSTMPricePredictor(symbol=symbol)
            if predictor.load_model():
                self.predictors[symbol] = predictor
                logger.info("lstm_predictor_loaded", symbol=symbol)
            else:
                logger.warning("lstm_predictor_not_found", symbol=symbol)
        
        logger.info("news_signal_analyzer_initialized", symbols=self.symbols)
    
    def get_symbol_from_news(self, title: str, content: str) -> list:
        """
        Detect which crypto symbols are mentioned in news.
        
        Returns list of symbols found.
        """
        text = f"{title} {content}".lower()
        
        keywords = {
            'BTCUSDT': ['bitcoin', 'btc', 'satoshi'],
            'ETHUSDT': ['ethereum', 'eth', 'ether', 'vitalik'],
            'BNBUSDT': ['binance', 'bnb', 'binance coin'],
            'SOLUSDT': ['solana', 'sol'],
            'ADAUSDT': ['cardano', 'ada']
        }
        
        found_symbols = []
        for symbol, kws in keywords.items():
            if any(kw in text for kw in kws):
                found_symbols.append(symbol)
        
        return found_symbols
    
    def analyze_news_impact(self, news: NewsArticle) -> dict:
        """
        Analisa impact news terhadap trading decision.
        
        Returns dict with:
        - sentiment: positive/negative/neutral
        - score: sentiment score
        - urgency: high/medium/low
        - symbols: affected symbols
        - recommendation: BUY/HOLD/SELL
        """
        title = news.title or ""
        content = news.content or ""
        sentiment_score = news.sentiment_score or 0.0
        
        # Detect symbols
        symbols = self.get_symbol_from_news(title, content)
        if not symbols:
            symbols = ['BTCUSDT']  # Default to BTC
        
        # Determine sentiment label
        if sentiment_score > 0.5:
            sentiment = "positive"
            urgency = "high" if sentiment_score > 0.7 else "medium"
        elif sentiment_score < -0.5:
            sentiment = "negative"
            urgency = "high" if sentiment_score < -0.7 else "medium"
        else:
            sentiment = "neutral"
            urgency = "low"
        
        # Check for breaking news keywords
        breaking_keywords = [
            'breaking', 'urgent', 'alert', 'crash', 'surge', 'skyrocket',
            'plunge', 'rally', 'milestone', 'record', 'hack', 'regulation',
            'sec', 'etf', 'approved', 'rejected', 'ban'
        ]
        
        text_lower = f"{title} {content}".lower()
        if any(kw in text_lower for kw in breaking_keywords):
            urgency = "high"
        
        # Initial recommendation based on sentiment
        if sentiment_score > 0.6:
            recommendation = "BUY"
        elif sentiment_score < -0.6:
            recommendation = "SELL"
        else:
            recommendation = "HOLD"
        
        return {
            'sentiment': sentiment,
            'score': sentiment_score,
            'urgency': urgency,
            'symbols': symbols,
            'recommendation': recommendation,
            'title': title,
            'source': news.source,
            'published_at': news.published_at
        }
    
    def get_lstm_prediction(self, symbol: str) -> dict:
        """Get LSTM prediction for symbol if available."""
        if symbol not in self.predictors:
            return None
        
        try:
            # Fetch recent data
            session = get_session()
            since = datetime.utcnow() - timedelta(hours=6)
            
            klines = session.query(KlineData).filter(
                KlineData.symbol == symbol,
                KlineData.close_time >= since
            ).order_by(KlineData.close_time.asc()).all()
            
            session.close()
            
            if not klines or len(klines) < 60:
                return None
            
            # Create DataFrame
            df = pd.DataFrame([{
                'timestamp': k.close_time,
                'close_price': k.close_price,
                'volume': k.volume,
                'sentiment_score': 0.0  # Will be merged if available
            } for k in klines])
            
            # Make prediction
            predictor = self.predictors[symbol]
            prediction = predictor.predict_next(df)
            
            if 'error' not in prediction:
                return prediction
            
        except Exception as e:
            logger.error("lstm_prediction_failed", symbol=symbol, error=str(e))
        
        return None
    
    def combine_signals(self, news_analysis: dict, lstm_prediction: dict = None) -> dict:
        """
        Combine news sentiment with LSTM prediction for final recommendation.
        
        Logic:
        - Strong positive news + BUY signal → STRONG BUY
        - Strong positive news + SELL signal → HOLD (conflicting)
        - Strong negative news + SELL signal → STRONG SELL
        - Strong negative news + BUY signal → HOLD (conflicting)
        - Neutral news → Follow LSTM
        - No LSTM → Follow news only
        """
        news_sentiment = news_analysis['score']
        news_rec = news_analysis['recommendation']
        
        if lstm_prediction is None:
            # No LSTM, use news only
            return {
                'final_signal': news_rec,
                'confidence': abs(news_sentiment) * 100,
                'reason': 'Based on news sentiment only',
                'lstm_available': False
            }
        
        lstm_signal = lstm_prediction['signal']
        lstm_confidence = lstm_prediction['confidence']
        price_change = lstm_prediction['price_change_pct']
        
        # Combine logic
        if news_sentiment > 0.5 and lstm_signal == 'BUY':
            # Both bullish
            final_signal = 'STRONG BUY'
            confidence = min((abs(news_sentiment) + lstm_confidence) / 2 * 100, 95)
            reason = f"Positive news ({news_sentiment:+.2f}) + LSTM predicts +{price_change:.1f}%"
        
        elif news_sentiment < -0.5 and lstm_signal == 'SELL':
            # Both bearish
            final_signal = 'STRONG SELL'
            confidence = min((abs(news_sentiment) + lstm_confidence) / 2 * 100, 95)
            reason = f"Negative news ({news_sentiment:+.2f}) + LSTM predicts {price_change:.1f}%"
        
        elif abs(news_sentiment) > 0.5 and lstm_signal in ['BUY', 'SELL']:
            # Conflicting signals
            if news_rec != lstm_signal:
                final_signal = 'HOLD'
                confidence = 40
                reason = f"Conflicting: News says {news_rec}, LSTM says {lstm_signal}"
            else:
                final_signal = news_rec
                confidence = 60
                reason = f"Both agree on {news_rec} (moderate confidence)"
        
        else:
            # Follow LSTM if news is neutral
            final_signal = lstm_signal
            confidence = lstm_confidence * 100
            reason = f"News neutral, following LSTM ({lstm_signal})"
        
        return {
            'final_signal': final_signal,
            'confidence': confidence,
            'reason': reason,
            'lstm_available': True,
            'lstm_signal': lstm_signal,
            'lstm_confidence': lstm_confidence,
            'price_change_pct': price_change
        }
    
    def send_trading_alert(self, news_analysis: dict, combined_signal: dict, symbol: str):
        """Send comprehensive trading alert to Telegram."""
        
        if not _is_configured():
            logger.debug("telegram_not_configured")
            return
        
        # Signal emoji
        signal_emojis = {
            'STRONG BUY': '🟢🟢',
            'BUY': '🟢',
            'STRONG SELL': '🔴🔴',
            'SELL': '🔴',
            'HOLD': '🟡'
        }
        
        emoji = signal_emojis.get(combined_signal['final_signal'], '⚪')
        
        # Urgency indicator
        urgency = news_analysis['urgency'].upper()
        urgency_emoji = '🚨' if urgency == 'HIGH' else '⚠️' if urgency == 'MEDIUM' else 'ℹ️'
        
        # Build message
        text = (
            f"{emoji} <b>TRADING SIGNAL - {symbol}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"{urgency_emoji} <b>Urgency:</b> {urgency}\n"
            f"\n"
            f"📰 <b>News Alert</b>\n"
            f"<b>Source:</b> {news_analysis['source']}\n"
            f"<b>Title:</b> {news_analysis['title'][:120]}...\n"
            f"<b>Sentiment:</b> {news_analysis['sentiment'].title()} ({news_analysis['score']:+.2f})\n"
            f"\n"
            f"🎯 <b>RECOMMENDATION: {combined_signal['final_signal']}</b>\n"
            f"💪 <b>Confidence:</b> {combined_signal['confidence']:.0f}%\n"
            f"📝 <b>Reason:</b> {combined_signal['reason']}\n"
        )
        
        # Add LSTM details if available
        if combined_signal.get('lstm_available'):
            text += (
                f"\n"
                f"🤖 <b>LSTM Analysis</b>\n"
                f"Signal: {combined_signal['lstm_signal']}\n"
                f"Predicted Change: {combined_signal['price_change_pct']:+.2f}%\n"
                f"ML Confidence: {combined_signal['lstm_confidence']:.0%}\n"
            )
        
        text += (
            f"\n"
            f"🕐 <b>Time:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
            f"\n"
            f"💡 <i>Recommendation based on news + ML analysis</i>"
        )
        
        _send_message(text)
        logger.info(
            "trading_alert_sent",
            symbol=symbol,
            signal=combined_signal['final_signal'],
            confidence=combined_signal['confidence']
        )
    
    def check_new_news(self):
        """Check for new high-impact news and send alerts."""
        session = get_session()
        
        try:
            # Get latest news in last 5 minutes
            since = datetime.utcnow() - timedelta(minutes=5)
            
            query = session.query(NewsArticle).filter(
                NewsArticle.fetched_at >= since,
                NewsArticle.sentiment_score != None
            ).order_by(NewsArticle.fetched_at.desc())
            
            news_list = query.limit(10).all()
            
            for news in news_list:
                # Skip if already processed
                if news.id in self.last_checked_news_id:
                    continue
                
                self.last_checked_news_id[news.id] = True
                
                # Analyze news
                news_analysis = self.analyze_news_impact(news)
                
                # Only alert on high/medium urgency
                if news_analysis['urgency'] in ['high', 'medium']:
                    
                    # Process for each affected symbol
                    for symbol in news_analysis['symbols']:
                        if symbol not in self.symbols:
                            continue
                        
                        # Get LSTM prediction
                        lstm_pred = self.get_lstm_prediction(symbol)
                        
                        # Combine signals
                        combined = self.combine_signals(news_analysis, lstm_pred)
                        
                        # Send alert if confidence > 50%
                        if combined['confidence'] > 50:
                            self.send_trading_alert(news_analysis, combined, symbol)
                        
                        logger.info(
                            "news_analyzed",
                            symbol=symbol,
                            urgency=news_analysis['urgency'],
                            signal=combined['final_signal'],
                            confidence=combined['confidence']
                        )
        
        except Exception as e:
            logger.error("news_check_failed", error=str(e))
        finally:
            session.close()
    
    def run(self):
        """Run continuous news monitoring loop."""
        print(f"\n{'='*60}")
        print(f"  News-Based Trading Signal Analyzer")
        print(f"{'='*60}\n")
        print(f"Monitoring symbols: {', '.join(self.symbols)}")
        print(f"Check interval: {self.check_interval} seconds")
        print(f"Telegram alerts: {'Enabled' if _is_configured() else 'Disabled'}")
        print(f"\n🚀 Starting news monitoring...\n")
        
        check_count = 0
        
        try:
            while True:
                check_count += 1
                print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] Checking for new high-impact news... (check #{check_count})")
                
                self.check_new_news()
                
                # Clean old news IDs (keep last 1000)
                if len(self.last_checked_news_id) > 1000:
                    keys = list(self.last_checked_news_id.keys())
                    for key in keys[:500]:
                        del self.last_checked_news_id[key]
                
                time.sleep(self.check_interval)
        
        except KeyboardInterrupt:
            print(f"\n\n🛑 Monitoring stopped by user")
            print(f"   Total checks: {check_count}")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="News-based trading signal analyzer with Telegram alerts"
    )
    parser.add_argument(
        '--symbols',
        type=str,
        default='BTCUSDT,ETHUSDT,BNBUSDT',
        help='Comma-separated symbols to monitor (default: BTCUSDT,ETHUSDT,BNBUSDT)'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=60,
        help='Check interval in seconds (default: 60)'
    )
    
    args = parser.parse_args()
    
    symbols = [s.strip().upper() for s in args.symbols.split(',')]
    
    analyzer = NewsSignalAnalyzer(symbols=symbols, check_interval=args.interval)
    analyzer.run()


if __name__ == "__main__":
    main()
