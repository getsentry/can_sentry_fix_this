class InstaFrameApp {
    constructor() {
        this.stream = null;
        this.currentFacingMode = 'environment';
        this.photoData = null;
        this.stats = {
            photosProcessed: 0,
            framesApplied: 0,
            aiAnalyses: 0
        };
        
        // Performance optimization: batch DOM operations
        this.initializeElements();
        this.bindEvents();
        this.loadStats();
        
        // Register service worker for caching
        this.registerServiceWorker();
        
        // Defer camera access to next tick for smoother page load
        requestAnimationFrame(() => {
            this.requestCameraAccess();
        });
    }

    async registerServiceWorker() {
        if ('serviceWorker' in navigator) {
            try {
                const registration = await navigator.serviceWorker.register('/sw.js');
                console.log('Service Worker registered:', registration);
            } catch (error) {
                console.log('Service Worker registration failed:', error);
            }
        }
    }

    initializeElements() {
        this.cameraPreview = document.getElementById('cameraPreview');
        this.cameraControls = document.getElementById('cameraControls');
        this.captureBtn = document.getElementById('captureBtn');
        this.processing = document.getElementById('processing');
        this.resultSection = document.getElementById('resultSection');
        this.resultImage = document.getElementById('resultImage');
        this.downloadBtn = document.getElementById('downloadBtn');
        this.closeResultBtn = document.getElementById('closeResultBtn');
        this.errorMessage = document.getElementById('errorMessage');
        
        // Stats elements
        this.photosProcessedEl = document.getElementById('photosProcessed');
        this.framesAppliedEl = document.getElementById('framesApplied');
        this.aiAnalysesEl = document.getElementById('aiAnalyses');
    }

    bindEvents() {
        this.captureBtn.addEventListener('click', () => this.capturePhoto());
        this.downloadBtn.addEventListener('click', () => this.downloadPhoto());
        this.closeResultBtn.addEventListener('click', () => this.closeResult());
    }

    async requestCameraAccess() {
        try {
            // Show loading state
            this.cameraPreview.innerHTML = `
                <div class="loading">
                    <p>Requesting camera access...</p>
                </div>
            `;
            this.cameraPreview.classList.add('loading');

            const constraints = {
                video: {
                    facingMode: this.currentFacingMode,
                    width: { ideal: 1280 },
                    height: { ideal: 720 }
                }
            };

            const stream = await navigator.mediaDevices.getUserMedia(constraints);
            this.stream = stream;
            this.openCamera();
        } catch (error) {
            console.error('Error requesting camera access:', error);
            this.showError('Failed to access camera. Please check permissions and try again.');
            this.cameraPreview.innerHTML = `
                <div class="camera-error">
                    ⚠️
                    <small>Camera access denied or failed.</small>
                    <small>${this.getErrorMessage(error)}</small>
                    <button onclick="window.instaFrameApp.requestCameraAccess()">Retry</button>
                </div>
            `;
        }
    }

    getErrorMessage(error) {
        if (error.name === 'NotAllowedError') {
            return 'Please allow camera access in your browser settings.';
        } else if (error.name === 'NotFoundError') {
            return 'No camera found on this device.';
        } else if (error.name === 'NotReadableError') {
            return 'Camera is already in use by another application.';
        } else if (error.name === 'OverconstrainedError') {
            return 'Camera constraints not supported.';
        } else {
            return 'Unknown camera error occurred.';
        }
    }

    async openCamera() {
        try {
            this.showError('');
            
            // Clear loading state
            this.cameraPreview.innerHTML = '';
            this.cameraPreview.classList.remove('loading');

            const video = document.createElement('video');
            video.srcObject = this.stream;
            video.autoplay = true;
            video.playsInline = true;
            
            this.cameraPreview.appendChild(video);
            this.cameraControls.classList.remove('hidden');
            
        } catch (error) {
            console.error('Error opening camera:', error);
            this.showError('Failed to open camera. Please check permissions and try again.');
            this.cameraPreview.innerHTML = `
                <div class="camera-error">
                    <i>⚠️</i>
                    <p>Failed to open camera. Please check permissions and try again.</p>
                    <button onclick="window.instaFrameApp.requestCameraAccess()">Retry</button>
                </div>
            `;
        }
    }

    capturePhoto() {
        if (!this.stream) return;

        const video = this.cameraPreview.querySelector('video');
        if (!video) return;

        const canvas = document.createElement('canvas');
        const context = canvas.getContext('2d');

        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        context.drawImage(video, 0, 0);

        // Compress the photo before processing
        this.compressPhoto(canvas);
    }

    compressPhoto(canvas) {
        const maxWidth = 1024;
        const maxHeight = 1024;
        const quality = 0.75;

        let { width, height } = canvas;

        // Calculate new dimensions while maintaining aspect ratio
        if (width > height) {
            if (width > maxWidth) {
                height = (height * maxWidth) / width;
                width = maxWidth;
            }
        } else {
            if (height > maxHeight) {
                width = (width * maxHeight) / height;
                height = maxHeight;
            }
        }

        // Create a new canvas with compressed dimensions
        const compressedCanvas = document.createElement('canvas');
        const compressedContext = compressedCanvas.getContext('2d');
        
        compressedCanvas.width = width;
        compressedCanvas.height = height;

        // Use high-quality image smoothing
        compressedContext.imageSmoothingEnabled = true;
        compressedContext.imageSmoothingQuality = 'high';

        // Draw the image with new dimensions
        compressedContext.drawImage(canvas, 0, 0, width, height);

        // Convert to compressed JPEG
        this.photoData = compressedCanvas.toDataURL('image/jpeg', quality);
        
        // Process immediately after compression
        this.processPhoto();
    }

    async processPhoto() {
        try {
            this.processing.classList.remove('hidden');
            this.showError('');

            // Convert base64 to blob (more efficient than fetch)
            const byteString = atob(this.photoData.split(',')[1]);
            const mimeString = this.photoData.split(',')[0].split(':')[1].split(';')[0];
            const ab = new ArrayBuffer(byteString.length);
            const ia = new Uint8Array(ab);
            for (let i = 0; i < byteString.length; i++) {
                ia[i] = byteString.charCodeAt(i);
            }
            const blob = new Blob([ab], { type: mimeString });

            // Create FormData
            const formData = new FormData();
            formData.append('photo', blob, 'photo.jpg');

            // Send to cloud function
            const result = await fetch('https://us-central1-jeffreyhung-test.cloudfunctions.net/can-sentry-fix-this', {
                method: 'POST',
                body: formData
            });

            if (!result.ok) {
                throw new Error(`HTTP error! status: ${result.status}`);
            }

            const data = await result.json();
            
            if (data.success) {
                this.displayResult(data.imageUrl, data.frameStyle, data.analysisResult);
                this.updateStats(data.frameStyle);
            } else {
                throw new Error(data.error || 'Failed to process photo');
            }

        } catch (error) {
            console.error('Error processing photo:', error);
            this.showError('Failed to process photo. Please try again.');
        } finally {
            this.processing.classList.add('hidden');
        }
    }

    displayResult(imageUrl, frameStyle, analysisResult) {
        // Preload the result image for faster display
        const img = new Image();
        img.onload = () => {
            this.resultImage.src = imageUrl;
            this.resultSection.classList.remove('hidden');
        };
        img.src = imageUrl;
        
        // Update frame style badge based on analysis result
        const styleNames = {
            'yes': 'Software Issue Detected',
            'no': 'No Software Issue'
        };
        
        // Update result section title based on analysis
        const resultTitle = document.querySelector('.result-section h3');
        if (resultTitle) {
            if (analysisResult === 'yes') {
                resultTitle.textContent = 'hell yeah';
                resultTitle.style.color = '#f6f6f8';
            } else if (analysisResult === 'no') {
                resultTitle.textContent = 'oopsie';
                resultTitle.style.color = '#f6f6f8';
            } else {
                resultTitle.textContent = 'Analysis Complete';
                resultTitle.style.color = '#6e47ae';
            }
        }
        const resultText = document.querySelector('.result-section h4');
        if (resultText) {
            if (analysisResult === 'yes') {
                resultText.innerHTML = 'what are you waiting for? <br/> let them know Sentry can help!';
                resultText.style.color = '#f6f6f8';
            } else if (analysisResult === 'no') {
                resultText.innerHTML = '<i>so what exactly can Sentry fix?</i> 🤔';
                resultText.style.color = '#f6f6f8';
            }
        }
    }

    closeResult() {
        this.resultSection.classList.add('hidden');
        
        // Clean up result image to free memory
        this.resultImage.src = '';
        
        // Restart camera
        this.requestCameraAccess();
    }

    // Memory cleanup method
    cleanupResources() {
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }
        
        // Clear large data
        this.photoData = null;
        
        // Clear result image
        if (this.resultImage) {
            this.resultImage.src = '';
        }
    }

    updateStats(frameStyle) {
        this.stats.photosProcessed++;
        this.stats.framesApplied++;
        this.stats.aiAnalyses++;
        this.saveStats();
        this.displayStats();
    }

    displayStats() {
        if (this.photosProcessedEl) this.photosProcessedEl.textContent = this.stats.photosProcessed;
        if (this.framesAppliedEl) this.framesAppliedEl.textContent = this.stats.framesApplied;
        if (this.aiAnalysesEl) this.aiAnalysesEl.textContent = this.stats.aiAnalyses;
    }

    saveStats() {
        localStorage.setItem('instaframe_stats', JSON.stringify(this.stats));
    }

    loadStats() {
        const saved = localStorage.getItem('instaframe_stats');
        if (saved) {
            this.stats = JSON.parse(saved);
            this.displayStats();
        }
    }

    downloadPhoto() {
        if (this.resultImage.src) {
            const link = document.createElement('a');
            link.href = this.resultImage.src;
            link.download = `instaframe-${Date.now()}.jpg`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }
    }

    showError(message) {
        if (message) {
            this.errorMessage.textContent = message;
            this.errorMessage.classList.remove('hidden');
        } else {
            this.errorMessage.classList.add('hidden');
        }
    }
}

// Initialize the app when the page loads
document.addEventListener('DOMContentLoaded', () => {
    window.instaFrameApp = new InstaFrameApp();
});
