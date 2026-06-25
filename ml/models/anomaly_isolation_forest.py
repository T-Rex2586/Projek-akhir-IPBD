"""
Implementasi konstruksi algoritma Isolation Forest guna mengidentifikasi titik data pencilan (outlier) dalam struktur fitur multidimensi.
"""
from sklearn.ensemble import IsolationForest
import numpy as np
import pandas as pd
from typing import List, Dict
import joblib
import os

class PriceAnomalyDetector:

    def __init__(self, contamination: float=0.05):
        self.model = IsolationForest(contamination=contamination, random_state=42, n_estimators=100)
        self.is_trained = False

    def prepare_features(self, price_data: List[Dict]) -> np.ndarray:
        df = pd.DataFrame(price_data)
        df = df.sort_values('timestamp')
        df['price_change'] = df['price'].pct_change()
        df['volume_change'] = df['volume'].pct_change()
        df = df.fillna(0)
        features = df[['price', 'volume', 'price_change', 'volume_change']].values
        return features

    def train(self, price_data: List[Dict]):
        features = self.prepare_features(price_data)
        self.model.fit(features)
        self.is_trained = True
        print(f'Model trained on {len(features)} samples')

    def predict(self, price_data: List[Dict]) -> List[int]:
        if not self.is_trained:
            raise ValueError('Model must be trained before prediction')
        features = self.prepare_features(price_data)
        predictions = self.model.predict(features)
        return predictions.tolist()

    def save_model(self, filepath: str='ml/models/anomaly_detector.joblib'):
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        joblib.dump(self.model, filepath)
        print(f'Model saved to {filepath}')

    def load_model(self, filepath: str='ml/models/anomaly_detector.joblib'):
        self.model = joblib.load(filepath)
        self.is_trained = True
        print(f'Model loaded from {filepath}')
if __name__ == '__main__':
    from storage.db_utils import get_recent_prices
    prices = get_recent_prices('BTCUSDT', hours=168)
    if len(prices) > 100:
        detector = PriceAnomalyDetector()
        detector.train(prices)
        recent = prices[:50]
        predictions = detector.predict(recent)
        for i, pred in enumerate(predictions):
            if pred == -1:
                print(f"Anomaly detected at {recent[i]['timestamp']}: ${recent[i]['price']}")
        detector.save_model()
    else:
        print('Not enough data for training')
