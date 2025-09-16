"""
Base forms with centralized validation and common functionality
Eliminates code duplication across form files
"""
from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, ValidationError
from app.models.department import Department
from app.services.validation_service import ValidationService


class BaseForm(FlaskForm):
    """Base form with common functionality"""
    
    def __init__(self, *args, **kwargs):
        super(BaseForm, self).__init__(*args, **kwargs)
        self._populate_dynamic_choices()
    
    def _populate_dynamic_choices(self):
        """Populate dynamic choice fields - override in subclasses"""
        pass
    
    def validate_with_service(self, validation_func):
        """Use ValidationService for complex validation"""
        if not super().validate():
            return False
        
        # Get form data
        data = {field.name: field.data for field in self}
        
        # Use validation service
        errors = validation_func(data)
        
        if errors:
            for field_name, field_errors in errors.items():
                if hasattr(self, field_name):
                    field = getattr(self, field_name)
                    for error in field_errors:
                        field.errors.append(error)
            return False
        
        return True


class DepartmentMixin:
    """Mixin for forms that need department selection"""
    
    department_id = SelectField(
        'Department',
        coerce=int,
        validators=[DataRequired(message="Please select a department")]
    )
    
    def populate_department_choices(self, user_role=None, user_department_id=None):
        """Populate department choices based on user permissions"""
        if user_role == 'coordinator' and user_department_id:
            # Coordinators can only see their department
            departments = Department.query.filter_by(
                id=user_department_id, 
                is_active=True
            ).all()
        else:
            # Admins and superadmins can see all active departments
            departments = Department.query.filter_by(is_active=True).order_by(Department.name).all()
        
        self.department_id.choices = [
            (dept.id, dept.name) for dept in departments
        ]
        
        # If only one department available, pre-select it
        if len(departments) == 1:
            self.department_id.data = departments[0].id


class BaseUserForm(BaseForm, DepartmentMixin):
    """Base form for user-related forms"""
    
    full_name = StringField(
        'Full Name', 
        validators=[DataRequired(message="Full name is required")]
    )
    
    email = StringField(
        'Email', 
        validators=[DataRequired(message="Email is required")]
    )
    
    phone = StringField('Phone Number')
    
    def validate_full_name(self, field):
        """Validate full name using ValidationService"""
        is_valid, error = ValidationService.validate_name(field.data, 'Full Name')
        if not is_valid:
            raise ValidationError(error)
    
    def validate_email(self, field):
        """Validate email using ValidationService"""
        is_valid, error = ValidationService.validate_email(field.data)
        if not is_valid:
            raise ValidationError(error)
        
        # Check for uniqueness if this is a new user
        from app.models.user import User
        existing_user = User.query.filter(User.email.ilike(field.data)).first()
        
        # For edit forms, exclude current user from uniqueness check
        if hasattr(self, 'user_id') and self.user_id:
            existing_user = User.query.filter(
                User.email.ilike(field.data),
                User.id != self.user_id
            ).first()
        
        if existing_user:
            raise ValidationError('Email address already registered')
    
    def validate_phone(self, field):
        """Validate phone using ValidationService"""
        if field.data:  # Phone is optional in base form
            is_valid, error = ValidationService.validate_phone(field.data, required=False)
            if not is_valid:
                raise ValidationError(error)
    
    def _populate_dynamic_choices(self):
        """Populate department choices"""
        from flask_login import current_user
        if current_user.is_authenticated:
            self.populate_department_choices(
                current_user.role, 
                current_user.department_id
            )


class BaseStudentForm(BaseForm):
    """Base form for student-related forms"""
    
    grade = SelectField(
        'Grade',
        choices=[
            ('', 'Select Grade'),
            ('1', 'Grade 1'), ('2', 'Grade 2'), ('3', 'Grade 3'),
            ('4', 'Grade 4'), ('5', 'Grade 5'), ('6', 'Grade 6'),
            ('7', 'Grade 7'), ('8', 'Grade 8'), ('9', 'Grade 9'),
            ('10', 'Grade 10'), ('11', 'Grade 11'), ('12', 'Grade 12')
        ],
        validators=[DataRequired(message="Please select a grade")]
    )
    
    board = SelectField(
        'Board',
        choices=[
            ('', 'Select Board'),
            ('CBSE', 'CBSE'),
            ('ICSE', 'ICSE'),
            ('State Board', 'State Board'),
            ('IB', 'International Baccalaureate (IB)'),
            ('IGCSE', 'IGCSE'),
            ('Other', 'Other')
        ],
        validators=[DataRequired(message="Please select a board")]
    )
    
    school_name = StringField('School Name')
    address = TextAreaField('Address')
    state = StringField('State')
    pin_code = StringField('PIN Code')
    
    def validate_grade(self, field):
        """Validate grade selection"""
        valid_grades = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12']
        is_valid, error = ValidationService.validate_choice(
            field.data, valid_grades, 'Grade'
        )
        if not is_valid:
            raise ValidationError(error)
    
    def validate_board(self, field):
        """Validate board selection"""
        valid_boards = ['CBSE', 'ICSE', 'State Board', 'IB', 'IGCSE', 'Other']
        is_valid, error = ValidationService.validate_choice(
            field.data, valid_boards, 'Board'
        )
        if not is_valid:
            raise ValidationError(error)
    
    def validate_pin_code(self, field):
        """Validate PIN code if provided"""
        if field.data:
            import re
            if not re.match(r'^\d{6}$', field.data):
                raise ValidationError('PIN code must be 6 digits')


class BaseClassForm(BaseForm):
    """Base form for class-related forms"""
    
    subject = StringField(
        'Subject',
        validators=[DataRequired(message="Subject is required")]
    )
    
    class_type = SelectField(
        'Class Type',
        choices=[
            ('', 'Select Type'),
            ('one_on_one', 'One-on-One'),
            ('group', 'Group Class'),
            ('demo', 'Demo Class')
        ],
        validators=[DataRequired(message="Please select class type")]
    )
    
    platform = SelectField(
        'Platform',
        choices=[
            ('', 'Select Platform'),
            ('zoom', 'Zoom'),
            ('google_meet', 'Google Meet'),
            ('teams', 'Microsoft Teams'),
            ('other', 'Other')
        ]
    )
    
    meeting_link = StringField('Meeting Link')
    class_notes = TextAreaField('Class Notes')
    
    def validate_subject(self, field):
        """Validate subject name"""
        if not field.data or len(field.data.strip()) < 2:
            raise ValidationError('Subject must be at least 2 characters long')
        
        if len(field.data) > 100:
            raise ValidationError('Subject name is too long')
    
    def validate_class_type(self, field):
        """Validate class type"""
        valid_types = ['one_on_one', 'group', 'demo']
        is_valid, error = ValidationService.validate_choice(
            field.data, valid_types, 'Class Type'
        )
        if not is_valid:
            raise ValidationError(error)
    
    def validate_meeting_link(self, field):
        """Validate meeting link if provided"""
        if field.data:
            import re
            url_pattern = re.compile(
                r'^https?://'  # http:// or https://
                r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
                r'localhost|'  # localhost...
                r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
                r'(?::\d+)?'  # optional port
                r'(?:/?|[/?]\S+)$', re.IGNORECASE
            )
            if not url_pattern.match(field.data):
                raise ValidationError('Please enter a valid URL')


class SearchForm(BaseForm):
    """Base form for search functionality"""
    
    search = StringField('Search')
    page = StringField('Page', default='1')
    per_page = SelectField(
        'Results per page',
        choices=[('10', '10'), ('20', '20'), ('50', '50'), ('100', '100')],
        default='20'
    )
    
    def get_search_terms(self):
        """Get cleaned search terms"""
        if not self.search.data:
            return []
        
        # Split by space and filter empty strings
        terms = [term.strip() for term in self.search.data.split() if term.strip()]
        return terms
    
    def get_pagination_params(self):
        """Get pagination parameters"""
        try:
            page = int(self.page.data or 1)
            per_page = int(self.per_page.data or 20)
        except (ValueError, TypeError):
            page = 1
            per_page = 20
        
        return {
            'page': max(1, page),
            'per_page': min(100, max(10, per_page))  # Limit between 10-100
        }


# Helper functions for dynamic form population

def get_subject_choices():
    """Get unique subjects from students for dropdown"""
    from app.models.student import Student
    
    all_subjects = set()
    students = Student.query.all()
    
    for student in students:
        subjects = student.get_subjects_enrolled()
        all_subjects.update(subjects)
    
    # Add common subjects if none exist
    if not all_subjects:
        all_subjects = {
            'Mathematics', 'Physics', 'Chemistry', 'Biology', 'English',
            'Hindi', 'History', 'Geography', 'Economics', 'Computer Science',
            'Accountancy', 'Business Studies', 'Political Science', 'Sociology'
        }
    
    # Convert to choices format
    choices = [('', 'Select Subject')]
    choices.extend([(subject, subject) for subject in sorted(all_subjects)])
    
    return choices


def get_tutor_choices(department_id=None):
    """Get active tutors for dropdown"""
    from app.models.tutor import Tutor
    
    query = Tutor.query.filter_by(status='active').join('user')
    
    if department_id:
        query = query.filter_by(department_id=department_id)
    
    tutors = query.all()
    
    choices = [('', 'Select Tutor')]
    choices.extend([
        (tutor.id, tutor.user.full_name if tutor.user else f'Tutor {tutor.id}')
        for tutor in tutors
    ])
    
    return choices


def get_student_choices(department_id=None):
    """Get active students for dropdown"""
    from app.models.student import Student
    
    query = Student.query.filter_by(is_active=True, enrollment_status='active')
    
    if department_id:
        query = query.filter_by(department_id=department_id)
    
    students = query.all()
    
    choices = [('', 'Select Student')]
    choices.extend([
        (student.id, f"{student.full_name} ({student.grade} - {student.board})")
        for student in students
    ])
    
    return choices