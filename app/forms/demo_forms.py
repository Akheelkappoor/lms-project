# app/forms/demo_forms.py

from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, DateField, TimeField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Email, Length, Optional
from wtforms.widgets import TextArea
from datetime import date, datetime

class DemoStudentForm(FlaskForm):
    """Simplified form for demo student registration"""
    
    # Student Basic Info
    full_name = StringField('Student Name', validators=[DataRequired(), Length(max=100)], 
                           render_kw={'placeholder': 'Enter student full name'})
    
    grade = SelectField('Grade', validators=[DataRequired()], 
                       choices=[('', 'Select Grade')] + 
                               [(str(i), f'Grade {i}') for i in range(1, 13)] + 
                               [('PG', 'Post Graduate'), ('UG', 'Under Graduate')])
    
    board = SelectField('Board', validators=[Optional()], 
                       choices=[('', 'Select Board'), ('CBSE', 'CBSE'), ('ICSE', 'ICSE'), 
                               ('State Board', 'State Board'), ('IB', 'IB'), ('Other', 'Other')])
    
    subject = StringField('Subject of Interest', validators=[DataRequired(), Length(max=100)], 
                         render_kw={'placeholder': 'e.g., Mathematics, Physics, English'})
    
    # Parent/Contact Info
    parent_name = StringField('Parent/Guardian Name', validators=[DataRequired(), Length(max=100)], 
                             render_kw={'placeholder': 'Enter parent/guardian name'})
    
    phone = StringField('Contact Number', validators=[DataRequired(), Length(max=20)], 
                       render_kw={'placeholder': 'Enter contact number'})
    
    email = StringField('Email Address', validators=[DataRequired(), Email()], 
                       render_kw={'placeholder': 'Enter email address'})
    
    # Demo Preferences
    preferred_time = SelectField('Preferred Time', validators=[DataRequired()], 
                                choices=[('', 'Select Preferred Time'),
                                        ('morning', 'Morning (9 AM - 12 PM)'),
                                        ('afternoon', 'Afternoon (12 PM - 4 PM)'),
                                        ('evening', 'Evening (4 PM - 8 PM)')])
    
    demo_date = DateField('Preferred Demo Date', validators=[DataRequired()],
                         default=date.today())
    
    additional_notes = TextAreaField('Additional Notes', validators=[Optional()],
                                   render_kw={'placeholder': 'Any specific requirements or notes', 'rows': 3})
    
    submit = SubmitField('Schedule Demo Class')
    
    def validate_demo_date(self, demo_date):
        if demo_date.data < date.today():
            raise ValidationError('Demo date cannot be in the past')

class DemoClassForm(FlaskForm):
    """Form for scheduling demo class with tutor"""
    
    # Demo Student Selection
    demo_student_id = SelectField('Demo Student', validators=[DataRequired()], coerce=int)
    
    # Class Details
    subject = StringField('Subject', validators=[DataRequired(), Length(max=100)])
    
    # Scheduling
    scheduled_date = DateField('Demo Date', validators=[DataRequired()])
    scheduled_time = TimeField('Demo Time', validators=[DataRequired()])
    duration = SelectField('Duration', validators=[DataRequired()], 
                          choices=[('30', '30 minutes'), ('45', '45 minutes'), ('60', '1 hour')])
    
    # Tutor Assignment
    tutor_id = SelectField('Assign Tutor', validators=[DataRequired()], coerce=int)
    
    # Meeting Link
    meeting_link = StringField('Meeting Link', validators=[DataRequired(), Length(max=500)], 
                              render_kw={'placeholder': 'Paste Zoom, Google Meet, or Teams link here'})
    
    # Additional Info
    class_notes = TextAreaField('Demo Class Notes', validators=[Optional()],
                               render_kw={'placeholder': 'Special instructions for the demo', 'rows': 3})
    
    submit = SubmitField('Schedule Demo Class')
    
    def __init__(self, *args, **kwargs):
        super(DemoClassForm, self).__init__(*args, **kwargs)
        
        # Populate demo students
        from app.models.demo_student import DemoStudent
        self.demo_student_id.choices = [(0, 'Select Demo Student')] + \
            [(ds.id, f"{ds.full_name} - Grade {ds.grade} ({ds.subject})") 
             for ds in DemoStudent.query.filter_by(demo_status='scheduled').all()]
        
        # Populate tutors
        from app.models.tutor import Tutor
        self.tutor_id.choices = [(0, 'Select Tutor')] + \
            [(t.id, t.user.full_name) for t in Tutor.query.filter_by(status='active').all()]

class DemoFeedbackForm(FlaskForm):
    """Form for demo class feedback"""
    
    # Student Assessment
    student_level = SelectField('Student Current Level', validators=[DataRequired()],
                               choices=[('beginner', 'Beginner'), ('intermediate', 'Intermediate'), 
                                       ('advanced', 'Advanced')])
    
    student_engagement = SelectField('Student Engagement', validators=[DataRequired()],
                                   choices=[('excellent', 'Excellent'), ('good', 'Good'), 
                                           ('average', 'Average'), ('needs_improvement', 'Needs Improvement')])
    
    topics_covered = StringField('Topics Covered', validators=[DataRequired()],
                                render_kw={'placeholder': 'List topics covered in demo'})
    
    student_strengths = TextAreaField('Student Strengths', validators=[Optional()],
                                    render_kw={'rows': 3, 'placeholder': 'What the student is good at'})
    
    areas_for_improvement = TextAreaField('Areas for Improvement', validators=[Optional()],
                                        render_kw={'rows': 3, 'placeholder': 'Areas where student needs help'})
    
    # Recommendation
    recommendation = SelectField('Recommendation', validators=[DataRequired()],
                               choices=[('highly_recommend', 'Highly Recommend Enrollment'),
                                       ('recommend', 'Recommend Enrollment'),
                                       ('maybe', 'Student Needs More Time'),
                                       ('not_recommend', 'Not Suitable at This Time')])
    
    suggested_frequency = SelectField('Suggested Class Frequency', validators=[Optional()],
                                    choices=[('', 'Select Frequency'),
                                            ('daily', 'Daily'), ('alternate_days', 'Alternate Days'),
                                            ('twice_week', 'Twice a Week'), ('weekly', 'Weekly')])
    
    tutor_comments = TextAreaField('Additional Comments', validators=[Optional()],
                                 render_kw={'rows': 4, 'placeholder': 'Any additional notes about the demo session'})
    
    submit = SubmitField('Submit Feedback')

class ConvertDemoForm(FlaskForm):
    """Form for converting demo student to regular student"""
    
    demo_student_id = HiddenField('Demo Student ID', validators=[DataRequired()])
    
    # Additional fields that weren't in demo form
    date_of_birth = DateField('Date of Birth', validators=[DataRequired()])
    
    address = TextAreaField('Complete Address', validators=[DataRequired()],
                           render_kw={'rows': 3, 'placeholder': 'Enter complete address'})
    
    state = StringField('State', validators=[DataRequired()],
                       render_kw={'placeholder': 'Enter state'})
    
    pin_code = StringField('Pin Code', validators=[DataRequired(), Length(max=10)],
                          render_kw={'placeholder': 'Enter pin code'})
    
    school_name = StringField('School Name', validators=[DataRequired()],
                             render_kw={'placeholder': 'Enter school name'})
    
    academic_year = StringField('Academic Year', validators=[DataRequired()],
                               render_kw={'placeholder': 'e.g., 2024-25'})
    
    # Fee Structure
    total_fee = SelectField('Fee Package', validators=[DataRequired()],
                           choices=[('', 'Select Fee Package'),
                                   ('5000', '₹5,000/month - Basic'),
                                   ('8000', '₹8,000/month - Standard'),
                                   ('12000', '₹12,000/month - Premium')])
    
    payment_mode = SelectField('Payment Mode', validators=[DataRequired()],
                              choices=[('monthly', 'Monthly'), ('quarterly', 'Quarterly'),
                                      ('half_yearly', 'Half Yearly'), ('yearly', 'Yearly')])
    
    # Parent Details (additional)
    father_name = StringField('Father Name', validators=[DataRequired()],
                             render_kw={'placeholder': "Enter father's name"})
    
    mother_name = StringField('Mother Name', validators=[DataRequired()],
                             render_kw={'placeholder': "Enter mother's name"})
    
    parent_occupation = StringField('Parent Occupation', validators=[Optional()],
                                   render_kw={'placeholder': 'Enter parent occupation'})
    
    conversion_notes = TextAreaField('Conversion Notes', validators=[Optional()],
                                   render_kw={'rows': 3, 'placeholder': 'Notes about the conversion'})
    
    submit = SubmitField('Convert to Regular Student')