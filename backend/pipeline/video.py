import subprocess
import base64
import os
import cv2
import numpy as np

def extract_single_frame_ffmpeg(video_path: str, timestamp: float) -> np.ndarray:
    """Uses ffmpeg to extract a single frame extremely fast, returning an OpenCV image array."""
    cmd = [
        'ffmpeg', '-y', '-ss', str(timestamp), '-i', video_path,
        '-vframes', '1', '-q:v', '2', '-f', 'image2pipe', '-vcodec', 'mjpeg', '-'
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=15)
        if result.returncode == 0 and result.stdout:
            nparr = np.frombuffer(result.stdout, np.uint8)
            return cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    except Exception as e:
        print(f"  [FFmpeg] Failed to extract frame at {timestamp}s: {e}")
    return None

def extract_frame_base64(video_path: str, timestamp: float) -> str:
    """Extracts a frame using fast FFmpeg seeking."""
    frame = extract_single_frame_ffmpeg(video_path, timestamp)
    if frame is not None:
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return base64.b64encode(buffer).decode('utf-8')
    return ""

def create_frame_grid_base64(video_path: str, start_ts: float, interval_secs: float = 1.0, num_frames: int = 8) -> str:
    """Uses fast FFmpeg extraction to create a grid of sequential frames with burned-in timestamps."""
    print(f"  [Grid Phase] Extracting {num_frames} frames from {start_ts}s at {interval_secs}s intervals using FFmpeg...")
    
    frames = []
    frame_width, frame_height = 480, 270
    
    for i in range(num_frames):
        target_ts = start_ts + (i * interval_secs)
        frame = extract_single_frame_ffmpeg(video_path, target_ts)
        
        if frame is not None:
            frame = cv2.resize(frame, (frame_width, frame_height))
        else:
            frame = np.zeros((frame_height, frame_width, 3), dtype=np.uint8)
            
        # Burn in the timestamp
        mins = int(target_ts // 60)
        secs = int(target_ts % 60)
        timestamp_str = f"Frame {i+1}: {mins}m {secs}s"
        
        # Add a black background rectangle for text readability
        cv2.rectangle(frame, (5, frame_height - 35), (280, frame_height - 5), (0, 0, 0), -1)
        # Put the text on top
        cv2.putText(frame, timestamp_str, (10, frame_height - 10), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
                    
        frames.append(frame)
    
    # Stitch dynamically based on num_frames
    if num_frames == 9:
        row1 = cv2.hconcat(frames[0:3])
        row2 = cv2.hconcat(frames[3:6])
        row3 = cv2.hconcat(frames[6:9])
        grid = cv2.vconcat([row1, row2, row3])
    elif num_frames == 8:
        row1 = cv2.hconcat(frames[0:4])
        row2 = cv2.hconcat(frames[4:8])
        grid = cv2.vconcat([row1, row2])
    elif num_frames == 4:
        row1 = cv2.hconcat(frames[0:2])
        row2 = cv2.hconcat(frames[2:4])
        grid = cv2.vconcat([row1, row2])
    else:
        # Fallback horizontal concat
        grid = cv2.hconcat(frames)
    
    _, buffer = cv2.imencode('.jpg', grid, [cv2.IMWRITE_JPEG_QUALITY, 85])
    encoded_string = base64.b64encode(buffer).decode('utf-8')
    print(f"  [Grid Phase] Successfully created Image Grid ({num_frames} frames) for AI.")
    return encoded_string

def create_batch_verification_grid(video_path: str, timestamps: list[float], expected_minutes: list[str]) -> str:
    """
    Creates a 3x3 grid of 9 frames using fast FFmpeg extraction.
    Burns in both the video timestamp AND the expected match minute for AI verification.
    """
    num_frames = len(timestamps)
    print(f"  [Batch Grid] Extracting {num_frames} verification frames using FFmpeg...")
    
    frames = []
    frame_width, frame_height = 480, 270
    
    for i in range(num_frames):
        target_ts = timestamps[i]
        frame = extract_single_frame_ffmpeg(video_path, target_ts)
        
        if frame is not None:
            frame = cv2.resize(frame, (frame_width, frame_height))
        else:
            frame = np.zeros((frame_height, frame_width, 3), dtype=np.uint8)
            
        # Burn in: Frame number + expected match minute + video timestamp
        vid_mins = int(target_ts // 60)
        vid_secs = int(target_ts % 60)
        label = f"F{i+1} | Expect: {expected_minutes[i]} | Vid: {vid_mins}m{vid_secs:02d}s"
        
        # Black background for text
        cv2.rectangle(frame, (5, frame_height - 35), (470, frame_height - 5), (0, 0, 0), -1)
        cv2.putText(frame, label, (10, frame_height - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2, cv2.LINE_AA)
                    
        frames.append(frame)
    
    # Stitch into a 3x3 grid
    rows = []
    cols = 3
    for r in range(0, num_frames, cols):
        row_frames = frames[r:r+cols]
        # Pad with black if less than 3 frames in last row
        while len(row_frames) < cols:
            row_frames.append(np.zeros((frame_height, frame_width, 3), dtype=np.uint8))
        rows.append(cv2.hconcat(row_frames))
    
    grid = cv2.vconcat(rows)
    
    _, buffer = cv2.imencode('.jpg', grid, [cv2.IMWRITE_JPEG_QUALITY, 85])
    encoded_string = base64.b64encode(buffer).decode('utf-8')
    print(f"  [Batch Grid] Successfully created 4x4 Verification Grid ({num_frames} frames).")
    return encoded_string

def cut_clip(input_path: str, start: float, end: float, output_path: str):
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    duration = end - start
    try:
        cmd = [
            'ffmpeg', '-y', '-ss', str(start), '-i', input_path,
            '-t', str(duration), '-c', 'copy', '-avoid_negative_ts', '1', output_path
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"  [FFmpeg] Exception cutting clip {output_path}: {e}")

def concat_clips(clip_paths: list, output_path: str):
    if not clip_paths:
        return
        
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    list_file = "clips.txt"
    valid_clips = []
    with open(list_file, "w") as f:
        for clip in clip_paths:
            if os.path.exists(clip):
                # Escape path properly for ffmpeg or use relative
                abs_path = os.path.abspath(clip).replace('\\', '/')
                f.write(f"file '{abs_path}'\n")
                valid_clips.append(clip)
            else:
                print(f"  [FFmpeg] Warning: Skipping missing clip for concatenation: {clip}")
    
    if len(valid_clips) == 0:
        print(f"  [FFmpeg] Error: No valid clips found for concatenation.")
        if os.path.exists(list_file):
            os.remove(list_file)
        return
    
    cmd = [
        'ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', list_file,
        '-c', 'copy', output_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if os.path.exists(list_file):
        os.remove(list_file)
