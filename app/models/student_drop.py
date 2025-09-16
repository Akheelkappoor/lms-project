from datetime import datetime
from app import db
import json

class StudentDrop(db.Model):
    __tablename__ = 'student_drops'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    drop_date = db.Column(db.Date, nullable=False, index=True)
    
    # Drop Reasons and Details
    drop_reason = db.Column(db.String(50), nullable=False, index=True)  # Primary category
    detailed_reason = db.Column(db.Text, nullable=False)  # Detailed explanation
    
    # Financial Information
    refund_amount = db.Column(db.Numeric(10,2), default=0)
    refund_reason = db.Column(db.Text)  # Justification for refund
    refund_processed = db.Column(db.Boolean, default=False)
    refund_processed_date = db.Column(db.Date)
    refund_processed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Exit Process
    exit_interview_conducted = db.Column(db.Boolean, default=False)
    exit_interview_notes = db.Column(db.Text)
    exit_interview_date = db.Column(db.Date)
    exit_interview_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Future Enrollment
    re_enrollment_allowed = db.Column(db.Boolean, default=True)
    blacklisted = db.Column(db.Boolean, default=False, index=True)
    blacklist_reason = db.Column(db.Text)
    
    # Process Information
    dropped_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    internal_notes = db.Column(db.Text)  # Admin-only notes
    
    # Notification Status
    student_notified = db.Column(db.Boolean, default=False)
    parents_notified = db.Column(db.Boolean, default=False)
    tutor_notified = db.Column(db.Boolean, default=False)
    
    # Class Management
    future_classes_cancelled = db.Column(db.Boolean, default=False)
    cancelled_classes_count = db.Column(db.Integer, default=0)
    
    # Performance at Drop Time
    attendance_at_drop = db.Column(db.Numeric(5,2))  # Attendance % when dropped
    classes_attended = db.Column(db.Integer, default=0)
    classes_scheduled = db.Column(db.Integer, default=0)
    course_completion_percentage = db.Column(db.Numeric(5,2))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships  
    student = db.relationship('Student', backref=db.backref('drop_record', uselist=False))
    dropped_by_user = db.relationship('User', foreign_keys=[dropped_by], 
                                     backref='students_dropped')
    refund_processor = db.relationship('User', foreign_keys=[refund_processed_by])
    exit_interviewer = db.relationship('User', foreign_keys=[exit_interview_by])
    
    def get_drop_reason_display(self):
        """Get human-readable drop reason"""
        reasons = {
            'voluntary': 'Voluntary (Student/Parent Choice)',
            'academic': 'Academic Performance Issues',
            'financial': 'Financial Difficulties',
            'behavioral': 'Behavioral Issues',
            'attendance': 'Poor Attendance',
            'medical': 'Medical/Health Reasons',
            'relocation': 'Student/Family Relocated',
            'dissatisfaction': 'Dissatisfaction with Service',
            'schedule_conflict': 'Schedule/Time Conflicts',
            'other': 'Other Reasons'
        }
        return reasons.get(self.drop_reason, self.drop_reason)
    
    def process_refund(self, processed_by_user_id, processed_date=None):
        """Mark refund as processed"""
        self.refund_processed = True
        self.refund_processed_date = processed_date or datetime.now().date()
        self.refund_processed_by = processed_by_user_id
        db.session.commit()
    
    def conduct_exit_interview(self, interviewer_id, notes, interview_date=None):
        """Record exit interview details"""
        self.exit_interview_conducted = True
        self.exit_interview_notes = notes
        self.exit_interview_date = interview_date or datetime.now().date()
        self.exit_interview_by = interviewer_id
        db.session.commit()
    
    def blacklist_student(self, reason, blacklisted_by_user_id):
        """Add student to blacklist"""
        self.blacklisted = True
        self.blacklist_reason = reason
        self.re_enrollment_allowed = False
        # Log this action
        db.session.commit()
    
    def get_financial_summary(self):
        """Get financial summary"""
        return {
            'refund_amount': float(self.refund_amount) if self.refund_amount else 0,
            'refund_processed': self.refund_processed,
            'refund_pending': bool(self.refund_amount and not self.refund_processed),
            'refund_date': self.refund_processed_date.isoformat() if self.refund_processed_date else None
        }
    
    def get_performance_at_drop(self):
        """Get student performance metrics at time of drop"""
        return {
            'attendance_rate': float(self.attendance_at_drop) if self.attendance_at_drop else 0,
            'classes_attended': self.classes_attended or 0,
            'classes_scheduled': self.classes_scheduled or 0,
            'course_completion': float(self.course_completion_percentage) if self.course_completion_percentage else 0
        }
    
    def to_dict(self):
        """Convert to dictionary for JSON response"""
        return {
            'id': self.id,
            'student_id': self.student_id,
            'student_name': self.student.full_name if self.student else '',
            'drop_date': self.drop_date.isoformat() if self.drop_date else None,
            'drop_reason': self.drop_reason,
            'drop_reason_display': self.get_drop_reason_display(),
            'detailed_reason': self.detailed_reason,
            'refund_amount': float(self.refund_amount) if self.refund_amount else 0,
            'refund_processed': self.refund_processed,
            'exit_interview_conducted': self.exit_interview_conducted,
            're_enrollment_allowed': self.re_enrollment_allowed,
            'blacklisted': self.blacklisted,
            'performance_at_drop': self.get_performance_at_drop(),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @staticmethod
    def get_drop_statistics(year=None, month=None):
        """Get drop statistics"""
        query = StudentDrop.query
        
        if year:
            query = query.filter(db.extract('year', StudentDrop.drop_date) == year)
        if month:
            query = query.filter(db.extract('month', StudentDrop.drop_date) == month)
        
        drops = query.all()
        
        stats = {
            'total_drops': len(drops),
            'reason_distribution': {},
            'refunds_pending': 0,
            'refunds_processed': 0,
            'total_refund_amount': 0,
            'blacklisted_count': 0,
            'exit_interviews_completed': 0,
            'average_attendance_at_drop': 0
        }
        
        # Calculate statistics
        for drop in drops:
            # Reason distribution
            reason = drop.drop_reason
            stats['reason_distribution'][reason] = stats['reason_distribution'].get(reason, 0) + 1
            
            # Financial stats
            if drop.refund_amount and drop.refund_amount > 0:
                if drop.refund_processed:
                    stats['refunds_processed'] += 1
                else:
                    stats['refunds_pending'] += 1
                stats['total_refund_amount'] += float(drop.refund_amount)
            
            # Other counts
            if drop.blacklisted:
                stats['blacklisted_count'] += 1
            if drop.exit_interview_conducted:
                stats['exit_interviews_completed'] += 1
        
        # Calculate average attendance at drop
        if drops:
            total_attendance = sum(float(d.attendance_at_drop or 0) for d in drops)
            stats['average_attendance_at_drop'] = round(total_attendance / len(drops), 2)
        
        return stats
    
    @staticmethod
    def get_common_drop_reasons(limit=5):
        """Get most common drop reasons"""
        from sqlalchemy import func
        
        return db.session.query(
            StudentDrop.drop_reason,
            func.count(StudentDrop.drop_reason).label('count')
        ).group_by(StudentDrop.drop_reason)\
         .order_by(func.count(StudentDrop.drop_reason).desc())\
         .limit(limit).all()
    
    def __repr__(self):
        return f'<StudentDrop {self.student.full_name if self.student else "Unknown"} - {self.drop_date}>'