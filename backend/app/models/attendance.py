# backend/app/models/attendance.py
from app.models import db
from datetime import datetime
import uuid

class Attendance(db.Model):
    __tablename__ = 'attendance'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    class_id = db.Column(db.String(36), db.ForeignKey('classes.id'), nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    user_type = db.Column(db.Enum('tutor', 'student', name='attendance_user_types'), nullable=False)
    status = db.Column(db.Enum('present', 'absent', 'late', 'early_departure', name='attendance_status'), nullable=False)
    marked_at = db.Column(db.DateTime, default=datetime.utcnow)
    join_time = db.Column(db.DateTime)
    leave_time = db.Column(db.DateTime)
    late_minutes = db.Column(db.Integer, default=0)
    participation_rating = db.Column(db.Integer)  # 1-5 scale
    notes = db.Column(db.Text)
    marked_by = db.Column(db.String(36), db.ForeignKey('users.id'))
    
    # Relationships
    class_session = db.relationship('Class', backref='attendance_records')
    user = db.relationship('User', foreign_keys=[user_id], backref='attendance_records')
    marker = db.relationship('User', foreign_keys=[marked_by])