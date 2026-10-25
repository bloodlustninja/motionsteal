"""
Token Extractor Module - Design Token Extraction
Uses Gemini Vision to extract color swatches, corner radii, and map icons.
"""

import base64
from typing import Dict, List, Optional
from google import genai
from google.genai import types


class TokenExtractor:
    """Extracts design tokens from video frames using AI vision."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize token extractor.
        
        Args:
            api_key: Google API key for Gemini Vision
        """
        self.api_key = api_key
        self.client = None
        if api_key:
            self.client = genai.Client(api_key=api_key)

    def extract_design_tokens(
        self,
        frame_bytes: bytes,
        prompt_context: str = ""
    ) -> Dict:
        """
        Extract design tokens from a frame.
        
        Args:
            frame_bytes: Image data as bytes
            prompt_context: Additional context for analysis
            
        Returns:
            Dictionary with colors, corner radius, typography, etc.
        """
        if not self.client:
            return self._fallback_extraction()

        try:
            prompt = f"""
Analyze this UI design and extract the following design tokens:

{prompt_context}

Extract and return ONLY a JSON object with:
- colors: hex codes for primary, secondary, background, text colors
- corner_radius: approximate corner radius in pixels or dp
- shadows: shadow details (elevation, blur, color)
- typography: font size, weight, line height estimates
- icons: identify any icons and map to Material/Lucide symbol names

Return ONLY valid JSON, no conversational text.
"""

            response = self.client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[
                    prompt,
                    types.Part.from_bytes(data=frame_bytes, mime_type="image/jpeg")
                ]
            )

            # Try to parse JSON from response
            import json
            try:
                tokens = json.loads(response.text)
                return tokens
            except json.JSONDecodeError:
                # If response isn't pure JSON, try to extract it
                import re
                json_match = re.search(r'\{[^}]+\}', response.text)
                if json_match:
                    tokens = json.loads(json_match.group())
                    return tokens

            return self._fallback_extraction()

        except Exception as e:
            print(f"Token extraction error: {e}")
            return self._fallback_extraction()

    def _fallback_extraction(self) -> Dict:
        """
        Fallback extraction without AI.
        
        Returns:
            Default design tokens
        """
        return {
            "colors": {
                "primary": "#6366F1",
                "secondary": "#8B5CF6",
                "background": "#1A1A1A",
                "text": "#FFFFFF"
            },
            "corner_radius": 12,
            "shadows": {
                "elevation": 2,
                "blur": 8,
                "color": "rgba(0,0,0,0.3)"
            },
            "typography": {
                "font_size": 16,
                "weight": "normal",
                "line_height": 1.5
            },
            "icons": []
        }

    def map_icon_to_library(
        self,
        icon_description: str
    ) -> str:
        """
        Map icon description to Material/Lucide symbol name.
        
        Args:
            icon_description: Text description of icon
            
        Returns:
            Icon symbol name
        """
        # Simple mapping - could be expanded
        icon_map = {
            "check": "Check",
            "close": "X",
            "arrow": "ArrowRight",
            "menu": "Menu",
            "search": "Search",
            "home": "Home",
            "settings": "Settings",
            "plus": "Plus",
            "minus": "Minus"
        }

        description_lower = icon_description.lower()
        for key, value in icon_map.items():
            if key in description_lower:
                return value

        return "Default"


def extract_tokens_from_video(
    video_path: str,
    api_key: Optional[str] = None,
    frame_num: int = 0
) -> Dict:
    """
    Extract design tokens from a specific video frame.
    
    Args:
        video_path: Path to video file
        api_key: Google API key
        frame_num: Frame number to analyze
        
    Returns:
        Design tokens dictionary
    """
    import cv2
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError("Could not open video file")

    try:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
        ret, frame = cap.read()
        if not ret:
            raise ValueError("Could not read frame")

        # Encode frame
        _, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()

        extractor = TokenExtractor(api_key)
        tokens = extractor.extract_design_tokens(frame_bytes)

        return tokens

    finally:
        cap.release()
