# app/models/demo_student.py

from app import db
from datetime import datetime
import json

class DemoStudent(db.Model):
    __tablename__ = 'demo_students'
    
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    parent_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), nullable=False, unique=True)
    grade = db.Column(db.String(10), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    board = db.Column(db.String(50))
    
    # Demo specific fields
    preferred_time = db.Column(db.String(20))  # morning, afternoon, evening
    demo_status = db.Column(db.String(20), default='scheduled')  # scheduled, completed, converted, cancelled
    conversion_date = db.Column(db.DateTime)
    regular_student_id = db.Column(db.Integer, db.ForeignKey('students.id'))
    
    # Meeting details
    meeting_link = db.Column(db.String(500))
    meeting_id = db.Column(db.String(100))
    meeting_password = db.Column(db.String(50))
    
    # Feedback and notes
    demo_feedback = db.Column(db.Text)
    tutor_notes = db.Column(db.Text)
    conversion_notes = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    regular_student = db.relationship('Student', backref='demo_profile')
    demo_classes = db.relationship('Class', foreign_keys='Class.demo_student_id', overlaps="demo_student_profile")

    def __repr__(self):
        return f'<DemoStudent {self.full_name}>'
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'full_name': self.full_name,
            'parent_name': self.parent_name,
            'phone': self.phone,
            'email': self.email,
            'grade': self.grade,
            'subject': self.subject,
            'board': self.board,
            'preferred_time': self.preferred_time,
            'demo_status': self.demo_status,
            'meeting_link': self.meeting_link,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'conversion_date': self.conversion_date.isoformat() if self.conversion_date else None
        }
    
    def get_demo_classes(self):
        """Get all demo classes for this student"""
        from app.models.class_model import Class
        return Class.query.filter_by(demo_student_id=self.id).all()
    
    def get_latest_demo_class(self):
        """Get the most recent demo class"""
        from app.models.class_model import Class
        return Class.query.filter_by(demo_student_id=self.id)\
                          .order_by(Class.scheduled_date.desc(), Class.scheduled_time.desc())\
                          .first()
    
    def mark_as_converted(self, regular_student_id, notes=None):
        """Mark demo student as converted to regular"""
        self.demo_status = 'converted'
        self.regular_student_id = regular_student_id
        self.conversion_date = datetime.utcnow()
        if notes:
            self.conversion_notes = notes
    
    def set_demo_feedback(self, feedback_data):
        """Set demo feedback from tutor"""
        if isinstance(feedback_data, dict):
            self.demo_feedback = json.dumps(feedback_data)
        else:
            self.demo_feedback = feedback_data
    
    def get_demo_feedback(self):
        """Get parsed demo feedback"""
        if self.demo_feedback:
            try:
                return json.loads(self.demo_feedback)
            except:
                return {'comments': self.demo_feedback}
        return {}
    
    def set_meeting_details(self, meeting_data):
        """Set meeting link and details"""
        self.meeting_link = meeting_data.get('link')
        self.meeting_id = meeting_data.get('meeting_id')
        self.meeting_password = meeting_data.get('password')