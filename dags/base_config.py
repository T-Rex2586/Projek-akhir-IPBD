"""
Konfigurasi dasar (Base Configuration) untuk integrasi DAG Apache Airflow.
Memuat pengaturan bawaan seperti interval pengulangan, penundaan eksekusi,
serta metrik notifikasi peringatan.
"""
from datetime import timedelta
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from monitoring.telegram_alert import send_airflow_failure_alert

GLOBAL_DEFAULT_ARGS = {
    "owner": "crypto-pipeline",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "on_failure_callback": send_airflow_failure_alert,
}
