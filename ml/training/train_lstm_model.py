"""
Train LSTM price prediction model using historical data from database.

Usage:
    python ml/training/train_lstm_model.py --symbol BTCUSDT --days 30 --epochs 50
"""
import sys
import os
import argparse
from datetime import datetime, timedelta
import pandas as pd

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from storage.db_models import get_session, KlineData, NewsArticle
from ml.models.lstm_price_predictor import LSTMPricePredictor
from monitoring.logger import get_logger

logger = get_logger(__name__)


def fetch_training_data(symbol: str, days: int = 30) -> pd.DataFrame:
    """
    Fetch historical data from database for training.
    
    Parameters
    ----------
    symbol : str
        Crypto symbol (e.g., BTCUSDT)
    days : int
        Number of days of historical data
    
    Returns
    -------
    pd.DataFrame
        Combined price and sentiment data
    """
    logger.info("fetching_training_data", symbol=symbol, days=days)
    
    session = get_session()
    try:
        since = datetime.utcnow() - timedelta(days=days)
        
        # Fetch kline data (price + volume)
        klines = session.query(KlineData).filter(
            KlineData.symbol == symbol,
            KlineData.close_time >= since
        ).order_by(KlineData.close_time.asc()).all()
        
        if not klines:
            logger.error("no_kline_data_found", symbol=symbol)
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame([{
            'timestamp': k.close_time,
            'open_price': k.open_price,
            'high_price': k.high_price,
            'low_price': k.low_price,
            'close_price': k.close_price,
            'volume': k.volume,
        } for k in klines])
        
        # Fetch sentiment data (averaged by hour)
        df['hour'] = pd.to_datetime(df['timestamp']).dt.floor('h')  # lowercase 'h'
        
        # Get sentiment scores for relevant news
        keywords = {
            'BTCUSDT': ['bitcoin', 'btc'],
            'ETHUSDT': ['ethereum', 'eth'],
            'BNBUSDT': ['binance', 'bnb'],
            'SOLUSDT': ['solana', 'sol'],
            'ADAUSDT': ['cardano', 'ada']
        }
        
        kws = keywords.get(symbol.upper(), [symbol[:3].lower()])
        
        # Build sentiment query
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
            # Merge sentiment with price data
            df = df.merge(
                sentiment_df,
                left_on='hour',
                right_on='hour',
                how='left'
            )
            df['sentiment_score'] = df['avg_sentiment'].fillna(0.0)
        else:
            df['sentiment_score'] = 0.0
        
        # Drop helper column
        df = df.drop(columns=['hour', 'avg_sentiment'], errors='ignore')
        
        logger.info("training_data_fetched", rows=len(df), features=len(df.columns))
        
        return df
    
    except Exception as e:
        logger.error("training_data_fetch_failed", error=str(e))
        return pd.DataFrame()
    finally:
        session.close()


def train_lstm_model(
    symbol: str,
    days: int = 30,
    epochs: int = 50,
    batch_size: int = 32,
    lookback_window: int = 60
):
    """
    Train LSTM model for a specific symbol.
    
    Parameters
    ----------
    symbol : str
        Crypto symbol (e.g., BTCUSDT)
    days : int
        Days of historical data to use
    epochs : int
        Training epochs
    batch_size : int
        Batch size
    lookback_window : int
        Lookback window size
    """
    print(f"\n{'='*60}")
    print(f"  LSTM Model Training - {symbol}")
    print(f"{'='*60}\n")
    
    # Fetch data
    print("📊 Fetching training data from database...")
    df = fetch_training_data(symbol, days)
    
    if df.empty:
        print(f"❌ No data available for {symbol}")
        print("   Run the pipeline first to collect data:")
        print("   python ingestion/binance_websocket.py")
        return
    
    print(f"✅ Fetched {len(df)} records ({days} days)")
    print(f"   Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    
    # Check minimum data requirement
    min_required = lookback_window + 100  # Need enough for train/test split
    if len(df) < min_required:
        print(f"⚠️  Warning: Only {len(df)} records available")
        print(f"   Minimum recommended: {min_required} records")
        response = input("   Continue anyway? (y/n): ")
        if response.lower() != 'y':
            print("❌ Training cancelled")
            return
    
    # Initialize predictor
    print(f"\n🔧 Initializing LSTM predictor...")
    print(f"   Lookback window: {lookback_window}")
    print(f"   Epochs: {epochs}")
    print(f"   Batch size: {batch_size}")
    
    predictor = LSTMPricePredictor(
        symbol=symbol,
        lookback_window=lookback_window
    )
    
    # Train model
    print(f"\n🚀 Training started...")
    print(f"   This may take several minutes...\n")
    
    try:
        metrics = predictor.train(
            df,
            epochs=epochs,
            batch_size=batch_size,
            validation_split=0.1
        )
        
        print(f"\n{'='*60}")
        print(f"  ✅ Training Completed!")
        print(f"{'='*60}")
        print(f"  Test Loss (MSE): {metrics['test_loss']:.6f}")
        print(f"  Test MAE: {metrics['test_mae']:.2f}")
        print(f"  Epochs: {metrics['epochs_completed']}")
        print(f"  Final Train Loss: {metrics['final_train_loss']:.6f}")
        print(f"  Final Val Loss: {metrics['final_val_loss']:.6f}")
        print(f"{'='*60}\n")
        
        # Test prediction
        print("🔮 Testing prediction on recent data...")
        prediction = predictor.predict_next(df.tail(lookback_window + 10))
        
        if 'error' not in prediction:
            print(f"\n📊 Sample Prediction:")
            print(f"   Current Price: ${prediction['current_price']:,.2f}")
            print(f"   Predicted Price: ${prediction['predicted_price']:,.2f}")
            print(f"   Expected Change: {prediction['price_change_pct']:+.2f}%")
            print(f"   Signal: {prediction['signal']}")
            print(f"   Confidence: {prediction['confidence']:.2%}")
        
        print(f"\n💾 Model saved to: ml/saved_models/lstm_{symbol}.h5")
        print(f"   Ready for predictions!\n")
        
    except Exception as e:
        print(f"\n❌ Training failed: {str(e)}")
        logger.error("lstm_training_failed", symbol=symbol, error=str(e))


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Train LSTM price prediction model"
    )
    parser.add_argument(
        '--symbol',
        type=str,
        default='BTCUSDT',
        help='Crypto symbol (default: BTCUSDT)'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=30,
        help='Days of historical data (default: 30)'
    )
    parser.add_argument(
        '--epochs',
        type=int,
        default=50,
        help='Training epochs (default: 50)'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=32,
        help='Batch size (default: 32)'
    )
    parser.add_argument(
        '--lookback',
        type=int,
        default=60,
        help='Lookback window (default: 60)'
    )
    
    args = parser.parse_args()
    
    # Train model
    train_lstm_model(
        symbol=args.symbol,
        days=args.days,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lookback_window=args.lookback
    )


if __name__ == "__main__":
    main()
