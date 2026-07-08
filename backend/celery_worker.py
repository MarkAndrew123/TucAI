import os
import asyncio
from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "video_worker",
    broker=REDIS_URL,
    backend=REDIS_URL
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    worker_concurrency=2, # Limit concurrency so OpenCV doesn't overwhelm memory
)

@celery_app.task(bind=True, name="process_highlight_job")
def process_highlight_job(self, video_path: str, prompt: str, intent_data: dict, user_id: str, project_id: str, token: str):
    """
    Celery background worker task to process a video asynchronously using OpenCV and FFmpeg.
    In a fully cloud-native setup (like GKE), a lightweight Celery worker would use the 
    Kubernetes Python API here to dispatch a Job instead of running it locally.
    For Cloud Run or simple VM setups, it runs directly.
    """
    from app import run_pipeline_with_error_handling, pipeline  # Import locally to avoid circular dependencies
    print(f"Starting Celery Task for Project: {project_id}")
    
    # Celery functions are synchronous by default. If run_pipeline_with_error_handling is async:
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    try:
        result = loop.run_until_complete(
            run_pipeline_with_error_handling(
                pipeline, video_path, prompt, intent_data, user_id, project_id, token
            )
        )
        return {"status": "success", "result": result}
    except Exception as e:
        print(f"Celery task failed: {e}")
        return {"status": "error", "error": str(e)}

