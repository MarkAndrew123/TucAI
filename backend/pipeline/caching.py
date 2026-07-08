"""
GCS-backed JSON caching for web scraper results.

This module provides persistent caching using Google Cloud Storage so that
scraped match data (ESPN game IDs, WhoScored URLs, extracted moments) survives
ephemeral Cloud Run container restarts.
"""
import json
import os

GCS_BUCKET = "tuc-ai-raw-uploads"
CACHE_PREFIX = "scraper_cache"


def _get_bucket():
    """Lazy-load GCS bucket client."""
    try:
        from google.cloud import storage
        client = storage.Client()
        return client.bucket(GCS_BUCKET)
    except Exception as e:
        print(f"[Cache] Could not connect to GCS: {e}")
        return None


def get_cache(cache_key: str) -> dict | None:
    """
    Retrieve a cached JSON object from GCS.
    
    Args:
        cache_key: A unique key like 'espn/australia_vs_egypt_2026' or 'whoscored/australia_vs_egypt_2026'
    
    Returns:
        The cached dict, or None if not found.
    """
    bucket = _get_bucket()
    if not bucket:
        return None
    
    blob_name = f"{CACHE_PREFIX}/{cache_key}.json"
    blob = bucket.blob(blob_name)
    
    try:
        if blob.exists():
            data = blob.download_as_text()
            result = json.loads(data)
            print(f"[Cache] ✓ HIT for '{cache_key}'")
            return result
    except Exception as e:
        print(f"[Cache] Error reading '{cache_key}': {e}")
    
    return None


def set_cache(cache_key: str, data: dict) -> bool:
    """
    Store a JSON object in GCS cache.
    
    Args:
        cache_key: A unique key like 'espn/australia_vs_egypt_2026'
        data: The dict to cache (must be JSON-serializable)
    
    Returns:
        True if cached successfully, False otherwise.
    """
    bucket = _get_bucket()
    if not bucket:
        return False
    
    blob_name = f"{CACHE_PREFIX}/{cache_key}.json"
    blob = bucket.blob(blob_name)
    
    try:
        blob.upload_from_string(
            json.dumps(data, default=str),
            content_type="application/json"
        )
        print(f"[Cache] ✓ SAVED '{cache_key}'")
        return True
    except Exception as e:
        print(f"[Cache] Error writing '{cache_key}': {e}")
        return False


def delete_cache_prefix(prefix: str) -> int:
    """
    Delete all cached objects under a prefix (e.g. for cleanup).
    
    Returns:
        Number of objects deleted.
    """
    bucket = _get_bucket()
    if not bucket:
        return 0
    
    full_prefix = f"{CACHE_PREFIX}/{prefix}"
    blobs = list(bucket.list_blobs(prefix=full_prefix))
    count = 0
    for blob in blobs:
        try:
            blob.delete()
            count += 1
        except Exception:
            pass
    
    if count:
        print(f"[Cache] Deleted {count} cached objects under '{prefix}'")
    return count
