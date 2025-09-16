from flask import Flask
from app.utils.error_tracker import init_error_tracking
from app.routes import error_monitoring


def initialize_error_monitoring(app: Flask):
    """Initialize the error monitoring system"""
    try:
        # Initialize error tracking middleware
        init_error_tracking(app)
        
        # Register error monitoring blueprint
        app.register_blueprint(error_monitoring.bp)
        
        app.logger.info("Error monitoring system initialized successfully")
        
    except Exception as e:
        app.logger.error(f"Failed to initialize error monitoring: {str(e)}")


def setup_error_monitoring_permissions():
    """Setup error monitoring permissions for different roles"""
    # This function can be called during app setup to ensure permissions are correctly configured
    
    permission_mappings = {
        'error_monitoring': {
            'description': 'Access to error monitoring dashboard and tools',
            'roles': ['superadmin', 'admin', 'coordinator'],
            'level': 'high'
        }
    }
    
    return permission_mappings