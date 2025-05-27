from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import os
import uuid
import shutil
import pydicom
from pydicom.pixel_data_handlers.util import apply_voi_lut
from PIL import Image
import numpy as np
import requests
import json
from dotenv import load_dotenv

# --- CONFIG ---
load_dotenv()

# Use environment variables with fallbacks
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "uploads")
ANNOTATION_DIR = os.environ.get("ANNOTATION_DIR", "annotations")
ROBOFLOW_API_URL = "https://detect.roboflow.com/adr/6"
ROBOFLOW_API_KEY = os.environ.get("ROBOFLOW_API_KEY", "demo")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", None)

# Ensure directories exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(ANNOTATION_DIR, exist_ok=True)

# Initialize FastAPI app
app = FastAPI(
    title="Dental DICOM Analyzer API",
    description="AI-Powered Dental X-ray Analysis with Pathology Detection",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS for production
# For development and flexible deployment
development_origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]

# Get production frontend URL from environment variable
frontend_url = os.environ.get("FRONTEND_URL")
if frontend_url:
    allowed_origins = development_origins + [frontend_url]
else:
    # Allow all origins during development/initial deployment
    # You can set FRONTEND_URL environment variable later
    allowed_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Health check endpoint
@app.get("/")
def root():
    return {
        "message": "Dental DICOM Analyzer API",
        "status": "healthy",
        "version": "1.0.0"
    }

@app.get("/health")
def health_check():
    frontend_url = os.environ.get("FRONTEND_URL")
    return {
        "status": "healthy",
        "services": {
            "roboflow": "configured" if ROBOFLOW_API_KEY != "demo" else "demo_mode",
            "groq_llm": "configured" if GROQ_API_KEY else "not_configured"
        },
        "cors": {
            "frontend_url": frontend_url if frontend_url else "not_set",
            "mode": "production" if frontend_url else "development"
        }
    }

def dicom_to_png(dicom_path, png_path):
    """Convert DICOM file to PNG with comprehensive error handling and fallbacks"""
    try:
        ds = pydicom.dcmread(dicom_path, force=True)
        if not hasattr(ds, 'pixel_array'):
            raise ValueError("DICOM file does not contain pixel data")
        try:
            arr = ds.pixel_array
        except Exception as pixel_error:
            try:
                ds.decompress()
                arr = ds.pixel_array
            except Exception as decomp_error:
                raise Exception(f"DICOM decompression failed: {pixel_error} | {decomp_error}")
        try:
            if hasattr(ds, 'VOILUTSequence') or hasattr(ds, 'WindowCenter'):
                arr = apply_voi_lut(arr, ds)
        except Exception:
            pass
        if arr is None or arr.size == 0:
            raise ValueError("Resulting pixel array is empty")
        if len(arr.shape) > 2:
            arr = arr[0] if arr.shape[0] < arr.shape[-1] else arr[:, :, 0]
        arr = arr.astype(float)
        arr_min, arr_max = arr.min(), arr.max()
        if arr_max > arr_min:
            arr = (arr - arr_min) / (arr_max - arr_min) * 255.0
        else:
            arr = np.full_like(arr, 128.0)
        arr = np.uint8(np.clip(arr, 0, 255))
        img = Image.fromarray(arr)
        if img.mode != "L":
            img = img.convert("L")
        if img.size[0] < 10 or img.size[1] < 10:
            raise ValueError(f"Resulting image is too small: {img.size}")
        img.save(png_path, "PNG")
        return png_path
    except Exception as e:
        error_msg = str(e)
        if "requires pylibjpeg" in error_msg:
            detailed_error = (
                f"DICOM decompression failed: {error_msg}. "
                f"This DICOM file uses a compressed format that requires additional dependencies. "
                f"Please ensure the server has pylibjpeg>=1.4.0 and pylibjpeg-libjpeg>=1.3.0 installed."
            )
        elif "JPEG Lossless" in error_msg:
            detailed_error = (
                f"JPEG Lossless compression not supported: {error_msg}. "
                f"This DICOM file uses JPEG Lossless compression which requires pylibjpeg libraries."
            )
        else:
            detailed_error = f"DICOM processing error: {error_msg}"
        raise Exception(detailed_error)

@app.post("/upload/")
async def upload_dicom(file: UploadFile = File(...)):
    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    if not (file.filename.lower().endswith(".dcm") or file.filename.lower().endswith(".rvg")):
        raise HTTPException(status_code=400, detail="File must be .dcm or .rvg")
    
    # Check file size (limit to 50MB)
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset to beginning
    
    if file_size > 50 * 1024 * 1024:  # 50MB limit
        raise HTTPException(status_code=413, detail="File too large (max 50MB)")
    
    if file_size == 0:
        raise HTTPException(status_code=400, detail="Empty file")
    
    # Generate unique file ID
    file_id = str(uuid.uuid4())
    dicom_path = os.path.join(UPLOAD_DIR, f"{file_id}.dcm")
    png_path = os.path.join(UPLOAD_DIR, f"{file_id}.png")
    
    try:
        # Save uploaded DICOM file
        with open(dicom_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        
        # Convert to PNG
        dicom_to_png(dicom_path, png_path)
        
        return {
            "file_id": file_id, 
            "dicom_url": f"/file/{file_id}.dcm", 
            "png_url": f"/file/{file_id}.png"
        }
        
    except Exception as e:
        # Clean up files on error
        for path in [dicom_path, png_path]:
            if os.path.exists(path):
                os.remove(path)
        raise HTTPException(status_code=500, detail=f"DICOM processing failed: {str(e)}")

@app.get("/file/{filename}")
def get_file(filename: str):
    # Security: Prevent directory traversal attacks
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    # Set appropriate media type based on file extension
    if filename.endswith('.png'):
        media_type = "image/png"
    elif filename.endswith('.dcm') or filename.endswith('.rvg'):
        media_type = "application/dicom"
    else:
        media_type = "application/octet-stream"
    
    return FileResponse(file_path, media_type=media_type)

@app.post("/predict/")
def predict(file_id: str):
    png_path = os.path.join(UPLOAD_DIR, f"{file_id}.png")
    if not os.path.exists(png_path):
        raise HTTPException(status_code=404, detail="PNG file not found")
    
    try:
        with open(png_path, "rb") as img_file:
            resp = requests.post(
                f"{ROBOFLOW_API_URL}?api_key={ROBOFLOW_API_KEY}&confidence=30&overlap=50",
                files={"file": img_file},
                timeout=30  # 30 second timeout
            )
        
        if resp.status_code != 200:
            raise HTTPException(
                status_code=500, 
                detail=f"Roboflow API error: {resp.status_code} - {resp.text}"
            )
        
        result = resp.json()
        
        # Validate response structure
        if "predictions" not in result:
            result["predictions"] = []
        
        # Save annotation
        annotation_path = os.path.join(ANNOTATION_DIR, f"{file_id}.json")
        with open(annotation_path, "w") as f:
            json.dump(result, f, indent=2)
        
        return {
            "annotations": result, 
            "annotation_url": f"/annotation/{file_id}.json"
        }
        
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="Roboflow API request timed out")
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Request to Roboflow failed: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")

@app.get("/annotation/{file_id}.json")
def get_annotation(file_id: str):
    annotation_path = os.path.join(ANNOTATION_DIR, f"{file_id}.json")
    if not os.path.exists(annotation_path):
        raise HTTPException(status_code=404, detail="Annotation not found")
    return FileResponse(annotation_path, media_type="application/json")

@app.post("/report/")
def generate_report(file_id: str):
    annotation_path = os.path.join(ANNOTATION_DIR, f"{file_id}.json")
    if not os.path.exists(annotation_path):
        raise HTTPException(status_code=404, detail="Annotation not found")
    
    with open(annotation_path) as f:
        annotations = json.load(f)
    
    prompt = (
        "You are a dental radiologist. Based on the image annotations provided below (which include detected pathologies), "
        "write a concise diagnostic report in clinical language. Output a brief paragraph highlighting: Detected pathologies, "
        "location if possible (e.g., upper left molar), and clinical advice (optional).\n\nAnnotations: "
        + json.dumps(annotations)
    )
    
    if GROQ_API_KEY:
        try:
            from groq import Groq
            client = Groq(api_key=GROQ_API_KEY)
            chat_completion = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
                stream=False,
            )
            report = chat_completion.choices[0].message.content.strip()
        except Exception as e:
            # Fallback to mock report if Groq API fails
            report = f"LLM service temporarily unavailable. Detected pathologies: "
            preds = annotations.get("predictions", [])
            if preds:
                for p in preds:
                    report += f"{p.get('class', 'unknown')} (confidence: {p.get('confidence', 0):.2f}), "
                report = report.rstrip(", ")
            else:
                report += "None detected"
    else:
        report = "Detected pathologies: "
        preds = annotations.get("predictions", [])
        if preds:
            for p in preds:
                report += f"{p.get('class', 'unknown')} (confidence: {p.get('confidence', 0):.2f}), "
            report = report.rstrip(", ")
            report += ". Clinical advice: Please consult your dentist for further evaluation."
        else:
            report = "No pathologies detected."
    
    return {"report": report}

@app.delete("/cleanup/{file_id}")
def cleanup_files(file_id: str):
    """Clean up all files associated with a file_id"""
    files_removed = []
    
    # List of possible files to clean up
    file_patterns = [
        f"{file_id}.dcm",
        f"{file_id}.png",
        f"{file_id}.json"  # annotation file
    ]
    
    for pattern in file_patterns:
        # Check upload directory
        upload_file = os.path.join(UPLOAD_DIR, pattern)
        if os.path.exists(upload_file):
            os.remove(upload_file)
            files_removed.append(f"uploads/{pattern}")
        
        # Check annotation directory
        if pattern.endswith('.json'):
            annotation_file = os.path.join(ANNOTATION_DIR, pattern)
            if os.path.exists(annotation_file):
                os.remove(annotation_file)
                files_removed.append(f"annotations/{pattern}")
    
    return {
        "message": f"Cleanup completed for file_id: {file_id}",
        "files_removed": files_removed
    }

# For Railway deployment
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
