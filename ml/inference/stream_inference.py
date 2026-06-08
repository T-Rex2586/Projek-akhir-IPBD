"""
Stream Inference — Real-time anomaly prediction for the streaming pipeline.

Loads the trained Isolation Forest model and provides a lightweight
`predict_single()` interface for the stream processor.
Auto-reloads the model when the file changes (e.g. after retraining).
"""
import os
import sys
import time

import numpy as np
import joblib

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from monitoring.logger import get_logger

logger = get_logger(__name__)

MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "anomaly_detector.joblib")


class StreamAnomalyInference:
    """
    Real-time inference engine for price anomaly detection.

    Loads the model once and caches it. Checks for model file changes
    periodically to hot-reload after retraining.
    """

    def __init__(self):
        self._model = None
        self._model_mtime = 0
        self._last_check_time = 0
        self._check_interval = 60  # seconds between file-change checks

        self._load_model()

    def _load_model(self):
        """Load (or reload) the model from disk."""
        if not os.path.exists(MODEL_PATH):
            logger.info("stream_inference_model_not_found", 
                       path=MODEL_PATH,
                       message="Anomaly detection will use rule-based only. To train: python ml/training/train_anomaly_model.py")
            self._model = None
            return False

        try:
            self._model = joblib.load(MODEL_PATH)
            self._model_mtime = os.path.getmtime(MODEL_PATH)
            logger.info("stream_inference_model_loaded",
                         path=MODEL_PATH,
                         mtime=time.ctime(self._model_mtime))
            return True
        except Exception as e:
            logger.error("stream_inference_model_load_failed", error=str(e))
            self._model = None
            return False

    def _maybe_reload(self):
        """Check if the model file has been updated and reload if so."""
        now = time.time()
        if now - self._last_check_time < self._check_interval:
            return
        self._last_check_time = now

        if not os.path.exists(MODEL_PATH):
            return

        current_mtime = os.path.getmtime(MODEL_PATH)
        if current_mtime > self._model_mtime:
            logger.info("stream_inference_model_file_changed_reloading")
            self._load_model()

    def is_ready(self) -> bool:
        """Check if the model is loaded and ready."""
        return self._model is not None

    def predict_single(self, data: dict) -> bool:
        """
        Predict whether a single data point is an anomaly.

        Parameters
        ----------
        data : dict
            Must contain 'price' and 'volume'. Optionally 'price_change',
            'volume_change', 'price_volatility'.

        Returns
        -------
        bool
            True if the data point is predicted as an anomaly.
        """
        self._maybe_reload()

        if self._model is None:
            return False

        try:
            features = np.array([[
                float(data.get("price", 0)),
                float(data.get("volume", 0)),
                float(data.get("price_change", 0)),
                float(data.get("volume_change", 0)),
                float(data.get("price_volatility", 0)),
            ]])

            prediction = self._model.predict(features)
            return int(prediction[0]) == -1  # -1 = anomaly

        except Exception as e:
            logger.debug("stream_inference_predict_failed", error=str(e))
            return False

    def predict_batch(self, data_list: list) -> list:
        """
        Predict anomalies for a batch of data points.

        Returns a list of booleans (True = anomaly).
        """
        self._maybe_reload()

        if self._model is None:
            return [False] * len(data_list)

        try:
            features = np.array([
                [
                    float(d.get("price", 0)),
                    float(d.get("volume", 0)),
                    float(d.get("price_change", 0)),
                    float(d.get("volume_change", 0)),
                    float(d.get("price_volatility", 0)),
                ]
                for d in data_list
            ])

            predictions = self._model.predict(features)
            return [int(p) == -1 for p in predictions]

        except Exception as e:
            logger.debug("stream_inference_batch_predict_failed", error=str(e))
            return [False] * len(data_list)


if __name__ == "__main__":
    engine = StreamAnomalyInference()

    if engine.is_ready():
        # Test with sample data
        test_data = {"price": 43000.0, "volume": 1500.0, "price_change": 0.02}
        result = engine.predict_single(test_data)
        print(f"Test data: {test_data}")
        print(f"Is anomaly: {result}")
    else:
        print("Model not available. Run ml/training/train_anomaly_model.py first.")
