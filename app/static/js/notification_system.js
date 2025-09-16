/**
 * Advanced Notification System for LMS
 * Handles popup notifications, in-app alerts, and real-time updates
 */

class NotificationSystem {
    constructor() {
        this.checkInterval = 30000; // Check every 30 seconds
        this.isInitialized = false;
        this.activePopups = new Map();
        this.notificationQueue = [];
        this.soundEnabled = true;
        
        this.init();
    }
    
    init() {
        if (this.isInitialized) return;
        
        this.createNotificationContainer();
        this.loadUserPreferences();
        this.startPeriodicCheck();
        this.bindEvents();
        
        // Check for notifications on page load
        this.checkForPopupNotifications();
        this.updateUnreadCount();
        
        this.isInitialized = true;
        console.log('Notification system initialized');
    }
    
    createNotificationContainer() {
        // Create popup container if it doesn't exist
        if (!document.getElementById('notification-popup-container')) {
            const container = document.createElement('div');
            container.id = 'notification-popup-container';
            container.className = 'notification-popup-container';
            document.body.appendChild(container);
        }
        
        // Create notification bell container if it doesn't exist
        if (!document.getElementById('notification-bell')) {
            // This will be handled by the template
        }
        
        // Add CSS styles
        this.injectStyles();
    }
    
    injectStyles() {
        if (document.getElementById('notification-system-styles')) return;
        
        const styles = `
            <style id="notification-system-styles">
            .notification-popup-container {
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 10000;
                max-width: 400px;
                pointer-events: none;
            }
            
            .notification-popup {
                background: white;
                border-radius: 12px;
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
                margin-bottom: 15px;
                overflow: hidden;
                transform: translateX(100%);
                transition: all 0.3s cubic-bezier(0.68, -0.55, 0.265, 1.55);
                pointer-events: auto;
                border-left: 5px solid #667eea;
                max-width: 380px;
            }
            
            .notification-popup.show {
                transform: translateX(0);
            }
            
            .notification-popup.emergency {
                border-left-color: #ff6b6b;
                animation: urgent-pulse 2s infinite;
            }
            
            .notification-popup.holiday {
                border-left-color: #feca57;
            }
            
            .notification-popup.critical {
                border-left-color: #ff3838;
                animation: critical-shake 0.5s infinite;
            }
            
            @keyframes urgent-pulse {
                0%, 100% { box-shadow: 0 10px 30px rgba(255, 107, 107, 0.3); }
                50% { box-shadow: 0 15px 40px rgba(255, 107, 107, 0.5); }
            }
            
            @keyframes critical-shake {
                0%, 100% { transform: translateX(0); }
                25% { transform: translateX(-2px); }
                75% { transform: translateX(2px); }
            }
            
            .notification-popup-header {
                padding: 15px 20px 10px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
            }
            
            .notification-popup.emergency .notification-popup-header {
                background: linear-gradient(135deg, #ff6b6b 0%, #ee5a24 100%);
            }
            
            .notification-popup.holiday .notification-popup-header {
                background: linear-gradient(135deg, #feca57 0%, #ff9ff3 100%);
            }
            
            .notification-popup-title {
                font-weight: bold;
                font-size: 16px;
                margin: 0;
                flex: 1;
                line-height: 1.3;
            }
            
            .notification-popup-priority {
                background: rgba(255, 255, 255, 0.2);
                padding: 2px 8px;
                border-radius: 10px;
                font-size: 10px;
                font-weight: bold;
                text-transform: uppercase;
                margin-left: 10px;
                white-space: nowrap;
            }
            
            .notification-popup-close {
                background: none;
                border: none;
                color: white;
                font-size: 20px;
                cursor: pointer;
                padding: 0;
                width: 24px;
                height: 24px;
                display: flex;
                align-items: center;
                justify-content: center;
                border-radius: 50%;
                transition: background-color 0.2s;
                margin-left: 10px;
            }
            
            .notification-popup-close:hover {
                background: rgba(255, 255, 255, 0.2);
            }
            
            .notification-popup-body {
                padding: 20px;
            }
            
            .notification-popup-message {
                color: #333;
                line-height: 1.5;
                margin-bottom: 15px;
                font-size: 14px;
            }
            
            .notification-popup-actions {
                display: flex;
                gap: 10px;
                justify-content: flex-end;
                margin-top: 15px;
            }
            
            .notification-popup-btn {
                padding: 8px 16px;
                border: none;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 500;
                cursor: pointer;
                transition: all 0.2s;
            }
            
            .notification-popup-btn.primary {
                background: #667eea;
                color: white;
            }
            
            .notification-popup-btn.primary:hover {
                background: #5a6fd8;
            }
            
            .notification-popup-btn.secondary {
                background: #f8f9fa;
                color: #666;
                border: 1px solid #dee2e6;
            }
            
            .notification-popup-btn.secondary:hover {
                background: #e9ecef;
            }
            
            .notification-popup-timestamp {
                color: #888;
                font-size: 12px;
                margin-top: 10px;
                text-align: right;
            }
            
            .notification-bell {
                position: relative;
                cursor: pointer;
                color: #666;
                transition: color 0.2s;
            }
            
            .notification-bell:hover {
                color: #333;
            }
            
            .notification-bell.has-notifications {
                color: #ff6b6b;
                animation: bell-ring 2s infinite;
            }
            
            @keyframes bell-ring {
                0%, 15%, 30% { transform: rotate(0deg); }
                5%, 25% { transform: rotate(15deg); }
                10%, 20% { transform: rotate(-15deg); }
            }
            
            .notification-count {
                position: absolute;
                top: -8px;
                right: -8px;
                background: #ff4757;
                color: white;
                border-radius: 50%;
                width: 20px;
                height: 20px;
                font-size: 10px;
                font-weight: bold;
                display: flex;
                align-items: center;
                justify-content: center;
                animation: count-pulse 2s infinite;
            }
            
            @keyframes count-pulse {
                0%, 100% { transform: scale(1); }
                50% { transform: scale(1.1); }
            }
            
            .notification-sound-toggle {
                position: fixed;
                bottom: 20px;
                right: 20px;
                background: #667eea;
                color: white;
                border: none;
                border-radius: 50%;
                width: 50px;
                height: 50px;
                font-size: 20px;
                cursor: pointer;
                box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
                transition: all 0.3s;
                z-index: 9999;
            }
            
            .notification-sound-toggle:hover {
                transform: scale(1.1);
                box-shadow: 0 6px 16px rgba(102, 126, 234, 0.4);
            }
            
            .notification-sound-toggle.muted {
                background: #95a5a6;
            }
            
            @media (max-width: 768px) {
                .notification-popup-container {
                    left: 10px;
                    right: 10px;
                    top: 10px;
                    max-width: none;
                }
                
                .notification-popup {
                    max-width: none;
                }
                
                .notification-popup-header {
                    padding: 12px 15px 8px;
                }
                
                .notification-popup-body {
                    padding: 15px;
                }
                
                .notification-popup-title {
                    font-size: 14px;
                }
                
                .notification-popup-message {
                    font-size: 13px;
                }
            }
            </style>
        `;
        
        document.head.insertAdjacentHTML('beforeend', styles);
    }
    
    startPeriodicCheck() {
        // Check immediately on start
        this.checkForPopupNotifications();
        
        // Set up periodic checks
        setInterval(() => {
            this.checkForPopupNotifications();
            this.updateUnreadCount();
        }, this.checkInterval);
    }
    
    async checkForPopupNotifications() {
        try {
            const response = await fetch('/api/notifications/popup');
            const data = await response.json();
            
            if (data.notifications && data.notifications.length > 0) {
                data.notifications.forEach(notification => {
                    if (!this.activePopups.has(notification.id)) {
                        this.showPopupNotification(notification);
                    }
                });
            }
        } catch (error) {
            console.error('Error checking for popup notifications:', error);
        }
    }
    
    async updateUnreadCount() {
        try {
            const response = await fetch('/api/notifications/unread-count');
            const data = await response.json();
            
            const bellElement = document.querySelector('.notification-bell');
            const countElement = document.querySelector('.notification-count');
            
            if (bellElement) {
                if (data.unread_count > 0) {
                    bellElement.classList.add('has-notifications');
                    
                    if (countElement) {
                        countElement.textContent = data.unread_count;
                        countElement.style.display = 'flex';
                    }
                } else {
                    bellElement.classList.remove('has-notifications');
                    
                    if (countElement) {
                        countElement.style.display = 'none';
                    }
                }
            }
        } catch (error) {
            console.error('Error updating unread count:', error);
        }
    }
    
    showPopupNotification(notification) {
        // Add to active popups
        this.activePopups.set(notification.id, notification);
        
        // Create popup element
        const popup = this.createPopupElement(notification);
        
        // Add to container
        const container = document.getElementById('notification-popup-container');
        container.appendChild(popup);
        
        // Trigger animation
        setTimeout(() => {
            popup.classList.add('show');
        }, 100);
        
        // Play sound if enabled
        if (this.soundEnabled && notification.priority !== 'normal') {
            this.playNotificationSound(notification.priority);
        }
        
        // Auto-hide after delay (except for critical notifications)
        if (notification.priority !== 'critical') {
            const delay = this.getAutoHideDelay(notification.priority);
            setTimeout(() => {
                this.hidePopupNotification(notification.id);
            }, delay);
        }
        
        // Mark popup as shown
        this.markPopupAsShown(notification.id);
    }
    
    createPopupElement(notification) {
        const popup = document.createElement('div');
        popup.className = `notification-popup ${notification.type}`;
        popup.dataset.notificationId = notification.id;
        
        const priorityIcons = {
            normal: '📢',
            high: '⚡',
            urgent: '⚠️',
            critical: '🚨'
        };
        
        const typeIcons = {
            general: '📢',
            holiday: '🎉',
            emergency: '🚨',
            academic: '📚',
            administrative: '📋',
            maintenance: '🔧'
        };
        
        popup.innerHTML = `
            <div class="notification-popup-header">
                <div style="flex: 1;">
                    <div class="notification-popup-title">
                        ${typeIcons[notification.type] || '📢'} ${notification.title}
                    </div>
                </div>
                <div class="notification-popup-priority">
                    ${priorityIcons[notification.priority]} ${notification.priority.toUpperCase()}
                </div>
                <button class="notification-popup-close" onclick="notificationSystem.hidePopupNotification(${notification.id})">
                    ×
                </button>
            </div>
            <div class="notification-popup-body">
                <div class="notification-popup-message">
                    ${this.formatMessage(notification.message)}
                </div>
                <div class="notification-popup-actions">
                    <button class="notification-popup-btn secondary" onclick="notificationSystem.dismissNotification(${notification.id})">
                        Dismiss
                    </button>
                    <button class="notification-popup-btn primary" onclick="notificationSystem.viewNotification(${notification.id})">
                        View Details
                    </button>
                </div>
                <div class="notification-popup-timestamp">
                    ${this.formatTimestamp(notification.created_at)}
                </div>
            </div>
        `;
        
        return popup;
    }
    
    hidePopupNotification(notificationId) {
        const popup = document.querySelector(`[data-notification-id="${notificationId}"]`);
        if (popup) {
            popup.classList.remove('show');
            setTimeout(() => {
                popup.remove();
                this.activePopups.delete(notificationId);
            }, 300);
        }
    }
    
    async dismissNotification(notificationId) {
        try {
            const response = await fetch(`/api/notifications/${notificationId}/dismiss`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                }
            });
            
            if (response.ok) {
                this.hidePopupNotification(notificationId);
                this.updateUnreadCount();
            }
        } catch (error) {
            console.error('Error dismissing notification:', error);
        }
    }
    
    async viewNotification(notificationId) {
        // Mark as read and redirect to notification view
        try {
            await fetch(`/api/notifications/${notificationId}/read`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                }
            });
            
            this.hidePopupNotification(notificationId);
            window.location.href = `/notifications/${notificationId}`;
        } catch (error) {
            console.error('Error marking notification as read:', error);
            // Still redirect even if marking as read fails
            window.location.href = `/notifications/${notificationId}`;
        }
    }
    
    async markPopupAsShown(notificationId) {
        try {
            await fetch(`/api/notifications/${notificationId}/popup-shown`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                }
            });
        } catch (error) {
            console.error('Error marking popup as shown:', error);
        }
    }
    
    playNotificationSound(priority) {
        if (!this.soundEnabled) return;
        
        // Create audio context for playing notification sounds
        try {
            const audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const oscillator = audioContext.createOscillator();
            const gainNode = audioContext.createGain();
            
            oscillator.connect(gainNode);
            gainNode.connect(audioContext.destination);
            
            // Different tones for different priorities
            const frequencies = {
                high: [800, 1000],
                urgent: [600, 800, 1000],
                critical: [400, 600, 800, 1000]
            };
            
            const freqs = frequencies[priority] || [800];
            
            oscillator.frequency.value = freqs[0];
            gainNode.gain.value = 0.1;
            
            oscillator.start();
            
            // Play sequence for urgent/critical
            if (freqs.length > 1) {
                let index = 0;
                const interval = setInterval(() => {
                    index++;
                    if (index < freqs.length) {
                        oscillator.frequency.value = freqs[index];
                    } else {
                        clearInterval(interval);
                        oscillator.stop();
                    }
                }, 200);
            } else {
                setTimeout(() => oscillator.stop(), 300);
            }
        } catch (error) {
            console.warn('Could not play notification sound:', error);
        }
    }
    
    getAutoHideDelay(priority) {
        const delays = {
            normal: 5000,
            high: 8000,
            urgent: 12000,
            critical: 0 // Never auto-hide
        };
        return delays[priority] || 5000;
    }
    
    formatMessage(message) {
        // Basic HTML sanitization and formatting
        return message
            .replace(/\n/g, '<br>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>');
    }
    
    formatTimestamp(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const diffInMinutes = Math.floor((now - date) / 60000);
        
        if (diffInMinutes < 1) {
            return 'Just now';
        } else if (diffInMinutes < 60) {
            return `${diffInMinutes} minute${diffInMinutes > 1 ? 's' : ''} ago`;
        } else if (diffInMinutes < 1440) {
            const hours = Math.floor(diffInMinutes / 60);
            return `${hours} hour${hours > 1 ? 's' : ''} ago`;
        } else {
            return date.toLocaleDateString();
        }
    }
    
    getCSRFToken() {
        const token = document.querySelector('meta[name=csrf-token]');
        return token ? token.getAttribute('content') : '';
    }
    
    bindEvents() {
        // Sound toggle button
        this.createSoundToggle();
        
        // Notification bell click
        document.addEventListener('click', (e) => {
            if (e.target.closest('.notification-bell')) {
                window.location.href = '/notifications';
            }
        });
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // Esc to close all popups
            if (e.key === 'Escape') {
                this.closeAllPopups();
            }
        });
    }
    
    createSoundToggle() {
        const toggle = document.createElement('button');
        toggle.className = 'notification-sound-toggle';
        toggle.innerHTML = this.soundEnabled ? '🔊' : '🔇';
        toggle.title = this.soundEnabled ? 'Disable notification sounds' : 'Enable notification sounds';
        
        toggle.addEventListener('click', () => {
            this.soundEnabled = !this.soundEnabled;
            toggle.innerHTML = this.soundEnabled ? '🔊' : '🔇';
            toggle.title = this.soundEnabled ? 'Disable notification sounds' : 'Enable notification sounds';
            toggle.classList.toggle('muted', !this.soundEnabled);
            
            // Save preference
            localStorage.setItem('notificationSoundEnabled', this.soundEnabled);
        });
        
        document.body.appendChild(toggle);
    }
    
    loadUserPreferences() {
        const soundPref = localStorage.getItem('notificationSoundEnabled');
        if (soundPref !== null) {
            this.soundEnabled = soundPref === 'true';
        }
    }
    
    closeAllPopups() {
        this.activePopups.forEach((notification, id) => {
            this.hidePopupNotification(id);
        });
    }
    
    // Public method to manually trigger notification check
    forceCheck() {
        this.checkForPopupNotifications();
        this.updateUnreadCount();
    }
}

// Initialize notification system when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.notificationSystem = new NotificationSystem();
});

// Also initialize if DOM is already loaded
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.notificationSystem = new NotificationSystem();
    });
} else {
    window.notificationSystem = new NotificationSystem();
}