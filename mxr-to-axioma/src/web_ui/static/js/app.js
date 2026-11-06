// MXR-to-Axioma Web UI JavaScript

document.addEventListener('DOMContentLoaded', () => {
    console.log('MXR-to-Axioma Translator loaded');
});

// Utility functions
function formatPercent(value) {
    return `${(value * 100).toFixed(0)}%`;
}

function formatDecibels(value) {
    return `${value >= 0 ? '+' : ''}${value.toFixed(1)} dB`;
}

// API helper
async function apiRequest(endpoint, options = {}) {
    const response = await fetch(endpoint, {
        headers: {
            'Content-Type': 'application/json',
            ...options.headers
        },
        ...options
    });
    
    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(error.detail || 'Request failed');
    }
    
    return response.json();
}

// Toast notifications
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.classList.add('show');
    }, 10);
    
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Export for use in templates
window.apiRequest = apiRequest;
window.showToast = showToast;
window.formatPercent = formatPercent;
window.formatDecibels = formatDecibels;
