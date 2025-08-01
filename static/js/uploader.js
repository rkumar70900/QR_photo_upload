import config from './config.js';

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

        const response = await fetch(`${config.getApiUrl()}/api/upload/chunk/${this.uploadId}`, {
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
            const startResponse = await fetch(`${config.getApiUrl()}/api/upload/start`, {
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
            const completeResponse = await fetch(`${config.getApiUrl()}/api/upload/complete/${this.uploadId}`, {
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
