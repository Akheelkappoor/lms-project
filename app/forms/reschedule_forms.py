# app/forms/reschedule_forms.py

from flask_wtf import FlaskForm
from wtforms import (
    StringField, TextAreaField, DateField, TimeField, SelectField, 
    HiddenField, SubmitField, BooleanField
)
from wtforms.validators import DataRequired, Length, Optional, ValidationError
from datetime import datetime, date
from app.models.reschedule_request import RescheduleRequest
from app.models.class_model import Class
from app.models.tutor import Tutor
from app.models.user import User
from wtforms_sqlalchemy.fields import QuerySelectField
from app.models.user import User

class CreateRescheduleRequestForm(FlaskForm):
    class_id = HiddenField('Class ID', validators=[DataRequired()])
    requested_date = DateField('New Date', validators=[DataRequired()])
    requested_time = TimeField('New Time', validators=[DataRequired()])
    reason = TextAreaField('Reason for Rescheduling', 
                          validators=[DataRequired(), Length(min=10, max=500)],
                          render_kw={'placeholder': 'Please explain why you need to reschedule this class...', 'rows': 4})
    submit = SubmitField('Submit Reschedule Request')
    
    def validate_requested_date(self, requested_date):
        """Validate that the new date is not in the past"""
        if requested_date.data < date.today():
            raise ValidationError('New date cannot be in the past.')
    
    def validate_requested_time(self, requested_time):
        """Validate that the new time is not in the past if it's today"""
        if (self.requested_date.data == date.today() and 
            requested_time.data < datetime.now().time()):
            raise ValidationError('New time cannot be in the past for today.')
    
    def validate_class_id(self, class_id):
        """Validate that the class exists and can be rescheduled"""
        class_item = Class.query.get(class_id.data)
        if not class_item:
            raise ValidationError('Class not found.')
        
        if not class_item.can_be_rescheduled():
            raise ValidationError('This class cannot be rescheduled.')
        
        # Check if there's already a pending request for this class
        existing_request = RescheduleRequest.query.filter_by(
            class_id=class_id.data,
            status='pending'
        ).first()
        
        if existing_request:
            raise ValidationError('There is already a pending reschedule request for this class.')

class ReviewRescheduleRequestForm(FlaskForm):
    request_id = HiddenField('Request ID', validators=[DataRequired()])
    action = SelectField('Action', 
                        validators=[DataRequired()],
                        choices=[('', 'Select Action'), ('approve', 'Approve'), ('reject', 'Reject')])
    review_notes = TextAreaField('Review Notes', 
                                validators=[Optional(), Length(max=1000)],
                                render_kw={'placeholder': 'Add any comments about your decision...', 'rows': 3})
    force_approve = BooleanField('Force Approve (Override Conflicts)', 
                                render_kw={'title': 'Check this to approve even if there are conflicts'})
    submit = SubmitField('Submit Review')
    
    def validate_review_notes(self, review_notes):
        """Make review notes required for rejection"""
        if self.action.data == 'reject' and not review_notes.data:
            raise ValidationError('Please provide a reason for rejecting this request.')

class BulkRescheduleRequestForm(FlaskForm):
    """Form for handling multiple reschedule requests at once"""
    action = SelectField('Bulk Action',
                        validators=[DataRequired()],
                        choices=[('', 'Select Action'), ('approve_all', 'Approve All'), ('reject_all', 'Reject All')])
    review_notes = TextAreaField('Bulk Review Notes',
                                validators=[Optional(), Length(max=1000)],
                                render_kw={'placeholder': 'Notes that will be applied to all selected requests...', 'rows': 3})
    submit = SubmitField('Apply to Selected')

class RescheduleRequestSearchForm(FlaskForm):
    """Form for searching and filtering reschedule requests"""
    status = SelectField('Status',
                        choices=[('', 'All Status'), ('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')])
    
    tutor = SelectField('Tutor', choices=[])

    date_from = DateField('From Date', validators=[Optional()])
    date_to = DateField('To Date', validators=[Optional()])
    search = StringField('Search', 
                        render_kw={'placeholder': 'Search by reason, class details...'})
    submit = SubmitField('Filter')
    
    def __init__(self, department_id=None, *args, **kwargs):
        super(RescheduleRequestSearchForm, self).__init__(*args, **kwargs)
        
        # Populate tutor choices based on department
        from app.models.tutor import Tutor
        from app.models.user import User
        
        tutor_query = Tutor.query.join(User).filter(Tutor.status == 'active')
        
        if department_id:
            tutor_query = tutor_query.filter(User.department_id == department_id)
        
        tutors = tutor_query.all()
        self.tutor.choices = [('', 'All Tutors')] + [(str(t.id), t.user.full_name) for t in tutors]
    
    def validate_date_to(self, date_to):
        """Validate that end date is after start date"""
        if self.date_from.data and date_to.data and date_to.data < self.date_from.data:
            raise ValidationError('End date must be after start date.')

class QuickRescheduleForm(FlaskForm):
    """Simple form for quick reschedule by admin/coordinator"""
    class_id = HiddenField('Class ID', validators=[DataRequired()])
    new_date = DateField('New Date', validators=[DataRequired()])
    new_time = TimeField('New Time', validators=[DataRequired()])
    reason = TextAreaField('Reason', 
                          validators=[DataRequired(), Length(min=5, max=200)],
                          render_kw={'placeholder': 'Brief reason for reschedule...', 'rows': 2})
    notify_tutor = BooleanField('Notify Tutor', default=True)
    notify_students = BooleanField('Notify Students', default=True)
    submit = SubmitField('Reschedule Now')
    
    def validate_new_date(self, new_date):
        if new_date.data < date.today():
            raise ValidationError('New date cannot be in the past.')
    
    def validate_new_time(self, new_time):
        if (self.new_date.data == date.today() and 
            new_time.data < datetime.now().time()):
            raise ValidationError('New time cannot be in the past for today.')