import json
from google.cloud import storage

storage_client = storage.Client()
bucket = storage_client.bucket('tuc-ai-raw-uploads')
blob = bucket.blob('scraper_cache/espn/game_760511.json')
data = json.loads(blob.download_as_string())

print(f"Moments length: {len(data.get('moments', []))}")
for m in data.get('moments', []):
    print(m)
