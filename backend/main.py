from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
import uvicorn
import os
import shutil
import uuid
import pydicom
from PIL import Image
import numpy as np

app = FastAPI()

# Allow CORS for local frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "temp_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.get("/")
def root():
    return {"message": "Dobbe AI Dental DICOM Analyzer Backend"}

@app.post("/upload")
async def upload_dicom(file: UploadFile = File(...)):
    # Save uploaded file
    file_id = str(uuid.uuid4())
    dicom_path = os.path.join(UPLOAD_DIR, f"{file_id}.dcm")
    with open(dicom_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    # Convert DICOM to PNG
    ds = pydicom.dcmread(dicom_path)
    arr = ds.pixel_array
    arr = ((arr - arr.min()) / (arr.ptp()) * 255.0).astype(np.uint8)
    img = Image.fromarray(arr)
    png_path = os.path.join(UPLOAD_DIR, f"{file_id}.png")
    img.save(png_path)
    return {"image_id": file_id, "image_url": f"/image/{file_id}"}

@app.get("/image/{image_id}")
def get_image(image_id: str):
    png_path = os.path.join(UPLOAD_DIR, f"{image_id}.png")
    if not os.path.exists(png_path):
        return JSONResponse(status_code=404, content={"error": "Image not found"})
    return FileResponse(png_path, media_type="image/png")

@app.post("/predict")
async def predict(image_id: str):
    # Placeholder: Call Roboflow API here
    # Return dummy bounding boxes for now
    return {
        "boxes": [
            {"x": 50, "y": 60, "width": 100, "height": 80, "label": "cavity", "confidence": 0.92}
        ]
    }

@app.post("/report")
async def report(image_id: str, annotations: dict):
    # Placeholder: Call LLM or return dummy report
    return {
        "report": "Detected a cavity in the upper left molar. Recommend further clinical evaluation."
    }
