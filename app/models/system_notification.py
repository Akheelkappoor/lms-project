# app/models/system_notification.py

from datetime import datetime
from app import db
import json

class SystemNotification(db.Model):
    __tablename__ = 'system_notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    
    # Notification categorization
    type = db.Column(db.String(50), nullable=False, default='general')  # holiday, emergency, academic, administrative, general
    priority = db.Column(db.String(20), nullable=False, default='normal')  # normal, high, urgent, critical
    
    # Targeting system
    target_type = db.Column(db.String(20), nullable=False, default='all')  # all, department, role, individual
    target_departments = db.Column(db.Text)  # JSON list of department IDs
    target_roles = db.Column(db.Text)  # JSON list of roles (tutor, student, coordinator, etc.)
    target_users = db.Column(db.Text)  # JSON list of specific user IDs
    
    # Delivery settings
    email_enabled = db.Column(db.Boolean, default=True)
    popup_enabled = db.Column(db.Boolean, default=False)  # For urgent notifications
    include_parents = db.Column(db.Boolean, default=False)  # Include student parents in emails
    
    # Status and timing
    is_active = db.Column(db.Boolean, default=True)
    send_immediately = db.Column(db.Boolean, default=True)
    scheduled_for = db.Column(db.DateTime)  # For scheduled notifications
    expires_at = db.Column(db.DateTime)
    
    # Tracking
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sent_at = db.Column(db.DateTime)
    email_sent_count = db.Column(db.Integer, default=0)
    popup_delivered_count = db.Column(db.Integer, default=0)
    
    # Delivery status tracking (JSON)
    delivery_status = db.Column(db.Text)  # JSON tracking delivery per user
    
    # Relationships
    author = db.relationship('User', foreign_keys=[created_by], backref='authored_system_notifications')
    user_notifications = db.relationship('UserSystemNotification', backref='system_notification', lazy='dynamic', cascade='all, delete-orphan')
    
    def __init__(self, **kwargs):
        super(SystemNotification, self).__init__(**kwargs)
        if self.target_departments is None:
            self.target_departments = '[]'
        if self.target_roles is None:
            self.target_roles = '[]'
        if self.target_users is None:
            self.target_users = '[]'
        if self.delivery_status is None:
            self.delivery_status = '{}'
    
    def get_target_departments(self):
        """Get target departments as list"""
        if self.target_departments:
            try:
                return json.loads(self.target_departments)
            except:
                return []
        return []
    
    def set_target_departments(self, departments):
        """Set target departments from list"""
        self.target_departments = json.dumps(departments if departments else [])
    
    def get_target_roles(self):
        """Get target roles as list"""
        if self.target_roles:
            try:
                return json.loads(self.target_roles)
            except:
                return []
        return []
    
    def set_target_roles(self, roles):
        """Set target roles from list"""
        self.target_roles = json.dumps(roles if roles else [])
    
    def get_target_users(self):
        """Get target users as list"""
        if self.target_users:
            try:
                return json.loads(self.target_users)
            except:
                return []
        return []
    
    def set_target_users(self, users):
        """Set target users from list"""
        self.target_users = json.dumps(users if users else [])
    
    def get_delivery_status(self):
        """Get delivery status as dict"""
        if self.delivery_status:
            try:
                return json.loads(self.delivery_status)
            except:
                return {}
        return {}
    
    def set_delivery_status(self, status_dict):
        """Set delivery status from dict"""
        self.delivery_status = json.dumps(status_dict if status_dict else {})
    
    def is_urgent(self):
        """Check if notification is urgent"""
        return self.priority in ['urgent', 'critical']
    
    def is_expired(self):
        """Check if notification has expired"""
        if self.expires_at:
            return datetime.utcnow() > self.expires_at
        return False
    
    def should_show_popup(self):
        """Check if notification should show popup"""
        return self.popup_enabled and self.is_urgent() and not self.is_expired()
    
    def can_be_sent(self):
        """Check if notification can be sent"""
        if not self.is_active or self.is_expired():
            return False
        
        if self.send_immediately:
            return True
        
        if self.scheduled_for:
            return datetime.utcnow() >= self.scheduled_for
        
        return False
    
    def get_target_user_ids(self):
        """Get all target user IDs based on targeting criteria"""
        from app.models.user import User
        from app.models.department import Department
        
        target_user_ids = set()
        
        if self.target_type == 'all':
            # All active users
            users = User.query.filter_by(is_active=True).all()
            target_user_ids.update([u.id for u in users])
            
        elif self.target_type == 'department':
            # Users in specific departments
            dept_ids = self.get_target_departments()
            if dept_ids:
                users = User.query.filter(
                    User.department_id.in_(dept_ids),
                    User.is_active == True
                ).all()
                target_user_ids.update([u.id for u in users])
                
        elif self.target_type == 'role':
            # Users with specific roles
            roles = self.get_target_roles()
            if roles:
                users = User.query.filter(
                    User.role.in_(roles),
                    User.is_active == True
                ).all()
                target_user_ids.update([u.id for u in users])
                
        elif self.target_type == 'individual':
            # Specific users
            user_ids = self.get_target_users()
            target_user_ids.update(user_ids)
        
        return list(target_user_ids)
    
    def mark_as_sent(self):
        """Mark notification as sent"""
        self.sent_at = datetime.utcnow()
        db.session.commit()
    
    def update_delivery_count(self, email_sent=0, popup_delivered=0):
        """Update delivery counts"""
        if email_sent:
            self.email_sent_count = (self.email_sent_count or 0) + email_sent
        if popup_delivered:
            self.popup_delivered_count = (self.popup_delivered_count or 0) + popup_delivered
        db.session.commit()
    
    def get_delivery_stats(self):
        """Get delivery statistics"""
        target_count = len(self.get_target_user_ids())
        user_notifications = self.user_notifications.all()
        
        delivered_count = len([un for un in user_notifications if un.delivered_at])
        read_count = len([un for un in user_notifications if un.read_at])
        
        return {
            'target_count': target_count,
            'delivered_count': delivered_count,
            'read_count': read_count,
            'email_sent_count': self.email_sent_count or 0,
            'popup_delivered_count': self.popup_delivered_count or 0,
            'delivery_rate': (delivered_count / target_count * 100) if target_count > 0 else 0,
            'read_rate': (read_count / target_count * 100) if target_count > 0 else 0
        }
    
    def to_dict(self):
        """Convert notification to dictionary"""
        return {
            'id': self.id,
            'title': self.title,
            'message': self.message,
            'type': self.type,
            'priority': self.priority,
            'target_type': self.target_type,
            'email_enabled': self.email_enabled,
            'popup_enabled': self.popup_enabled,
            'include_parents': self.include_parents,
            'is_active': self.is_active,
            'send_immediately': self.send_immediately,
            'scheduled_for': self.scheduled_for.isoformat() if self.scheduled_for else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'created_at': self.created_at.isoformat(),
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'author': self.author.full_name if self.author else '',
            'delivery_stats': self.get_delivery_stats(),
            'is_urgent': self.is_urgent(),
            'should_show_popup': self.should_show_popup()
        }
    
    def __repr__(self):
        return f'<SystemNotification {self.id}: {self.title}>'


class UserSystemNotification(db.Model):
    """Individual user delivery tracking for system notifications"""
    __tablename__ = 'user_system_notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    system_notification_id = db.Column(db.Integer, db.ForeignKey('system_notifications.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Delivery tracking
    delivered_at = db.Column(db.DateTime, default=datetime.utcnow)
    read_at = db.Column(db.DateTime)
    email_sent = db.Column(db.Boolean, default=False)
    popup_shown = db.Column(db.Boolean, default=False)
    popup_shown_at = db.Column(db.DateTime)
    
    # Status flags
    is_read = db.Column(db.Boolean, default=False)
    is_dismissed = db.Column(db.Boolean, default=False)
    dismissed_at = db.Column(db.DateTime)
    
    # Relationships
    user = db.relationship('User', foreign_keys=[user_id])
    
    # Unique constraint to prevent duplicate records
    __table_args__ = (db.UniqueConstraint('system_notification_id', 'user_id', name='unique_system_notification_user'),)
    
    def mark_as_read(self):
        """Mark notification as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = datetime.utcnow()
            db.session.commit()
    
    def mark_popup_shown(self):
        """Mark popup as shown"""
        if not self.popup_shown:
            self.popup_shown = True
            self.popup_shown_at = datetime.utcnow()
            db.session.commit()
    
    def dismiss(self):
        """Dismiss notification"""
        self.is_dismissed = True
        self.dismissed_at = datetime.utcnow()
        # Also mark as read when dismissed
        if not self.is_read:
            self.is_read = True
            self.read_at = datetime.utcnow()
        db.session.commit()
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'system_notification_id': self.system_notification_id,
            'user_id': self.user_id,
            'delivered_at': self.delivered_at.isoformat() if self.delivered_at else None,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'email_sent': self.email_sent,
            'popup_shown': self.popup_shown,
            'popup_shown_at': self.popup_shown_at.isoformat() if self.popup_shown_at else None,
            'is_read': self.is_read,
            'is_dismissed': self.is_dismissed,
            'dismissed_at': self.dismissed_at.isoformat() if self.dismissed_at else None,
            'notification': self.system_notification.to_dict() if self.system_notification else None
        }
    
    def __repr__(self):
        return f'<UserSystemNotification {self.id}: Notification {self.system_notification_id} -> User {self.user_id}>'