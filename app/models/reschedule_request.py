# app/models/reschedule_request.py

from datetime import datetime
from app import db
from sqlalchemy import or_
from app.models.user import User

class RescheduleRequest(db.Model):
    __tablename__ = 'reschedule_requests'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Original Class Information
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=False)
    original_date = db.Column(db.Date, nullable=False)
    original_time = db.Column(db.Time, nullable=False)
    
    # New Proposed Schedule
    requested_date = db.Column(db.Date, nullable=False)
    requested_time = db.Column(db.Time, nullable=False)
    
    # Request Details
    reason = db.Column(db.Text, nullable=False)
    requested_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    request_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Approval Workflow
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    review_notes = db.Column(db.Text, nullable=True)
    
    # Conflict Check Results
    has_conflicts = db.Column(db.Boolean, default=False)
    conflict_details = db.Column(db.Text, nullable=True)  # JSON string of conflicts
    
    # Relationships
    class_item = db.relationship('Class', backref='reschedule_requests', lazy=True)
    requester = db.relationship('User', foreign_keys=[requested_by], backref='reschedule_requests_made', lazy=True)
    reviewer = db.relationship('User', foreign_keys=[reviewed_by], backref='reschedule_requests_reviewed', lazy=True)
    
    def __init__(self, **kwargs):
        super(RescheduleRequest, self).__init__(**kwargs)
        if self.class_item:
            self.original_date = self.class_item.scheduled_date
            self.original_time = self.class_item.scheduled_time
    
    def check_conflicts(self):
        """Check for scheduling conflicts with the requested time"""
        from app.models.class_model import Class
        
        conflicts = []
        
        # Check if tutor has another class at the requested time
        tutor_conflict = Class.query.filter_by(
            tutor_id=self.class_item.tutor_id,
            scheduled_date=self.requested_date,
            status='scheduled'
        ).filter(
            Class.id != self.class_id  # Exclude current class
        ).first()
        
        if tutor_conflict:
            # Check for time overlap
            requested_end = self._add_duration_to_time(self.requested_time, self.class_item.duration)
            existing_end = tutor_conflict.end_time
            
            if (self.requested_time < existing_end and 
                requested_end > tutor_conflict.scheduled_time):
                conflicts.append({
                    'type': 'tutor_conflict',
                    'message': f'Tutor already has a class from {tutor_conflict.scheduled_time} to {existing_end}',
                    'conflicting_class_id': tutor_conflict.id
                })
        
        # Check if students have conflicts (for group classes)
        if self.class_item.class_type == 'group':
            student_ids = self.class_item.get_students()
            for student_id in student_ids:
                student_conflicts = Class.query.filter(
                    or_(
                        Class.primary_student_id == student_id,
                        Class.students.contains(str(student_id))
                    )
                ).filter_by(
                    scheduled_date=self.requested_date,
                    status='scheduled'
                ).filter(
                    Class.id != self.class_id
                ).all()
                
                for conflict in student_conflicts:
                    requested_end = self._add_duration_to_time(self.requested_time, self.class_item.duration)
                    existing_end = conflict.end_time
                    
                    if (self.requested_time < existing_end and 
                        requested_end > conflict.scheduled_time):
                        conflicts.append({
                            'type': 'student_conflict',
                            'message': f'Student has another class from {conflict.scheduled_time} to {existing_end}',
                            'student_id': student_id,
                            'conflicting_class_id': conflict.id
                        })
        
        # Check tutor availability
        if hasattr(self.class_item.tutor, 'is_available_at'):
            day_of_week = self.requested_date.strftime('%A').lower()
            time_str = self.requested_time.strftime('%H:%M')
            
            if not self.class_item.tutor.is_available_at(day_of_week, time_str):
                conflicts.append({
                    'type': 'tutor_unavailable',
                    'message': f'Tutor is not available on {day_of_week} at {time_str}'
                })
        
        self.has_conflicts = len(conflicts) > 0
        if conflicts:
            import json
            self.conflict_details = json.dumps(conflicts)
        else:
            self.conflict_details = None
        
        return conflicts
    
    def _add_duration_to_time(self, time_obj, duration_minutes):
        """Helper to add duration to time object"""
        from datetime import datetime, timedelta
        dt = datetime.combine(datetime.today(), time_obj)
        dt += timedelta(minutes=duration_minutes)
        return dt.time()
    
    def approve(self, reviewer, notes=None):
        """Approve the reschedule request"""
        self.status = 'approved'
        self.reviewed_by = reviewer.id
        self.reviewed_at = datetime.utcnow()
        self.review_notes = notes
        
        # Update the actual class
        self.class_item.scheduled_date = self.requested_date
        self.class_item.scheduled_time = self.requested_time
        self.class_item.calculate_end_time()
        self.class_item.updated_at = datetime.utcnow()
        
        db.session.commit()
    
    def reject(self, reviewer, notes=None):
        """Reject the reschedule request"""
        self.status = 'rejected'
        self.reviewed_by = reviewer.id
        self.reviewed_at = datetime.utcnow()
        self.review_notes = notes
        db.session.commit()
    
    def can_be_approved(self):
        """Check if request can be approved (no conflicts)"""
        return not self.has_conflicts and self.status == 'pending'
    
    def get_conflicts(self):
        """Get conflicts as list"""
        if self.conflict_details:
            import json
            try:
                return json.loads(self.conflict_details)
            except:
                return []
        return []
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'class_id': self.class_id,
            'original_date': self.original_date.isoformat() if self.original_date else None,
            'original_time': self.original_time.strftime('%H:%M') if self.original_time else None,
            'requested_date': self.requested_date.isoformat() if self.requested_date else None,
            'requested_time': self.requested_time.strftime('%H:%M') if self.requested_time else None,
            'reason': self.reason,
            'status': self.status,
            'requested_by': self.requester.full_name if self.requester else None,
            'request_date': self.request_date.isoformat() if self.request_date else None,
            'reviewed_by': self.reviewer.full_name if self.reviewer else None,
            'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None,
            'review_notes': self.review_notes,
            'has_conflicts': self.has_conflicts,
            'conflicts': self.get_conflicts(),
            'can_approve': self.can_be_approved()
        }
    
    @staticmethod
    def get_pending_requests(department_id=None):
        """Get all pending reschedule requests"""
        query = RescheduleRequest.query.filter_by(status='pending')
        
        if department_id:
            from app.models.class_model import Class
            from app.models.tutor import Tutor
            from app.models.user import User
            
            query = query.join(Class).join(Tutor).join(User).filter(
                User.department_id == department_id
            )
        
        return query.order_by(RescheduleRequest.request_date.desc()).all()
    
    @staticmethod
    def get_requests_for_tutor(tutor_id):
        """Get reschedule requests for specific tutor"""
        from app.models.class_model import Class
        
        return RescheduleRequest.query.join(Class).filter(
            Class.tutor_id == tutor_id
        ).order_by(RescheduleRequest.request_date.desc()).all()
    
    def __repr__(self):
        return f'<RescheduleRequest {self.id} - Class {self.class_id} - {self.status}>'
    
    def approve(self, reviewer, notes=None):
        """Approve the reschedule request and send notifications"""
        self.status = 'approved'
        self.reviewed_by = reviewer.id
        self.reviewed_at = datetime.utcnow()
        self.review_notes = notes
        
        # Update the actual class
        self.class_item.scheduled_date = self.requested_date
        self.class_item.scheduled_time = self.requested_time
        self.class_item.calculate_end_time()
        self.class_item.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Send notification
        from app.services.reschedule_notifications import RescheduleNotificationService
        RescheduleNotificationService.send_reschedule_approved_notification(self)
    
    def reject(self, reviewer, notes=None):
        """Reject the reschedule request and send notifications"""
        self.status = 'rejected'
        self.reviewed_by = reviewer.id
        self.reviewed_at = datetime.utcnow()
        self.review_notes = notes
        db.session.commit()
        
        # Send notification
        from app.services.reschedule_notifications import RescheduleNotificationService
        RescheduleNotificationService.send_reschedule_rejected_notification(self)
