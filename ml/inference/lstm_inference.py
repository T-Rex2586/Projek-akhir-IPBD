"""
Real-time LSTM inference for trading signal generation.

Usage:
    python ml/inference/lstm_inference.py --symbol BTCUSDT --interval 300
"""
import sys
import os
import argparse
import time
from datetime import datetime, timedelta
import pandas as pd

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from storage.db_models import get_session, KlineData, NewsArticle
from storage.db_utils import save_anomaly_event
from ml.models.lstm_price_predictor import LSTMPricePredictor
from monitoring.logger import get_logger
from monitoring.telegram_alert import send_startup_notification

logger = get_logger(__name__)


def fetch_recent_data(symbol: str, hours: int = 6) -> pd.DataFrame:
    """
    Fetch recent data for prediction.
    
    Parameters
    ----------
    symbol : str
        Crypto symbol
    hours : int
        Hours of recent data to fetch
    
    Returns
    -------
    pd.DataFrame
        Recent price and sentiment data
    """
    session = get_session()
    try:
        since = datetime.utcnow() - timedelta(hours=hours)
        
        # Fetch kline data
        klines = session.query(KlineData).filter(
            KlineData.symbol == symbol,
            KlineData.close_time >= since
        ).order_by(KlineData.close_time.asc()).all()
        
        if not klines:
            logger.warning("no_recent_kline_data", symbol=symbol)
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame([{
            'timestamp': k.close_time,
            'close_price': k.close_price,
            'volume': k.volume,
        } for k in klines])
        
        # Add sentiment (hourly average)
        df['hour'] = pd.to_datetime(df['timestamp']).dt.floor('h')  # lowercase 'h'
        
        keywords = {
            'BTCUSDT': ['bitcoin', 'btc'],
            'ETHUSDT': ['ethereum', 'eth'],
            'BNBUSDT': ['binance', 'bnb'],
            'SOLUSDT': ['solana', 'sol'],
            'ADAUSDT': ['cardano', 'ada']
        }
        
        kws = keywords.get(symbol.upper(), [symbol[:3].lower()])
        
        from sqlalchemy import or_, func
        sentiment_query = session.query(
            func.date_trunc('hour', NewsArticle.published_at).label('hour'),
            func.avg(NewsArticle.sentiment_score).label('avg_sentiment')
        ).filter(
            NewsArticle.published_at >= since,
            or_(*[NewsArticle.title.ilike(f'%{kw}%') for kw in kws])
        ).group_by(
            func.date_trunc('hour', NewsArticle.published_at)
        )
        
        sentiment_df = pd.read_sql(sentiment_query.statement, session.bind)
        
        if not sentiment_df.empty:
            df = df.merge(sentiment_df, left_on='hour', right_on='hour', how='left')
            df['sentiment_score'] = df['avg_sentiment'].fillna(0.0)
        else:
            df['sentiment_score'] = 0.0
        
        df = df.drop(columns=['hour', 'avg_sentiment'], errors='ignore')
        
        return df
    
    except Exception as e:
        logger.error("recent_data_fetch_failed", error=str(e))
        return pd.DataFrame()
    finally:
        session.close()


def run_inference_loop(
    symbol: str,
    interval: int = 300,  # 5 minutes
    alert_on_signal: bool = True
):
    """
    Run continuous LSTM inference loop.
    
    Parameters
    ----------
    symbol : str
        Crypto symbol
    interval : int
        Seconds between predictions
    alert_on_signal : bool
        Send alerts for BUY/SELL signals
    """
    print(f"\n{'='*60}")
    print(f"  LSTM Real-Time Inference - {symbol}")
    print(f"{'='*60}\n")
    
    # Initialize predictor
    predictor = LSTMPricePredictor(symbol=symbol, lookback_window=60)
    
    # Load model
    if not predictor.load_model():
        print(f"❌ No trained model found for {symbol}")
        print(f"   Train model first:")
        print(f"   python ml/training/train_lstm_model.py --symbol {symbol}")
        return
    
    print(f"✅ Model loaded successfully")
    print(f"⏱️  Prediction interval: {interval} seconds")
    print(f"📡 Alert on signals: {'Yes' if alert_on_signal else 'No'}")
    print(f"\n🚀 Starting inference loop...\n")
    
    # Send startup notification
    if alert_on_signal:
        send_startup_notification()
    
    last_signal = None
    prediction_count = 0
    
    try:
        while True:
            try:
                # Fetch recent data
                df = fetch_recent_data(symbol, hours=6)
                
                if df.empty or len(df) < predictor.lookback_window:
                    logger.warning("insufficient_data_for_prediction", symbol=symbol)
                    print(f"⚠️  [{datetime.utcnow().strftime('%H:%M:%S')}] Insufficient data, waiting...")
                    time.sleep(interval)
                    continue
                
                # Make prediction
                prediction = predictor.predict_next(df)
                
                if 'error' in prediction:
                    logger.error("prediction_failed", error=prediction['error'])
                    time.sleep(interval)
                    continue
                
                prediction_count += 1
                
                # Display prediction
                current_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                signal_emoji = {
                    'BUY': '🟢',
                    'SELL': '🔴',
                    'HOLD': '🟡'
                }.get(prediction['signal'], '⚪')
                
                print(f"{signal_emoji} [{current_time}] {symbol}")
                print(f"   Current: ${prediction['current_price']:,.2f}")
                print(f"   Predicted: ${prediction['predicted_price']:,.2f} ({prediction['price_change_pct']:+.2f}%)")
                print(f"   Signal: {prediction['signal']} (confidence: {prediction['confidence']:.2%})")
                print(f"   Total predictions: {prediction_count}\n")
                
                # Send alert if signal changed to BUY or SELL
                if alert_on_signal and prediction['signal'] != last_signal:
                    if prediction['signal'] in ['BUY', 'SELL'] and prediction['confidence'] > 0.5:
                        from monitoring.telegram_alert import send_prediction_alert
                        send_prediction_alert(
                            symbol=symbol,
                            current_price=prediction['current_price'],
                            predicted_price=prediction['predicted_price'],
                            signal=prediction['signal'],
                            confidence=prediction['confidence']
                        )
                        
                        # Save as anomaly event (for tracking)
                        save_anomaly_event({
                            'event_type': f'lstm_{prediction["signal"].lower()}_signal',
                            'symbol': symbol,
                            'description': (
                                f"LSTM prediction: {prediction['signal']} signal "
                                f"(predicted change: {prediction['price_change_pct']:+.2f}%)"
                            ),
                            'severity': 'medium' if prediction['confidence'] < 0.7 else 'high',
                            'value': prediction['predicted_price'],
                            'threshold': prediction['current_price']
                        }, send_alert=False)
                        
                        logger.info(
                            "trading_signal_generated",
                            symbol=symbol,
                            signal=prediction['signal'],
                            confidence=prediction['confidence']
                        )
                
                last_signal = prediction['signal']
                
                # Wait for next prediction
                time.sleep(interval)
            
            except KeyboardInterrupt:
                raise
            except Exception as e:
                logger.error("inference_loop_error", error=str(e))
                print(f"❌ Error: {str(e)}")
                time.sleep(interval)
    
    except KeyboardInterrupt:
        print(f"\n\n🛑 Inference stopped by user")
        print(f"   Total predictions made: {prediction_count}")


def predict_once(symbol: str):
    """
    Make a single prediction for a symbol.
    
    Parameters
    ----------
    symbol : str
        Crypto symbol
    """
    print(f"\n🔮 Making prediction for {symbol}...\n")
    
    # Initialize predictor
    predictor = LSTMPricePredictor(symbol=symbol)
    
    # Load model
    if not predictor.load_model():
        print(f"❌ No trained model found for {symbol}")
        return
    
    # Fetch data
    df = fetch_recent_data(symbol, hours=6)
    
    if df.empty or len(df) < predictor.lookback_window:
        print(f"❌ Insufficient data for prediction")
        print(f"   Need at least {predictor.lookback_window} records")
        return
    
    # Predict
    prediction = predictor.predict_next(df)
    
    if 'error' in prediction:
        print(f"❌ Prediction failed: {prediction['error']}")
        return
    
    # Display result
    signal_emoji = {
        'BUY': '🟢',
        'SELL': '🔴',
        'HOLD': '🟡'
    }.get(prediction['signal'], '⚪')
    
    print(f"{'='*60}")
    print(f"  {signal_emoji} LSTM Trading Signal - {symbol}")
    print(f"{'='*60}")
    print(f"  Current Price: ${prediction['current_price']:,.2f}")
    print(f"  Predicted Price: ${prediction['predicted_price']:,.2f}")
    print(f"  Expected Change: {prediction['price_change_pct']:+.2f}%")
    print(f"  ")
    print(f"  📊 Signal: {prediction['signal']}")
    print(f"  🎯 Confidence: {prediction['confidence']:.2%}")
    print(f"  🕐 Time: {prediction['timestamp']}")
    print(f"{'='*60}\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="LSTM inference for trading signals"
    )
    parser.add_argument(
        '--symbol',
        type=str,
        default='BTCUSDT',
        help='Crypto symbol (default: BTCUSDT)'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=300,
        help='Prediction interval in seconds (default: 300)'
    )
    parser.add_argument(
        '--once',
        action='store_true',
        help='Make single prediction and exit'
    )
    parser.add_argument(
        '--no-alerts',
        action='store_true',
        help='Disable Telegram alerts'
    )
    
    args = parser.parse_args()
    
    if args.once:
        predict_once(args.symbol)
    else:
        run_inference_loop(
            symbol=args.symbol,
            interval=args.interval,
            alert_on_signal=not args.no_alerts
        )


if __name__ == "__main__":
    main()
