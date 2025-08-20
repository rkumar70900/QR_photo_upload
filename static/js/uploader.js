class ChunkedUploader {
    constructor(options = {}) {
        this.chunkSize = options.chunkSize || 5 * 1024 * 1024; // 5MB
        this.maxParallelUploads = options.maxParallelUploads || 4;
        this.retryAttempts = options.retryAttempts || 3;
        this.retryDelay = options.retryDelay || 1000; // 1 second
        this.onProgress = options.onProgress || (() => {});
        this.onComplete = options.onComplete || (() => {});
        this.onError = options.onError || (() => {});
        this.activeUploads = 0;
        this.uploadQueue = [];
        this.uploadId = null;
        this.totalChunks = 0;
        this.completedChunks = 0;
        this.uploadedBytes = 0;
        this.totalBytes = 0;
    }

    async compressChunk(chunk) {
        if (!window.CompressionStream) {
            return chunk;
        }

        try {
            const stream = new Response(chunk).body
                .pipeThrough(new CompressionStream('gzip'));
            return await new Response(stream).arrayBuffer();
        } catch (e) {
            console.warn('Compression failed, using uncompressed chunk', e);
            return chunk;
        }
    }

    async processQueue() {
        while (this.uploadQueue.length > 0 && this.activeUploads < this.maxParallelUploads) {
            const { chunkIndex, chunk, retryCount = 0 } = this.uploadQueue.shift();
            this.activeUploads++;
            
            try {
                await this.uploadChunk(chunkIndex, chunk);
                this.completedChunks++;
                this.uploadedBytes += chunk.byteLength;
                this.updateProgress();
            } catch (error) {
                if (retryCount < this.retryAttempts) {
                    console.log(`Retrying chunk ${chunkIndex} (${retryCount + 1}/${this.retryAttempts})`);
                    this.uploadQueue.unshift({
                        chunkIndex,
                        chunk,
                        retryCount: retryCount + 1
                    });
                    // Add delay before retry
                    await new Promise(resolve => setTimeout(resolve, this.retryDelay * (retryCount + 1)));
                } else {
                    console.error(`Failed to upload chunk ${chunkIndex} after ${this.retryAttempts} attempts`, error);
                    this.onError({
                        chunkIndex,
                        error,
                        message: `Failed to upload chunk ${chunkIndex}`
                    });
                }
            } finally {
                this.activeUploads--;
                this.processQueue();
            }
        }
    }

    async uploadChunk(chunkIndex, chunk) {
        const formData = new FormData();
        const blob = new Blob([chunk]);
        formData.append('file', blob, `chunk_${chunkIndex}`);
        formData.append('chunk_index', chunkIndex);
        formData.append('total_chunks', this.totalChunks);

        const response = await fetch(`/api/upload/chunk/${this.uploadId}`, {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.detail || 'Upload failed');
        }

        return response.json();
    }

    updateProgress() {
        const progress = {
            loaded: this.uploadedBytes,
            total: this.totalBytes,
            percent: Math.round((this.completedChunks / this.totalChunks) * 100)
        };
        this.onProgress(progress);
    }

    async uploadFile(file, guest) {
        try {
            // Start upload session
            const startResponse = await fetch('/api/upload/start', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: new URLSearchParams({
                    filename: file.name,
                    total_chunks: Math.ceil(file.size / this.chunkSize),
                    guest: guest
                })
            });

            if (!startResponse.ok) {
                throw new Error('Failed to start upload session');
            }

            const { upload_id, chunk_size } = await startResponse.json();
            this.uploadId = upload_id;
            this.totalChunks = Math.ceil(file.size / chunk_size);
            this.totalBytes = file.size;
            this.completedChunks = 0;
            this.uploadedBytes = 0;
            this.uploadQueue = [];

            // Start preloading all folders in the background
            preloadAllFolders();

            // Read file in chunks
            const chunkPromises = [];
            for (let i = 0; i < this.totalChunks; i++) {
                const start = i * chunk_size;
                const end = Math.min(start + chunk_size, file.size);
                const chunk = file.slice(start, end);
                this.uploadQueue.push({ chunkIndex: i, chunk });
            }

            // Start processing queue
            await this.processQueue();

            // Complete upload
            const completeResponse = await fetch(`/api/upload/complete/${this.uploadId}`, {
                method: 'POST'
            });

            if (!completeResponse.ok) {
                throw new Error('Failed to complete upload');
            }

            const result = await completeResponse.json();
            this.onComplete(result);
            return result;

        } catch (error) {
            console.error('Upload failed:', error);
            this.onError({
                error,
                message: 'Upload failed',
                uploadId: this.uploadId
            });
            throw error;
        }
    }
}

// Global variables to store all folders and their contents
let allFolders = [];
let folderContentsCache = new Map();

// Function to preload all folders and their contents
async function preloadAllFolders() {
    try {
        console.log('Starting background preload of all folders...');
        const response = await fetch('/api/folders');
        if (!response.ok) throw new Error('Failed to fetch folders');
        
        allFolders = await response.json();
        console.log(`Found ${allFolders.length} folders to preload`);
        
        // Preload contents for each folder
        const preloadPromises = allFolders.map(async (folder) => {
            try {
                const contentsResponse = await fetch(`/api/folders/${encodeURIComponent(folder.name)}`);
                if (contentsResponse.ok) {
                    const contents = await contentsResponse.json();
                    folderContentsCache.set(folder.name, {
                        files: contents,
                        timestamp: Date.now()
                    });
                    console.log(`Preloaded folder: ${folder.name} (${contents.length} files)`);
                }
            } catch (error) {
                console.error(`Error preloading folder ${folder.name}:`, error);
            }
        });
        
        await Promise.all(preloadPromises);
        console.log('Background preloading completed for all folders');
        return true;
    } catch (error) {
        console.error('Error in background preloading:', error);
        return false;
    }
}

// Start preloading all folders when the script loads
preloadAllFolders().then(() => {
    console.log('Background preloading completed');
}).catch(error => {
    console.error('Background preloading failed:', error);
});

document.addEventListener('DOMContentLoaded', function() {
    // Load folders for immediate display
    loadFolders();
});

async function loadFolderContents(folderName) {
    // Show loading state
    const folderView = document.getElementById('folderView');
    if (folderView) {
        folderView.innerHTML = '<div class="spinner"></div>';
    }

    // Check if we have cached the folder contents
    const cachedData = folderContentsCache.get(folderName);
    if (cachedData) {
        console.log(`Loading folder from cache: ${folderName}`);
        displayFolderContents(folderName, cachedData.files);
        
        // Refresh the data in the background if it's older than 5 minutes
        const fiveMinutesAgo = Date.now() - (5 * 60 * 1000);
        if (cachedData.timestamp < fiveMinutesAgo) {
            console.log(`Refreshing cache for folder: ${folderName}`);
            fetch(`/api/folders/${encodeURIComponent(folderName)}`)
                .then(response => response.ok ? response.json() : null)
                .then(files => {
                    if (files) {
                        folderContentsCache.set(folderName, {
                            files,
                            timestamp: Date.now()
                        });
                        console.log(`Refreshed cache for folder: ${folderName}`);
                    }
                })
                .catch(error => console.error(`Error refreshing cache for ${folderName}:`, error));
        }
        return;
    }
    
    // If not in cache or cache is stale, fetch from server
    try {
        console.log(`Fetching folder contents from server: ${folderName}`);
        const response = await fetch(`/api/folders/${encodeURIComponent(folderName)}`);
        if (!response.ok) throw new Error('Failed to load folder contents');
        
        const files = await response.json();
        
        // Cache the result for future use
        folderContentsCache.set(folderName, {
            files,
            timestamp: Date.now()
        });
        
        displayFolderContents(folderName, files);
    } catch (error) {
        console.error('Error loading folder contents:', error);
        const errorMessage = document.createElement('div');
        errorMessage.className = 'error-message';
        errorMessage.textContent = 'Failed to load folder contents. Please try again.';
        if (folderView) {
            folderView.innerHTML = '';
            folderView.appendChild(errorMessage);
        } else {
            alert('Failed to load folder contents. Please try again.');
        }
    }
}
