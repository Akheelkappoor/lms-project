# app/models/notice.py

from datetime import datetime
from app import db
import json

class Notice(db.Model):
    __tablename__ = 'notices'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    
    # Categorization
    category = db.Column(db.String(50), nullable=False, default='general')  # academic, administrative, emergency, celebration
    priority = db.Column(db.String(20), nullable=False, default='normal')  # normal, high, urgent
    
    # Targeting
    target_type = db.Column(db.String(20), nullable=False, default='all')  # all, department, individual
    target_departments = db.Column(db.Text)  # JSON list of department IDs
    target_users = db.Column(db.Text)  # JSON list of user IDs
    
    # Settings
    requires_acknowledgment = db.Column(db.Boolean, default=False)
    is_published = db.Column(db.Boolean, default=False)
    publish_date = db.Column(db.DateTime)
    expiry_date = db.Column(db.DateTime)
    
    # Metadata
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    author = db.relationship('User', foreign_keys=[created_by], backref='authored_notices')
    attachments = db.relationship('NoticeAttachment', backref='notice', lazy='dynamic', cascade='all, delete-orphan')
    distributions = db.relationship('NoticeDistribution', backref='notice', lazy='dynamic', cascade='all, delete-orphan')
    
    def __init__(self, **kwargs):
        super(Notice, self).__init__(**kwargs)
        if self.target_departments is None:
            self.target_departments = '[]'
        if self.target_users is None:
            self.target_users = '[]'
    
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
    
    def is_urgent(self):
        """Check if notice is urgent"""
        return self.priority == 'urgent' or self.category == 'emergency'
    
    def is_active(self):
        """Check if notice is currently active"""
        now = datetime.utcnow()
        if not self.is_published:
            return False
        if self.publish_date and self.publish_date > now:
            return False
        if self.expiry_date and self.expiry_date < now:
            return False
        return True
    
    def get_delivery_stats(self):
        """Get delivery statistics"""
        distributions = self.distributions.all()
        total = len(distributions)
        delivered = len([d for d in distributions if d.delivered_at])
        read = len([d for d in distributions if d.is_read])
        acknowledged = len([d for d in distributions if d.is_acknowledged])
        
        return {
            'total': total,
            'delivered': delivered,
            'read': read,
            'acknowledged': acknowledged,
            'delivery_rate': (delivered / total * 100) if total > 0 else 0,
            'read_rate': (read / total * 100) if total > 0 else 0,
            'acknowledgment_rate': (acknowledged / total * 100) if total > 0 else 0
        }
    
    def can_be_viewed_by(self, user):
        """Check if user can view this notice"""
        if not self.is_active():
            return False
        
        # Check if user is in target audience
        if self.target_type == 'all':
            return True
        elif self.target_type == 'department':
            target_depts = self.get_target_departments()
            return user.department_id in target_depts if user.department_id else False
        elif self.target_type == 'individual':
            target_users = self.get_target_users()
            return user.id in target_users
        
        return False
    
    def to_dict(self):
        """Convert notice to dictionary"""
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'category': self.category,
            'priority': self.priority,
            'target_type': self.target_type,
            'requires_acknowledgment': self.requires_acknowledgment,
            'is_published': self.is_published,
            'publish_date': self.publish_date.isoformat() if self.publish_date else None,
            'expiry_date': self.expiry_date.isoformat() if self.expiry_date else None,
            'created_at': self.created_at.isoformat(),
            'author': self.author.full_name if self.author else '',
            'attachments_count': self.attachments.count(),
            'delivery_stats': self.get_delivery_stats()
        }
    
    def __repr__(self):
        return f'<Notice {self.id}: {self.title}>'


class NoticeAttachment(db.Model):
    __tablename__ = 'notice_attachments'
    
    id = db.Column(db.Integer, primary_key=True)
    notice_id = db.Column(db.Integer, db.ForeignKey('notices.id'), nullable=False)
    
    # File information
    filename = db.Column(db.String(255), nullable=False)  # Stored filename
    original_filename = db.Column(db.String(255), nullable=False)  # Original upload name
    file_size = db.Column(db.Integer)  # File size in bytes
    file_type = db.Column(db.String(50))  # MIME type
    
    # Storage information
    s3_key = db.Column(db.String(500))  # S3 object key
    s3_bucket = db.Column(db.String(100))  # S3 bucket name
    
    # Metadata
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Relationships
    uploader = db.relationship('User', foreign_keys=[uploaded_by])
    
    def get_file_size_formatted(self):
        """Get formatted file size"""
        if not self.file_size:
            return 'Unknown'
        
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
    
    def is_image(self):
        """Check if file is an image"""
        image_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
        return self.file_type in image_types
    
    def is_document(self):
        """Check if file is a document"""
        doc_types = ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
        return self.file_type in doc_types
    
    def to_dict(self):
        """Convert attachment to dictionary"""
        return {
            'id': self.id,
            'filename': self.filename,
            'original_filename': self.original_filename,
            'file_size': self.file_size,
            'file_size_formatted': self.get_file_size_formatted(),
            'file_type': self.file_type,
            'uploaded_at': self.uploaded_at.isoformat(),
            'uploader': self.uploader.full_name if self.uploader else '',
            'is_image': self.is_image(),
            'is_document': self.is_document()
        }
    
    def __repr__(self):
        return f'<NoticeAttachment {self.id}: {self.original_filename}>'


class NoticeDistribution(db.Model):
    __tablename__ = 'notice_distributions'
    
    id = db.Column(db.Integer, primary_key=True)
    notice_id = db.Column(db.Integer, db.ForeignKey('notices.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Delivery tracking
    delivered_at = db.Column(db.DateTime, default=datetime.utcnow)
    read_at = db.Column(db.DateTime)
    acknowledged_at = db.Column(db.DateTime)
    
    # Status flags
    is_read = db.Column(db.Boolean, default=False)
    is_acknowledged = db.Column(db.Boolean, default=False)
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', foreign_keys=[user_id])
    
    # Unique constraint to prevent duplicate distributions
    __table_args__ = (db.UniqueConstraint('notice_id', 'user_id', name='unique_notice_user'),)
    
    def mark_as_read(self):
        """Mark notice as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = datetime.utcnow()
            db.session.commit()
    
    def mark_as_acknowledged(self):
        """Mark notice as acknowledged"""
        if not self.is_acknowledged:
            self.is_acknowledged = True
            self.acknowledged_at = datetime.utcnow()
            # Also mark as read
            if not self.is_read:
                self.is_read = True
                self.read_at = datetime.utcnow()
            db.session.commit()
    
    def to_dict(self):
        """Convert distribution to dictionary"""
        return {
            'id': self.id,
            'notice_id': self.notice_id,
            'user_id': self.user_id,
            'user_name': self.user.full_name if self.user else '',
            'delivered_at': self.delivered_at.isoformat() if self.delivered_at else None,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'acknowledged_at': self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            'is_read': self.is_read,
            'is_acknowledged': self.is_acknowledged
        }
    
    def __repr__(self):
        return f'<NoticeDistribution {self.id}: Notice {self.notice_id} -> User {self.user_id}>'