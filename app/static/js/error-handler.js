
// Minimal Error Handler - No Network Calls
console.log('Minimal error handler loaded - network errors disabled');

// Override any existing error reporters
window.reportError = function() {
    console.log('Error reporting disabled to prevent loops');
};

// Disable fetch for error reporting
const originalFetch = window.fetch;
window.fetch = function(url, options) {
    if (url.includes('/api/error-report') || url.includes('/api/notices') || url.includes('/reschedule/api') || url.includes('/admin/errors/api')) {
        console.log('Blocked problematic API call:', url);
        return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({status: 'disabled'})
        });
    }
    return originalFetch.apply(this, arguments);
};
