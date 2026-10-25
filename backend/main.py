"""
MotionForge Direct API
Purged of all OpenCV tracking and SciPy fitting.
Pure AI-driven video-to-code synthesis.
"""

import os
import shutil
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from direct_synthesizer import synthesize_from_video, synthesize_multi_framework

app = FastAPI(title="MotionForge Direct API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "temp_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.post("/api/synthesize")
async def synthesize_ui(
    video: UploadFile = File(...),
    framework: str = Form("Jetpack Compose")
):
    """
    Direct video-to-code synthesis using Gemini Vision.
    No tracking, no fitting - pure AI vision.
    """
    temp_path = os.path.join(UPLOAD_DIR, video.filename)
    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(video.file, buffer)
            
        code = synthesize_from_video(temp_path, framework)
        return {"status": "success", "code": code}
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@app.post("/api/synthesize-multi")
async def synthesize_multi(
    video: UploadFile = File(...)
):
    """
    Synthesize code for all frameworks at once.
    """
    temp_path = os.path.join(UPLOAD_DIR, video.filename)
    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(video.file, buffer)
            
        codes = synthesize_multi_framework(temp_path)
        return {"status": "success", "codes": codes}
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@app.get("/")
async def root():
    return {
        "message": "MotionForge Direct API",
        "version": "2.0",
        "description": "Pure AI-driven video-to-code synthesis - no tracking"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
