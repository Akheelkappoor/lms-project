from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired, FileSize
from wtforms import StringField, PasswordField, SelectField, TextAreaField, BooleanField, SubmitField, DateField, FloatField, SelectMultipleField, widgets
from wtforms.validators import DataRequired, Email, Length, Optional, ValidationError, NumberRange, EqualTo, InputRequired
from app.models.user import User
from app.models.department import Department
from app.forms.auth import validate_password_strength


class MultiCheckboxField(SelectMultipleField):
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()

class CreateUserForm(FlaskForm):
    # Basic Information
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=20)], 
                          render_kw={'placeholder': 'Enter unique username'})
    email = StringField('Email', validators=[DataRequired(), Email()], 
                       render_kw={'placeholder': 'Enter email address'})
    full_name = StringField('Full Name', validators=[DataRequired(), Length(max=100)], 
                           render_kw={'placeholder': 'Enter full name'})
    phone = StringField('Phone Number', validators=[Optional(), Length(max=20)], 
                       render_kw={'placeholder': 'Enter phone number'})
    
    # Role and Department
    role = SelectField('Role', validators=[DataRequired()], 
                      choices=[('admin', 'Admin'), ('coordinator', 'Coordinator'), ('tutor', 'Tutor')])
    department_id = SelectField('Department', validators=[DataRequired()], coerce=int)
    
    # Password
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8, max=128), validate_password_strength], 
                           render_kw={'placeholder': 'Enter password (min 8 chars, 1 upper, 1 lower, 1 digit, 1 special char)'})
    password_confirm = PasswordField('Confirm Password', validators=[
        DataRequired(), 
        EqualTo('password', message='Passwords must match')
    ], render_kw={'placeholder': 'Re-enter password'})

    # Additional Information
    address = TextAreaField('Address', validators=[Optional()], 
                           render_kw={'placeholder': 'Enter complete address', 'rows': 3})
    working_hours = StringField('Working Hours', validators=[Optional()], 
                               render_kw={'placeholder': 'e.g., 9:00 AM - 6:00 PM'})
    joining_date = DateField('Joining Date', validators=[Optional()])
    
    # Profile Picture
    profile_picture = FileField('Profile Picture', validators=[
        FileAllowed(['jpg', 'png', 'jpeg'], 'Only JPG, PNG and JPEG images allowed!'),
        FileSize(max_size=5*1024*1024, message='File size must be less than 5MB'),
        Optional()
    ])
    
    # Status
    is_active = BooleanField('Active', default=True)
    
    submit = SubmitField('Create User')
    
    def __init__(self, *args, **kwargs):
        super(CreateUserForm, self).__init__(*args, **kwargs)
        self.department_id.choices = [(0, 'Select Department')] + \
            [(d.id, d.name) for d in Department.query.filter_by(is_active=True).all()]
    
    def validate_username(self, username):
        user = User.query.filter(User.username.ilike(username.data)).first()
        if user:
            raise ValidationError('Username already exists. Please choose a different one.')
    
    def validate_email(self, email):
        user = User.query.filter(User.email.ilike(email.data)).first()
        if user:
            raise ValidationError('Email already registered. Please choose a different one.')

class EditUserForm(FlaskForm):
    # Basic Information
    full_name = StringField('Full Name', validators=[DataRequired(), Length(max=100)], 
                           render_kw={'placeholder': 'Enter full name'})
    email = StringField('Email', validators=[DataRequired(), Email()], 
                       render_kw={'placeholder': 'Enter email address'})
    phone = StringField('Phone Number', validators=[Optional(), Length(max=20)], 
                       render_kw={'placeholder': 'Enter phone number'})
    
    # Role and Department
    role = SelectField('Role', validators=[DataRequired()], 
                      choices=[('admin', 'Admin'), ('coordinator', 'Coordinator'), ('tutor', 'Tutor')])
    department_id = SelectField('Department', validators=[DataRequired()], coerce=int)
    
    # Additional Information
    address = TextAreaField('Address', validators=[Optional()], 
                           render_kw={'placeholder': 'Enter complete address', 'rows': 3})
    working_hours = StringField('Working Hours', validators=[Optional()], 
                               render_kw={'placeholder': 'e.g., 9:00 AM - 6:00 PM'})
    joining_date = DateField('Joining Date', validators=[Optional()])
    
    # Profile Picture
    profile_picture = FileField('Profile Picture', validators=[
        FileAllowed(['jpg', 'png', 'jpeg'], 'Only JPG, PNG and JPEG images allowed!'),
        FileSize(max_size=5*1024*1024, message='File size must be less than 5MB'),
        Optional()
    ])
    
    # Status
    is_active = BooleanField('Active')
    
    submit = SubmitField('Update User')
    
    def __init__(self, user_id, *args, **kwargs):
        super(EditUserForm, self).__init__(*args, **kwargs)
        self.user_id = user_id
        self.department_id.choices = [(0, 'Select Department')] + \
            [(d.id, d.name) for d in Department.query.filter_by(is_active=True).all()]
    
    def validate_email(self, email):
        user = User.query.filter(User.email.ilike(email.data), User.id != self.user_id).first()
        if user:
            raise ValidationError('Email already registered. Please choose a different one.')

class TutorRegistrationForm(FlaskForm):
    # Personal Information
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=20)], 
                          render_kw={'placeholder': 'Enter unique username'})
    full_name = StringField('Full Name', validators=[DataRequired(), Length(max=100)], 
                           render_kw={'placeholder': 'Enter full name'})
    password = PasswordField('Password', validators=[
        DataRequired(), 
        Length(min=8, max=128), 
        validate_password_strength
    ], render_kw={'placeholder': 'Enter password (min 8 chars, 1 upper, 1 lower, 1 digit, 1 special char)'})
    password_confirm = PasswordField('Confirm Password', validators=[
        DataRequired(), 
        EqualTo('password', message='Passwords must match')
    ], render_kw={'placeholder': 'Re-enter password'})
    email = StringField('Email', validators=[DataRequired(), Email()], 
                       render_kw={'placeholder': 'Enter email address'})
    phone = StringField('Contact Number', validators=[DataRequired(), Length(max=20)], 
                       render_kw={'placeholder': 'Enter contact number'})
    date_of_birth = DateField('Date of Birth', validators=[DataRequired()])
    address = TextAreaField('Complete Address', validators=[DataRequired()], 
                           render_kw={'placeholder': 'Enter complete address', 'rows': 3})
    state = StringField('State', validators=[DataRequired()], 
                       render_kw={'placeholder': 'Enter state'})
    pin_code = StringField('Pin Code', validators=[DataRequired(), Length(max=10)], 
                          render_kw={'placeholder': 'Enter pin code'})
    
    # Department
    department_id = SelectField('Department', validators=[DataRequired()], coerce=int)
    
    # Professional Details
    qualification = StringField('Qualification', validators=[DataRequired(), Length(max=200)], 
                               render_kw={'placeholder': 'Enter highest qualification'})
    experience = TextAreaField('Experience', validators=[DataRequired()], 
                              render_kw={'placeholder': 'Years and relevant background', 'rows': 4})
    
    # Test Score Information - NEW FIELDS ADDED
    test_score = FloatField('Test Score', validators=[
        DataRequired(), 
        NumberRange(min=0, max=100, message='Test score must be between 0 and 100')
    ], render_kw={'placeholder': 'Enter total test score (0-100)', 'step': '0.1'})
    
    test_date = DateField('Test Date', validators=[DataRequired()],
                         render_kw={'placeholder': 'Date when test was taken'})
    
    test_notes = TextAreaField('Test Performance Notes', validators=[Optional()], 
                              render_kw={'placeholder': 'Additional notes about test performance', 'rows': 3})
    
    # Teaching Details
    subjects = StringField('Subjects', validators=[DataRequired()], 
                          render_kw={'placeholder': 'Enter subjects separated by commas'})
    grades = StringField('Grades', validators=[DataRequired()], 
                        render_kw={'placeholder': 'Enter grades separated by commas (e.g., 1,2,3,4,5)'})
    boards = StringField('Boards', validators=[DataRequired()], 
                        render_kw={'placeholder': 'Enter education boards separated by commas'})
    
    # Compensation
    salary_type = SelectField('Salary Type', validators=[DataRequired()], 
                             choices=[('monthly', 'Fixed Monthly'), ('hourly', 'Hourly Rate')])
    monthly_salary = FloatField('Monthly Salary (₹)', validators=[Optional(), NumberRange(min=0)], 
                               render_kw={'placeholder': 'Enter monthly salary'})
    hourly_rate = FloatField('Hourly Rate (₹)', validators=[Optional(), NumberRange(min=0)], 
                            render_kw={'placeholder': 'Enter hourly rate'})
    
    # Documents
    aadhaar_card = FileField('Aadhaar Card', validators=[
        FileRequired(), 
        FileAllowed(['jpg', 'png', 'jpeg', 'pdf'], 'Images and PDF only!'),
        FileSize(max_size=10*1024*1024, message='File size must be less than 10MB')
    ])
    pan_card = FileField('PAN Card', validators=[
        FileRequired(), 
        FileAllowed(['jpg', 'png', 'jpeg', 'pdf'], 'Images and PDF only!'),
        FileSize(max_size=10*1024*1024, message='File size must be less than 10MB')
    ])
    resume = FileField('Resume/CV', validators=[
        FileRequired(), 
        FileAllowed(['pdf'], 'PDF files only!'),
        FileSize(max_size=10*1024*1024, message='File size must be less than 10MB')
    ])
    degree_certificate = FileField('Degree Certificate', validators=[
        FileRequired(), 
        FileAllowed(['jpg', 'png', 'jpeg', 'pdf'], 'Images and PDF only!'),
        FileSize(max_size=10*1024*1024, message='File size must be less than 10MB')
    ])
    
    # Videos
    demo_video = FileField('Demo Video', validators=[
        FileAllowed(['mp4'], 'MP4 videos only!'),
        FileSize(max_size=50*1024*1024, message='Video size must be less than 50MB'),
        Optional()
    ])
    interview_video = FileField('Interview Video', validators=[
        FileAllowed(['mp4'], 'MP4 videos only!'),
        FileSize(max_size=100*1024*1024, message='Video size must be less than 100MB'),
        Optional()
    ])
    
    # Banking Information
    account_holder_name = StringField('Account Holder Name', validators=[DataRequired()], 
                                     render_kw={'placeholder': 'Enter account holder name'})
    bank_name = StringField('Bank Name', validators=[DataRequired()], 
                           render_kw={'placeholder': 'Enter bank name'})
    branch_name = StringField('Branch Name', validators=[DataRequired()], 
                             render_kw={'placeholder': 'Enter branch name'})
    account_number = StringField('Account Number', validators=[DataRequired()], 
                                render_kw={'placeholder': 'Enter account number'})
    ifsc_code = StringField('IFSC Code', validators=[DataRequired()], 
                           render_kw={'placeholder': 'Enter IFSC code'})
    
    submit = SubmitField('Register Tutor')

    def __init__(self, *args, **kwargs):
        super(TutorRegistrationForm, self).__init__(*args, **kwargs)
        self.department_id.choices = [(0, 'Select Department')] + \
            [(d.id, d.name) for d in Department.query.filter_by(is_active=True).all()]
    
    def validate_username(self, username):
        user = User.query.filter(User.username.ilike(username.data)).first()
        if user:
            raise ValidationError('Username already exists. Please choose a different one.')
    
    def validate_email(self, email):
        user = User.query.filter(User.email.ilike(email.data)).first()
        if user:
            raise ValidationError('Email already registered. Please choose a different one.')
    
    # NEW VALIDATION METHODS FOR TEST SCORE FIELDS
    def validate_test_score(self, test_score):
        if test_score.data is not None:
            if test_score.data < 0 or test_score.data > 100:
                raise ValidationError('Test score must be between 0 and 100.')
    
    def validate_test_date(self, test_date):
        from datetime import date
        if test_date.data:
            if test_date.data > date.today():
                raise ValidationError('Test date cannot be in the future.')
    
    def validate_salary_type(self, salary_type):
        if salary_type.data == 'monthly' and not self.monthly_salary.data:
            raise ValidationError('Monthly salary is required when salary type is monthly.')
        elif salary_type.data == 'hourly' and not self.hourly_rate.data:
            raise ValidationError('Hourly rate is required when salary type is hourly.')


from wtforms import DecimalField, FileField

class StudentRegistrationForm(FlaskForm):
    # Basic Information
    full_name = StringField('Full Name', validators=[DataRequired(), Length(max=100)], 
                           render_kw={'placeholder': 'Enter student full name'})
    email = StringField('Student Email', validators=[DataRequired(), Email()], 
                       render_kw={'placeholder': 'Enter student email'})
    phone = StringField('Phone Number', validators=[Optional(), Length(max=20)], 
                       render_kw={'placeholder': 'Enter phone number'})
    date_of_birth = DateField('Date of Birth', validators=[DataRequired()])
    address = TextAreaField('Complete Address', validators=[DataRequired()], 
                           render_kw={'placeholder': 'Enter complete address', 'rows': 3})
    state = StringField('State', validators=[DataRequired()], 
                       render_kw={'placeholder': 'Enter state'})
    pin_code = StringField('Pin Code', validators=[DataRequired(), Length(max=10)], 
                          render_kw={'placeholder': 'Enter pin code'})
    
    # Academic Information
    grade = StringField('Grade Level', validators=[DataRequired()], 
                       render_kw={'placeholder': 'Enter grade (e.g., 5, 10, 12)'})
    board = StringField('Educational Board', validators=[DataRequired()], 
                       render_kw={'placeholder': 'Enter board (e.g., CBSE, ICSE, State Board)'})
    school_name = StringField('School Name', validators=[DataRequired()], 
                             render_kw={'placeholder': 'Enter school name'})
    academic_year = StringField('Academic Year', validators=[DataRequired()], 
                               render_kw={'placeholder': 'Enter academic year (e.g., 2024-25)'})
    course_start_date = DateField('Course Start Date', validators=[DataRequired()])
    
    # Department
    department_id = SelectField('Department', validators=[DataRequired()], coerce=int)
    
    # Parent Details - Father
    father_name = StringField('Father Name', validators=[DataRequired()], 
                             render_kw={'placeholder': 'Enter father name'})
    father_phone = StringField('Father Phone', validators=[DataRequired()], 
                              render_kw={'placeholder': 'Enter father phone'})
    father_email = StringField('Father Email', validators=[Optional(), Email()], 
                              render_kw={'placeholder': 'Enter father email'})
    father_profession = StringField('Father Profession', validators=[Optional()], 
                                   render_kw={'placeholder': 'Enter father profession'})
    father_workplace = StringField('Father Workplace', validators=[Optional()], 
                                  render_kw={'placeholder': 'Enter father workplace'})
    
    # Parent Details - Mother
    mother_name = StringField('Mother Name', validators=[DataRequired()], 
                             render_kw={'placeholder': 'Enter mother name'})
    mother_phone = StringField('Mother Phone', validators=[Optional()], 
                              render_kw={'placeholder': 'Enter mother phone'})
    mother_email = StringField('Mother Email', validators=[Optional(), Email()], 
                              render_kw={'placeholder': 'Enter mother email'})
    mother_profession = StringField('Mother Profession', validators=[Optional()], 
                                   render_kw={'placeholder': 'Enter mother profession'})
    mother_workplace = StringField('Mother Workplace', validators=[Optional()], 
                                  render_kw={'placeholder': 'Enter mother workplace'})
    
    # Academic Profile
    siblings = StringField('Number of Siblings', validators=[Optional()], 
                          render_kw={'placeholder': 'Enter number of siblings'})
    hobbies = StringField('Hobbies', validators=[Optional()], 
                         render_kw={'placeholder': 'Enter hobbies separated by commas'})
    learning_styles = StringField('Learning Styles', validators=[Optional()], 
                                 render_kw={'placeholder': 'Enter learning styles (Visual, Auditory, etc.)'})
    learning_patterns = StringField('Learning Patterns', validators=[Optional()], 
                                   render_kw={'placeholder': 'Enter learning patterns'})
    favorite_subjects = StringField('Favorite Subjects', validators=[Optional()], 
                                   render_kw={'placeholder': 'Enter favorite subjects'})
    difficult_subjects = StringField('Difficult Subjects', validators=[Optional()], 
                                    render_kw={'placeholder': 'Enter subjects that need attention'})
    parent_feedback = TextAreaField('Parent Feedback', validators=[Optional()], 
                                   render_kw={'placeholder': 'Previous tutoring experience, learning challenges, etc.', 'rows': 4})
    
    # Subjects and Classes
    subjects_enrolled = StringField('Subjects Enrolled', validators=[DataRequired()], 
                                   render_kw={'placeholder': 'Enter subjects separated by commas'})
    
    # Assignment Details
    relationship_manager = StringField('Relationship Manager', validators=[Optional()], 
                                      render_kw={'placeholder': 'Enter RM name'})
    
    # Fee Structure
    total_fee = FloatField('Total Fee (₹)', validators=[InputRequired(), NumberRange(min=0)],
                      render_kw={'placeholder': 'Enter total course fee'})
    amount_paid = FloatField('Amount Paid (₹)', validators=[Optional(), NumberRange(min=0)], 
                            render_kw={'placeholder': 'Enter amount already paid'})
    payment_mode = SelectField('Payment Mode', validators=[DataRequired()], 
                              choices=[('online', 'Online'), ('bank_transfer', 'Bank Transfer'), 
                                     ('cash', 'Cash'), ('cheque', 'Cheque'), ('upi', 'UPI')])
    payment_schedule = SelectField('Payment Schedule', validators=[DataRequired()], 
                                  choices=[('paid_full', 'Paid in Full'), ('installment_plan', 'Create Installment Payment Plan')])
    
    # Documents
    marksheet = FileField('Previous Year Marksheet', validators=[
        FileAllowed(['jpg', 'png', 'jpeg', 'pdf'], 'Images and PDF only!')
    ])
    student_aadhaar = FileField('Student Aadhaar Card', validators=[
        FileAllowed(['jpg', 'png', 'jpeg', 'pdf'], 'Images and PDF only!')
    ])
    school_id = FileField('School ID (if available)', validators=[
        FileAllowed(['jpg', 'png', 'jpeg', 'pdf'], 'Images and PDF only!')
    ])
    
    submit = SubmitField('Register Student')
    
    ownership_type = SelectField('Ownership Type', choices=[('i2g', 'i2g'), ('franchisee', 'Franchisee')],
                                  validators=[DataRequired()],
                                  render_kw={'placeholder': 'Select ownership type'})

    def __init__(self, *args, **kwargs):
        super(StudentRegistrationForm, self).__init__(*args, **kwargs)
        self.department_id.choices = [(0, 'Select Department')] + \
            [(d.id, d.name) for d in Department.query.filter_by(is_active=True).all()]
    
    def validate_email(self, email):
        from app.models.student import Student
        student = Student.query.filter(Student.email.ilike(email.data)).first()
        if student:
            raise ValidationError('Email already registered. Please choose a different one.')
            
    def validate_total_fee(self, field):
        if self.ownership_type.data == 'i2g' and (field.data is None or field.data == 0):
            raise ValidationError('Total fee must be greater than 0 for i2g ownership.')
        if self.ownership_type.data == 'franchisee' and (field.data is None or field.data != 0):
            raise ValidationError('Total fee must be 0 for franchisee ownership.')
        
    def validate(self, extra_validators=None):
        rv = super().validate(extra_validators=extra_validators)
        if not rv:
            return False

        # Enforce business rule: i2g must have total_fee > 0, franchisee must be 0
        if self.ownership_type.data == 'i2g' and (self.total_fee.data is None or self.total_fee.data == 0):
            self.total_fee.errors.append('Total fee must be greater than 0 for i2g ownership.')
            return False

        if self.ownership_type.data == 'franchisee' and (self.total_fee.data is None or self.total_fee.data != 0):
            self.total_fee.errors.append('Total fee must be 0 for franchisee ownership.')
            return False

        return True



        
from wtforms import DecimalField
class EditStudentForm(StudentRegistrationForm):
    """Form for editing existing students - inherits from registration form but modifies email validation"""
    
    # Additional fields for editing (fee-related fields that might be missing)
    total_fee = DecimalField('Total Fee (₹)', validators=[Optional()], places=2,
                            render_kw={'placeholder': 'Enter total course fee'})
    amount_paid = DecimalField('Amount Paid (₹)', validators=[Optional()], places=2,
                              render_kw={'placeholder': 'Enter amount already paid'})
    payment_mode = SelectField('Payment Mode', validators=[Optional()],
                              choices=[('', 'Select Payment Mode'), 
                                     ('cash', 'Cash'), ('online', 'Online'), 
                                     ('cheque', 'Cheque'), ('card', 'Card'),
                                     ('bank_transfer', 'Bank Transfer')])
    payment_schedule = SelectField('Payment Schedule', validators=[Optional()],
                                  choices=[('', 'Select Schedule'), 
                                         ('paid_full', 'Paid in Full'), 
                                         ('installment_plan', 'Create Installment Payment Plan')])
    
    # Additional academic fields that might be missing
    parent_feedback = TextAreaField('Parent Feedback', validators=[Optional()],
                                   render_kw={'rows': 3, 'placeholder': 'Enter parent feedback or special requirements'})
    learning_patterns = StringField('Learning Patterns', validators=[Optional()],
                                   render_kw={'placeholder': 'e.g., Fast learner, Needs repetition, Visual learner'})
    
    ownership_type = SelectField('Ownership Type (validation only)',
                                 choices=[('i2g', 'i2g'), ('franchisee', 'Franchisee')],
                                 validators=[Optional()],
                                 render_kw={'placeholder': 'Choose ownership type for fee logic'})
    
    def __init__(self, student_id=None, *args, **kwargs):
        super(EditStudentForm, self).__init__(*args, **kwargs)
        self.student_id = student_id
        
        # Make some fields optional for editing (that were required for registration)
        self.father_name.validators = [Optional()]
        self.father_phone.validators = [Optional()]
        self.mother_name.validators = [Optional()]
    
    def validate_email(self, email):
        """Modified email validation that excludes current student"""
        from app.models.student import Student
        
        # Only check for duplicates if email has changed or student_id is not provided
        if self.student_id:
            student = Student.query.filter(
                Student.email.ilike(email.data),
                Student.id != self.student_id
            ).first()
        else:
            student = Student.query.filter(Student.email.ilike(email.data)).first()
            
        if student:
            raise ValidationError('Email already registered. Please choose a different one.')
        
    def validate(self, extra_validators=None):
        rv = super().validate(extra_validators=extra_validators)
        if not rv:
            return False

        # Conditional validation for fee logic
        if self.ownership_type.data == 'i2g' and (self.total_fee.data is None or self.total_fee.data == 0):
            self.total_fee.errors.append('Total fee must be greater than 0 for i2g ownership.')
            return False

        if self.ownership_type.data == 'franchisee' and (self.total_fee.data is not None and self.total_fee.data != 0):
            self.total_fee.errors.append('Total fee must be 0 for franchisee ownership.')
            return False

        return True
