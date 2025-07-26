from datetime import datetime, date
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
    
    # Penalties and Adjustments
    tutor_penalty_applied = db.Column(db.Boolean, default=False)
    penalty_amount = db.Column(db.Float, default=0.0)
    penalty_reason = db.Column(db.String(200))
    
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

    
    def mark_tutor_attendance(self, present, join_time=None, leave_time=None, absence_reason=None):
        """Mark tutor attendance"""
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
    
    def mark_student_attendance(self, present, join_time=None, leave_time=None, absence_reason=None, engagement=None):
        """Mark student attendance"""
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
        """Calculate penalty for tutor based on attendance issues"""
        if not penalty_settings:
            penalty_settings = {
                'late_penalty_per_minute': 10,  # ₹10 per minute late
                'absence_penalty': 500,  # ₹500 for unexcused absence
                'early_leave_penalty_per_minute': 5  # ₹5 per minute early leave
            }
        
        total_penalty = 0
        penalty_reasons = []
        
        if not self.tutor_present:
            total_penalty += penalty_settings.get('absence_penalty', 0)
            penalty_reasons.append('Absent from class')
        else:
            if self.tutor_late_minutes > 0:
                late_penalty = self.tutor_late_minutes * penalty_settings.get('late_penalty_per_minute', 0)
                total_penalty += late_penalty
                penalty_reasons.append(f'Late by {self.tutor_late_minutes} minutes')
            
            if self.tutor_early_leave_minutes > 0:
                early_leave_penalty = self.tutor_early_leave_minutes * penalty_settings.get('early_leave_penalty_per_minute', 0)
                total_penalty += early_leave_penalty
                penalty_reasons.append(f'Left {self.tutor_early_leave_minutes} minutes early')
        
        if total_penalty > 0:
            self.penalty_amount = total_penalty
            self.penalty_reason = '; '.join(penalty_reasons)
            self.tutor_penalty_applied = True
        
        return total_penalty
    
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
    
    @staticmethod
    def get_attendance_summary(tutor_id=None, student_id=None, start_date=None, end_date=None):
        """Get attendance summary for tutor or student"""
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
            'average_punctuality_score': 0
        }
        
        if records:
            punctuality_scores = []
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
                
                elif student_id:
                    if record.student_present:
                        summary['present_count'] += 1
                    else:
                        summary['absent_count'] += 1
                    
                    if record.student_late_minutes > 0:
                        summary['late_count'] += 1
                        summary['total_late_minutes'] += record.student_late_minutes
                
                punctuality_scores.append(record.get_punctuality_score())
            
            summary['attendance_percentage'] = (summary['present_count'] / summary['total_classes']) * 100
            summary['average_punctuality_score'] = sum(punctuality_scores) / len(punctuality_scores)
        
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
                scheduled_end=class_obj.end_time
            )
            records.append(attendance)
            db.session.add(attendance)
        
        return records
    
    def to_dict(self):
        """Convert attendance to dictionary"""
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
            'student_engagement': self.student_engagement,
            'marked_at': self.marked_at.isoformat() if self.marked_at else None
        }
    
    def __repr__(self):
        return f'<Attendance Class:{self.class_id} Tutor:{self.tutor_id} Student:{self.student_id}>'