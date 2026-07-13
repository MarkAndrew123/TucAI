from google.cloud import storage

storage_client = storage.Client()
bucket = storage_client.bucket('tuc-ai-raw-uploads')
blob = bucket.blob('scraper_cache/espn/game_760511.json')
if blob.exists():
    blob.delete()
    print("Deleted cache")
else:
    print("Cache not found")
