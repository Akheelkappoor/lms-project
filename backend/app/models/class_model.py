# backend/app/models/class_model.py
from app.models import db
from datetime import datetime
import uuid

class Class(db.Model):
    __tablename__ = 'classes'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = db.Column(db.String(200), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    grade_level = db.Column(db.String(20))
    class_type = db.Column(db.Enum('one_on_one', 'group', 'demo', name='class_types'), nullable=False)
    tutor_id = db.Column(db.String(36), db.ForeignKey('tutors.id'), nullable=False)
    students = db.Column(db.JSON)  # Array of student IDs for group classes
    scheduled_start = db.Column(db.DateTime, nullable=False)
    scheduled_end = db.Column(db.DateTime, nullable=False)
    actual_start = db.Column(db.DateTime)
    actual_end = db.Column(db.DateTime)
    status = db.Column(db.Enum('scheduled', 'ongoing', 'completed', 'cancelled', 'rescheduled', name='class_status'), default='scheduled')
    meeting_platform = db.Column(db.String(50))  # zoom, google_meet, etc.
    meeting_url = db.Column(db.String(500))
    meeting_id = db.Column(db.String(100))
    meeting_password = db.Column(db.String(50))
    backup_meeting_url = db.Column(db.String(500))
    video_recording_url = db.Column(db.String(500))
    class_notes = db.Column(db.Text)
    homework_assigned = db.Column(db.Text)
    materials_shared = db.Column(db.JSON)  # URLs of shared materials
    cancellation_reason = db.Column(db.String(500))
    reschedule_reason = db.Column(db.String(500))
    # backend/app/models/class_model.py (continued)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tutor = db.relationship('Tutor', backref='classes')
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'subject': self.subject,
            'grade_level': self.grade_level,
            'class_type': self.class_type,
            'tutor_id': self.tutor_id,
            'students': self.students,
            'scheduled_start': self.scheduled_start.isoformat(),
            'scheduled_end': self.scheduled_end.isoformat(),
            'actual_start': self.actual_start.isoformat() if self.actual_start else None,
            'actual_end': self.actual_end.isoformat() if self.actual_end else None,
            'status': self.status,
            'meeting_platform': self.meeting_platform,
            'meeting_url': self.meeting_url,
            'meeting_id': self.meeting_id,
            'video_recording_url': self.video_recording_url,
            'class_notes': self.class_notes,
            'homework_assigned': self.homework_assigned,
            'materials_shared': self.materials_shared,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }