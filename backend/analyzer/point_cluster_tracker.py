"""
Point-Cluster Kinematics Module
Replaces single-box CSRT with Dense Point-Cluster Optical Flow.
Tracks center of mass and standard deviation spread instead of enclosing rectangles.
"""

import cv2
import numpy as np
from typing import List, Dict, Tuple, Optional


class PointClusterTracker:
    """
    Tracks UI elements using dense point-cluster optical flow.
    More robust for non-rigid morphing and shape changes.
    """

    def __init__(self, roi: Dict[str, int], point_spacing: int = 6):
        """
        Initialize point-cluster tracker.
        
        Args:
            roi: Region of interest with 'x', 'y', 'w', 'h'
            point_spacing: Spacing between feature points (4-8px recommended)
        """
        self.roi = roi
        self.point_spacing = point_spacing
        self.initial_points = None
        self.prev_gray = None
        self.initial_count = 0
        self.min_density_ratio = 0.4  # Re-seed if below 40% of initial count

    def initialize(self, frame: np.ndarray) -> bool:
        """
        Initialize feature points in a grid pattern across the ROI.
        
        Args:
            frame: First frame to initialize on
            
        Returns:
            True if initialization successful
        """
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Create ROI mask
            mask = np.zeros_like(gray)
            x, y, w, h = self.roi["x"], self.roi["y"], self.roi["w"], self.roi["h"]
            mask[y:y+h, x:x+w] = 255
            
            # Generate uniform grid of points
            points = []
            for py in range(y + self.point_spacing // 2, y + h, self.point_spacing):
                for px in range(x + self.point_spacing // 2, x + w, self.point_spacing):
                    points.append([float(px), float(py)])
            
            if len(points) < 10:
                # Fallback to goodFeaturesToTrack if grid is too small
                corners = cv2.goodFeaturesToTrack(
                    gray,
                    mask=mask,
                    maxCorners=100,
                    qualityLevel=0.01,
                    minDistance=self.point_spacing
                )
                if corners is not None:
                    self.initial_points = corners.reshape(-1, 2)
                else:
                    return False
            else:
                self.initial_points = np.array(points, dtype=np.float32).reshape(-1, 1, 2)
            
            self.initial_count = len(self.initial_points)
            self.prev_gray = gray
            return True
            
        except Exception as e:
            print(f"Point cluster initialization error: {e}")
            return False

    def track_frame(self, frame: np.ndarray) -> Optional[Dict]:
        """
        Track points in current frame using pyramidal Lucas-Kanade optical flow.
        
        Args:
            frame: Current frame to track
            
        Returns:
            Dictionary with center of mass, spread, and velocity metrics
        """
        if self.initial_points is None or self.prev_gray is None:
            return None

        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Pyramidal Lucas-Kanade optical flow
            curr_points, status, _ = cv2.calcOpticalFlowPyrLK(
                self.prev_gray,
                gray,
                self.initial_points,
                None,
                winSize=(15, 15),
                maxLevel=3,
                criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03)
            )
            
            # Filter valid points
            valid_points = curr_points[status == 1]
            prev_valid = self.initial_points[status == 1]
            
            if len(valid_points) < 5:
                return None
            
            # Forward-backward error check
            if len(valid_points) > 10:
                prev_points_rev, status_rev, _ = cv2.calcOpticalFlowPyrLK(
                    gray,
                    self.prev_gray,
                    valid_points,
                    None,
                    winSize=(15, 15),
                    maxLevel=3
                )
                
                # Calculate forward-backward error
                fb_error = np.linalg.norm(prev_valid - prev_points_rev, axis=1)
                valid_mask = fb_error < 2.0  # Threshold 2 pixels
                valid_points = valid_points[valid_mask]
                prev_valid = prev_valid[valid_mask]
            
            # Check density ratio - re-seed if too many points lost
            density_ratio = len(valid_points) / self.initial_count
            if density_ratio < self.min_density_ratio:
                # Re-initialize with current points
                self.initial_points = valid_points.reshape(-1, 1, 2)
                self.initial_count = len(valid_points)
            
            # Calculate center of mass
            cx = np.mean(valid_points[:, 0])
            cy = np.mean(valid_points[:, 1])
            
            # Calculate shape spread (2 * standard deviation)
            spread_x = 2 * np.std(valid_points[:, 0])
            spread_y = 2 * np.std(valid_points[:, 1])
            
            # Calculate morph velocity (rate of change of spread)
            prev_cx = np.mean(prev_valid[:, 0])
            prev_cy = np.mean(prev_valid[:, 1])
            prev_spread_x = 2 * np.std(prev_valid[:, 0])
            prev_spread_y = 2 * np.std(prev_valid[:, 1])
            
            trans_velocity = np.sqrt((cx - prev_cx)**2 + (cy - prev_cy)**2)
            morph_velocity = np.sqrt((spread_x - prev_spread_x)**2 + (spread_y - prev_spread_y)**2)
            
            # Update for next frame
            self.initial_points = valid_points.reshape(-1, 1, 2)
            self.prev_gray = gray
            
            return {
                "success": True,
                "cx": float(cx),
                "cy": float(cy),
                "spread_x": float(spread_x),
                "spread_y": float(spread_y),
                "trans_velocity": float(trans_velocity),
                "morph_velocity": float(morph_velocity),
                "point_count": len(valid_points)
            }
            
        except Exception as e:
            print(f"Frame tracking error: {e}")
            return None


def extract_point_cluster_trajectory(
    video_path: str,
    roi: Dict[str, int],
    fps_override: Optional[float] = None
) -> List[Dict]:
    """
    Extract full trajectory using point-cluster tracking.
    
    Args:
        video_path: Path to video file
        roi: Region of interest
        fps_override: Optional FPS override
        
    Returns:
        List of trajectory dictionaries with point-cluster metrics
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

        tracker = PointClusterTracker(roi, point_spacing=6)
        if not tracker.initialize(frame):
            raise ValueError("Failed to initialize point cluster tracker")

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
                    "cx": track_result["cx"],
                    "cy": track_result["cy"],
                    "spread_x": track_result["spread_x"],
                    "spread_y": track_result["spread_y"],
                    "trans_velocity": track_result["trans_velocity"],
                    "morph_velocity": track_result["morph_velocity"],
                    "point_count": track_result["point_count"]
                })

            frame_idx += 1

        return trajectory

    finally:
        cap.release()
