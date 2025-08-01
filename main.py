from fastapi import FastAPI, File, UploadFile, Request, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import shutil
import asyncio
import uuid
from typing import List, Dict, Optional, Tuple
import re
from pathlib import Path
import time
import gzip
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor

# Configuration
UPLOAD_DIR = "/Users/raj/Documents/GitHub/QR_photo_upload/uploads"
CHUNK_DIR = os.path.join(UPLOAD_DIR, "_chunks")  # Temporary chunk storage
MAX_FILE_SIZE = 1024 * 1024 * 1024  # 1GB in bytes
CHUNK_SIZE = 5 * 1024 * 1024  # 5MB chunks
MAX_PARALLEL_UPLOADS = 4  # Maximum parallel chunk uploads
ALLOWED_EXTENSIONS = {
    'image': ['jpg', 'jpeg', 'png', 'gif', 'webp'],
    'video': ['mp4', 'webm', 'mov', 'avi']
}

# Thread pool for parallel operations
executor = ThreadPoolExecutor(max_workers=MAX_PARALLEL_UPLOADS)

# Track upload sessions
upload_sessions: Dict[str, Dict] = {}

def get_chunk_path(upload_id: str, chunk_index: int) -> str:
    """Get the path for a chunk file"""
    return os.path.join(CHUNK_DIR, upload_id, f"chunk_{chunk_index:05d}.gz")

async def save_chunk(upload_id: str, chunk_index: int, chunk_data: bytes, total_chunks: int) -> Dict[str, any]:
    """Save an uploaded chunk"""
    chunk_dir = os.path.join(CHUNK_DIR, upload_id)
    os.makedirs(chunk_dir, exist_ok=True)
    
    chunk_path = get_chunk_path(upload_id, chunk_index)
    
    # Save the compressed chunk
    with open(chunk_path, 'wb') as f:
        f.write(chunk_data)
    
    # Update session
    if upload_id not in upload_sessions:
        upload_sessions[upload_id] = {
            'total_chunks': total_chunks,
            'received_chunks': set(),
            'created_at': time.time()
        }
    
    upload_sessions[upload_id]['received_chunks'].add(chunk_index)
    received = len(upload_sessions[upload_id]['received_chunks'])
    total = upload_sessions[upload_id]['total_chunks']
    
    return {
        'status': 'chunk_uploaded',
        'upload_id': upload_id,
        'chunk': chunk_index,
        'received': received,
        'total': total
    }

async def assemble_file(upload_id: str, original_filename: str, guest: str) -> Dict[str, any]:
    """Assemble chunks into final file and clean up"""
    if upload_id not in upload_sessions:
        raise HTTPException(status_code=404, detail="Upload session not found")
    
    session = upload_sessions[upload_id]
    total_chunks = session['total_chunks']
    chunk_dir = os.path.join(CHUNK_DIR, upload_id)
    
    # Verify all chunks are present
    missing_chunks = [i for i in range(total_chunks) 
                     if not os.path.exists(get_chunk_path(upload_id, i))]
    
    if missing_chunks:
        raise HTTPException(
            status_code=400, 
            detail=f"Missing chunks: {missing_chunks}"
        )
    
    # Create guest directory
    guest_dir = os.path.join(UPLOAD_DIR, sanitize_filename(guest))
    os.makedirs(guest_dir, exist_ok=True)
    
    # Final file path
    final_path = os.path.join(guest_dir, os.path.basename(original_filename))
    
    # Assemble file
    try:
        with open(final_path, 'wb') as outfile:
            for i in range(total_chunks):
                chunk_path = get_chunk_path(upload_id, i)
                with gzip.open(chunk_path, 'rb') as infile:
                    shutil.copyfileobj(infile, outfile)
    except Exception as e:
        if os.path.exists(final_path):
            os.remove(final_path)
        raise HTTPException(status_code=500, detail=f"Error assembling file: {str(e)}")
    finally:
        # Clean up chunks
        shutil.rmtree(chunk_dir, ignore_errors=True)
        upload_sessions.pop(upload_id, None)
    
    return {
        'status': 'complete',
        'path': final_path,
        'size': os.path.getsize(final_path)
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

# Ensure upload and chunk directories exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(CHUNK_DIR, exist_ok=True)

@app.post("/api/upload/start")
async def start_upload(
    filename: str = Form(...),
    total_chunks: int = Form(...),
    guest: str = Form(...)
):
    """Initialize a new chunked upload session"""
    upload_id = str(uuid.uuid4())
    upload_sessions[upload_id] = {
        'filename': filename,
        'total_chunks': total_chunks,
        'received_chunks': set(),
        'guest': guest,
        'created_at': time.time()
    }
    return {"upload_id": upload_id, "chunk_size": CHUNK_SIZE}

@app.post("/api/upload/chunk/{upload_id}")
async def upload_chunk(
    upload_id: str,
    chunk_index: int = Form(...),
    total_chunks: int = Form(...),
    file: UploadFile = File(...)
):
    """Upload a single chunk"""
    try:
        chunk_data = await file.read()
        return await save_chunk(upload_id, chunk_index, chunk_data, total_chunks)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload/complete/{upload_id}")
async def complete_upload(upload_id: str):
    """Complete the upload and assemble the file"""
    if upload_id not in upload_sessions:
        raise HTTPException(status_code=404, detail="Upload session not found")
    
    session = upload_sessions[upload_id]
    try:
        result = await assemble_file(
            upload_id=upload_id,
            original_filename=session['filename'],
            guest=session['guest']
        )
        return result
    except Exception as e:
        # Clean up on error
        chunk_dir = os.path.join(CHUNK_DIR, upload_id)
        shutil.rmtree(chunk_dir, ignore_errors=True)
        upload_sessions.pop(upload_id, None)
        raise HTTPException(status_code=500, detail=str(e))

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
    file: UploadFile = File(...),
    guest: str = Form(None)  # Make guest optional for better error handling
):
    try:
        print(f"\n=== New Upload Request ===")
        print(f"Headers: {dict(request.headers)}")
        print(f"Form data: guest={guest}, filename={file.filename if file else 'None'}")
        
        # Validate input
        if not file or not file.filename:
            raise HTTPException(status_code=400, detail="No file selected")
            
        if not guest or not guest.strip():
            raise HTTPException(status_code=400, detail="Guest name is required")
            
        # Sanitize guest name for directory
        safe_guest = sanitize_filename(guest.strip())
        if not safe_guest:
            raise HTTPException(status_code=400, detail="Invalid guest name")
            
        guest_dir = os.path.join(UPLOAD_DIR, safe_guest)
        os.makedirs(guest_dir, exist_ok=True)
        
        # Process filename
        original_filename = file.filename
        is_compressed = original_filename.endswith('.gz')
        
        # Get the original filename without .gz if it was added by compression
        display_filename = original_filename[:-3] if is_compressed else original_filename
        
        # Validate file extension
        if '.' not in display_filename:
            raise HTTPException(status_code=400, detail="File has no extension")
            
        file_ext = display_filename.split('.')[-1].lower()
        if not any(file_ext in exts for exts in ALLOWED_EXTENSIONS.values()):
            allowed = ', '.join(sorted({ext for exts in ALLOWED_EXTENSIONS.values() for ext in exts}))
            raise HTTPException(
                status_code=400,
                detail=f"File type '.{file_ext}' not allowed. Allowed types: {allowed}"
            )
        
        # Create a safe filename
        from urllib.parse import unquote
        
        # Decode URL-encoded filenames and clean up
        clean_filename = unquote(display_filename)
        safe_basename = os.path.basename(clean_filename)
        
        # Use the original filename as-is (already sanitized)
        safe_filename = safe_basename
        file_path = os.path.join(guest_dir, safe_filename)
        
        print(f"Saving file to: {file_path}")
        
        # Save the file with appropriate handling
        try:
            # Read the file content
            file_content = await file.read()
            
            if is_compressed:
                try:
                    # Try to decompress
                    import gzip
                    from io import BytesIO
                    
                    print(f"Attempting to decompress {len(file_content)} bytes...")
                    
                    # First try to detect if it's actually gzipped
                    if len(file_content) >= 2 and (file_content[0] == 0x1f and file_content[1] == 0x8b):
                        with gzip.GzipFile(fileobj=BytesIO(file_content)) as gz_file:
                            decompressed = gz_file.read()
                            with open(file_path, 'wb') as f:
                                f.write(decompressed)
                        print(f"Successfully decompressed {len(file_content)} bytes to {len(decompressed)} bytes")
                    else:
                        print("File has .gz extension but is not a valid gzip file, saving as is")
                        with open(file_path, 'wb') as f:
                            f.write(file_content)
                except Exception as e:
                    print(f"Decompression failed: {str(e)}, saving as is")
                    with open(file_path, 'wb') as f:
                        f.write(file_content)
            else:
                # Save uncompressed file
                with open(file_path, 'wb') as f:
                    f.write(file_content)
                    
            # Verify the file was saved and is not empty
            if not os.path.exists(file_path):
                raise Exception("Failed to save file")
                
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                os.remove(file_path)
                raise Exception("File saved with 0 bytes, likely an error occurred during save")
            
            # Verify file was saved
            if not os.path.exists(file_path):
                raise Exception("Failed to save file")
                
            file_size = os.path.getsize(file_path)
            print(f"Successfully saved {file.filename} ({file_size} bytes)")

            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": f"Successfully uploaded {os.path.basename(original_filename)}",
                    "folder": safe_guest,
                    "filename": safe_filename,
                    "size": file_size
                }
            )
            
        except Exception as e:
            print(f"Error saving file: {str(e)}")
            import traceback
            traceback.print_exc()
            if os.path.exists(file_path):
                os.remove(file_path)
            raise HTTPException(
                status_code=500,
                detail=f"Error saving file: {str(e)}"
            )
        
    except HTTPException as he:
        print(f"HTTP Error {he.status_code}: {he.detail}")
        raise
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Unexpected error: {error_trace}")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )

# Serve uploaded files
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
