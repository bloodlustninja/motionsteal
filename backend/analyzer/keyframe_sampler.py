"""
Keyframe Frame Sampler Module
Extracts exactly 3 frames from video for semantic state-diffing.
"""

import cv2
import numpy as np
from typing import Dict, List, Optional
import base64


class KeyframeSampler:
    """
    Extracts 3 keyframes for state-diffing analysis.
    """

    def __init__(self):
        """Initialize keyframe sampler."""
        pass

    def extract_keyframes(
        self,
        video_path: str,
        roi: Optional[Dict[str, int]] = None
    ) -> Dict:
        """
        Extract 3 keyframes at specific timestamps.
        
        Args:
            video_path: Path to video file
            roi: Optional region of interest for cropping
            
        Returns:
            Dictionary with base64-encoded keyframe crops
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError("Could not open video file")

        try:
            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0:
                fps = 30.0

            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = total_frames / fps

            # Calculate timestamps
            # Frame 0: Idle/Rest at t = 0.05s
            t_idle = min(0.05, duration * 0.05)
            # Frame 1: Apex/Morph at t = 0.45 * duration
            t_apex = duration * 0.45
            # Frame 2: Settled/Expanded at t = 0.90 * duration
            t_settled = duration * 0.90

            # Extract frames
            keyframes = {}
            timestamps = {
                "idle": t_idle,
                "apex": t_apex,
                "settled": t_settled
            }

            for name, t in timestamps.items():
                frame_num = int(t * fps)
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
                ret, frame = cap.read()
                if ret:
                    # Crop to ROI if provided
                    if roi:
                        x, y, w, h = roi["x"], roi["y"], roi["w"], roi["h"]
                        frame = frame[y:y+h, x:x+w]

                    # Encode as PNG
                    _, buffer = cv2.imencode('.png', frame)
                    keyframes[name] = base64.b64encode(buffer).decode('utf-8')
                else:
                    keyframes[name] = None

            return {
                "timestamps": timestamps,
                "keyframes": keyframes,
                "duration": duration,
                "fps": fps
            }

        finally:
            cap.release()


def extract_keyframes_from_video(
    video_path: str,
    roi: Optional[Dict[str, int]] = None
) -> Dict:
    """
    Extract 3 keyframes for state-diffing analysis.
    
    Args:
        video_path: Path to video file
        roi: Optional region of interest
        
    Returns:
        Dictionary with keyframe data
    """
    sampler = KeyframeSampler()
    return sampler.extract_keyframes(video_path, roi)
