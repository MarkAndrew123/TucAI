import subprocess
import base64
import os
import cv2
import numpy as np

def extract_frame_base64(video_path: str, timestamp: float) -> str:
    """Extracts a frame using OpenCV."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return ""
    
    video_fps = cap.get(cv2.CAP_PROP_FPS)
    if video_fps <= 0:
        video_fps = 30
        
    target_frame = int(timestamp * video_fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
    ret, frame = cap.read()
    cap.release()
    
    if ret:
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return base64.b64encode(buffer).decode('utf-8')
    return ""

def create_frame_grid_base64(video_path: str, start_ts: float, interval_secs: float = 1.0, num_frames: int = 8) -> str:
    """Uses OpenCV to create a grid (e.g. 4x2 for 8 frames) of sequential frames with burned-in timestamps."""
    print(f"  [Grid Phase] Extracting {num_frames} frames from {start_ts}s at {interval_secs}s intervals...")
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return ""
        
    video_fps = cap.get(cv2.CAP_PROP_FPS)
    if video_fps <= 0:
        video_fps = 30
        
    frames = []
    for i in range(num_frames):
        target_ts = start_ts + (i * interval_secs)
        target_frame = int(target_ts * video_fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
        ret, frame = cap.read()
        
        # We resize each frame to 480x270 so a 4x2 grid is 1920x540
        frame_width, frame_height = 480, 270
        
        if ret:
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
            
    cap.release()
    
    # Stitch dynamically based on num_frames (assumes 8 frames = 4x2, 4 frames = 2x2)
    if num_frames == 8:
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
    Creates a 3x3 grid of 9 frames, each taken from a specific video timestamp.
    Burns in both the video timestamp AND the expected match minute for AI verification.
    
    Args:
        video_path: Path to the video file.
        timestamps: List of 9 video timestamps (in seconds) to extract frames from.
        expected_minutes: List of 9 strings like "03:24" showing what the scoreboard SHOULD read.
    
    Returns:
        Base64-encoded JPEG of the 3x3 grid.
    """
    num_frames = len(timestamps)
    print(f"  [Batch Grid] Extracting {num_frames} verification frames...")
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return ""
        
    video_fps = cap.get(cv2.CAP_PROP_FPS)
    if video_fps <= 0:
        video_fps = 30
        
    frames = []
    frame_width, frame_height = 480, 270
    
    for i in range(num_frames):
        target_ts = timestamps[i]
        target_frame = int(target_ts * video_fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
        ret, frame = cap.read()
        
        if ret:
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
        
    cap.release()
    
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
    cmd = [
        'ffmpeg', '-y', '-ss', str(start), '-i', input_path,
        '-t', str(duration), '-c', 'copy', '-avoid_negative_ts', '1', output_path
    ]
    subprocess.run(cmd)

def concat_clips(clip_paths: list, output_path: str):
    if not clip_paths:
        return
        
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    list_file = "clips.txt"
    with open(list_file, "w") as f:
        for clip in clip_paths:
            # Escape path properly for ffmpeg or use relative
            abs_path = os.path.abspath(clip).replace('\\', '/')
            f.write(f"file '{abs_path}'\n")
    
    cmd = [
        'ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', list_file,
        '-c', 'copy', output_path
    ]
    subprocess.run(cmd)
    if os.path.exists(list_file):
        os.remove(list_file)
