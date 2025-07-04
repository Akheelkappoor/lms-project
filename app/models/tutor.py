from datetime import datetime, date
from app import db
import json

class Tutor(db.Model):
    __tablename__ = 'tutors'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)

    date_of_birth = db.Column(db.Date)
    state = db.Column(db.String(50))
    pin_code = db.Column(db.String(10))
    
    # Professional Information
    qualification = db.Column(db.String(200), nullable=False)
    experience = db.Column(db.Text)  # Years and background
    subjects = db.Column(db.Text)  # JSON array of subjects
    grades = db.Column(db.Text)  # JSON array of grade levels
    boards = db.Column(db.Text)  # JSON array of education boards
    
    # Availability
    availability = db.Column(db.Text)  # JSON object for weekly schedule
    
    # Compensation
    salary_type = db.Column(db.String(20), nullable=False)  # 'monthly' or 'hourly'
    monthly_salary = db.Column(db.Float)
    hourly_rate = db.Column(db.Float)
    
    # Documents and Media
    documents = db.Column(db.Text)  # JSON object with document file paths
    demo_video = db.Column(db.String(2000))
    interview_video = db.Column(db.String(2000))
    
    # Banking Information
    bank_details = db.Column(db.Text)  # JSON object with banking info
    
    # Status and Performance
    status = db.Column(db.String(20), default='pending')  # pending, active, inactive, suspended
    verification_status = db.Column(db.String(20), default='pending')  # pending, verified, rejected
    rating = db.Column(db.Float, default=0.0)
    total_classes = db.Column(db.Integer, default=0)
    completed_classes = db.Column(db.Integer, default=0)
    
    # Tracking
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_class = db.Column(db.DateTime)
    
    def __init__(self, **kwargs):
        super(Tutor, self).__init__(**kwargs)
    
    def get_subjects(self):
        """Get subjects as list"""
        if self.subjects:
            try:
                return json.loads(self.subjects)
            except:
                return []
        return []
    
    def set_subjects(self, subjects_list):
        """Set subjects from list"""
        self.subjects = json.dumps(subjects_list)
    
    def get_grades(self):
        """Get grades as list"""
        if self.grades:
            try:
                return json.loads(self.grades)
            except:
                return []
        return []
    
    def set_grades(self, grades_list):
        """Set grades from list"""
        self.grades = json.dumps(grades_list)
    
    def get_boards(self):
        """Get boards as list"""
        if self.boards:
            try:
                return json.loads(self.boards)
            except:
                return []
        return []
    
    def set_boards(self, boards_list):
        """Set boards from list"""
        self.boards = json.dumps(boards_list)
    
    def get_availability(self):
        """Get availability as dict"""
        if self.availability:
            try:
                return json.loads(self.availability)
            except:
                return {}
        return {}
    
    def set_availability(self, availability_dict):
        """Set availability from dict
        Format: {
            'monday': [{'start': '09:00', 'end': '12:00'}, {'start': '14:00', 'end': '17:00'}],
            'tuesday': [...],
            ...
        }
        """
        self.availability = json.dumps(availability_dict)
    
    def get_documents(self):
        """Get documents as dict"""
        if self.documents:
            try:
                return json.loads(self.documents)
            except:
                return {}
        return {}
    
    def set_documents(self, documents_dict):
        """Set documents from dict"""
        self.documents = json.dumps(documents_dict)
    
    def get_bank_details(self):
        """Get bank details as dict"""
        if self.bank_details:
            try:
                return json.loads(self.bank_details)
            except:
                return {}
        return {}
    
    def set_bank_details(self, bank_dict):
        """Set bank details from dict"""
        self.bank_details = json.dumps(bank_dict)
    
    def is_available_at(self, day_of_week, time_str):
        """Check if tutor is available at specific day and time
        Args:
            day_of_week: 'monday', 'tuesday', etc.
            time_str: '14:30' format
        """
        availability = self.get_availability()
        if day_of_week.lower() not in availability:
            return False
        
        day_slots = availability[day_of_week.lower()]
        for slot in day_slots:
            if slot['start'] <= time_str <= slot['end']:
                return True
        return False
    
    def get_monthly_earnings(self, month=None, year=None):
        """Calculate monthly earnings based on classes taught"""
        if not month:
            month = datetime.now().month
        if not year:
            year = datetime.now().year
            
        # This would need to be implemented with actual attendance/class data
        # For now, return based on salary type
        if self.salary_type == 'monthly':
            return self.monthly_salary or 0
        else:
            # Calculate based on hours taught (would need attendance records)
            return 0
    
    def get_completion_rate(self):
        """Get class completion rate as percentage"""
        if self.total_classes == 0:
            return 0
        return (self.completed_classes / self.total_classes) * 100
    
    def get_status_display(self):
        """Get formatted status"""
        status_map = {
            'pending': 'Pending Review',
            'active': 'Active',
            'inactive': 'Inactive',
            'suspended': 'Suspended'
        }
        return status_map.get(self.status, self.status.title())
    
    def can_teach_subject(self, subject):
        """Check if tutor can teach specific subject"""
        return subject.lower() in [s.lower() for s in self.get_subjects()]
    
    def can_teach_grade(self, grade):
        """Check if tutor can teach specific grade"""
        return str(grade) in [str(g) for g in self.get_grades()]
    
    def can_teach_board(self, board):
        """Check if tutor is familiar with specific board"""
        return board.lower() in [b.lower() for b in self.get_boards()]
    
    @staticmethod
    def get_available_tutors(subject=None, grade=None, board=None, day=None, time=None):
        """Get available tutors based on criteria"""
        query = Tutor.query.filter_by(status='active')
        
        available_tutors = []
        for tutor in query:
            # Check subject compatibility
            if subject and not tutor.can_teach_subject(subject):
                continue
            
            # Check grade compatibility
            if grade and not tutor.can_teach_grade(grade):
                continue
            
            # Check board compatibility
            if board and not tutor.can_teach_board(board):
                continue
            
            # Check availability
            if day and time and not tutor.is_available_at(day, time):
                continue
            
            available_tutors.append(tutor)
        
        return available_tutors
    
    def to_dict(self):
        """Convert tutor to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'user_name': self.user.full_name if self.user else '',
            'qualification': self.qualification,
            'experience': self.experience,
            'subjects': self.get_subjects(),
            'grades': self.get_grades(),
            'boards': self.get_boards(),
            'salary_type': self.salary_type,
            'monthly_salary': self.monthly_salary,
            'hourly_rate': self.hourly_rate,
            'status': self.status,
            'verification_status': self.verification_status,
            'rating': self.rating,
            'total_classes': self.total_classes,
            'completed_classes': self.completed_classes,
            'completion_rate': self.get_completion_rate(),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f'<Tutor {self.user.full_name if self.user else self.id}>'
    
    def calculate_monthly_salary(self, month=None, year=None):
        """Calculate monthly salary based on attendance and performance"""
        from datetime import datetime, date
        from app.models.attendance import Attendance
        
        # Set default month/year if not provided
        if not month:
            month = datetime.now().month
        if not year:
            year = datetime.now().year

        # Initialize salary calculation components
        base_salary = self.monthly_salary or 0
        attendance_records = self._get_monthly_attendance_records(month, year)
        attended_classes = [att for att in attendance_records if att.status == 'present']

        # Calculate salary based on type
        if self.salary_type == 'hourly':
            calculated_salary = self._calculate_hourly_salary(attended_classes)
        else:
            calculated_salary = self._calculate_fixed_monthly_salary(base_salary, attendance_records, attended_classes)

        return {
            'base_salary': base_salary,
            'calculated_salary': calculated_salary,
            'total_classes': len(attendance_records),
            'attended_classes': len(attended_classes),
            'month': month,
            'year': year
        }

    def _get_monthly_attendance_records(self, month, year):
        """Helper method to get attendance records for a specific month"""
        from datetime import date
        from app.models.attendance import Attendance
        
        start_date = date(year, month, 1)
        end_date = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
        
        return Attendance.query.filter(
            Attendance.tutor_id == self.id,
            Attendance.class_date >= start_date,
            Attendance.class_date < end_date
        ).all()

    def _calculate_hourly_salary(self, attended_classes):
        """Helper method to calculate hourly-based salary"""
        total_hours = sum(att.duration_hours or 1 for att in attended_classes)
        return total_hours * (self.hourly_rate or 0)

    def _calculate_fixed_monthly_salary(self, base_salary, all_classes, attended_classes):
        """Helper method to calculate fixed monthly salary with attendance adjustment"""
        total_classes = len(all_classes)
        if total_classes > 0:
            attendance_rate = len(attended_classes) / total_classes
            return base_salary * attendance_rate
        return base_salary

    # Salary history and payment methods
    def get_salary_history(self):
        """Get salary payment history"""
        if hasattr(self, 'salary_payments') and self.salary_payments:
            try:
                return json.loads(self.salary_payments)
            except:
                return []
        return []

    def get_outstanding_salary(self):
        """Get pending salary payments"""
        salary_history = self.get_salary_history()
        return sum(payment['amount'] for payment in salary_history if payment['status'] == 'pending')

    def add_salary_payment(self, amount, month, year, status='pending', payment_date=None):
        """Add salary payment record"""
        from datetime import datetime
        
        salary_history = self.get_salary_history()
        payment_record = {
            'id': len(salary_history) + 1,
            'amount': amount,
            'month': month,
            'year': year,
            'status': status,
            'payment_date': payment_date.isoformat() if payment_date else None,
            'created_at': datetime.now().isoformat()
        }
        
        salary_history.append(payment_record)
        self.salary_payments = json.dumps(salary_history)
        return payment_record
