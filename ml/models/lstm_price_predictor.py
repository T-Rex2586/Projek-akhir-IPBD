"""
Definisi kelas arsitektur jaringan saraf tiruan berulang (RNN) tipe LSTM yang dioptimalkan khusus untuk peramalan deret waktu.
"""
import os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import joblib
try:
    from tensorflow import keras
    from tensorflow.keras.models import Sequential, load_model
    from tensorflow.keras.layers import LSTM, Dense, Dropout
    from tensorflow.keras.callbacks import EarlyStopping
    TENSORFLOW_AVAILABLE = True
except ImportError:
    TENSORFLOW_AVAILABLE = False
    print('⚠️ TensorFlow not installed. LSTM predictor will be disabled.')
from sklearn.preprocessing import MinMaxScaler
from monitoring.logger import get_logger
logger = get_logger(__name__)
MODEL_DIR = 'ml/saved_models'
os.makedirs(MODEL_DIR, exist_ok=True)

class LSTMPricePredictor:

    def __init__(self, symbol: str='BTCUSDT', lookback_window: int=60, prediction_horizon: int=1):
        if not TENSORFLOW_AVAILABLE:
            raise ImportError('TensorFlow is required for LSTM predictor')
        self.symbol = symbol
        self.lookback_window = lookback_window
        self.prediction_horizon = prediction_horizon
        self.model = None
        self.scaler = MinMaxScaler(feature_range=(0, 1))
        self.is_trained = False
        self.model_path = os.path.join(MODEL_DIR, f'lstm_{symbol}.h5')
        self.scaler_path = os.path.join(MODEL_DIR, f'scaler_{symbol}.pkl')
        logger.info('lstm_predictor_initialized', symbol=symbol)

    def build_model(self, input_shape: Tuple[int, int]) -> Sequential:
        model = Sequential([LSTM(units=50, return_sequences=True, input_shape=input_shape), Dropout(0.2), LSTM(units=50, return_sequences=True), Dropout(0.2), LSTM(units=50, return_sequences=False), Dropout(0.2), Dense(units=25, activation='relu'), Dense(units=1)])
        model.compile(optimizer='adam', loss='mean_squared_error', metrics=['mae'])
        logger.info('lstm_model_built', layers=len(model.layers))
        return model

    def prepare_data(self, df: pd.DataFrame, train_split: float=0.8) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        required_cols = ['close_price', 'volume', 'sentiment_score']
        for col in required_cols:
            if col not in df.columns:
                df[col] = 0.0
        data = df[required_cols].values
        scaled_data = self.scaler.fit_transform(data)
        X, y = ([], [])
        for i in range(self.lookback_window, len(scaled_data) - self.prediction_horizon):
            X.append(scaled_data[i - self.lookback_window:i])
            y.append(scaled_data[i + self.prediction_horizon - 1, 0])
        X, y = (np.array(X), np.array(y))
        split_idx = int(len(X) * train_split)
        X_train, X_test = (X[:split_idx], X[split_idx:])
        y_train, y_test = (y[:split_idx], y[split_idx:])
        logger.info('lstm_data_prepared', train_samples=len(X_train), test_samples=len(X_test), features=data.shape[1])
        return (X_train, y_train, X_test, y_test)

    def train(self, df: pd.DataFrame, epochs: int=50, batch_size: int=32, validation_split: float=0.1) -> Dict:
        logger.info('lstm_training_started', symbol=self.symbol, epochs=epochs)
        X_train, y_train, X_test, y_test = self.prepare_data(df)
        input_shape = (X_train.shape[1], X_train.shape[2])
        self.model = self.build_model(input_shape)
        early_stop = EarlyStopping(monitor='val_loss', patience=5, restore_best_weights=True)
        history = self.model.fit(X_train, y_train, epochs=epochs, batch_size=batch_size, validation_split=validation_split, callbacks=[early_stop], verbose=1)
        test_loss, test_mae = self.model.evaluate(X_test, y_test, verbose=0)
        self.save_model()
        self.is_trained = True
        logger.info('lstm_training_completed', test_loss=round(test_loss, 6), test_mae=round(test_mae, 6))
        return {'test_loss': test_loss, 'test_mae': test_mae, 'epochs_completed': len(history.history['loss']), 'final_train_loss': history.history['loss'][-1], 'final_val_loss': history.history['val_loss'][-1]}

    def predict_next(self, recent_data: pd.DataFrame) -> Dict:
        if not self.is_trained and (not self.load_model()):
            logger.warning('lstm_model_not_trained', symbol=self.symbol)
            return {'predicted_price': None, 'signal': 'HOLD', 'confidence': 0.0, 'error': 'Model not trained'}
        required_cols = ['close_price', 'volume', 'sentiment_score']
        for col in required_cols:
            if col not in recent_data.columns:
                recent_data[col] = 0.0
        data = recent_data[required_cols].tail(self.lookback_window).values
        if len(data) < self.lookback_window:
            return {'predicted_price': None, 'signal': 'HOLD', 'confidence': 0.0, 'error': f'Insufficient data: need {self.lookback_window} rows'}
        scaled_data = self.scaler.transform(data)
        X = scaled_data.reshape(1, self.lookback_window, len(required_cols))
        predicted_scaled = self.model.predict(X, verbose=0)[0, 0]
        dummy = np.zeros((1, len(required_cols)))
        dummy[0, 0] = predicted_scaled
        predicted_price = self.scaler.inverse_transform(dummy)[0, 0]
        current_price = recent_data['close_price'].iloc[-1]
        signal, confidence = self._generate_signal(current_price, predicted_price)
        logger.info('lstm_prediction_made', symbol=self.symbol, current=round(current_price, 2), predicted=round(predicted_price, 2), signal=signal, confidence=round(confidence, 3))
        margin_of_error_pct = (1.0 - confidence) * 0.05
        lower_bound = predicted_price * (1.0 - margin_of_error_pct)
        upper_bound = predicted_price * (1.0 + margin_of_error_pct)
        return {'predicted_price': float(predicted_price), 'current_price': float(current_price), 'price_change_pct': float((predicted_price - current_price) / current_price * 100), 'signal': signal, 'confidence': float(confidence), 'lower_bound': float(lower_bound), 'upper_bound': float(upper_bound), 'timestamp': datetime.utcnow().isoformat()}

    def _generate_signal(self, current_price: float, predicted_price: float) -> Tuple[str, float]:
        price_change_pct = (predicted_price - current_price) / current_price * 100
        BUY_THRESHOLD = 2.0
        SELL_THRESHOLD = -2.0
        
        if price_change_pct > BUY_THRESHOLD:
            confidence = min(abs(price_change_pct) / 5.0, 1.0)
            return ('BUY', confidence)
        elif price_change_pct < SELL_THRESHOLD:
            confidence = min(abs(price_change_pct) / 5.0, 1.0)
            return ('SELL', confidence)
        else:
            # For HOLD, confidence is higher when price change is closer to 0
            # 0% change = 100% confidence, +/-2% change = 50% confidence
            hold_confidence = 1.0 - (abs(price_change_pct) / max(BUY_THRESHOLD, abs(SELL_THRESHOLD))) * 0.5
            return ('HOLD', hold_confidence)

    def save_model(self):
        if self.model:
            self.model.save(self.model_path)
            joblib.dump(self.scaler, self.scaler_path)
            logger.info('lstm_model_saved', path=self.model_path)

    def load_model(self) -> bool:
        try:
            if os.path.exists(self.model_path) and os.path.exists(self.scaler_path):
                self.model = load_model(self.model_path)
                self.scaler = joblib.load(self.scaler_path)
                self.is_trained = True
                logger.info('lstm_model_loaded', path=self.model_path)
                return True
        except Exception as e:
            logger.error('lstm_model_load_failed', error=str(e))
        return False

def predict_trading_signal(symbol: str, recent_data: pd.DataFrame) -> Dict:
    predictor = LSTMPricePredictor(symbol=symbol)
    if not predictor.load_model():
        logger.warning('lstm_no_pretrained_model', symbol=symbol)
        return {'signal': 'HOLD', 'confidence': 0.0, 'error': 'Model not trained yet. Run training first.'}
    return predictor.predict_next(recent_data)
if __name__ == '__main__':
    print('Testing LSTM Predictor...')
    if not TENSORFLOW_AVAILABLE:
        print('❌ TensorFlow not available')
        exit(1)
    np.random.seed(42)
    dates = pd.date_range(end=datetime.utcnow(), periods=200, freq='1h')
    dummy_data = pd.DataFrame({'timestamp': dates, 'close_price': np.cumsum(np.random.randn(200)) + 50000, 'volume': np.random.uniform(1000, 10000, 200), 'sentiment_score': np.random.uniform(-0.5, 0.5, 200)})
    print(f'Generated {len(dummy_data)} dummy data points')
    predictor = LSTMPricePredictor(symbol='BTCUSDT', lookback_window=30)
    print('\n🔧 Training model...')
    metrics = predictor.train(dummy_data, epochs=10, batch_size=16)
    print(f"✅ Training completed: MAE = {metrics['test_mae']:.2f}")
    print('\n🔮 Making prediction...')
    prediction = predictor.predict_next(dummy_data.tail(60))
    print(f'\n📊 Prediction Results:')
    print(f"  Current Price: ${prediction['current_price']:,.2f}")
    print(f"  Predicted Price: ${prediction['predicted_price']:,.2f}")
    print(f"  Change: {prediction['price_change_pct']:+.2f}%")
    print(f"  Signal: {prediction['signal']}")
    print(f"  Confidence: {prediction['confidence']:.2%}")
