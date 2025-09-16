from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from sqlalchemy import desc
from app import db

bp = Blueprint('error_monitoring', __name__, url_prefix='/admin/errors')

@bp.route('/')
@login_required
def dashboard():
    """Simple error monitoring dashboard"""
    # Check basic permission (admin, superadmin, coordinator)
    if current_user.role not in ['superadmin', 'admin', 'coordinator']:
        flash('Access denied', 'error')
        return redirect(url_for('dashboard.index'))
    
    try:
        from app.models.error_log import ErrorLog
        
        # Get basic statistics
        total_errors = ErrorLog.query.count()
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_errors = ErrorLog.query.filter(ErrorLog.created_at >= today).count()
        
        # Get recent errors
        recent_errors = ErrorLog.query.order_by(desc(ErrorLog.created_at)).limit(20).all()
        
        # Basic stats
        stats = {
            'total_errors': total_errors,
            'today_errors': today_errors,
            'recent_count': len(recent_errors)
        }
        
        return render_template('admin/simple_error_dashboard.html', 
                             stats=stats, 
                             recent_errors=recent_errors)
    
    except Exception as e:
        flash(f'Error loading dashboard: {str(e)}', 'error')
        return redirect(url_for('dashboard.index'))

@bp.route('/api/critical-count')
@login_required
def critical_count():
    """API endpoint for critical errors count"""
    if current_user.role not in ['superadmin', 'admin', 'coordinator']:
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        from app.models.error_log import ErrorLog
        
        # Get critical errors from last 24 hours
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
    
    except Exception as e:
        return jsonify({
            'error': str(e),
            'critical_count': 0
        })

@bp.route('/search')
@login_required
def search():
    """Simple error search"""
    if current_user.role not in ['superadmin', 'admin', 'coordinator']:
        flash('Access denied', 'error')
        return redirect(url_for('dashboard.index'))
    
    try:
        from app.models.error_log import ErrorLog
        from app.models.user import User
        
        # Get search parameters
        query = request.args.get('q', '')
        user_id = request.args.get('user_id', '')
        
        errors = ErrorLog.query
        
        if query:
            errors = errors.filter(ErrorLog.error_message.contains(query))
        
        if user_id:
            errors = errors.filter(ErrorLog.user_id == user_id)
        
        errors = errors.order_by(desc(ErrorLog.created_at)).limit(50).all()
        
        # Get all users for search dropdown
        users = User.query.order_by(User.full_name).all()
        
        return render_template('admin/simple_error_search.html', 
                             errors=errors, 
                             users=users,
                             query=query,
                             selected_user_id=user_id)
    
    except Exception as e:
        flash(f'Error performing search: {str(e)}', 'error')
        return redirect(url_for('error_monitoring.dashboard'))