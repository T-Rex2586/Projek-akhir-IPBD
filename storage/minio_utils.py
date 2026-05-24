"""
MinIO utilities for Bronze Layer (Raw Data Lake) storage.

Handles connection to MinIO and raw data persistence.
Organizes data under a partition-friendly layout:
bronze/{source}/year={YYYY}/month={MM}/day={DD}/{timestamp}_{unique_id}.json
"""
import os
import json
import uuid
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, Union
from minio import Minio
from dotenv import load_dotenv
from monitoring.logger import get_logger

load_dotenv()
logger = get_logger(__name__)

# Load configurations
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadminpassword")
MINIO_SECURE = os.getenv("MINIO_SECURE", "False").lower() == "true"
BRONZE_BUCKET = os.getenv("MINIO_BRONZE_BUCKET", "bronze-crypto")

_client = None


def get_minio_client() -> Minio:
    """Lazy initialize and return the MinIO client."""
    global _client
    if _client is None:
        try:
            _client = Minio(
                MINIO_ENDPOINT,
                access_key=MINIO_ACCESS_KEY,
                secret_key=MINIO_SECRET_KEY,
                secure=MINIO_SECURE,
            )
            logger.info("minio_client_initialized", endpoint=MINIO_ENDPOINT)
            
            # Ensure the bronze bucket exists
            if not _client.bucket_exists(BRONZE_BUCKET):
                _client.make_bucket(BRONZE_BUCKET)
                logger.info("minio_bucket_created", bucket=BRONZE_BUCKET)
        except Exception as e:
            logger.error("minio_client_initialization_failed", error=str(e))
            raise e
    return _client


def save_to_bronze(source: str, data: Union[Dict[str, Any], str, bytes], identifier: str = None) -> bool:
    """
    Save raw unprocessed data to the MinIO Bronze bucket.

    Parameters
    ----------
    source : str
        The source identifier (e.g. 'binance_websocket', 'binance_rest', 'reddit_scraper', 'rss_feed')
    data : dict or str or bytes
        The raw unprocessed data (payload / response)
    identifier : str, optional
        A unique identifier or filename suffix. If None, a UUID will be generated.
    """
    try:
        client = get_minio_client()
        now = datetime.utcnow()

        # Format layout for partitioning
        year = now.strftime("%Y")
        month = now.strftime("%m")
        day = now.strftime("%d")
        timestamp_str = now.strftime("%Y%m%d_%H%M%S")
        
        if not identifier:
            identifier = str(uuid.uuid4())[:8]

        file_extension = "json"
        
        # Serialize/normalize input to bytes
        if isinstance(data, (dict, list)):
            content_bytes = json.dumps(data, default=str).encode("utf-8")
        elif isinstance(data, str):
            content_bytes = data.encode("utf-8")
            if data.strip().startswith("<"):
                file_extension = "xml"
        elif isinstance(data, (bytes, bytearray)):
            content_bytes = bytes(data)
            # Detect XML content from raw bytes
            if content_bytes.lstrip()[:5] in (b"<?xml", b"<rss ", b"<feed", b"<html"):
                file_extension = "xml"
        else:
            content_bytes = str(data).encode("utf-8")

        object_name = f"bronze/{source}/year={year}/month={month}/day={day}/{timestamp_str}_{identifier}.{file_extension}"
        
        # Upload using stream
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
