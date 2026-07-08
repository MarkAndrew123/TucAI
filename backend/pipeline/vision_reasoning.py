import base64
import os
import re
import json
from openai import AzureOpenAI
from config import AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY, AZURE_OPENAI_DEPLOYMENT, AZURE_OPENAI_API_VERSION

# Directory to save debug grid images
GRID_DEBUG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "grid_debug")
os.makedirs(GRID_DEBUG_DIR, exist_ok=True)

def get_client():
    if not AZURE_OPENAI_ENDPOINT:
        return None
    return AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_KEY,
        api_version=AZURE_OPENAI_API_VERSION
    )

# ─────────────────────────────────────────────────────────────
# CALIBRATION HELPER — reads the scoreboard clock from a frame
# ─────────────────────────────────────────────────────────────

def read_scoreboard_clock(base64_frame: str) -> str:
    """Uses GPT-4o Vision to read the mm:ss from the scoreboard in the frame."""
    client = get_client()
    if not client:
        return ""
        
    prompt = """
    Look at the football scoreboard in this image.
    Extract the match clock time (mm:ss).
    Reply ONLY with the time in mm:ss format (e.g. 22:30). If you cannot see a clock, reply with NONE.
    """
    
    try:
        response = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=[
                {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_frame}"}}
                ]}
            ],
            max_tokens=10
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error reading scoreboard: {e}")
        return ""

# ─────────────────────────────────────────────────────────────
# SMART NAVIGATION — read scoreboard and jump until we're close
# ─────────────────────────────────────────────────────────────

def navigate_to_minute(video_path: str, target_match_seconds: int, initial_ts: float, frame_fn, video_duration: float = None) -> float:
    """
    Iteratively navigate the video until the scoreboard shows we're exactly
    at the target match second.
    
    Tracks all successful scoreboard readings ("known good" memory) so that
    if we land in a dead zone (no clock visible), we can calculate the
    correct position mathematically instead of jumping blindly.
    
    Returns the corrected video timestamp where the scoreboard matches the target.
    """
    current_ts = initial_ts
    jump_size = 900  # Initial jump if no clock is found (15 mins to escape commercial breaks)
    
    # Track every successful reading: list of (video_ts, clock_total_seconds)
    known_readings = []
    # Track visited positions to detect loops
    visited_positions = set()
    
    for nav_step in range(7):  # Max 7 navigation steps (up from 5)
        # Clamp to video bounds
        if video_duration:
            current_ts = max(0, min(current_ts, video_duration - 1))
        else:
            current_ts = max(0, current_ts)
        
        # Loop detection: if we've been here before (within 30s), we're stuck
        position_key = round(current_ts / 30) * 30  # bucket into 30s windows
        if position_key in visited_positions and known_readings:
            # We've been here before — calculate from known data instead
            best = min(known_readings, key=lambda r: abs(r[1] - target_match_seconds))
            calculated_ts = best[0] + (target_match_seconds - best[1])
            if video_duration:
                calculated_ts = max(0, min(calculated_ts, video_duration - 1))
            print(f"  [Navigate] ⚡ Loop detected at {current_ts:.0f}s. Using math from known reading: {best[1]//60}:{best[1]%60:02d} @ {best[0]:.0f}s → target {calculated_ts:.0f}s")
            return calculated_ts
        visited_positions.add(position_key)
        
        print(f"  [Navigate Step {nav_step+1}] Reading scoreboard at video {current_ts:.0f}s...")
        
        frame_b64 = frame_fn(video_path, current_ts)
        if not frame_b64:
            print(f"  [Navigate] ✗ Could not extract frame. Trying +30s...")
            current_ts += 30
            continue
        
        clock_str = read_scoreboard_clock(frame_b64)
        print(f"  [Navigate] Scoreboard reads: {clock_str}")
        
        if not clock_str or clock_str.upper() == "NONE":
            if known_readings:
                # We have a known reading — calculate the target position mathematically
                best = min(known_readings, key=lambda r: abs(r[1] - target_match_seconds))
                calculated_ts = best[0] + (target_match_seconds - best[1])
                if video_duration:
                    calculated_ts = max(0, min(calculated_ts, video_duration - 1))
                print(f"  [Navigate] No clock visible. Calculating from known reading: {best[1]//60}:{best[1]%60:02d} @ {best[0]:.0f}s → jumping to {calculated_ts:.0f}s")
                current_ts = calculated_ts
            elif current_ts > initial_ts and initial_ts > 0:
                # We jumped forward and found nothing. Try backward from initial.
                print(f"  [Navigate] No clock visible. Trying backward from initial estimate...")
                current_ts = max(0, initial_ts - jump_size)
            else:
                print(f"  [Navigate] No clock visible (commercial/halftime). Jumping +{jump_size}s...")
                current_ts += jump_size
            continue
        
        # Parse the clock
        clock_match = re.search(r'(\d+):(\d+)', clock_str)
        if not clock_match:
            print(f"  [Navigate] Could not parse clock. Jumping +60s...")
            current_ts += 60
            continue
        
        clock_minutes = int(clock_match.group(1))
        clock_seconds = int(clock_match.group(2))
        clock_total = clock_minutes * 60 + clock_seconds
        
        # Store this known good reading
        known_readings.append((current_ts, clock_total))
        
        diff_seconds = target_match_seconds - clock_total
        
        target_minutes = target_match_seconds // 60
        target_rem_seconds = target_match_seconds % 60
        
        print(f"  [Navigate] Scoreboard: {clock_minutes}:{clock_seconds:02d} (video {current_ts:.0f}s)")
        print(f"  [Navigate] Target: {target_minutes}:{target_rem_seconds:02d} — Difference: {diff_seconds:+.0f} seconds")
        
        # If we're within 2 seconds, we've nailed it perfectly
        if abs(diff_seconds) <= 2:
            print(f"  [Navigate] ✓ Calibrated timestamp: {current_ts:.0f}s")
            return max(0, current_ts)
        
        # We're far off — jump by the EXACT difference
        print(f"  [Navigate] Jumping exact difference {diff_seconds:+.0f}s...")
        current_ts = max(0, current_ts + diff_seconds)
    
    # Exhausted steps — use the best available data
    if known_readings:
        # Calculate mathematically from the best known reading
        best = min(known_readings, key=lambda r: abs(r[1] - target_match_seconds))
        calculated_ts = best[0] + (target_match_seconds - best[1])
        if video_duration:
            calculated_ts = max(0, min(calculated_ts, video_duration - 1))
        print(f"  [Navigate] ⚠ Max steps reached. Calculated from known reading: {best[1]//60}:{best[1]%60:02d} @ {best[0]:.0f}s → {calculated_ts:.0f}s")
        return calculated_ts
    else:
        print(f"  [Navigate] ⚠ Could not find any scoreboard. Using best guess: {current_ts:.0f}s")
        return current_ts

# ─────────────────────────────────────────────────────────────
# BATCH SYNC VERIFICATION — checks 9 frames in one API call
# ─────────────────────────────────────────────────────────────

def batch_verify_sync(grid_b64: str, expected_minutes: list[str]) -> dict:
    """
    Sends a 3x3 verification grid to GPT-4o.
    Each frame has a burned-in label showing: Frame number, Expected match time, Video timestamp.
    The AI reads the actual scoreboard in each frame and reports which ones are in sync vs drifted.
    
    Returns:
        {
            "all_synced": bool,
            "first_desync_frame": int or None (1-indexed),
            "frame_results": [{"frame": 1, "expected": "03:24", "actual": "03:25", "synced": True}, ...],
            "raw_analysis": str
        }
    """
    client = get_client()
    if not client:
        print("  ✗ Azure OpenAI client not configured for batch verification!")
        return {"all_synced": True, "first_desync_frame": None, "frame_results": [], "raw_analysis": ""}

    num_frames = len(expected_minutes)
    expected_list = "\n".join([f"  Frame {i+1}: {m}" for i, m in enumerate(expected_minutes)])

    prompt = f"""You are a football video synchronization expert. You are looking at a grid of {num_frames} screenshots.
Each screenshot is taken from a different moment in a football match video.
Each frame has a burned-in label at the bottom showing:
  - The Frame number (F1 through F{num_frames})
  - The EXPECTED match clock time (what the scoreboard SHOULD show)
  - The video file timestamp

Your job is to look at the ACTUAL scoreboard clock in each frame and compare it to the EXPECTED time.

IMPORTANT: There are ONLY {num_frames} frames in this grid. Do NOT report more than {num_frames} frames. Ignore any empty/black grid cells.

## EXPECTED TIMES:
{expected_list}

## RULES:
- A frame is "IN SYNC" if the actual scoreboard clock is within ±90 seconds of the expected time.
- A frame is "DESYNCED" if the actual scoreboard clock differs by more than ±90 seconds, OR if no scoreboard is visible (commercial break, halftime graphics, etc.).
- Report ONLY frames 1 through {num_frames}. Do NOT report any frames beyond {num_frames}.

## OUTPUT FORMAT (plain text, no markdown, no code blocks):
For each frame, write one line:
FRAME_1: ACTUAL=mm:ss STATUS=SYNCED
FRAME_2: ACTUAL=mm:ss STATUS=SYNCED
...up to FRAME_{num_frames} only...

Then at the end:
ALL_SYNCED: YES or NO
FIRST_DESYNC: number (e.g. 3) or NONE"""

    try:
        response = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=[
                {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{grid_b64}"}}
                ]}
            ],
            max_tokens=1200,
            timeout=45.0
        )
        
        text = response.choices[0].message.content.strip()
        
        # Print the full analysis
        print(f"\n  ┌──────────────────────────────────────────────────────────────┐")
        print(f"  │  🔄 BATCH SYNC VERIFICATION RESULTS                        │")
        print(f"  ├──────────────────────────────────────────────────────────────┤")
        for line in text.split('\n'):
            print(f"  │  {line}")
        print(f"  └──────────────────────────────────────────────────────────────┘")
        
        # Parse results
        all_synced = bool(re.search(r'ALL_SYNCED\W+YES', text, re.IGNORECASE))
        
        first_desync = None
        desync_match = re.search(r'FIRST_DESYNC.*?(\d+)', text, re.IGNORECASE)
        if desync_match:
            val = int(desync_match.group(1))
            # Only count it if it's within the actual frame range
            if val <= len(expected_minutes):
                first_desync = val
            else:
                first_desync = None  # Phantom frame beyond batch size
        
        # Parse individual frame results
        frame_results = []
        for fm in re.finditer(r'FRAME_(\d+):\s*ACTUAL[=:]\s*(\S+)\s*STATUS[=:]\s*(\S+)', text, re.IGNORECASE):
            frame_results.append({
                "frame": int(fm.group(1)),
                "actual": fm.group(2),
                "synced": "SYNC" in fm.group(3).upper() and "DESYNC" not in fm.group(3).upper()
            })
        
        # Re-evaluate all_synced based only on frames that exist
        real_results = [fr for fr in frame_results if fr["frame"] <= len(expected_minutes)]
        real_all_synced = all(fr["synced"] for fr in real_results) if real_results else all_synced

        return {
            "all_synced": real_all_synced,
            "first_desync_frame": first_desync,
            "frame_results": frame_results,
            "raw_analysis": text
        }
        
    except Exception as e:
        print(f"  ✗ ERROR: Batch sync verification failed: {e}")
        return {"all_synced": True, "first_desync_frame": None, "frame_results": [], "raw_analysis": ""}


# ─────────────────────────────────────────────────────────────
# MAIN ENTRY POINT — called by orchestrator for each moment
# ─────────────────────────────────────────────────────────────

def _detect_replay_grid(grid_b64: str) -> dict:
    """
    Sends a 4x2 grid of 8 aftermath frames to Azure OpenAI to detect if a broadcast replay is occurring.
    """
    if not AZURE_OPENAI_ENDPOINT:
        return {"replay_detected": False, "last_replay_frame": 0, "live_play_resumed": True}
        
    client = AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_KEY,
        api_version=AZURE_OPENAI_API_VERSION
    )
    
    system_prompt = """
    You are an expert football broadcast analyst. You are looking at a 4x2 grid of 8 consecutive screenshots taken AFTER a goal was scored.
    Frames are numbered 1 to 8, and the exact timestamp is burned into the bottom-left of each frame.
    
    Your task is to determine if a slow-motion broadcast REPLAY of the goal is happening, and if so, when it ends.
    Markers of a replay: Alternate camera angles (e.g. from behind the goal, extreme close-ups of the shot), slow-motion aesthetics, or broadcast transition graphics.
    Markers of live play resuming: Players set up at the center circle for kickoff, or normal wide-angle match play has restarted.
    
    Return a JSON object:
    {
      "replay_detected": boolean, // True if ANY of the frames show a replay
      "last_replay_frame": integer, // 1-8. The frame number where the replay is STILL happening. 0 if no replay.
      "live_play_resumed": boolean, // True if normal match play (like kickoff) has clearly resumed in one of the frames.
      "reasoning": "Brief explanation"
    }
    """
    
    try:
        response = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": [
                    {"type": "text", "text": "Analyze this aftermath grid for replays:"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{grid_b64}"}}
                ]}
            ],
            max_tokens=800,
            timeout=45.0
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"    [Replay Detect Error]: {e}")
        return {"replay_detected": False, "last_replay_frame": 0, "live_play_resumed": True}

def analyze_moment(video_path: str, synced_ts: float, moment_context: dict,
                   grid_fn, frame_fn) -> tuple[float, float, str]:
    """
    Full iterative analysis of a match moment.
    
    Flow:
      1. NAVIGATE: Read scoreboard, if far from target jump closer (repeat until within ~2 min)
      2. GRID ANALYSIS: Extract 8 frames covering 70s, save grid image, send to AI
      3. AI analyzes each quadrant individually with progressive reasoning
      4. If commercial → jump ±90-180s and retry
      5. If football but event not found → scan NEXT 60s sequentially
      6. Save all grid images to grid_debug/ for inspection
    """
    minute = moment_context["minute"]
    added_time = moment_context.get("added_time")
    event_type = moment_context["type"]
    player = moment_context["player"]
    details = moment_context.get("details", "")
    
    # Calculate the true minute shown on the scoreboard (e.g., 45' + 2 = 47')
    target_nav_minute = minute + (added_time or 0)
    
    # ── Step 0: Smart Navigation — make sure we're at the right time ──
    print(f"\n  {'─'*60}")
    added_str = f"+{added_time}" if added_time else ""
    print(f"  SMART NAVIGATION — Getting to match clock {target_nav_minute}' (from {minute}'{added_str})")
    print(f"  {'─'*60}")
    
    navigated_ts = navigate_to_minute(video_path, target_nav_minute * 60, synced_ts, frame_fn)
    
    # Calculate the video offset so dumb cuts can use it later
    calibrated_offset = navigated_ts - (target_nav_minute * 60)
    
    # Grid config
    GRID_INTERVAL = 10.0   # 10 seconds between frames (8 frames covers 70s total)
    NUM_FRAMES = 8
    MAX_ATTEMPTS = 4
    
    all_commercial = True
    
    # Attempt offsets:
    # - Start: cover (minute-1):00 to minute:00 
    # - If football but not found: scan FORWARD sequentially (+60s each time)
    # - If commercial: big jumps to escape
    next_offset = 0
    
    for attempt in range(MAX_ATTEMPTS):
        # Start grid 35s BEFORE the navigated midpoint
        grid_start = max(0, navigated_ts - 35 + next_offset)
        
        frame_timestamps = [grid_start + (i * GRID_INTERVAL) for i in range(NUM_FRAMES)]
        
        # ── Print what we're doing ──
        print(f"\n{'='*70}")
        print(f"  GRID ANALYSIS — Attempt {attempt + 1}/{MAX_ATTEMPTS}")
        print(f"  Looking for: {event_type.upper()} at minute {minute}' by {player}")
        print(f"  Details: {details}")
        print(f"  Search offset from navigated position: {next_offset:+d}s")
        print(f"  Grid sampling window:")
        for i, ts in enumerate(frame_timestamps):
            mins = int(ts // 60)
            secs = int(ts % 60)
            print(f"    Frame {i+1}: video {mins}m{secs:02d}s  ({ts:.0f}s)")
        print(f"{'='*70}")
        
        # ── Extract the grid ──
        grid_b64 = grid_fn(video_path, grid_start, interval_secs=GRID_INTERVAL, num_frames=NUM_FRAMES)
        if not grid_b64:
            print(f"  ✗ ERROR: Failed to extract grid frames. Retrying...")
            next_offset += 60
            continue
        
        # ── Save grid image to disk for debugging ──
        grid_filename = f"grid_minute{minute}_{event_type}_attempt{attempt+1}.jpg"
        grid_path = os.path.join(GRID_DEBUG_DIR, grid_filename)
        try:
            grid_bytes = base64.b64decode(grid_b64)
            with open(grid_path, "wb") as f:
                f.write(grid_bytes)
            print(f"  📸 Grid saved: {grid_path}")
        except Exception as e:
            print(f"  ⚠ Could not save grid image: {e}")
            
        # ── Run deep AI analysis ──
        analysis = _deep_analyze_grid(grid_b64, moment_context, frame_timestamps)
        
        # ── RELATIVE CONTEXT VALIDATION ──
        # Check this BEFORE blindly accepting the event!
        expected_score = moment_context.get("expected_score")
        actual_score = analysis.get("score_before")
        if expected_score and actual_score and actual_score.upper() != "UNKNOWN" and expected_score.upper() != "UNKNOWN":
            if expected_score != actual_score:
                print(f"\n  ⚠ RELATIVE CONTEXT VALIDATION FAILED!")
                print(f"    Expected score {expected_score} but AI sees {actual_score}.")
                print(f"    The timestamp is likely out of sync. Forcing event_found=NO.")
                analysis["event_found"] = False
        
        # ── Decision based on AI output ──
        if analysis["is_valid_scene"] and analysis["event_found"]:
            climax_frame = analysis.get("climax_frame", 0)
            if climax_frame > 0:
                climax_idx = climax_frame - 1
                climax_ts = frame_timestamps[climax_idx]
            else:
                # Event confirmed but exact climax missed. Default to middle.
                climax_ts = frame_timestamps[NUM_FRAMES // 2]
            
            # ── DYNAMIC NARRATIVE BUFFERS ──
            event_lower = event_type.lower()
            clips = []
            
            if "goal" in event_lower:
                # Clip 1: 12s buildup, 2s celebration
                live_start = max(0, climax_ts - 12)
                live_end = climax_ts + 2
                clips.append({
                    "type": "live",
                    "start": live_start,
                    "end": live_end,
                    "reasoning": analysis.get("raw_analysis", "")
                })
                
                # Fallback anchor for starting the replay hunt
                end_cut_anchor = climax_ts + 20
            elif "red card" in event_lower:
                # Clip 1: 15s buildup (the foul), 5s argument
                live_start = max(0, climax_ts - 15)
                live_end = climax_ts + 5
                clips.append({
                    "type": "live",
                    "start": live_start,
                    "end": live_end,
                    "reasoning": analysis.get("raw_analysis", "")
                })
                
                # Fallback anchor
                end_cut_anchor = climax_ts + 15
            else:
                # Big chances: 10s buildup, 3s reaction
                live_start = max(0, climax_ts - 10)
                live_end = climax_ts + 3
                clips.append({
                    "type": "live",
                    "start": live_start,
                    "end": live_end,
                    "reasoning": analysis.get("raw_analysis", "")
                })
                
                # Fallback anchor
                end_cut_anchor = climax_ts + 10
                
            is_player_focus = moment_context.get("intent_data", {}).get("intent") == "PLAYER_FOCUS" if moment_context.get("intent_data") else False
            
            if is_player_focus and "goal" not in event_lower:
                print(f"\n  [Replay Hunt] Skipping replay hunt for {event_type} in PLAYER_FOCUS workflow.")
                return clips, analysis.get("score_after", "UNKNOWN"), calibrated_offset

            # Skip replay hunt for shot events — user requested no replays for these
            NO_REPLAY_EVENTS = ["savedshot", "shotonpost"]
            if event_lower in NO_REPLAY_EVENTS:
                print(f"\n  [Replay Hunt] Skipping replay hunt for {event_type} (no replays allowed for shot events).")
                return clips, analysis.get("score_after", "UNKNOWN"), calibrated_offset
                
            print(f"\n  [Replay Hunt] Event detected! Hunting for broadcast replays...")            
            # INTELLIGENT CHAINING
            prediction = analysis.get("replay_prediction", "")
            print(f"  [AI Prediction] {prediction}")
            
            if "STARTED_IN_FRAME_" in prediction.upper():
                pred_frame_match = re.search(r'\d+', prediction)
                if pred_frame_match:
                    pred_frame = int(pred_frame_match.group())
                    replay_search_start = frame_timestamps[max(0, pred_frame-1)]
                    print(f"  [Chaining] AI saw replay start in Frame {pred_frame}. Starting Grid 2 at {replay_search_start:.0f}s.")
                else:
                    replay_search_start = end_cut_anchor
                    print(f"  [Chaining] No replay visible yet. Starting Grid 2 after celebration at {replay_search_start:.0f}s.")
            else:
                replay_search_start = end_cut_anchor
                print(f"  [Chaining] No replay visible yet. Starting Grid 2 after celebration at {replay_search_start:.0f}s.")
            
            max_replay_attempts = 3
            
            for r_attempt in range(max_replay_attempts):
                # Create the 8-frame Replay Hunt grid
                grid_b64 = grid_fn(video_path, replay_search_start, interval_secs=GRID_INTERVAL, num_frames=NUM_FRAMES)
                
                if grid_b64:
                    # Save for debug
                    os.makedirs("grid_debug", exist_ok=True)
                    with open(f"grid_debug/replay_hunt_minute{minute}_attempt{r_attempt+1}.jpg", "wb") as f:
                        f.write(base64.b64decode(grid_b64))
                        
                    replay_analysis = _detect_replay_grid(grid_b64)
                    
                    # We need to calculate timestamps to find the end_cut
                    replay_timestamps = [replay_search_start + (i * GRID_INTERVAL) for i in range(NUM_FRAMES)]
                    
                    print(f"    Attempt {r_attempt+1}: Replay Detected? {replay_analysis.get('replay_detected')} | Last Frame: {replay_analysis.get('last_replay_frame')} | Live Resumed? {replay_analysis.get('live_play_resumed')}")
                    
                    if replay_analysis.get("replay_detected"):
                        last_frame_idx = max(0, replay_analysis.get("last_replay_frame", 1) - 1)
                        # Replay clip end
                        replay_end_ts = replay_timestamps[last_frame_idx] + 5
                        
                        # If live play hasn't resumed, we might want to slide forward and check again
                        if not replay_analysis.get("live_play_resumed") and r_attempt < max_replay_attempts - 1:
                            replay_search_start = replay_timestamps[-1] + 10 # Slide forward
                            continue # Next attempt
                        else:
                            print(f"  [Replay Hunt] Replay sequence captured! Added replay clip: {replay_search_start:.0f}s to {replay_end_ts:.0f}s.")
                            clips.append({
                                "type": "replay",
                                "start": replay_search_start,
                                "end": replay_end_ts,
                                "reasoning": replay_analysis.get("reasoning", "")
                            })
                            break
                    else:
                        print(f"  [Replay Hunt] No (more) replays detected.")
                        break
                else:
                    break # Failed to extract frames
            
            print(f"\n  ✓ EVENT LOCATED IN FRAME {climax_frame}!" if climax_frame > 0 else f"\n  ✓ EVENT LOCATED BETWEEN FRAMES!")
            print(f"    Climax video timestamp: {climax_ts:.0f}s")
            for clip_i, clip in enumerate(clips):
                print(f"    Clip {clip_i+1} ({clip['type']}):   {clip['start']:.0f}s  →  {clip['end']:.0f}s")
            if analysis.get("score_before"):
                print(f"    Score before: {analysis['score_before']}")
            if analysis.get("score_after"):
                print(f"    Score after:  {analysis['score_after']}")
            print(f"{'='*70}\n")
            return clips, analysis.get("score_after", "UNKNOWN"), calibrated_offset
        
        elif not analysis["is_valid_scene"]:
            # Commercial break — make a BIG jump to escape it
            print(f"\n  ✗ NOT A FOOTBALL SCENE — Commercial break or graphic.")
            if attempt == 0:
                next_offset = -120  # Try 2 minutes earlier
            elif attempt == 1:
                next_offset = +120  # Try 2 minutes later
            else:
                next_offset = -240  # Try 4 minutes earlier
            print(f"    Next attempt: jumping {next_offset:+d}s from navigated position")
            print(f"{'='*70}\n")
        
        else:
            all_commercial = False  # It was a football scene, just wrong moment
            
            # Scan FORWARD sequentially — the event is probably in the next 60 seconds
            next_offset += 60
            print(f"\n  ⚠ Football scene confirmed, but {event_type} NOT captured (or validation failed).")
            print(f"    Scanning forward to next 60-second window (+{next_offset}s)...")
            print(f"{'='*70}\n")
    
    # ── All attempts exhausted ──
    if all_commercial:
        print(f"\n  ✗ SKIPPING: All {MAX_ATTEMPTS} attempts landed on commercials/graphics.")
        print(f"    Cannot locate {event_type} at {minute}'. This moment will be excluded.")
        print(f"{'='*70}\n")
        return [], "UNKNOWN", None
    
    # At least some attempts found football — use fallback window
    print(f"\n  ⚠ FALLBACK: Could not pinpoint {event_type} at {minute}' after {MAX_ATTEMPTS} attempts.")
    print(f"    Using default ±12s window around navigated timestamp {navigated_ts:.0f}s.")
    print(f"{'='*70}\n")
    return [{"type": "live", "start": max(0, navigated_ts - 12), "end": navigated_ts + 12, "reasoning": "Fallback used."}], "UNKNOWN", calibrated_offset


# ─────────────────────────────────────────────────────────────
# DEEP GRID ANALYSIS — the AI "thinks out loud"
# ─────────────────────────────────────────────────────────────

def _deep_analyze_grid(grid_b64: str, moment_context: dict,
                       frame_timestamps: list) -> dict:
    """
    Sends the 2x2 grid to GPT-4o with a rich progressive-reasoning prompt.
    The AI describes each frame individually, connects them into a narrative,
    validates the scene, and identifies the climax frame.
    """
    client = get_client()
    if not client:
        print("  ✗ Azure OpenAI client not configured!")
        return {"is_valid_scene": True, "event_found": False, "climax_frame": 0}
    
    minute = moment_context["minute"]
    event_type = moment_context["type"]
    player = moment_context["player"]
    details = moment_context.get("details", "")
    
    # Format timestamps for the prompt
    ts_labels = []
    for ts in frame_timestamps:
        m = int(ts // 60)
        s = int(ts % 60)
        ts_labels.append(f"{m}m{s:02d}s")
        
    intent_data = moment_context.get("intent_data") or {}
    is_player_focus = intent_data.get("intent") == "PLAYER_FOCUS"
    
    player_instructions = ""
    if is_player_focus:
        player_instructions = f"""
### PLAYER FOCUS MODE ACTIVATED
You are looking for every touch by **{player}**. 
Pay extreme attention to finding the player who matches his description/jersey. Even if the action is minor (a pass, a foul, a header), if {player} is involved, it is a valid scene!
"""

    scoreless_instructions = """
### SCORELESS / FALLBACK MODE
If you do NOT see a scoreboard in the frames, DO NOT automatically reject the scene. 
Instead, look for visual contextual cues (e.g., players setting up for a corner, referee whistling, intense tackles, celebrations). Use these cues to determine the phase of play and climax frame.
"""

    prompt = f"""You are an expert football video analyst. I am building an automated highlight reel.

I need you to find a **{event_type}** that happened at match minute **{minute}'** by **{player}** ({details}).
{player_instructions}
{scoreless_instructions}
This is a 4x2 grid of 8 sequential screenshots from the match video file.
Each frame has its exact frame number and video timestamp burned into the bottom-left corner.

## STEP 1: ANALYZE EACH FRAME INDIVIDUALLY

For EACH frame:
- Is this a live football match scene, or a commercial/graphic/replay/halftime screen?
- Read the scoreboard: teams, score, match clock time
- Describe the phase of play

## STEP 2: PROGRESSIVE REASONING

Connect all 8 frames:
1. What is the phase-of-play sequence?
2. Did the score change between any frames? (confirms a goal)
3. Is the {event_type} by {player} visible? Which frame is the CLIMAX?
4. If not visible — explain why
5. Predict Replays: Do any frames show a broadcast replay already starting?

## STEP 3: FINAL VERDICT

Use EXACTLY this format (no bold, no markdown, plain text):

IS_FOOTBALL_SCENE: YES or NO
EVENT_FOUND: YES or NO
CLIMAX_FRAME: 1 to 8 (or 0)
SCORE_BEFORE: e.g. 0-0
SCORE_AFTER: e.g. 1-0
REPLAY_PREDICTION: STARTED_IN_FRAME_X or NOT_STARTED
REASONING: one sentence"""

    try:
        response = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=[
                {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{grid_b64}"}}
                ]}
            ],
            max_tokens=800,
            timeout=45.0
        )
        
        text = response.choices[0].message.content.strip()
        
        # ── Print the FULL AI reasoning to the terminal ──
        print(f"\n  ┌──────────────────────────────────────────────────────────────┐")
        print(f"  │  🧠 AI VISION ANALYSIS — Minute {minute}' {event_type.upper():>10s} by {player}")
        print(f"  ├──────────────────────────────────────────────────────────────┤")
        for line in text.split('\n'):
            print(f"  │  {line}")
        print(f"  └──────────────────────────────────────────────────────────────┘")
        
        # ── Parse structured verdict ──
        # Use \W+ to match any non-word characters (handles **bold**, colons, spaces, etc.)
        is_football = bool(re.search(r'IS_FOOTBALL_SCENE\W+YES', text, re.IGNORECASE))
        event_found = bool(re.search(r'EVENT_FOUND\W+YES', text, re.IGNORECASE))
        
        climax_frame = 0
        climax_match = re.search(r'CLIMAX_FRAME\W+([0-8])', text, re.IGNORECASE)
        if climax_match:
            climax_frame = int(climax_match.group(1))
        
        score_before = "UNKNOWN"
        score_before_match = re.search(r'SCORE_BEFORE\W+(.+)', text, re.IGNORECASE)
        if score_before_match:
            score_before = score_before_match.group(1).strip().strip('*')
        
        score_after = "UNKNOWN"
        score_after_match = re.search(r'SCORE_AFTER\W+(.+)', text, re.IGNORECASE)
        if score_after_match:
            score_after = score_after_match.group(1).strip().strip('*')
        
        # ── Print parsed verdict summary ──
        print(f"\n  PARSED VERDICT:")
        print(f"    Football Scene: {'YES ✓' if is_football else 'NO ✗'}")
        print(f"    Event Found:    {'YES ✓' if event_found else 'NO ✗'}")
        print(f"    Climax Frame:   {climax_frame}")
        
        replay_prediction = "NOT_STARTED"
        pred_match = re.search(r'REPLAY_PREDICTION\W+(STARTED_IN_FRAME_\d+|NOT_STARTED)', text, re.IGNORECASE)
        if pred_match:
            replay_prediction = pred_match.group(1).upper()
            
        return {
            "is_valid_scene": is_football,
            "event_found": event_found,
            "climax_frame": climax_frame,
            "score_before": score_before,
            "score_after": score_after,
            "replay_prediction": replay_prediction,
            "raw_analysis": text
        }
    
    except Exception as e:
        print(f"  ✗ ERROR: AI grid analysis failed: {e}")
        return {"is_valid_scene": True, "event_found": False, "climax_frame": 0}
