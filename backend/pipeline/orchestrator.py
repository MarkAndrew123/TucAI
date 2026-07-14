import os
import json
import shutil
from . import espn, timestamp, vision_reasoning, video, match_locator

class HighlightPipeline:
    def __init__(self, output_dir: str):
        self.output_dir = output_dir

    def run(self, video_path: str, prompt: str, half: int = 0, intent_data: dict = None, user_id: str = None, project_id: str = None, token: str = None, start_moment_index: int = 0, initial_timeline: list = None):
        print(f"\n{'#'*70}")
        print(f"  HIGHLIGHT PIPELINE STARTING")
        print(f"  Prompt: {prompt}")
        print(f"  Video:  {video_path}")
        print(f"  Half:   {half}")
        if intent_data:
            print(f"  Intent: {intent_data.get('intent')} | Player: {intent_data.get('player_name')}")
        print(f"{'#'*70}\n")

        def update_status(status, **kwargs):
            if project_id and user_id:
                import database
                database.update_project_status(project_id, status, token=token, **kwargs)


        update_status('scanning', stage_message='Scanning match database...')

        # Determine Pipeline Strategy
        moments = []
        is_player_focus = intent_data and intent_data.get('intent') == "PLAYER_FOCUS"
        
        if is_player_focus:
            print("  [STRATEGY] Player Focus -> Using WhoScored Subprocess Scraper")
            from . import whoscored
            import re as _re
            raw_match_name = intent_data.get('match_name') or prompt
            # Strip the embedded (id:...) tag so validation/cache keys stay clean,
            # but pass it through the query so whoscored's URL regex can still extract it.
            clean_match_name = _re.sub(r'\s*\(?id:[^)]+\)?', '', raw_match_name).strip()
            # Build the whoscored query with the raw name (contains URL for direct extraction)
            year = intent_data.get('year')
            player = intent_data.get('player_name')
            moments = whoscored.fetch_player_touches(raw_match_name, year, player, clean_match_name=clean_match_name)
            
            # Sub-filter: only process major events with Vision AI if requested, others just dumb cut
            # We'll let vision_reasoning decide if it wants to analyze based on event_type.
            
        else:
            print("  [STRATEGY] General Highlight -> Using ESPN Match Locator")
            import re as _re
            # 1. Search match via NLP match locator
            raw_match_name = intent_data.get('match_name') or prompt
            year = intent_data.get('year') or ""
            search_query = f"{raw_match_name} {year}".strip()
            game_id = match_locator.locate_exact_match(search_query)
            # 2. Get moments from ESPN
            moments = espn.fetch_match_details(game_id)
            
        print(f"\n  Found {len(moments)} total moments from data:")
        for i, m in enumerate(moments):
            added = f"+{m.added_time}" if m.added_time else ""
            print(f"    {i+1}. {m.minute}'{added} — {m.moment_type.upper()} — {m.player} ({m.details})")
        
        # Get actual video duration via OpenCV
        import cv2
        cap = cv2.VideoCapture(video_path)
        video_duration = cap.get(cv2.CAP_PROP_FRAME_COUNT) / max(1, cap.get(cv2.CAP_PROP_FPS))
        cap.release()
        print(f"\n  Video duration: {video_duration:.0f}s ({video_duration/60:.1f} minutes)")
        
        # Smart detect Full Match vs Single Half
        video_duration_minutes = video_duration / 60.0
        if video_duration_minutes > 85.0 and half != 0:
            print(f"  [Smart Detect] Video is {video_duration_minutes:.1f} minutes long -> Detected FULL MATCH. Overriding requested half={half} to half=0 (process all).")
            half = 0
            
        # Differentiate single halves (first half, second half, extra time) if video is short
        if video_duration_minutes <= 85.0:
            print(f"  [Smart Detect] Video is {video_duration_minutes:.1f} minutes long -> Single half detected. Sampling scoreboard to determine segment...")
            detected_half = None
            sample_timestamps = [min(300.0, video_duration * 0.2), min(600.0, video_duration * 0.4)]
            
            for ts in sample_timestamps:
                try:
                    frame_b64 = video.extract_frame_base64(video_path, ts)
                    if frame_b64:
                        clock_str = vision_reasoning.read_scoreboard_clock(frame_b64)
                        print(f"  [Smart Detect] Sampled scoreboard at {ts:.0f}s: {clock_str}")
                        clock_seconds = timestamp.parse_mm_ss(clock_str)
                        if clock_seconds > 0:
                            clock_minute = clock_seconds / 60.0
                            if clock_minute <= 48.0:
                                detected_half = 1
                                print(f"  [Smart Detect] Scoreboard shows minute {clock_minute:.1f} -> Detected FIRST HALF")
                                break
                            elif clock_minute <= 95.0:
                                detected_half = 2
                                print(f"  [Smart Detect] Scoreboard shows minute {clock_minute:.1f} -> Detected SECOND HALF")
                                break
                            else:
                                detected_half = 3
                                print(f"  [Smart Detect] Scoreboard shows minute {clock_minute:.1f} -> Detected EXTRA TIME")
                                break
                except Exception as e:
                    print(f"  [Smart Detect] Error sampling scoreboard at {ts:.0f}s: {e}")
            
            if detected_half:
                print(f"  [Smart Detect] Overriding half={half} to detected half={detected_half}")
                half = detected_half
            else:
                print("  [Smart Detect] Could not read scoreboard clock from samples. Defaulting to full match moment processing.")

        # Filter moments for the requested half
        filtered_moments = []
        for moment in moments:
            if half == 1 and moment.minute > 48:
                # Exclude first half moments that fall outside typical first half (including injury time)
                continue
            if half == 2 and (moment.minute <= 45 or moment.minute > 95):
                # Exclude first half and extra time moments from second half
                continue
            if half == 3 and moment.minute <= 90:
                # Exclude regular time moments from extra time
                continue
            filtered_moments.append(moment)
        
        # VERY IMPORTANT: Sort moments chronologically to prevent half-change flip-flopping
        filtered_moments.sort(key=lambda m: getattr(m, 'sort_key', getattr(m, 'absolute_seconds', m.minute * 60 + (m.added_time or 0) * 60)))
        
        if half == 1:
            half_str = "First Half Only"
        elif half == 2:
            half_str = "Second Half Only"
        elif half == 3:
            half_str = "Extra Time Only"
        else:
            half_str = "Full Match"
            
        print(f"  Processing {len(filtered_moments)} moments for {half_str}.\n")
        
        # ── Early exit if no moments found ──
        if len(filtered_moments) == 0:
            error_msg = "Could not find any match data for this game. The match may not exist on our data sources, or the web search failed to find results."
            print(f"\n  [ERROR] {error_msg}")
            update_status('error', stage_message=error_msg, last_error_log=error_msg)
            return None
        
        update_status('analyzing', total_moments=len(filtered_moments), stage_message=f'Identified {len(filtered_moments)} target moments')
        
        clip_paths = []
        timeline_state = []
        
        # ══════════════════════════════════════════════════════════════
        # CHECKPOINT RESUME LOGIC
        # ══════════════════════════════════════════════════════════════
        # If resuming from a previous crash, download previously cut clips
        # from GCS and skip to the moment where we left off.
        # ══════════════════════════════════════════════════════════════
        if start_moment_index > 0 and initial_timeline:
            print(f"\n{'='*70}")
            print(f"  RESUMING FROM CHECKPOINT — Moment {start_moment_index}/{len(filtered_moments)}")
            print(f"  Downloading {len(initial_timeline)} previously cut clips from GCS...")
            print(f"{'='*70}")
            
            timeline_state = list(initial_timeline)
            for tl_entry in initial_timeline:
                clip_blob = tl_entry.get("gcs_clip_path")
                local_clip = tl_entry.get("output_file")
                if clip_blob and local_clip:
                    try:
                        from google.cloud import storage as gcs_storage
                        client = gcs_storage.Client()
                        bucket = client.bucket("tuc-ai-raw-uploads")
                        blob = bucket.blob(clip_blob)
                        os.makedirs(os.path.dirname(local_clip), exist_ok=True)
                        blob.download_to_filename(local_clip)
                        clip_paths.append(local_clip)
                        print(f"    ✓ Downloaded: {os.path.basename(local_clip)}")
                    except Exception as dl_err:
                        print(f"    ✗ Failed to download {clip_blob}: {dl_err}")
            
            print(f"  Resume complete. {len(clip_paths)} clips recovered.\n")
            update_status('analyzing', current_moment_index=start_moment_index, stage_message=f'Resumed from checkpoint at moment {start_moment_index}')
        
        # ══════════════════════════════════════════════════════════════
        # BATCH VERIFICATION ARCHITECTURE
        # ══════════════════════════════════════════════════════════════
        # 1. Calibrate offset on the very first touch (Vision AI reads scoreboard)
        # 2. Process moments in batches of up to 16
        # 3. For each batch, create a 4x4 verification grid (1 API call)
        # 4. If all 16 frames are in sync -> dumb cut all of them
        # 5. If a frame is desynced -> corrective navigation to recalibrate
        # 6. Major events (Goals, Shots, Dribbles) ALWAYS get full Vision AI
        # ══════════════════════════════════════════════════════════════
        
        video_offset = None
        current_half = None
        MAJOR_EVENTS = ["Goal", "Big Chance", "SavedShot", "Red Card", "ShotOnPost"]
        
        # Split moments into batches for processing
        moment_index = start_moment_index
        retry_counts = {}  # Track retries per moment_index to prevent infinite loops
        
        while moment_index < len(filtered_moments):
            try:
                # ── Kill Switch Check ──
                if user_id:
                    import database
                    proj = database.get_highlight_project(project_id)
                    if proj and proj.get('status') == 'cancelled':
                        print(f"  [Kill Switch] Generation cancelled by user. Terminating worker loop.")
                        update_status('cancelled', stage_message='Generation cancelled by user.')
                        return None
                        

                moment = filtered_moments[moment_index]
                added = f"+{moment.added_time}" if moment.added_time else ""
                
                # ── Half Change Detection ──
                if moment.minute <= 45:
                    moment_half = 1
                elif moment.minute <= 90:
                    moment_half = 2
                else:
                    moment_half = 3
                if current_half != moment_half:
                    previous_half = current_half
                    current_half = moment_half
                    print(f"\n  [Halftime] Entering Half {current_half} (was {previous_half}).")
                    
                    # Try DB cache for this specific half first
                    cached_offset_for_half = None
                    if user_id:
                        import database
                        cached = database.get_cached_offsets(user_id, os.path.basename(video_path))
                        if cached:
                            cached_offset_for_half = cached.get('half_1_offset') if current_half == 1 else cached.get('half_2_offset')
                    
                    if cached_offset_for_half is not None:
                        video_offset = cached_offset_for_half
                        print(f"  [Cache Hit] Loaded half {current_half} offset from database: {video_offset:+.0f}s")
                    elif video_offset is not None:
                        # KEEP the current offset — don't reset to None!
                        # The batch verifier will detect desync and corrective navigation will fix it.
                        # This prevents the catastrophic scenario where recalibration lands in the halftime break.
                        print(f"  [Halftime] Carrying forward offset {video_offset:+.0f}s (batch verifier will validate)")
                    else:
                        print(f"  [Halftime] No offset available. Will calibrate from scratch.")
                
                # ══════════════════════════════════════════════════════════
                # STEP 1: INITIAL CALIBRATION (if no offset yet)
                # ══════════════════════════════════════════════════════════
                if video_offset is None:
                    # Check DB cache first (in case we didn't check it yet on first loop iteration)
                    if user_id:
                        import database
                        cached = database.get_cached_offsets(user_id, os.path.basename(video_path))
                        if cached:
                            cached_offset = cached.get('half_1_offset') if current_half == 1 else cached.get('half_2_offset')
                            if cached_offset is not None:
                                video_offset = cached_offset
                                print(f"  [Cache Hit] Loaded offset from database: {video_offset:+.0f}s")
                                
                    if video_offset is None:
                        print(f"\n{'='*70}")
                        print(f"  CALIBRATION -- Reading scoreboard to sync video timestamps")
                        print(f"  Using moment: {moment.minute}'{added} -- {moment.moment_type}")
                        print(f"{'='*70}")
                        update_status('calibrating', stage_message='Syncing video timeline...')
                        
                        est_ts = timestamp.estimate_video_timestamp(
                            moment.minute, video_duration, half, moment.added_time
                        )
                        
                        # Use navigate_to_minute to find the exact video position
                        target_nav_seconds = getattr(moment, 'absolute_seconds', moment.minute * 60)
                        navigated_ts = vision_reasoning.navigate_to_minute(
                            video_path, target_nav_seconds, est_ts, video.extract_frame_base64, video_duration
                        )
                        
                        # Calculate the offset
                        match_seconds = getattr(moment, 'match_seconds', getattr(moment, 'absolute_seconds', moment.minute * 60))
                        video_offset = navigated_ts - match_seconds
                        print(f"  [Calibration] Video offset = {video_offset:+.0f}s")
                        print(f"    Match time {moment.minute}'{added} -> Video time {navigated_ts:.0f}s")
                        update_status('calibrated', stage_message=f'Timeline synced. Offset: {video_offset:+.0f}s')
                        
                        # Cache in DB
                        if user_id:
                            import database
                            h1_val = video_offset if current_half == 1 else None
                            h2_val = video_offset if current_half == 2 else None
                            
                            # Fetch existing cache first so we don't overwrite the other half's offset
                            existing = database.get_cached_offsets(user_id, os.path.basename(video_path))
                            if existing:
                                if current_half == 1:
                                    h2_val = existing.get('half_2_offset')
                                else:
                                    h1_val = existing.get('half_1_offset')
                            
                            database.cache_calibration_offsets(user_id, os.path.basename(video_path), h1_val, h2_val)
                
                # ══════════════════════════════════════════════════════════
                # STEP 2: COLLECT BATCH (up to 9 minor moments)
                # ══════════════════════════════════════════════════════════
                # Scan forward from current position, collecting minor events for batch verification.
                # Major events break the batch immediately and get individual Vision AI treatment.
                
                batch_moments = []
                major_moment = None
                scan_idx = moment_index
                
                while scan_idx < len(filtered_moments) and len(batch_moments) < 9:
                    m = filtered_moments[scan_idx]
                    
                    # Check if we crossed a half boundary
                    if m.minute <= 45:
                        m_half = 1
                    elif m.minute <= 90:
                        m_half = 2
                    else:
                        m_half = 3
                        
                    if m_half != current_half:
                        break  # Stop batch, will recalibrate on next iteration
                    
                    if m.moment_type in MAJOR_EVENTS:
                        if scan_idx == moment_index:
                            # The very first moment IS a major event — process it individually
                            major_moment = m
                            scan_idx += 1
                        break  # Stop collecting batch
                    
                    batch_moments.append((scan_idx, m))
                    scan_idx += 1
                
                # ══════════════════════════════════════════════════════════
                # PATH A: MAJOR EVENT → Full Vision AI (8-frame grid + replay hunt)
                # ══════════════════════════════════════════════════════════
                if major_moment:
                    m = major_moment
                    m_added = f"+{m.added_time}" if m.added_time else ""
                    i = moment_index
                    
                    print(f"\n{'*'*70}")
                    print(f"  [MAJOR] EVENT {i+1}/{len(filtered_moments)}: {m.minute}'{m_added} -- {m.moment_type.upper()}")
                    print(f"  Player: {m.player}")
                    print(f"  Details: {m.details}")
                    print(f"{'*'*70}")
                    update_status('cutting', current_moment_index=moment_index, stage_message=f'Processing {m.moment_type} at {m.minute}\'')
                    
                    # Use calibrated offset if we have one (saves 2-5 API calls)
                    abs_sec_major = getattr(m, 'absolute_seconds', m.minute * 60)
                    if video_offset is not None:
                        est_ts = abs_sec_major + video_offset
                        print(f"  [Fast Nav] Using calibrated offset → video {est_ts:.0f}s")
                    else:
                        est_ts = timestamp.estimate_video_timestamp(
                            m.minute, video_duration, half, m.added_time
                        )
                    
                    moment_context = {
                        "minute": m.minute,
                        "type": m.moment_type,
                        "player": m.player,
                        "details": m.details,
                        "added_time": m.added_time,
                        "expected_score": m.expected_score_before,
                        "intent_data": intent_data
                    }
                    
                    print(f"  [Vision AI] Full 8-frame grid analysis for {m.moment_type}...")
                    clips, new_score, new_offset = vision_reasoning.analyze_moment(
                        video_path, est_ts, moment_context,
                        video.create_frame_grid_base64, video.extract_frame_base64,
                        video_duration=video_duration
                    )
                    
                    # Update offset from Vision AI's navigation
                    if new_offset is not None:
                        video_offset = new_offset
                        print(f"  [Calibration] Offset refreshed from major event: {video_offset:+.0f}s")
                    
                    if not clips:
                        print(f"\n  ⏭ SKIPPING major event — could not locate in video.")
                        moment_index = scan_idx
                        continue
                    
                    # Cut clips for major event
                    for clip_idx, clip in enumerate(clips):
                        start = clip["start"]
                        end = clip["end"]
                        clip_path = os.path.join(self.output_dir, f"clip_{i}_{clip_idx}.mp4")
                        duration = end - start
                        print(f"\n  Cutting clip {clip_idx+1}/{len(clips)} ({clip['type']}): {start:.0f}s → {end:.0f}s ({duration:.0f}s)")
                        
                        video.cut_clip(video_path, start, end, clip_path)
                        
                        if os.path.exists(clip_path) and os.path.getsize(clip_path) > 0:
                            clip_paths.append(clip_path)
                            print(f"  ✓ Clip saved ({os.path.getsize(clip_path) / 1024:.0f} KB)")
                            gcs_blob = self._checkpoint_clip(clip_path, user_id, project_id, os.path.basename(clip_path))
                            timeline_state.append({
                                "id": f"moment_{i}_clip_{clip_idx}",
                                "type": m.moment_type,
                                "moment_type": m.moment_type,
                                "player": m.player,
                                "clip_type": clip["type"],
                                "start": start,
                                "end": end,
                                "minute": m.minute,
                                "source_video": video_path,
                                "output_file": clip_path,
                                "gcs_clip_path": gcs_blob,
                                "reasoning": clip["reasoning"]
                            })
                            update_status('cutting', current_moment_index=moment_index, timeline_state=timeline_state)
                        else:
                            print(f"  ✗ WARNING: Clip file is empty or missing!")
                    
                    moment_index = scan_idx
                    continue
                
                # ══════════════════════════════════════════════════════════
                # PATH B: BATCH OF MINOR EVENTS → 4x4 Verification Grid + Dumb Cuts
                # ══════════════════════════════════════════════════════════
                if not batch_moments:
                    moment_index = scan_idx
                    continue
                
                print(f"\n{'='*70}")
                print(f"  [BATCH] VERIFICATION -- {len(batch_moments)} minor moments")
                print(f"  Moments: {batch_moments[0][1].minute}' to {batch_moments[-1][1].minute}'")
                print(f"  Current video offset: {video_offset:+.0f}s")
                print(f"{'='*70}")
                update_status('cutting', current_moment_index=moment_index, stage_message=f'Verifying batch of {len(batch_moments)} moments...')
                
                # Calculate estimated video timestamps for each moment using the offset
                batch_video_timestamps = []
                batch_expected_minutes = []
                
                for _, m in batch_moments:
                    abs_sec = getattr(m, 'absolute_seconds', m.minute * 60)
                    est_video_ts = abs_sec + video_offset
                    batch_video_timestamps.append(est_video_ts)
                    
                    mins = abs_sec // 60
                    secs = abs_sec % 60
                    batch_expected_minutes.append(f"{int(mins):02d}:{int(secs):02d}")
                
                for idx, (_, m) in enumerate(batch_moments):
                    print(f"    F{idx+1}: {m.minute}' {m.moment_type} → Video {batch_video_timestamps[idx]:.0f}s (expect {batch_expected_minutes[idx]})")
                
                # Create the 4x4 verification grid
                grid_b64 = video.create_batch_verification_grid(
                    video_path, batch_video_timestamps, batch_expected_minutes
                )
                
                if not grid_b64:
                    print(f"  ✗ Failed to create verification grid. Falling back to individual processing.")
                    moment_index = scan_idx
                    continue
                
                # Save debug grid
                if os.getenv("GRID_DEBUG") == "true":
                    os.makedirs("grid_debug", exist_ok=True)
                    import base64
                    batch_label = f"batch_verify_half{current_half}_min{batch_moments[0][1].minute}"
                    with open(f"grid_debug/{batch_label}.jpg", "wb") as f:
                        f.write(base64.b64decode(grid_b64))
                
                # Send to Vision AI for sync verification
                sync_result = vision_reasoning.batch_verify_sync(grid_b64, batch_expected_minutes)
                
                if sync_result["all_synced"]:
                    # ── ALL IN SYNC → Dumb cut everything! ──
                    print(f"\n  ✓ ALL {len(batch_moments)} FRAMES IN SYNC! Dumb cutting entire batch...")
                    
                    for idx, (orig_idx, m) in enumerate(batch_moments):
                        abs_sec = getattr(m, 'absolute_seconds', m.minute * 60)
                        cut_ts = abs_sec + video_offset
                        
                        moment_type_lower = m.moment_type.lower()
                        short_cut_types = ["pass", "ball touch", "dispossessed", "corner awarded", "aerial"]
                        
                        if any(t in moment_type_lower for t in short_cut_types):
                            start = max(0, cut_ts - 6)
                            end = cut_ts + 5
                        else:
                            start = max(0, cut_ts - 10)
                            end = cut_ts + 5
                            
                        clip_path = os.path.join(self.output_dir, f"clip_{orig_idx}_0.mp4")
                        
                        print(f"    ✂ {m.minute}' {m.moment_type}: {start:.0f}s → {end:.0f}s")
                        video.cut_clip(video_path, start, end, clip_path)
                        
                        if os.path.exists(clip_path) and os.path.getsize(clip_path) > 0:
                            clip_paths.append(clip_path)
                            gcs_blob = self._checkpoint_clip(clip_path, user_id, project_id, os.path.basename(clip_path))
                            timeline_state.append({
                                "id": f"moment_{orig_idx}_clip_0",
                                "type": m.moment_type,
                                "moment_type": m.moment_type,
                                "player": m.player,
                                "clip_type": "live",
                                "start": start,
                                "end": end,
                                "minute": m.minute,
                                "source_video": video_path,
                                "output_file": clip_path,
                                "gcs_clip_path": gcs_blob,
                                "reasoning": f"Batch verified in sync. Dumb cut at offset {video_offset:+.0f}s."
                            })
                            update_status('cutting', current_moment_index=moment_index, timeline_state=timeline_state)
                    
                    moment_index = scan_idx
                
                else:
                    # ── DESYNC DETECTED → Corrective navigation ──
                    desync_frame = sync_result["first_desync_frame"]
                    
                    if desync_frame is None:
                        # All real frames are synced but AI hallucinated phantom desyncs
                        # Treat as all synced — dumb cut everything
                        print(f"\n  ✓ All real frames synced (phantom desyncs in empty grid cells). Dumb cutting batch...")
                        for idx, (orig_idx, m) in enumerate(batch_moments):
                            abs_sec = getattr(m, 'absolute_seconds', m.minute * 60)
                            cut_ts = abs_sec + video_offset
                            moment_type_lower = m.moment_type.lower()
                            short_cut_types = ["pass", "ball touch", "dispossessed", "corner awarded", "aerial"]
                            if any(t in moment_type_lower for t in short_cut_types):
                                start = max(0, cut_ts - 6)
                                end = cut_ts + 5
                            else:
                                start = max(0, cut_ts - 10)
                                end = cut_ts + 5
                            clip_path = os.path.join(self.output_dir, f"clip_{orig_idx}_0.mp4")
                            print(f"    ✂ {m.minute}' {m.moment_type}: {start:.0f}s → {end:.0f}s")
                            video.cut_clip(video_path, start, end, clip_path)
                            if os.path.exists(clip_path) and os.path.getsize(clip_path) > 0:
                                clip_paths.append(clip_path)
                                gcs_blob = self._checkpoint_clip(clip_path, user_id, project_id, os.path.basename(clip_path))
                                timeline_state.append({
                                    "id": f"moment_{orig_idx}_clip_0",
                                    "type": m.moment_type,
                                    "moment_type": m.moment_type,
                                    "player": m.player,
                                    "clip_type": "live",
                                    "start": start,
                                    "end": end,
                                    "minute": m.minute,
                                    "source_video": video_path,
                                    "output_file": clip_path,
                                    "gcs_clip_path": gcs_blob,
                                    "reasoning": f"Forced dumb cut at offset {video_offset:+.0f}s."
                                })
                                update_status('cutting', current_moment_index=moment_index, timeline_state=timeline_state)
                        moment_index = scan_idx
                        continue
                    
                    desync_batch_idx = max(0, desync_frame - 1)
                    
                    # Check retry limit
                    retries = retry_counts.get(moment_index, 0)
                    if retries >= 2:
                        print(f"\n  ⚠ RETRY LIMIT REACHED for batch at moment {moment_index}. Dumb cutting with current offset and moving on.")
                        for idx, (orig_idx, m) in enumerate(batch_moments):
                            abs_sec = getattr(m, 'absolute_seconds', m.minute * 60)
                            cut_ts = abs_sec + video_offset
                            moment_type_lower = m.moment_type.lower()
                            short_cut_types = ["pass", "ball touch", "dispossessed", "corner awarded", "aerial"]
                            if any(t in moment_type_lower for t in short_cut_types):
                                start = max(0, cut_ts - 6)
                                end = cut_ts + 5
                            else:
                                start = max(0, cut_ts - 10)
                                end = cut_ts + 5
                            clip_path = os.path.join(self.output_dir, f"clip_{orig_idx}_0.mp4")
                            print(f"    ✂ {m.minute}' {m.moment_type}: {start:.0f}s → {end:.0f}s (forced)")
                            video.cut_clip(video_path, start, end, clip_path)
                            if os.path.exists(clip_path) and os.path.getsize(clip_path) > 0:
                                clip_paths.append(clip_path)
                                gcs_blob = self._checkpoint_clip(clip_path, user_id, project_id, os.path.basename(clip_path))
                                timeline_state.append({
                                    "id": f"moment_{orig_idx}_clip_0",
                                    "type": m.moment_type,
                                    "moment_type": m.moment_type,
                                    "player": m.player,
                                    "clip_type": "live",
                                    "start": start,
                                    "end": end,
                                    "minute": m.minute,
                                    "source_video": video_path,
                                    "output_file": clip_path,
                                    "gcs_clip_path": gcs_blob,
                                    "reasoning": f"Retry limit reached. Forced cut at offset {video_offset:+.0f}s."
                                })
                                update_status('cutting', current_moment_index=moment_index, timeline_state=timeline_state)
                        moment_index = scan_idx
                        continue
                    
                    print(f"\n  ⚠ DESYNC at Frame {desync_frame}!")
                    print(f"    Dumb cutting frames 1-{desync_frame - 1} (verified synced)...")
                    
                    # Dumb cut everything BEFORE the desync point (they were verified)
                    for idx, (orig_idx, m) in enumerate(batch_moments):
                        if idx >= desync_batch_idx:
                            break
                        
                        abs_sec = getattr(m, 'absolute_seconds', m.minute * 60)
                        cut_ts = abs_sec + video_offset
                        moment_type_lower = m.moment_type.lower()
                        short_cut_types = ["pass", "ball touch", "dispossessed", "corner awarded", "aerial"]
                        if any(t in moment_type_lower for t in short_cut_types):
                            start = max(0, cut_ts - 6)
                            end = cut_ts + 5
                        else:
                            start = max(0, cut_ts - 10)
                            end = cut_ts + 5
                        clip_path = os.path.join(self.output_dir, f"clip_{orig_idx}_0.mp4")
                        
                        print(f"    ✂ {m.minute}' {m.moment_type}: {start:.0f}s → {end:.0f}s")
                        video.cut_clip(video_path, start, end, clip_path)
                        
                        if os.path.exists(clip_path) and os.path.getsize(clip_path) > 0:
                            clip_paths.append(clip_path)
                            gcs_blob = self._checkpoint_clip(clip_path, user_id, project_id, os.path.basename(clip_path))
                            timeline_state.append({
                                "id": f"moment_{orig_idx}_clip_0",
                                "type": m.moment_type,
                                "moment_type": m.moment_type,
                                "player": m.player,
                                "clip_type": "live",
                                "start": start,
                                "end": end,
                                "minute": m.minute,
                                "source_video": video_path,
                                "output_file": clip_path,
                                "gcs_clip_path": gcs_blob,
                                "reasoning": f"Pre-desync verified cut at offset {video_offset:+.0f}s."
                            })
                            update_status('cutting', current_moment_index=moment_index, timeline_state=timeline_state)
                    
                    # Recalibrate at the desynced moment
                    desync_orig_idx, desync_moment = batch_moments[desync_batch_idx]
                    print(f"\n  [Corrective Navigation] Recalibrating at minute {desync_moment.minute}'...")
                    
                    # Use current offset as starting point (what we learned), not a blind estimate
                    target_nav_seconds = getattr(desync_moment, 'absolute_seconds', desync_moment.minute * 60)
                    est_ts = target_nav_seconds + video_offset
                    navigated_ts = vision_reasoning.navigate_to_minute(
                        video_path, target_nav_seconds, est_ts, video.extract_frame_base64, video_duration
                    )
                    
                    # Update the offset
                    match_seconds = getattr(desync_moment, 'match_seconds', getattr(desync_moment, 'absolute_seconds', desync_moment.minute * 60))
                    old_offset = video_offset
                    video_offset = navigated_ts - match_seconds
                    print(f"  [Corrective Navigation] ✓ New offset = {video_offset:+.0f}s")
                    
                    # Cache the corrected offset for this half so future runs skip the halftime nightmare
                    if user_id:
                        import database
                        h1_val = video_offset if current_half == 1 else None
                        h2_val = video_offset if current_half == 2 else None
                        existing = database.get_cached_offsets(user_id, os.path.basename(video_path))
                        if existing:
                            if current_half == 1:
                                h2_val = existing.get('half_2_offset')
                            else:
                                h1_val = existing.get('half_1_offset')
                        database.cache_calibration_offsets(user_id, os.path.basename(video_path), h1_val, h2_val)
                        print(f"  [Cache] Saved corrected half {current_half} offset to database")
                    
                    if abs(old_offset - video_offset) < 1:
                        print(f"  [Corrective Navigation] ✓ Math mathematically verified. Skipping redundant retries.")
                        retry_counts[moment_index] = 2
                    else:
                        retry_counts[moment_index] = retries + 1
                    
                    # Resume processing from the desynced moment onward (will be picked up in next iteration)
                    moment_index = desync_orig_idx
                    continue
                
    
            except Exception as e:
                import traceback
                print(f"  [Orchestrator] CRITICAL ERROR processing moment {moment_index}: {e}")
                traceback.print_exc()
                moment_index = scan_idx if 'scan_idx' in locals() and scan_idx > moment_index else moment_index + 1
                continue
        # ── Calculate final stitched video timestamps for frontend navigation ──
        current_final_time = 0.0
        for clip in timeline_state:
            clip["final_start"] = current_final_time
            duration = clip["end"] - clip["start"]
            current_final_time += duration

        # ── Export Timeline State ──
        timeline_file = os.path.join(self.output_dir, "timeline.json")
        with open(timeline_file, "w") as f:
            json.dump(timeline_state, f, indent=2)
        print(f"\n  [OK] Exported timeline state to {timeline_file}")
        update_status('rendering', stage_message=f'Stitching {len(clip_paths)} clips into final reel...')
        
        # ── Step E: Concatenate all clips ──
        # Generate a clean filename based on the prompt/match name
        import re
        safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', (intent_data.get('match_name') or prompt).replace(' ', '_'))
        output_filename = f"{safe_name}.mp4"
        final_output = os.path.join(self.output_dir, output_filename)
        
        print(f"\n{'*'*70}")
        print(f"  FINAL ASSEMBLY")
        print(f"  Joining {len(clip_paths)} clips into final highlight reel...")
        for i, cp in enumerate(clip_paths):
            print(f"    Clip {i+1}: {cp}")
        print(f"  Output: {final_output}")
        print(f"{'*'*70}")
        
        if clip_paths:
            video.concat_clips(clip_paths, final_output)
            if os.path.exists(final_output):
                size_mb = os.path.getsize(final_output) / (1024 * 1024)
                print(f"\n  [OK] FINAL HIGHLIGHTS READY -- {size_mb:.1f} MB")
            else:
                print(f"\n  [ERROR] Final output file not created!")
        else:
            print(f"\n  [ERROR] No clips were generated!")
        
        print(f"\n{'#'*70}")
        print(f"  PIPELINE COMPLETE")
        print(f"{'#'*70}\n")
        
        # ── Upload to GCS and update project status ──
        gcs_video_url = f"/outputs/{os.path.basename(final_output)}"
        if user_id and project_id:
            self.upload_to_gcs(timeline_file, f"{user_id}/projects/{project_id}/timeline.json")
            gcs_video_url = self.upload_to_gcs(final_output, f"{user_id}/projects/{project_id}/{output_filename}")
            
            # ── Cleanup: Delete temporary checkpoint clips from GCS ──
            self._cleanup_checkpoint_clips(user_id, project_id)
            
        update_status('complete', video_url=gcs_video_url, timeline_state=timeline_state)
            
        return final_output

    def _checkpoint_clip(self, clip_path: str, user_id: str, project_id: str, clip_name: str):
        """Upload a single clip to GCS as a checkpoint for crash recovery."""
        if not user_id or not project_id:
            return None
        blob_name = f"{user_id}/projects/{project_id}/clips/{clip_name}"
        return self.upload_to_gcs(clip_path, blob_name)

    def _cleanup_checkpoint_clips(self, user_id: str, project_id: str):
        """Delete all temporary checkpoint clips from GCS after successful final upload."""
        prefix = f"{user_id}/projects/{project_id}/clips/"
        try:
            from google.cloud import storage
            client = storage.Client()
            bucket = client.bucket("tuc-ai-raw-uploads")
            blobs = list(bucket.list_blobs(prefix=prefix))
            if blobs:
                for blob in blobs:
                    blob.delete()
                print(f"\n  🧹 Cleaned up {len(blobs)} checkpoint clips from GCS.")
        except Exception as e:
            print(f"  ⚠ Checkpoint cleanup failed: {e}")

    def upload_to_gcs(self, local_path: str, blob_name: str) -> str:
        """Upload a local file to GCS and return a signed URL."""
        try:
            from google.cloud import storage
            from google.oauth2 import service_account
            import datetime
            
            # Use explicit service account credentials for signing
            sa_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "gcp-credentials.json")
            if os.path.exists(sa_path):
                credentials = service_account.Credentials.from_service_account_file(sa_path)
                storage_client = storage.Client(credentials=credentials)
            else:
                storage_client = storage.Client()
                
            bucket = storage_client.bucket("tuc-ai-raw-uploads")
            blob = bucket.blob(blob_name)
            
            print(f"Uploading {local_path} to GCS: {blob_name}...")
            blob.upload_from_filename(local_path)
            print("Upload complete!")
            
            # Generate signed URL valid for 7 days
            url = blob.generate_signed_url(
                version="v4",
                expiration=datetime.timedelta(days=7),
                method="GET"
            )
            return url
        except Exception as e:
            print(f"GCS upload failed for {local_path}: {e}")
            return f"/outputs/{os.path.basename(local_path)}"

    def render_from_timeline(self, video_path: str, user_id: str = None, project_id: str = None, token: str = None, timeline_state: list = None) -> str:
        """
        Fast-path rendering: reads timeline state, re-cuts based on updated timestamps, 
        concatenates, and uploads the final output to GCS.
        """
        print(f"\n{'#'*70}")
        print(f"  FAST RE-RENDER STARTING")
        print(f"{'#'*70}\n")
        
        # 1. Use GCS FUSE or fallback to download
        fuse_path = f"/mnt/gcs/{video_path}"
        if os.path.exists(fuse_path):
            local_video_path = fuse_path
            print(f"Using GCS FUSE mount for fast re-render: {local_video_path}")
        else:
            local_video_path = video_path
            downloaded_from_gcs = False
            if not os.path.exists(local_video_path) and not local_video_path.startswith("/tmp/"):
                local_video_path = f"/tmp/{os.path.basename(video_path)}"
                try:
                    from google.cloud import storage
                    print(f"Downloading source video from GCS to {local_video_path}...")
                    storage_client = storage.Client()
                    bucket = storage_client.bucket("tuc-ai-raw-uploads")
                    blob = bucket.blob(video_path)
                    blob.download_to_filename(local_video_path)
                    downloaded_from_gcs = True
                    print("Download complete!")
                except Exception as e:
                    print(f"Failed to download source video from GCS: {e}")
                    # Fallback to whatever path was given
                    local_video_path = video_path
                
        # 2. Get timeline state (either passed directly or loaded from GCS/local)
        if not timeline_state:
            # Try to load timeline.json from GCS first
            if user_id and project_id:
                try:
                    from google.cloud import storage
                    storage_client = storage.Client()
                    bucket = storage_client.bucket("tuc-ai-raw-uploads")
                    blob = bucket.blob(f"{user_id}/projects/{project_id}/timeline.json")
                    timeline_state = json.loads(blob.download_as_bytes())
                    print("Loaded timeline state from GCS.")
                except Exception as e:
                    print(f"Failed to load timeline from GCS: {e}")
            
            # Fallback to local file
            if not timeline_state:
                timeline_file = os.path.join(self.output_dir, "timeline.json")
                if not os.path.exists(timeline_file):
                    raise FileNotFoundError(f"Timeline state not found locally or in cloud storage.")
                with open(timeline_file, "r") as f:
                    timeline_state = json.load(f)
                    
        clip_paths = []
        try:
            for clip in timeline_state:
                # Resolve local output path for the clip (ensure it's in the outputs folder)
                filename = os.path.basename(clip["output_file"])
                clip_path = os.path.join(self.output_dir, filename)
                start = clip["start"]
                end = clip["end"]
                
                print(f"  Cutting {clip['id']} ({clip['clip_type']}) from {start}s to {end}s...")
                video.cut_clip(local_video_path, start, end, clip_path)
                
                if os.path.exists(clip_path) and os.path.getsize(clip_path) > 0:
                    clip_paths.append(clip_path)
                else:
                    print(f"  ✗ WARNING: Re-cut clip file is empty or missing!")
                    
            import time
            final_output = os.path.join(self.output_dir, f"final_highlights_{int(time.time())}.mp4")
            if clip_paths:
                print(f"  Joining {len(clip_paths)} clips into final highlight reel...")
                video.concat_clips(clip_paths, final_output)
                print(f"\n  ✓ FAST RE-RENDER COMPLETE!")
                
                # 3. Upload output to GCS and update Supabase project status
                gcs_video_url = f"/outputs/{os.path.basename(final_output)}"
                if user_id and project_id:
                    # Upload updated timeline state to GCS
                    temp_timeline_path = os.path.join(self.output_dir, "timeline.json")
                    with open(temp_timeline_path, "w") as f:
                        json.dump(timeline_state, f, indent=2)
                    self.upload_to_gcs(temp_timeline_path, f"{user_id}/projects/{project_id}/timeline.json")
                    
                    # Upload final highlights video to GCS
                    gcs_video_url = self.upload_to_gcs(final_output, f"{user_id}/projects/{project_id}/{os.path.basename(final_output)}")
                    
                    # Update status in database
                    import database
                    database.update_project_status(project_id, 'complete', video_url=gcs_video_url, timeline_state=timeline_state, token=token)
                
                return gcs_video_url
            else:
                raise Exception("No valid clips were re-cut.")
        finally:
            # Clean up source video from temp disk if we downloaded it
            if downloaded_from_gcs and os.path.exists(local_video_path):
                try:
                    os.remove(local_video_path)
                    print(f"Cleaned up downloaded source video: {local_video_path}")
                except Exception as e:
                    print(f"Error cleaning up source video: {e}")
