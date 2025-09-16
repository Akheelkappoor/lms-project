from datetime import datetime
from app import db
import json
import traceback
import uuid

class ErrorLog(db.Model):
    """Comprehensive error logging model"""
    __tablename__ = 'error_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    error_id = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    
    # User Information
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    user_role = db.Column(db.String(20))
    session_id = db.Column(db.String(255))
    
    # Error Details
    error_type = db.Column(db.String(100), nullable=False)  # login_error, database_error, etc.
    error_category = db.Column(db.String(50), nullable=False)  # authentication, database, network, etc.
    error_message = db.Column(db.Text)
    error_code = db.Column(db.String(20))
    stack_trace = db.Column(db.Text)
    
    # Request Information
    request_url = db.Column(db.String(500))
    request_method = db.Column(db.String(10))
    request_data = db.Column(db.Text)  # JSON string of form data
    request_headers = db.Column(db.Text)  # JSON string of headers
    
    # Technical Details
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    browser = db.Column(db.String(50))
    device_type = db.Column(db.String(20))  # mobile, desktop, tablet
    operating_system = db.Column(db.String(50))
    
    # Context Information
    previous_page = db.Column(db.String(500))
    action_attempted = db.Column(db.String(200))
    form_data = db.Column(db.Text)  # JSON string of form inputs
    
    # System State
    server_load = db.Column(db.Float)
    memory_usage = db.Column(db.Float)
    database_status = db.Column(db.String(20))
    response_time = db.Column(db.Float)
    
    # Error Status
    severity = db.Column(db.String(20), default='medium')  # low, medium, high, critical
    status = db.Column(db.String(20), default='open')  # open, investigating, resolved, ignored
    resolution = db.Column(db.Text)
    resolved_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    resolved_at = db.Column(db.DateTime)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', foreign_keys=[user_id], backref='error_logs')
    resolver = db.relationship('User', foreign_keys=[resolved_by])
    
    def __init__(self, **kwargs):
        super(ErrorLog, self).__init__(**kwargs)
    
    def set_request_data(self, request_data_dict):
        """Set request data as JSON"""
        self.request_data = json.dumps(request_data_dict) if request_data_dict else None
    
    def get_request_data(self):
        """Get request data as dict"""
        if self.request_data:
            try:
                return json.loads(self.request_data)
            except:
                return {}
        return {}
    
    def set_request_headers(self, headers_dict):
        """Set request headers as JSON"""
        # Filter sensitive headers
        safe_headers = {k: v for k, v in headers_dict.items() 
                       if k.lower() not in ['authorization', 'cookie', 'x-api-key']}
        self.request_headers = json.dumps(safe_headers)
    
    def get_request_headers(self):
        """Get request headers as dict"""
        if self.request_headers:
            try:
                return json.loads(self.request_headers)
            except:
                return {}
        return {}
    
    def set_form_data(self, form_dict):
        """Set form data as JSON (sensitive data filtered)"""
        if form_dict:
            # Filter sensitive fields
            safe_form = {k: v for k, v in form_dict.items() 
                        if k.lower() not in ['password', 'confirm_password', 'token']}
            self.form_data = json.dumps(safe_form)
    
    def get_form_data(self):
        """Get form data as dict"""
        if self.form_data:
            try:
                return json.loads(self.form_data)
            except:
                return {}
        return {}
    
    def mark_resolved(self, resolution_text, resolved_by_user_id):
        """Mark error as resolved"""
        self.status = 'resolved'
        self.resolution = resolution_text
        self.resolved_by = resolved_by_user_id
        self.resolved_at = datetime.utcnow()
        db.session.commit()
    
    def get_severity_color(self):
        """Get color code for severity"""
        colors = {
            'low': '#28a745',      # Green
            'medium': '#ffc107',   # Yellow
            'high': '#fd7e14',     # Orange
            'critical': '#dc3545'  # Red
        }
        return colors.get(self.severity, '#6c757d')
    
    def to_dict(self):
        """Convert error log to dictionary"""
        return {
            'id': self.id,
            'error_id': self.error_id,
            'user_id': self.user_id,
            'user_name': self.user.full_name if self.user else 'Anonymous',
            'user_role': self.user_role,
            'error_type': self.error_type,
            'error_category': self.error_category,
            'error_message': self.error_message,
            'error_code': self.error_code,
            'request_url': self.request_url,
            'request_method': self.request_method,
            'ip_address': self.ip_address,
            'browser': self.browser,
            'device_type': self.device_type,
            'operating_system': self.operating_system,
            'severity': self.severity,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'resolver': self.resolver.full_name if self.resolver else None
        }
    
    @staticmethod
    def log_error(error_type, error_message, **kwargs):
        """Static method to log errors easily"""
        error_log = ErrorLog(
            error_type=error_type,
            error_message=error_message,
            **kwargs
        )
        db.session.add(error_log)
        db.session.commit()
        return error_log
    
    @staticmethod
    def get_error_statistics(days=30):
        """Get error statistics for dashboard"""
        from datetime import datetime, timedelta
        from sqlalchemy import func
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        stats = db.session.query(
            ErrorLog.error_category,
            ErrorLog.severity,
            func.count(ErrorLog.id).label('count')
        ).filter(
            ErrorLog.created_at >= start_date
        ).group_by(
            ErrorLog.error_category, 
            ErrorLog.severity
        ).all()
        
        return stats
    
    @staticmethod
    def get_user_errors(user_id, days=7):
        """Get errors for specific user"""
        from datetime import datetime, timedelta
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        return ErrorLog.query.filter(
            ErrorLog.user_id == user_id,
            ErrorLog.created_at >= start_date
        ).order_by(ErrorLog.created_at.desc()).all()
    
    @staticmethod
    def get_frequent_errors(limit=10):
        """Get most frequent error types"""
        from sqlalchemy import func
        
        return db.session.query(
            ErrorLog.error_type,
            ErrorLog.error_message,
            func.count(ErrorLog.id).label('count')
        ).group_by(
            ErrorLog.error_type,
            ErrorLog.error_message
        ).order_by(
            func.count(ErrorLog.id).desc()
        ).limit(limit).all()
    
    def __repr__(self):
        return f'<ErrorLog {self.error_id}: {self.error_type}>'


class UserActivityLog(db.Model):
    """Detailed user activity logging"""
    __tablename__ = 'user_activity_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    session_id = db.Column(db.String(255))
    
    # Activity Details
    activity_type = db.Column(db.String(50))  # login, logout, page_view, action, error
    page_url = db.Column(db.String(500))
    action_taken = db.Column(db.String(200))
    success = db.Column(db.Boolean)
    
    # Technical Details
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    response_time = db.Column(db.Float)
    
    # Context
    previous_page = db.Column(db.String(500))
    time_on_page = db.Column(db.Integer)  # seconds
    
    # Timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='activity_logs')
    
    @staticmethod
    def log_activity(user_id, activity_type, **kwargs):
        """Log user activity"""
        activity = UserActivityLog(
            user_id=user_id,
            activity_type=activity_type,
            **kwargs
        )
        db.session.add(activity)
        db.session.commit()
        return activity
    
    def to_dict(self):
        """Convert activity to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'user_name': self.user.full_name if self.user else 'Anonymous',
            'activity_type': self.activity_type,
            'page_url': self.page_url,
            'action_taken': self.action_taken,
            'success': self.success,
            'ip_address': self.ip_address,
            'response_time': self.response_time,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class SystemHealthLog(db.Model):
    """System health monitoring"""
    __tablename__ = 'system_health_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # System Metrics
    cpu_usage = db.Column(db.Float)
    memory_usage = db.Column(db.Float)
    disk_usage = db.Column(db.Float)
    database_response_time = db.Column(db.Float)
    active_sessions = db.Column(db.Integer)
    
    # Network Metrics
    network_latency = db.Column(db.Float)
    external_api_status = db.Column(db.Text)  # JSON of external service statuses
    
    # Application Metrics
    error_rate = db.Column(db.Float)
    login_success_rate = db.Column(db.Float)
    page_load_time = db.Column(db.Float)
    
    # Status
    overall_health = db.Column(db.String(20))  # healthy, warning, critical
    alerts_triggered = db.Column(db.Text)  # JSON array of alerts
    
    # Timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    @staticmethod
    def log_health_metrics(**kwargs):
        """Log system health metrics"""
        health_log = SystemHealthLog(**kwargs)
        db.session.add(health_log)
        db.session.commit()
        return health_log
    
    def to_dict(self):
        """Convert health log to dictionary"""
        return {
            'id': self.id,
            'cpu_usage': self.cpu_usage,
            'memory_usage': self.memory_usage,
            'disk_usage': self.disk_usage,
            'database_response_time': self.database_response_time,
            'active_sessions': self.active_sessions,
            'network_latency': self.network_latency,
            'error_rate': self.error_rate,
            'login_success_rate': self.login_success_rate,
            'overall_health': self.overall_health,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }