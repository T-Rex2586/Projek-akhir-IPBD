"""
Isolation Forest for anomaly detection in price data.
"""
from sklearn.ensemble import IsolationForest
import numpy as np
import pandas as pd
from typing import List, Dict
import joblib
import os

class PriceAnomalyDetector:
    """Anomaly detector for cryptocurrency prices."""
    
    def __init__(self, contamination: float = 0.05):
        """
        Initialize anomaly detector.
        
        Args:
            contamination: Expected proportion of outliers (default 5%)
        """
        self.model = IsolationForest(
            contamination=contamination,
            random_state=42,
            n_estimators=100
        )
        self.is_trained = False
    
    def prepare_features(self, price_data: List[Dict]) -> np.ndarray:
        """
        Prepare features from price data.
        
        Features:
        - price
        - volume
        - price_change (%)
        - volume_change (%)
        """
        df = pd.DataFrame(price_data)
        df = df.sort_values('timestamp')
        
        # Calculate changes
        df['price_change'] = df['price'].pct_change()
        df['volume_change'] = df['volume'].pct_change()
        
        # Fill NaN values
        df = df.fillna(0)
        
        # Select features
        features = df[['price', 'volume', 'price_change', 'volume_change']].values
        
        return features
    
    def train(self, price_data: List[Dict]):
        """Train the anomaly detection model."""
        features = self.prepare_features(price_data)
        self.model.fit(features)
        self.is_trained = True
        print(f"Model trained on {len(features)} samples")
    
    def predict(self, price_data: List[Dict]) -> List[int]:
        """
        Predict anomalies.
        
        Returns:
            List of predictions: 1 for normal, -1 for anomaly
        """
        if not self.is_trained:
            raise ValueError("Model must be trained before prediction")
        
        features = self.prepare_features(price_data)
        predictions = self.model.predict(features)
        
        return predictions.tolist()
    
    def save_model(self, filepath: str = "ml/models/anomaly_detector.joblib"):
        """Save trained model to disk."""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        joblib.dump(self.model, filepath)
        print(f"Model saved to {filepath}")
    
    def load_model(self, filepath: str = "ml/models/anomaly_detector.joblib"):
        """Load trained model from disk."""
        self.model = joblib.load(filepath)
        self.is_trained = True
        print(f"Model loaded from {filepath}")

if __name__ == "__main__":
    # Example usage
    from storage.db_utils import get_recent_prices
    
    # Get historical data
    prices = get_recent_prices("BTCUSDT", hours=168)  # 1 week
    
    if len(prices) > 100:
        # Train model
        detector = PriceAnomalyDetector()
        detector.train(prices)
        
        # Predict on recent data
        recent = prices[:50]
        predictions = detector.predict(recent)
        
        # Show anomalies
        for i, pred in enumerate(predictions):
            if pred == -1:
                print(f"Anomaly detected at {recent[i]['timestamp']}: ${recent[i]['price']}")
        
        # Save model
        detector.save_model()
    else:
        print("Not enough data for training")
