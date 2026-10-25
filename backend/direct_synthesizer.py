"""
Direct Synthesizer Module
Uses Gemini Vision for direct video-to-code synthesis.
No OpenCV tracking or SciPy fitting - pure AI vision.
"""

import base64
from google import genai
from google.genai import types


def synthesize_from_video(
    video_path: str,
    target_framework: str = "Jetpack Compose",
    model: str = "gemini-2.0-flash"
) -> str:
    """
    Synthesize UI code directly from video using Gemini Vision.
    
    Args:
        video_path: Path to video file
        target_framework: Target framework (Jetpack Compose, Flutter, Framer Motion)
        model: Gemini model to use
        
    Returns:
        Generated code string
    """
    client = genai.Client()
    
    # Read video file and encode as base64
    with open(video_path, "rb") as f:
        video_bytes = f.read()
    
    print(f"Generating {target_framework} code with {model}...")
    
    # Generate code using the video directly
    prompt = f"""You are an expert creative technologist and mobile UI engineer.
Analyze this UI/UX animation video carefully.

Your task:
Synthesize drop-in, production-ready {target_framework} code recreating the visual design, topology changes, and physics shown in this clip.

Deconstruct and implement:
1. Visual styling: colors, gradients, corner radii, borders, drop shadows, and layout hierarchies.
2. Fluid geometry: implement any custom Shapes, Paths, Canvas cutouts, or morphing pills directly.
3. Natural choreography: extract spring parameters, dampening, staggers, and squash-and-stretch. Map them to standard {target_framework} animation APIs.
4. Interactive state: encapsulate the entire interaction into a self-contained component toggled by click/tap.

Return ONLY clean, production-ready code with all necessary imports. No markdown wrappers, conversational filler, or pseudo-code.
"""

    response = client.models.generate_content(
        model=model,
        contents=[
            prompt,
            types.Part.from_bytes(data=video_bytes, mime_type="video/mp4")
        ]
    )
    
    print("Code generation complete")
    return response.text


def synthesize_multi_framework(
    video_path: str,
    frameworks: list = None,
    model: str = "gemini-2.0-flash"
) -> dict:
    """
    Synthesize code for multiple frameworks.
    
    Args:
        video_path: Path to video file
        frameworks: List of frameworks to generate for
        model: Gemini model to use
        
    Returns:
        Dictionary mapping framework names to generated code
    """
    if frameworks is None:
        frameworks = ["Jetpack Compose", "Flutter", "Framer Motion"]
    
    results = {}
    for framework in frameworks:
        print(f"Generating code for {framework}...")
        try:
            code = synthesize_from_video(video_path, framework, model)
            results[framework] = code
        except Exception as e:
            print(f"Error generating {framework} code: {e}")
            results[framework] = f"Error: {str(e)}"
    
    return results
