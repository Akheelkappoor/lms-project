# app/forms/notification_forms.py

from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, BooleanField, DateTimeField, SelectMultipleField, HiddenField
from wtforms.validators import DataRequired, Length, Optional
from wtforms.widgets import TextArea, CheckboxInput, ListWidget
from datetime import datetime, timedelta
from app.models.department import Department
from app.models.user import User

class MultiCheckboxField(SelectMultipleField):
    """Custom field for multiple checkboxes"""
    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()

class SystemNotificationForm(FlaskForm):
    """Form for creating system notifications"""
    
    # Basic notification info
    title = StringField('Title', 
                       validators=[DataRequired(), Length(min=5, max=200)],
                       render_kw={'placeholder': 'Enter notification title'})
    
    message = TextAreaField('Message', 
                          validators=[DataRequired(), Length(min=10, max=2000)],
                          render_kw={'rows': 6, 'placeholder': 'Enter your message here...'})
    
    # Categorization
    type = SelectField('Notification Type', 
                      choices=[
                          ('general', 'General Announcement'),
                          ('holiday', 'Holiday Notice'),
                          ('emergency', 'Emergency Alert'),
                          ('academic', 'Academic Notice'),
                          ('administrative', 'Administrative Notice'),
                          ('maintenance', 'System Maintenance')
                      ],
                      default='general')
    
    priority = SelectField('Priority', 
                          choices=[
                              ('normal', 'Normal'),
                              ('high', 'High'),
                              ('urgent', 'Urgent'),
                              ('critical', 'Critical')
                          ],
                          default='normal')
    
    # Targeting
    target_type = SelectField('Target Audience', 
                             choices=[
                                 ('all', 'All Users'),
                                 ('department', 'Specific Departments'),
                                 ('role', 'Specific Roles'),
                                 ('individual', 'Individual Users')
                             ],
                             default='all')
    
    target_departments = MultiCheckboxField('Target Departments', 
                                          coerce=int,
                                          choices=[])
    
    target_roles = MultiCheckboxField('Target Roles',
                                    choices=[
                                        ('student', 'Students'),
                                        ('tutor', 'Tutors'),
                                        ('coordinator', 'Coordinators'),
                                        ('admin', 'Administrators')
                                    ])
    
    target_users = SelectMultipleField('Target Users', 
                                     coerce=int,
                                     choices=[])
    
    # Delivery settings
    email_enabled = BooleanField('Send Email Notification', default=True)
    popup_enabled = BooleanField('Show Popup Notification', default=False)
    include_parents = BooleanField('Include Parent Emails (for students)', default=False)
    
    # Timing
    send_immediately = BooleanField('Send Immediately', default=True)
    scheduled_for = DateTimeField('Schedule For', 
                                 validators=[Optional()],
                                 format='%Y-%m-%dT%H:%M')
    
    expires_at = DateTimeField('Expires At', 
                              validators=[Optional()],
                              format='%Y-%m-%dT%H:%M')
    
    def __init__(self, *args, **kwargs):
        super(SystemNotificationForm, self).__init__(*args, **kwargs)
        
        # Populate department choices
        departments = Department.query.filter_by(is_active=True).all()
        self.target_departments.choices = [(d.id, d.name) for d in departments]
        
        # Populate user choices (limit to reasonable number)
        users = User.query.filter_by(is_active=True).order_by(User.full_name).limit(200).all()
        self.target_users.choices = [(u.id, f"{u.full_name} ({u.get_role_display()})") for u in users]
    
    def validate(self, extra_validators=None):
        if not super().validate(extra_validators):
            return False
        
        # Custom validation for targeting
        if self.target_type.data == 'department' and not self.target_departments.data:
            self.target_departments.errors.append('Please select at least one department.')
            return False
        
        if self.target_type.data == 'role' and not self.target_roles.data:
            self.target_roles.errors.append('Please select at least one role.')
            return False
        
        if self.target_type.data == 'individual' and not self.target_users.data:
            self.target_users.errors.append('Please select at least one user.')
            return False
        
        # Validate scheduling
        if not self.send_immediately.data and not self.scheduled_for.data:
            self.scheduled_for.errors.append('Please specify when to send the notification.')
            return False
        
        if self.scheduled_for.data and self.scheduled_for.data < datetime.now():
            self.scheduled_for.errors.append('Scheduled time cannot be in the past.')
            return False
        
        if self.expires_at.data and self.expires_at.data < datetime.now():
            self.expires_at.errors.append('Expiry time cannot be in the past.')
            return False
        
        return True

class HolidayNotificationForm(FlaskForm):
    """Simplified form for holiday notifications"""
    
    title = StringField('Holiday Title', 
                       validators=[DataRequired(), Length(min=5, max=200)],
                       render_kw={'placeholder': 'e.g., Diwali Holiday'})
    
    message = TextAreaField('Holiday Message', 
                          validators=[DataRequired(), Length(min=10, max=1000)],
                          render_kw={'rows': 4, 'placeholder': 'Describe the holiday and any special instructions...'})
    
    holiday_date = DateTimeField('Holiday Date', 
                                validators=[DataRequired()],
                                format='%Y-%m-%d')
    
    target_departments = MultiCheckboxField('Departments (leave empty for all)', 
                                          coerce=int,
                                          choices=[])
    
    include_parents = BooleanField('Notify Parents', default=True)
    
    def __init__(self, *args, **kwargs):
        super(HolidayNotificationForm, self).__init__(*args, **kwargs)
        
        # Populate department choices
        departments = Department.query.filter_by(is_active=True).all()
        self.target_departments.choices = [(d.id, d.name) for d in departments]
    
    def validate(self, extra_validators=None):
        if not super().validate(extra_validators):
            return False
        
        if self.holiday_date.data and self.holiday_date.data < datetime.now().date():
            self.holiday_date.errors.append('Holiday date cannot be in the past.')
            return False
        
        return True

class EmergencyNotificationForm(FlaskForm):
    """Form for emergency notifications"""
    
    title = StringField('Emergency Title', 
                       validators=[DataRequired(), Length(min=5, max=200)],
                       render_kw={'placeholder': 'Brief emergency title'})
    
    message = TextAreaField('Emergency Message', 
                          validators=[DataRequired(), Length(min=20, max=2000)],
                          render_kw={'rows': 6, 'placeholder': 'Detailed emergency information and instructions...'})
    
    target_type = SelectField('Target Audience', 
                             choices=[
                                 ('all', 'Everyone'),
                                 ('department', 'Specific Departments')
                             ],
                             default='all')
    
    target_departments = MultiCheckboxField('Departments', 
                                          coerce=int,
                                          choices=[])
    
    def __init__(self, *args, **kwargs):
        super(EmergencyNotificationForm, self).__init__(*args, **kwargs)
        
        # Populate department choices
        departments = Department.query.filter_by(is_active=True).all()
        self.target_departments.choices = [(d.id, d.name) for d in departments]

class NotificationSearchForm(FlaskForm):
    """Form for searching notifications"""
    
    search = StringField('Search', 
                        render_kw={'placeholder': 'Search notifications...'})
    
    type = SelectField('Type', 
                      choices=[
                          ('', 'All Types'),
                          ('general', 'General'),
                          ('holiday', 'Holiday'),
                          ('emergency', 'Emergency'),
                          ('academic', 'Academic'),
                          ('administrative', 'Administrative'),
                          ('maintenance', 'Maintenance')
                      ],
                      default='')
    
    priority = SelectField('Priority', 
                          choices=[
                              ('', 'All Priorities'),
                              ('normal', 'Normal'),
                              ('high', 'High'),
                              ('urgent', 'Urgent'),
                              ('critical', 'Critical')
                          ],
                          default='')
    
    status = SelectField('Status', 
                        choices=[
                            ('', 'All'),
                            ('active', 'Active'),
                            ('expired', 'Expired'),
                            ('scheduled', 'Scheduled')
                        ],
                        default='')
    
    department = SelectField('Department', 
                           coerce=int,
                           choices=[])
    
    def __init__(self, *args, **kwargs):
        super(NotificationSearchForm, self).__init__(*args, **kwargs)
        
        # Populate department choices
        departments = Department.query.filter_by(is_active=True).all()
        self.department.choices = [(0, 'All Departments')] + [(d.id, d.name) for d in departments]

class BulkNotificationActionForm(FlaskForm):
    """Form for bulk actions on notifications"""
    
    action = SelectField('Action', 
                        choices=[
                            ('activate', 'Activate'),
                            ('deactivate', 'Deactivate'),
                            ('delete', 'Delete')
                        ])
    
    notification_ids = HiddenField('Notification IDs')

class QuickAnnouncementForm(FlaskForm):
    """Quick form for simple announcements"""
    
    title = StringField('Title', 
                       validators=[DataRequired(), Length(min=5, max=200)],
                       render_kw={'placeholder': 'Announcement title'})
    
    message = TextAreaField('Message', 
                          validators=[DataRequired(), Length(min=10, max=1000)],
                          render_kw={'rows': 4, 'placeholder': 'Your announcement...'})
    
    target_type = SelectField('Send To', 
                             choices=[
                                 ('all', 'Everyone'),
                                 ('students', 'All Students'),
                                 ('tutors', 'All Tutors'),
                                 ('my_department', 'My Department')
                             ],
                             default='all')
    
    include_email = BooleanField('Send Email', default=True)
    include_popup = BooleanField('Show Popup', default=False)