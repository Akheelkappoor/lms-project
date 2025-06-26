# backend/app/models/student.py
from app.models import db
from datetime import datetime
import uuid

class Student(db.Model):
    __tablename__ = 'students'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), unique=True, nullable=False)
    grade_level = db.Column(db.String(20))
    educational_board = db.Column(db.String(50))
    academic_year = db.Column(db.String(20))
    school_name = db.Column(db.String(200))
    date_of_birth = db.Column(db.Date)
    address = db.Column(db.Text)
    state = db.Column(db.String(50))
    pin_code = db.Column(db.String(10))
    
    # Parent/Guardian Information
    father_name = db.Column(db.String(100))
    father_phone = db.Column(db.String(20))
    father_email = db.Column(db.String(120))
    father_profession = db.Column(db.String(100))
    father_workplace = db.Column(db.String(200))
    
    mother_name = db.Column(db.String(100))
    mother_phone = db.Column(db.String(20))
    mother_email = db.Column(db.String(120))
    mother_profession = db.Column(db.String(100))
    mother_workplace = db.Column(db.String(200))
    
    # Academic Profile
    siblings_count = db.Column(db.Integer, default=0)
    hobbies = db.Column(db.JSON)
    learning_styles = db.Column(db.JSON)
    learning_patterns = db.Column(db.JSON)
    favorite_subjects = db.Column(db.JSON)
    difficult_subjects = db.Column(db.JSON)
    parent_feedback = db.Column(db.Text)
    
    # Availability
    availability_schedule = db.Column(db.JSON)
    
    # Documents
    documents = db.Column(db.JSON)
    
    # Admission Details
    relationship_manager = db.Column(db.String(100))
    classes_enrolled = db.Column(db.JSON)
    class_hours_per_week = db.Column(db.Integer)
    number_of_classes_per_week = db.Column(db.Integer)
    course_duration_months = db.Column(db.Integer)
    
    # Fee Structure
    total_fee = db.Column(db.Decimal(10, 2))
    amount_paid = db.Column(db.Decimal(10, 2), default=0)
    balance_amount = db.Column(db.Decimal(10, 2))
    payment_schedule = db.Column(db.Enum('monthly', 'quarterly', 'one_time', name='payment_schedules'))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='student_profile')
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'grade_level': self.grade_level,
            'educational_board': self.educational_board,
            'academic_year': self.academic_year,
            'school_name': self.school_name,
            'date_of_birth': self.date_of_birth.isoformat() if self.date_of_birth else None,
            'address': self.address,
            'state': self.state,
            'pin_code': self.pin_code,
            'father_name': self.father_name,
            'father_phone': self.father_phone,
            'father_email': self.father_email,
            'father_profession': self.father_profession,
            'father_workplace': self.father_workplace,
            'mother_name': self.mother_name,
            'mother_phone': self.mother_phone,
            'mother_email': self.mother_email,
            'mother_profession': self.mother_profession,
            'mother_workplace': self.mother_workplace,
            'siblings_count': self.siblings_count,
            'hobbies': self.hobbies,
            'learning_styles': self.learning_styles,
            'learning_patterns': self.learning_patterns,
            'favorite_subjects': self.favorite_subjects,
            'difficult_subjects': self.difficult_subjects,
            'parent_feedback': self.parent_feedback,
            'availability_schedule': self.availability_schedule,
            'documents': self.documents,
            'relationship_manager': self.relationship_manager,
            'classes_enrolled': self.classes_enrolled,
            'class_hours_per_week': self.class_hours_per_week,
            'number_of_classes_per_week': self.number_of_classes_per_week,
            'course_duration_months': self.course_duration_months,
            'total_fee': float(self.total_fee) if self.total_fee else None,
            'amount_paid': float(self.amount_paid) if self.amount_paid else None,
            'balance_amount': float(self.balance_amount) if self.balance_amount else None,
            'payment_schedule': self.payment_schedule,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }