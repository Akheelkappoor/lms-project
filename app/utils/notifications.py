"""
Notification utilities for sending alerts to superadmin
"""
from datetime import datetime
from flask import current_app
from app.models.user import User
from app.extensions import db
import json

def send_finance_alert(alert_type, message, data=None):
    """
    Send finance-related alerts to superadmin
    
    Args:
        alert_type: Type of alert (payment_recorded, fee_structure_changed, etc.)
        message: Human-readable message
        data: Additional data dictionary
    """
    try:
        # Find all superadmins
        superadmins = User.query.filter_by(role='superadmin', is_active=True).all()
        
        if not superadmins:
            print("No superadmins found to send finance alert")
            return False
        
        alert_record = {
            'type': alert_type,
            'message': message,
            'data': data or {},
            'timestamp': datetime.now().isoformat(),
            'read': False
        }
        
        # For now, we'll store alerts in a simple way
        # In production, you might want to use a proper notification system
        for admin in superadmins:
            # Store alert in user's notification field or send email
            notifications = getattr(admin, 'notifications', None)
            if notifications:
                try:
                    notifications_list = json.loads(notifications)
                except:
                    notifications_list = []
            else:
                notifications_list = []
            
            notifications_list.append(alert_record)
            
            # Keep only last 100 notifications
            if len(notifications_list) > 100:
                notifications_list = notifications_list[-100:]
            
            # Save notifications back to user
            admin.notifications = json.dumps(notifications_list)
        
        db.session.commit()
        
        # Also log to console for development
        print(f"Finance Alert [{alert_type}]: {message}")
        if data:
            print(f"Alert Data: {data}")
        
        return True
        
    except Exception as e:
        print(f"Error sending finance alert: {e}")
        return False

def send_fee_structure_change_alert(student_name, old_fee, new_fee, changed_by, reason):
    """Send alert when fee structure is changed"""
    return send_finance_alert(
        'fee_structure_changed',
        f'Fee structure changed for {student_name}: ₹{old_fee:,.0f} → ₹{new_fee:,.0f}',
        {
            'student_name': student_name,
            'old_fee': old_fee,
            'new_fee': new_fee,
            'changed_by': changed_by,
            'reason': reason
        }
    )

def send_installment_plan_alert(student_name, action, changed_by, details=None):
    """Send alert when installment plan is created/updated"""
    return send_finance_alert(
        'installment_plan_changed',
        f'Installment plan {action} for {student_name}',
        {
            'student_name': student_name,
            'action': action,
            'changed_by': changed_by,
            'details': details or {}
        }
    )

def send_monthly_fee_status_alert(student_name, old_status, new_status, changed_by):
    """Send alert when monthly fee status is changed"""
    return send_finance_alert(
        'monthly_fee_status_changed',
        f'Monthly fee status changed for {student_name}: {old_status} → {new_status}',
        {
            'student_name': student_name,
            'old_status': old_status,
            'new_status': new_status,
            'changed_by': changed_by
        }
    )

def get_finance_alerts(user_id, limit=20):
    """Get finance alerts for a specific user"""
    try:
        user = User.query.get(user_id)
        if not user or not user.notifications:
            return []
        
        notifications = json.loads(user.notifications)
        
        # Filter for finance alerts
        finance_alerts = [
            alert for alert in notifications 
            if alert.get('type', '').startswith(('payment_', 'fee_', 'installment_', 'monthly_fee_'))
        ]
        
        # Sort by timestamp (newest first)
        finance_alerts.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        return finance_alerts[:limit]
        
    except Exception as e:
        print(f"Error getting finance alerts: {e}")
        return []

def mark_alert_as_read(user_id, alert_timestamp):
    """Mark a specific alert as read"""
    try:
        user = User.query.get(user_id)
        if not user or not user.notifications:
            return False
        
        notifications = json.loads(user.notifications)
        
        for alert in notifications:
            if alert.get('timestamp') == alert_timestamp:
                alert['read'] = True
                break
        
        user.notifications = json.dumps(notifications)
        db.session.commit()
        
        return True
        
    except Exception as e:
        print(f"Error marking alert as read: {e}")
        return False