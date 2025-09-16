/**
 * Advanced Lazy Loading System for LMS
 * Handles images, tables, content blocks, and async operations
 */

class LazyLoadingManager {
    constructor() {
        this.observers = new Map();
        this.loadingStates = new Map();
        this.options = {
            root: null,
            rootMargin: '50px',
            threshold: 0.1
        };
        this.init();
    }

    init() {
        // Check for IntersectionObserver support
        if (!window.IntersectionObserver) {
            console.error('IntersectionObserver not supported in this browser');
            return;
        }
        
        // Initialize lazy loading for different content types
        this.initImageLazyLoading();
        this.initTableLazyLoading();
        this.initContentLazyLoading();
        this.initFormLazyLoading();
        this.initAPILazyLoading();
        
        // Global event listeners
        document.addEventListener('DOMContentLoaded', () => {
            this.scanForLazyElements();
        });
        
        // Re-scan when new content is added dynamically
        this.setupMutationObserver();
    }

    /**
     * Image Lazy Loading
     */
    initImageLazyLoading() {
        const imageObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    this.loadImage(entry.target);
                    imageObserver.unobserve(entry.target);
                }
            });
        }, this.options);

        this.observers.set('images', imageObserver);
        this.observeImages();
    }

    observeImages() {
        const images = document.querySelectorAll('img[data-lazy-src]:not([data-lazy-loaded])');
        images.forEach(img => {
            this.addLoadingSpinner(img);
            this.observers.get('images').observe(img);
        });
    }

    loadImage(img) {
        const src = img.dataset.lazySrc;
        const placeholder = img.src;
        
        // Create a new image to preload
        const newImg = new Image();
        newImg.onload = () => {
            img.src = src;
            img.classList.add('lazy-loaded');
            img.dataset.lazyLoaded = 'true';
            this.removeLoadingSpinner(img);
            
            // Fade in effect
            img.style.opacity = '0';
            img.style.transition = 'opacity 0.3s ease-in-out';
            setTimeout(() => {
                img.style.opacity = '1';
            }, 10);
        };
        
        newImg.onerror = () => {
            img.src = placeholder || '/static/images/placeholder.svg';
            img.classList.add('lazy-error');
            this.removeLoadingSpinner(img);
        };
        
        newImg.src = src;
    }

    /**
     * Table Lazy Loading
     */
    initTableLazyLoading() {
        const tableObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    this.loadTable(entry.target);
                    tableObserver.unobserve(entry.target);
                }
            });
        }, this.options);

        this.observers.set('tables', tableObserver);
        this.observeTables();
    }

    observeTables() {
        const tables = document.querySelectorAll('[data-lazy-table]:not([data-lazy-loaded])');
        tables.forEach(table => {
            this.addTableSkeleton(table);
            this.observers.get('tables').observe(table);
        });
    }

    async loadTable(tableContainer) {
        const endpoint = tableContainer.dataset.lazyTable;
        const tableId = tableContainer.id || `table_${Date.now()}`;
        
        try {
            this.setLoadingState(tableId, true);
            
            const response = await fetch(endpoint, {
                headers: {
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || ''
                }
            });
            
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            
            if (data.html) {
                tableContainer.innerHTML = data.html;
            } else if (data.data) {
                this.renderTableData(tableContainer, data);
            }
            
            tableContainer.dataset.lazyLoaded = 'true';
            this.setLoadingState(tableId, false);
            
            // Initialize any additional functionality
            this.initTableFeatures(tableContainer);
            
        } catch (error) {
            console.error('Error loading table:', error);
            this.showTableError(tableContainer);
            this.setLoadingState(tableId, false);
        }
    }

    /**
     * Content Block Lazy Loading
     */
    initContentLazyLoading() {
        const contentObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    this.loadContent(entry.target);
                    contentObserver.unobserve(entry.target);
                }
            });
        }, this.options);

        this.observers.set('content', contentObserver);
        this.observeContent();
    }

    observeContent() {
        const content = document.querySelectorAll('[data-lazy-content]:not([data-lazy-loaded])');
        content.forEach(element => {
            this.addContentSkeleton(element);
            this.observers.get('content').observe(element);
        });
    }

    async loadContent(element) {
        const endpoint = element.dataset.lazyContent;
        const contentId = element.id || `content_${Date.now()}`;
        
        try {
            this.setLoadingState(contentId, true);
            
            const response = await fetch(endpoint, {
                headers: {
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || ''
                }
            });
            
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            
            // Handle different response types
            if (data.html) {
                element.innerHTML = data.html;
            } else if (data.content) {
                element.innerHTML = data.content;
            } else {
                element.innerHTML = this.formatContentData(data);
            }
            
            element.dataset.lazyLoaded = 'true';
            this.setLoadingState(contentId, false);
            
            // Re-scan for nested lazy elements
            this.scanForLazyElements(element);
            
        } catch (error) {
            console.error('Error loading content:', error);
            this.showContentError(element);
            this.setLoadingState(contentId, false);
        }
    }

    /**
     * Form Lazy Loading
     */
    initFormLazyLoading() {
        document.addEventListener('submit', (e) => {
            const form = e.target;
            if (form.dataset.lazySubmit !== undefined) {
                e.preventDefault();
                this.handleLazyFormSubmit(form);
            }
        });
    }

    async handleLazyFormSubmit(form) {
        const formId = form.id || `form_${Date.now()}`;
        const submitBtn = form.querySelector('[type="submit"]');
        const originalText = submitBtn ? submitBtn.innerHTML : '';
        
        try {
            this.setLoadingState(formId, true);
            
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = `
                    <span class="spinner-border spinner-border-sm me-2"></span>
                    ${form.dataset.loadingText || 'Processing...'}
                `;
            }
            
            const formData = new FormData(form);
            const response = await fetch(form.action, {
                method: form.method || 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': formData.get('csrf_token') || document.querySelector('meta[name="csrf-token"]')?.content || ''
                }
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showFormSuccess(form, result.message);
                if (result.redirect) {
                    setTimeout(() => window.location.href = result.redirect, 1500);
                }
            } else {
                this.showFormError(form, result.message || 'An error occurred');
            }
            
        } catch (error) {
            console.error('Form submission error:', error);
            this.showFormError(form, 'Network error occurred');
        } finally {
            this.setLoadingState(formId, false);
            
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalText;
            }
        }
    }

    /**
     * API Lazy Loading
     */
    initAPILazyLoading() {
        // Auto-load API elements on page load
        document.addEventListener('DOMContentLoaded', () => {
            this.loadAPIElements();
        });
    }

    loadAPIElements() {
        const apiElements = document.querySelectorAll('[data-lazy-api]:not([data-lazy-loaded])');
        apiElements.forEach(element => {
            this.loadAPIData(element);
        });
    }

    async loadAPIData(element) {
        const endpoint = element.dataset.lazyApi;
        const interval = parseInt(element.dataset.lazyInterval) || 0;
        const elementId = element.id || `api_${Date.now()}`;
        
        const loadData = async () => {
            try {
                this.setLoadingState(elementId, true, false);
                
                const response = await fetch(endpoint, {
                    headers: {
                        'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || ''
                    }
                });
                
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                
                const data = await response.json();
                this.renderAPIData(element, data);
                
                element.dataset.lazyLoaded = 'true';
                
            } catch (error) {
                console.error('API loading error:', error);
                this.showAPIError(element);
            } finally {
                this.setLoadingState(elementId, false);
            }
        };
        
        // Initial load
        await loadData();
        
        // Set up interval if specified
        if (interval > 0) {
            setInterval(loadData, interval);
        }
    }

    /**
     * Utility Methods
     */
    addLoadingSpinner(element) {
        const spinner = document.createElement('div');
        spinner.className = 'lazy-loading-spinner';
        spinner.innerHTML = `
            <div class="spinner-border spinner-border-sm" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
        `;
        
        if (element.parentNode) {
            element.parentNode.insertBefore(spinner, element.nextSibling);
        }
    }

    removeLoadingSpinner(element) {
        const spinner = element.parentNode?.querySelector('.lazy-loading-spinner');
        if (spinner) {
            spinner.remove();
        }
    }

    addTableSkeleton(table) {
        const skeleton = `
            <div class="table-skeleton">
                <div class="skeleton-row">
                    <div class="skeleton-cell"></div>
                    <div class="skeleton-cell"></div>
                    <div class="skeleton-cell"></div>
                    <div class="skeleton-cell"></div>
                </div>
                <div class="skeleton-row">
                    <div class="skeleton-cell"></div>
                    <div class="skeleton-cell"></div>
                    <div class="skeleton-cell"></div>
                    <div class="skeleton-cell"></div>
                </div>
                <div class="skeleton-row">
                    <div class="skeleton-cell"></div>
                    <div class="skeleton-cell"></div>
                    <div class="skeleton-cell"></div>
                    <div class="skeleton-cell"></div>
                </div>
            </div>
        `;
        table.innerHTML = skeleton;
    }

    addContentSkeleton(element) {
        const skeleton = `
            <div class="content-skeleton">
                <div class="skeleton-line"></div>
                <div class="skeleton-line short"></div>
                <div class="skeleton-line"></div>
                <div class="skeleton-line medium"></div>
            </div>
        `;
        element.innerHTML = skeleton;
    }

    showTableError(table) {
        table.innerHTML = `
            <div class="alert alert-warning" role="alert">
                <i class="fas fa-exclamation-triangle me-2"></i>
                Failed to load table data. <a href="#" onclick="location.reload()">Refresh page</a>
            </div>
        `;
    }

    showContentError(element) {
        element.innerHTML = `
            <div class="alert alert-warning" role="alert">
                <i class="fas fa-exclamation-triangle me-2"></i>
                Failed to load content. <a href="#" onclick="location.reload()">Try again</a>
            </div>
        `;
    }

    showAPIError(element) {
        element.innerHTML = `
            <div class="text-muted small">
                <i class="fas fa-exclamation-circle me-1"></i>
                Unable to load data
            </div>
        `;
    }

    showFormSuccess(form, message) {
        this.showFormAlert(form, message, 'success');
    }

    showFormError(form, message) {
        this.showFormAlert(form, message, 'danger');
    }

    showFormAlert(form, message, type) {
        const alertId = `alert_${Date.now()}`;
        const alert = document.createElement('div');
        alert.id = alertId;
        alert.className = `alert alert-${type} alert-dismissible fade show`;
        alert.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        form.parentNode.insertBefore(alert, form);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            const alertElement = document.getElementById(alertId);
            if (alertElement) {
                alertElement.remove();
            }
        }, 5000);
    }

    setLoadingState(id, isLoading, showGlobal = true) {
        this.loadingStates.set(id, isLoading);
        
        // Update any loading indicators for this specific element
        const element = document.getElementById(id);
        if (element) {
            if (isLoading) {
                element.classList.add('lazy-loading');
            } else {
                element.classList.remove('lazy-loading');
            }
        }
    }

    renderTableData(container, data) {
        // Basic table rendering - can be customized
        if (data.columns && data.rows) {
            let html = '<table class="table table-hover">';
            
            // Header
            html += '<thead><tr>';
            data.columns.forEach(col => {
                html += `<th>${col}</th>`;
            });
            html += '</tr></thead>';
            
            // Body
            html += '<tbody>';
            data.rows.forEach(row => {
                html += '<tr>';
                row.forEach(cell => {
                    html += `<td>${cell}</td>`;
                });
                html += '</tr>';
            });
            html += '</tbody></table>';
            
            container.innerHTML = html;
        }
    }

    renderAPIData(element, data) {
        // Handle different data formats
        if (data.html) {
            element.innerHTML = data.html;
        } else if (data.count !== undefined) {
            element.textContent = data.count;
        } else if (data.text) {
            element.textContent = data.text;
        } else if (typeof data === 'string') {
            element.textContent = data;
        } else {
            element.innerHTML = `<pre>${JSON.stringify(data, null, 2)}</pre>`;
        }
    }

    formatContentData(data) {
        // Default content formatting
        return `<div class="lazy-content">${JSON.stringify(data)}</div>`;
    }

    initTableFeatures(table) {
        // Initialize any table-specific features like sorting, filtering
        const sortableHeaders = table.querySelectorAll('[data-sortable]');
        sortableHeaders.forEach(header => {
            header.style.cursor = 'pointer';
            header.addEventListener('click', () => {
                this.sortTable(table, header);
            });
        });
    }

    sortTable(table, header) {
        // Basic table sorting implementation
        console.log('Sorting table by:', header.textContent);
        // Implementation would go here
    }

    setupMutationObserver() {
        const observer = new MutationObserver((mutations) => {
            mutations.forEach(mutation => {
                if (mutation.type === 'childList') {
                    mutation.addedNodes.forEach(node => {
                        if (node.nodeType === 1) { // Element node
                            this.scanForLazyElements(node);
                        }
                    });
                }
            });
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    }

    scanForLazyElements(container = document) {
        // Re-observe new lazy images
        const newImages = container.querySelectorAll('img[data-lazy-src]:not([data-lazy-loaded])');
        newImages.forEach(img => {
            this.addLoadingSpinner(img);
            this.observers.get('images').observe(img);
        });

        // Re-observe new lazy tables
        const newTables = container.querySelectorAll('[data-lazy-table]:not([data-lazy-loaded])');
        newTables.forEach(table => {
            this.addTableSkeleton(table);
            this.observers.get('tables').observe(table);
        });

        // Re-observe new lazy content
        const newContent = container.querySelectorAll('[data-lazy-content]:not([data-lazy-loaded])');
        newContent.forEach(element => {
            this.addContentSkeleton(element);
            this.observers.get('content').observe(element);
        });

        // Load new API elements
        const newAPI = container.querySelectorAll('[data-lazy-api]:not([data-lazy-loaded])');
        newAPI.forEach(element => {
            this.loadAPIData(element);
        });
    }

    // Public API methods
    refresh(selector) {
        const elements = document.querySelectorAll(selector);
        elements.forEach(element => {
            element.dataset.lazyLoaded = 'false';
            delete element.dataset.lazyLoaded;
        });
        this.scanForLazyElements();
    }

    destroy() {
        this.observers.forEach(observer => observer.disconnect());
        this.observers.clear();
        this.loadingStates.clear();
    }
}

// Global instance
window.LazyLoader = new LazyLoadingManager();

// Expose useful methods globally
window.refreshLazyLoading = (selector = '[data-lazy-src], [data-lazy-table], [data-lazy-content], [data-lazy-api]') => {
    window.LazyLoader.refresh(selector);
};