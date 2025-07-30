from fastapi import FastAPI, File, UploadFile, Form, Request
from typing import List
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import shutil

UPLOAD_DIR = "/app/uploads"  # change this to your NAS mount

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Optional CSS/static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def upload_form(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})

@app.post("/upload", response_class=HTMLResponse)
async def upload_files(
    request: Request,
    guest: str = Form(...),
    photo: UploadFile = File(...)
):
    try:
        # Create directory for the guest if it doesn't exist
        guest_dir = os.path.join(UPLOAD_DIR, guest)
        os.makedirs(guest_dir, exist_ok=True)
        
        # Save the uploaded file
        file_path = os.path.join(guest_dir, photo.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(photo.file, buffer)
            
        return templates.TemplateResponse("upload.html", {
            "request": request,
            "message": f"Thanks {guest}! Your photo has been uploaded successfully."
        })
        
    except Exception as e:
        return templates.TemplateResponse("upload.html", {
            "request": request,
            "error": f"Error uploading file: {str(e)}"
        })
