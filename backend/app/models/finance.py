# backend/app/models/finance.py
from app.models import db
from datetime import datetime
import uuid

class TutorSalary(db.Model):
    __tablename__ = 'tutor_salaries'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tutor_id = db.Column(db.String(36), db.ForeignKey('tutors.id'), nullable=False)
    month = db.Column(db.Integer, nullable=False)  # 1-12
    year = db.Column(db.Integer, nullable=False)
    base_amount = db.Column(db.Decimal(10, 2))
    classes_taught = db.Column(db.Integer, default=0)
    hours_taught = db.Column(db.Decimal(5, 2), default=0)
    late_deductions = db.Column(db.Decimal(8, 2), default=0)
    leave_deductions = db.Column(db.Decimal(8, 2), default=0)
    bonus_amount = db.Column(db.Decimal(8, 2), default=0)
    total_amount = db.Column(db.Decimal(10, 2))
    status = db.Column(db.Enum('pending', 'processed', 'paid', name='salary_status'), default='pending')
    payment_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    tutor = db.relationship('Tutor', backref='salary_records')

class StudentFee(db.Model):
    __tablename__ = 'student_fees'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = db.Column(db.String(36), db.ForeignKey('students.id'), nullable=False)
    fee_type = db.Column(db.String(50))  # monthly_tuition, admission, etc.
    amount = db.Column(db.Decimal(10, 2), nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    paid_amount = db.Column(db.Decimal(10, 2), default=0)
    payment_date = db.Column(db.DateTime)
    payment_method = db.Column(db.String(50))  # online, bank_transfer, cash, etc.
    transaction_id = db.Column(db.String(100))
    status = db.Column(db.Enum('pending', 'paid', 'overdue', 'partial', name='fee_status'), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    student = db.relationship('Student', backref='fee_records')