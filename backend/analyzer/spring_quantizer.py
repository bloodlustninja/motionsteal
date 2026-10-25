"""
Design System Physics Quantization Module
Snaps raw (zeta, omega) values to standard mobile design system spring presets.
"""

from typing import Dict, Tuple
import numpy as np


SPRING_PRESETS = {
    "Snappy": {
        "damping_ratio": 0.85,
        "stiffness": 420.0,
        "description": "High stiffness, zero bounce"
    },
    "Bouncy": {
        "damping_ratio": 0.65,
        "stiffness": 300.0,
        "description": "Medium spring with visible overshoot"
    },
    "Fluid": {
        "damping_ratio": 0.75,
        "stiffness": 220.0,
        "description": "Smooth liquid transitions"
    },
    "Gentle": {
        "damping_ratio": 1.00,
        "stiffness": 140.0,
        "description": "Critically damped, soft deceleration"
    }
}


class SpringQuantizer:
    """
    Quantizes raw spring parameters to design system presets.
    Prevents micro-jitter from unconstrained curve fitting.
    """

    def __init__(self, presets: Dict = None):
        """
        Initialize spring quantizer.
        
        Args:
            presets: Custom spring presets (defaults to standard presets)
        """
        self.presets = presets or SPRING_PRESETS

    def quantize(
        self,
        raw_zeta: float,
        raw_omega: float
    ) -> Tuple[str, Dict]:
        """
        Match fitted parameters to the closest design preset.
        
        Args:
            raw_zeta: Raw damping ratio from curve fitting
            raw_omega: Raw natural frequency from curve fitting
            
        Returns:
            Tuple of (preset_name, preset_dict)
        """
        raw_stiffness = raw_omega ** 2

        # Calculate distance to each preset
        # Weight damping ratio 2x more than stiffness
        best_key = min(
            self.presets.keys(),
            key=lambda k: (
                abs(self.presets[k]["damping_ratio"] - raw_zeta) * 2.0 +
                abs(self.presets[k]["stiffness"] - raw_stiffness) / 300.0
            )
        )

        return best_key, self.presets[best_key]

    def quantize_with_confidence(
        self,
        raw_zeta: float,
        raw_omega: float
    ) -> Dict:
        """
        Quantize and return confidence score.
        
        Args:
            raw_zeta: Raw damping ratio
            raw_omega: Raw natural frequency
            
        Returns:
            Dictionary with preset name, values, and confidence
        """
        best_key, preset = self.quantize(raw_zeta, raw_omega)
        
        # Calculate confidence based on distance
        raw_stiffness = raw_omega ** 2
        zeta_diff = abs(preset["damping_ratio"] - raw_zeta)
        stiffness_diff = abs(preset["stiffness"] - raw_stiffness)
        
        # Normalize differences
        zeta_normalized = zeta_diff / 0.5  # Max expected diff 0.5
        stiffness_normalized = stiffness_diff / 300.0  # Max expected diff 300
        
        confidence = max(0.0, 1.0 - (zeta_normalized + stiffness_normalized) / 2)

        return {
            "preset_name": best_key,
            "damping_ratio": preset["damping_ratio"],
            "stiffness": preset["stiffness"],
            "omega": np.sqrt(preset["stiffness"]),
            "description": preset["description"],
            "confidence": float(confidence),
            "raw_zeta": raw_zeta,
            "raw_omega": raw_omega,
            "raw_stiffness": raw_stiffness
        }


def quantize_spring(
    raw_zeta: float,
    raw_omega: float,
    custom_presets: Dict = None
) -> Dict:
    """
    Quantize spring parameters to design system preset.
    
    Args:
        raw_zeta: Raw damping ratio
        raw_omega: Raw natural frequency
        custom_presets: Optional custom presets
        
    Returns:
        Dictionary with quantized parameters
    """
    quantizer = SpringQuantizer(custom_presets)
    return quantizer.quantize_with_confidence(raw_zeta, raw_omega)


def get_preset_by_name(preset_name: str) -> Dict:
    """
    Get a specific preset by name.
    
    Args:
        preset_name: Name of the preset
        
    Returns:
        Preset dictionary
    """
    return SPRING_PRESETS.get(preset_name, SPRING_PRESETS["Fluid"])
