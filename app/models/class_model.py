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
    scheduled_date = db.Column(db.Date, nullable=False, index=True)
    scheduled_time = db.Column(db.Time, nullable=False, index=True)
    duration = db.Column(db.Integer, nullable=False)  # Duration in minutes
    end_time = db.Column(db.Time)  # Calculated field
    
    # Assignments
    tutor_id = db.Column(db.Integer, db.ForeignKey('tutors.id'), nullable=False, index=True)
    primary_student_id = db.Column(db.Integer, db.ForeignKey('students.id'), index=True)  # For one-on-one

    # ADD THIS NEW FIELD - Demo student relationship
    demo_student_id = db.Column(db.Integer, db.ForeignKey('demo_students.id'), nullable=True)
    
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
    status = db.Column(db.String(20), default='scheduled', index=True)  # scheduled, ongoing, completed, cancelled, rescheduled
    completion_status = db.Column(db.String(30), index=True)  # completed, incomplete, no_show, cancelled_student_dropped
    
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
    
    # ADD THIS RELATIONSHIP
    demo_student_profile = db.relationship('DemoStudent', 
                                         foreign_keys=[demo_student_id], 
                                         lazy=True)

    # Relationships
    tutor = db.relationship('Tutor', backref='classes', lazy=True)
    primary_student = db.relationship('Student', backref='primary_classes', lazy=True)
    creator = db.relationship('User', 
                            foreign_keys=[created_by], 
                            backref='created_classes', 
                            lazy=True)
    parent_class = db.relationship('Class', 
                                 remote_side=[id], 
                                 backref='recurring_classes')
    
    
    video_uploaded_at = db.Column(db.DateTime)  # When video was uploaded
    video_upload_deadline = db.Column(db.DateTime)  # 24-hour deadline
    video_reminder_sent = db.Column(db.Boolean, default=False)  # 1-hour reminder sent
    video_final_warning_sent = db.Column(db.Boolean, default=False)  # Final warning sent
    
    # 🔥 NEW: Auto-Attendance Tracking
    auto_attendance_marked = db.Column(db.Boolean, default=False)  # Auto-attendance applied on start
    attendance_review_completed = db.Column(db.Boolean, default=False)  # Tutor reviewed attendance
    attendance_verified_by = db.Column(db.Integer, db.ForeignKey('users.id'))  # Who verified
    attendance_verified_at = db.Column(db.DateTime)  # When verified
    
    # 🔥 NEW: Enhanced Status Tracking
    completion_method = db.Column(db.String(20))  # 'auto', 'manual', 'admin_override'
    quality_review_status = db.Column(db.String(20))  # 'pending', 'approved', 'rejected'
    quality_reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    quality_reviewed_at = db.Column(db.DateTime)
    quality_feedback = db.Column(db.Text)  # Admin feedback on video quality
    
    # 🔥 NEW: Performance Metrics
    punctuality_score = db.Column(db.Float)  # Calculated punctuality score
    engagement_average = db.Column(db.Float)  # Average student engagement
    completion_compliance = db.Column(db.Boolean, default=True)  # Met all requirements
    
    # Add new relationships
    verified_by_user = db.relationship('User', 
                                     foreign_keys=[attendance_verified_by], 
                                     backref='verified_classes', 
                                     lazy=True)

    quality_reviewer = db.relationship('User', 
                                     foreign_keys=[quality_reviewed_by], 
                                     backref='quality_reviewed_classes', 
                                     lazy=True)
    
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
        elif self.class_type == 'demo': 
            return [self.demo_student_id] if self.demo_student_id else []
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
        elif self.class_type == 'demo' and student_ids:  # ADD THIS
            self.demo_student_id = student_ids[0] 
    
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
        if self.class_type == 'demo':
            # For demo classes, return demo student objects
            from app.models.demo_student import DemoStudent
            if self.demo_student_id:
                demo_student = DemoStudent.query.get(self.demo_student_id)
                return [demo_student] if demo_student else []
            return []
        else:
            # For regular classes, return regular student objects
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
    
    def get_end_time(self):
        """Get the end time of the class"""
        if self.end_time:
            return self.end_time
        elif self.scheduled_time and self.duration:
            start_datetime = datetime.combine(datetime.today(), self.scheduled_time)
            end_datetime = start_datetime + timedelta(minutes=self.duration)
            return end_datetime.time()

        return None
    
    
    def get_scheduled_datetime_str(self):
        """Get formatted scheduled datetime string"""
        if self.scheduled_date and self.scheduled_time:
            dt = datetime.combine(self.scheduled_date, self.scheduled_time)
            return dt.strftime('%Y-%m-%d %H:%M')
        return None

    def get_time_until_class_formatted(self):
        """Get human-readable time until class"""
        delta = self.time_until_class()
        if delta.total_seconds() <= 0:
            return "Class time has passed"
        
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes = remainder // 60
        
        if days > 0:
            return f"{days} day{'s' if days != 1 else ''}, {hours} hour{'s' if hours != 1 else ''}"
        elif hours > 0:
            return f"{hours} hour{'s' if hours != 1 else ''}, {minutes} minute{'s' if minutes != 1 else ''}"
        else:
            return f"{minutes} minute{'s' if minutes != 1 else ''}"

    def can_be_started(self, minutes_before=15):
        """Check if class can be started within X minutes of scheduled time"""
        if self.status != 'scheduled':
            return False
        
        now = datetime.now()
        scheduled_dt = datetime.combine(self.scheduled_date, self.scheduled_time)
        
        # Can start 15 minutes before or anytime after scheduled time
        start_window = scheduled_dt - timedelta(minutes=minutes_before)
        end_window = scheduled_dt + timedelta(minutes=self.duration)
        
        return start_window <= now <= end_window

    def get_conflict_score(self):
        """Calculate conflict score based on overlapping classes"""
        conflicts = Class.query.filter(
            Class.tutor_id == self.tutor_id,
            Class.scheduled_date == self.scheduled_date,
            Class.id != self.id,
            Class.status.in_(['scheduled', 'ongoing'])
        ).all()
        
        conflict_count = 0
        for other_class in conflicts:
            # Check time overlap
            start1 = datetime.combine(self.scheduled_date, self.scheduled_time)
            end1 = start1 + timedelta(minutes=self.duration)
            start2 = datetime.combine(other_class.scheduled_date, other_class.scheduled_time)
            end2 = start2 + timedelta(minutes=other_class.duration)
            
            if start1 < end2 and start2 < end1:
                conflict_count += 1
        
        return conflict_count

    def get_attendance_summary(self):
        """Get attendance summary for this class"""
        from app.models.attendance import Attendance
        
        attendance_records = Attendance.query.filter_by(class_id=self.id).all()
        
        summary = {
            'total_students': len(attendance_records),
            'present': len([a for a in attendance_records if a.status == 'present']),
            'absent': len([a for a in attendance_records if a.status == 'absent']),
            'late': len([a for a in attendance_records if a.status == 'late']),
            'attendance_rate': 0
        }
        
        if summary['total_students'] > 0:
            summary['attendance_rate'] = round((summary['present'] / summary['total_students']) * 100, 1)
        
        return summary

    def get_quality_metrics(self):
        """Get quality metrics for this class"""
        metrics = {
            'completion_rate': 100 if self.status == 'completed' else 0,
            'on_time_start': False,
            'full_duration': False,
            'student_satisfaction': 0,
            'tutor_satisfaction': 0
        }
        
        # Check if started on time (within 5 minutes)
        if self.actual_start_time and self.scheduled_time:
            scheduled_dt = datetime.combine(self.scheduled_date, self.scheduled_time)
            start_diff = abs((self.actual_start_time - scheduled_dt).total_seconds())
            metrics['on_time_start'] = start_diff <= 300  # 5 minutes
        
        # Check if full duration was completed
        if self.actual_start_time and self.actual_end_time:
            actual_duration = (self.actual_end_time - self.actual_start_time).total_seconds() / 60
            expected_duration = self.duration
            metrics['full_duration'] = actual_duration >= (expected_duration * 0.9)  # 90% of expected
        
        # Parse feedback scores (if available)
        if self.student_feedback:
            try:
                import json
                feedback_data = json.loads(self.student_feedback)
                if 'rating' in feedback_data:
                    metrics['student_satisfaction'] = feedback_data['rating']
            except:
                pass
        
        if self.tutor_feedback:
            try:
                import json
                feedback_data = json.loads(self.tutor_feedback)
                if 'rating' in feedback_data:
                    metrics['tutor_satisfaction'] = feedback_data['rating']
            except:
                pass
        
        return metrics

    def generate_meeting_room(self):
        """Generate a meeting room/link if not already set"""
        if self.meeting_link:
            return self.meeting_link
        
        # Generate a simple meeting room identifier
        import uuid
        room_id = str(uuid.uuid4())[:8].upper()
        
        # You can integrate with actual meeting platforms here
        # For now, create a placeholder
        self.meeting_id = room_id
        self.meeting_link = f"https://meet.example.com/room/{room_id}"
        
        return self.meeting_link

    def send_notifications(self, notification_type='reminder'):
        """Send notifications for this class"""
        from app.utils.notification_utils import send_class_notification
        
        recipients = []
        
        # Add tutor
        if self.tutor and self.tutor.user and self.tutor.user.email:
            recipients.append({
                'type': 'tutor',
                'email': self.tutor.user.email,
                'name': self.tutor.user.full_name,
                'phone': self.tutor.user.phone
            })
        
        # Add students
        students = self.get_student_objects()
        for student in students:
            if hasattr(student, 'email') and student.email:
                recipients.append({
                    'type': 'student',
                    'email': student.email,
                    'name': student.full_name if hasattr(student, 'full_name') else student.name,
                    'phone': getattr(student, 'phone', None)
                })
        
        # Send notifications
        for recipient in recipients:
            try:
                send_class_notification(self, recipient, notification_type)
            except Exception as e:
                print(f"Failed to send notification to {recipient['email']}: {str(e)}")

    def get_preparation_checklist(self):
        """Get preparation checklist for this class"""
        checklist = []
        
        # Basic preparations
        checklist.append({
            'item': 'Meeting link ready',
            'completed': bool(self.meeting_link),
            'required': True
        })
        
        checklist.append({
            'item': 'Class materials prepared',
            'completed': bool(self.materials),
            'required': False
        })
        
        checklist.append({
            'item': 'Students notified',
            'completed': self.created_at and (datetime.utcnow() - self.created_at).days >= 1,
            'required': True
        })
        
        # Check if it's within 1 hour of class time
        if self.is_upcoming() and self.time_until_class().total_seconds() <= 3600:
            checklist.append({
                'item': 'Final reminder sent',
                'completed': False,  # Would check notification log
                'required': True
            })
        
        return checklist

    def get_similar_classes(self, limit=5):
        """Get similar classes (same subject, tutor, or students)"""
        similar_classes = Class.query.filter(
            Class.id != self.id,
            or_(
                Class.subject == self.subject,
                Class.tutor_id == self.tutor_id,
                # Could add student overlap check here
            )
        ).order_by(Class.scheduled_date.desc()).limit(limit).all()
        
        return similar_classes

    def export_to_ical_event(self):
        """Export this class as an iCal event"""
        if not self.scheduled_date or not self.scheduled_time:
            return None
        
        start_dt = datetime.combine(self.scheduled_date, self.scheduled_time)
        end_dt = start_dt + timedelta(minutes=self.duration)
        
        # Basic iCal event format
        event = f"""BEGIN:VEVENT
    UID:class-{self.id}-{int(start_dt.timestamp())}
    DTSTART:{start_dt.strftime('%Y%m%dT%H%M%S')}
    DTEND:{end_dt.strftime('%Y%m%dT%H%M%S')}
    SUMMARY:{self.subject}
    DESCRIPTION:Tutor: {self.tutor.user.full_name if self.tutor and self.tutor.user else 'TBA'}\\nStatus: {self.status}\\nDuration: {self.duration} minutes
    STATUS:{self.status.upper()}
    CATEGORIES:Education,Class
    PRIORITY:5"""

        if self.meeting_link:
            event += f"\nLOCATION:{self.meeting_link}"
        
        if self.class_notes:
            event += f"\nCOMMENT:{self.class_notes}"
        
        event += "\nEND:VEVENT"
        
        return event

    @classmethod
    def get_dashboard_stats(cls, user=None, date_range=None):
        """Get dashboard statistics for classes"""
        from sqlalchemy import func
        
        # Base query
        query = cls.query
        
        # Filter by user role and permissions
        if user:
            if user.role == 'coordinator':
                query = query.join(Tutor).join(User).filter(User.department_id == user.department_id)
            elif user.role == 'tutor':
                tutor = Tutor.query.filter_by(user_id=user.id).first()
                if tutor:
                    query = query.filter(cls.tutor_id == tutor.id)
        
        # Date range filter
        if date_range:
            if 'start' in date_range:
                query = query.filter(cls.scheduled_date >= date_range['start'])
            if 'end' in date_range:
                query = query.filter(cls.scheduled_date <= date_range['end'])
        
        # Get counts by status
        stats = {}
        
        # Overall stats
        stats['total_classes'] = query.count()
        stats['scheduled'] = query.filter(cls.status == 'scheduled').count()
        stats['completed'] = query.filter(cls.status == 'completed').count()
        stats['cancelled'] = query.filter(cls.status == 'cancelled').count()
        stats['ongoing'] = query.filter(cls.status == 'ongoing').count()
        
        # Today's stats
        today = datetime.now().date()
        today_query = query.filter(cls.scheduled_date == today)
        stats['today'] = {
            'total': today_query.count(),
            'scheduled': today_query.filter(cls.status == 'scheduled').count(),
            'completed': today_query.filter(cls.status == 'completed').count(),
            'ongoing': today_query.filter(cls.status == 'ongoing').count(),
            'cancelled': today_query.filter(cls.status == 'cancelled').count()
        }
        
        # This week's stats
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        week_query = query.filter(
            cls.scheduled_date >= week_start,
            cls.scheduled_date <= week_end
        )
        stats['this_week'] = {
            'total': week_query.count(),
            'completed': week_query.filter(cls.status == 'completed').count(),
            'scheduled': week_query.filter(cls.status == 'scheduled').count()
        }
        
        # Calculate completion rate
        if stats['total_classes'] > 0:
            stats['completion_rate'] = round((stats['completed'] / stats['total_classes']) * 100, 1)
        else:
            stats['completion_rate'] = 0
        
        # Upcoming classes (next 7 days)
        upcoming_query = query.filter(
            cls.scheduled_date > today,
            cls.scheduled_date <= today + timedelta(days=7),
            cls.status == 'scheduled'
        )
        stats['upcoming_count'] = upcoming_query.count()
        
        return stats

    @classmethod
    def get_popular_time_slots(cls, days=30):
        """Get most popular time slots for scheduling"""
        from sqlalchemy import func
        
        # Get classes from last X days
        start_date = datetime.now().date() - timedelta(days=days)
        
        time_slots = db.session.query(
            cls.scheduled_time,
            func.count(cls.id).label('count')
        ).filter(
            cls.scheduled_date >= start_date,
            cls.status.in_(['scheduled', 'completed'])
        ).group_by(cls.scheduled_time).order_by(func.count(cls.id).desc()).limit(10).all()
        
        return [{'time': slot[0].strftime('%H:%M'), 'count': slot[1]} for slot in time_slots]

    @classmethod
    def get_busiest_days(cls, weeks=4):
        """Get busiest days of the week"""
        from sqlalchemy import func, extract
        
        # Get classes from last X weeks
        start_date = datetime.now().date() - timedelta(weeks=weeks)
        
        # PostgreSQL: EXTRACT(DOW FROM scheduled_date)
        # SQLite: strftime('%w', scheduled_date)
        # MySQL: DAYOFWEEK(scheduled_date)
        
        # Use a database-agnostic approach
        classes = cls.query.filter(
            cls.scheduled_date >= start_date,
            cls.status.in_(['scheduled', 'completed'])
        ).all()
        
        day_counts = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}  # Mon-Sun
        
        for class_item in classes:
            day_of_week = class_item.scheduled_date.weekday()  # 0=Monday
            day_counts[day_of_week] += 1
        
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        
        return [{'day': day_names[i], 'count': day_counts[i]} for i in range(7)]

    def to_dict_detailed(self):
        """Convert to detailed dictionary with all relationships"""
        base_dict = self.to_dict()
        
        # Add detailed information
        base_dict.update({
            'tutor_details': {
                'id': self.tutor.id if self.tutor else None,
                'name': self.tutor.user.full_name if self.tutor and self.tutor.user else None,
                'email': self.tutor.user.email if self.tutor and self.tutor.user else None,
                'phone': self.tutor.user.phone if self.tutor and self.tutor.user else None,
                'subjects': self.tutor.get_subjects_taught() if self.tutor else [],
                'experience': self.tutor.experience_years if self.tutor else 0
            },
            'student_details': [
                {
                    'id': student.id,
                    'name': getattr(student, 'full_name', 'Unknown'),
                    'grade': getattr(student, 'grade', ''),
                    'email': getattr(student, 'email', ''),
                    'type': 'demo' if hasattr(student, 'demo_status') else 'regular'
                }
                for student in self.get_student_objects()
            ],
            'attendance_summary': self.get_attendance_summary(),
            'quality_metrics': self.get_quality_metrics(),
            'time_until_class': self.get_time_until_class_formatted() if self.is_upcoming() else None,
            'can_be_started': self.can_be_started(),
            'conflict_score': self.get_conflict_score(),
            'preparation_checklist': self.get_preparation_checklist()
        })
        
        return base_dict

    # ============ CLASS INSTANCE METHODS ============

    def __str__(self):
        """String representation of the class"""
        return f"{self.subject} - {self.scheduled_date} {self.scheduled_time} ({self.status})"

    def __eq__(self, other):
        """Check equality based on ID"""
        if not isinstance(other, Class):
            return False
        return self.id == other.id

    def __hash__(self):
        """Hash method for set operations"""
        return hash(self.id) if self.id else hash(id(self))

    # ============ VALIDATION METHODS ============

    def validate_scheduling(self):
        """Validate class scheduling constraints"""
        errors = []
        
        # Check if date is in the past
        if self.scheduled_date < datetime.now().date():
            errors.append("Cannot schedule classes in the past")
        
        # Check if time is reasonable (not too early or late)
        if self.scheduled_time:
            hour = self.scheduled_time.hour
            if hour < 6 or hour > 23:
                errors.append("Class time should be between 6:00 AM and 11:00 PM")
        
        # Check duration is reasonable
        if self.duration < 15:
            errors.append("Class duration must be at least 15 minutes")
        elif self.duration > 480:  # 8 hours
            errors.append("Class duration cannot exceed 8 hours")
        
        # Check tutor availability
        if self.tutor_id:
            conflict_exists, conflicting_class = self.check_time_conflict(
                self.tutor_id, self.scheduled_date, self.scheduled_time, self.duration, self.id
            )
            if conflict_exists:
                errors.append(f"Tutor has a conflicting class: {conflicting_class.subject}")
        
        return errors

    def is_editable(self):
        """Check if class can be edited"""
        # Can't edit if class is in progress or completed
        if self.status in ['ongoing', 'completed']:
            return False
        
        # Can't edit if class is in the past
        if self.is_past():
            return False
        
        # Can't edit if class starts in less than 1 hour (emergency changes only)
        if self.is_upcoming() and self.time_until_class().total_seconds() < 3600:
            return False
        
        return True

    def is_deletable(self):
        """Check if class can be deleted"""
        # Can't delete completed classes (for record keeping)
        if self.status == 'completed':
            return False
        
        # Can't delete if class has started
        if self.actual_start_time:
            return False
        
        return True
    
    def start_class_with_auto_attendance(self):
        """Enhanced start class method with auto-attendance"""
        from datetime import datetime, timedelta
        
        current_time = datetime.now()
        
        # Update class status
        self.status = 'ongoing'
        self.actual_start_time = current_time
        self.auto_attendance_marked = True
        
        # Set video upload deadline (24 hours from now)
        self.video_upload_deadline = current_time + timedelta(hours=24)
        
        return True

    def complete_class_with_review(self):
        """Enhanced complete class method"""
        from datetime import datetime
        
        current_time = datetime.now()
        
        # Update class status
        self.status = 'completed'
        self.actual_end_time = current_time
        self.completion_method = 'manual'  # Tutor completed manually
        
        # Update video deadline if not set
        if not self.video_upload_deadline:
            self.video_upload_deadline = current_time + timedelta(hours=24)
        
        return True

    def calculate_performance_metrics(self):
        """Calculate performance metrics for this class"""
        from app.models.attendance import Attendance
        
        # Get attendance records
        attendance_records = Attendance.query.filter_by(class_id=self.id).all()
        
        if not attendance_records:
            return
        
        # Calculate punctuality score (based on tutor attendance)
        tutor_attendance = next((a for a in attendance_records if a.tutor_id), None)
        if tutor_attendance:
            if tutor_attendance.tutor_late_minutes == 0:
                self.punctuality_score = 5.0
            elif tutor_attendance.tutor_late_minutes <= 2:
                self.punctuality_score = 4.0
            elif tutor_attendance.tutor_late_minutes <= 5:
                self.punctuality_score = 3.0
            elif tutor_attendance.tutor_late_minutes <= 10:
                self.punctuality_score = 2.0
            else:
                self.punctuality_score = 1.0
        
        # Calculate average engagement
        engagement_scores = []
        for attendance in attendance_records:
            if attendance.student_engagement:
                if attendance.student_engagement == 'high':
                    engagement_scores.append(5)
                elif attendance.student_engagement == 'medium':
                    engagement_scores.append(3)
                elif attendance.student_engagement == 'low':
                    engagement_scores.append(1)
        
        if engagement_scores:
            self.engagement_average = sum(engagement_scores) / len(engagement_scores)
        
        # Check completion compliance
        self.completion_compliance = bool(
            self.video_link and  # Video uploaded
            self.attendance_review_completed and  # Attendance reviewed
            self.status == 'completed'  # Class completed
        )

    def is_video_upload_overdue(self):
        """Check if video upload is overdue"""
        if not self.video_upload_deadline:
            return False
        
        from datetime import datetime
        return datetime.now() > self.video_upload_deadline

    def get_video_upload_time_remaining(self):
        """Get time remaining for video upload in minutes"""
        if not self.video_upload_deadline:
            return None
        
        from datetime import datetime
        remaining = self.video_upload_deadline - datetime.now()
        return max(0, int(remaining.total_seconds() / 60))

    def mark_video_uploaded(self, uploaded_by_user_id):
        """Mark video as uploaded and update related fields"""
        from datetime import datetime
        
        self.video_uploaded_at = datetime.now()
        self.quality_review_status = 'pending'
        
        # Cancel reminder flags since video is uploaded
        self.video_reminder_sent = False
        self.video_final_warning_sent = False
        
        # Update compliance
        self.calculate_performance_metrics()
        
        return True
    
    
