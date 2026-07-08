import re

def estimate_video_timestamp(match_minute: int, video_duration: float, half: int, added_time: int = None) -> float:
    """
    Simple direct estimate: 1 match minute ≈ 60 video seconds.
    Supports smart single half detection adjusting offsets relative to start.
    Now properly incorporates added_time (e.g., 45+2 injury time).
    """
    is_single_half = (video_duration / 60.0) <= 85.0
    extra = (added_time or 0) * 60.0  # Convert added minutes to seconds
    
    # If half == 0 (Full Match), dynamically determine the half based on the match minute.
    if half == 0:
        if match_minute <= 45:
            half = 1
        elif match_minute <= 90:
            half = 2
        else:
            half = 3

    if half == 1:
        # First half starts at minute 0
        return match_minute * 60.0 + extra
    elif half == 2:
        if is_single_half:
            # If it's a second-half-only video, match minute 45 corresponds to video start (0s)
            minute_in_half = max(0, match_minute - 45)
            return minute_in_half * 60.0 + extra
        else:
            # Full match video: second half starts roughly 60 minutes in (45m + 15m halftime)
            HALF_2_VIDEO_START = 60 * 60.0  # 3600s
            minute_in_half = max(0, match_minute - 45)
            return HALF_2_VIDEO_START + (minute_in_half * 60.0) + extra
    elif half == 3:
        if is_single_half:
            # If it's an extra-time-only video, match minute 90 corresponds to video start (0s)
            minute_in_half = max(0, match_minute - 90)
            return minute_in_half * 60.0 + extra
        else:
            # Full match video: extra time starts roughly 110 minutes in (90m + 15m halftime + 5m rest)
            EXTRA_TIME_VIDEO_START = 110 * 60.0  # 6600s
            minute_in_half = max(0, match_minute - 90)
            return EXTRA_TIME_VIDEO_START + (minute_in_half * 60.0) + extra
    
    return 0.0

def search_window(estimated_ts: float, window_secs: int = 30) -> tuple[float, float]:
    """Returns the start and end of the search window."""
    start = max(0.0, estimated_ts - window_secs)
    end = estimated_ts + window_secs
    return start, end

def parse_mm_ss(time_str: str) -> float:
    """Converts mm:ss to total seconds."""
    if not time_str or time_str == "NONE":
        return -1.0
    try:
        match = re.search(r'(\d+):(\d+)', time_str)
        if match:
            m = int(match.group(1))
            s = int(match.group(2))
            return m * 60.0 + s
        return -1.0
    except:
        return -1.0

def calibrate_timestamp(video_path: str, target_match_minute: int, initial_guess_ts: float) -> float:
    """
    Takes a single frame at initial_guess_ts, reads the scoreboard, and calculates the drift.
    """
    from pipeline import video, vision_reasoning
    print(f"  [Calibration] Target match minute: {target_match_minute}'")
    print(f"  [Calibration] Initial guess: {initial_guess_ts:.0f}s ({int(initial_guess_ts//60)}m{int(initial_guess_ts%60):02d}s)")
    
    frame_b64 = video.extract_frame_base64(video_path, initial_guess_ts)
    if not frame_b64:
        print("  [Calibration] ✗ Failed to extract frame. Using initial guess.")
        return initial_guess_ts
        
    clock_str = vision_reasoning.read_scoreboard_clock(frame_b64)
    print(f"  [Calibration] AI read scoreboard clock as: {clock_str}")
    
    clock_seconds = parse_mm_ss(clock_str)
    if clock_seconds < 0:
        print("  [Calibration] ✗ Could not read clock. Using initial guess.")
        return initial_guess_ts
    
    clock_minute = clock_seconds / 60.0
    print(f"  [Calibration] Scoreboard shows match minute: {clock_minute:.1f}'")
    
    # Sanity check: if the scoreboard shows a time WAY off from our target,
    # the initial estimate was probably in a commercial or the wrong half.
    # In that case, the drift would be too large to trust.
    target_seconds = target_match_minute * 60.0
    drift = target_seconds - clock_seconds
    
    if abs(drift) > 1800:  # More than 30 minutes of drift = something is very wrong
        print(f"  [Calibration] ⚠ Drift is {drift:.0f}s ({abs(drift)/60:.0f} minutes) — too large!")
        print(f"  [Calibration] The initial estimate likely landed in the wrong half or a commercial.")
        print(f"  [Calibration] Using initial guess instead.")
        return initial_guess_ts
        
    calibrated_ts = initial_guess_ts + drift
    print(f"  [Calibration] Drift: {drift:.0f}s → Calibrated timestamp: {calibrated_ts:.0f}s ({int(calibrated_ts//60)}m{int(calibrated_ts%60):02d}s)")
    return max(0.0, calibrated_ts)
