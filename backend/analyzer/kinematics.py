"""
Kinematics Module - Optical Flow & CSRT Tracking
Handles translation, scale, and rotation tracking using classical OpenCV methods.
"""

import cv2
import numpy as np
from typing import List, Dict, Tuple, Optional


class KinematicsTracker:
    """Multi-modal tracker combining CSRT and optical flow for robust tracking."""

    def __init__(self, roi: Dict[str, int]):
        """
        Initialize tracker with ROI.
        
        Args:
            roi: Dictionary with 'x', 'y', 'w', 'h' keys
        """
        self.roi = roi
        self.tracker = None
        self.prev_gray = None
        self.prev_features = None
        self.initialized = False

    def initialize(self, frame: np.ndarray) -> bool:
        """
        Initialize CSRT tracker and optical flow features.
        
        Args:
            frame: First frame to initialize tracking on
            
        Returns:
            True if initialization successful
        """
        try:
            # Initialize CSRT tracker
            self.tracker = cv2.TrackerCSRT_create()
            bbox = (self.roi["x"], self.roi["y"], self.roi["w"], self.roi["h"])
            success = self.tracker.init(frame, bbox)
            
            if not success:
                return False

            # Initialize optical flow features
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            roi_mask = np.zeros_like(gray)
            roi_mask[
                self.roi["y"]:self.roi["y"]+self.roi["h"],
                self.roi["x"]:self.roi["x"]+self.roi["w"]
            ] = 255
            
            # Shi-Tomasi feature detection
            self.prev_features = cv2.goodFeaturesToTrack(
                gray,
                mask=roi_mask,
                maxCorners=100,
                qualityLevel=0.01,
                minDistance=5
            )
            
            self.prev_gray = gray
            self.initialized = True
            return True
            
        except Exception as e:
            print(f"Kinematics initialization error: {e}")
            return False

    def track_frame(self, frame: np.ndarray) -> Optional[Dict]:
        """
        Track object in frame using CSRT + optical flow fallback.
        
        Args:
            frame: Current frame to track
            
        Returns:
            Dictionary with 'success', 'bbox', 'center', 'scale', 'rotation'
        """
        if not self.initialized:
            return None

        result = {
            "success": False,
            "bbox": None,
            "center": None,
            "scale": 1.0,
            "rotation": 0.0
        }

        try:
            # Try CSRT tracker first
            success, bbox = self.tracker.update(frame)
            
            if success:
                x, y, w, h = [int(v) for v in bbox]
                result["success"] = True
                result["bbox"] = bbox
                result["center"] = {"x": x + w/2, "y": y + h/2}
                result["scale"] = (w * h) / (self.roi["w"] * self.roi["h"])
                
                # Calculate rotation using optical flow
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                if self.prev_features is not None and len(self.prev_features) > 4:
                    curr_features, status, _ = cv2.calcOpticalFlowPyrLK(
                        self.prev_gray, gray, self.prev_features, None
                    )
                    
                    good_prev = self.prev_features[status == 1]
                    good_curr = curr_features[status == 1]
                    
                    if len(good_prev) > 4:
                        # Estimate affine transform for rotation
                        matrix, _ = cv2.estimateAffinePartial2D(good_prev, good_curr)
                        if matrix is not None:
                            angle_rad = np.arctan2(matrix[0, 1], matrix[0, 0])
                            result["rotation"] = float(np.degrees(angle_rad))
                
                self.prev_gray = gray
                return result
            else:
                # Fallback to optical flow only
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                if self.prev_features is not None and len(self.prev_features) > 4:
                    curr_features, status, _ = cv2.calcOpticalFlowPyrLK(
                        self.prev_gray, gray, self.prev_features, None
                    )
                    
                    good_prev = self.prev_features[status == 1]
                    good_curr = curr_features[status == 1]
                    
                    if len(good_curr) > 4:
                        # Calculate average position
                        avg_x = np.mean(good_curr[:, 0])
                        avg_y = np.mean(good_curr[:, 1])
                        
                        # Estimate bbox from feature spread
                        std_x = np.std(good_curr[:, 0])
                        std_y = np.std(good_curr[:, 1])
                        
                        w = int(std_x * 4)
                        h = int(std_y * 4)
                        x = int(avg_x - w/2)
                        y = int(avg_y - h/2)
                        
                        result["success"] = True
                        result["bbox"] = (x, y, w, h)
                        result["center"] = {"x": avg_x, "y": avg_y}
                        result["scale"] = 1.0
                        
                        # Rotation from affine
                        matrix, _ = cv2.estimateAffinePartial2D(good_prev, good_curr)
                        if matrix is not None:
                            angle_rad = np.arctan2(matrix[0, 1], matrix[0, 0])
                            result["rotation"] = float(np.degrees(angle_rad))
                
                self.prev_gray = gray
                return result
                
        except Exception as e:
            print(f"Frame tracking error: {e}")
            return result


def extract_full_trajectory(
    video_path: str,
    roi: Dict[str, int],
    fps_override: Optional[float] = None
) -> List[Dict]:
    """
    Extract full trajectory from video using kinematics tracking.
    
    Args:
        video_path: Path to video file
        roi: Region of interest
        fps_override: Optional FPS override
        
    Returns:
        List of trajectory dictionaries with timestamp and kinematic data
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError("Could not open video file")

    try:
        fps = fps_override if fps_override else cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 30.0

        ret, frame = cap.read()
        if not ret:
            raise ValueError("Could not read first frame")

        tracker = KinematicsTracker(roi)
        if not tracker.initialize(frame):
            raise ValueError("Failed to initialize tracker")

        trajectory = []
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            track_result = tracker.track_frame(frame)
            
            if track_result and track_result["success"]:
                trajectory.append({
                    "frame": frame_idx,
                    "t": frame_idx / fps,
                    "x": track_result["center"]["x"],
                    "y": track_result["center"]["y"],
                    "w": track_result["bbox"][2],
                    "h": track_result["bbox"][3],
                    "scale": track_result["scale"],
                    "rotation": track_result["rotation"]
                })

            frame_idx += 1

        return trajectory

    finally:
        cap.release()
