# app/routes/system_notifications.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from datetime import datetime
from app import db
from app.models.system_notification import SystemNotification, UserSystemNotification
from app.models.user import User
from app.models.department import Department
from app.forms.notification_forms import (
    SystemNotificationForm, HolidayNotificationForm, EmergencyNotificationForm,
    NotificationSearchForm, BulkNotificationActionForm, QuickAnnouncementForm
)
from app.services.institutional_notification_service import (
    institutional_notification_service, NotificationType, NotificationPriority
)
from app.utils.advanced_permissions import require_permission
from functools import wraps

bp = Blueprint('system_notifications', __name__)

def notification_management_required(f):
    """Decorator to check notification management permissions"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role not in ['superadmin', 'admin', 'coordinator']:
            flash('Access denied. You do not have permission to manage notifications.', 'error')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated_function

# ============ ADMIN NOTIFICATION MANAGEMENT ROUTES ============

@bp.route('/admin/notifications')
@login_required
@notification_management_required
def admin_notifications():
    """Admin notification management dashboard"""
    form = NotificationSearchForm()
    
    # Build query
    query = SystemNotification.query
    
    # Apply filters
    if request.args.get('search'):
        search_term = request.args.get('search')
        search_pattern = f"%{search_term}%"
        query = query.filter(SystemNotification.title.ilike(search_pattern))
    
    if request.args.get('type'):
        query = query.filter(SystemNotification.type == request.args.get('type'))
    
    if request.args.get('priority'):
        query = query.filter(SystemNotification.priority == request.args.get('priority'))
    
    if request.args.get('status'):
        status = request.args.get('status')
        now = datetime.utcnow()
        if status == 'active':
            query = query.filter(
                SystemNotification.is_active == True,
                (SystemNotification.expires_at.is_(None)) | (SystemNotification.expires_at > now)
            )
        elif status == 'expired':
            query = query.filter(
                SystemNotification.expires_at < now
            )
        elif status == 'scheduled':
            query = query.filter(
                SystemNotification.send_immediately == False,
                SystemNotification.sent_at.is_(None)
            )
    
    # Department filter (if coordinator, only show notifications they can manage)
    if current_user.role == 'coordinator' and request.args.get('department'):
        dept_id = int(request.args.get('department'))
        if dept_id != current_user.department_id:
            flash('Access denied. You can only view notifications for your department.', 'error')
            return redirect(url_for('system_notifications.admin_notifications'))
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    notifications = query.order_by(SystemNotification.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    # Get statistics
    stats = {
        'total': SystemNotification.query.count(),
        'active': SystemNotification.query.filter_by(is_active=True).count(),
        'urgent': SystemNotification.query.filter(
            SystemNotification.priority.in_(['urgent', 'critical'])
        ).count(),
        'sent_today': SystemNotification.query.filter(
            SystemNotification.sent_at >= datetime.utcnow().date()
        ).count()
    }
    
    return render_template('admin/notifications/index.html', 
                         notifications=notifications, form=form, stats=stats)

@bp.route('/admin/notifications/create', methods=['GET', 'POST'])
@login_required
@notification_management_required
def create_notification():
    """Create new system notification"""
    form = SystemNotificationForm()
    
    if form.validate_on_submit():
        try:
            # Determine target data based on form
            target_departments = None
            target_roles = None
            target_users = None
            
            if form.target_type.data == 'department':
                target_departments = form.target_departments.data
            elif form.target_type.data == 'role':
                target_roles = form.target_roles.data
            elif form.target_type.data == 'individual':
                target_users = form.target_users.data
            
            # Create notification
            notification = institutional_notification_service.create_system_notification(
                title=form.title.data,
                message=form.message.data,
                created_by=current_user.id,
                notification_type=form.type.data,
                priority=form.priority.data,
                target_type=form.target_type.data,
                target_departments=target_departments,
                target_roles=target_roles,
                target_users=target_users,
                email_enabled=form.email_enabled.data,
                popup_enabled=form.popup_enabled.data,
                include_parents=form.include_parents.data,
                send_immediately=form.send_immediately.data,
                scheduled_for=form.scheduled_for.data,
                expires_at=form.expires_at.data
            )
            
            if form.send_immediately.data:
                flash(f'Notification "{notification.title}" created and sent successfully!', 'success')
            else:
                flash(f'Notification "{notification.title}" created and scheduled!', 'success')
            
            return redirect(url_for('system_notifications.admin_notifications'))
            
        except Exception as e:
            flash(f'Error creating notification: {str(e)}', 'error')
    
    return render_template('admin/notifications/create.html', form=form)

@bp.route('/admin/notifications/quick-announcement', methods=['GET', 'POST'])
@login_required
@notification_management_required
def quick_announcement():
    """Quick announcement form"""
    form = QuickAnnouncementForm()
    
    if form.validate_on_submit():
        try:
            # Determine target based on selection
            target_type = 'all'
            target_roles = None
            target_departments = None
            
            if form.target_type.data == 'students':
                target_type = 'role'
                target_roles = ['student']
            elif form.target_type.data == 'tutors':
                target_type = 'role'
                target_roles = ['tutor']
            elif form.target_type.data == 'my_department' and current_user.department_id:
                target_type = 'department'
                target_departments = [current_user.department_id]
            
            # Create notification
            notification = institutional_notification_service.create_system_notification(
                title=form.title.data,
                message=form.message.data,
                created_by=current_user.id,
                notification_type=NotificationType.GENERAL,
                priority=NotificationPriority.NORMAL,
                target_type=target_type,
                target_roles=target_roles,
                target_departments=target_departments,
                email_enabled=form.include_email.data,
                popup_enabled=form.include_popup.data,
                send_immediately=True
            )
            
            flash(f'Announcement "{notification.title}" sent successfully!', 'success')
            return redirect(url_for('system_notifications.admin_notifications'))
            
        except Exception as e:
            flash(f'Error sending announcement: {str(e)}', 'error')
    
    return render_template('admin/notifications/quick_announcement.html', form=form)

@bp.route('/admin/notifications/holiday', methods=['GET', 'POST'])
@login_required
@notification_management_required
def create_holiday_notification():
    """Create holiday notification"""
    form = HolidayNotificationForm()
    
    if form.validate_on_submit():
        try:
            # Create holiday notification
            notification = institutional_notification_service.create_holiday_notification(
                title=form.title.data,
                message=form.message.data,
                holiday_date=datetime.combine(form.holiday_date.data, datetime.min.time()),
                created_by=current_user.id,
                target_departments=form.target_departments.data if form.target_departments.data else None
            )
            
            flash(f'Holiday notification "{notification.title}" sent successfully!', 'success')
            return redirect(url_for('system_notifications.admin_notifications'))
            
        except Exception as e:
            flash(f'Error creating holiday notification: {str(e)}', 'error')
    
    return render_template('admin/notifications/create_holiday.html', form=form)

@bp.route('/admin/notifications/emergency', methods=['GET', 'POST'])
@login_required
@notification_management_required
def create_emergency_notification():
    """Create emergency notification"""
    form = EmergencyNotificationForm()
    
    if form.validate_on_submit():
        try:
            # Create emergency notification
            notification = institutional_notification_service.create_emergency_notification(
                title=form.title.data,
                message=form.message.data,
                created_by=current_user.id,
                target_type=form.target_type.data,
                target_departments=form.target_departments.data if form.target_departments.data else None
            )
            
            flash(f'Emergency notification "{notification.title}" sent successfully!', 'success')
            return redirect(url_for('system_notifications.admin_notifications'))
            
        except Exception as e:
            flash(f'Error creating emergency notification: {str(e)}', 'error')
    
    return render_template('admin/notifications/create_emergency.html', form=form)

@bp.route('/admin/notifications/<int:notification_id>')
@login_required
@notification_management_required
def view_notification(notification_id):
    """View notification details and analytics"""
    notification = SystemNotification.query.get_or_404(notification_id)
    
    # Check permissions for coordinators
    if current_user.role == 'coordinator':
        if notification.target_type == 'department':
            target_depts = notification.get_target_departments()
            if current_user.department_id not in target_depts:
                flash('Access denied.', 'error')
                return redirect(url_for('system_notifications.admin_notifications'))
    
    # Get analytics
    analytics = institutional_notification_service.get_notification_analytics(notification_id)
    
    return render_template('admin/notifications/view.html', 
                         notification=notification, analytics=analytics)

@bp.route('/admin/notifications/<int:notification_id>/send', methods=['POST'])
@login_required
@notification_management_required
def send_notification(notification_id):
    """Manually send a scheduled notification"""
    notification = SystemNotification.query.get_or_404(notification_id)
    
    # Check permissions
    if current_user.role == 'coordinator' and notification.created_by != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        result = institutional_notification_service.send_notification(notification_id)
        if result:
            return jsonify({'success': True, 'message': 'Notification sent successfully'})
        else:
            return jsonify({'error': 'Failed to send notification'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/admin/notifications/<int:notification_id>/delete', methods=['POST'])
@login_required
@notification_management_required
def delete_notification(notification_id):
    """Delete a notification"""
    notification = SystemNotification.query.get_or_404(notification_id)
    
    # Check permissions
    if current_user.role == 'coordinator' and notification.created_by != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        db.session.delete(notification)
        db.session.commit()
        flash('Notification deleted successfully.', 'success')
    except Exception as e:
        flash(f'Error deleting notification: {str(e)}', 'error')
    
    return redirect(url_for('system_notifications.admin_notifications'))

# ============ USER NOTIFICATION INBOX ROUTES ============

@bp.route('/notifications')
@login_required
def user_notifications():
    """User notification inbox"""
    # Get user's notifications
    page = request.args.get('page', 1, type=int)
    
    notifications_query = UserSystemNotification.query.filter_by(
        user_id=current_user.id
    ).join(SystemNotification).filter(
        SystemNotification.is_active == True
    ).order_by(SystemNotification.created_at.desc())
    
    # Filter by read status
    read_status = request.args.get('read_status')
    if read_status == 'unread':
        notifications_query = notifications_query.filter(UserSystemNotification.is_read == False)
    elif read_status == 'read':
        notifications_query = notifications_query.filter(UserSystemNotification.is_read == True)
    
    # Filter by type
    notification_type = request.args.get('type')
    if notification_type:
        notifications_query = notifications_query.filter(SystemNotification.type == notification_type)
    
    notifications = notifications_query.paginate(page=page, per_page=20, error_out=False)
    
    # Get user's notification statistics
    stats = {
        'total': UserSystemNotification.query.filter_by(user_id=current_user.id).count(),
        'unread': len(institutional_notification_service.get_user_unread_notifications(current_user.id)),
        'urgent': UserSystemNotification.query.filter_by(
            user_id=current_user.id,
            is_read=False
        ).join(SystemNotification).filter(
            SystemNotification.priority.in_(['urgent', 'critical'])
        ).count()
    }
    
    return render_template('notifications/inbox.html', 
                         notifications=notifications, stats=stats)

@bp.route('/notifications/<int:notification_id>')
@login_required
def view_user_notification(notification_id):
    """View specific notification for user"""
    notification = SystemNotification.query.get_or_404(notification_id)
    
    # Get user's notification record
    user_notification = UserSystemNotification.query.filter_by(
        system_notification_id=notification_id,
        user_id=current_user.id
    ).first()
    
    if not user_notification:
        flash('Notification not found.', 'error')
        return redirect(url_for('system_notifications.user_notifications'))
    
    # Mark as read if not already read
    if not user_notification.is_read:
        institutional_notification_service.mark_notification_read(notification_id, current_user.id)
        user_notification = UserSystemNotification.query.filter_by(
            system_notification_id=notification_id,
            user_id=current_user.id
        ).first()  # Refresh the record
    
    return render_template('notifications/detail.html', 
                         notification=notification, user_notification=user_notification)

# ============ API ENDPOINTS ============

@bp.route('/api/notifications/unread-count')
@login_required
def api_unread_count():
    """Get unread notification count for current user"""
    unread_notifications = institutional_notification_service.get_user_unread_notifications(current_user.id)
    return jsonify({'unread_count': len(unread_notifications)})

@bp.route('/api/notifications/popup')
@login_required
def api_popup_notifications():
    """Get notifications that should show popup"""
    popup_notifications = institutional_notification_service.get_user_popup_notifications(current_user.id)
    
    notifications_data = []
    for user_notification in popup_notifications:
        notification = user_notification.system_notification
        notifications_data.append({
            'id': notification.id,
            'title': notification.title,
            'message': notification.message,
            'type': notification.type,
            'priority': notification.priority,
            'created_at': notification.created_at.isoformat(),
            'user_notification_id': user_notification.id
        })
    
    return jsonify({'notifications': notifications_data})

@bp.route('/api/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def api_mark_notification_read(notification_id):
    """Mark notification as read"""
    try:
        success = institutional_notification_service.mark_notification_read(notification_id, current_user.id)
        if success:
            return jsonify({'success': True, 'message': 'Notification marked as read'})
        else:
            return jsonify({'error': 'Error marking notification as read'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/notifications/<int:notification_id>/popup-shown', methods=['POST'])
@login_required
def api_mark_popup_shown(notification_id):
    """Mark popup as shown"""
    try:
        success = institutional_notification_service.mark_popup_shown(notification_id, current_user.id)
        if success:
            return jsonify({'success': True, 'message': 'Popup marked as shown'})
        else:
            return jsonify({'error': 'Error marking popup as shown'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/notifications/<int:notification_id>/dismiss', methods=['POST'])
@login_required
def api_dismiss_notification(notification_id):
    """Dismiss notification"""
    try:
        success = institutional_notification_service.dismiss_notification(notification_id, current_user.id)
        if success:
            return jsonify({'success': True, 'message': 'Notification dismissed'})
        else:
            return jsonify({'error': 'Error dismissing notification'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/admin/notifications/bulk-action', methods=['POST'])
@login_required
@notification_management_required
def bulk_notification_action():
    """Handle bulk actions on notifications"""
    form = BulkNotificationActionForm()
    
    if form.validate_on_submit():
        try:
            action = form.action.data
            notification_ids = [int(x) for x in form.notification_ids.data.split(',') if x.strip()]
            
            if not notification_ids:
                return jsonify({'error': 'No notifications selected'}), 400
            
            success_count = 0
            
            for notification_id in notification_ids:
                notification = SystemNotification.query.get(notification_id)
                if not notification:
                    continue
                
                # Check permissions for coordinators
                if current_user.role == 'coordinator' and notification.created_by != current_user.id:
                    continue
                
                if action == 'activate':
                    notification.is_active = True
                    success_count += 1
                elif action == 'deactivate':
                    notification.is_active = False
                    success_count += 1
                elif action == 'delete':
                    db.session.delete(notification)
                    success_count += 1
            
            db.session.commit()
            
            return jsonify({
                'success': True, 
                'message': f'{action.title()} action completed for {success_count} notifications'
            })
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    return jsonify({'error': 'Invalid form data'}), 400

# ============ TEST ROUTES ============

@bp.route('/admin/notifications/test-create')
@login_required
@require_permission('notification_management')
def test_create_notification():
    """Simple test notification creation interface"""
    return render_template('notifications/test_create.html')

@bp.route('/admin/notifications/api/create-test', methods=['POST'])
@login_required
@require_permission('notification_management')
def api_create_test_notification():
    """API endpoint to create test notification"""
    try:
        title = request.form.get('title', '').strip()
        message = request.form.get('message', '').strip()
        target_type = request.form.get('target_type', 'all')
        priority = request.form.get('priority', 'normal')
        email_enabled = request.form.get('email_enabled') == 'on'
        popup_enabled = request.form.get('popup_enabled') == 'on'
        
        if not title or not message:
            flash('Title and message are required!', 'error')
            return redirect(url_for('system_notifications.test_create_notification'))
        
        # Determine target roles based on target_type
        target_roles = None
        if target_type == 'role':
            # This is a simplified version - you can extend this
            target_roles = ['admin']  # Default to admin for testing
        
        # Create notification
        notification = institutional_notification_service.create_system_notification(
            title=title,
            message=message,
            created_by=current_user.id,
            notification_type='general',
            priority=priority,
            target_type=target_type,
            target_roles=target_roles,
            email_enabled=email_enabled,
            popup_enabled=popup_enabled,
            send_immediately=True
        )
        
        if notification:
            flash(f'Test notification "{title}" sent successfully! Check your email and notification bell.', 'success')
            return redirect(url_for('system_notifications.admin_notifications'))
        else:
            flash('Failed to create test notification.', 'error')
            
    except Exception as e:
        current_app.logger.error(f"Error creating test notification: {str(e)}")
        flash('An error occurred while creating the test notification.', 'error')
    
    return redirect(url_for('system_notifications.test_create_notification'))