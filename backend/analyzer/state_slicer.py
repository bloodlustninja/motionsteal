"""
State Slicer Module - Velocity Inflection Detection
Detects animation phase transitions by analyzing velocity inflection points.
"""

import numpy as np
from typing import List, Dict, Tuple, Optional
from scipy.ndimage import gaussian_filter1d


class StateSlicer:
    """Detects animation phase transitions from velocity profiles."""

    def __init__(self, velocity_threshold: float = 0.05, min_phase_duration: float = 0.1):
        """
        Initialize state slicer.
        
        Args:
            velocity_threshold: Threshold for detecting motion (5% of peak)
            min_phase_duration: Minimum duration for a phase (seconds)
        """
        self.velocity_threshold = velocity_threshold
        self.min_phase_duration = min_phase_duration

    def detect_phases(
        self,
        trajectory: List[Dict],
        metric: str = "scale"
    ) -> List[Dict]:
        """
        Detect animation phases from trajectory data.
        
        Args:
            trajectory: List of trajectory dictionaries
            metric: Which metric to analyze ('x', 'y', 'scale', 'rotation')
            
        Returns:
            List of phase dictionaries with start/end times and type
        """
        if len(trajectory) < 3:
            return [{
                "name": "single_phase",
                "start_t": 0.0,
                "end_t": trajectory[-1]["t"],
                "type": "unknown"
            }]

        # Extract metric values
        values = np.array([frame[metric] for frame in trajectory])
        times = np.array([frame["t"] for frame in trajectory])

        # Calculate velocity
        if len(values) > 1:
            dt = np.diff(times)
            dv = np.diff(values)
            velocity = dv / dt
            velocity = np.nan_to_num(velocity, 0.0)
        else:
            velocity = np.array([0.0])

        # Smooth velocity
        velocity_smooth = gaussian_filter1d(velocity, sigma=2)

        # Find inflection points
        inflection_points = self._find_inflection_points(times, velocity_smooth)

        # Group into phases
        phases = self._group_into_phases(times, inflection_points, trajectory)

        return phases

    def _find_inflection_points(
        self,
        times: np.ndarray,
        velocity: np.ndarray
    ) -> List[float]:
        """
        Find velocity inflection points.
        
        Args:
            times: Timestamp array
            velocity: Velocity array
            
        Returns:
            List of inflection point timestamps
        """
        if len(velocity) < 3:
            return []

        # Calculate velocity derivative (acceleration)
        acceleration = np.gradient(velocity)

        # Find where acceleration changes sign (inflection)
        inflection_indices = []
        for i in range(1, len(acceleration) - 1):
            if acceleration[i-1] * acceleration[i+1] < 0:
                # Sign change indicates inflection
                if abs(acceleration[i]) > np.std(acceleration) * 0.5:
                    inflection_indices.append(i)

        # Convert to timestamps
        inflection_times = [times[i] for i in inflection_indices]
        
        return inflection_times

    def _group_into_phases(
        self,
        times: np.ndarray,
        inflection_points: List[float],
        trajectory: List[Dict]
    ) -> List[Dict]:
        """
        Group trajectory into distinct animation phases.
        
        Args:
            times: Timestamp array
            inflection_points: List of inflection timestamps
            trajectory: Original trajectory data
            
        Returns:
            List of phase dictionaries
        """
        phases = []
        
        # Add start and end points
        boundaries = [0.0] + inflection_points + [trajectory[-1]["t"]]
        
        for i in range(len(boundaries) - 1):
            start_t = boundaries[i]
            end_t = boundaries[i + 1]
            
            # Skip very short phases
            if end_t - start_t < self.min_phase_duration:
                continue
            
            # Determine phase type
            phase_type = self._classify_phase(trajectory, start_t, end_t)
            
            phases.append({
                "name": f"phase_{i+1}",
                "start_t": start_t,
                "end_t": end_t,
                "type": phase_type
            })

        return phases

    def _classify_phase(
        self,
        trajectory: List[Dict],
        start_t: float,
        end_t: float
    ) -> str:
        """
        Classify the type of animation phase.
        
        Args:
            trajectory: Full trajectory data
            start_t: Phase start time
            end_t: Phase end time
            
        Returns:
            Phase type string
        """
        # Extract data for this phase
        phase_data = [
            frame for frame in trajectory
            if start_t <= frame["t"] <= end_t
        ]
        
        if len(phase_data) < 2:
            return "static"

        # Analyze different metrics
        x_values = [frame["x"] for frame in phase_data]
        y_values = [frame["y"] for frame in phase_data]
        scale_values = [frame["scale"] for frame in phase_data]
        rotation_values = [frame["rotation"] for frame in phase_data]

        # Calculate variances
        x_var = np.var(x_values)
        y_var = np.var(y_values)
        scale_var = np.var(scale_values)
        rotation_var = np.var(rotation_values)

        # Determine dominant motion
        max_var = max(x_var, y_var, scale_var, rotation_var)
        
        if max_var == scale_var and scale_var > 0.01:
            return "scale"
        elif max_var == rotation_var and rotation_var > 1.0:
            return "rotation"
        elif max_var == x_var:
            return "translation_x"
        elif max_var == y_var:
            return "translation_y"
        else:
            return "static"


def slice_video_states(
    video_path: str,
    trajectory: List[Dict]
) -> List[Dict]:
    """
    Slice video into distinct animation states based on trajectory analysis.
    
    Args:
        video_path: Path to video file
        trajectory: Extracted trajectory data
        
    Returns:
        List of state dictionaries with metadata
    """
    slicer = StateSlicer()
    phases = slicer.detect_phases(trajectory)
    
    states = []
    for i, phase in enumerate(phases):
        state = {
            "id": i,
            "name": phase["name"],
            "start_t": phase["start_t"],
            "end_t": phase["end_t"],
            "duration": phase["end_t"] - phase["start_t"],
            "type": phase["type"],
            "trajectory": [
                frame for frame in trajectory
                if phase["start_t"] <= frame["t"] <= phase["end_t"]
            ]
        }
        states.append(state)
    
    return states
