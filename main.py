from fastapi import FastAPI, File, UploadFile, Request, Form, HTTPException, Query, status
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import shutil
import io
import zipfile
import uuid
from typing import List, Dict, Optional
import re
from pathlib import Path
import json

UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
MAX_FILE_SIZE = 1024 * 1024 * 1024  # 1GB in bytes
CHUNK_SIZE = 5 * 1024 * 1024  # 5MB chunks
ALLOWED_EXTENSIONS = {
    'image': ['jpg', 'jpeg', 'png', 'gif', 'webp', 'heif', 'heic'],
    'video': ['mp4', 'webm', 'mov', 'avi']
}

# Store upload sessions in memory (in production, use a database)
upload_sessions: Dict[str, Dict] = {}

def sanitize_filename(name: str) -> str:
    """Sanitize the guest name to create a safe directory name"""
    name = re.sub(r'[^\w\s-]', '', name).strip()
    return re.sub(r'[\s-]+', '_', name)

def get_file_extension(filename: str) -> str:
    """Get the file extension in lowercase"""
    return Path(filename).suffix[1:].lower()

def is_allowed_file(filename: str) -> bool:
    """Check if the file has an allowed extension"""
    if not filename:
        return False
    ext = get_file_extension(filename)
    # Normalize HEIC/HEIF extensions
    if ext in ['heic', 'heif']:
        return True
    return any(ext in extensions for extensions in ALLOWED_EXTENSIONS.values())

# Add MIME type for HEIF/HEIC files
import mimetypes
mimetypes.add_type('image/heif', '.heif')
mimetypes.add_type('image/heif', '.heic')

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
            file_path = os.path.join(folder_path, filename)
            file_lower = filename.lower()
            
            # Check if file has a supported extension (case-insensitive)
            is_supported = any(file_lower.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.heif', '.heic'])
            
            if is_supported and os.path.isfile(file_path) and os.access(file_path, os.R_OK):
                # Use the original filename in the URL to preserve case
                photos.append({
                    "name": filename,
                    "url": f"/uploads/{folder}/{filename}",
                    "type": "image"
                })
        
        return {
            "photos": sorted(photos, key=lambda x: x["name"])
        }
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error listing photos in folder {folder}:\n{error_details}")
        raise HTTPException(status_code=500, detail=f"Error listing photos: {str(e)}")

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

@app.post("/api/upload/start")
async def start_upload(
    filename: str = Form(...),
    total_chunks: int = Form(...),
    guest: str = Form(...)
):
    try:
        if not is_allowed_file(filename):
            raise HTTPException(status_code=400, detail="File type not allowed")

        upload_id = str(uuid.uuid4())
        guest_dir = sanitize_filename(guest)
        
        if not guest_dir:
            raise HTTPException(status_code=400, detail="Invalid guest name")

        upload_dir = os.path.join(UPLOAD_DIR, guest_dir)
        os.makedirs(upload_dir, exist_ok=True)

        upload_sessions[upload_id] = {
            "filename": filename,
            "total_chunks": total_chunks,
            "received_chunks": set(),
            "guest_dir": guest_dir,
            "upload_dir": upload_dir,
            "file_path": os.path.join(upload_dir, filename)
        }

        return {"upload_id": upload_id, "chunk_size": CHUNK_SIZE}

    except Exception as e:
        print(f"Error starting upload: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload/chunk/{upload_id}")
async def upload_chunk(
    upload_id: str,
    chunk_index: int = Form(...),
    total_chunks: int = Form(...),
    file: UploadFile = File(...)
):
    try:
        if upload_id not in upload_sessions:
            raise HTTPException(status_code=404, detail="Upload session not found")

        session = upload_sessions[upload_id]
        session["received_chunks"].add(chunk_index)
        
        # Create a temporary directory for chunks if it doesn't exist
        chunk_dir = os.path.join(session["upload_dir"], f"{upload_id}_chunks")
        os.makedirs(chunk_dir, exist_ok=True)
        
        # Save the chunk
        chunk_path = os.path.join(chunk_dir, str(chunk_index))
        with open(chunk_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Check if all chunks are uploaded
        if len(session["received_chunks"]) == total_chunks:
            # Combine chunks
            with open(session["file_path"], "wb") as outfile:
                for i in range(total_chunks):
                    chunk_path = os.path.join(chunk_dir, str(i))
                    with open(chunk_path, "rb") as infile:
                        shutil.copyfileobj(infile, outfile)
            
            # Clean up chunks
            shutil.rmtree(chunk_dir, ignore_errors=True)
            
            # Remove session
            upload_sessions.pop(upload_id, None)
            
            return {"status": "complete", "message": "File uploaded successfully"}
        
        return {"status": "chunk_uploaded", "received": len(session["received_chunks"])}

    except Exception as e:
        print(f"Error uploading chunk: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload/complete/{upload_id}")
async def complete_upload(upload_id: str):
    try:
        if upload_id not in upload_sessions:
            raise HTTPException(status_code=404, detail="Upload session not found")
        
        session = upload_sessions[upload_id]
        
        # Verify all chunks were received
        if len(session["received_chunks"]) != session["total_chunks"]:
            raise HTTPException(status_code=400, detail="Not all chunks were received")
        
        # The actual file should already be combined in the chunk upload handler
        if not os.path.exists(session["file_path"]):
            raise HTTPException(status_code=500, detail="Failed to combine file chunks")
        
        # Clean up
        upload_sessions.pop(upload_id, None)
        
        return {"status": "success", "message": "File upload completed successfully"}
    
    except Exception as e:
        print(f"Error completing upload: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload")
async def upload_files(
    request: Request,
    guest: str = Form(...),
    files: List[UploadFile] = File(...)
):
    try:
        guest_dir = sanitize_filename(guest)
        if not guest_dir:
            raise HTTPException(status_code=400, detail="Invalid guest name")

        upload_dir = os.path.join(UPLOAD_DIR, guest_dir)
        os.makedirs(upload_dir, exist_ok=True)

        saved_files = []
        for file in files:
            if not is_allowed_file(file.filename):
                continue
                
            # Check file size
            file_size = 0
            for chunk in file.file:
                file_size += len(chunk)
            file.file.seek(0)  # Reset file pointer
                
            if file_size > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=400,
                    detail=f"File too large: {file.filename} (max {MAX_FILE_SIZE/1024/1024/1024}GB)"
                )
            
            # Create a safe filename
            filename = os.path.basename(file.filename)
            # Ensure filename is safe
            filename = "".join(c for c in filename if c.isalnum() or c in '._- ').strip()
            file_path = os.path.join(upload_dir, filename)
            
            # Save the file
            try:
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
                print(f"Successfully saved {filename} to {guest_dir}")
            except Exception as e:
                print(f"Error saving file {filename}: {str(e)}")
                raise
            
            saved_files.append(filename)

        return JSONResponse(
            status_code=200,
            content={
                "message": f"Successfully uploaded {len(saved_files)} files to {guest}'s folder",
                "folder": guest_dir
            }
        )
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error in upload_files: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error uploading files: {str(e)}"
        )

@app.get("/download/image/{folder}/{filename}")
async def download_single_image(folder: str, filename: str):
    file_path = os.path.join(UPLOAD_DIR, folder, filename)
    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=file_path, filename=filename, media_type='application/octet-stream')

@app.get("/download/folder/{folder}")
async def download_folder_as_zip(folder: str):
    folder_path = os.path.join(UPLOAD_DIR, folder)
    if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
        raise HTTPException(status_code=404, detail="Folder not found")

    # Create a bytes buffer for the zip file
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for root, _, files in os.walk(folder_path):
            for file in files:
                if file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.heif')):
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, folder_path)
                    zip_file.write(file_path, arcname)

    zip_buffer.seek(0)
    zip_filename = f"{folder}.zip"

    return StreamingResponse(zip_buffer, media_type="application/x-zip-compressed", 
                           headers={"Content-Disposition": f"attachment; filename={zip_filename}"})

# Create uploads directory if it doesn't exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
# Mount the uploads directory to serve files
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")