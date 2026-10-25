"""
Spline Tracer Module - Vector Boundary Path Extraction
Extracts continuous vector boundary paths and Bézier curves for fluid animations.
"""

import cv2
import numpy as np
from typing import List, Dict, Tuple, Optional
from scipy.interpolate import splprep, splev


class SplineTracer:
    """Extracts and simplifies boundary paths as spline curves."""

    def __init__(self, smoothing: float = 0.0, points_per_contour: int = 20):
        """
        Initialize spline tracer.
        
        Args:
            smoothing: Smoothing factor for spline fitting (0 = exact fit)
            points_per_contour: Number of points to sample per contour
        """
        self.smoothing = smoothing
        self.points_per_contour = points_per_contour

    def extract_boundary_path(
        self,
        frame: np.ndarray,
        roi: Dict[str, int]
    ) -> Optional[List[Tuple[float, float]]]:
        """
        Extract boundary path from ROI in frame.
        
        Args:
            frame: Input frame
            roi: Region of interest
            
        Returns:
            List of (x, y) tuples representing the boundary path
        """
        try:
            # Crop to ROI
            x, y, w, h = roi["x"], roi["y"], roi["w"], roi["h"]
            crop = frame[y:y+h, x:x+w]
            
            if crop.size == 0:
                return None

            # Convert to grayscale
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

            # Apply adaptive thresholding
            thresh = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, 11, 2
            )

            # Find contours
            contours, _ = cv2.findContours(
                thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )

            if not contours:
                return None

            # Get largest contour
            largest_contour = max(contours, key=cv2.contourArea)

            # Simplify contour with Ramer-Douglas-Peucker
            epsilon = 0.02 * cv2.arcLength(largest_contour, True)
            simplified = cv2.approxPolyDP(largest_contour, epsilon, True)

            # Extract points
            points = []
            for point in simplified:
                px, py = point[0]
                points.append((float(px + x), float(py + y)))

            if len(points) < 3:
                return None

            return points

        except Exception as e:
            print(f"Boundary path extraction error: {e}")
            return None

    def fit_bezier_spline(
        self,
        points: List[Tuple[float, float]]
    ) -> Dict:
        """
        Fit Bézier spline to boundary points.
        
        Args:
            points: List of (x, y) boundary points
            
        Returns:
            Dictionary with spline parameters and control points
        """
        if len(points) < 4:
            return {
                "type": "simple",
                "points": points,
                "control_points": None
            }

        try:
            # Separate x and y coordinates
            x = np.array([p[0] for p in points])
            y = np.array([p[1] for p in points])

            # Calculate cumulative distance along path
            dist = np.cumsum(np.sqrt(np.diff(x)**2 + np.diff(y)**2))
            dist = np.insert(dist, 0, 0)
            dist = dist / dist[-1]  # Normalize to [0, 1]

            # Fit spline
            tck, u = splprep([x, y], u=dist, s=self.smoothing)

            # Generate smooth curve
            u_new = np.linspace(0, 1, self.points_per_contour)
            x_new, y_new = splev(u_new, tck)

            # Extract control points
            t_control = np.linspace(0, 1, 4)  # Cubic Bézier needs 4 control points
            x_control, y_control = splev(t_control, tck)

            control_points = [
                (float(xc), float(yc))
                for xc, yc in zip(x_control, y_control)
            ]

            return {
                "type": "bezier",
                "points": [(float(xn), float(yn)) for xn, yn in zip(x_new, y_new)],
                "control_points": control_points,
                "tck": tck
            }

        except Exception as e:
            print(f"B spline fitting error: {e}")
            return {
                "type": "simple",
                "points": points,
                "control_points": None
            }

    def trace_evolution(
        self,
        video_path: str,
        roi: Dict[str, int],
        frame_interval: int = 5
    ) -> List[Dict]:
        """
        Trace boundary evolution across video frames.
        
        Args:
            video_path: Path to video file
            roi: Region of interest
            frame_interval: Process every Nth frame
            
        Returns:
            List of boundary data per frame
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError("Could not open video file")

        try:
            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0:
                fps = 30.0

            boundary_evolution = []
            frame_idx = 0

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_idx % frame_interval == 0:
                    boundary = self.extract_boundary_path(frame, roi)
                    if boundary:
                        spline = self.fit_bezier_spline(boundary)
                        boundary_evolution.append({
                            "frame": frame_idx,
                            "t": frame_idx / fps,
                            "boundary": boundary,
                            "spline": spline
                        })

                frame_idx += 1

            return boundary_evolution

        finally:
            cap.release()


def extract_fluid_contours(
    video_path: str,
    roi: Dict[str, int]
) -> Dict:
    """
    Extract fluid contour evolution for morphing animations.
    
    Args:
        video_path: Path to video file
        roi: Region of interest
        
    Returns:
        Dictionary with initial and final boundary splines
    """
    tracer = SplineTracer()
    evolution = tracer.trace_evolution(video_path, roi, frame_interval=10)
    
    if len(evolution) < 2:
        return {
            "initial": None,
            "final": None,
            "evolution": evolution
        }

    return {
        "initial": evolution[0]["spline"],
        "final": evolution[-1]["spline"],
        "evolution": evolution
    }
