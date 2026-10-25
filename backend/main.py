from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import cv2
import numpy as np
from scipy.optimize import curve_fit
from scipy.ndimage import gaussian_filter1d
import json
import tempfile
import os
import math
import base64
from google import genai
from google.genai import types

app = FastAPI(title="MotionSteal API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ROI(BaseModel):
    x: int
    y: int
    w: int
    h: int


class MotionAnalysisRequest(BaseModel):
    roi: ROI
    mode: str  # "translate" or "fill_progress"
    fps_override: Optional[float] = None


def spring_model(t, zeta, omega):
    """Underdamped/critically damped harmonic oscillator model"""
    if zeta >= 1.0:
        # Critically damped
        return 1.0 - np.exp(-omega * t) * (1 + omega * t)
    else:
        # Underdamped
        omega_d = omega * np.sqrt(1 - zeta**2)
        return 1.0 - np.exp(-zeta * omega * t) * (
            np.cos(omega_d * t) + (zeta / np.sqrt(1 - zeta**2)) * np.sin(omega_d * t)
        )


def bezier_model(t, y1, y2):
    """Cubic Bézier curve with fixed endpoints (0,0) and (1,1)"""
    return 3 * (1 - t) ** 2 * t * y1 + 3 * (1 - t) * t ** 2 * y2 + t ** 3


def trim_idle_frames(telemetry, velocity_threshold=0.05):
    """Trim stationary frames at start and end based on velocity threshold"""
    if len(telemetry) < 3:
        return telemetry

    # Calculate velocities
    velocities = []
    for i in range(1, len(telemetry)):
        dt = telemetry[i]["t"] - telemetry[i - 1]["t"]
        if dt > 0:
            dx = telemetry[i]["progress"] - telemetry[i - 1]["progress"]
            velocities.append(abs(dx / dt))
        else:
            velocities.append(0)

    if not velocities:
        return telemetry

    max_velocity = max(velocities)
    threshold = max_velocity * velocity_threshold

    # Find start index
    start_idx = 0
    for i, v in enumerate(velocities):
        if v > threshold:
            start_idx = i
            break

    # Find end index
    end_idx = len(telemetry) - 1
    for i in range(len(velocities) - 1, -1, -1):
        if velocities[i] > threshold:
            end_idx = i + 1
            break

    return telemetry[start_idx:end_idx]


def fit_curves(telemetry):
    """Fit both spring and Bézier models to the data"""
    if len(telemetry) < 3:
        return None, None, None, None, None, None

    t = np.array([point["t"] for point in telemetry])
    progress = np.array([point["progress"] for point in telemetry])

    # Normalize time to 0-1 range
    t_norm = (t - t[0]) / (t[-1] - t[0]) if t[-1] > t[0] else t

    # Fit spring model
    try:
        # Initial guesses: zeta=0.5, omega=10
        spring_params, _ = curve_fit(
            spring_model, t_norm, progress, p0=[0.5, 10.0], maxfev=10000
        )
        zeta, omega = spring_params
        spring_pred = spring_model(t_norm, zeta, omega)
        spring_mse = np.mean((spring_pred - progress) ** 2)
    except:
        spring_mse = float("inf")
        zeta, omega = 0.5, 10.0

    # Fit Bézier model
    try:
        # Initial guesses: y1=0.25, y2=0.25
        bezier_params, _ = curve_fit(
            bezier_model, t_norm, progress, p0=[0.25, 0.25], maxfev=10000
        )
        y1, y2 = bezier_params
        bezier_pred = bezier_model(t_norm, y1, y2)
        bezier_mse = np.mean((bezier_pred - progress) ** 2)
    except:
        bezier_mse = float("inf")
        y1, y2 = 0.25, 0.25

    return spring_mse, zeta, omega, bezier_mse, y1, y2


def generate_compose_code(fit_type, metrics, duration_ms):
    """Generate Jetpack Compose code based on fit type"""
    if fit_type == "spring":
        damping_ratio = metrics.get("damping_ratio", 0.5)
        stiffness = metrics.get("stiffness", 100.0)
        return f"""// Spring animation based on extracted physics
val springSpec = spring<Float>(
    dampingRatio = {damping_ratio:.2f}f,
    stiffness = {stiffness:.1f}f
)

// Usage in animateFloatAsState or animate*AsState
val animatedValue by animateFloatAsState(
    targetValue = targetValue,
    animationSpec = springSpec,
    label = "motion"
)"""
    elif fit_type == "bezier":
        handles = metrics.get("bezier_handles", [0.25, 0.1, 0.25, 1.0])
        return f"""// Cubic Bézier easing based on extracted curve
val bezierEasing = CubicBezierEasing(
    {handles[0]:.2f}f, {handles[1]:.2f}f,
    {handles[2]:.2f}f, {handles[3]:.2f}f
)

// Usage in tween
val tweenSpec = tween<Float>(
    durationMillis = {duration_ms},
    easing = bezierEasing
)

// Or directly in animate*AsState
val animatedValue by animateFloatAsState(
    targetValue = targetValue,
    animationSpec = tweenSpec,
    label = "motion"
)"""
    else:
        return f"""// Keyframe animation for complex motion
val keyframeSpec = keyframes {{
    durationMillis = {duration_ms}
    // Add keyframes based on telemetry data
    // 0f at 0ms using LinearEasing
    // 1f at {duration_ms}ms using LinearEasing
}}"""


def generate_framer_motion_code(fit_type, metrics, duration_ms):
    """Generate Framer Motion (React) code based on fit type"""
    if fit_type == "spring":
        damping_ratio = metrics.get("damping_ratio", 0.5)
        stiffness = metrics.get("stiffness", 100.0)
        omega = math.sqrt(stiffness)
        damping = 2 * damping_ratio * omega
        return f"""// Spring animation based on extracted physics
<motion.div
  animate={{
    // Your animated properties
  }}
  transition={{
    type: "spring",
    stiffness: {stiffness:.1f},
    damping: {damping:.1f},
    mass: 1.0
  }}
/>"""
    elif fit_type == "bezier":
        handles = metrics.get("bezier_handles", [0.25, 0.1, 0.25, 1.0])
        duration_sec = duration_ms / 1000.0
        return f"""// Cubic Bézier easing based on extracted curve
<motion.div
  animate={{
    // Your animated properties
  }}
  transition={{
    duration: {duration_sec:.3f},
    ease: [0.25, {handles[1]:.2f}, 0.25, {handles[3]:.2f}]
  }}
/>"""
    else:
        duration_sec = duration_ms / 1000.0
        return f"""// Keyframe animation for complex motion
<motion.div
  animate={{
    // Your animated properties
  }}
  transition={{
    duration: {duration_sec:.3f},
    times: [0, 1],
    ease: "linear"
  }}
/>"""


def generate_flutter_code(fit_type, metrics, duration_ms):
    """Generate Flutter code based on fit type"""
    if fit_type == "spring":
        damping_ratio = metrics.get("damping_ratio", 0.5)
        stiffness = metrics.get("stiffness", 100.0)
        omega = math.sqrt(stiffness)
        damping = 2 * damping_ratio * omega
        return f"""// Spring animation based on extracted physics
final springSimulation = SpringSimulation(
  SpringDescription(
    mass: 1.0,
    stiffness: {stiffness:.1f},
    damping: {damping:.1f}
  ),
  0.0,
  1.0,
  0.0,
);

AnimationController _controller = AnimationController(
  vsync: this,
  duration: const Duration(milliseconds: {duration_ms}),
)..repeat(reverse: true);

Animation<double> _animation = CurvedAnimation(
  parent: _controller,
  curve: springSimulation,
);"""
    elif fit_type == "bezier":
        handles = metrics.get("bezier_handles", [0.25, 0.1, 0.25, 1.0])
        return f"""// Cubic Bézier easing based on extracted curve
AnimationController _controller = AnimationController(
  vsync: this,
  duration: const Duration(milliseconds: {duration_ms}),
)..repeat(reverse: true);

Animation<double> _animation = CurvedAnimation(
  parent: _controller,
  curve: const Cubic(0.25, {handles[1]:.2f}, 0.25, {handles[3]:.2f}),
);"""
    else:
        return f"""// Keyframe animation for complex motion
AnimationController _controller = AnimationController(
  vsync: this,
  duration: const Duration(milliseconds: {duration_ms}),
)..repeat(reverse: true);

Animation<double> _animation = CurvedAnimation(
  parent: _controller,
  curve: Curves.linear,
);"""


def process_translate_mode(video_path, roi, fps_override):
    """Process video in translate mode using CSRT tracker"""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise HTTPException(status_code=400, detail="Could not open video file")

    try:
        fps = fps_override if fps_override else cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 30.0  # Default fallback

        # Get first frame
        ret, frame = cap.read()
        if not ret:
            raise HTTPException(status_code=400, detail="Could not read first frame")

        # Initialize tracker - use the available API
        tracker = cv2.TrackerCSRT_create()
        print("Using cv2.TrackerCSRT_create()")
        bbox = (roi["x"], roi["y"], roi["w"], roi["h"])
        tracker.init(frame, bbox)

        telemetry = []
        frame_count = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            success, bbox = tracker.update(frame)
            if success:
                x, y, w, h = [int(v) for v in bbox]
                center_x = x + w / 2
                center_y = y + h / 2
                scale = w / roi["w"]  # Relative scale

                telemetry.append(
                    {
                        "t": frame_count / fps,
                        "progress": 0.0,  # Will be normalized later
                        "x": center_x,
                        "y": center_y,
                        "scale": scale,
                    }
                )

            frame_count += 1
    finally:
        cap.release()

    if len(telemetry) < 3:
        raise HTTPException(
            status_code=400, detail="Not enough tracking data points"
        )

    # Determine dominant axis
    x_range = max(t["x"] for t in telemetry) - min(t["x"] for t in telemetry)
    y_range = max(t["y"] for t in telemetry) - min(t["y"] for t in telemetry)

    dominant_axis = "TranslationX" if x_range > y_range else "TranslationY"

    # Normalize progress based on dominant axis
    if dominant_axis == "TranslationX":
        positions = [t["x"] for t in telemetry]
    else:
        positions = [t["y"] for t in telemetry]

    min_pos = min(positions)
    max_pos = max(positions)
    pos_range = max_pos - min_pos

    if pos_range > 0:
        for t in telemetry:
            t["progress"] = (t[dominant_axis.replace("Translation", "").lower()] - min_pos) / pos_range

    # Trim idle frames
    telemetry = trim_idle_frames(telemetry)

    if len(telemetry) < 3:
        raise HTTPException(
            status_code=400, detail="Not enough data after trimming idle frames"
        )

    # Fit curves
    spring_mse, zeta, omega, bezier_mse, y1, y2 = fit_curves(telemetry)

    # Determine fit type
    fit_type = "spring" if spring_mse < bezier_mse else "bezier"

    # Calculate stiffness from omega (stiffness = omega^2 for mass=1)
    stiffness = omega ** 2

    duration_ms = int((telemetry[-1]["t"] - telemetry[0]["t"]) * 1000)

    metrics = {
        "spring_mse": float(spring_mse) if spring_mse != float("inf") else None,
        "damping_ratio": float(zeta),
        "stiffness": float(stiffness),
        "bezier_mse": float(bezier_mse) if bezier_mse != float("inf") else None,
        "bezier_handles": [0.25, float(y1), 0.25, float(y2)],
    }

    compose_code = generate_compose_code(fit_type, metrics, duration_ms)
    framer_code = generate_framer_motion_code(fit_type, metrics, duration_ms)
    flutter_code = generate_flutter_code(fit_type, metrics, duration_ms)

    return {
        "status": "success",
        "dominant_axis": dominant_axis,
        "duration_ms": duration_ms,
        "fit_type": fit_type,
        "metrics": metrics,
        "raw_telemetry": telemetry,
        "code": {
            "compose": compose_code,
            "framer": framer_code,
            "flutter": flutter_code,
        },
    }


def extract_slider_level(crop, is_vertical=True):
    """
    Computes fill percentage (0.0 to 1.0) of a slider frame
    by analyzing the gradient boundary along the primary axis.
    """
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    if is_vertical:
        profile = np.mean(blurred, axis=1)  # 1D vertical profile
        grad = np.abs(np.diff(profile))
        if len(grad) == 0:
            return 0.0
        boundary_idx = np.argmax(grad)
        fill_ratio = (len(profile) - boundary_idx) / float(len(profile))
    else:
        profile = np.mean(blurred, axis=0)  # 1D horizontal profile
        grad = np.abs(np.diff(profile))
        if len(grad) == 0:
            return 0.0
        boundary_idx = np.argmax(grad)
        fill_ratio = boundary_idx / float(len(profile))

    return float(np.clip(fill_ratio, 0.0, 1.0))


def process_fill_progress_mode(video_path, roi, fps_override, orientation="auto"):
    """Process video in fill_progress mode for sliders/progress bars using improved algorithm"""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise HTTPException(status_code=400, detail="Could not open video file")

    try:
        fps = fps_override if fps_override else cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 30.0

        telemetry = []
        frame_count = 0

        # Determine orientation
        if orientation == "vertical":
            is_vertical = True
        elif orientation == "horizontal":
            is_vertical = False
        else:
            # Auto-detect based on ROI aspect ratio
            is_vertical = roi["h"] > roi["w"]

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Crop to ROI
            x, y, w, h = roi["x"], roi["y"], roi["w"], roi["h"]
            cropped = frame[y : y + h, x : x + w]

            if cropped.size == 0:
                break

            # Use improved fill extraction with Gaussian blur
            fill_level = extract_slider_level(cropped, is_vertical=is_vertical)

            telemetry.append(
                {
                    "t": frame_count / fps,
                    "progress": fill_level,
                    "x": roi["x"] + w / 2,
                    "y": roi["y"] + h / 2,
                    "scale": 1.0,
                }
            )

            frame_count += 1
    finally:
        cap.release()

    if len(telemetry) < 3:
        raise HTTPException(
            status_code=400, detail="Not enough data points in fill progress mode"
        )

    # Improved velocity-based trimming with Gaussian smoothing
    fills = np.array([t["progress"] for t in telemetry])
    t_raw = np.array([t["t"] for t in telemetry])

    smoothed = gaussian_filter1d(fills, sigma=2)
    velocity = np.abs(np.gradient(smoothed, t_raw))
    max_v = np.max(velocity)
    v_thresh = max(max_v * 0.05, 0.02)

    moving_indices = np.where(velocity > v_thresh)[0]
    if len(moving_indices) > 0:
        start_idx = max(0, moving_indices[0] - 1)
        end_idx = min(len(fills) - 1, moving_indices[-1] + 1)
    else:
        start_idx = 0
        end_idx = len(fills) - 1

    telemetry = telemetry[start_idx:end_idx+1]

    if len(telemetry) < 3:
        raise HTTPException(
            status_code=400, detail="Not enough data after trimming idle frames"
        )

    # Normalize progress
    fills = np.array([t["progress"] for t in telemetry])
    t = np.array([t["t"] for t in telemetry])
    t = t - t[0]

    start_fill = fills[0]
    end_fill = fills[-1]
    delta = end_fill - start_fill

    norm_progress = (fills - start_fill) / delta if abs(delta) > 1e-4 else np.zeros_like(fills)

    # Update telemetry with normalized progress
    for i, t in enumerate(telemetry):
        t["progress"] = float(norm_progress[i])
        t["t"] = float(t[i])

    # Fit curves with improved bounds
    spring_mse, zeta, omega, bezier_mse, y1, y2 = fit_curves(telemetry)

    # Determine fit type with damping ratio consideration
    fit_type = "spring" if (spring_mse < bezier_mse and zeta < 0.90) else "bezier"

    stiffness = omega ** 2
    duration_ms = int((telemetry[-1]["t"] - telemetry[0]["t"]) * 1000)

    metrics = {
        "spring_mse": float(spring_mse) if spring_mse != float("inf") else None,
        "damping_ratio": float(zeta),
        "stiffness": float(stiffness),
        "bezier_mse": float(bezier_mse) if bezier_mse != float("inf") else None,
        "bezier_handles": [0.25, float(y1), 0.25, float(y2)],
    }

    compose_code = generate_compose_code(fit_type, metrics, duration_ms)
    framer_code = generate_framer_motion_code(fit_type, metrics, duration_ms)
    flutter_code = generate_flutter_code(fit_type, metrics, duration_ms)

    return {
        "status": "success",
        "dominant_axis": "FillProgress",
        "duration_ms": duration_ms,
        "fit_type": fit_type,
        "metrics": metrics,
        "raw_telemetry": telemetry,
        "code": {
            "compose": compose_code,
            "framer": framer_code,
            "flutter": flutter_code,
        },
    }


def get_rotation_angle(prev_gray, curr_gray, roi):
    """Compute rotation angle using optical flow"""
    x, y, w, h = roi
    mask = np.zeros_like(prev_gray)
    mask[y:y+h, x:x+w] = 255
    p0 = cv2.goodFeaturesToTrack(prev_gray, mask=mask, maxCorners=50, qualityLevel=0.01, minDistance=5)
    if p0 is None or len(p0) < 4:
        return 0.0
    p1, status, _ = cv2.calcOpticalFlowPyrLK(prev_gray, curr_gray, p0, None)
    good_p0 = p0[status == 1]
    good_p1 = p1[status == 1]
    if len(good_p0) < 4:
        return 0.0
    matrix, _ = cv2.estimateAffinePartial2D(good_p0, good_p1)
    if matrix is None:
        return 0.0
    # Rotation angle from affine matrix: theta = atan2(M[0,1], M[0,0])
    angle_rad = np.arctan2(matrix[0, 1], matrix[0, 0])
    return float(np.degrees(angle_rad))


def process_multi_element_mode(video_path, rois, fps_override):
    """Process video in multi-element mode with rotation tracking"""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise HTTPException(status_code=400, detail="Could not open video file")

    try:
        fps = fps_override if fps_override else cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 30.0

        ret, frame = cap.read()
        if not ret:
            raise HTTPException(status_code=400, detail="Could not read first frame")

        # Initialize trackers for each ROI
        trackers = []
        for roi in rois:
            tracker = cv2.TrackerCSRT_create()
            bbox = (roi["x"], roi["y"], roi["w"], roi["h"])
            tracker.init(frame, bbox)
            trackers.append(tracker)

        element_tracks = {i: [] for i in range(len(rois))}
        cumulative_angles = {i: 0.0 for i in range(len(rois))}
        prev_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frame_idx = 0

        # Save initial crops for vision synthesis
        element_crops = {}
        for i, roi in enumerate(rois):
            x, y, w, h = roi["x"], roi["y"], roi["w"], roi["h"]
            crop = frame[y:y+h, x:x+w]
            _, buffer = cv2.imencode('.png', crop)
            element_crops[f"start_{i}"] = base64.b64encode(buffer).decode('utf-8')

        last_valid_frame = frame.copy()

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            last_valid_frame = frame.copy()
            curr_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            t_sec = frame_idx / fps

            for i, tracker in enumerate(trackers):
                success, box = tracker.update(frame)
                if success:
                    x, y, w, h = [int(v) for v in box]
                    d_theta = get_rotation_angle(prev_gray, curr_gray, (x, y, w, h))
                    cumulative_angles[i] += d_theta

                    element_tracks[i].append({
                        "t": round(t_sec, 4),
                        "x": x + w / 2.0,
                        "y": y + h / 2.0,
                        "w": w,
                        "h": h,
                        "rot_deg": round(cumulative_angles[i], 2)
                    })

            prev_gray = curr_gray
            frame_idx += 1
    finally:
        cap.release()

    # Save final crops for vision synthesis
    for i, track in enumerate(element_tracks):
        if len(track) > 0:
            last_record = track[-1]
            cx, cy = int(last_record["x"]), int(last_record["y"])
            hw, hh = int(last_record["w"] // 2), int(last_record["h"] // 2)
            y1, y2 = max(0, cy - hh), min(last_valid_frame.shape[0], cy + hh)
            x1, x2 = max(0, cx - hw), min(last_valid_frame.shape[1], cx + hw)
            crop = last_valid_frame[y1:y2, x1:x2]
            _, buffer = cv2.imencode('.png', crop)
            element_crops[f"end_{i}"] = base64.b64encode(buffer).decode('utf-8')

    # Calculate stagger delays
    stagger_delays = []
    for i in range(len(rois)):
        if len(element_tracks[i]) > 0:
            start_time = element_tracks[i][0]["t"]
            stagger_delays.append(start_time)

    # Compute delays relative to first element
    if stagger_delays:
        base_time = min(stagger_delays)
        stagger_delays = [d - base_time for d in stagger_delays]

    # Generate staggered animation code
    stagger_code = generate_staggered_compose_code(rois, stagger_delays, element_tracks)

    return {
        "status": "success",
        "total_elements": len(rois),
        "stagger_delays": stagger_delays,
        "element_tracks": element_tracks,
        "element_crops": element_crops,
        "compose_code": stagger_code,
    }


def generate_staggered_compose_code(rois, stagger_delays, element_tracks):
    """Generate Jetpack Compose code for staggered multi-element animations"""
    code = """// Staggered multi-element animation
@Composable
fun StaggeredAnimation() {
    val elements = listOf(
"""

    for i, (roi, delay) in enumerate(zip(rois, stagger_delays)):
        code += f"""        ElementData(
            id = {i},
            startX = {roi['x']}f,
            startY = {roi['y']}f,
            delay = {delay * 1000:.0f}ms
        ),
"""

    code += """    )

    elements.forEachIndexed { index, element ->
        val animatedState by animateFloatAsState(
            targetValue = 1f,
            animationSpec = tween(
                durationMillis = 300,
                easing = FastOutSlowInEasing,
                delayMillis = element.delay
            ),
            label = "element_$index"
        )
        // Render each element with animatedState
    }
}"""

    return code


@app.post("/api/auto-segment")
async def auto_segment(
    video: UploadFile = File(...),
):
    """Automatically detect UI elements using Canny edge detection and contour analysis"""
    try:
        # Save uploaded video to temp file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        content = await video.read()
        temp_file.write(content)
        temp_file.close()
        temp_file_path = temp_file.name
        print(f"Saved video to: {temp_file_path}")

        try:
            # Open video and read first frame
            cap = cv2.VideoCapture(temp_file_path)
            if not cap.isOpened():
                raise HTTPException(status_code=400, detail="Could not open video file")

            ret, frame = cap.read()
            if not ret:
                raise HTTPException(status_code=400, detail="Could not read first frame")

            cap.release()

            # Check if frame is valid
            if frame is None or frame.size == 0:
                raise HTTPException(status_code=400, detail="Invalid frame from video")

            # Convert to grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Apply Gaussian blur to reduce noise
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)

            # Canny edge detection
            edges = cv2.Canny(blurred, 30, 100)

            # Check if edges are empty
            if edges is None or edges.size == 0 or np.count_nonzero(edges) == 0:
                print("No edges detected, using adaptive thresholding fallback")
                # Fallback: use adaptive thresholding
                edges = cv2.adaptiveThreshold(
                    gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY, 11, 2
                )

            # Dilate to bridge borders
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
            dilated = cv2.dilate(edges, kernel, iterations=1)

            # Find contours with error handling
            try:
                contours, hierarchy = cv2.findContours(
                    dilated, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
                )
            except cv2.error as e:
                print(f"Contour detection error: {e}")
                # Fallback: use RETR_EXTERNAL
                contours, hierarchy = cv2.findContours(
                    dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
                )

            # Check if contours were found
            if contours is None or len(contours) == 0:
                print("No contours found, returning empty proposals")
                return {
                    "status": "success",
                    "proposals": [],
                    "total_detected": 0,
                    "message": "No UI elements detected. Try manual selection."
                }

            # Filter contours
            frame_area = frame.shape[0] * frame.shape[1]
            proposals = []

            for contour in contours:
                # Get bounding rect
                x, y, w, h = cv2.boundingRect(contour)
                area = w * h

                # Filter by area
                if area < 0.002 * frame_area:  # Less than 0.2% of frame area
                    continue
                if area > 0.85 * frame_area:  # More than 85% of frame area
                    continue

                # Filter by size
                if w < 20 or h < 20:
                    continue

                proposals.append({
                    "x": int(x),
                    "y": int(y),
                    "w": int(w),
                    "h": int(h),
                    "area": int(area)
                })

            # Sort by area descending and take top 15
            proposals.sort(key=lambda p: p["area"], reverse=True)
            proposals = proposals[:15]

            # Remove area from output
            output_proposals = [
                {"x": p["x"], "y": p["y"], "w": p["w"], "h": p["h"]}
                for p in proposals
            ]

            print(f"Found {len(proposals)} UI element proposals")

            return {
                "status": "success",
                "proposals": output_proposals,
                "total_detected": len(proposals),
                "message": f"Detected {len(proposals)} UI elements."
            }

        finally:
            # Clean up temp file
            import time
            time.sleep(0.1)
            try:
                os.unlink(temp_file_path)
                print(f"Deleted temp file: {temp_file_path}")
            except Exception as e:
                print(f"Could not delete temp file: {e}")

    except Exception as e:
        print(f"Auto-segmentation error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


def synthesize_styled_ui_with_gemini(start_crop_bytes, end_crop_bytes, duration_ms, max_rotation, api_key=None):
    """Use Gemini AI to generate fully styled Jetpack Compose code from visual crops"""
    if not api_key:
        # Try to get from environment variable
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            return None, "Google API key not provided"

    try:
        client = genai.Client(api_key=api_key)

        prompt = f"""
You are an expert Jetpack Compose engineer and UI designer.
Look at these two cropped images representing the initial and final states of a UI component:
- Image 1: Initial state
- Image 2: Final settled state

Motion Telemetry:
- Duration: {duration_ms} ms
- Max Rotation Detected: {max_rotation:.1f} degrees
- Primary Motion: Translation & Scaling

Your Task:
1. Reconstruct the static UI layout in Jetpack Compose:
   - Identify background colors / gradients (extract approximate hex codes).
   - Corner radius (RoundedCornerShape).
   - Inner typography, borders, drop shadows, or icons.
2. Wire the animation into the Composable:
   - Use `remember {{ Animatable(0f) }}` or `animateFloatAsState`.
   - Apply translation, scale, and rotationZ directly via `Modifier.graphicsLayer {{ ... }}`.
3. Output ONLY production-ready Kotlin code with imports. No conversational filler.
"""

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                prompt,
                types.Part.from_bytes(data=start_crop_bytes, mime_type="image/png"),
                types.Part.from_bytes(data=end_crop_bytes, mime_type="image/png")
            ]
        )

        return response.text, None
    except Exception as e:
        return None, str(e)


@app.post("/api/vision-synthesize")
async def vision_synthesize(
    start_crop: UploadFile = File(...),
    end_crop: UploadFile = File(...),
    duration_ms: int = Form(...),
    max_rotation: float = Form(0.0),
    api_key: Optional[str] = Form(None),
):
    """Generate fully styled Jetpack Compose code using Gemini AI"""
    try:
        start_bytes = await start_crop.read()
        end_bytes = await end_crop.read()

        compose_code, error = synthesize_styled_ui_with_gemini(
            start_bytes,
            end_bytes,
            duration_ms,
            max_rotation,
            api_key
        )

        if error:
            raise HTTPException(status_code=500, detail=error)

        # Generate code for all targets
        framer_code = generate_framer_motion_code("spring", {"damping_ratio": 0.5, "stiffness": 100.0}, duration_ms)
        flutter_code = generate_flutter_code("spring", {"damping_ratio": 0.5, "stiffness": 100.0}, duration_ms)

        return {
            "status": "success",
            "code": {
                "compose": compose_code,
                "framer": framer_code,
                "flutter": flutter_code,
            },
        }
    except Exception as e:
        print(f"Vision synthesis error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/analyze-motion")
async def analyze_motion(
    video: UploadFile = File(...),
    roi: str = Form(...),
    mode: str = Form(...),
    orientation: Optional[str] = Form("auto"),
    rois: Optional[str] = Form(None),
    fps_override: Optional[float] = Form(None),
):
    """Analyze motion from uploaded video"""
    try:
        # Parse ROI JSON
        roi_data = json.loads(roi)
        print(f"ROI: {roi_data}")

        # Parse multiple ROIs if provided
        rois_data = None
        if rois:
            rois_data = json.loads(rois)
            print(f"Multiple ROIs: {len(rois_data)} elements")

        # Validate mode
        if mode not in ["translate", "fill_progress", "multi_element"]:
            raise HTTPException(
                status_code=400, detail="Invalid mode. Must be 'translate', 'fill_progress', or 'multi_element'"
            )

        print(f"Mode: {mode}")
        print(f"Orientation: {orientation}")
        print(f"Video file: {video.filename}, size: {video.size}")

        # Save uploaded video to temp file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        content = await video.read()
        print(f"Read {len(content)} bytes from video")
        temp_file.write(content)
        temp_file.close()
        temp_file_path = temp_file.name
        print(f"Saved to: {temp_file_path}")

        try:
            if mode == "translate":
                print("Starting translate mode processing...")
                result = process_translate_mode(temp_file_path, roi_data, fps_override)
            elif mode == "fill_progress":
                print("Starting fill progress mode processing...")
                result = process_fill_progress_mode(temp_file_path, roi_data, fps_override, orientation)
            elif mode == "multi_element":
                print("Starting multi-element mode processing...")
                if not rois_data or len(rois_data) == 0:
                    raise HTTPException(status_code=400, detail="Multi-element mode requires at least one ROI")
                result = process_multi_element_mode(temp_file_path, rois_data, fps_override)

            print("Processing complete!")
            return result
        finally:
            # Give OpenCV time to release the file handle
            import time
            time.sleep(0.1)
            try:
                os.unlink(temp_file_path)
                print(f"Deleted temp file: {temp_file_path}")
            except Exception as e:
                print(f"Could not delete temp file: {e}")
                pass  # Ignore deletion errors

    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        raise HTTPException(status_code=400, detail="Invalid ROI JSON format")
    except Exception as e:
        print(f"Error during analysis: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    return {"message": "MotionSteal API is running"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
