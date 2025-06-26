# backend/app/models/tutor.py
from app.models import db
from datetime import datetime
import uuid

class Tutor(db.Model):
    __tablename__ = 'tutors'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), unique=True, nullable=False)
    qualification = db.Column(db.String(200))
    experience_years = db.Column(db.Integer)
    experience_description = db.Column(db.Text)
    subjects = db.Column(db.JSON)  # Store as JSON array
    grades = db.Column(db.JSON)    # Store as JSON array
    boards = db.Column(db.JSON)    # Store as JSON array
    availability_schedule = db.Column(db.JSON)  # Weekly schedule
    salary_type = db.Column(db.Enum('fixed_monthly', 'hourly_rate', name='salary_types'))
    fixed_monthly_amount = db.Column(db.Decimal(10, 2))
    hourly_rate = db.Column(db.Decimal(8, 2))
    bank_account_holder = db.Column(db.String(100))
    bank_name = db.Column(db.String(100))
    bank_account_number = db.Column(db.String(50))
    bank_ifsc_code = db.Column(db.String(20))
    documents = db.Column(db.JSON)  # Store document URLs
    demo_video_url = db.Column(db.String(255))
    interview_video_url = db.Column(db.String(255))
    verification_status = db.Column(db.Enum('pending', 'verified', 'rejected', name='verification_status'), default='pending')
    performance_rating = db.Column(db.Float, default=0.0)
    total_classes_taught = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='tutor_profile')
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'qualification': self.qualification,
            'experience_years': self.experience_years,
            'experience_description': self.experience_description,
            'subjects': self.subjects,
            'grades': self.grades,
            'boards': self.boards,
            'availability_schedule': self.availability_schedule,
            'salary_type': self.salary_type,
            'fixed_monthly_amount': float(self.fixed_monthly_amount) if self.fixed_monthly_amount else None,
            'hourly_rate': float(self.hourly_rate) if self.hourly_rate else None,
            'bank_account_holder': self.bank_account_holder,
            'bank_name': self.bank_name,
            'bank_account_number': self.bank_account_number,
            'bank_ifsc_code': self.bank_ifsc_code,
            'documents': self.documents,
            'demo_video_url': self.demo_video_url,
            'interview_video_url': self.interview_video_url,
            'verification_status': self.verification_status,
            'performance_rating': self.performance_rating,
            'total_classes_taught': self.total_classes_taught,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }