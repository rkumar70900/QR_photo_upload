from fastapi import FastAPI, File, UploadFile, Request, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import shutil
from typing import List
import re
from pathlib import Path

UPLOAD_DIR = "/app/uploads"
MAX_FILE_SIZE = 1024 * 1024 * 1024  # 1GB in bytes
ALLOWED_EXTENSIONS = {
    'image': ['jpg', 'jpeg', 'png', 'gif', 'webp'],
    'video': ['mp4', 'webm', 'mov', 'avi']
}

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
        raise HTTPException(status_csode=500, detail=str(e))

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
    try:
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")

        # Sanitize guest name for directory
        guest_dir = os.path.join(UPLOAD_DIR, sanitize_filename(guest))
        os.makedirs(guest_dir, exist_ok=True)
        
        saved_files = []
        
        for file in files:
            # Check file extension
            if not is_allowed_file(file.filename):
                raise HTTPException(
                    status_code=400,
                    detail=f"File type not allowed: {file.filename}"
                )
            
            # Check file size
            file.file.seek(0, 2)  # Move to end of file
            file_size = file.file.tell()
            file.file.seek(0)  # Reset file pointer
            
            if file_size > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=400,
                    detail=f"File too large: {file.filename} (max {MAX_FILE_SIZE/1024/1024/1024}GB)"
                )
            
            # Create a safe filename
            filename = file.filename
            file_path = os.path.join(guest_dir, filename)
            
            # Save the file
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            saved_files.append(filename)

        return JSONResponse(
            status_code=200,
            content={
                "message": f"Successfully uploaded {len(saved_files)} files to {guest}'s folder",
                "folder": sanitize_filename(guest)
            }
        )
        
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error uploading files: {str(e)}"
        )

# Serve uploaded files
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")