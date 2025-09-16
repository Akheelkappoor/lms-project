from flask_wtf import FlaskForm
from wtforms import SelectField, TextAreaField, DateField, DecimalField, BooleanField, StringField
from wtforms.validators import DataRequired, Optional, NumberRange, Length
from datetime import date

class GraduateStudentForm(FlaskForm):
    """Form for graduating a student"""
    final_grade = SelectField('Final Grade', choices=[
        ('', 'Select Grade (Optional)'),
        ('A+', 'A+ (Outstanding - 95-100%)'),
        ('A', 'A (Excellent - 90-94%)'),  
        ('B+', 'B+ (Very Good - 85-89%)'),
        ('B', 'B (Good - 80-84%)'),
        ('C+', 'C+ (Above Average - 75-79%)'),
        ('C', 'C (Average - 70-74%)'),
        ('D', 'D (Below Average - 60-69%)'),
        ('F', 'F (Fail - Below 60%)')
    ], validators=[Optional()])
    
    graduation_date = DateField('Graduation Date', default=date.today, 
                               validators=[DataRequired()])
    
    overall_performance = SelectField('Overall Performance Rating', choices=[
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('satisfactory', 'Satisfactory'),
        ('needs_improvement', 'Needs Improvement')
    ], validators=[DataRequired()], default='good')
    
    feedback = TextAreaField('Graduation Feedback/Comments', 
                           validators=[Optional(), Length(max=1000)],
                           render_kw={'rows': 4, 'placeholder': 'Congratulations message, achievements, recommendations, etc.'})
    
    issue_certificate = BooleanField('Issue Completion Certificate', default=True)
    
    achievements = TextAreaField('Notable Achievements', 
                                validators=[Optional(), Length(max=500)],
                                render_kw={'rows': 3, 'placeholder': 'List any notable achievements, improvements, or recognitions'})
    
    # Manual Override Options
    manual_override = BooleanField('Manual Override (Bypass Eligibility Checks)', default=False)
    override_reason = TextAreaField('Override Reason', 
                                  validators=[Optional(), Length(max=300)],
                                  render_kw={'rows': 2, 'placeholder': 'Required when using manual override - explain why normal requirements are being bypassed'})

class DropStudentForm(FlaskForm):
    """Form for dropping a student"""
    drop_reason = SelectField('Primary Drop Reason', choices=[
        ('voluntary', 'Voluntary (Student/Parent Choice)'),
        ('academic', 'Academic Performance Issues'),
        ('financial', 'Financial Difficulties'),
        ('behavioral', 'Behavioral Issues'),
        ('attendance', 'Poor Attendance'),
        ('medical', 'Medical/Health Reasons'),
        ('relocation', 'Student/Family Relocated'),
        ('dissatisfaction', 'Dissatisfaction with Service'),
        ('schedule_conflict', 'Schedule/Time Conflicts'),
        ('other', 'Other Reasons')
    ], validators=[DataRequired()])
    
    detailed_reason = TextAreaField('Detailed Reason/Notes', 
                                  validators=[DataRequired(), Length(min=10, max=1000)],
                                  render_kw={'rows': 4, 'placeholder': 'Please provide specific details about the reason for dropping'})
    
    drop_date = DateField('Drop Date', default=date.today, 
                         validators=[DataRequired()])
    
    refund_amount = DecimalField('Refund Amount (₹)', places=2, 
                               validators=[Optional(), NumberRange(min=0, max=999999.99)],
                               render_kw={'placeholder': '0.00'})
    
    refund_reason = TextAreaField('Refund Justification', 
                                validators=[Optional(), Length(max=500)],
                                render_kw={'rows': 2, 'placeholder': 'Explain refund calculation if applicable'})
    
    exit_interview_conducted = BooleanField('Exit Interview Conducted')
    
    exit_interview_notes = TextAreaField('Exit Interview Notes', 
                                       validators=[Optional(), Length(max=1000)],
                                       render_kw={'rows': 4, 'placeholder': 'Key points from exit interview'})
    
    cancel_future_classes = BooleanField('Cancel All Future Classes', default=True)
    
    notify_tutor = BooleanField('Notify Assigned Tutor(s)', default=True)
    
    notify_parents = BooleanField('Send Notification to Parents', default=True)
    
    re_enrollment_allowed = BooleanField('Allow Future Re-enrollment', default=True)
    
    blacklist_student = BooleanField('Add to Blacklist (Permanent Ban)', default=False)
    
    internal_notes = TextAreaField('Internal Notes (Admin Only)', 
                                 validators=[Optional(), Length(max=500)],
                                 render_kw={'rows': 3, 'placeholder': 'Internal notes not shared with student/parents'})
    
    # Manual Override Options
    manual_override = BooleanField('Manual Override (Force Drop)', default=False)
    override_reason = TextAreaField('Override Reason', 
                                  validators=[Optional(), Length(max=300)],
                                  render_kw={'rows': 2, 'placeholder': 'Required when using manual override - explain why student is being dropped despite restrictions'})

class StudentStatusChangeForm(FlaskForm):
    """Form for general status changes (pause/reactivate)"""
    new_status = SelectField('New Status', choices=[
        ('active', 'Active'),
        ('paused', 'Paused/On Hold'),
        ('completed', 'Completed'),
        ('dropped', 'Dropped')
    ], validators=[DataRequired()])
    
    reason = TextAreaField('Reason for Status Change', 
                          validators=[DataRequired(), Length(min=5, max=500)],
                          render_kw={'rows': 3, 'placeholder': 'Explain why the status is being changed'})
    
    effective_date = DateField('Effective Date', default=date.today, 
                              validators=[DataRequired()])
    
    notify_student = BooleanField('Send Notification to Student', default=True)
    
    notify_parents = BooleanField('Send Notification to Parents', default=True)
    
    # Manual Override Options
    manual_override = BooleanField('Manual Override (Force Drop)', default=False)
    override_reason = TextAreaField('Override Reason', 
                                  validators=[Optional(), Length(max=300)],
                                  render_kw={'rows': 2, 'placeholder': 'Required when using manual override - explain why student is being dropped despite restrictions'})

class ReactivateStudentForm(FlaskForm):
    """Form for reactivating a dropped/paused student"""
    reactivation_date = DateField('Reactivation Date', default=date.today, 
                                 validators=[DataRequired()])
    
    reason = TextAreaField('Reason for Reactivation', 
                          validators=[DataRequired(), Length(min=10, max=500)],
                          render_kw={'rows': 3, 'placeholder': 'Explain why the student is being reactivated'})
    
    reset_attendance = BooleanField('Reset Attendance Records', default=False)
    
    new_course_start_date = DateField('New Course Start Date (if different)', 
                                     validators=[Optional()])
    
    special_conditions = TextAreaField('Special Conditions/Notes', 
                                     validators=[Optional(), Length(max=500)],
                                     render_kw={'rows': 2, 'placeholder': 'Any special conditions for reactivation'})
    
    notify_tutor = BooleanField('Notify Assigned Tutor(s)', default=True)
    
    notify_student = BooleanField('Send Welcome Back Message', default=True)

class BulkStatusChangeForm(FlaskForm):
    """Form for bulk status changes"""
    student_ids = StringField('Student IDs (comma-separated)', validators=[DataRequired()])
    
    new_status = SelectField('New Status', choices=[
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('completed', 'Graduated/Completed'),
        ('dropped', 'Dropped')
    ], validators=[DataRequired()])
    
    reason = TextAreaField('Reason for Bulk Change', 
                          validators=[DataRequired(), Length(min=10, max=500)],
                          render_kw={'rows': 3})
    
    effective_date = DateField('Effective Date', default=date.today, 
                              validators=[DataRequired()])
    
    send_notifications = BooleanField('Send Individual Notifications', default=True)

class HoldGraduationForm(FlaskForm):
    """Form for putting student graduation on hold"""
    hold_reason = SelectField('Hold Reason', choices=[
        ('pending_review', 'Pending Administrative Review'),
        ('incomplete_requirements', 'Incomplete Requirements'),
        ('investigation', 'Under Investigation'),
        ('financial_issues', 'Financial Issues to Resolve'),
        ('academic_review', 'Academic Performance Review'),
        ('documentation', 'Missing Documentation'),
        ('other', 'Other (Specify in notes)')
    ], validators=[DataRequired()])
    
    notes = TextAreaField('Hold Notes/Details', 
                         validators=[DataRequired(), Length(min=10, max=500)],
                         render_kw={'rows': 3, 'placeholder': 'Explain why graduation is being put on hold and what needs to be resolved'})

class HoldDropForm(FlaskForm):
    """Form for putting student drop on hold (preventing drop)"""
    hold_reason = SelectField('Hold Reason', choices=[
        ('retention_effort', 'Student Retention Effort in Progress'),
        ('financial_assistance', 'Financial Assistance Being Arranged'),
        ('counseling', 'Academic/Personal Counseling in Progress'),
        ('medical_accommodation', 'Medical Accommodation Review'),
        ('appeal_process', 'Drop Appeal Process'),
        ('guardian_request', 'Guardian/Parent Request'),
        ('other', 'Other (Specify in notes)')
    ], validators=[DataRequired()])
    
    notes = TextAreaField('Hold Notes/Details', 
                         validators=[DataRequired(), Length(min=10, max=500)],
                         render_kw={'rows': 3, 'placeholder': 'Explain why drop is being prevented and what intervention is being attempted'})

class RemoveHoldForm(FlaskForm):
    """Form for removing hold status"""
    removal_reason = TextAreaField('Reason for Removing Hold', 
                                  validators=[DataRequired(), Length(min=10, max=300)],
                                  render_kw={'rows': 3, 'placeholder': 'Explain why the hold is being removed and what has been resolved'})
    
    notes = TextAreaField('Additional Notes', 
                         validators=[Optional(), Length(max=300)],
                         render_kw={'rows': 2, 'placeholder': 'Any additional information about the hold removal'})