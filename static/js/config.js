// Environment configuration
const config = {
    // For development - will be overridden in production
    apiBaseUrl: '',
    
    // For production - will be set by the deployment script
    // This will be replaced with the actual service URL during the build process
    kubernetesServiceUrl: process.env.API_BASE_URL || 'http://qr-photo-upload-service',
    
    // Check if running in Kubernetes
    isKubernetes: window.location.hostname.includes('k8s') || 
                 window.location.hostname.includes('kubernetes') ||
                 process.env.NODE_ENV === 'production',
    
    // Get the appropriate API URL based on environment
    getApiUrl: function() {
        if (this.isKubernetes) {
            return this.kubernetesServiceUrl;
        }
        // For development, use relative URLs
        return this.apiBaseUrl || '';
    }
};

export default config;
