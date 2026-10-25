"""
Curve Fitters Module - Physics Model Fitting
Fits harmonic oscillators and cubic Béziers to find ground-truth animation specs.
"""

import numpy as np
from scipy.optimize import curve_fit
from scipy.ndimage import gaussian_filter1d
from typing import Dict, Tuple, Optional


class CurveFitter:
    """Fits animation curves to physics models."""

    def __init__(self):
        """Initialize curve fitter."""
        pass

    def spring_model(self, t: np.ndarray, omega: float, zeta: float) -> np.ndarray:
        """
        Damped harmonic oscillator model.
        
        Args:
            t: Time array
            omega: Natural frequency
            zeta: Damping ratio
            
        Returns:
            Displacement array
        """
        zeta = np.clip(zeta, 0.01, 1.5)
        
        if zeta < 1.0:
            # Underdamped
            omega_d = omega * np.sqrt(1.0 - zeta**2)
            return 1.0 - np.exp(-zeta * omega * t) * (
                np.cos(omega_d * t) + (zeta / np.sqrt(1.0 - zeta**2)) * np.sin(omega_d * t)
            )
        else:
            # Critically damped or overdamped
            return 1.0 - (1.0 + omega * t) * np.exp(-omega * t)

    def cubic_bezier_1d(self, t: np.ndarray, p1: float, p2: float) -> np.ndarray:
        """
        Cubic Bézier curve with fixed endpoints (0,0) and (1,1).
        
        Args:
            t: Time array (normalized to [0,1])
            p1: First control point Y
            p2: Second control point Y
            
        Returns:
            Curve values
        """
        return 3 * (1 - t)**2 * t * p1 + 3 * (1 - t) * t**2 * p2 + t**3

    def fit_spring(
        self,
        t: np.ndarray,
        progress: np.ndarray
    ) -> Tuple[Dict, float]:
        """
        Fit spring model to trajectory data.
        
        Args:
            t: Time array
            progress: Progress values (normalized 0-1)
            
        Returns:
            Tuple of (parameters dict, MSE)
        """
        try:
            popt, _ = curve_fit(
                self.spring_model,
                t,
                progress,
                p0=[15.0, 0.7],
                bounds=([1.0, 0.05], [60.0, 1.5]),
                maxfev=2000
            )
            
            omega_fit, zeta_fit = popt
            pred = self.spring_model(t, omega_fit, zeta_fit)
            mse = np.mean((progress - pred)**2)
            
            params = {
                "omega": float(omega_fit),
                "zeta": float(zeta_fit),
                "stiffness": float(omega_fit**2),
                "damping_ratio": float(zeta_fit)
            }
            
            return params, mse

        except Exception as e:
            print(f"Spring fitting error: {e}")
            return {"omega": 15.0, "zeta": 0.7, "stiffness": 225.0, "damping_ratio": 0.7}, 999.0

    def fit_bezier(
        self,
        t: np.ndarray,
        progress: np.ndarray
    ) -> Tuple[Dict, float]:
        """
        Fit cubic Bézier model to trajectory data.
        
        Args:
            t: Time array (normalized to [0,1])
            progress: Progress values (normalized 0-1)
            
        Returns:
            Tuple of (parameters dict, MSE)
        """
        try:
            popt, _ = curve_fit(
                self.cubic_bezier_1d,
                t,
                progress,
                p0=[0.4, 0.2],
                bounds=([-1.0, -1.0], [2.0, 2.0]),
                maxfev=2000
            )
            
            p1_fit, p2_fit = popt
            pred = self.cubic_bezier_1d(t, p1_fit, p2_fit)
            mse = np.mean((progress - pred)**2)
            
            params = {
                "handles": [0.25, float(p1_fit), 0.25, float(p2_fit)],
                "p1": float(p1_fit),
                "p2": float(p2_fit)
            }
            
            return params, mse

        except Exception as e:
            print(f"Bézier fitting error: {e}")
            return {"handles": [0.25, 0.1, 0.25, 1.0], "p1": 0.1, "p2": 1.0}, 999.0

    def fit_best_model(
        self,
        t: np.ndarray,
        progress: np.ndarray
    ) -> Dict:
        """
        Fit both models and return the best one.
        
        Args:
            t: Time array
            progress: Progress values
            
        Returns:
            Dictionary with best fit type and parameters
        """
        spring_params, spring_mse = self.fit_spring(t, progress)
        bezier_params, bezier_mse = self.fit_bezier(t, progress)

        # Choose based on MSE
        if spring_mse < bezier_mse and spring_params["damping_ratio"] < 0.9:
            return {
                "fit_type": "spring",
                "metrics": {
                    **spring_params,
                    "spring_mse": float(spring_mse),
                    "bezier_mse": float(bezier_mse)
                }
            }
        else:
            return {
                "fit_type": "bezier",
                "metrics": {
                    **bezier_params,
                    "spring_mse": float(spring_mse),
                    "bezier_mse": float(bezier_mse)
                }
            }


def fit_animation_curve(
    trajectory: List[Dict],
    metric: str = "scale"
) -> Dict:
    """
    Fit animation curve to trajectory data.
    
    Args:
        trajectory: List of trajectory dictionaries
        metric: Which metric to fit ('x', 'y', 'scale', 'rotation')
        
    Returns:
        Dictionary with fit results
    """
    if len(trajectory) < 3:
        return {
            "fit_type": "none",
            "metrics": {},
            "raw_telemetry": trajectory
        }

    # Extract metric and time
    values = np.array([frame[metric] for frame in trajectory])
    times = np.array([frame["t"] for frame in trajectory])

    # Normalize progress
    start_val = values[0]
    end_val = values[-1]
    delta = end_val - start_val

    if abs(delta) < 1e-4:
        # No significant motion
        return {
            "fit_type": "static",
            "metrics": {},
            "raw_telemetry": trajectory
        }

    normalized = (values - start_val) / delta
    t_normalized = (times - times[0]) / (times[-1] - times[0])

    # Fit curve
    fitter = CurveFitter()
    result = fitter.fit_best_model(t_normalized, normalized)

    # Add telemetry
    result["raw_telemetry"] = [
        {
            "t": float(t),
            "progress": float(p),
            "raw_value": float(v)
        }
        for t, p, v in zip(times, normalized, values)
    ]

    return result
