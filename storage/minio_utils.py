"""
Modul Utilitas MinIO untuk pengelolaan Lapisan Perunggu (Bronze Layer).
Berperan sebagai Danau Data (Data Lake) sekunder yang memastikan
keseluruhan jejak muatan asli tersimpan dengan format hierarkis partisi.
"""
import os
import json
import uuid
import time
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Union
from minio import Minio
from dotenv import load_dotenv
from monitoring.logger import get_logger

load_dotenv()
logger = get_logger(__name__)

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadminpassword")
MINIO_SECURE = os.getenv("MINIO_SECURE", "False").lower() == "true"
BRONZE_BUCKET = os.getenv("MINIO_BRONZE_BUCKET", "bronze-crypto")

_client = None


def get_minio_client(max_retries: int = 3, retry_delay: float = 2.0) -> Minio:
    """Menginisialisasi klien koneksi MinIO dengan pola lazy-initialization dan penanganan repetitif."""
    global _client
    if _client is None:
        for attempt in range(1, max_retries + 1):
            try:
                _client = Minio(
                    MINIO_ENDPOINT,
                    access_key=MINIO_ACCESS_KEY,
                    secret_key=MINIO_SECRET_KEY,
                    secure=MINIO_SECURE,
                )
                logger.info("minio_client_initialized", endpoint=MINIO_ENDPOINT)

                if not _client.bucket_exists(BRONZE_BUCKET):
                    _client.make_bucket(BRONZE_BUCKET)
                    logger.info("minio_bucket_created", bucket=BRONZE_BUCKET)
                break
            except Exception as e:
                if attempt == max_retries:
                    logger.error("minio_client_initialization_failed", error=str(e))
                    raise e
                logger.warning("minio_connection_retry", attempt=attempt, max_retries=max_retries, error=str(e))
                time.sleep(retry_delay)
    return _client


def save_to_bronze(source: str, data: Union[Dict[str, Any], str, bytes], identifier: str = None) -> bool:
    """
    Mengarsipkan rekaman muatan kasar ke dalam partisi spesifik waktu pada Lapisan Perunggu.
    """
    try:
        client = get_minio_client()
        now = datetime.utcnow()

        year = now.strftime("%Y")
        month = now.strftime("%m")
        day = now.strftime("%d")
        timestamp_str = now.strftime("%Y%m%d_%H%M%S")
        
        if not identifier:
            identifier = str(uuid.uuid4())[:8]

        file_extension = "json"
        
        if isinstance(data, (dict, list)):
            content_bytes = json.dumps(data, default=str).encode("utf-8")
        elif isinstance(data, str):
            content_bytes = data.encode("utf-8")
            if data.strip().startswith("<"):
                file_extension = "xml"
        elif isinstance(data, (bytes, bytearray)):
            content_bytes = bytes(data)
            if content_bytes.lstrip()[:5] in (b"<?xml", b"<rss ", b"<feed", b"<html"):
                file_extension = "xml"
        else:
            content_bytes = str(data).encode("utf-8")

        object_name = f"bronze/{source}/year={year}/month={month}/day={day}/{timestamp_str}_{identifier}.{file_extension}"
        
        stream = BytesIO(content_bytes)
        client.put_object(
            BRONZE_BUCKET,
            object_name,
            stream,
            length=len(content_bytes),
            content_type="application/json" if file_extension == "json" else "application/xml"
        )
        
        logger.info("saved_to_bronze_layer", bucket=BRONZE_BUCKET, path=object_name, size_bytes=len(content_bytes))
        return True
        
    except Exception as e:
        logger.error("save_to_bronze_layer_failed", source=source, error=str(e))
        return False


def list_bronze_objects(prefix: str = "bronze/", max_results: int = 100) -> List[Dict]:
    """Menyajikan rincian agregat terhadap objek biner yang bermukim di dalam kontainer Lapisan Perunggu."""
    try:
        client = get_minio_client()
        objects = client.list_objects(BRONZE_BUCKET, prefix=prefix, recursive=True)

        results = []
        for obj in objects:
            results.append({
                "name": obj.object_name,
                "size_bytes": obj.size,
                "last_modified": obj.last_modified.isoformat() if obj.last_modified else None,
            })
            if len(results) >= max_results:
                break

        logger.info("bronze_objects_listed", prefix=prefix, count=len(results))
        return results

    except Exception as e:
        logger.error("list_bronze_objects_failed", error=str(e))
        return []
