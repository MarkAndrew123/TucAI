from database import get_user_subscription, update_subscription_usage
from datetime import datetime
import json
import os

def check_can_process_request(user_id: str, is_edit: bool, token: str = None) -> tuple[bool, str]:
    """
    Checks if the user has enough daily quota to process the video.
    Returns (True, "") if allowed, or (False, "reason") if blocked.
    """
    if not user_id:
        return True, ""  # Skip if no user auth

    sub = get_user_subscription(user_id, token)
    
    # 1. Check Daily Limits (Reset at midnight)
    last_reset = sub.get("last_reset_date", "")
    today = datetime.now().strftime("%Y-%m-%d")
    
    # If it's a new day, reset usage counters
    if last_reset != today:
        update_subscription_usage(user_id, {
            "last_reset_date": today,
            "player_highlights_used": 0, # Used for daily edits
            "free_videos_used": 0        # Used for daily generations
        }, token)
        sub["player_highlights_used"] = 0
        sub["free_videos_used"] = 0

    # 2. Check Quotas
    if is_edit:
        # Edit Quota
        if sub.get("player_highlights_used", 0) >= 1:
            return False, "You've reached your limit of 1 video edit per day. Please try again tomorrow!"
    else:
        # Generation Quota
        if sub.get("free_videos_used", 0) >= 1:
            return False, "You've reached your limit of 1 new video generation per day. Please try again tomorrow!"

    # 3. Check 2GB Storage Limit
    return check_storage_limit(user_id)

def check_storage_limit(user_id: str) -> tuple[bool, str]:
    """
    Checks if the user has exceeded their 2GB storage limit.
    Returns (True, "") if allowed, or (False, "reason") if blocked.
    """
    if not user_id:
        return True, ""

    try:
        from google.cloud import storage
        storage_client = storage.Client()
        bucket = storage_client.bucket("tuc-ai-raw-uploads")
        blobs = list(bucket.list_blobs(prefix=f"{user_id}/"))
        total_size = sum(b.size for b in blobs if b.size)
        if total_size > 2 * 1024 * 1024 * 1024:
            return False, "You have exceeded your 2GB storage limit. Please delete some old videos in your Workspace."
    except Exception as e:
        print(f"Storage check failed (allowing request): {e}")

    return True, ""

def record_successful_generation(user_id: str, is_edit: bool, token: str = None):
    """
    Called after a successful video generation to increment daily quotas.
    """
    if not user_id:
        return

    sub = get_user_subscription(user_id, token)
    updates = {}

    if is_edit:
        updates["player_highlights_used"] = sub.get("player_highlights_used", 0) + 1
    else:
        updates["free_videos_used"] = sub.get("free_videos_used", 0) + 1
        
    if updates:
        update_subscription_usage(user_id, updates, token)
