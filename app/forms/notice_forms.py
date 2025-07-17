# app/forms/notice_forms.py

from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, MultipleFileField
from wtforms import StringField, TextAreaField, SelectField, BooleanField, DateTimeField, SubmitField, SelectMultipleField
from wtforms.validators import DataRequired, Length, Optional
from wtforms.widgets import ListWidget, CheckboxInput
from app.models.department import Department
from app.models.user import User

class MultiCheckboxField(SelectMultipleField):
    """Custom field for multiple checkboxes"""
    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()

class NoticeForm(FlaskForm):
    """Form for creating and editing notices"""
    
    title = StringField('Notice Title', validators=[
        DataRequired(message='Title is required'),
        Length(min=5, max=200, message='Title must be between 5 and 200 characters')
    ])
    
    content = TextAreaField('Notice Content', validators=[
        DataRequired(message='Content is required'),
        Length(min=10, message='Content must be at least 10 characters')
    ])
    
    category = SelectField('Category', validators=[DataRequired()], choices=[
        ('academic', 'Academic'),
        ('administrative', 'Administrative'),
        ('emergency', 'Emergency'),
        ('celebration', 'Celebration')
    ])
    
    priority = SelectField('Priority', validators=[DataRequired()], choices=[
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent')
    ])
    
    target_type = SelectField('Target Audience', validators=[DataRequired()], choices=[
        ('all', 'All Users'),
        ('department', 'Specific Departments'),
        ('individual', 'Specific Users')
    ])
    
    target_departments = MultiCheckboxField('Target Departments', coerce=int)
    target_users = MultiCheckboxField('Target Users', coerce=int)
    
    requires_acknowledgment = BooleanField('Requires Acknowledgment')
    
    publish_date = DateTimeField('Publish Date (Optional)', 
                               format='%Y-%m-%dT%H:%M',
                               validators=[Optional()])
    
    expiry_date = DateTimeField('Expiry Date (Optional)', 
                              format='%Y-%m-%dT%H:%M',
                              validators=[Optional()])
    
    attachments = MultipleFileField('Attachments (Optional)', validators=[
        FileAllowed(['pdf', 'doc', 'docx', 'jpg', 'png', 'jpeg', 'gif', 'txt'], 
                   'Only PDF, DOC, DOCX, JPG, PNG, GIF, and TXT files allowed!')
    ])
    
    submit = SubmitField('Create Notice')
    publish = SubmitField('Create & Publish')
    
    def __init__(self, *args, **kwargs):
        super(NoticeForm, self).__init__(*args, **kwargs)
        
        # Populate department choices
        self.target_departments.choices = [(d.id, d.name) for d in 
                                         Department.query.filter_by(is_active=True).all()]
        
        # Populate user choices (limit to active users)
        self.target_users.choices = [(u.id, f"{u.full_name} ({u.role})") for u in 
                                   User.query.filter_by(is_active=True).order_by(User.full_name).all()]
    
    def validate(self, extra_validators=None):
        """Custom validation"""
        initial_validation = super(NoticeForm, self).validate(extra_validators)
        if not initial_validation:
            return False
        
        # Validate target audience selections
        if self.target_type.data == 'department':
            if not self.target_departments.data:
                self.target_departments.errors.append('Please select at least one department')
                return False
        elif self.target_type.data == 'individual':
            if not self.target_users.data:
                self.target_users.errors.append('Please select at least one user')
                return False
        
        # Validate dates
        if self.publish_date.data and self.expiry_date.data:
            if self.publish_date.data >= self.expiry_date.data:
                self.expiry_date.errors.append('Expiry date must be after publish date')
                return False
        
        return True


class NoticeSearchForm(FlaskForm):
    """Form for searching and filtering notices"""
    
    search = StringField('Search', validators=[Optional()])
    
    category = SelectField('Category', validators=[Optional()], choices=[
        ('', 'All Categories'),
        ('academic', 'Academic'),
        ('administrative', 'Administrative'),
        ('emergency', 'Emergency'),
        ('celebration', 'Celebration')
    ])
    
    priority = SelectField('Priority', validators=[Optional()], choices=[
        ('', 'All Priorities'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent')
    ])
    
    status = SelectField('Status', validators=[Optional()], choices=[
        ('', 'All Statuses'),
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('expired', 'Expired')
    ])
    
    department = SelectField('Department', validators=[Optional()], coerce=int)
    
    submit = SubmitField('Filter')
    
    def __init__(self, *args, **kwargs):
        super(NoticeSearchForm, self).__init__(*args, **kwargs)
        
        # Populate department choices
        self.department.choices = [(0, 'All Departments')] + \
            [(d.id, d.name) for d in Department.query.filter_by(is_active=True).all()]


class UserNoticeSearchForm(FlaskForm):
    """Form for user notice inbox filtering"""
    
    search = StringField('Search Notices', validators=[Optional()])
    
    category = SelectField('Category', validators=[Optional()], choices=[
        ('', 'All Categories'),
        ('academic', 'Academic'),
        ('administrative', 'Administrative'),
        ('emergency', 'Emergency'),
        ('celebration', 'Celebration')
    ])
    
    read_status = SelectField('Read Status', validators=[Optional()], choices=[
        ('', 'All Notices'),
        ('unread', 'Unread Only'),
        ('read', 'Read Only')
    ])
    
    acknowledgment_status = SelectField('Acknowledgment Status', validators=[Optional()], choices=[
        ('', 'All Notices'),
        ('pending', 'Pending Acknowledgment'),
        ('acknowledged', 'Acknowledged')
    ])
    
    submit = SubmitField('Filter')


class BulkNoticeActionForm(FlaskForm):
    """Form for bulk notice actions"""
    
    action = SelectField('Action', validators=[DataRequired()], choices=[
        ('delete', 'Delete Selected'),
        ('publish', 'Publish Selected'),
        ('unpublish', 'Unpublish Selected')
    ])
    
    notice_ids = StringField('Selected Notices', validators=[DataRequired()])
    
    submit = SubmitField('Apply Action')