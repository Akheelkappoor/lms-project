from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from datetime import datetime
import logging
import json
from sqlalchemy import or_
from app import db
from app.models.user import User
from app.models.department import Department
from app.models.tutor import Tutor
from app.models.student import Student
from app.models.class_model import Class
from app.models.attendance import Attendance

# Set up logging
logger = logging.getLogger(__name__)
error_logger = logging.getLogger('errors')
performance_logger = logging.getLogger('performance')

bp = Blueprint('api_monitoring', __name__, url_prefix='/api')

@bp.route('/error-report', methods=['POST'])
@login_required
def error_report():
    """Receive and log client-side errors"""
    try:
        # Better JSON handling
        if not request.is_json:
            return jsonify({'error': 'Content-Type must be application/json'}), 400
        
        try:
            data = request.get_json(force=False, silent=False, cache=False)
        except Exception as json_err:
            logger.error(f"JSON parsing error in error-report: {str(json_err)}")
            return jsonify({'error': 'Invalid JSON format'}), 400
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Extract error data
        errors = data.get('errors', [])
        performance = data.get('performance', {})
        timestamp = data.get('timestamp', datetime.now().isoformat())
        
        # Log each error
        for error in errors:
            error_info = {
                'user_id': current_user.id,
                'user_role': current_user.role,
                'username': current_user.username,
                'error_type': error.get('type', 'unknown'),
                'message': error.get('message', ''),
                'url': error.get('url', ''),
                'filename': error.get('filename', ''),
                'line_number': error.get('lineno', 0),
                'column_number': error.get('colno', 0),
                'stack_trace': error.get('stack', ''),
                'user_agent': error.get('userAgent', ''),
                'timestamp': error.get('timestamp', timestamp)
            }
            
            # Log to file
            error_logger.error(f"Client Error: {json.dumps(error_info, indent=2)}")
            
            # For critical errors, also log to console
            if error.get('type') in ['network_error', 'dashboard_data_missing']:
                logger.critical(f"Critical client error: {error_info}")
        
        # Log performance data if provided
        if performance:
            performance_info = {
                'user_id': current_user.id,
                'user_role': current_user.role,
                'load_time': performance.get('loadTime', 0),
                'dom_ready_time': performance.get('domReadyTime', 0),
                'first_paint': performance.get('firstPaint', 0),
                'url': performance.get('url', ''),
                'timestamp': timestamp
            }
            
            performance_logger.info(f"Performance Data: {json.dumps(performance_info, indent=2)}")
        
        return jsonify({'status': 'success', 'message': 'Error report received'})
    
    except Exception as e:
        logger.error(f"Error processing error report: {str(e)}")
        return jsonify({'error': 'Failed to process error report'}), 500

@bp.route('/performance-report', methods=['POST'])
@login_required
def performance_report():
    """Receive and log performance metrics"""
    try:
        # Better JSON handling
        if not request.is_json:
            return jsonify({'error': 'Content-Type must be application/json'}), 400
        
        try:
            data = request.get_json(force=False, silent=False, cache=False)
        except Exception as json_err:
            logger.error(f"JSON parsing error in performance-report: {str(json_err)}")
            return jsonify({'error': 'Invalid JSON format'}), 400
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        performance_info = {
            'user_id': current_user.id,
            'user_role': current_user.role,
            'username': current_user.username,
            'load_time': data.get('loadTime', 0),
            'dom_ready_time': data.get('domReadyTime', 0),
            'first_paint': data.get('firstPaint', 0),
            'url': data.get('url', ''),
            'timestamp': data.get('timestamp', datetime.now().isoformat())
        }
        
        # Log slow loading
        if performance_info['load_time'] > 5000:
            logger.warning(f"Slow page load detected: {json.dumps(performance_info, indent=2)}")
        
        performance_logger.info(f"Performance Report: {json.dumps(performance_info, indent=2)}")
        
        return jsonify({'status': 'success', 'message': 'Performance report received'})
    
    except Exception as e:
        logger.error(f"Error processing performance report: {str(e)}")
        return jsonify({'error': 'Failed to process performance report'}), 500

@bp.route('/health-check')
@login_required
def health_check():
    """System health check endpoint"""
    try:
        health_status = {
            'database': False,
            'load': 'normal',
            'timestamp': datetime.now().isoformat(),
            'status': 'healthy'
        }
        
        # Test database connection
        try:
            db.session.execute('SELECT 1')
            health_status['database'] = True
        except Exception as e:
            logger.error(f"Database health check failed: {str(e)}")
            health_status['database'] = False
            health_status['status'] = 'degraded'
        
        # Simple load check (you can enhance this)
        try:
            user_count = User.query.count()
            if user_count > 10000:  # Example threshold
                health_status['load'] = 'high'
            elif user_count > 5000:
                health_status['load'] = 'medium'
        except Exception:
            health_status['load'] = 'unknown'
        
        return jsonify(health_status)
    
    except Exception as e:
        logger.error(f"Health check error: {str(e)}")
        return jsonify({
            'database': False,
            'load': 'unknown',
            'status': 'error',
            'timestamp': datetime.now().isoformat()
        }), 500

@bp.route('/dashboard-section/<section_name>')
@login_required
def dashboard_section(section_name):
    """Load dashboard sections dynamically"""
    try:
        if current_user.role not in ['superadmin', 'admin', 'coordinator', 'tutor']:
            return jsonify({'error': 'Access denied'}), 403
        
        # Define section loaders
        section_loaders = {
            'stats': load_stats_section,
            'recent_activity': load_recent_activity_section,
            'attendance_alerts': load_attendance_alerts_section,
            'pending_tasks': load_pending_tasks_section,
            'upcoming_classes': load_upcoming_classes_section
        }
        
        loader = section_loaders.get(section_name)
        if not loader:
            return jsonify({'error': 'Section not found'}), 404
        
        html_content = loader()
        return jsonify({'html': html_content, 'status': 'success'})
    
    except Exception as e:
        logger.error(f"Error loading dashboard section {section_name}: {str(e)}")
        return jsonify({'error': f'Failed to load {section_name}'}), 500

def load_stats_section():
    """Load statistics section"""
    try:
        # Basic stats that load quickly
        stats = {
            'total_users': User.query.filter_by(is_active=True).count(),
            'total_students': Student.query.filter_by(is_active=True).count(),
            'total_tutors': Tutor.query.filter_by(status='active').count(),
            'todays_classes': Class.query.filter_by(scheduled_date=datetime.now().date()).count()
        }
        
        return f"""
        <div class="row">
            <div class="col-md-3">
                <div class="stats-card">
                    <h3>{stats['total_users']}</h3>
                    <p>Total Users</p>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stats-card">
                    <h3>{stats['total_students']}</h3>
                    <p>Active Students</p>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stats-card">
                    <h3>{stats['total_tutors']}</h3>
                    <p>Active Tutors</p>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stats-card">
                    <h3>{stats['todays_classes']}</h3>
                    <p>Today's Classes</p>
                </div>
            </div>
        </div>
        """
    except Exception as e:
        logger.error(f"Error loading stats section: {str(e)}")
        return '<div class="alert alert-warning">Failed to load statistics</div>'

def load_recent_activity_section():
    """Load recent activity section"""
    try:
        from datetime import timedelta
        week_ago = datetime.now().date() - timedelta(days=7)
        
        recent_students = Student.query.filter(
            Student.created_at >= week_ago
        ).order_by(Student.created_at.desc()).limit(5).all()
        
        html = '<div class="recent-activity">'
        
        if recent_students:
            html += '<h6>Recent Student Registrations</h6><ul class="list-unstyled">'
            for student in recent_students:
                html += f'<li><i class="fas fa-user-plus text-success me-2"></i>{student.full_name}</li>'
            html += '</ul>'
        else:
            html += '<p class="text-muted">No recent activity</p>'
        
        html += '</div>'
        return html
    
    except Exception as e:
        logger.error(f"Error loading recent activity: {str(e)}")
        return '<div class="alert alert-warning">Failed to load recent activity</div>'

def load_attendance_alerts_section():
    """Load attendance alerts section"""
    try:
        today = datetime.now().date()
        
        # Get attendance issues for today
        attendance_issues = Attendance.query.filter(
            Attendance.class_date == today,
            or_(
                Attendance.tutor_present == False,
                Attendance.student_present == False,
                Attendance.tutor_late_minutes > 5,
                Attendance.student_late_minutes > 5
            )
        ).limit(5).all()
        
        html = '<div class="attendance-alerts">'
        
        if attendance_issues:
            html += '<h6>Today\'s Attendance Issues</h6><ul class="list-unstyled">'
            for issue in attendance_issues:
                if not issue.tutor_present:
                    html += f'<li><i class="fas fa-exclamation-circle text-danger me-2"></i>Tutor absent in class {issue.class_session_id}</li>'
                elif issue.tutor_late_minutes > 5:
                    html += f'<li><i class="fas fa-clock text-warning me-2"></i>Tutor {issue.tutor_late_minutes}min late</li>'
            html += '</ul>'
        else:
            html += '<p class="text-success"><i class="fas fa-check-circle me-2"></i>No attendance issues today</p>'
        
        html += '</div>'
        return html
    
    except Exception as e:
        logger.error(f"Error loading attendance alerts: {str(e)}")
        return '<div class="alert alert-warning">Failed to load attendance alerts</div>'

def load_pending_tasks_section():
    """Load pending tasks section"""
    try:
        # Quick count of pending items
        pending_tutors = Tutor.query.filter_by(verification_status='pending').count()
        
        html = '<div class="pending-tasks">'
        
        if pending_tutors > 0:
            html += f'<div class="alert alert-info"><i class="fas fa-tasks me-2"></i>{pending_tutors} tutors pending verification</div>'
        else:
            html += '<p class="text-success"><i class="fas fa-check me-2"></i>No pending tasks</p>'
        
        html += '</div>'
        return html
    
    except Exception as e:
        logger.error(f"Error loading pending tasks: {str(e)}")
        return '<div class="alert alert-warning">Failed to load pending tasks</div>'

def load_upcoming_classes_section():
    """Load upcoming classes section"""
    try:
        from datetime import timedelta
        tomorrow = datetime.now().date() + timedelta(days=1)
        
        upcoming = Class.query.filter(
            Class.scheduled_date == tomorrow,
            Class.status == 'scheduled'
        ).limit(5).all()
        
        html = '<div class="upcoming-classes">'
        
        if upcoming:
            html += '<h6>Tomorrow\'s Classes</h6><ul class="list-unstyled">'
            for class_item in upcoming:
                html += f'<li><i class="fas fa-calendar me-2"></i>{class_item.subject} at {class_item.scheduled_time}</li>'
            html += '</ul>'
        else:
            html += '<p class="text-muted">No classes scheduled for tomorrow</p>'
        
        html += '</div>'
        return html
    
    except Exception as e:
        logger.error(f"Error loading upcoming classes: {str(e)}")
        return '<div class="alert alert-warning">Failed to load upcoming classes</div>'

@bp.route('/dashboard-reload')
@login_required
def dashboard_reload():
    """Force reload dashboard data"""
    try:
        if current_user.role not in ['superadmin', 'admin', 'coordinator', 'tutor']:
            return jsonify({'error': 'Access denied'}), 403
        
        # Clear any cached data (implement based on your caching strategy)
        # cache.clear('dashboard_data')
        
        return jsonify({
            'status': 'success',
            'message': 'Dashboard data refreshed',
            'timestamp': datetime.now().isoformat()
        })
    
    except Exception as e:
        logger.error(f"Error reloading dashboard: {str(e)}")
        return jsonify({'error': 'Failed to reload dashboard'}), 500