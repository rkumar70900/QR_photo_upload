# QR Photo Upload System

A modern web application for event photo sharing with QR code generation and 3D printing capabilities. Perfect for weddings, parties, and events where guests can easily upload photos and videos.

## Features

- **Guest Photo Upload**: Simple interface for guests to upload photos and videos with their names
- **Gallery View**: Browse and view photos organized by guest folders
- **QR Code Generation**: Automatically generates QR codes linking to the upload interface
- **3D Printable QR Codes**: Export QR codes as STL files for 3D printing
- **Chunked Upload**: Handles large files up to 1GB with resumable uploads
- **Responsive Design**: Works seamlessly on desktop and mobile devices
- **File Downloads**: Download individual photos or entire guest folders as ZIP files

## Tech Stack

- **Backend**: FastAPI (Python)
- **Frontend**: HTML5, CSS3, JavaScript (Vanilla)
- **Template Engine**: Jinja2
- **File Processing**: Pillow, trimesh, numpy
- **QR Generation**: qrcode library
- **Containerization**: Docker

## Quick Start

### Prerequisites

- Python 3.8+
- Docker (optional, for containerized deployment)

### Local Development

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd QR_photo_upload
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

5. **Access the application**
   Open your browser and navigate to `http://localhost:8000`

### Docker Deployment

1. **Build the Docker image**
   ```bash
   docker build -t qr-photo-upload .
   ```

2. **Run the container**
   ```bash
   docker run -p 8000:8000 -v $(pwd)/uploads:/app/uploads qr-photo-upload
   ```

## Project Structure

```
QR_photo_upload/
├── main.py              # FastAPI application and API endpoints
├── QR_code.py           # QR code generation and STL export
├── requirements.txt     # Python dependencies
├── Dockerfile          # Docker configuration
├── templates/
│   └── upload.html     # Main web interface
├── static/
│   ├── styles.css      # Additional styles
│   ├── js/            # JavaScript files
│   └── images/        # Static images
├── uploads/            # User uploaded files (auto-created)
├── photos/            # Photo storage
├── temp_uploads/      # Temporary upload storage
└── README.md          # This file
```

## API Endpoints

### Upload Endpoints

- `POST /upload` - Upload multiple files with guest name
- `POST /api/upload/start` - Initialize chunked upload session
- `POST /api/upload/chunk/{upload_id}` - Upload file chunk
- `POST /api/upload/complete/{upload_id}` - Complete chunked upload

### Gallery Endpoints

- `GET /api/gallery/folders` - List all guest folders
- `GET /api/gallery/photos/{folder}` - List photos in a specific folder

### Download Endpoints

- `GET /download/image/{folder}/{filename}` - Download single image
- `GET /download/folder/{folder}` - Download entire folder as ZIP

### Static Files

- `GET /uploads/{folder}/{filename}` - Serve uploaded files
- `GET /static/*` - Serve static assets

## Supported File Types

### Images
- JPEG (.jpg, .jpeg)
- PNG (.png)
- GIF (.gif)
- WebP (.webp)
- HEIF/HEIC (.heif, .heic)

### Videos
- MP4 (.mp4)
- WebM (.webm)
- MOV (.mov)
- AVI (.avi)

## Configuration

### Environment Variables

The application uses the following default configurations (can be modified in `main.py`):

```python
UPLOAD_DIR = "uploads"                    # Upload directory
MAX_FILE_SIZE = 1024 * 1024 * 1024       # 1GB max file size
CHUNK_SIZE = 5 * 1024 * 1024             # 5MB chunk size
```

### File Limits

- Maximum file size: 1GB per file
- Maximum files per upload: 40 files
- Supported formats: Images and videos (see above)

## QR Code Generation

### Generate QR Code Image

```python
from QR_code import generate_qr_image

# Generate QR code for a URL
qr_image = generate_qr_image("http://your-event-url.com", "event_qr.png")
```

### Generate 3D Printable QR Code

```python
from QR_code import main

# Run the interactive QR code generator
# This will prompt for a URL and generate both PNG and STL files
python QR_code.py
```

The STL file can be 3D printed to create physical QR codes for events.

## Usage

### For Guests

1. **Upload Photos**
   - Enter your name in the "Your Name" field
   - Select photos or videos from your device
   - Click "Upload" to upload files
   - Wait for the upload confirmation

2. **View Gallery**
   - Click "View Gallery" to see all uploaded photos
   - Browse photos by guest folders
   - Click on photos to preview
   - Download individual photos or entire folders

### For Event Organizers

1. **Generate QR Codes**
   - Run `python QR_code.py` to generate QR codes for your event URL
   - Print the QR codes and display them at your venue
   - Guests can scan the codes to quickly access the upload page

2. **Manage Photos**
   - Access the gallery to view all uploaded content
   - Download photos for sharing or printing
   - Organize content by guest names

## Development

### Adding New Features

The application is structured for easy extension:

- **API endpoints**: Add new routes in `main.py`
- **Frontend**: Modify `templates/upload.html` for UI changes
- **QR functionality**: Extend `QR_code.py` for new QR features
- **Styling**: Update `static/styles.css` for visual changes

### Testing

Run the application locally and test:

1. File upload functionality
2. Gallery browsing
3. Download features
4. QR code generation
5. Mobile responsiveness

## Deployment

### Production Considerations

1. **Database**: Replace in-memory session storage with a database
2. **File Storage**: Use cloud storage for uploaded files
3. **Authentication**: Add user authentication for admin features
4. **SSL/TLS**: Configure HTTPS for production
5. **Rate Limiting**: Implement upload rate limiting
6. **Backup**: Set up regular backups of uploaded content

### Environment Setup

For production deployment:

1. Set up reverse proxy (nginx)
2. Configure SSL certificates
3. Set up process manager (systemd/supervisor)
4. Configure monitoring and logging
5. Set up automated backups

## Troubleshooting

### Common Issues

1. **Upload Fails**
   - Check file size limits (max 1GB)
   - Verify file format is supported
   - Ensure upload directory has write permissions

2. **QR Code Not Working**
   - Verify the URL is accessible
   - Check QR code image quality
   - Test with different QR code readers

3. **Gallery Not Loading**
   - Check if uploads directory exists
   - Verify file permissions
   - Check browser console for errors

### Logs

Check the application logs for detailed error information:

```bash
# When running with uvicorn
uvicorn main:app --log-level debug
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
- Create an issue in the repository
- Check the troubleshooting section above
- Review the application logs for error details

---

**Perfect for weddings, birthdays, corporate events, and any occasion where you want to collect and share memories from your guests!**
