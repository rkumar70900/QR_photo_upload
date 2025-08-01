import config from './config.js';

// Gallery functionality
document.addEventListener('DOMContentLoaded', () => {
    const galleryModal = document.getElementById('galleryModal');
    const galleryFolders = document.getElementById('galleryFolders');
    const galleryPhotos = document.getElementById('galleryPhotos');
    const previewModal = document.getElementById('previewModal');
    const previewImage = document.getElementById('previewImage');
    const viewGalleryBtn = document.getElementById('viewGalleryBtn');
    const closeButtons = document.querySelectorAll('.close-btn');
    
    let initialFolders = [];
    const preloadedImages = new Map();
    let currentFolder = '';

    // Initialize gallery
    async function initGallery() {
        try {
            const response = await fetch(`${config.getApiUrl()}/api/gallery/folders`);
            const data = await response.json();
            if (data.folders && data.folders.length > 0) {
                initialFolders = data.folders;
                preloadAllFolders();
                if (initialFolders[0]) {
                    loadPhotos(initialFolders[0]);
                }
            }
        } catch (error) {
            console.error('Error initializing gallery:', error);
        }
    }

    // Preload all folders' images in the background
    function preloadAllFolders() {
        if (!initialFolders.length) return;
        
        initialFolders.forEach(folder => {
            fetch(`${config.getApiUrl()}/api/gallery/photos/${encodeURIComponent(folder)}`)
                .then(response => response.json())
                .then(data => {
                    if (data.photos && data.photos.length > 0) {
                        preloadedImages.set(folder, data.photos);
                        data.photos.forEach(photo => {
                            const img = new Image();
                            img.src = photo.url;
                        });
                    }
                })
                .catch(console.error);
        });
    }

    // Load photos in a folder
    async function loadPhotos(folder) {
        if (!folder) return;
        
        galleryPhotos.innerHTML = '<div class="loading">Loading photos...</div>';
        currentFolder = folder;
        
        if (preloadedImages.has(folder)) {
            const photos = preloadedImages.get(folder);
            renderPhotos(photos);
            return;
        }
        
        try {
            const response = await fetch(`${config.getApiUrl()}/api/gallery/photos/${encodeURIComponent(folder)}`);
            const data = await response.json();
            
            if (data.photos && data.photos.length > 0) {
                preloadedImages.set(folder, data.photos);
                renderPhotos(data.photos);
            } else {
                galleryPhotos.innerHTML = '<div class="loading">No photos found in this folder</div>';
            }
        } catch (error) {
            console.error('Error loading photos:', error);
            galleryPhotos.innerHTML = '<div class="loading">Error loading photos</div>';
        }
    }
    
    // Render photos in the gallery
    function renderPhotos(photos) {
        galleryPhotos.innerHTML = photos.map(photo => `
            <div class="photo" data-src="${photo.url}">
                <img src="${photo.url}" alt="${photo.name}" loading="lazy">
            </div>
        `).join('');
        
        document.querySelectorAll('.photo').forEach(photo => {
            photo.addEventListener('click', () => {
                previewImage.src = photo.dataset.src;
                previewModal.style.display = 'block';
            });
        });
    }
    
    // Render folders in the gallery
    function renderFolders() {
        if (initialFolders.length > 0) {
            galleryFolders.innerHTML = initialFolders.map(folder => `
                <div class="folder" data-folder="${folder}">
                    <div>📁</div>
                    <div>${folder}</div>
                </div>
            `).join('');
            
            document.querySelectorAll('.folder').forEach(folder => {
                folder.addEventListener('click', () => {
                    currentFolder = folder.dataset.folder;
                    loadPhotos(currentFolder);
                });
            });
        } else {
            galleryFolders.innerHTML = '<div class="loading">No folders found</div>';
        }
    }
    
    // Event Listeners
    viewGalleryBtn?.addEventListener('click', () => {
        galleryModal.style.display = 'block';
        renderFolders();
        if (currentFolder) {
            loadPhotos(currentFolder);
        } else if (initialFolders.length > 0) {
            loadPhotos(initialFolders[0]);
        }
    });
    
    closeButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            galleryModal.style.display = 'none';
            previewModal.style.display = 'none';
        });
    });
    
    window.addEventListener('click', (event) => {
        if (event.target === galleryModal) {
            galleryModal.style.display = 'none';
        }
        if (event.target === previewModal && !event.target.closest('.preview-content')) {
            previewModal.style.display = 'none';
        }
    });
    
    // Initialize the gallery when the page loads
    initGallery();
});
