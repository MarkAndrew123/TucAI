from database import get_user_subscription, update_subscription_usage
from datetime import datetime
import json

def check_can_process_request(user_id: str, is_player_focus: bool, token: str = None) -> tuple[bool, str]:
    """
    Checks if the user has enough credits/permission to process the video.
    Returns (True, "") if allowed, or (False, "reason") if blocked.
    """
    if not user_id:
        return True, ""  # Skip if no user auth

    sub = get_user_subscription(user_id, token)
    plan_tier = sub.get("plan_tier", "FREE")
    
    # 1. Check Daily Limits (Reset at midnight)
    last_reset = sub.get("last_reset_date", "")
    today = datetime.now().strftime("%Y-%m-%d")
    
    # If it's a new day, reset usage counters
    if last_reset != today:
        update_subscription_usage(user_id, {
            "last_reset_date": today,
            "player_highlights_used": 0,
            # We don't reset free_videos_used because free trial is a one-time limit!
        }, token)
        sub["player_highlights_used"] = 0

    # 2. Free Tier Logic (1 Video Generation total within 7 days)
    if plan_tier == "FREE":
        # Check 7-day time limit
        created_at_str = sub.get("created_at")
        if created_at_str:
            try:
                # Handle standard Supabase ISO timestamps with offset awareness
                from datetime import timezone
                created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                if (datetime.now(timezone.utc) - created_at).days >= 7:
                    return False, "FREE_TRIAL_EXPIRED"
            except Exception as e:
                print(f"Error parsing created_at timestamp in billing limits: {e}")
                
        if sub.get("free_videos_used", 0) >= 1:
            return False, "FREE_LIMIT_REACHED"
        return True, ""

    # 3. Basic Plan Logic (Unlimited Match, 2 Player Highlights per day)
    if plan_tier == "BASIC":
        if is_player_focus:
            if sub.get("player_highlights_used", 0) >= 2:
                return False, "BASIC_PLAYER_LIMIT_REACHED"
        return True, ""

    # 4. Pro Plan Logic (Unlimited Everything)
    if plan_tier == "PRO":
        return True, ""

    return True, ""

def record_successful_generation(user_id: str, is_player_focus: bool, token: str = None):
    """
    Called after a successful video generation to deduct credits.
    """
    if not user_id:
        return

    sub = get_user_subscription(user_id, token)
    plan_tier = sub.get("plan_tier", "FREE")
    updates = {}

    if plan_tier == "FREE":
        updates["free_videos_used"] = sub.get("free_videos_used", 0) + 1
    
    elif plan_tier == "BASIC" and is_player_focus:
        updates["player_highlights_used"] = sub.get("player_highlights_used", 0) + 1
        
    if updates:
        update_subscription_usage(user_id, updates, token)
