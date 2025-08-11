from datetime import datetime, date, timedelta
from app import db
import json

class Attendance(db.Model):
    __tablename__ = 'attendance'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Class and User References
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=False)
    tutor_id = db.Column(db.Integer, db.ForeignKey('tutors.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    
    # Attendance Status
    tutor_present = db.Column(db.Boolean, default=False)
    student_present = db.Column(db.Boolean, default=False)
    
    # Timing Details
    class_date = db.Column(db.Date, nullable=False)
    scheduled_start = db.Column(db.Time)
    scheduled_end = db.Column(db.Time)
    
    # Actual Timing
    tutor_join_time = db.Column(db.DateTime)
    tutor_leave_time = db.Column(db.DateTime)
    student_join_time = db.Column(db.DateTime)
    student_leave_time = db.Column(db.DateTime)
    
    # Punctuality Tracking
    tutor_late_minutes = db.Column(db.Integer, default=0)
    student_late_minutes = db.Column(db.Integer, default=0)
    tutor_early_leave_minutes = db.Column(db.Integer, default=0)
    student_early_leave_minutes = db.Column(db.Integer, default=0)
    
    # Class Quality and Engagement
    class_duration_actual = db.Column(db.Integer)  # Actual duration in minutes
    student_engagement = db.Column(db.String(20))  # high, medium, low
    participation_quality = db.Column(db.String(20))  # excellent, good, average, poor
    
    # Absence Reasons
    tutor_absence_reason = db.Column(db.String(100))
    student_absence_reason = db.Column(db.String(100))
    
    # Notes and Feedback
    attendance_notes = db.Column(db.Text)
    behavioral_notes = db.Column(db.Text)
    technical_issues = db.Column(db.Text)
    
    # Administrative
    marked_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    marked_at = db.Column(db.DateTime, default=datetime.utcnow)
    verified_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    verified_at = db.Column(db.DateTime)
    
    # Enhanced Penalties and Adjustments
    tutor_penalty_applied = db.Column(db.Boolean, default=False)
    penalty_amount = db.Column(db.Float, default=0.0)
    penalty_reason = db.Column(db.String(500))  # Increased length for detailed reasons
    
    # 🔥 NEW: Auto-attendance tracking
    auto_marked = db.Column(db.Boolean, default=False)  # Was this marked automatically?
    auto_marked_at = db.Column(db.DateTime)  # When was auto-marking done?
    
    # 🔥 NEW: Enhanced penalty breakdown
    late_arrival_penalty = db.Column(db.Float, default=0.0)
    early_completion_penalty = db.Column(db.Float, default=0.0)
    absence_penalty = db.Column(db.Float, default=0.0)
    
    # 🔥 NEW: Class completion tracking
    expected_duration = db.Column(db.Integer)  # Expected class duration
    completion_percentage = db.Column(db.Float, default=0.0)  # What % of class was completed
    
    # Relationships
    class_session = db.relationship('Class', backref='attendance_records', lazy=True)
    tutor = db.relationship('Tutor', backref='attendance_records', lazy=True)
    student = db.relationship('Student', backref='attendance_records', lazy=True)
    marked_by_user = db.relationship('User', foreign_keys=[marked_by], backref='marked_attendance', lazy=True)
    verified_by_user = db.relationship('User', foreign_keys=[verified_by], backref='verified_attendance', lazy=True)
    
    def __init__(self, **kwargs):
        super(Attendance, self).__init__(**kwargs)
        
    @property
    def status(self):
        """Backward compatibility property for templates"""
        if self.student_present and self.tutor_present:
            if self.student_late_minutes > 0 or self.tutor_late_minutes > 0:
                return 'late'
            return 'present'
        return 'absent'
    
    @property 
    def duration_hours(self):
        """Calculate class duration in hours"""
        if self.class_duration_actual:
            return round(self.class_duration_actual / 60, 1)
        elif self.scheduled_start and self.scheduled_end:
            start_datetime = datetime.combine(date.today(), self.scheduled_start)
            end_datetime = datetime.combine(date.today(), self.scheduled_end)
            duration_minutes = (end_datetime - start_datetime).total_seconds() / 60
            return round(duration_minutes / 60, 1)
        return 1.0  # Default 1 hour

    # 🔥 ENHANCED: Auto-mark tutor attendance (called when START button pressed)
    def auto_mark_tutor_attendance(self, join_time=None, scheduled_duration=60):
        """Automatically mark tutor attendance when START button is pressed"""
        current_time = join_time or datetime.now()
        
        # Mark tutor as present
        self.tutor_present = True
        self.tutor_join_time = current_time
        self.auto_marked = True
        self.auto_marked_at = current_time
        self.expected_duration = scheduled_duration
        
        # Calculate if tutor is late
        if self.scheduled_start:
            scheduled_datetime = datetime.combine(self.class_date, self.scheduled_start)
            if current_time > scheduled_datetime:
                late_minutes = int((current_time - scheduled_datetime).total_seconds() / 60)
                # Apply grace period of 2 minutes
                if late_minutes > 2:
                    self.tutor_late_minutes = late_minutes
                    self.late_arrival_penalty = (late_minutes - 2) * 10  # ₹10 per minute after grace
                    self.penalty_amount = (self.penalty_amount or 0) + self.late_arrival_penalty
                    self.penalty_reason = f"Late arrival: {late_minutes} minutes"
                    self.tutor_penalty_applied = True
        
        return {
            'late_minutes': self.tutor_late_minutes,
            'penalty_amount': self.late_arrival_penalty,
            'on_time': self.tutor_late_minutes <= 2
        }
    
    # 🔥 ENHANCED: Auto-calculate completion when COMPLETE button pressed
    def auto_mark_completion(self, completion_time=None, student_attendance_data=None):
        """Automatically mark completion and calculate penalties when COMPLETE button pressed"""
        current_time = completion_time or datetime.now()
        
        # Set tutor leave time
        self.tutor_leave_time = current_time
        
        # Calculate actual duration
        if self.tutor_join_time:
            actual_duration = int((current_time - self.tutor_join_time).total_seconds() / 60)
            self.class_duration_actual = actual_duration
            
            # Calculate completion percentage
            if self.expected_duration and self.expected_duration > 0:
                self.completion_percentage = min((actual_duration / self.expected_duration) * 100, 100)
            
            # Check for early completion (less than 90% of expected duration)
            if self.expected_duration and actual_duration < (self.expected_duration * 0.9):
                early_minutes = self.expected_duration - actual_duration
                self.tutor_early_leave_minutes = early_minutes
                self.early_completion_penalty = early_minutes * 5  # ₹5 per minute early
                self.penalty_amount = (self.penalty_amount or 0) + self.early_completion_penalty
                
                # Update penalty reason
                existing_reason = self.penalty_reason or ""
                early_reason = f"Early completion: {early_minutes} minutes"
                self.penalty_reason = f"{existing_reason}; {early_reason}" if existing_reason else early_reason
                self.tutor_penalty_applied = True
        
        # Mark student attendance if provided
        if student_attendance_data:
            for student_data in student_attendance_data:
                if student_data.get('student_id') == self.student_id:
                    self.mark_student_attendance(
                        present=student_data.get('present', True),
                        join_time=self.tutor_join_time,  # Assume student joined when class started
                        leave_time=current_time,
                        absence_reason=student_data.get('absence_reason', ''),
                        engagement=student_data.get('engagement', 'good')
                    )
                    break
        
        return {
            'actual_duration': self.class_duration_actual,
            'expected_duration': self.expected_duration,
            'completion_percentage': self.completion_percentage,
            'is_early_completion': self.tutor_early_leave_minutes > 0,
            'early_penalty': self.early_completion_penalty,
            'total_penalty': self.penalty_amount
        }
    
    def mark_tutor_attendance(self, present, join_time=None, leave_time=None, absence_reason=None):
        """Mark tutor attendance (enhanced version)"""
        self.tutor_present = present
        
        if present and join_time:
            self.tutor_join_time = join_time
            if leave_time:
                self.tutor_leave_time = leave_time
            
            # Calculate late minutes
            if self.scheduled_start:
                scheduled_datetime = datetime.combine(self.class_date, self.scheduled_start)
                if join_time > scheduled_datetime:
                    self.tutor_late_minutes = int((join_time - scheduled_datetime).total_seconds() / 60)
            
            # Calculate early leave if applicable
            if leave_time and self.scheduled_end:
                scheduled_end_datetime = datetime.combine(self.class_date, self.scheduled_end)
                if leave_time < scheduled_end_datetime:
                    self.tutor_early_leave_minutes = int((scheduled_end_datetime - leave_time).total_seconds() / 60)
        
        elif not present and absence_reason:
            self.tutor_absence_reason = absence_reason
            # Apply absence penalty
            self.absence_penalty = 500  # ₹500 for unexcused absence
            self.penalty_amount = (self.penalty_amount or 0) + self.absence_penalty
            self.penalty_reason = "Absent from class"
            self.tutor_penalty_applied = True
    
    def mark_student_attendance(self, present, join_time=None, leave_time=None, absence_reason=None, engagement=None):
        """Mark student attendance (enhanced version)"""
        self.student_present = present
        
        if present and join_time:
            self.student_join_time = join_time
            if leave_time:
                self.student_leave_time = leave_time
            
            # Calculate late minutes
            if self.scheduled_start:
                scheduled_datetime = datetime.combine(self.class_date, self.scheduled_start)
                if join_time > scheduled_datetime:
                    self.student_late_minutes = int((join_time - scheduled_datetime).total_seconds() / 60)
            
            # Calculate early leave if applicable
            if leave_time and self.scheduled_end:
                scheduled_end_datetime = datetime.combine(self.class_date, self.scheduled_end)
                if leave_time < scheduled_end_datetime:
                    self.student_early_leave_minutes = int((scheduled_end_datetime - leave_time).total_seconds() / 60)
            
            # Set engagement level
            if engagement:
                self.student_engagement = engagement
        
        elif not present and absence_reason:
            self.student_absence_reason = absence_reason
    
    def calculate_actual_duration(self):
        """Calculate and set actual class duration"""
        if self.tutor_join_time and self.tutor_leave_time:
            duration = (self.tutor_leave_time - self.tutor_join_time).total_seconds() / 60
            self.class_duration_actual = int(duration)
        elif self.scheduled_start and self.scheduled_end:
            start_dt = datetime.combine(self.class_date, self.scheduled_start)
            end_dt = datetime.combine(self.class_date, self.scheduled_end)
            duration = (end_dt - start_dt).total_seconds() / 60
            self.class_duration_actual = int(duration)
    
    def calculate_tutor_penalty(self, penalty_settings=None):
        """Enhanced penalty calculation for tutor based on attendance issues"""
        if not penalty_settings:
            penalty_settings = {
                'late_penalty_per_minute': 10,  # ₹10 per minute late (after 2 min grace)
                'absence_penalty': 500,  # ₹500 for unexcused absence
                'early_leave_penalty_per_minute': 5  # ₹5 per minute early leave
            }
        
        # Reset penalty components
        self.late_arrival_penalty = 0
        self.early_completion_penalty = 0
        self.absence_penalty = 0
        penalty_reasons = []
        
        if not self.tutor_present:
            self.absence_penalty = penalty_settings.get('absence_penalty', 0)
            penalty_reasons.append('Absent from class')
        else:
            # Late arrival penalty (with 2-minute grace period)
            if self.tutor_late_minutes > 2:
                self.late_arrival_penalty = (self.tutor_late_minutes - 2) * penalty_settings.get('late_penalty_per_minute', 0)
                penalty_reasons.append(f'Late by {self.tutor_late_minutes} minutes')
            
            # Early completion penalty
            if self.tutor_early_leave_minutes > 0:
                self.early_completion_penalty = self.tutor_early_leave_minutes * penalty_settings.get('early_leave_penalty_per_minute', 0)
                penalty_reasons.append(f'Left {self.tutor_early_leave_minutes} minutes early')
        
        # Calculate total penalty
        total_penalty = self.late_arrival_penalty + self.early_completion_penalty + self.absence_penalty
        
        if total_penalty > 0:
            self.penalty_amount = total_penalty
            self.penalty_reason = '; '.join(penalty_reasons)
            self.tutor_penalty_applied = True
        
        return total_penalty
    
    # 🔥 NEW: Check if class needs video upload reminder
    def needs_video_upload_reminder(self):
        """Check if this class needs video upload reminder"""
        if not self.class_session:
            return False
        
        # Only completed classes need video upload
        if self.class_session.status != 'completed':
            return False
        
        # Check if video is already uploaded
        if self.class_session.video_upload_status == 'uploaded':
            return False
        
        # Check if deadline is approaching (within 30 minutes)
        if hasattr(self.class_session, 'video_upload_deadline') and self.class_session.video_upload_deadline:
            time_remaining = self.class_session.video_upload_deadline - datetime.now()
            return time_remaining.total_seconds() <= 30 * 60  # 30 minutes
        
        return False
    
    # 🔥 NEW: Get penalty breakdown for admin dashboard
    def get_penalty_breakdown(self):
        """Get detailed penalty breakdown"""
        return {
            'late_arrival': self.late_arrival_penalty or 0,
            'early_completion': self.early_completion_penalty or 0,
            'absence': self.absence_penalty or 0,
            'total': self.penalty_amount or 0,
            'reasons': self.penalty_reason.split('; ') if self.penalty_reason else [],
            'applied': self.tutor_penalty_applied
        }
    
    def is_tutor_punctual(self, tolerance_minutes=5):
        """Check if tutor was punctual (within tolerance)"""
        return self.tutor_late_minutes <= tolerance_minutes
    
    def is_student_punctual(self, tolerance_minutes=5):
        """Check if student was punctual (within tolerance)"""
        return self.student_late_minutes <= tolerance_minutes
    
    def get_attendance_status(self):
        """Get overall attendance status"""
        if self.tutor_present and self.student_present:
            return 'both_present'
        elif self.tutor_present and not self.student_present:
            return 'tutor_only'
        elif not self.tutor_present and self.student_present:
            return 'student_only'
        else:
            return 'both_absent'
    
    def get_punctuality_score(self):
        """Calculate punctuality score (0-100)"""
        score = 100
        
        # Deduct for lateness
        if self.tutor_late_minutes > 0:
            score -= min(self.tutor_late_minutes * 2, 50)  # Max 50 point deduction
        
        if self.student_late_minutes > 0:
            score -= min(self.student_late_minutes * 1, 25)  # Max 25 point deduction
        
        # Deduct for early leaving
        if self.tutor_early_leave_minutes > 0:
            score -= min(self.tutor_early_leave_minutes * 3, 60)  # Max 60 point deduction
        
        return max(0, score)
    
    # 🔥 ENHANCED: Get attendance summary with penalty tracking
    @staticmethod
    def get_attendance_summary(tutor_id=None, student_id=None, start_date=None, end_date=None):
        """Enhanced attendance summary with penalty tracking"""
        query = Attendance.query
        
        if tutor_id:
            query = query.filter_by(tutor_id=tutor_id)
        
        if student_id:
            query = query.filter_by(student_id=student_id)
        
        if start_date:
            query = query.filter(Attendance.class_date >= start_date)
        
        if end_date:
            query = query.filter(Attendance.class_date <= end_date)
        
        records = query.all()
        
        summary = {
            'total_classes': len(records),
            'present_count': 0,
            'absent_count': 0,
            'late_count': 0,
            'total_late_minutes': 0,
            'total_penalty': 0,
            'penalty_breakdown': {
                'late_arrival': 0,
                'early_completion': 0,
                'absence': 0
            },
            'average_punctuality_score': 0,
            'auto_marked_count': 0,  # How many were auto-marked
            'completion_rate': 0  # Average completion percentage
        }
        
        if records:
            punctuality_scores = []
            completion_percentages = []
            
            for record in records:
                if tutor_id:
                    if record.tutor_present:
                        summary['present_count'] += 1
                    else:
                        summary['absent_count'] += 1
                    
                    if record.tutor_late_minutes > 0:
                        summary['late_count'] += 1
                        summary['total_late_minutes'] += record.tutor_late_minutes
                    
                    summary['total_penalty'] += record.penalty_amount or 0
                    summary['penalty_breakdown']['late_arrival'] += record.late_arrival_penalty or 0
                    summary['penalty_breakdown']['early_completion'] += record.early_completion_penalty or 0
                    summary['penalty_breakdown']['absence'] += record.absence_penalty or 0
                
                elif student_id:
                    if record.student_present:
                        summary['present_count'] += 1
                    else:
                        summary['absent_count'] += 1
                    
                    if record.student_late_minutes > 0:
                        summary['late_count'] += 1
                        summary['total_late_minutes'] += record.student_late_minutes
                
                # Count auto-marked records
                if record.auto_marked:
                    summary['auto_marked_count'] += 1
                
                # Track completion rates
                if record.completion_percentage:
                    completion_percentages.append(record.completion_percentage)
                
                punctuality_scores.append(record.get_punctuality_score())
            
            summary['attendance_percentage'] = (summary['present_count'] / summary['total_classes']) * 100
            summary['average_punctuality_score'] = sum(punctuality_scores) / len(punctuality_scores)
            summary['completion_rate'] = sum(completion_percentages) / len(completion_percentages) if completion_percentages else 0
        
        return summary
    
    @staticmethod
    def get_daily_attendance(date_obj):
        """Get all attendance records for a specific date"""
        return Attendance.query.filter_by(class_date=date_obj).all()
    
    @staticmethod
    def create_attendance_record(class_obj):
        """Create attendance records for all students in a class"""
        records = []
        
        for student_id in class_obj.get_students():
            attendance = Attendance(
                class_id=class_obj.id,
                tutor_id=class_obj.tutor_id,
                student_id=student_id,
                class_date=class_obj.scheduled_date,
                scheduled_start=class_obj.scheduled_time,
                scheduled_end=class_obj.end_time,
                expected_duration=class_obj.duration  # Set expected duration
            )
            records.append(attendance)
            db.session.add(attendance)
        
        return records
    
    # 🔥 NEW: Get overdue video uploads for admin alerts
    @staticmethod
    def get_overdue_video_uploads():
        """Get classes with overdue video uploads"""
        from app.models.class_model import Class
        
        overdue_classes = db.session.query(Attendance).join(Class).filter(
            Class.status == 'completed',
            Class.video_upload_status == 'overdue'
        ).all()
        
        return overdue_classes
    
    def to_dict(self):
        """Convert attendance to dictionary with enhanced fields"""
        return {
            'id': self.id,
            'class_id': self.class_id,
            'class_date': self.class_date.isoformat() if self.class_date else None,
            'tutor_name': self.tutor.user.full_name if self.tutor and self.tutor.user else '',
            'student_name': self.student.full_name if self.student else '',
            'tutor_present': self.tutor_present,
            'student_present': self.student_present,
            'tutor_late_minutes': self.tutor_late_minutes,
            'student_late_minutes': self.student_late_minutes,
            'attendance_status': self.get_attendance_status(),
            'punctuality_score': self.get_punctuality_score(),
            'penalty_amount': self.penalty_amount,
            'penalty_breakdown': self.get_penalty_breakdown(),
            'student_engagement': self.student_engagement,
            'marked_at': self.marked_at.isoformat() if self.marked_at else None,
            'auto_marked': self.auto_marked,
            'completion_percentage': self.completion_percentage,
            'actual_duration': self.class_duration_actual,
            'expected_duration': self.expected_duration
        }
    
    def __repr__(self):
        return f'<Attendance Class:{self.class_id} Tutor:{self.tutor_id} Student:{self.student_id}>'