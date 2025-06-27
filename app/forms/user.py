from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, SelectField, TextAreaField, BooleanField, SubmitField, DateField, FloatField, SelectMultipleField, widgets
from wtforms.validators import DataRequired, Email, Length, Optional, ValidationError, NumberRange
from app.models.user import User
from app.models.department import Department

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
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, max=20)], 
                           render_kw={'placeholder': 'Enter password'})
    
    # Additional Information
    address = TextAreaField('Address', validators=[Optional()], 
                           render_kw={'placeholder': 'Enter complete address', 'rows': 3})
    working_hours = StringField('Working Hours', validators=[Optional()], 
                               render_kw={'placeholder': 'e.g., 9:00 AM - 6:00 PM'})
    joining_date = DateField('Joining Date', validators=[Optional()])
    
    # Profile Picture
    profile_picture = FileField('Profile Picture', validators=[
        FileAllowed(['jpg', 'png', 'jpeg', 'gif'], 'Images only!')
    ])
    
    # Status
    is_active = BooleanField('Active', default=True)
    
    submit = SubmitField('Create User')
    
    def __init__(self, *args, **kwargs):
        super(CreateUserForm, self).__init__(*args, **kwargs)
        self.department_id.choices = [(0, 'Select Department')] + \
            [(d.id, d.name) for d in Department.query.filter_by(is_active=True).all()]
    
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username already exists. Please choose a different one.')
    
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
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
        FileAllowed(['jpg', 'png', 'jpeg', 'gif'], 'Images only!')
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
        user = User.query.filter(User.email == email.data, User.id != self.user_id).first()
        if user:
            raise ValidationError('Email already registered. Please choose a different one.')

class TutorRegistrationForm(FlaskForm):
    # Personal Information
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=20)], 
                          render_kw={'placeholder': 'Enter unique username'})
    full_name = StringField('Full Name', validators=[DataRequired(), Length(max=100)], 
                           render_kw={'placeholder': 'Enter full name'})
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
        DataRequired(), FileAllowed(['jpg', 'png', 'jpeg', 'pdf'], 'Images and PDF only!')
    ])
    pan_card = FileField('PAN Card', validators=[
        DataRequired(), FileAllowed(['jpg', 'png', 'jpeg', 'pdf'], 'Images and PDF only!')
    ])
    resume = FileField('Resume/CV', validators=[
        DataRequired(), FileAllowed(['pdf', 'doc', 'docx'], 'Documents only!')
    ])
    degree_certificate = FileField('Degree Certificate', validators=[
        DataRequired(), FileAllowed(['jpg', 'png', 'jpeg', 'pdf'], 'Images and PDF only!')
    ])
    
    # Videos
    demo_video = FileField('Demo Video', validators=[
        DataRequired(), FileAllowed(['mp4', 'avi', 'mov', 'wmv'], 'Video files only!')
    ])
    interview_video = FileField('Interview Video', validators=[
        DataRequired(), FileAllowed(['mp4', 'avi', 'mov', 'wmv'], 'Video files only!')
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
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username already exists. Please choose a different one.')
    
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email already registered. Please choose a different one.')

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
    total_fee = FloatField('Total Fee (₹)', validators=[DataRequired(), NumberRange(min=0)], 
                          render_kw={'placeholder': 'Enter total course fee'})
    amount_paid = FloatField('Amount Paid (₹)', validators=[Optional(), NumberRange(min=0)], 
                            render_kw={'placeholder': 'Enter amount already paid'})
    payment_mode = SelectField('Payment Mode', validators=[DataRequired()], 
                              choices=[('online', 'Online'), ('bank_transfer', 'Bank Transfer'), 
                                     ('cash', 'Cash'), ('cheque', 'Cheque'), ('upi', 'UPI')])
    payment_schedule = SelectField('Payment Schedule', validators=[DataRequired()], 
                                  choices=[('monthly', 'Monthly'), ('quarterly', 'Quarterly'), 
                                         ('one_time', 'One Time')])
    
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
    
    def __init__(self, *args, **kwargs):
        super(StudentRegistrationForm, self).__init__(*args, **kwargs)
        self.department_id.choices = [(0, 'Select Department')] + \
            [(d.id, d.name) for d in Department.query.filter_by(is_active=True).all()]
    
    def validate_email(self, email):
        from app.models.student import Student
        student = Student.query.filter_by(email=email.data).first()
        if student:
            raise ValidationError('Email already registered. Please choose a different one.')