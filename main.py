from fastapi import FastAPI, File, UploadFile, Request, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import shutil
import uuid
from typing import List, Dict, Optional
import re
from pathlib import Path
import json

UPLOAD_DIR = "/app/uploads"
MAX_FILE_SIZE = 1024 * 1024 * 1024  # 1GB in bytes
ALLOWED_EXTENSIONS = {
    'image': ['jpg', 'jpeg', 'png', 'gif', 'webp'],
    'video': ['mp4', 'webm', 'mov', 'avi']
}
CHUNK_SIZE = 5 * 1024 * 1024  # 5MB chunks
UPLOAD_TEMP_DIR = os.path.join(os.path.dirname(__file__), "temp_uploads")
os.makedirs(UPLOAD_TEMP_DIR, exist_ok=True)

def sanitize_filename(name: str) -> str:
    """Sanitize the guest name to create a safe directory name"""
    name = re.sub(r'[^\w\s-]', '', name).strip()
    return re.sub(r'[\s-]+', '_', name)

def get_file_extension(filename: str) -> str:
    """Get the file extension in lowercase"""
    return Path(filename).suffix[1:].lower()

def is_allowed_file(filename: str) -> bool:
    """Check if the file has an allowed extension"""
    ext = get_file_extension(filename)
    return any(ext in extensions for extensions in ALLOWED_EXTENSIONS.values())

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Ensure upload directory exists
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/api/upload/start")
async def start_upload(guest: str = Form(...), filename: str = Form(...), file_size: int = Form(...)):
    """Initialize a new chunked upload"""
    upload_id = str(uuid.uuid4())
    upload_dir = os.path.join(UPLOAD_TEMP_DIR, upload_id)
    os.makedirs(upload_dir, exist_ok=True)
    
    # Save upload metadata
    metadata = {
        "guest": guest,
        "filename": filename,
        "file_size": file_size,
        "chunks_uploaded": [],
        "total_chunks": (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE
    }
    
    with open(os.path.join(upload_dir, "metadata.json"), 'w') as f:
        json.dump(metadata, f)
    
    return {"upload_id": upload_id, "chunk_size": CHUNK_SIZE}

@app.post("/api/upload/chunk")
async def upload_chunk(
    upload_id: str = Form(...),
    chunk_number: int = Form(...),
    chunk: UploadFile = File(...)
):
    """Upload a single chunk"""
    chunk_path = os.path.join(UPLOAD_TEMP_DIR, upload_id, f"chunk_{chunk_number}")
    
    # Save the chunk
    with open(chunk_path, 'wb') as f:
        shutil.copyfileobj(chunk.file, f)
    
    # Update metadata
    metadata_path = os.path.join(UPLOAD_TEMP_DIR, upload_id, "metadata.json")
    with open(metadata_path, 'r+') as f:
        metadata = json.load(f)
        if chunk_number not in metadata["chunks_uploaded"]:
            metadata["chunks_uploaded"].append(chunk_number)
            f.seek(0)
            json.dump(metadata, f)
            f.truncate()
    
    return {"status": "success", "chunk_number": chunk_number}

@app.post("/api/upload/complete")
async def complete_upload(upload_id: str = Form(...)):
    """Combine all chunks into the final file"""
    upload_dir = os.path.join(UPLOAD_TEMP_DIR, upload_id)
    metadata_path = os.path.join(upload_dir, "metadata.json")
    
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)
    
    # Check if all chunks are uploaded
    expected_chunks = set(range(1, metadata["total_chunks"] + 1))
    uploaded_chunks = set(metadata["chunks_uploaded"])
    
    if expected_chunks != uploaded_chunks:
        missing = expected_chunks - uploaded_chunks
        raise HTTPException(status_code=400, detail=f"Missing chunks: {missing}")
    
    # Create guest directory
    guest_dir = os.path.join(UPLOAD_DIR, sanitize_filename(metadata["guest"]))
    os.makedirs(guest_dir, exist_ok=True)
    
    # Combine chunks
    final_path = os.path.join(guest_dir, metadata["filename"])
    with open(final_path, 'wb') as outfile:
        for chunk_num in range(1, metadata["total_chunks"] + 1):
            chunk_path = os.path.join(upload_dir, f"chunk_{chunk_num}")
            with open(chunk_path, 'rb') as chunk_file:
                shutil.copyfileobj(chunk_file, outfile)
    
    # Cleanup
    shutil.rmtree(upload_dir)
    
    return {"status": "success", "path": final_path}

@app.get("/api/gallery/folders")
async def list_gallery_folders():
    """List all guest folders in the upload directory"""
    try:
        if not os.path.exists(UPLOAD_DIR):
            os.makedirs(UPLOAD_DIR, exist_ok=True)
            return []
            
        folders = [f for f in os.listdir(UPLOAD_DIR) 
                  if os.path.isdir(os.path.join(UPLOAD_DIR, f)) and not f.startswith('.')]
        return {"folders": sorted(folders)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/gallery/photos/{folder}")
async def list_photos_in_folder(folder: str):
    """List all photos in a specific guest folder"""
    try:
        folder_path = os.path.join(UPLOAD_DIR, folder)
        if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
            raise HTTPException(status_code=404, detail="Folder not found")
            
        photos = []
        for filename in os.listdir(folder_path):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.heif')):
                photos.append({
                    "name": filename,
                    "url": f"/uploads/{folder}/{filename}"
                })
        return {"photos": sorted(photos, key=lambda x: x["name"])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/", response_class=HTMLResponse)
async def upload_form(request: Request):
    # Get list of folders for the gallery
    folders = []
    if os.path.exists(UPLOAD_DIR):
        folders = [f for f in os.listdir(UPLOAD_DIR) 
                 if os.path.isdir(os.path.join(UPLOAD_DIR, f)) and not f.startswith('.')]
    
    return templates.TemplateResponse("upload.html", {
        "request": request,
        "initial_folders": folders
    })

@app.post("/upload")
async def upload_files(
    request: Request,
    guest: str = Form(...),
    files: List[UploadFile] = File(...)
):
    # This endpoint is kept for backward compatibility
    # It will now use chunked upload internally
    responses = []
    
    for file in files:
        # Start upload
        start_resp = await start_upload(guest, file.filename, file.size)
        upload_id = start_resp["upload_id"]
        
        # Upload chunks
        chunk_number = 0
        while True:
            chunk = await file.read(CHUNK_SIZE)
            if not chunk:
                break
            chunk_number += 1
            # In a real implementation, you'd upload each chunk to the server
            # For simplicity, we're just writing them directly here
            chunk_path = os.path.join(UPLOAD_TEMP_DIR, upload_id, f"chunk_{chunk_number}")
            with open(chunk_path, 'wb') as f:
                f.write(chunk)
        
        # Complete upload
        response = await complete_upload(upload_id)
        responses.append({"filename": file.filename, "status": "success"})
    
    return JSONResponse(content={"message": f"Uploaded {len(responses)} files", "details": responses})

# Serve uploaded files
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
