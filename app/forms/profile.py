from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import StringField, TextAreaField, PasswordField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length, Email, EqualTo, Optional, ValidationError
from flask_login import current_user
from app.models.user import User

class EditProfileForm(FlaskForm):
    """Edit user profile form"""
    
    # Basic Information
    full_name = StringField('Full Name', validators=[
        DataRequired(), 
        Length(min=2, max=100)
    ], render_kw={'placeholder': 'Enter your full name'})
    
    phone = StringField('Phone Number', validators=[
        Optional(), 
        Length(min=10, max=15)
    ], render_kw={'placeholder': '+91 9876543210'})
    
    address = TextAreaField('Address', validators=[Optional()], 
                           render_kw={'placeholder': 'Enter your complete address', 'rows': 3})
    
    working_hours = StringField('Working Hours', validators=[Optional()], 
                               render_kw={'placeholder': '9:00 AM - 6:00 PM'})
    
    # Profile Picture
    profile_picture = FileField('Profile Picture', validators=[
        FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Images only!')
    ])
    
    # Emergency Contact
    emergency_name = StringField('Emergency Contact Name', validators=[Optional()], 
                                render_kw={'placeholder': 'Contact person name'})
    
    emergency_phone = StringField('Emergency Contact Phone', validators=[Optional()], 
                                 render_kw={'placeholder': 'Contact person phone'})
    
    emergency_relationship = SelectField('Relationship', 
                                       choices=[
                                           ('', 'Select Relationship'),
                                           ('parent', 'Parent'),
                                           ('spouse', 'Spouse'),
                                           ('sibling', 'Sibling'),
                                           ('friend', 'Friend'),
                                           ('colleague', 'Colleague'),
                                           ('other', 'Other')
                                       ], 
                                       validators=[Optional()])
    
    emergency_email = StringField('Emergency Contact Email', validators=[
        Optional(), 
        Email()
    ], render_kw={'placeholder': 'emergency@example.com'})
    
    submit = SubmitField('Update Profile')

class ChangePasswordForm(FlaskForm):
    """Change password form"""
    
    current_password = PasswordField('Current Password', validators=[
        DataRequired()
    ], render_kw={'placeholder': 'Enter current password'})
    
    new_password = PasswordField('New Password', validators=[
        DataRequired(), 
        Length(min=6, max=20)
    ], render_kw={'placeholder': 'Enter new password'})
    
    confirm_password = PasswordField('Confirm New Password', validators=[
        DataRequired(), 
        EqualTo('new_password', message='Passwords must match')
    ], render_kw={'placeholder': 'Confirm new password'})
    
    submit = SubmitField('Change Password')

class BankingDetailsForm(FlaskForm):
    """Banking information form for tutors"""
    
    account_holder_name = StringField('Account Holder Name', validators=[
        DataRequired(), 
        Length(min=2, max=100)
    ], render_kw={'placeholder': 'As per bank records'})
    
    bank_name = StringField('Bank Name', validators=[
        DataRequired(), 
        Length(min=2, max=100)
    ], render_kw={'placeholder': 'e.g., State Bank of India'})
    
    branch_name = StringField('Branch Name', validators=[
        DataRequired(), 
        Length(min=2, max=100)
    ], render_kw={'placeholder': 'Bank branch name'})
    
    account_number = StringField('Account Number', validators=[
        DataRequired(), 
        Length(min=9, max=18)
    ], render_kw={'placeholder': 'Bank account number'})
    
    ifsc_code = StringField('IFSC Code', validators=[
        DataRequired(), 
        Length(min=11, max=11)
    ], render_kw={'placeholder': 'e.g., SBIN0001234'})
    
    account_type = SelectField('Account Type', 
                              choices=[
                                  ('', 'Select Account Type'),
                                  ('savings', 'Savings Account'),
                                  ('current', 'Current Account'),
                                  ('salary', 'Salary Account')
                              ], 
                              validators=[DataRequired()])
    
    bank_document = FileField('Bank Verification Document', validators=[
        FileAllowed(['jpg', 'jpeg', 'png', 'pdf'], 'Images and PDFs only!')
    ], description='Upload cancelled cheque or bank statement')
    
    submit = SubmitField('Update Banking Details')
    
    def validate_account_number(self, account_number):
        """Validate account number format"""
        if not account_number.data.isdigit():
            raise ValidationError('Account number should contain only digits')
    
    def validate_ifsc_code(self, ifsc_code):
        """Validate IFSC code format"""
        code = ifsc_code.data.upper()
        if len(code) != 11:
            raise ValidationError('IFSC code must be exactly 11 characters')
        
        if not code[:4].isalpha():
            raise ValidationError('First 4 characters of IFSC code must be letters')
        
        if code[4] != '0':
            raise ValidationError('5th character of IFSC code must be 0')
        
        if not code[5:].isdigit():
            raise ValidationError('Last 6 characters of IFSC code must be digits')

class DocumentUploadForm(FlaskForm):
    """Document upload form"""
    
    document_type = SelectField('Document Type', 
                               choices=[
                                   ('', 'Select Document Type'),
                                   ('id_proof', 'ID Proof (Aadhaar/PAN)'),
                                   ('address_proof', 'Address Proof'),
                                   ('educational_certificate', 'Educational Certificate'),
                                   ('experience_certificate', 'Experience Certificate'),
                                   ('resume', 'Resume/CV'),
                                   ('photo', 'Passport Size Photo'),
                                   ('other', 'Other Document')
                               ], 
                               validators=[DataRequired()])
    
    document_file = FileField('Upload Document', validators=[
        FileRequired(),
        FileAllowed(['jpg', 'jpeg', 'png', 'pdf', 'doc', 'docx'], 
                   'Only images, PDFs and documents allowed!')
    ])
    
    description = TextAreaField('Description (Optional)', 
                               render_kw={'placeholder': 'Brief description of the document', 'rows': 2})
    
    submit = SubmitField('Upload Document')

class ProfessionalDetailsForm(FlaskForm):
    """Professional details form for tutors"""
    
    qualification = StringField('Highest Qualification', validators=[
        DataRequired(), 
        Length(min=2, max=200)
    ], render_kw={'placeholder': 'e.g., M.Sc. Mathematics'})
    
    experience = TextAreaField('Experience Details', validators=[
        Optional()
    ], render_kw={'placeholder': 'Describe your teaching/professional experience', 'rows': 4})
    
    subjects = StringField('Subjects/Specializations', validators=[
        Optional()
    ], render_kw={'placeholder': 'Mathematics, Physics, Chemistry (comma separated)'})
    
    grades = StringField('Grade Levels', validators=[
        Optional()
    ], render_kw={'placeholder': '10, 11, 12 (comma separated)'})
    
    boards = StringField('Education Boards', validators=[
        Optional()
    ], render_kw={'placeholder': 'CBSE, ICSE, State Board (comma separated)'})
    
    certifications = TextAreaField('Additional Certifications', validators=[
        Optional()
    ], render_kw={'placeholder': 'List any additional certifications or training', 'rows': 3})
    
    achievements = TextAreaField('Achievements & Awards', validators=[
        Optional()
    ], render_kw={'placeholder': 'Any notable achievements or awards', 'rows': 3})
    
    submit = SubmitField('Update Professional Details')

class AvailabilityForm(FlaskForm):
    """Availability form for tutors"""
    
    monday_from = StringField('Monday From', render_kw={'placeholder': '09:00 AM'})
    monday_to = StringField('Monday To', render_kw={'placeholder': '06:00 PM'})
    monday_available = SelectField('Monday Available', 
                                  choices=[('yes', 'Available'), ('no', 'Not Available')])
    
    tuesday_from = StringField('Tuesday From', render_kw={'placeholder': '09:00 AM'})
    tuesday_to = StringField('Tuesday To', render_kw={'placeholder': '06:00 PM'})
    tuesday_available = SelectField('Tuesday Available', 
                                   choices=[('yes', 'Available'), ('no', 'Not Available')])
    
    wednesday_from = StringField('Wednesday From', render_kw={'placeholder': '09:00 AM'})
    wednesday_to = StringField('Wednesday To', render_kw={'placeholder': '06:00 PM'})
    wednesday_available = SelectField('Wednesday Available', 
                                     choices=[('yes', 'Available'), ('no', 'Not Available')])
    
    thursday_from = StringField('Thursday From', render_kw={'placeholder': '09:00 AM'})
    thursday_to = StringField('Thursday To', render_kw={'placeholder': '06:00 PM'})
    thursday_available = SelectField('Thursday Available', 
                                    choices=[('yes', 'Available'), ('no', 'Not Available')])
    
    friday_from = StringField('Friday From', render_kw={'placeholder': '09:00 AM'})
    friday_to = StringField('Friday To', render_kw={'placeholder': '06:00 PM'})
    friday_available = SelectField('Friday Available', 
                                  choices=[('yes', 'Available'), ('no', 'Not Available')])
    
    saturday_from = StringField('Saturday From', render_kw={'placeholder': '09:00 AM'})
    saturday_to = StringField('Saturday To', render_kw={'placeholder': '06:00 PM'})
    saturday_available = SelectField('Saturday Available', 
                                    choices=[('yes', 'Available'), ('no', 'Not Available')])
    
    sunday_from = StringField('Sunday From', render_kw={'placeholder': '09:00 AM'})
    sunday_to = StringField('Sunday To', render_kw={'placeholder': '06:00 PM'})
    sunday_available = SelectField('Sunday Available', 
                                  choices=[('yes', 'Available'), ('no', 'Not Available')])
    
    submit = SubmitField('Update Availability')

class ContactPreferencesForm(FlaskForm):
    """Contact and notification preferences form"""
    
    preferred_contact_method = SelectField('Preferred Contact Method',
                                         choices=[
                                             ('email', 'Email'),
                                             ('phone', 'Phone Call'),
                                             ('sms', 'SMS'),
                                             ('whatsapp', 'WhatsApp')
                                         ],
                                         validators=[DataRequired()])
    
    notification_frequency = SelectField('Notification Frequency',
                                       choices=[
                                           ('immediate', 'Immediate'),
                                           ('daily', 'Daily Digest'),
                                           ('weekly', 'Weekly Summary'),
                                           ('minimal', 'Only Important')
                                       ],
                                       validators=[DataRequired()])
    
    submit = SubmitField('Update Preferences')