from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, DateField, TimeField, IntegerField, SelectMultipleField, BooleanField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Optional, NumberRange, Length, ValidationError
from wtforms.widgets import TextArea, Select
from datetime import datetime, date, time
from app.models.tutor import Tutor
from app.models.student import Student
from app.models.department import Department

class MultiCheckboxField(SelectMultipleField):
    """Custom field for multiple checkboxes"""
    def pre_validate(self, form):
        # Disable pre-validation for dynamic choices
        pass

class CreateClassForm(FlaskForm):
    # Basic Class Information
    subject = StringField('Subject', validators=[DataRequired(), Length(max=100)], 
                         render_kw={'placeholder': 'Enter subject name'})
    
    class_type = SelectField('Class Type', validators=[DataRequired()], 
                            choices=[('one_on_one', 'One-on-One'), ('group', 'Group Class'), ('demo', 'Demo Class')])
    
    grade = StringField('Grade', validators=[Optional(), Length(max=10)], 
                       render_kw={'placeholder': 'e.g., 10, 12, Graduate'})
    
    board = StringField('Board', validators=[Optional(), Length(max=50)], 
                       render_kw={'placeholder': 'e.g., CBSE, ICSE, State Board'})
    
    # Scheduling
    scheduled_date = DateField('Scheduled Date', validators=[DataRequired()])
    
    scheduled_time = TimeField('Start Time', validators=[DataRequired()])
    
    duration = IntegerField('Duration (minutes)', validators=[DataRequired(), NumberRange(min=15, max=300)], 
                           render_kw={'placeholder': '60'})
    
    # Tutor Assignment
    tutor_id = SelectField('Assign Tutor', validators=[DataRequired()],coerce=int)
    
    # Student Assignment
    primary_student_id = SelectField('Primary Student', validators=[Optional()], coerce=int)
    
    students = MultiCheckboxField('Students (for Group Classes)', validators=[Optional()], coerce=int)
    
    max_students = IntegerField('Maximum Students (for Group Classes)', validators=[Optional(), NumberRange(min=1, max=20)], 
                               default=1, render_kw={'placeholder': '5'})
    
    # Platform Information
    platform = SelectField('Platform', validators=[Optional()], 
                           choices=[('', 'Select Platform'), ('zoom', 'Zoom'), ('google_meet', 'Google Meet'), 
                                  ('teams', 'Microsoft Teams'), ('other', 'Other')])
    
    meeting_link = StringField('Meeting Link', validators=[Optional(), Length(max=500)], 
                              render_kw={'placeholder': 'https://zoom.us/j/...'})
    
    meeting_id = StringField('Meeting ID', validators=[Optional(), Length(max=100)], 
                            render_kw={'placeholder': 'Meeting ID or Room Number'})
    
    meeting_password = StringField('Meeting Password', validators=[Optional(), Length(max=50)], 
                                  render_kw={'placeholder': 'Meeting password if required'})
    
    backup_link = StringField('Backup Meeting Link', validators=[Optional(), Length(max=500)], 
                             render_kw={'placeholder': 'Alternative meeting link'})
    
    # Additional Information
    class_notes = TextAreaField('Class Notes', validators=[Optional()], 
                               render_kw={'placeholder': 'Any additional notes for this class', 'rows': 3})
    
    # Recurring Class Options
    is_recurring = BooleanField('Create Recurring Classes')
    
    recurring_frequency = SelectField('Frequency', validators=[Optional()], 
                                     choices=[('', 'Select Frequency'), ('daily', 'Daily'), ('weekly', 'Weekly'), 
                                            ('monthly', 'Monthly')])
    
    recurring_count = IntegerField('Number of Classes', validators=[Optional(), NumberRange(min=1, max=100)], 
                                  render_kw={'placeholder': 'How many classes to create'})
    
    recurring_end_date = DateField('End Date', validators=[Optional()])
    
    submit = SubmitField('Create Class')
    
    def __init__(self, department_id=None, *args, **kwargs):
        super(CreateClassForm, self).__init__(*args, **kwargs)
        
        # Populate tutor choices
        tutor_query = Tutor.query.join(Tutor.user).filter(Tutor.status == 'active')
        if department_id:
            tutor_query = tutor_query.filter(Tutor.user.has(department_id=department_id))
        
        tutors = tutor_query.all()
        self.tutor_id.choices = [(0, 'Select Tutor')] + \
            [(t.id, f"{t.user.full_name} - {', '.join(t.get_subjects()[:2])}") for t in tutors]
        
        # Populate student choices
        student_query = Student.query.filter(Student.is_active == True)
        if department_id:
            student_query = student_query.filter_by(department_id=department_id)
        
        students = student_query.all()
        self.primary_student_id.choices = [(0, 'Select Student')] + \
            [(s.id, f"{s.full_name} - Grade {s.grade}") for s in students]
        
        self.students.choices = [(s.id, f"{s.full_name} - Grade {s.grade}") for s in students]
    
    def validate_scheduled_date(self, scheduled_date):
        if scheduled_date.data < date.today():
            raise ValidationError('Scheduled date cannot be in the past.')
    
    def validate_scheduled_time(self, scheduled_time):
        if self.scheduled_date.data == date.today() and scheduled_time.data < datetime.now().time():
            raise ValidationError('Scheduled time cannot be in the past for today.')
    
    def validate_students(self, students):
        if self.class_type.data == 'group' and not students.data and not self.primary_student_id.data:
            raise ValidationError('Group classes must have at least one student assigned.')
    
    def validate_primary_student_id(self, primary_student_id):
        if self.class_type.data == 'one_on_one' and not primary_student_id.data:
            raise ValidationError('One-on-one classes must have a primary student assigned.')
    
    def validate_recurring_count(self, recurring_count):
        if self.is_recurring.data and not recurring_count.data and not self.recurring_end_date.data:
            raise ValidationError('For recurring classes, specify either number of classes or end date.')

class EditClassForm(CreateClassForm):
    class_id = HiddenField()
    submit = SubmitField('Update Class')
    
    def validate_scheduled_date(self, scheduled_date):
        # Allow editing past classes for rescheduling
        pass
    
    def validate_scheduled_time(self, scheduled_time):
        # Allow editing past times for rescheduling
        pass

class RescheduleClassForm(FlaskForm):
    class_id = HiddenField()
    new_date = DateField('New Date', validators=[DataRequired()])
    new_time = TimeField('New Time', validators=[DataRequired()])
    reason = TextAreaField('Reason for Rescheduling', validators=[Optional()], 
                          render_kw={'placeholder': 'Why is this class being rescheduled?', 'rows': 3})
    notify_participants = BooleanField('Notify Participants', default=True)
    submit = SubmitField('Reschedule Class')
    
    def validate_new_date(self, new_date):
        if new_date.data < date.today():
            raise ValidationError('New date cannot be in the past.')
    
    def validate_new_time(self, new_time):
        if self.new_date.data == date.today() and new_time.data < datetime.now().time():
            raise ValidationError('New time cannot be in the past for today.')

class CancelClassForm(FlaskForm):
    class_id = HiddenField()
    reason = SelectField('Cancellation Reason', validators=[DataRequired()], 
                        choices=[('tutor_unavailable', 'Tutor Unavailable'), 
                               ('student_unavailable', 'Student Unavailable'), 
                               ('technical_issues', 'Technical Issues'), 
                               ('emergency', 'Emergency'), 
                               ('other', 'Other')])
    
    custom_reason = TextAreaField('Custom Reason', validators=[Optional()], 
                                 render_kw={'placeholder': 'Please specify if Other is selected', 'rows': 2})
    
    notify_participants = BooleanField('Notify Participants', default=True)
    
    refund_required = BooleanField('Refund Required')
    
    reschedule_option = BooleanField('Offer Reschedule Option to Students')
    
    submit = SubmitField('Cancel Class')
    
    def validate_custom_reason(self, custom_reason):
        if self.reason.data == 'other' and not custom_reason.data:
            raise ValidationError('Please specify the reason when selecting Other.')

class AttendanceForm(FlaskForm):
    class_id = HiddenField()
    
    # Tutor Attendance
    tutor_present = BooleanField('Tutor Present', default=True)
    tutor_join_time = TimeField('Tutor Join Time', validators=[Optional()])
    tutor_leave_time = TimeField('Tutor Leave Time', validators=[Optional()])
    tutor_absence_reason = SelectField('Tutor Absence Reason', validators=[Optional()], 
                                      choices=[('', 'Select Reason'), ('sick', 'Sick'), ('emergency', 'Emergency'), 
                                             ('technical', 'Technical Issues'), ('other', 'Other')])
    
    # Dynamic student attendance fields will be added via JavaScript
    attendance_notes = TextAreaField('Attendance Notes', validators=[Optional()], 
                                    render_kw={'placeholder': 'Any notes about the attendance', 'rows': 3})
    
    submit = SubmitField('Mark Attendance')

class ClassFeedbackForm(FlaskForm):
    class_id = HiddenField()
    
    # Topics Covered
    topics_covered = TextAreaField('Topics Covered', validators=[Optional()], 
                                  render_kw={'placeholder': 'What topics were covered in this class?', 'rows': 3})
    
    # Homework Assigned
    homework_assigned = TextAreaField('Homework Assigned', validators=[Optional()], 
                                     render_kw={'placeholder': 'Any homework or assignments given', 'rows': 2})
    
    # Class Notes
    class_notes = TextAreaField('Class Notes', validators=[Optional()], 
                               render_kw={'placeholder': 'Additional notes about the class', 'rows': 4})
    
    # Student Performance
    student_engagement = SelectField('Student Engagement', validators=[Optional()], 
                                    choices=[('', 'Rate Engagement'), ('excellent', 'Excellent'), 
                                           ('good', 'Good'), ('average', 'Average'), ('poor', 'Poor')])
    
    participation_quality = SelectField('Participation Quality', validators=[Optional()], 
                                       choices=[('', 'Rate Participation'), ('excellent', 'Excellent'), 
                                              ('good', 'Good'), ('average', 'Average'), ('poor', 'Poor')])
    
    # Overall Feedback
    tutor_feedback = TextAreaField('Tutor Feedback', validators=[Optional()], 
                                  render_kw={'placeholder': 'Overall feedback about the class and student performance', 'rows': 4})
    
    # Next Class Preparation
    next_class_preparation = TextAreaField('Next Class Preparation', validators=[Optional()], 
                                          render_kw={'placeholder': 'What should be prepared for the next class?', 'rows': 2})
    
    submit = SubmitField('Submit Feedback')

# Fix in app/forms/class_forms.py - Replace the incomplete BulkClassForm

class BulkClassForm(FlaskForm):
    # Basic Information
    subject = StringField('Subject', validators=[DataRequired(), Length(max=100)])
    grade = StringField('Grade', validators=[DataRequired(), Length(max=10)])
    class_type = SelectField('Class Type', validators=[DataRequired()], 
                            choices=[('one_on_one', 'One-on-One'), ('group', 'Group Class')])
    duration = IntegerField('Duration (minutes)', validators=[DataRequired(), NumberRange(min=15, max=300)])
    
    # Assignment
    tutor_id = SelectField('Tutor', validators=[DataRequired()], coerce=int)
    students = MultiCheckboxField('Students', validators=[DataRequired()], coerce=int)
    meeting_id = StringField('Meeting ID', validators=[Optional(), Length(max=100)], 
                            render_kw={'placeholder': 'Meeting ID or Room Number'})
    class_notes = TextAreaField('Class Notes', validators=[Optional()], 
                               render_kw={'placeholder': 'Any additional notes for this class', 'rows': 3})
    
    # Schedule Pattern - THESE ARE THE MISSING FIELDS
    start_date = DateField('Start Date', validators=[DataRequired()])
    end_date = DateField('End Date', validators=[DataRequired()])
    start_time = TimeField('Start Time', validators=[DataRequired()])
    days_of_week = MultiCheckboxField('Days of Week', validators=[DataRequired()], coerce=int,
                                     choices=[(0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'), 
                                            (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday')])
    
    submit = SubmitField('Create Bulk Classes')
    
    def __init__(self, department_id=None, *args, **kwargs):
        super(BulkClassForm, self).__init__(*args, **kwargs)
        
        # Populate tutor choices
        tutor_query = Tutor.query.join(Tutor.user).filter(Tutor.status == 'active')
        if department_id:
            tutor_query = tutor_query.filter(Tutor.user.has(department_id=department_id))
        
        tutors = tutor_query.all()
        self.tutor_id.choices = [(0, 'Select Tutor')] + \
            [(t.id, f"{t.user.full_name}") for t in tutors]
        
        # Populate student choices
        student_query = Student.query.filter(Student.is_active == True)
        if department_id:
            student_query = student_query.filter_by(department_id=department_id)
        
        students = student_query.all()
        self.students.choices = [(s.id, f"{s.full_name} - Grade {s.grade}") for s in students]
    
    def validate_end_date(self, end_date):
        if end_date.data <= self.start_date.data:
            raise ValidationError('End date must be after start date.')
    
    def validate_students(self, students):
        if not students.data:
            raise ValidationError('At least one student must be selected.')

class ClassSearchForm(FlaskForm):
    search_query = StringField('Search', validators=[Optional()], 
                              render_kw={'placeholder': 'Search by subject, tutor, or student name'})
    
    date_from = DateField('From Date', validators=[Optional()])
    
    date_to = DateField('To Date', validators=[Optional()])
    
    tutor_id = SelectField('Tutor', validators=[Optional()], coerce=int)
    
    student_id = SelectField('Student', validators=[Optional()], coerce=int)
    
    class_type = SelectField('Class Type', validators=[Optional()], 
                            choices=[('', 'All Types'), ('one_on_one', 'One-on-One'), 
                                   ('group', 'Group'), ('demo', 'Demo')])
    
    status = SelectField('Status', validators=[Optional()], 
                        choices=[('', 'All Status'), ('scheduled', 'Scheduled'), ('ongoing', 'Ongoing'), 
                               ('completed', 'Completed'), ('cancelled', 'Cancelled'), ('rescheduled', 'Rescheduled')])
    
    department_id = SelectField('Department', validators=[Optional()], coerce=int)
    
    submit = SubmitField('Search')
    
    def __init__(self, *args, **kwargs):
        super(ClassSearchForm, self).__init__(*args, **kwargs)
        
        # Populate tutor choices
        tutors = Tutor.query.join(Tutor.user).filter(Tutor.status == 'active').all()
        self.tutor_id.choices = [(0, 'All Tutors')] + \
            [(t.id, t.user.full_name) for t in tutors]
        
        # Populate student choices
        students = Student.query.filter(Student.is_active == True).all()
        self.student_id.choices = [(0, 'All Students')] + \
            [(s.id, s.full_name) for s in students]
        
        # Populate department choices
        departments = Department.query.filter(Department.is_active == True).all()
        self.department_id.choices = [(0, 'All Departments')] + \
            [(d.id, d.name) for d in departments]
            
# ADD THESE FORMS TO YOUR EXISTING app/forms/class_forms.py
# Don't replace the file - just append these at the bottom

class EditClassForm(FlaskForm):
    """Form for editing existing classes - ADD THIS TO YOUR FILE"""
    
    # Hidden field to store class ID
    class_id = HiddenField()
    
    # Basic Information (same as create but for editing)
    subject = StringField('Subject', validators=[DataRequired()], 
                         render_kw={'placeholder': 'e.g., Mathematics'})
    class_type = SelectField('Class Type', validators=[DataRequired()],
                            choices=[('one_on_one', 'One-on-One'), 
                                   ('group', 'Group'), ('demo', 'Demo')])
    grade = StringField('Grade', validators=[Optional()], 
                       render_kw={'placeholder': 'e.g., 10, 12'})
    board = StringField('Board', validators=[Optional()], 
                       render_kw={'placeholder': 'e.g., CBSE, ICSE'})
    
    # Scheduling
    scheduled_date = DateField('Scheduled Date', validators=[DataRequired()])
    scheduled_time = TimeField('Scheduled Time', validators=[DataRequired()])
    duration = IntegerField('Duration (minutes)', validators=[DataRequired(), NumberRange(min=15, max=480)])
    
    # Assignments
    tutor_id = SelectField('Tutor', validators=[DataRequired()], coerce=int)
    primary_student_id = SelectField('Primary Student', validators=[Optional()], coerce=int)
    students = SelectMultipleField('Students (for group classes)', coerce=int)
    
    # Platform and Links
    platform = SelectField('Platform', validators=[Optional()],
                          choices=[('', 'Select Platform'), ('zoom', 'Zoom'), 
                                 ('google_meet', 'Google Meet'), ('teams', 'Microsoft Teams')])
    meeting_link = StringField('Meeting Link', validators=[Optional()], 
                              render_kw={'placeholder': 'https://...'})
    meeting_id = StringField('Meeting ID', validators=[Optional()], 
                            render_kw={'placeholder': 'Meeting ID'})
    meeting_password = StringField('Meeting Password', validators=[Optional()], 
                                  render_kw={'placeholder': 'Meeting Password'})
    
    # Content
    class_notes = TextAreaField('Class Notes', validators=[Optional()], 
                               render_kw={'placeholder': 'Any additional notes', 'rows': 3})
    
    submit = SubmitField('Update Class')
    
    def __init__(self, class_obj=None, department_id=None, *args, **kwargs):
        super(EditClassForm, self).__init__(*args, **kwargs)
        
        # Same tutor/student population as your CreateClassForm
        tutor_query = Tutor.query.join(Tutor.user).filter(Tutor.status == 'active')
        if department_id:
            tutor_query = tutor_query.filter(Tutor.user.has(department_id=department_id))
        
        tutors = tutor_query.all()
        self.tutor_id.choices = [(t.id, f"{t.user.full_name} - {', '.join(t.get_subjects()[:2])}") for t in tutors]
        
        student_query = Student.query.filter(Student.is_active == True)
        if department_id:
            student_query = student_query.filter_by(department_id=department_id)
        
        students = student_query.all()
        self.primary_student_id.choices = [(0, 'No Primary Student')] + \
            [(s.id, f"{s.full_name} - Grade {s.grade}") for s in students]
        
        self.students.choices = [(s.id, f"{s.full_name} - Grade {s.grade}") for s in students]
        
        # Pre-populate form if class object provided
        if class_obj:
            self.class_id.data = class_obj.id
            self.subject.data = class_obj.subject
            self.class_type.data = class_obj.class_type
            self.grade.data = class_obj.grade
            self.board.data = class_obj.board
            self.scheduled_date.data = class_obj.scheduled_date
            self.scheduled_time.data = class_obj.scheduled_time
            self.duration.data = class_obj.duration
            self.tutor_id.data = class_obj.tutor_id
            self.primary_student_id.data = class_obj.primary_student_id or 0
            self.platform.data = class_obj.platform
            self.meeting_link.data = class_obj.meeting_link
            self.meeting_id.data = class_obj.meeting_id
            self.meeting_password.data = class_obj.meeting_password
            self.class_notes.data = class_obj.class_notes
            
            # Handle students for group classes
            if class_obj.students:
                try:
                    import json
                    student_ids = json.loads(class_obj.students)
                    self.students.data = [int(sid) for sid in student_ids]
                except:
                    self.students.data = []
    
    # EDIT-SPECIFIC VALIDATION (different from create validation)
    def validate_tutor_id(self, tutor_id):
        """Check tutor availability for the new time slot"""
        if not tutor_id.data:
            raise ValidationError('Tutor is required.')
        
        # Import here to avoid circular imports
        from app.models.class_model import Class
        
        # Check for conflicts with other classes
        class_obj = Class.query.get(self.class_id.data) if self.class_id.data else None
        exclude_class_id = class_obj.id if class_obj else None
        
        conflict_exists, conflicting_class = Class.check_time_conflict(
            tutor_id.data, 
            self.scheduled_date.data, 
            self.scheduled_time.data, 
            self.duration.data,
            exclude_class_id
        )
        
        if conflict_exists:
            raise ValidationError(f'Tutor has a conflicting class: {conflicting_class.subject} at {conflicting_class.scheduled_time}')


class BulkEditClassForm(FlaskForm):
    """Form for bulk editing multiple classes - ADD THIS TO YOUR FILE"""
    
    # Fields that can be bulk updated
    tutor_id = SelectField('Change Tutor', validators=[Optional()], coerce=int)
    platform = SelectField('Change Platform', validators=[Optional()],
                          choices=[('', 'Keep Current'), ('zoom', 'Zoom'), 
                                 ('google_meet', 'Google Meet'), ('teams', 'Microsoft Teams')])
    
    # Time adjustments
    time_adjustment = SelectField('Time Adjustment', validators=[Optional()],
                                choices=[('', 'No Change'), 
                                       ('add_15', 'Add 15 minutes'), 
                                       ('subtract_15', 'Subtract 15 minutes'),
                                       ('add_30', 'Add 30 minutes'), 
                                       ('subtract_30', 'Subtract 30 minutes')])
    
    # Duration changes
    new_duration = IntegerField('New Duration (minutes)', validators=[Optional(), NumberRange(min=15, max=480)])
    
    # Meeting link updates
    meeting_link = StringField('New Meeting Link', validators=[Optional()], 
                              render_kw={'placeholder': 'https://...'})
    
    # Additional notes
    bulk_notes = TextAreaField('Add Notes to All Classes', validators=[Optional()], 
                              render_kw={'placeholder': 'These notes will be appended to existing notes', 'rows': 3})
    
    # Selected classes (hidden field populated by JavaScript)
    selected_classes = HiddenField('Selected Classes')
    
    submit = SubmitField('Apply Bulk Changes')
    
    def __init__(self, department_id=None, *args, **kwargs):
        super(BulkEditClassForm, self).__init__(*args, **kwargs)
        
        # Same tutor population as your existing forms
        tutor_query = Tutor.query.join(Tutor.user).filter(Tutor.status == 'active')
        if department_id:
            tutor_query = tutor_query.filter(Tutor.user.has(department_id=department_id))
        
        tutors = tutor_query.all()
        self.tutor_id.choices = [(0, 'Keep Current Tutor')] + \
            [(t.id, f"{t.user.full_name} - {', '.join(t.get_subjects()[:2])}") for t in tutors]
    
    def validate_selected_classes(self, selected_classes):
        """Validate that classes are selected"""
        if not selected_classes.data:
            raise ValidationError('No classes selected for bulk edit.')
        
        try:
            import json
            class_ids = json.loads(selected_classes.data)
            if not class_ids:
                raise ValidationError('No classes selected for bulk edit.')
        except:
            raise ValidationError('Invalid class selection data.')