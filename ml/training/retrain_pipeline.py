"""
Alur otomasi pelatihan ulang (retraining pipeline) yang melakukan pemutakhiran bobot model secara periodik berdasarkan evaluasi distribusi data baru.
"""
import os
import sys
import shutil
from datetime import datetime
import joblib
import numpy as np
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from monitoring.logger import get_logger
from ml.training.train_anomaly_model import train_model, fetch_training_data, engineer_features, MODEL_PATH, METADATA_PATH, MODEL_DIR
from dotenv import load_dotenv
load_dotenv()
logger = get_logger(__name__)
MIN_NEW_RECORDS = 100
BACKUP_MODEL_PATH = os.path.join(MODEL_DIR, 'anomaly_detector_prev.joblib')

def should_retrain() -> bool:
    if not os.path.exists(METADATA_PATH):
        logger.info('no_existing_model_retrain_required')
        return True
    try:
        meta = joblib.load(METADATA_PATH)
        trained_at = datetime.fromisoformat(meta.get('trained_at', '2000-01-01'))
        last_training_samples = meta.get('training_samples', 0)
        df = fetch_training_data(hours=168)
        current_samples = len(df)
        new_samples = current_samples - last_training_samples
        hours_since_training = (datetime.utcnow() - trained_at).total_seconds() / 3600
        logger.info('retrain_check', last_trained=trained_at.isoformat(), hours_since=round(hours_since_training, 1), new_samples=new_samples)
        if new_samples >= MIN_NEW_RECORDS or hours_since_training >= 168:
            return True
        logger.info('retrain_not_needed')
        return False
    except Exception as e:
        logger.warning('retrain_check_failed_defaulting_to_retrain', error=str(e))
        return True

def compare_models(new_model_path: str, old_model_path: str) -> dict:
    if not os.path.exists(old_model_path):
        return {'winner': 'new', 'reason': 'no_previous_model'}
    try:
        old_model = joblib.load(old_model_path)
        new_model = joblib.load(new_model_path)
        df = fetch_training_data(hours=24)
        if df.empty or len(df) < 10:
            return {'winner': 'new', 'reason': 'insufficient_eval_data'}
        features = engineer_features(df)
        old_preds = old_model.predict(features)
        new_preds = new_model.predict(features)
        old_scores = old_model.decision_function(features)
        new_scores = new_model.decision_function(features)
        old_mean_score = float(np.mean(old_scores))
        new_mean_score = float(np.mean(new_scores))
        old_anomalies = int((old_preds == -1).sum())
        new_anomalies = int((new_preds == -1).sum())
        comparison = {'old_mean_score': round(old_mean_score, 4), 'new_mean_score': round(new_mean_score, 4), 'old_anomalies': old_anomalies, 'new_anomalies': new_anomalies, 'eval_samples': len(features), 'winner': 'new' if new_mean_score >= old_mean_score else 'old'}
        logger.info('model_comparison_completed', **comparison)
        return comparison
    except Exception as e:
        logger.warning('model_comparison_failed', error=str(e))
        return {'winner': 'new', 'reason': f'comparison_error: {e}'}

def run_retrain_pipeline() -> dict:
    logger.info('retrain_pipeline_started')
    if not should_retrain():
        return {'status': 'skipped', 'reason': 'retraining_not_needed'}
    if os.path.exists(MODEL_PATH):
        shutil.copy2(MODEL_PATH, BACKUP_MODEL_PATH)
        logger.info('existing_model_backed_up', path=BACKUP_MODEL_PATH)
    training_result = train_model(contamination=0.05, hours=168)
    if training_result.get('status') != 'completed':
        return {'status': 'failed', 'training': training_result}
    comparison = compare_models(MODEL_PATH, BACKUP_MODEL_PATH)
    if comparison['winner'] == 'new':
        logger.info('new_model_accepted')
        if os.path.exists(BACKUP_MODEL_PATH):
            os.remove(BACKUP_MODEL_PATH)
    else:
        logger.info('old_model_retained_rolling_back')
        if os.path.exists(BACKUP_MODEL_PATH):
            shutil.copy2(BACKUP_MODEL_PATH, MODEL_PATH)
            os.remove(BACKUP_MODEL_PATH)
    result = {'status': 'completed', 'training': training_result, 'comparison': comparison, 'deployed_model': comparison['winner']}
    logger.info('retrain_pipeline_completed', **result)
    return result
if __name__ == '__main__':
    from storage.db_models import init_db
    init_db()
    result = run_retrain_pipeline()
    print(f'\nRetrain result: {result}')
