from datetime import datetime, timedelta
from app import db
import json

class Class(db.Model):
    __tablename__ = 'classes'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Class Basic Information
    subject = db.Column(db.String(100), nullable=False)
    class_type = db.Column(db.String(20), nullable=False)  # 'one_on_one', 'group', 'demo'
    grade = db.Column(db.String(10))
    board = db.Column(db.String(50))
    
    # Scheduling
    scheduled_date = db.Column(db.Date, nullable=False)
    scheduled_time = db.Column(db.Time, nullable=False)
    duration = db.Column(db.Integer, nullable=False)  # Duration in minutes
    end_time = db.Column(db.Time)  # Calculated field
    
    # Assignments
    tutor_id = db.Column(db.Integer, db.ForeignKey('tutors.id'), nullable=False)
    primary_student_id = db.Column(db.Integer, db.ForeignKey('students.id'))  # For one-on-one
    
    # Group Classes
    students = db.Column(db.Text)  # JSON array of student IDs for group classes
    max_students = db.Column(db.Integer, default=1)
    
    # Platform and Links
    platform = db.Column(db.String(50))  # 'zoom', 'google_meet', 'teams'
    meeting_link = db.Column(db.String(500))
    meeting_id = db.Column(db.String(100))
    meeting_password = db.Column(db.String(50))
    backup_link = db.Column(db.String(500))
    
    # Class Status
    status = db.Column(db.String(20), default='scheduled')  # scheduled, ongoing, completed, cancelled, rescheduled
    completion_status = db.Column(db.String(20))  # completed, incomplete, no_show
    
    # Actual Class Timing
    actual_start_time = db.Column(db.DateTime)
    actual_end_time = db.Column(db.DateTime)
    
    # Content and Notes
    class_notes = db.Column(db.Text)
    topics_covered = db.Column(db.Text)  # JSON array
    homework_assigned = db.Column(db.Text)
    video_link = db.Column(db.String(500))
    materials = db.Column(db.Text)  # JSON array of material links/files
    
    # Feedback and Quality
    tutor_feedback = db.Column(db.Text)
    student_feedback = db.Column(db.Text)
    admin_notes = db.Column(db.Text)
    quality_score = db.Column(db.Float)
    
    # Tracking
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Recurring class information
    is_recurring = db.Column(db.Boolean, default=False)
    recurring_pattern = db.Column(db.Text)  # JSON with recurrence details
    parent_class_id = db.Column(db.Integer, db.ForeignKey('classes.id'))
    
    # Relationships
    tutor = db.relationship('Tutor', backref='classes', lazy=True)
    primary_student = db.relationship('Student', backref='primary_classes', lazy=True)
    creator = db.relationship('User', backref='created_classes', lazy=True)
    parent_class = db.relationship('Class', remote_side=[id], backref='recurring_classes')
    
    def __init__(self, **kwargs):
        super(Class, self).__init__(**kwargs)
        if self.scheduled_time and self.duration:
            self.calculate_end_time()
    
    def calculate_end_time(self):
        """Calculate end time based on start time and duration"""
        if self.scheduled_time and self.duration:
            start_datetime = datetime.combine(datetime.today(), self.scheduled_time)
            end_datetime = start_datetime + timedelta(minutes=self.duration)
            self.end_time = end_datetime.time()
    
    def get_students(self):
        """Get list of student IDs for this class"""
        if self.class_type == 'one_on_one':
            return [self.primary_student_id] if self.primary_student_id else []
        elif self.students:
            try:
                return json.loads(self.students)
            except:
                return []
        return []
    
    def set_students(self, student_ids):
        """Set students for group classes"""
        if self.class_type == 'group':
            self.students = json.dumps(student_ids)
        elif self.class_type == 'one_on_one' and student_ids:
            self.primary_student_id = student_ids[0]
    
    def add_student(self, student_id):
        """Add a student to group class"""
        if self.class_type == 'group':
            current_students = self.get_students()
            if len(current_students) < self.max_students and student_id not in current_students:
                current_students.append(student_id)
                self.set_students(current_students)
                return True
        return False
    
    def remove_student(self, student_id):
        """Remove a student from group class"""
        if self.class_type == 'group':
            current_students = self.get_students()
            if student_id in current_students:
                current_students.remove(student_id)
                self.set_students(current_students)
                return True
        return False
    
    def get_topics_covered(self):
        """Get topics covered as list"""
        if self.topics_covered:
            try:
                return json.loads(self.topics_covered)
            except:
                return []
        return []
    
    def set_topics_covered(self, topics_list):
        """Set topics covered from list"""
        self.topics_covered = json.dumps(topics_list)
    
    def get_materials(self):
        """Get materials as list"""
        if self.materials:
            try:
                return json.loads(self.materials)
            except:
                return []
        return []
    
    def set_materials(self, materials_list):
        """Set materials from list"""
        self.materials = json.dumps(materials_list)
    
    def get_recurring_pattern(self):
        """Get recurring pattern as dict"""
        if self.recurring_pattern:
            try:
                return json.loads(self.recurring_pattern)
            except:
                return {}
        return {}
    
    def set_recurring_pattern(self, pattern_dict):
        """Set recurring pattern from dict
        Format: {
            'frequency': 'weekly',  # daily, weekly, monthly
            'interval': 1,  # every 1 week
            'days_of_week': [1, 3, 5],  # Monday, Wednesday, Friday
            'end_date': '2024-12-31',
            'total_classes': 20
        }
        """
        self.recurring_pattern = json.dumps(pattern_dict)
    
    def is_today(self):
        """Check if class is scheduled for today"""
        return self.scheduled_date == datetime.now().date()
    
    def is_upcoming(self):
        """Check if class is upcoming (future)"""
        now = datetime.now()
        class_datetime = datetime.combine(self.scheduled_date, self.scheduled_time)
        return class_datetime > now
    
    def is_past(self):
        """Check if class is in the past"""
        now = datetime.now()
        class_datetime = datetime.combine(self.scheduled_date, self.scheduled_time)
        return class_datetime < now
    
    def time_until_class(self):
        """Get time remaining until class starts"""
        now = datetime.now()
        class_datetime = datetime.combine(self.scheduled_date, self.scheduled_time)
        if class_datetime > now:
            return class_datetime - now
        return timedelta(0)
    
    def get_duration_display(self):
        """Get formatted duration string"""
        hours = self.duration // 60
        minutes = self.duration % 60
        if hours > 0:
            return f"{hours}h {minutes}m" if minutes > 0 else f"{hours}h"
        return f"{minutes}m"
    
    def can_be_rescheduled(self):
        """Check if class can be rescheduled"""
        return self.status in ['scheduled'] and self.is_upcoming()
    
    def can_be_cancelled(self):
        """Check if class can be cancelled"""
        return self.status in ['scheduled'] and self.is_upcoming()
    
    def start_class(self):
        """Mark class as started"""
        self.status = 'ongoing'
        self.actual_start_time = datetime.now()
        db.session.commit()
    
    def complete_class(self, completion_status='completed'):
        """Mark class as completed"""
        self.status = 'completed'
        self.completion_status = completion_status
        self.actual_end_time = datetime.now()
        db.session.commit()
    
    def cancel_class(self, reason=None):
        """Cancel the class"""
        self.status = 'cancelled'
        if reason:
            self.admin_notes = f"Cancelled: {reason}"
        db.session.commit()
    
    def reschedule_class(self, new_date, new_time):
        """Reschedule the class"""
        self.scheduled_date = new_date
        self.scheduled_time = new_time
        self.calculate_end_time()
        self.status = 'rescheduled'
        db.session.commit()
    
    @staticmethod
    def get_classes_for_date(date_obj, tutor_id=None, student_id=None):
        """Get classes for specific date"""
        query = Class.query.filter_by(scheduled_date=date_obj)
        
        if tutor_id:
            query = query.filter_by(tutor_id=tutor_id)
        
        if student_id:
            # For group classes, need to check JSON field
            classes = query.all()
            filtered_classes = []
            for cls in classes:
                if cls.primary_student_id == student_id or student_id in cls.get_students():
                    filtered_classes.append(cls)
            return filtered_classes
        
        return query.all()
    
    @staticmethod
    def check_time_conflict(tutor_id, date_obj, start_time, duration, exclude_class_id=None):
        """Check if there's a time conflict for tutor"""
        end_time = (datetime.combine(date_obj, start_time) + timedelta(minutes=duration)).time()
        
        query = Class.query.filter(
            Class.tutor_id == tutor_id,
            Class.scheduled_date == date_obj,
            Class.status.in_(['scheduled', 'ongoing'])
        )
        
        if exclude_class_id:
            query = query.filter(Class.id != exclude_class_id)
        
        existing_classes = query.all()
        
        for existing_class in existing_classes:
            existing_end = existing_class.end_time
            
            # Check for overlap
            if (start_time < existing_end and end_time > existing_class.scheduled_time):
                return True, existing_class
        
        return False, None
    
    @staticmethod
    def get_todays_classes():
        """Get all classes scheduled for today"""
        today = datetime.now().date()
        return Class.query.filter_by(scheduled_date=today).order_by(Class.scheduled_time).all()
    
    @staticmethod
    def get_upcoming_classes(days=7):
        """Get upcoming classes within specified days"""
        start_date = datetime.now().date()
        end_date = start_date + timedelta(days=days)
        
        return Class.query.filter(
            Class.scheduled_date >= start_date,
            Class.scheduled_date <= end_date,
            Class.status.in_(['scheduled'])
        ).order_by(Class.scheduled_date, Class.scheduled_time).all()
    
    def to_dict(self):
        """Convert class to dictionary"""
        return {
            'id': self.id,
            'subject': self.subject,
            'class_type': self.class_type,
            'grade': self.grade,
            'board': self.board,
            'scheduled_date': self.scheduled_date.isoformat() if self.scheduled_date else None,
            'scheduled_time': self.scheduled_time.strftime('%H:%M') if self.scheduled_time else None,
            'duration': self.duration,
            'duration_display': self.get_duration_display(),
            'tutor_name': self.tutor.user.full_name if self.tutor and self.tutor.user else '',
            'student_names': [s.full_name for s in self.get_student_objects()],
            'status': self.status,
            'completion_status': self.completion_status,
            'platform': self.platform,
            'meeting_link': self.meeting_link,
            'is_today': self.is_today(),
            'is_upcoming': self.is_upcoming(),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def get_student_objects(self):
        """Get actual student objects for this class"""
        from app.models.student import Student
        student_ids = self.get_students()
        return Student.query.filter(Student.id.in_(student_ids)).all() if student_ids else []
    
    def __repr__(self):
        return f'<Class {self.subject} - {self.scheduled_date} {self.scheduled_time}>'
    
    def get_scheduled_datetime(self):
        """Get combined scheduled datetime"""
        if self.scheduled_date and self.scheduled_time:
            return datetime.combine(self.scheduled_date, self.scheduled_time)
        return None
    
    @property
    def scheduled_datetime(self):
        """Property to get scheduled datetime"""
        return self.get_scheduled_datetime()
    
    def can_start_soon(self, minutes_before=15):
        """Check if class can be started (within X minutes of start time)"""
        if not self.scheduled_datetime:
            return False
        
        now = datetime.now()
        time_diff = (self.scheduled_datetime - now).total_seconds()
        return 0 <= time_diff <= (minutes_before * 60)