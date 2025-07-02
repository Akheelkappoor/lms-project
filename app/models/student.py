from datetime import datetime, date
from app import db
import json

class Student(db.Model):
    __tablename__ = 'students'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Basic Information
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    date_of_birth = db.Column(db.Date)
    address = db.Column(db.Text)
    state = db.Column(db.String(50))
    pin_code = db.Column(db.String(10))
    
    # Academic Information
    grade = db.Column(db.String(10), nullable=False)
    board = db.Column(db.String(50), nullable=False)
    school_name = db.Column(db.String(200))
    academic_year = db.Column(db.String(20))
    course_start_date = db.Column(db.Date)
    
    # Parent/Guardian Information
    parent_details = db.Column(db.Text)  # JSON with father and mother details
    
    # Academic Profile
    academic_profile = db.Column(db.Text)  # JSON with learning preferences, hobbies, etc.
    subjects_enrolled = db.Column(db.Text)  # JSON array of subjects
    favorite_subjects = db.Column(db.Text)  # JSON array
    difficult_subjects = db.Column(db.Text)  # JSON array
    
    # Availability
    availability = db.Column(db.Text)  # JSON weekly schedule
    
    # Documents
    documents = db.Column(db.Text)  # JSON with document file paths
    
    # Admission and Assignment
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=False)
    relationship_manager = db.Column(db.String(100))  # RM name
    
    # Fee Structure
    fee_structure = db.Column(db.Text)  # JSON with fee details
    
    # Status and Tracking
    is_active = db.Column(db.Boolean, default=True)
    enrollment_status = db.Column(db.String(20), default='active')  # active, paused, completed, dropped
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_class = db.Column(db.DateTime)
    
    # Performance tracking
    total_classes = db.Column(db.Integer, default=0)
    attended_classes = db.Column(db.Integer, default=0)
    
    # Relationships
    department = db.relationship('Department', backref='students', lazy=True)
    
    def __init__(self, **kwargs):
        super(Student, self).__init__(**kwargs)
    
    def get_parent_details(self):
        """Get parent details as dict"""
        if self.parent_details:
            try:
                return json.loads(self.parent_details)
            except:
                return {}
        return {}
    
    def set_parent_details(self, parent_dict):
        """Set parent details from dict
        Format: {
            'father': {'name': '', 'phone': '', 'email': '', 'profession': '', 'workplace': ''},
            'mother': {'name': '', 'phone': '', 'email': '', 'profession': '', 'workplace': ''}
        }
        """
        self.parent_details = json.dumps(parent_dict)
    
    def get_academic_profile(self):
        """Get academic profile as dict"""
        if self.academic_profile:
            try:
                return json.loads(self.academic_profile)
            except:
                return {}
        return {}
    
    def set_academic_profile(self, profile_dict):
        """Set academic profile from dict
        Format: {
            'siblings': 2,
            'hobbies': ['reading', 'sports'],
            'learning_styles': ['visual', 'auditory'],
            'learning_patterns': ['fast_learner'],
            'parent_feedback': 'Previous tutoring experience...'
        }
        """
        self.academic_profile = json.dumps(profile_dict)
    
    def get_subjects_enrolled(self):
        """Get enrolled subjects as list"""
        if self.subjects_enrolled:
            try:
                return json.loads(self.subjects_enrolled)
            except:
                return []
        return []
    
    def set_subjects_enrolled(self, subjects_list):
        """Set enrolled subjects from list"""
        self.subjects_enrolled = json.dumps(subjects_list)
    
    def get_favorite_subjects(self):
        """Get favorite subjects as list"""
        if self.favorite_subjects:
            try:
                return json.loads(self.favorite_subjects)
            except:
                return []
        return []
    
    def set_favorite_subjects(self, subjects_list):
        """Set favorite subjects from list"""
        self.favorite_subjects = json.dumps(subjects_list)
    
    def get_difficult_subjects(self):
        """Get difficult subjects as list"""
        if self.difficult_subjects:
            try:
                return json.loads(self.difficult_subjects)
            except:
                return []
        return []
    
    def set_difficult_subjects(self, subjects_list):
        """Set difficult subjects from list"""
        self.difficult_subjects = json.dumps(subjects_list)
    
    def get_availability(self):
        """Get availability as dict"""
        if self.availability:
            try:
                return json.loads(self.availability)
            except:
                return {}
        return {}
    
    def set_availability(self, availability_dict):
        """Set availability from dict"""
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
    
    def get_fee_structure(self):
        """Get fee structure as dict"""
        if self.fee_structure:
            try:
                return json.loads(self.fee_structure)
            except:
                return {}
        return {}
    
    def set_fee_structure(self, fee_dict):
        """Set fee structure from dict
        Format: {
            'total_fee': 50000,
            'amount_paid': 20000,
            'balance_amount': 30000,
            'payment_mode': 'online',
            'payment_schedule': 'monthly',
            'installment_plan': {...}
        }
        """
        self.fee_structure = json.dumps(fee_dict)
    
    def is_available_at(self, day_of_week, time_str):
        """Check if student is available at specific day and time"""
        availability = self.get_availability()
        if day_of_week.lower() not in availability:
            return False
        
        day_slots = availability[day_of_week.lower()]
        for slot in day_slots:
            if slot['start'] <= time_str <= slot['end']:
                return True
        return False
    
    def get_attendance_percentage(self):
        """Calculate attendance percentage"""
        if self.total_classes == 0:
            return 0
        return (self.attended_classes / self.total_classes) * 100
    
    def get_fee_status(self):
        """Get fee payment status"""
        fee_structure = self.get_fee_structure()
        if not fee_structure:
            return 'unknown'
        
        total_fee = fee_structure.get('total_fee', 0)
        amount_paid = fee_structure.get('amount_paid', 0)
        
        if amount_paid >= total_fee:
            return 'paid'
        elif amount_paid > 0:
            return 'partial'
        else:
            return 'pending'
    
    def get_balance_amount(self):
        """Get remaining fee balance"""
        fee_structure = self.get_fee_structure()
        if not fee_structure:
            return 0
        
        total_fee = fee_structure.get('total_fee', 0)
        amount_paid = fee_structure.get('amount_paid', 0)
        return max(0, total_fee - amount_paid)
    
    def get_age(self):
        """Calculate student's age"""
        if self.date_of_birth:
            today = date.today()
            return today.year - self.date_of_birth.year - \
                   ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
        return None
    
    def get_primary_contact(self):
        """Get primary parent contact"""
        parent_details = self.get_parent_details()
        # Try father first, then mother
        if 'father' in parent_details and parent_details['father'].get('phone'):
            return {
                'name': parent_details['father'].get('name'),
                'phone': parent_details['father'].get('phone'),
                'email': parent_details['father'].get('email'),
                'relation': 'Father'
            }
        elif 'mother' in parent_details and parent_details['mother'].get('phone'):
            return {
                'name': parent_details['mother'].get('name'),
                'phone': parent_details['mother'].get('phone'),
                'email': parent_details['mother'].get('email'),
                'relation': 'Mother'
            }
        return None
    
    @staticmethod
    def get_students_by_criteria(grade=None, board=None, subject=None, department_id=None):
        """Get students matching specific criteria"""
        query = Student.query.filter_by(is_active=True)
        
        if grade:
            query = query.filter_by(grade=grade)
        
        if board:
            query = query.filter_by(board=board)
        
        if department_id:
            query = query.filter_by(department_id=department_id)
        
        students = query.all()
        
        if subject:
            # Filter by enrolled subjects
            filtered_students = []
            for student in students:
                if subject in student.get_subjects_enrolled():
                    filtered_students.append(student)
            return filtered_students
        
        return students
    
    def to_dict(self):
        """Convert student to dictionary"""
        return {
            'id': self.id,
            'full_name': self.full_name,
            'email': self.email,
            'phone': self.phone,
            'grade': self.grade,
            'board': self.board,
            'school_name': self.school_name,
            'department': self.department.name if self.department else '',
            'subjects_enrolled': self.get_subjects_enrolled(),
            'enrollment_status': self.enrollment_status,
            'attendance_percentage': self.get_attendance_percentage(),
            'fee_status': self.get_fee_status(),
            'balance_amount': self.get_balance_amount(),
            'relationship_manager': self.relationship_manager,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'age': self.get_age()
        }
    
    def __repr__(self):
        return f'<Student {self.full_name}>'
    
    # ADD THESE METHODS TO YOUR Student CLASS in app/models/student.py
    def get_compatible_tutors(self):
        """Get tutors compatible with this student"""
        from app.models.tutor import Tutor
        # Import here to avoid circular imports
        tutors = Tutor.query.filter_by(status='active').all()
        compatible_tutors = []
        for tutor in tutors:
            # Must have availability
            if not tutor.get_availability():
                continue

        # Check grade compatibility
            tutor_grades = [str(g) for g in tutor.get_grades()]
            if tutor_grades and str(self.grade) not in tutor_grades:
                continue
        
        # Check board compatibility
            tutor_boards = [b.lower() for b in tutor.get_boards()]
            if tutor_boards and self.board.lower() not in tutor_boards:
                continue

        # Check subject compatibility
            student_subjects = [s.lower() for s in self.get_subjects_enrolled()]
            tutor_subjects = [s.lower() for s in tutor.get_subjects()]
        
            if student_subjects and tutor_subjects:
                has_common_subject = any(
                    any(ss in ts or ts in ss for ts in tutor_subjects)
                    for ss in student_subjects
                )
                if not has_common_subject:
                  continue
        
        compatible_tutors.append(tutor)
    
        return compatible_tutors
    @staticmethod
    def find_students_for_tutor(tutor, subject=None):
       """Find students compatible with a specific tutor"""
       query = Student.query.filter_by(is_active=True, enrollment_status='active')
    
       compatible_students = []
       students = query.all()
    
       for student in students:
        # Check grade compatibility
           tutor_grades = [str(g) for g in tutor.get_grades()]
           if tutor_grades and str(student.grade) not in tutor_grades:
               continue
        
        # Check board compatibility
           tutor_boards = [b.lower() for b in tutor.get_boards()]
           if tutor_boards and student.board.lower() not in tutor_boards:
              continue
        
        # Check subject compatibility if specified
           if subject:
               student_subjects = [s.lower() for s in student.get_subjects_enrolled()]
               if student_subjects and subject.lower() not in student_subjects:
                   continue
        
           compatible_students.append(student)
    
       return compatible_students





