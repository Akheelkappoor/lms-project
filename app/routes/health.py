# Health check endpoint for production monitoring

from flask import Blueprint, jsonify, current_app
from datetime import datetime
from app import db
from app.models.user import User
import os

bp = Blueprint('health', __name__)

@bp.route('/health')
def health_check():
    """Comprehensive health check endpoint for monitoring"""
    
    health_status = {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'version': '1.0.0',
        'checks': {}
    }
    
    try:
        # Database connectivity check
        try:
            db.session.execute('SELECT 1')
            health_status['checks']['database'] = 'healthy'
        except Exception as e:
            health_status['checks']['database'] = f'unhealthy: {str(e)}'
            health_status['status'] = 'unhealthy'
        
        # User model check
        try:
            user_count = User.query.count()
            health_status['checks']['users'] = f'healthy ({user_count} users)'
        except Exception as e:
            health_status['checks']['users'] = f'unhealthy: {str(e)}'
            health_status['status'] = 'unhealthy'
        
        # Email configuration check
        try:
            mail_server = current_app.config.get('MAIL_SERVER')
            mail_username = current_app.config.get('MAIL_USERNAME')
            if mail_server and mail_username:
                health_status['checks']['email'] = 'configured'
            else:
                health_status['checks']['email'] = 'not_configured'
        except Exception as e:
            health_status['checks']['email'] = f'error: {str(e)}'
        
        # S3 configuration check
        try:
            s3_bucket = current_app.config.get('S3_BUCKET')
            aws_key = current_app.config.get('AWS_ACCESS_KEY_ID')
            if s3_bucket and aws_key:
                health_status['checks']['s3'] = 'configured'
            else:
                health_status['checks']['s3'] = 'not_configured'
        except Exception as e:
            health_status['checks']['s3'] = f'error: {str(e)}'
        
        # Disk space check
        try:
            statvfs = os.statvfs('.')
            free_space_gb = (statvfs.f_frsize * statvfs.f_bavail) / (1024**3)
            if free_space_gb > 1:  # More than 1GB free
                health_status['checks']['disk_space'] = f'healthy ({free_space_gb:.2f}GB free)'
            else:
                health_status['checks']['disk_space'] = f'warning ({free_space_gb:.2f}GB free)'
                health_status['status'] = 'degraded'
        except Exception as e:
            health_status['checks']['disk_space'] = f'error: {str(e)}'
        
        return jsonify(health_status), 200 if health_status['status'] == 'healthy' else 503
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@bp.route('/health/simple')
def simple_health_check():
    """Simple health check for load balancers"""
    return jsonify({'status': 'ok'}), 200