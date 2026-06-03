import cv2
import numpy as np
from pathlib import Path

def main():
    output_dir = Path("datasets/raw")
    output_dir.mkdir(parents=True, exist_ok=True)
    video_path = output_dir / "my_video.mp4"
    
    # 5 seconds of video at 25 fps
    fps = 25
    width, height = 640, 480
    num_frames = fps * 5
    
    # Use MP4V codec which is standard and widely supported
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(video_path), fourcc, fps, (width, height))
    
    if not out.isOpened():
        print("Error: Could not open VideoWriter.")
        return
        
    for i in range(num_frames):
        # Create a basic gray background frame
        frame = np.ones((height, width, 3), dtype=np.uint8) * 128
        
        # Draw a moving shape (circle)
        x = 50 + int((width - 100) * (i / num_frames))
        y = height // 2
        cv2.circle(frame, (x, y), 40, (0, 255, 0), -1)
        
        # Add some text
        cv2.putText(frame, f"VisionRetail Mock Feed - Frame {i}", (30, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        out.write(frame)
        
    out.release()
    print(f"Success: Mock video generated at {video_path.absolute()}")

if __name__ == "__main__":
    main()
