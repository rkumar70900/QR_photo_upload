from fastapi import FastAPI, File, UploadFile, Request, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import os
import shutil
from typing import List, Dict, Any
import re
from pathlib import Path
import zipfile
import io
from typing import Optional

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
MAX_FILE_SIZE = 1024 * 1024 * 1024  # 1GB in bytes
ALLOWED_EXTENSIONS = {
    'image': ['jpg', 'jpeg', 'png', 'gif', 'webp', 'heif', 'heic'],
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

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your domain
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

# Add trusted hosts middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"],  # In production, replace with your domain
)

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
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def upload_form(request: Request):
    return templates.TemplateResponse("upload.html", {
        "request": request
    })

@app.get("/gallery")
async def gallery_view(request: Request):
    return templates.TemplateResponse("gallery.html", {
        "request": request
    })

@app.get("/api/folders")
async def list_folders():
    """List all folders in the upload directory"""
    try:
        folders = []
        if os.path.exists(UPLOAD_DIR):
            for folder in os.listdir(UPLOAD_DIR):
                folder_path = os.path.join(UPLOAD_DIR, folder)
                if os.path.isdir(folder_path) and not folder.startswith('.'):
                    # Get list of files in the folder
                    files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]
                    # Find first image as thumbnail (including HEIF/HEIC)
                    thumbnail = next((f for f in files if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.heif', '.heic'))), None)
                    folders.append({
                        'name': folder,
                        'count': len(files),
                        'thumbnail': thumbnail
                    })
        return folders
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing folders: {str(e)}")

@app.get("/api/folders/{folder_name}")
async def list_folder_contents(folder_name: str):
    """List all files in a specific folder"""
    try:
        folder_path = os.path.join(UPLOAD_DIR, folder_name)
        if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
            raise HTTPException(status_code=404, detail="Folder not found")
        
        # Get all files in the folder, including HEIF/HEIC
        files = [f for f in os.listdir(folder_path) 
                if os.path.isfile(os.path.join(folder_path, f)) and 
                not f.startswith('.') and
                f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.mp4', '.mov', '.avi', '.heif', '.heic'))]
        
        return files
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing folder contents: {str(e)}")

@app.get("/api/folders/{folder_name}/download")
async def download_folder(folder_name: str):
    """Download all files in a folder as a zip"""
    try:
        folder_path = os.path.join(UPLOAD_DIR, folder_name)
        if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
            raise HTTPException(status_code=404, detail="Folder not found")
        
        # Create a zip file in memory
        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    if not file.startswith('.'):
                        file_path = os.path.join(root, file)
                        # Add file to zip with relative path
                        arcname = os.path.relpath(file_path, os.path.join(folder_path, '..'))
                        zf.write(file_path, arcname)
        
        memory_file.seek(0)
        
        # Return the zip file
        return FileResponse(
            memory_file,
            media_type='application/zip',
            filename=f"{folder_name}.zip"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating zip file: {str(e)}")

@app.get("/uploads/{folder_name}/{file_name}")
async def serve_file(folder_name: str, file_name: str):
    """Serve a file from a folder"""
    file_path = os.path.join(UPLOAD_DIR, folder_name, file_name)
    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)

@app.post("/upload")
async def upload_files(
    request: Request,
    guest: str = Form(None),
    files: List[UploadFile] = File(None)
):
    print(f"Received upload request. Guest: {guest}")
    
    # Check if this is an AJAX request
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    # Get form data
    form_data = await request.form()
    print(f"Form data keys: {form_data.keys()}")
    
    # Handle different file upload formats
    if not files:
        if 'files' in form_data:
            files = [form_data['files']]
        elif 'file' in form_data:
            files = [form_data['file']]
        else:
            # Try to find any file in form data
            files = [v for k, v in form_data.items() if hasattr(v, 'filename')]
            
    # Ensure guest is provided
    if not guest and 'guest' in form_data:
        guest = form_data['guest']
            
    try:
        if not files:
            print("No files in request")
            # Check if files are in the form data but not properly parsed
            if 'files' in form_data or 'file' in form_data:
                print("Files found in form data but not properly parsed")
                files = [v for k, v in form_data.items() if hasattr(v, 'filename')]
                print(f"Extracted files: {files}")
            
            if not files:
                raise HTTPException(status_code=400, detail="No files provided")

        # Sanitize guest name for directory
        guest_dir = os.path.join(UPLOAD_DIR, sanitize_filename(guest))
        os.makedirs(guest_dir, exist_ok=True)
        
        saved_files = []
        
        # If files is a single UploadFile, convert it to a list
        if not isinstance(files, list):
            files = [files]
            
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

        # Prepare response data
        response_data = {
            "message": f"Successfully uploaded {len(saved_files)} files to {guest}'s folder",
            "folder": sanitize_filename(guest),
            "file_count": len(saved_files)
        }
        
        if is_ajax:
            return JSONResponse(
                status_code=200,
                content=response_data
            )
        else:
            # For regular form submission, redirect to success page
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url=f'/?success={len(saved_files)}', status_code=303)
        
    except HTTPException as he:
        if is_ajax:
            raise he
        else:
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url=f'/?error={str(he.detail)}', status_code=303)
            
    except Exception as e:
        error_detail = f"Error uploading files: {str(e)}"
        if is_ajax:
            raise HTTPException(
                status_code=500,
                detail=error_detail
            )
        else:
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url=f'/?error={error_detail}', status_code=303)
        

@app.post("/api/upload/chunk/{upload_id}")
async def upload_chunk(
    upload_id: str,
    file: UploadFile = File(...),
    chunk_index: int = Form(...),
    total_chunks: int = Form(...)
):
    try:
        # In a real implementation, you would save the chunk and track upload progress
        # For now, we'll just return a success response
        return {"status": "success", "chunk_index": chunk_index}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Serve uploaded files
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")