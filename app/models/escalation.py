from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from app import db
import json

class Escalation(db.Model):
    __tablename__ = 'escalations'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Basic Information
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False)  # technical, academic, payment, scheduling, behavioral
    priority = db.Column(db.String(20), nullable=False, default='medium')  # high, medium, low
    status = db.Column(db.String(20), nullable=False, default='open')  # open, assigned, in_progress, resolved, closed
    
    # People Involved
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'))
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'))
    
    # Related Records (JSON to store references)
    related_records = db.Column(db.Text)  # JSON: {student_id: 123, tutor_id: 456, class_id: 789}
    
    # Resolution
    resolution = db.Column(db.Text)
    resolution_date = db.Column(db.DateTime)
    resolved_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Tracking
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    due_date = db.Column(db.DateTime)  # Auto-calculated based on priority
    
    # Additional Data (JSON)
    additional_data = db.Column(db.Text)  # Attachments, comments, etc.
    
    # Relationships
    creator = db.relationship('User', foreign_keys=[created_by], backref='created_escalations')
    assignee = db.relationship('User', foreign_keys=[assigned_to], backref='assigned_escalations')
    resolver = db.relationship('User', foreign_keys=[resolved_by], backref='resolved_escalations')
    department = db.relationship('Department', backref='escalations')
    
    def __repr__(self):
        return f'<Escalation {self.id}: {self.title}>'
    
    @staticmethod
    def get_categories():
        """Get available escalation categories"""
        return [
            ('technical', 'Technical Issues'),
            ('academic', 'Academic Concerns'),
            ('payment', 'Payment Disputes'),
            ('scheduling', 'Scheduling Conflicts'),
            ('behavioral', 'Behavioral Issues')
        ]
    
    @staticmethod
    def get_priorities():
        """Get available priority levels"""
        return [
            ('high', 'High (< 2 hours)'),
            ('medium', 'Medium (< 24 hours)'),
            ('low', 'Low (< 72 hours)')
        ]
    
    @staticmethod
    def get_statuses():
        """Get available status options"""
        return [
            ('open', 'Open'),
            ('assigned', 'Assigned'),
            ('in_progress', 'In Progress'),
            ('resolved', 'Resolved'),
            ('closed', 'Closed')
        ]
    
    def set_related_records(self, data):
        """Set related records as JSON"""
        self.related_records = json.dumps(data) if data else None
    
    def get_related_records(self):
        """Get related records from JSON"""
        if self.related_records:
            try:
                return json.loads(self.related_records)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}
    
    def set_additional_data(self, data):
        """Set additional data as JSON"""
        self.additional_data = json.dumps(data) if data else None
    
    def get_additional_data(self):
        """Get additional data from JSON"""
        if self.additional_data:
            try:
                return json.loads(self.additional_data)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}
    
    def add_comment(self, user_id, comment):
        """Add a comment to the escalation"""
        data = self.get_additional_data()
        if 'comments' not in data:
            data['comments'] = []
        
        data['comments'].append({
            'user_id': user_id,
            'comment': comment,
            'timestamp': datetime.utcnow().isoformat()
        })
        
        self.set_additional_data(data)
        self.updated_at = datetime.utcnow()
    
    def get_comments(self):
        """Get all comments"""
        data = self.get_additional_data()
        return data.get('comments', [])
    
    def calculate_due_date(self):
        """Calculate due date based on priority"""
        from datetime import timedelta
        
        hours_map = {
            'high': 2,
            'medium': 24,
            'low': 72
        }
        
        hours = hours_map.get(self.priority, 24)
        self.due_date = datetime.utcnow() + timedelta(hours=hours)
    
    def is_overdue(self):
        """Check if escalation is overdue"""
        if not self.due_date or self.status in ['resolved', 'closed']:
            return False
        return datetime.utcnow() > self.due_date
    
    def assign_to_user(self, user_id, assigned_by=None):
        """Assign escalation to a user"""
        self.assigned_to = user_id
        self.status = 'assigned'
        self.updated_at = datetime.utcnow()
        
        # Add assignment comment
        if assigned_by:
            self.add_comment(assigned_by, f"Escalation assigned to user ID {user_id}")
    
    def resolve(self, resolution, resolved_by):
        """Mark escalation as resolved"""
        self.resolution = resolution
        self.resolved_by = resolved_by
        self.resolution_date = datetime.utcnow()
        self.status = 'resolved'
        self.updated_at = datetime.utcnow()
        
        # Add resolution comment
        self.add_comment(resolved_by, f"Escalation resolved: {resolution}")
    
    def close(self, closed_by):
        """Close the escalation"""
        self.status = 'closed'
        self.updated_at = datetime.utcnow()
        self.add_comment(closed_by, "Escalation closed")
    
    @classmethod
    def get_for_user(cls, user_id, department_id=None):
        """Get escalations for a specific user"""
        query = cls.query.filter_by(assigned_to=user_id)
        
        if department_id:
            query = query.filter_by(department_id=department_id)
        
        return query.order_by(cls.created_at.desc()).all()
    
    @classmethod
    def get_for_department(cls, department_id):
        """Get escalations for a department"""
        return cls.query.filter_by(department_id=department_id).order_by(cls.created_at.desc()).all()
    
    @classmethod
    def get_overdue(cls):
        """Get all overdue escalations"""
        return cls.query.filter(
            cls.due_date < datetime.utcnow(),
            cls.status.notin_(['resolved', 'closed'])
        ).all()
    
    @classmethod
    def get_stats(cls, department_id=None):
        """Get escalation statistics"""
        query = cls.query
        if department_id:
            query = query.filter_by(department_id=department_id)
        
        total = query.count()
        open_count = query.filter_by(status='open').count()
        assigned_count = query.filter_by(status='assigned').count()
        in_progress_count = query.filter_by(status='in_progress').count()
        resolved_count = query.filter_by(status='resolved').count()
        closed_count = query.filter_by(status='closed').count()
        
        overdue_count = query.filter(
            cls.due_date < datetime.utcnow(),
            cls.status.notin_(['resolved', 'closed'])
        ).count()
        
        return {
            'total': total,
            'open': open_count,
            'assigned': assigned_count,
            'in_progress': in_progress_count,
            'resolved': resolved_count,
            'closed': closed_count,
            'overdue': overdue_count
        }