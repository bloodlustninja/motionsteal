# MotionSteal Web Dashboard

A web-based developer tool that extracts animation physics from screen-recording MP4s and generates production-ready Jetpack Compose code.

## Architecture

- **Backend**: Python 3.10+ (FastAPI, Uvicorn, OpenCV headless, NumPy, SciPy)
- **Frontend**: React + Vite + Tailwind CSS
- **Communication**: REST API with multipart form-data for video uploads

## Features

### Backend (`backend/`)
- FastAPI backend with `/api/analyze-motion` endpoint
- Two analysis modes:
  - **Translate Mode**: Uses OpenCV CSRT tracker to follow motion across frames
  - **Fill Progress Mode**: Analyzes slider/progress bar fill changes
- Physics curve fitting:
  - Spring model (damped harmonic oscillator)
  - Cubic Bézier curve fitting
- Automatic detection of best-fit model based on MSE
- Jetpack Compose code generation with spring/tween/keyframes

### Frontend (`frontend/`)
- Drag-and-drop MP4 upload
- Video player with canvas overlay
- Interactive ROI selection tool (click-and-drag bounding box)
- Mode selector (Translation vs Fill Progress)
- Interactive charts showing raw tracking vs fitted curves
- Live animation preview using CSS Web Animations API
- Syntax-highlighted Jetpack Compose code export with copy-to-clipboard

## Setup Instructions

### Prerequisites
- Python 3.10+
- Node.js 18+
- npm or yarn

### Backend Setup

1. Navigate to the backend directory:
```bash
cd backend
```

2. Create a virtual environment (recommended):
```bash
python -m venv venv
```

3. Install dependencies:
```bash
venv/Scripts/python.exe -m pip install -r requirements.txt  # Windows
# or
venv/bin/python -m pip install -r requirements.txt  # Linux/Mac
```

4. Start the backend server:
```bash
venv/Scripts/python.exe main.py  # Windows
# or
venv/bin/python main.py  # Linux/Mac
```

The backend will run on `http://localhost:8000`

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm run dev
```

Note: This project uses Tailwind CSS v4 with the new `@tailwindcss/postcss` plugin. The configuration is simplified compared to v3.

The frontend will run on `http://localhost:3000`

## Usage

1. Open `http://localhost:3000` in your browser
2. Upload an MP4 screen recording
3. Pause the video at the frame where motion begins
4. Click and drag on the video to select the region of interest (ROI)
5. Select the analysis mode:
   - **Physical Motion (Translation/Scale)**: For moving UI elements
   - **Component Fill (Slider/Level)**: For progress bars, sliders, etc.
6. Click "Analyze Motion"
7. View results:
   - Motion metrics (duration, damping ratio, stiffness, etc.)
   - Interactive chart showing raw tracking vs fitted curve
   - Live preview of the extracted animation
   - Generated Jetpack Compose code ready to copy

## API Endpoint

### POST /api/analyze-motion

**Request:**
- `video`: MP4 file (multipart/form-data)
- `roi`: JSON string `{"x": int, "y": int, "w": int, "h": int}`
- `mode`: `"translate"` or `"fill_progress"`
- `fps_override`: Optional float

**Response:**
```json
{
  "status": "success",
  "dominant_axis": "TranslationY",
  "duration_ms": 350,
  "fit_type": "spring",
  "metrics": {
    "spring_mse": 0.0012,
    "damping_ratio": 0.72,
    "stiffness": 280.5,
    "bezier_mse": 0.0084,
    "bezier_handles": [0.25, 0.45, 0.25, 1.1]
  },
  "raw_telemetry": [
    { "t": 0.0, "progress": 0.0, "x": 100.0, "y": 200.0, "scale": 1.0 }
  ],
  "compose_code": "// Jetpack Compose AnimationSpec code..."
}
```

## Technical Details

### Physics Models

**Spring Model:**
```
y(t) = 1.0 - exp(-ζωt)(cos(ωd t) + (ζ/√(1-ζ²))sin(ωd t))
```
Where ζ is the damping ratio and ω is the natural frequency.

**Bézier Model:**
```
B(t) = 3(1-t)²t·p₁ + 3(1-t)t²·p₂ + t³
```
With fixed endpoints (0,0) and (1,1).

### Tracking

- Uses OpenCV CSRT tracker for accurate motion tracking
- Auto-trims idle frames at start/end using 5% peak velocity threshold
- Determines dominant motion axis (X or Y)

## Constraints & Edge Cases

- No GUI windows in backend (uses `opencv-python-headless`)
- Graceful error handling for:
  - Short videos (< 5 frames)
  - Failed tracking convergence
  - Unmoving static selections
- Minimum 3 data points required for curve fitting
- Fallback to keyframes for complex/erratic motion (> 2000ms)

## License

MIT
