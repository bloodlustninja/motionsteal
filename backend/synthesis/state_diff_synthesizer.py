"""
Multimodal State Analyzer Module
Uses Gemini Vision to diff 3 keyframes and extract UI state transitions.
"""

import base64
from typing import Dict, Optional
from google import genai
from google.genai import types


class StateDiffSynthesizer:
    """
    Analyzes state transitions using multimodal vision.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize state diff synthesizer.
        
        Args:
            api_key: Google API key for Gemini Vision
        """
        self.api_key = api_key
        self.client = None
        if api_key:
            self.client = genai.Client(api_key=api_key)

    def analyze_states(
        self,
        keyframes: Dict[str, str]
    ) -> Dict:
        """
        Analyze 3 keyframes to extract state transitions.
        
        Args:
            keyframes: Dictionary with 'idle', 'apex', 'settled' base64-encoded images
            
        Returns:
            Dictionary with extracted UI properties and state transitions
        """
        if not self.client:
            return self._fallback_analysis(keyframes)

        try:
            prompt = """
Analyze these 3 UI component states:
- Frame 0 (Idle): Initial resting state
- Frame 1 (Apex): Maximum deformation/stretch
- Frame 2 (Settled): Final resting state

Extract and return ONLY a JSON object with:
{
  "component_type": "Button | Card | FAB | BottomSheet | Dialog",
  "states": {
    "idle": {
      "width_dp": int,
      "height_dp": int,
      "offset_y_dp": int,
      "offset_x_dp": int,
      "corner_radius_dp": int,
      "alpha": float,
      "scale": float,
      "rotation_deg": float,
      "background_color": "#RRGGBB",
      "elevation_dp": int
    },
    "apex": {
      "width_dp": int,
      "height_dp": int,
      "offset_y_dp": int,
      "offset_x_dp": int,
      "corner_radius_dp": int,
      "alpha": float,
      "scale": float,
      "rotation_deg": float,
      "background_color": "#RRGGBB",
      "elevation_dp": int
    },
    "settled": {
      "width_dp": int,
      "height_dp": int,
      "offset_y_dp": int,
      "offset_x_dp": int,
      "corner_radius_dp": int,
      "alpha": float,
      "scale": float,
      "rotation_deg": float,
      "background_color": "#RRGGBB",
      "elevation_dp": int
    }
  },
  "staggered_children": {
    "has_children": boolean,
    "count": int,
    "delay_step_ms": int,
    "child_type": "icon | text | badge"
  },
  "transition_type": "expand | slide | scale | fade | morph",
  "spring_preset": "Snappy | Bouncy | Fluid | Gentle"
}

Return ONLY valid JSON, no conversational text.
"""

            parts = [prompt]
            
            # Add keyframes in order
            for name in ["idle", "apex", "settled"]:
                if keyframes.get(name):
                    parts.append(
                        types.Part.from_bytes(
                            data=base64.b64decode(keyframes[name]),
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

            return self._fallback_analysis(keyframes)

        except Exception as e:
            print(f"State analysis error: {e}")
            return self._fallback_analysis(keyframes)

    def _fallback_analysis(self, keyframes: Dict[str, str]) -> Dict:
        """
        Fallback analysis without AI.
        
        Args:
            keyframes: Keyframe images
            
        Returns:
            Default state machine
        """
        return {
            "component_type": "Card",
            "states": {
                "idle": {
                    "width_dp": 200,
                    "height_dp": 100,
                    "offset_y_dp": 0,
                    "offset_x_dp": 0,
                    "corner_radius_dp": 12,
                    "alpha": 1.0,
                    "scale": 1.0,
                    "rotation_deg": 0.0,
                    "background_color": "#1A1A1A",
                    "elevation_dp": 2
                },
                "apex": {
                    "width_dp": 220,
                    "height_dp": 110,
                    "offset_y_dp": -10,
                    "offset_x_dp": 0,
                    "corner_radius_dp": 12,
                    "alpha": 1.0,
                    "scale": 1.1,
                    "rotation_deg": 0.0,
                    "background_color": "#6366F1",
                    "elevation_dp": 4
                },
                "settled": {
                    "width_dp": 200,
                    "height_dp": 100,
                    "offset_y_dp": 0,
                    "offset_x_dp": 0,
                    "corner_radius_dp": 12,
                    "alpha": 1.0,
                    "scale": 1.0,
                    "rotation_deg": 0.0,
                    "background_color": "#1A1A1A",
                    "elevation_dp": 2
                }
            },
            "staggered_children": {
                "has_children": False,
                "count": 0,
                "delay_step_ms": 0,
                "child_type": "icon"
            },
            "transition_type": "expand",
            "spring_preset": "Fluid"
        }


def analyze_state_transitions(
    keyframes: Dict[str, str],
    api_key: Optional[str] = None
) -> Dict:
    """
    Analyze state transitions from keyframes.
    
    Args:
        keyframes: Dictionary with keyframe images
        api_key: Google API key
        
    Returns:
        State machine dictionary
    """
    synthesizer = StateDiffSynthesizer(api_key)
    return synthesizer.analyze_states(keyframes)
