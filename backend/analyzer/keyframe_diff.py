"""
Keyframe Extraction & Semantic Diffing Module
Extracts discrete inflection frames and passes them to Gemini for state machine extraction.
"""

import cv2
import numpy as np
from typing import List, Dict, Tuple, Optional
import base64
from google import genai
from google.genai import types


class KeyframeDiff:
    """
    Extracts keyframes based on kinetic energy and diffing for semantic state extraction.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize keyframe diff engine.
        
        Args:
            api_key: Google API key for Gemini Vision
        """
        self.api_key = api_key
        self.client = None
        if api_key:
            self.client = genai.Client(api_key=api_key)

    def compute_kinetic_energy(
        self,
        trajectory: List[Dict]
    ) -> np.ndarray:
        """
        Compute kinetic energy from velocity profiles.
        
        E_k(t) = v_trans^2(t) + v_morph^2(t)
        
        Args:
            trajectory: Point-cluster trajectory data
            
        Returns:
            Kinetic energy array
        """
        trans_velocities = np.array([frame["trans_velocity"] for frame in trajectory])
        morph_velocities = np.array([frame["morph_velocity"] for frame in trajectory])
        
        kinetic_energy = trans_velocities**2 + morph_velocities**2
        return kinetic_energy

    def extract_keyframes(
        self,
        trajectory: List[Dict],
        video_path: str
    ) -> Dict:
        """
        Extract 3-4 keyframe timestamps based on kinetic energy inflection points.
        
        Args:
            trajectory: Point-cluster trajectory
            video_path: Path to video file
            
        Returns:
            Dictionary with keyframe timestamps and crops
        """
        if len(trajectory) < 5:
            return {
                "start_t": 0.0,
                "peak_t": 0.0,
                "inflect_t": 0.0,
                "settle_t": 0.0,
                "crops": {}
            }

        kinetic_energy = self.compute_kinetic_energy(trajectory)
        max_energy = np.max(kinetic_energy)
        threshold = 0.05 * max_energy

        # Start: First frame where energy exceeds threshold
        start_idx = np.where(kinetic_energy > threshold)[0]
        start_t = trajectory[start_idx[0]]["t"] if len(start_idx) > 0 else 0.0

        # Peak: Global maximum of kinetic energy
        peak_idx = np.argmax(kinetic_energy)
        peak_t = trajectory[peak_idx]["t"]

        # Inflection: Point where translation stops and expansion begins
        # Find where trans_velocity drops while morph_velocity increases
        trans_velocities = np.array([frame["trans_velocity"] for frame in trajectory])
        morph_velocities = np.array([frame["morph_velocity"] for frame in trajectory])
        
        # Calculate acceleration (derivative of velocity)
        trans_accel = np.gradient(trans_velocities)
        
        # Find zero-crossing of translation acceleration
        inflection_candidates = np.where(trans_accel < 0)[0]
        if len(inflection_candidates) > 0:
            # Pick the one after peak where morph velocity is significant
            inflection_idx = inflection_candidates[0]
            inflect_t = trajectory[inflection_idx]["t"]
        else:
            inflect_t = peak_t

        # Settle: Frame where motion returns to rest
        settle_candidates = np.where(kinetic_energy < threshold)[0]
        if len(settle_candidates) > 0:
            settle_idx = settle_candidates[-1]
            settle_t = trajectory[settle_idx]["t"]
        else:
            settle_t = trajectory[-1]["t"]

        # Extract crops at keyframes
        crops = self._extract_keyframe_crops(
            video_path,
            [start_t, peak_t, inflect_t, settle_t],
            trajectory[0]["cx"],
            trajectory[0]["cy"],
            trajectory[0]["spread_x"],
            trajectory[0]["spread_y"]
        )

        return {
            "start_t": start_t,
            "peak_t": peak_t,
            "inflect_t": inflect_t,
            "settle_t": settle_t,
            "crops": crops
        }

    def _extract_keyframe_crops(
        self,
        video_path: str,
        timestamps: List[float],
        cx: float,
        cy: float,
        spread_x: float,
        spread_y: float
    ) -> Dict[str, str]:
        """
        Extract crops at keyframe timestamps.
        
        Args:
            video_path: Path to video
            timestamps: List of timestamps
            cx, cy: Center coordinates
            spread_x, spread_y: Spread dimensions
            
        Returns:
            Dictionary mapping keyframe names to base64-encoded crops
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return {}

        try:
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            crops = {}
            names = ["start", "peak", "inflect", "settle"]

            for name, t in zip(names, timestamps):
                frame_num = int(t * fps)
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
                ret, frame = cap.read()
                if ret:
                    # Calculate crop region with padding
                    margin = 20
                    x = int(cx - spread_x - margin)
                    y = int(cy - spread_y - margin)
                    w = int(spread_x * 2 + margin * 2)
                    h = int(spread_y * 2 + margin * 2)

                    # Ensure within bounds
                    height, width = frame.shape[:2]
                    x = max(0, x)
                    y = max(0, y)
                    w = min(w, width - x)
                    h = min(h, height - y)

                    if w > 0 and h > 0:
                        crop = frame[y:y+h, x:x+w]
                        _, buffer = cv2.imencode('.png', crop)
                        crops[name] = base64.b64encode(buffer).decode('utf-8')

            return crops

        finally:
            cap.release()

    def diff_states_with_gemini(
        self,
        keyframes: Dict,
        trajectory: List[Dict]
    ) -> Dict:
        """
        Use Gemini Vision to diff states and extract property transitions.
        
        Args:
            keyframes: Dictionary with crops at keyframes
            trajectory: Trajectory data
            
        Returns:
            State machine with property transitions
        """
        if not self.client or not keyframes.get("crops"):
            return self._fallback_state_machine(trajectory)

        try:
            prompt = """
Analyze these UI element state transitions. Return ONLY a JSON object with:

{
  "component_type": "ExpandingFabMenu | FloatingCard | WaveDock | Button | Card",
  "states": [
    {
      "name": "COLLAPSED",
      "properties": {"width_dp": int, "height_dp": int, "offset_y_dp": int, "alpha": float}
    },
    {
      "name": "EXPANDED",
      "properties": {"width_dp": int, "height_dp": int, "offset_y_dp": int, "alpha": float}
    }
  ],
  "staggered_children": {
    "count": int,
    "delay_step_ms": int
  }
}

Images are: start, peak, inflection, settle states.
"""

            parts = [prompt]
            for name in ["start", "settle"]:
                if keyframes["crops"].get(name):
                    parts.append(
                        types.Part.from_bytes(
                            data=base64.b64decode(keyframes["crops"][name]),
                            mime_type="image/png"
                        )
                    )

            response = self.client.models.generate_content(
                model="gemini-2.0-flash",
                contents=parts
            )

            # Parse JSON response
            import json
            import re
            json_match = re.search(r'\{[^}]+\}', response.text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())

            return self._fallback_state_machine(trajectory)

        except Exception as e:
            print(f"Gemini state diff error: {e}")
            return self._fallback_state_machine(trajectory)

    def _fallback_state_machine(self, trajectory: List[Dict]) -> Dict:
        """
        Fallback state machine without AI.
        
        Args:
            trajectory: Trajectory data
            
        Returns:
            Default state machine
        """
        if not trajectory:
            return {"component_type": "Card", "states": [], "staggered_children": {"count": 0}}

        start_spread = trajectory[0]["spread_x"]
        end_spread = trajectory[-1]["spread_x"]
        width_change = abs(end_spread - start_spread)

        return {
            "component_type": "FloatingCard" if width_change > 20 else "Button",
            "states": [
                {
                    "name": "COLLAPSED",
                    "properties": {
                        "width_dp": int(start_spread),
                        "height_dp": int(trajectory[0]["spread_y"]),
                        "offset_y_dp": 0,
                        "alpha": 1.0
                    }
                },
                {
                    "name": "EXPANDED",
                    "properties": {
                        "width_dp": int(end_spread),
                        "height_dp": int(trajectory[-1]["spread_y"]),
                        "offset_y_dp": int(trajectory[-1]["cy"] - trajectory[0]["cy"]),
                        "alpha": 1.0
                    }
                }
            ],
            "staggered_children": {
                "count": 0,
                "delay_step_ms": 0
            }
        }


def extract_keyframe_diff(
    video_path: str,
    trajectory: List[Dict],
    api_key: Optional[str] = None
) -> Dict:
    """
    Extract keyframes and diff states for state machine extraction.
    
    Args:
        video_path: Path to video
        trajectory: Point-cluster trajectory
        api_key: Google API key
        
    Returns:
        Dictionary with keyframes and state machine
    """
    # Extract trajectory ROI for initialization
    if trajectory:
        roi = {
            "x": int(trajectory[0]["cx"] - trajectory[0]["spread_x"]),
            "y": int(trajectory[0]["cy"] - trajectory[0]["spread_y"]),
            "w": int(trajectory[0]["spread_x"] * 2),
            "h": int(trajectory[0]["spread_y"] * 2)
        }
    else:
        roi = {"x": 0, "y": 0, "w": 100, "h": 100}

    diff_engine = KeyframeDiff(api_key)
    keyframes = diff_engine.extract_keyframes(trajectory, video_path)
    state_machine = diff_engine.diff_states_with_gemini(keyframes, trajectory)

    return {
        "keyframes": keyframes,
        "state_machine": state_machine
    }
