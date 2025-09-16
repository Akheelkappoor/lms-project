from datetime import datetime, date
from dateutil.relativedelta import relativedelta
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
    is_active = db.Column(db.Boolean, default=True, index=True)
    enrollment_status = db.Column(db.String(20), default='active', index=True)  # active, paused, completed, dropped, hold_graduation, hold_drop
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    last_class = db.Column(db.DateTime)
    
    # Performance tracking
    total_classes = db.Column(db.Integer, default=0)
    attended_classes = db.Column(db.Integer, default=0)
    
    course_end_date = db.Column(db.Date, nullable=True)
    batch_identifier = db.Column(db.String(100), nullable=True)  
    course_duration_months = db.Column(db.Integer, nullable=True)
    
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
        """Get students matching specific criteria with optimized queries"""
        # Use joinedload for better performance
        query = Student.query.filter_by(is_active=True).options(
            db.joinedload(Student.department)
        )
        
        if grade:
            query = query.filter_by(grade=grade)
        
        if board:
            query = query.filter_by(board=board)
        
        if department_id:
            query = query.filter_by(department_id=department_id)
        
        if subject:
            # Use SQL LIKE for better performance with JSON fields
            query = query.filter(Student.subjects_enrolled.like(f'%"{subject}"%'))
        
        return query.all()
    
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
    
    def get_initials(self):
        """Get student initials for avatar generation"""
        if self.full_name:
            names = self.full_name.split()
            if len(names) >= 2:
                return f"{names[0][0]}{names[1][0]}".upper()
            else:
                return names[0][:2].upper()
        return self.email[:2].upper() if self.email else "S"
    
    def get_avatar_url(self):
        """Get avatar URL with fallback to default avatar"""
        # Students typically don't have profile pictures, so use generated avatars
        initials = self.get_initials()
        # Use different colors for students
        colors = ['28a745', 'dc3545', 'ffc107', '17a2b8', '6f42c1', 'fd7e14']
        color = colors[abs(hash(self.full_name)) % len(colors)]
        return f"https://ui-avatars.com/api/?name={initials}&background={color}&color=fff&size=200"

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

    def calculate_outstanding_fees(self):
        """Calculate outstanding fees"""
        fee_structure = self.get_fee_structure()
        if not fee_structure:
            return 0
        
        total_fee = fee_structure.get('total_fee', 0)
        amount_paid = fee_structure.get('amount_paid', 0)
        return max(0, total_fee - amount_paid)

    def get_monthly_fee_due(self, month=None, year=None):
        """Get monthly fee due amount"""
        from datetime import datetime
        
        if not month:
            month = datetime.now().month
        if not year:
            year = datetime.now().year
        
        fee_structure = self.get_fee_structure()
        if not fee_structure:
            return 0
        
        payment_schedule = fee_structure.get('payment_schedule', 'monthly')
        total_fee = fee_structure.get('total_fee', 0)
        
        if payment_schedule == 'monthly':
            return total_fee / 12
        elif payment_schedule == 'quarterly':
            return total_fee / 4
        else:
            return total_fee

    def add_fee_payment(self, amount, payment_mode, payment_date=None, notes='', recorded_by=None):
        """Add fee payment record and update installment plan"""
        from datetime import datetime
        from app import db
        
        fee_structure = self.get_fee_structure()
        current_paid = fee_structure.get('amount_paid', 0)
        
        # Update amounts
        fee_structure['amount_paid'] = current_paid + amount
        fee_structure['balance_amount'] = fee_structure.get('total_fee', 0) - fee_structure['amount_paid']
        
        # Add to history
        if 'payment_history' not in fee_structure:
            fee_structure['payment_history'] = []
        
        payment_record = {
            'id': len(fee_structure['payment_history']) + 1,
            'amount': amount,
            'payment_mode': payment_mode,
            'payment_date': payment_date.isoformat() if payment_date else datetime.now().date().isoformat(),
            'notes': notes,
            'recorded_by': recorded_by,
            'recorded_at': datetime.now().isoformat()
        }
        
        fee_structure['payment_history'].append(payment_record)
        
        # Update installment plan if exists
        self._update_installment_plan_after_payment(fee_structure, amount, payment_date or datetime.now().date())
        
        # Set the updated fee structure
        self.set_fee_structure(fee_structure)
        
        # Ensure database session is marked as dirty and will be committed
        db.session.add(self)
        
        return payment_record

    def create_installment_plan(self, installments):
        """Create installment payment plan
        installments: list of {'due_date': 'YYYY-MM-DD', 'amount': float, 'description': str}
        """
        from datetime import datetime
        
        fee_structure = self.get_fee_structure()
        total_planned = sum(inst['amount'] for inst in installments)
        
        # Calculate remaining balance (total fee minus amount already paid)
        remaining_balance = fee_structure.get('total_fee', 0) - fee_structure.get('amount_paid', 0)
        
        # Allow small floating point differences
        if abs(total_planned - remaining_balance) > 0.01:
            raise ValueError(f"Installment total ({total_planned}) doesn't match remaining balance ({remaining_balance})")
        
        # Create installment plan
        installment_plan = {
            'created_at': datetime.now().isoformat(),
            'total_installments': len(installments),
            'remaining_balance': remaining_balance,
            'installments': []
        }
        
        for i, inst in enumerate(installments, 1):
            installment_plan['installments'].append({
                'installment_number': i,
                'due_date': inst['due_date'],
                'amount': inst['amount'],
                'description': inst.get('description', f'Installment {i}'),
                'status': 'pending',
                'paid_amount': 0,
                'paid_date': None,
                'payment_method': None,
                'notes': ''
            })
        
        fee_structure['installment_plan'] = installment_plan
        self.set_fee_structure(fee_structure)
        
        return installment_plan

    def get_installment_plan(self):
        """Get current installment plan"""
        fee_structure = self.get_fee_structure()
        return fee_structure.get('installment_plan', {})

    def get_upcoming_installments(self, limit=3):
        """Get upcoming pending installments"""
        from datetime import datetime, date
        
        installment_plan = self.get_installment_plan()
        if not installment_plan:
            return []
        
        today = date.today()
        upcoming = []
        
        for inst in installment_plan.get('installments', []):
            if inst['status'] in ['pending', 'partial']:
                try:
                    due_date = datetime.fromisoformat(inst['due_date']).date()
                    if due_date >= today:
                        upcoming.append({
                            **inst,
                            'due_date_obj': due_date,
                            'days_until_due': (due_date - today).days,
                            'is_overdue': False
                        })
                except (ValueError, TypeError):
                    continue
        
        # Sort by due date
        upcoming.sort(key=lambda x: x['due_date_obj'])
        return upcoming[:limit]

    def get_overdue_installments(self):
        """Get overdue installments"""
        from datetime import datetime, date
        
        installment_plan = self.get_installment_plan()
        if not installment_plan:
            return []
        
        today = date.today()
        overdue = []
        
        for inst in installment_plan.get('installments', []):
            if inst['status'] in ['pending', 'partial']:
                try:
                    due_date = datetime.fromisoformat(inst['due_date']).date()
                    if due_date < today:
                        remaining_amount = inst['amount'] - inst.get('paid_amount', 0)
                        overdue.append({
                            **inst,
                            'due_date_obj': due_date,
                            'days_overdue': (today - due_date).days,
                            'remaining_amount': remaining_amount,
                            'is_overdue': True
                        })
                except (ValueError, TypeError):
                    continue
        
        # Sort by days overdue (most overdue first)
        overdue.sort(key=lambda x: x['days_overdue'], reverse=True)
        return overdue

    def get_installment_summary(self):
        """Get summary of installment plan"""
        installment_plan = self.get_installment_plan()
        if not installment_plan:
            return {
                'has_plan': False,
                'total_installments': 0,
                'completed': 0,
                'pending': 0,
                'overdue': 0,
                'next_due_amount': 0,
                'next_due_date': None
            }
        
        installments = installment_plan.get('installments', [])
        completed = sum(1 for inst in installments if inst['status'] == 'completed')
        pending = sum(1 for inst in installments if inst['status'] in ['pending', 'partial'])
        overdue = len(self.get_overdue_installments())
        
        upcoming = self.get_upcoming_installments(1)
        next_due_amount = upcoming[0]['amount'] - upcoming[0].get('paid_amount', 0) if upcoming else 0
        next_due_date = upcoming[0]['due_date'] if upcoming else None
        
        return {
            'has_plan': True,
            'total_installments': len(installments),
            'completed': completed,
            'pending': pending,
            'overdue': overdue,
            'next_due_amount': next_due_amount,
            'next_due_date': next_due_date
        }

    def _update_installment_plan_after_payment(self, fee_structure, payment_amount, payment_date):
        """Update installment plan after a payment is made"""
        from datetime import datetime
        
        if 'installment_plan' not in fee_structure:
            return
        
        installments = fee_structure['installment_plan'].get('installments', [])
        remaining_payment = float(payment_amount)
        
        # Apply payment to pending installments in order
        for inst in installments:
            if remaining_payment <= 0:
                break
                
            if inst['status'] in ['pending', 'partial']:
                remaining_due = float(inst['amount']) - float(inst.get('paid_amount', 0))
                
                if remaining_payment >= remaining_due:
                    # Complete this installment
                    inst['paid_amount'] = float(inst['amount'])
                    inst['status'] = 'completed'
                    inst['paid_date'] = payment_date.isoformat() if hasattr(payment_date, 'isoformat') else str(payment_date)
                    remaining_payment -= remaining_due
                else:
                    # Partial payment
                    inst['paid_amount'] = float(inst.get('paid_amount', 0)) + remaining_payment
                    inst['status'] = 'partial'
                    if not inst.get('paid_date'):
                        inst['paid_date'] = payment_date.isoformat() if hasattr(payment_date, 'isoformat') else str(payment_date)
                    remaining_payment = 0
        
        # Mark the installment plan as updated
        fee_structure['installment_plan']['last_updated'] = datetime.now().isoformat()

    def update_installment_plan(self, new_installments):
        """Update existing installment plan"""
        fee_structure = self.get_fee_structure()
        current_plan = fee_structure.get('installment_plan', {})
        
        if not current_plan:
            return self.create_installment_plan(new_installments)
        
        # Preserve payment history but update future installments
        current_installments = current_plan.get('installments', [])
        completed_payments = sum(inst.get('paid_amount', 0) for inst in current_installments)
        
        # Create new plan
        from datetime import datetime
        updated_plan = {
            'created_at': current_plan.get('created_at', datetime.now().isoformat()),
            'updated_at': datetime.now().isoformat(),
            'total_installments': len(new_installments),
            'installments': []
        }
        
        remaining_balance = fee_structure.get('total_fee', 0) - completed_payments
        total_new_planned = sum(inst['amount'] for inst in new_installments)
        
        if abs(total_new_planned - remaining_balance) > 0.01:  # Allow small floating point differences
            raise ValueError(f"New installment total ({total_new_planned}) doesn't match remaining balance ({remaining_balance})")
        
        # Add updated installments
        for i, inst in enumerate(new_installments, 1):
            updated_plan['installments'].append({
                'installment_number': i,
                'due_date': inst['due_date'],
                'amount': inst['amount'],
                'description': inst.get('description', f'Updated Installment {i}'),
                'status': 'pending',
                'paid_amount': 0,
                'paid_date': None,
                'payment_method': None,
                'notes': inst.get('notes', '')
            })
        
        fee_structure['installment_plan'] = updated_plan
        self.set_fee_structure(fee_structure)
        
        return updated_plan

    def get_monthly_fee_status(self):
        """Get monthly fee status for current month"""
        fee_structure = self.get_fee_structure()
        monthly_status = fee_structure.get('monthly_fee_status', {})
        
        from datetime import date
        current_month = date.today().strftime('%Y-%m')
        
        return monthly_status.get(current_month, {
            'status': 'pending',
            'due_date': None,
            'amount': 0,
            'notes': ''
        })

    def set_monthly_fee_status(self, month, status_data):
        """Set monthly fee status for a specific month
        Args:
            month: 'YYYY-MM' format
            status_data: {'status': 'paid/pending/overdue/exempted', 'due_date': 'YYYY-MM-DD', 'amount': float, 'notes': str}
        """
        fee_structure = self.get_fee_structure()
        
        if 'monthly_fee_status' not in fee_structure:
            fee_structure['monthly_fee_status'] = {}
        
        fee_structure['monthly_fee_status'][month] = status_data
        self.set_fee_structure(fee_structure)

    def get_monthly_fee_history(self, months=12):
        """Get monthly fee status history"""
        
        fee_structure = self.get_fee_structure()
        monthly_status = fee_structure.get('monthly_fee_status', {})
        
        history = []
        current_date = date.today()
        
        for i in range(months):
            month_date = current_date - relativedelta(months=i)
            month_key = month_date.strftime('%Y-%m')
            month_name = month_date.strftime('%B %Y')
            
            status_data = monthly_status.get(month_key, {
                'status': 'pending',
                'due_date': None,
                'amount': 0,
                'notes': ''
            })
            
            history.append({
                'month': month_key,
                'month_name': month_name,
                'status': status_data.get('status', 'pending'),
                'due_date': status_data.get('due_date'),
                'amount': status_data.get('amount', 0),
                'notes': status_data.get('notes', ''),
                'is_current': month_key == current_date.strftime('%Y-%m')
            })
        
        return history

    def update_monthly_fee_status_bulk(self, monthly_updates):
        """Update multiple months' fee status at once
        Args:
            monthly_updates: [{'month': 'YYYY-MM', 'status': '...', 'amount': float, ...}, ...]
        """
        fee_structure = self.get_fee_structure()
        
        if 'monthly_fee_status' not in fee_structure:
            fee_structure['monthly_fee_status'] = {}
        
        for update in monthly_updates:
            month = update.get('month')
            if month:
                status_data = {
                    'status': update.get('status', 'pending'),
                    'due_date': update.get('due_date'),
                    'amount': update.get('amount', 0),
                    'notes': update.get('notes', '')
                }
                fee_structure['monthly_fee_status'][month] = status_data
        
        self.set_fee_structure(fee_structure)
        return len(monthly_updates)

    def get_fee_payment_history(self):
        """Get fee payment history"""
        from datetime import datetime
        
        fee_structure = self.get_fee_structure()
        payment_history = fee_structure.get('payment_history', [])
        
        # If payment history is empty but amount_paid > 0, it means old data needs migration
        if not payment_history and fee_structure.get('amount_paid', 0) > 0:
            # Create a historical entry for existing payments
            payment_history = [{
                'id': 1,
                'amount': fee_structure.get('amount_paid', 0),
                'payment_mode': fee_structure.get('payment_mode', 'unknown'),
                'payment_date': datetime.now().date().isoformat(),
                'notes': 'Historical payment record (migrated)',
                'recorded_by': 'System Migration',
                'recorded_at': datetime.now().isoformat()
            }]
            
            # Update fee structure with migrated history
            fee_structure['payment_history'] = payment_history
            self.set_fee_structure(fee_structure)
            
            # Commit the migration
            from app import db
            db.session.add(self)
            try:
                db.session.commit()
            except:
                db.session.rollback()
        
        return payment_history

    def get_next_payment_info(self):
        """Get information about the next payment due"""
        # First check if there's an installment plan
        installment_summary = self.get_installment_summary()
        if installment_summary.get('has_plan') and installment_summary.get('next_due_amount', 0) > 0:
            return {
                'next_due_amount': installment_summary.get('next_due_amount', 0),
                'next_due_date': installment_summary.get('next_due_date'),
                'source': 'installment_plan'
            }
        
        # If no installment plan, check for outstanding balance
        outstanding = self.calculate_outstanding_fees()
        if outstanding > 0:
            return {
                'next_due_amount': outstanding,
                'next_due_date': None,
                'source': 'outstanding_balance'
            }
        
        # No payments due
        return {
            'next_due_amount': 0,
            'next_due_date': None,
            'source': 'none'
        }
    
    # ================== MONTHLY FEE TRACKING ==================
    
    def get_monthly_fee_status(self, month=None, year=None):
        """Get monthly fee status (paid, pending, overdue)"""
        from datetime import datetime, date
        
        if not month:
            month = datetime.now().month
        if not year:
            year = datetime.now().year
            
        # Check if future fees were cancelled (student dropped)
        if self._is_month_fee_cancelled(month, year):
            return 'cancelled'
            
        # Check if course was active during this month
        check_date = date(year, month, 15)  # Mid-month check
        if not self.is_course_active(check_date):
            return 'not_applicable'
        
        monthly_due = self.get_monthly_fee_due(month, year)
        monthly_paid = self.get_monthly_fee_paid(month, year)
        
        if monthly_paid >= monthly_due:
            return 'paid'
        elif date(year, month, 1) < date.today():
            return 'overdue'
        else:
            return 'pending'
    
    def get_monthly_fee_paid(self, month=None, year=None):
        """Get amount paid for a specific month"""
        from datetime import datetime, date
        
        if not month:
            month = datetime.now().month
        if not year:
            year = datetime.now().year
        
        payment_history = self.get_fee_payment_history()
        monthly_paid = 0
        
        # Calculate payments made for this month
        for payment in payment_history:
            try:
                payment_date = datetime.fromisoformat(payment.get('payment_date', '')).date()
                if payment_date.year == year and payment_date.month == month:
                    monthly_paid += payment.get('amount', 0)
            except (ValueError, AttributeError):
                continue
        
        return monthly_paid
    
    def get_monthly_fees_summary(self, start_month=None, start_year=None, months_count=12):
        """Get summary of monthly fees for a period"""
        from datetime import datetime, date
        from dateutil.relativedelta import relativedelta
        
        if not start_month or not start_year:
            start_month = datetime.now().month
            start_year = datetime.now().year
        
        summary = []
        current_date = date(start_year, start_month, 1)
        
        for i in range(months_count):
            month_data = {
                'month': current_date.month,
                'year': current_date.year,
                'month_name': current_date.strftime('%B'),
                'due_amount': self.get_monthly_fee_due(current_date.month, current_date.year),
                'paid_amount': self.get_monthly_fee_paid(current_date.month, current_date.year),
                'status': self.get_monthly_fee_status(current_date.month, current_date.year)
            }
            month_data['outstanding'] = month_data['due_amount'] - month_data['paid_amount']
            summary.append(month_data)
            
            # Move to next month
            current_date = current_date + relativedelta(months=1)
        
        return summary
    
    def get_overdue_months(self):
        """Get list of months with overdue fees"""
        from datetime import datetime, date
        from dateutil.relativedelta import relativedelta
        
        overdue_months = []
        
        # Check from course start date or 12 months ago, whichever is later
        start_date = self.course_start_date or date.today() - relativedelta(months=12)
        current_date = date(start_date.year, start_date.month, 1)
        today = date.today()
        
        while current_date < today:
            if self.get_monthly_fee_status(current_date.month, current_date.year) == 'overdue':
                due_amount = self.get_monthly_fee_due(current_date.month, current_date.year)
                paid_amount = self.get_monthly_fee_paid(current_date.month, current_date.year)
                
                overdue_months.append({
                    'month': current_date.month,
                    'year': current_date.year,
                    'month_name': current_date.strftime('%B'),
                    'due_amount': due_amount,
                    'paid_amount': paid_amount,
                    'outstanding': due_amount - paid_amount
                })
            
            current_date = current_date + relativedelta(months=1)
        
        return overdue_months
    
    def _is_month_fee_cancelled(self, month, year):
        """Check if fees for a specific month were cancelled due to drop"""
        from datetime import date
        
        fee_structure = self.get_fee_structure()
        
        # Check if future fees are cancelled
        if not fee_structure.get('future_fees_cancelled', False):
            return False
        
        cancellations = fee_structure.get('cancellations', [])
        check_month = date(year, month, 1)
        
        for cancellation in cancellations:
            if cancellation.get('type') == 'drop_cancellation':
                try:
                    cancelled_from = date.fromisoformat(cancellation.get('cancelled_from_month', ''))
                    if check_month >= cancelled_from:
                        return True
                except (ValueError, TypeError):
                    continue
        
        return False

    def is_course_active(self, check_date=None):
        """Check if student's course is active on given date"""
        if check_date is None:
            check_date = date.today()
        
        # Must have started
        if not self.course_start_date or self.course_start_date > check_date:
            return False
        
        # Check if not ended
        if self.course_end_date and self.course_end_date < check_date:
            return False
        
        # Check enrollment status
        return self.enrollment_status == 'active'

    def get_course_progress(self):
        """Get course progress percentage"""
        if not self.course_start_date or not self.course_end_date:
            return None
        
        total_days = (self.course_end_date - self.course_start_date).days
        if total_days <= 0:
            return 100
        
        elapsed_days = (date.today() - self.course_start_date).days
        progress = min(100, max(0, (elapsed_days / total_days) * 100))
        
        return round(progress, 1)

    def set_course_duration(self, months):
        """Set course duration and auto-calculate end date"""
        self.course_duration_months = months
        if self.course_start_date and months:
            from datetime import timedelta
            # Approximate: 30 days per month
            self.course_end_date = self.course_start_date + timedelta(days=months * 30)

    def get_batch_identifier(self):
        """Get or generate batch identifier"""
        if self.batch_identifier:
            return self.batch_identifier
        
        # Auto-generate if not set
        if self.course_start_date:
            month_year = self.course_start_date.strftime('%b-%Y')
            subjects = self.get_subjects_enrolled()
            if subjects:
                subject = subjects[0].replace(' ', '-')
                return f"{subject}-{month_year}"
        
        return f"Batch-{self.id}"

    def should_attend_class_on(self, class_date):
        """Check if student should attend class on given date"""
        return (
            self.is_course_active(class_date) and 
            self.enrollment_status == 'active' and 
            self.is_active
        )

    # ================== GRADUATION AND DROP FUNCTIONALITY ==================
    
    def can_graduate(self, manual_override=False):
        """Check if student is eligible for graduation"""
        # Check if student is on graduation hold
        if self.enrollment_status == 'hold_graduation':
            return False, "Student graduation is on hold - requires manual review"
        
        if self.enrollment_status not in ['active', 'hold_graduation']:
            return False, "Student must be in active status to graduate"
        
        # Manual override bypasses all automatic checks
        if manual_override:
            return True, "Manual override - eligibility checks bypassed by administrator"
        
        # Only check fee payment status
        fee_status = self.get_fee_status()
        if fee_status not in ['paid', 'unknown']:  # Allow unknown for flexibility
            balance = self.get_balance_amount()
            if balance > 0:
                return False, f"Outstanding fee balance: Rs.{balance:,.2f} must be cleared"
        
        return True, "Student is eligible for graduation"
    
    def graduate_student(self, final_grade=None, graduation_date=None, user_id=None,
                        feedback=None, achievements=None, performance_rating='good',
                        issue_certificate=True, manual_override=False, override_reason=None):
        """Graduate the student"""
        from app.models.student_graduation import StudentGraduation
        from app.models.student_status_history import StudentStatusHistory
        
        # Check eligibility (with manual override option)
        can_grad, reason = self.can_graduate(manual_override=manual_override)
        if not can_grad and not manual_override:
            raise ValueError(f"Cannot graduate student: {reason}")
        
        # Store old status for history
        old_status = self.enrollment_status
        old_is_active = self.is_active
        
        # Set graduation details
        self.enrollment_status = 'completed'
        graduation_date = graduation_date or date.today()
        
        # Create graduation record with current performance metrics
        graduation = StudentGraduation(
            student_id=self.id,
            graduation_date=graduation_date,
            final_grade=final_grade,
            overall_performance_rating=performance_rating,
            completion_percentage=self.get_attendance_percentage(),
            total_classes_attended=self.attended_classes,
            total_classes_scheduled=self.total_classes,
            attendance_percentage=self.get_attendance_percentage(),
            feedback=feedback,
            graduated_by=user_id,
            certificate_issued=issue_certificate
        )
        
        # Set achievements if provided
        if achievements:
            graduation.set_achievements(achievements)
        
        db.session.add(graduation)
        db.session.flush()  # Get the graduation ID
        
        # Log status change
        StudentStatusHistory.log_status_change(
            student_id=self.id,
            old_status=old_status,
            new_status='completed',
            old_is_active=old_is_active,
            new_is_active=self.is_active,
            reason=f"Student graduated with grade: {final_grade or 'Not specified'}",
            changed_by_user_id=user_id,
            change_method='manual',
            effective_date=graduation_date,
            notes=f"Graduation completed. Performance: {performance_rating}",
            graduation_id=graduation.id
        )
        
        db.session.commit()
        return graduation
    
    def drop_student(self, drop_reason, detailed_reason, drop_date=None, 
                    dropped_by=None, refund_amount=0, refund_reason=None,
                    exit_interview_notes=None, re_enrollment_allowed=True,
                    blacklist=False, cancel_future_classes=True,
                    internal_notes=None, manual_override=False, override_reason=None):
        """Drop the student from the course"""
        from app.models.student_drop import StudentDrop
        from app.models.student_status_history import StudentStatusHistory
        
        # Clear any pending transactions to avoid rollback issues
        try:
            db.session.rollback()
        except Exception:
            pass  # Ignore if no transaction to rollback
        
        try:
            # Check if student can be dropped (with manual override option)
            can_drop, reason = self.can_drop(manual_override=manual_override)
            if not can_drop and not manual_override:
                raise ValueError(f"Cannot drop student: {reason}")
            
            # Store old status for history
            old_status = self.enrollment_status
            old_is_active = self.is_active
            
            # Set drop details
            self.enrollment_status = 'dropped'
            self.is_active = False
            drop_date = drop_date or date.today()
            
            # Create drop record with current performance metrics
            drop_record = StudentDrop(
                student_id=self.id,
                drop_date=drop_date,
                drop_reason=drop_reason,
                detailed_reason=detailed_reason,
                dropped_by=dropped_by,
                refund_amount=refund_amount,
                refund_reason=refund_reason,
                exit_interview_notes=exit_interview_notes,
                re_enrollment_allowed=re_enrollment_allowed,
                blacklisted=blacklist,
                attendance_at_drop=self.get_attendance_percentage(),
                classes_attended=self.attended_classes,
                classes_scheduled=self.total_classes,
                course_completion_percentage=self.get_course_progress(),
                internal_notes=internal_notes,
                future_classes_cancelled=cancel_future_classes
            )
            
            db.session.add(drop_record)
            db.session.flush()  # Get the drop ID
            
            # Cancel future classes if requested
            if cancel_future_classes:
                cancelled_count = self._cancel_future_classes()
                drop_record.cancelled_classes_count = cancelled_count
            
            # Cancel future fee obligations
            self._cancel_future_fee_obligations(drop_date)
            
            # Log status change
            StudentStatusHistory.log_status_change(
                student_id=self.id,
                old_status=old_status,
                new_status='dropped',
                old_is_active=old_is_active,
                new_is_active=False,
                reason=f"Student dropped - {drop_reason}: {detailed_reason}",
                changed_by_user_id=dropped_by,
                change_method='manual',
                effective_date=drop_date,
                notes=f"Drop reason: {drop_reason}. Refund: ₹{refund_amount or 0}",
                drop_id=drop_record.id
            )
            
            db.session.commit()
            return drop_record
            
        except Exception as e:
            db.session.rollback()
            raise e
    
    def reactivate_student(self, reactivated_by, reason, reactivation_date=None,
                          reset_attendance=False, new_course_start_date=None,
                          special_conditions=None):
        """Reactivate a dropped or paused student"""
        from app.models.student_status_history import StudentStatusHistory
        
        if self.enrollment_status not in ['dropped', 'paused']:
            raise ValueError("Can only reactivate dropped or paused students")
        
        # Store old status for history
        old_status = self.enrollment_status
        old_is_active = self.is_active
        
        # Reactivate student
        self.enrollment_status = 'active'
        self.is_active = True
        reactivation_date = reactivation_date or date.today()
        
        # Reset attendance if requested
        if reset_attendance:
            self.attended_classes = 0
            self.total_classes = 0
        
        # Update course start date if provided
        if new_course_start_date:
            self.course_start_date = new_course_start_date
        
        # Log status change
        StudentStatusHistory.log_status_change(
            student_id=self.id,
            old_status=old_status,
            new_status='active',
            old_is_active=old_is_active,
            new_is_active=True,
            reason=reason,
            changed_by_user_id=reactivated_by,
            change_method='manual',
            effective_date=reactivation_date,
            notes=special_conditions or "Student reactivated"
        )
        
        db.session.commit()
        return True
    
    def _cancel_future_classes(self):
        """Cancel all future classes for this student"""
        from app.models.class_model import Class
        
        try:
            # Cancel future classes where this student is the primary student
            future_classes = Class.query.filter(
                Class.primary_student_id == self.id,
                Class.scheduled_date >= date.today(),
                Class.status.in_(['scheduled'])
            ).all()
            
            cancelled_count = 0
            for cls in future_classes:
                cls.status = 'cancelled'
                # Use shorter value as fallback for compatibility
                cls.completion_status = 'cancelled_dropped'  # 17 chars, fits in old 20-char limit
                cancelled_count += 1
            
            # Also handle group classes - this would need to be implemented based on your group class structure
            # For now, we'll just handle primary student classes
            
            return cancelled_count
            
        except Exception as e:
            # Log the error but don't raise it - allow the drop to continue
            print(f"Error cancelling future classes for student {self.id}: {str(e)}")
            return 0
    
    def _cancel_future_fee_obligations(self, drop_date):
        """Cancel future fee obligations from drop date onwards"""
        from datetime import date
        from dateutil.relativedelta import relativedelta
        
        fee_structure = self.get_fee_structure()
        
        # Add cancellation record to fee structure
        if 'cancellations' not in fee_structure:
            fee_structure['cancellations'] = []
        
        # Calculate months to cancel (from drop month onwards)
        current_month = date.today()
        drop_month = date(drop_date.year, drop_date.month, 1)
        
        # If dropped mid-month, still charge for current month, cancel from next month
        cancel_from_month = drop_month + relativedelta(months=1)
        
        # Calculate cancellation info
        cancellation_record = {
            'type': 'drop_cancellation',
            'drop_date': drop_date.isoformat(),
            'cancelled_from_month': cancel_from_month.isoformat(),
            'reason': f'Student dropped on {drop_date.strftime("%d %B %Y")}',
            'created_at': date.today().isoformat()
        }
        
        fee_structure['cancellations'].append(cancellation_record)
        
        # Mark student as having no future fee obligations
        fee_structure['future_fees_cancelled'] = True
        fee_structure['future_fees_cancelled_date'] = drop_date.isoformat()
        
        self.set_fee_structure(fee_structure)
        
        return True
    
    def get_graduation_record(self):
        """Get student's graduation record if exists"""
        from app.models.student_graduation import StudentGraduation
        return StudentGraduation.query.filter_by(student_id=self.id).first()
    
    def get_drop_record(self):
        """Get student's drop record if exists"""
        from app.models.student_drop import StudentDrop
        return StudentDrop.query.filter_by(student_id=self.id).first()
    
    def get_status_history(self, limit=10):
        """Get student's status change history"""
        from app.models.student_status_history import StudentStatusHistory
        return StudentStatusHistory.query.filter_by(student_id=self.id)\
                                        .order_by(StudentStatusHistory.created_at.desc())\
                                        .limit(limit).all()
    
    # ================== HOLD FUNCTIONALITY ==================
    
    def put_graduation_on_hold(self, reason, user_id, notes=None):
        """Put student graduation on hold"""
        from app.models.student_status_history import StudentStatusHistory
        
        if self.enrollment_status not in ['active']:
            raise ValueError("Can only put active students' graduation on hold")
        
        old_status = self.enrollment_status
        old_is_active = self.is_active
        
        self.enrollment_status = 'hold_graduation'
        
        # Log the hold
        StudentStatusHistory.log_status_change(
            student_id=self.id,
            old_status=old_status,
            new_status='hold_graduation',
            old_is_active=old_is_active,
            new_is_active=self.is_active,
            reason=f"Graduation put on hold: {reason}",
            changed_by_user_id=user_id,
            change_method='manual',
            notes=notes or f"Graduation hold applied: {reason}"
        )
        
        db.session.commit()
        return True
    
    def put_drop_on_hold(self, reason, user_id, notes=None):
        """Put student drop on hold (prevent dropping)"""
        from app.models.student_status_history import StudentStatusHistory
        
        if self.enrollment_status not in ['active']:
            raise ValueError("Can only put active students' drop on hold")
        
        old_status = self.enrollment_status
        old_is_active = self.is_active
        
        self.enrollment_status = 'hold_drop'
        
        # Log the hold
        StudentStatusHistory.log_status_change(
            student_id=self.id,
            old_status=old_status,
            new_status='hold_drop',
            old_is_active=old_is_active,
            new_is_active=self.is_active,
            reason=f"Drop put on hold: {reason}",
            changed_by_user_id=user_id,
            change_method='manual',
            notes=notes or f"Drop hold applied: {reason}"
        )
        
        db.session.commit()
        return True
    
    def remove_hold(self, user_id, reason, notes=None):
        """Remove hold status and return student to active"""
        from app.models.student_status_history import StudentStatusHistory
        
        if self.enrollment_status not in ['hold_graduation', 'hold_drop']:
            raise ValueError("Student is not currently on hold")
        
        old_status = self.enrollment_status
        old_is_active = self.is_active
        
        self.enrollment_status = 'active'
        
        # Log the hold removal
        StudentStatusHistory.log_status_change(
            student_id=self.id,
            old_status=old_status,
            new_status='active',
            old_is_active=old_is_active,
            new_is_active=self.is_active,
            reason=f"Hold removed: {reason}",
            changed_by_user_id=user_id,
            change_method='manual',
            notes=notes or f"Hold removed and student reactivated: {reason}"
        )
        
        db.session.commit()
        return True
    
    def can_drop(self, manual_override=False):
        """Check if student can be dropped"""
        # Check if student is on drop hold
        if self.enrollment_status == 'hold_drop':
            return False, "Student drop is on hold - requires manual review"
        
        if self.enrollment_status not in ['active', 'paused', 'hold_drop']:
            return False, "Student is not in a status that allows dropping"
        
        # Manual override bypasses all checks
        if manual_override:
            return True, "Manual override - drop restrictions bypassed by administrator"
        
        return True, "Student can be dropped"
    
    def get_hold_status(self):
        """Get current hold status information"""
        if self.enrollment_status in ['hold_graduation', 'hold_drop']:
            # Get the most recent status history entry for this hold
            from app.models.student_status_history import StudentStatusHistory
            recent_history = StudentStatusHistory.query.filter_by(
                student_id=self.id,
                new_status=self.enrollment_status
            ).order_by(StudentStatusHistory.created_at.desc()).first()
            
            return {
                'is_on_hold': True,
                'hold_type': self.enrollment_status,
                'hold_applied_date': recent_history.created_at if recent_history else None,
                'hold_reason': recent_history.change_reason if recent_history else 'Unknown',
                'hold_applied_by': recent_history.changed_by_user.full_name if recent_history and recent_history.changed_by_user else 'Unknown'
            }
        
        return {
            'is_on_hold': False,
            'hold_type': None,
            'hold_applied_date': None,
            'hold_reason': None,
            'hold_applied_by': None
        }
    
    def get_lifecycle_summary(self):
        """Get comprehensive lifecycle summary"""
        summary = {
            'current_status': self.enrollment_status,
            'is_active': self.is_active,
            'course_duration_days': None,
            'attendance_rate': self.get_attendance_percentage(),
            'fee_status': self.get_fee_status(),
            'balance_amount': self.get_balance_amount(),
            'graduation_eligible': False,
            'graduation_eligibility_reason': '',
            'has_graduated': False,
            'has_dropped': False,
            'graduation_record': None,
            'drop_record': None
        }
        
        # Calculate course duration
        if self.course_start_date:
            summary['course_duration_days'] = (date.today() - self.course_start_date).days
        
        # Check graduation eligibility
        can_grad, reason = self.can_graduate()
        summary['graduation_eligible'] = can_grad
        summary['graduation_eligibility_reason'] = reason
        
        # Check for graduation record
        graduation = self.get_graduation_record()
        if graduation:
            summary['has_graduated'] = True
            summary['graduation_record'] = graduation.to_dict()
        
        # Check for drop record
        drop_record = self.get_drop_record()
        if drop_record:
            summary['has_dropped'] = True
            summary['drop_record'] = drop_record.to_dict()
        
        return summary