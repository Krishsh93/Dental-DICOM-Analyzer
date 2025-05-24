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
UPLOAD_DIR = "uploads"
ANNOTATION_DIR = "annotations"
ROBOFLOW_API_URL = "https://detect.roboflow.com/adr/6"
ROBOFLOW_API_KEY = os.environ.get("ROBOFLOW_API_KEY", "demo")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", None)
LLM_API_KEY = os.environ.get("OPENAI_API_KEY", None)  # Optional

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(ANNOTATION_DIR, exist_ok=True)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def dicom_to_png(dicom_path, png_path):
    ds = pydicom.dcmread(dicom_path)
    arr = apply_voi_lut(ds.pixel_array, ds)
    arr = arr.astype(float)
    arr = (np.maximum(arr, 0) / arr.max()) * 255.0
    arr = np.uint8(arr)
    img = Image.fromarray(arr)
    img = img.convert("L")
    img.save(png_path)
    return png_path

@app.post("/upload/")
async def upload_dicom(file: UploadFile = File(...)):
    if not (file.filename.endswith(".dcm") or file.filename.endswith(".rvg")):
        raise HTTPException(status_code=400, detail="File must be .dcm or .rvg")
    file_id = str(uuid.uuid4())
    dicom_path = os.path.join(UPLOAD_DIR, f"{file_id}.dcm")
    png_path = os.path.join(UPLOAD_DIR, f"{file_id}.png")
    with open(dicom_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    try:
        dicom_to_png(dicom_path, png_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DICOM conversion failed: {e}")
    return {"file_id": file_id, "dicom_url": f"/file/{file_id}.dcm", "png_url": f"/file/{file_id}.png"}

@app.get("/file/{filename}")
def get_file(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)

@app.post("/predict/")
def predict(file_id: str):
    png_path = os.path.join(UPLOAD_DIR, f"{file_id}.png")
    if not os.path.exists(png_path):
        raise HTTPException(status_code=404, detail="PNG not found")
    with open(png_path, "rb") as img_file:
        resp = requests.post(
            f"{ROBOFLOW_API_URL}?api_key={ROBOFLOW_API_KEY}&confidence=30&overlap=50",
            files={"file": img_file},
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=500, detail="Roboflow API error")
    result = resp.json()
    # Save annotation
    annotation_path = os.path.join(ANNOTATION_DIR, f"{file_id}.json")
    with open(annotation_path, "w") as f:
        json.dump(result, f)
    return {"annotations": result, "annotation_url": f"/annotation/{file_id}.json"}

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
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            stream=False,
        )
        report = chat_completion.choices[0].message.content.strip()
    elif LLM_API_KEY:
        import openai
        openai.api_key = LLM_API_KEY
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
        )
        report = response.choices[0].message.content.strip()
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
