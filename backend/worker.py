import os
import json
import argparse
from pipeline.orchestrator import HighlightPipeline
from config import OUTPUT_DIR
import database

def download_from_gcs(blob_name: str, dest_path: str):
    """Downloads a file from the GCS raw uploads bucket to local storage."""
    from google.cloud import storage
    print(f"Downloading {blob_name} from GCS to {dest_path}...")
    storage_client = storage.Client()
    bucket = storage_client.bucket("tuc-ai-raw-uploads")
    blob = bucket.blob(blob_name)
    
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    blob.download_to_filename(dest_path)
    print(f"Download complete: {dest_path}")

def main():
    parser = argparse.ArgumentParser(description="Cloud Run Job Worker for TUC AI Highlights")
    parser.add_argument('--project_id', required=True, help="Supabase project ID")
    parser.add_argument('--user_id', required=True, help="Supabase user ID")
    parser.add_argument('--video_path', required=True, help="GCS Blob name or local path")
    parser.add_argument('--prompt', required=False, help="User prompt")
    parser.add_argument('--intent_data', required=False, help="JSON encoded intent data")
    parser.add_argument('--token', required=False, default=None, help="User auth token")
    parser.add_argument('--mode', required=False, default='full', help="Processing mode (full or edit)")
    
    args = parser.parse_args()
    
    print(f"=== Starting Worker for Project: {args.project_id} (Mode: {args.mode}) ===")
    
    pipeline = HighlightPipeline(OUTPUT_DIR)
    intent_data = json.loads(args.intent_data) if args.intent_data else {}
    
    local_video_path = args.video_path
    downloaded_from_gcs = False
    
    # If the video path does not exist locally, assume it's a GCS blob name
    if not os.path.exists(local_video_path):
        # We are likely in Cloud Run, and the path is a blob name like "user_id/1234_video.mp4"
        local_video_path = f"/tmp/{os.path.basename(args.video_path)}"
        try:
            download_from_gcs(args.video_path, local_video_path)
            downloaded_from_gcs = True
        except Exception as e:
            print(f"Failed to download video from GCS: {e}")
            database.update_project_status(args.project_id, 'error', last_error_log=f"Failed to download video from cloud storage: {e}", token=args.token)
            return

    try:
        project_state = database.get_highlight_project(args.project_id, args.token)
        
        if args.mode == "edit":
            print("  [Mode: Edit] Bypassing AI intent and jumping straight to render_from_timeline.")
            timeline_state = project_state.get('timeline_state') if project_state else None
            if not timeline_state:
                raise Exception("Cannot render edit: timeline_state not found in database.")
                
            result = pipeline.render_from_timeline(
                video_path=local_video_path,
                user_id=args.user_id,
                project_id=args.project_id,
                token=args.token,
                timeline_state=timeline_state
            )
            # update_status('complete') is already handled inside render_from_timeline
        else:
            # Check for resume state from a previous crash
            start_moment_index = 0
            initial_timeline = None
            
            if project_state:
                saved_index = project_state.get('current_moment_index', 0)
                saved_timeline = project_state.get('timeline_state')
                if saved_index and saved_index > 0 and saved_timeline and len(saved_timeline) > 0:
                    print(f"  [Resume] Found checkpoint at moment {saved_index} with {len(saved_timeline)} clips.")
                    start_moment_index = saved_index
                    initial_timeline = saved_timeline
            
            # Run the heavy processing pipeline
            result = pipeline.run(
                local_video_path,
                args.prompt,
                intent_data=intent_data,
                user_id=args.user_id,
                project_id=args.project_id,
                token=args.token,
                start_moment_index=start_moment_index,
                initial_timeline=initial_timeline
            )
            
            # Only deduct credits if the pipeline actually produced output
            if result is not None:
                import billing
                is_player_focus = intent_data.get('intent') == "PLAYER_FOCUS"
                billing.record_successful_generation(args.user_id, is_player_focus, args.token)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        if type(e).__name__ == 'PlayerNotFoundError':
            error_data = {
                "message": str(e),
                "candidates": getattr(e, 'candidates', [])
            }
            database.update_project_status(args.project_id, 'conversational_pushback', last_error_log=json.dumps(error_data), token=args.token)
        else:
            database.update_project_status(args.project_id, 'error', last_error_log=str(e), token=args.token)
    finally:
        # Cleanup large video file from the isolated container to prevent disk filling
        if downloaded_from_gcs and os.path.exists(local_video_path):
            try:
                os.remove(local_video_path)
                print(f"Cleaned up temporary video file: {local_video_path}")
            except Exception as cleanup_err:
                print(f"Warning: Failed to cleanup temp video: {cleanup_err}")

if __name__ == "__main__":
    main()
