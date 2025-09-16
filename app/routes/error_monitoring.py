from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from sqlalchemy import func, desc, and_
from app import db
from app.models.error_log import ErrorLog, UserActivityLog, SystemHealthLog
from app.models.user import User
from app.utils.error_tracker import SystemHealthMonitor

bp = Blueprint('error_monitoring', __name__, url_prefix='/admin/errors')

@bp.route('/')
@login_required
def dashboard():
    """Main error monitoring dashboard"""
    if not current_user.has_permission('error_monitoring'):
        flash('Access denied', 'error')
        return redirect(url_for('dashboard.index'))
    
    # Get dashboard statistics
    stats = get_error_statistics()
    recent_errors = get_recent_errors(limit=20)
    system_health = get_system_health_summary()
    
    return render_template('admin/error_monitoring/dashboard.html',
                         stats=stats,
                         recent_errors=recent_errors,
                         system_health=system_health)

@bp.route('/api/live-errors')
@login_required
def live_errors():
    """API endpoint for real-time error feed"""
    if not current_user.has_permission('error_monitoring'):
        if request.headers.get('Accept') == 'application/json':
            return jsonify({'error': 'Access denied'}), 403
        else:
            flash('Access denied', 'error')
            return redirect(url_for('dashboard.index'))
    
    # Get errors from last 5 minutes
    five_minutes_ago = datetime.utcnow() - timedelta(minutes=5)
    
    errors = ErrorLog.query.filter(
        ErrorLog.created_at >= five_minutes_ago
    ).order_by(desc(ErrorLog.created_at)).limit(50).all()
    
    # Return JSON for AJAX requests, HTML for direct access
    if request.headers.get('Accept') == 'application/json' or request.args.get('format') == 'json':
        return jsonify({
            'errors': [error.to_dict() for error in errors],
            'count': len(errors),
            'timestamp': datetime.utcnow().isoformat()
        })
    else:
        # Return HTML template for direct access
        return render_template('admin/error_monitoring/live_errors.html',
                             errors=errors,
                             count=len(errors),
                             timestamp=datetime.utcnow())

@bp.route('/api/critical-count')
@login_required
def critical_count():
    """API endpoint for critical errors count badge"""
    if not current_user.has_permission('error_monitoring'):
        return jsonify({'error': 'Access denied'}), 403
    
    # Get unresolved critical errors from last 24 hours
    last_24h = datetime.utcnow() - timedelta(hours=24)
    
    critical_count = ErrorLog.query.filter(
        ErrorLog.severity == 'critical',
        ErrorLog.status == 'open',
        ErrorLog.created_at >= last_24h
    ).count()
    
    return jsonify({
        'critical_count': critical_count,
        'timestamp': datetime.utcnow().isoformat()
    })

@bp.route('/error/<error_id>')
@login_required
def error_detail(error_id):
    """Detailed view of a specific error"""
    if not current_user.has_permission('error_monitoring'):
        flash('Access denied', 'error')
        return redirect(url_for('dashboard.index'))
    
    error = ErrorLog.query.filter_by(error_id=error_id).first_or_404()
    
    # Get related errors (same type, same user, similar time)
    related_errors = get_related_errors(error)
    
    # Get user's recent activity if user exists
    user_activity = []
    if error.user_id:
        user_activity = UserActivityLog.query.filter(
            UserActivityLog.user_id == error.user_id,
            UserActivityLog.created_at >= error.created_at - timedelta(hours=1),
            UserActivityLog.created_at <= error.created_at + timedelta(minutes=10)
        ).order_by(UserActivityLog.created_at).all()
    
    return render_template('admin/error_monitoring/error_detail.html',
                         error=error,
                         related_errors=related_errors,
                         user_activity=user_activity)

@bp.route('/resolve/<error_id>', methods=['POST'])
@login_required
def resolve_error(error_id):
    """Mark error as resolved"""
    try:
        if not current_user.has_permission('error_monitoring'):
            return jsonify({'error': 'Access denied'}), 403
        
        error = ErrorLog.query.filter_by(error_id=error_id).first_or_404()
        
        # Handle both JSON and form data
        if request.content_type == 'application/json':
            resolution = request.json.get('resolution', '') if request.json else ''
        else:
            resolution = request.form.get('resolution', '')
        
        error.mark_resolved(resolution, current_user.id)
        
        return jsonify({
            'success': True,
            'message': 'Error marked as resolved',
            'resolved_at': error.resolved_at.isoformat() if error.resolved_at else None
        })
        
    except Exception as e:
        current_app.logger.error(f"Error resolving error {error_id}: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Failed to resolve error: {str(e)}'
        }), 500

@bp.route('/user/<int:user_id>/errors')
@login_required
def user_errors(user_id):
    """View all errors for a specific user"""
    if not current_user.has_permission('error_monitoring'):
        flash('Access denied', 'error')
        return redirect(url_for('dashboard.index'))
    
    user = User.query.get_or_404(user_id)
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = 25
    
    errors = ErrorLog.query.filter_by(user_id=user_id).order_by(
        desc(ErrorLog.created_at)
    ).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Get user statistics
    user_stats = get_user_error_statistics(user_id)
    
    return render_template('admin/error_monitoring/user_errors.html',
                         user=user,
                         errors=errors,
                         user_stats=user_stats)

@bp.route('/search')
@login_required
def search_errors():
    """Search and filter errors"""
    if not current_user.has_permission('error_monitoring'):
        flash('Access denied', 'error')
        return redirect(url_for('dashboard.index'))
    
    # Get search parameters
    query = request.args.get('q', '')
    error_type = request.args.get('type', '')
    severity = request.args.get('severity', '')
    category = request.args.get('category', '')
    status = request.args.get('status', '')
    user_role = request.args.get('user_role', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    # Build query
    filters = []
    
    if query:
        filters.append(ErrorLog.error_message.contains(query))
    
    if error_type:
        filters.append(ErrorLog.error_type == error_type)
    
    if severity:
        filters.append(ErrorLog.severity == severity)
    
    if category:
        filters.append(ErrorLog.error_category == category)
    
    if status:
        filters.append(ErrorLog.status == status)
    
    if user_role:
        filters.append(ErrorLog.user_role == user_role)
    
    if date_from:
        try:
            date_from_dt = datetime.strptime(date_from, '%Y-%m-%d')
            filters.append(ErrorLog.created_at >= date_from_dt)
        except:
            pass
    
    if date_to:
        try:
            date_to_dt = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
            filters.append(ErrorLog.created_at < date_to_dt)
        except:
            pass
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = 25
    
    if filters:
        errors = ErrorLog.query.filter(and_(*filters)).order_by(
            desc(ErrorLog.created_at)
        ).paginate(
            page=page, per_page=per_page, error_out=False
        )
    else:
        errors = ErrorLog.query.order_by(
            desc(ErrorLog.created_at)
        ).paginate(
            page=page, per_page=per_page, error_out=False
        )
    
    # Get filter options
    filter_options = get_filter_options()
    
    return render_template('admin/error_monitoring/search.html',
                         errors=errors,
                         filter_options=filter_options,
                         current_filters={
                             'q': query,
                             'type': error_type,
                             'severity': severity,
                             'category': category,
                             'status': status,
                             'user_role': user_role,
                             'date_from': date_from,
                             'date_to': date_to
                         })

@bp.route('/analytics')
@login_required
def analytics():
    """Error analytics and trends"""
    if not current_user.has_permission('error_monitoring'):
        flash('Access denied', 'error')
        return redirect(url_for('dashboard.index'))
    
    # Get time range
    days = request.args.get('days', 30, type=int)
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Error trends over time
    error_trends = get_error_trends(start_date, days)
    
    # Top error types
    top_error_types = get_top_error_types(start_date)
    
    # User error statistics
    user_error_stats = get_user_error_breakdown(start_date)
    
    # System performance correlation
    performance_data = get_performance_correlation(start_date)
    
    return render_template('admin/error_monitoring/analytics.html',
                         error_trends=error_trends,
                         top_error_types=top_error_types,
                         user_error_stats=user_error_stats,
                         performance_data=performance_data,
                         days=days)

@bp.route('/system-health')
@login_required
def system_health():
    """System health monitoring"""
    if not current_user.has_permission('error_monitoring'):
        flash('Access denied', 'error')
        return redirect(url_for('dashboard.index'))
    
    # Get recent health metrics
    hours = request.args.get('hours', 24, type=int)
    start_time = datetime.utcnow() - timedelta(hours=hours)
    
    health_metrics = SystemHealthLog.query.filter(
        SystemHealthLog.created_at >= start_time
    ).order_by(SystemHealthLog.created_at).all()
    
    # Current system status
    try:
        current_status = SystemHealthMonitor.record_health_metrics()
        if hasattr(current_status, 'to_dict'):
            current_status = current_status.to_dict()
    except:
        current_status = None
    
    return render_template('admin/error_monitoring/system_health.html',
                         health_metrics=health_metrics,
                         current_status=current_status,
                         hours=hours)

@bp.route('/export')
@login_required
def export_errors():
    """Export error data"""
    if not current_user.has_permission('error_monitoring'):
        return jsonify({'error': 'Access denied'}), 403
    
    # Get parameters
    days = request.args.get('days', 7, type=int)
    format_type = request.args.get('format', 'csv')
    
    start_date = datetime.utcnow() - timedelta(days=days)
    
    errors = ErrorLog.query.filter(
        ErrorLog.created_at >= start_date
    ).order_by(desc(ErrorLog.created_at)).all()
    
    if format_type == 'json':
        return jsonify({
            'errors': [error.to_dict() for error in errors],
            'exported_at': datetime.utcnow().isoformat(),
            'total_count': len(errors)
        })
    
    # CSV export (you can implement this based on your needs)
    # For now, return JSON
    return jsonify({
        'message': 'CSV export not implemented yet',
        'available_formats': ['json']
    })

# Helper functions
def get_error_statistics():
    """Get dashboard statistics"""
    now = datetime.utcnow()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    
    stats = {
        'today': ErrorLog.query.filter(ErrorLog.created_at >= today).count(),
        'this_week': ErrorLog.query.filter(ErrorLog.created_at >= week_ago).count(),
        'this_month': ErrorLog.query.filter(ErrorLog.created_at >= month_ago).count(),
        'critical_today': ErrorLog.query.filter(
            ErrorLog.created_at >= today,
            ErrorLog.severity == 'critical'
        ).count(),
        'unresolved': ErrorLog.query.filter(ErrorLog.status == 'open').count(),
        'by_severity': dict(db.session.query(
            ErrorLog.severity, func.count(ErrorLog.id)
        ).filter(ErrorLog.created_at >= week_ago).group_by(ErrorLog.severity).all()),
        'by_category': dict(db.session.query(
            ErrorLog.error_category, func.count(ErrorLog.id)
        ).filter(ErrorLog.created_at >= week_ago).group_by(ErrorLog.error_category).all())
    }
    
    return stats

def get_recent_errors(limit=20):
    """Get recent errors for dashboard"""
    return ErrorLog.query.order_by(desc(ErrorLog.created_at)).limit(limit).all()

def get_system_health_summary():
    """Get current system health summary"""
    latest_health = SystemHealthLog.query.order_by(desc(SystemHealthLog.created_at)).first()
    
    if latest_health:
        return latest_health.to_dict()
    
    return {
        'overall_health': 'unknown',
        'cpu_usage': 0,
        'memory_usage': 0,
        'error_rate': 0,
        'created_at': datetime.utcnow().isoformat()
    }

def get_related_errors(error):
    """Get errors related to the given error"""
    one_hour_before = error.created_at - timedelta(hours=1)
    one_hour_after = error.created_at + timedelta(hours=1)
    
    return ErrorLog.query.filter(
        and_(
            ErrorLog.id != error.id,
            ErrorLog.created_at.between(one_hour_before, one_hour_after),
            db.or_(
                ErrorLog.error_type == error.error_type,
                ErrorLog.user_id == error.user_id,
                ErrorLog.ip_address == error.ip_address
            )
        )
    ).order_by(desc(ErrorLog.created_at)).limit(10).all()

def get_user_error_statistics(user_id):
    """Get error statistics for a specific user"""
    week_ago = datetime.utcnow() - timedelta(days=7)
    month_ago = datetime.utcnow() - timedelta(days=30)
    
    return {
        'total_errors': ErrorLog.query.filter_by(user_id=user_id).count(),
        'this_week': ErrorLog.query.filter(
            ErrorLog.user_id == user_id,
            ErrorLog.created_at >= week_ago
        ).count(),
        'this_month': ErrorLog.query.filter(
            ErrorLog.user_id == user_id,
            ErrorLog.created_at >= month_ago
        ).count(),
        'by_severity': dict(db.session.query(
            ErrorLog.severity, func.count(ErrorLog.id)
        ).filter(
            ErrorLog.user_id == user_id,
            ErrorLog.created_at >= month_ago
        ).group_by(ErrorLog.severity).all()),
        'by_type': dict(db.session.query(
            ErrorLog.error_type, func.count(ErrorLog.id)
        ).filter(
            ErrorLog.user_id == user_id,
            ErrorLog.created_at >= month_ago
        ).group_by(ErrorLog.error_type).all())
    }

def get_filter_options():
    """Get available filter options"""
    return {
        'error_types': [r[0] for r in db.session.query(ErrorLog.error_type.distinct()).all()],
        'severities': ['low', 'medium', 'high', 'critical'],
        'categories': [r[0] for r in db.session.query(ErrorLog.error_category.distinct()).all()],
        'statuses': ['open', 'investigating', 'resolved', 'ignored'],
        'user_roles': [r[0] for r in db.session.query(ErrorLog.user_role.distinct()).all()]
    }

def get_error_trends(start_date, days):
    """Get error trends over time"""
    # This would return data for charting
    # Implementation depends on your charting library
    return {}

def get_top_error_types(start_date):
    """Get most common error types"""
    return db.session.query(
        ErrorLog.error_type,
        ErrorLog.error_message,
        func.count(ErrorLog.id).label('count')
    ).filter(
        ErrorLog.created_at >= start_date
    ).group_by(
        ErrorLog.error_type,
        ErrorLog.error_message
    ).order_by(
        desc(func.count(ErrorLog.id))
    ).limit(10).all()

def get_user_error_breakdown(start_date):
    """Get error breakdown by user role"""
    return db.session.query(
        ErrorLog.user_role,
        func.count(ErrorLog.id).label('count')
    ).filter(
        ErrorLog.created_at >= start_date
    ).group_by(
        ErrorLog.user_role
    ).all()

def get_performance_correlation(start_date):
    """Get performance correlation data"""
    # This would analyze correlation between system performance and error rates
    return {}