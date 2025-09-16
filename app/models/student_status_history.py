from datetime import datetime
from app import db

class StudentStatusHistory(db.Model):
    __tablename__ = 'student_status_history'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False, index=True)
    
    # Status Change Information
    old_status = db.Column(db.String(20), index=True)  # Previous enrollment_status
    new_status = db.Column(db.String(20), nullable=False, index=True)  # New enrollment_status
    old_is_active = db.Column(db.Boolean)  # Previous is_active value
    new_is_active = db.Column(db.Boolean, nullable=False)  # New is_active value
    
    # Change Details
    change_reason = db.Column(db.Text, nullable=False)  # Reason for the change
    changed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # Who made the change
    change_method = db.Column(db.String(50))  # How the change was made (manual, bulk, automatic)
    
    # Additional Context
    effective_date = db.Column(db.Date)  # When the change takes effect
    notes = db.Column(db.Text)  # Additional notes about the change
    
    # Related Records
    graduation_id = db.Column(db.Integer, db.ForeignKey('student_graduations.id'))
    drop_id = db.Column(db.Integer, db.ForeignKey('student_drops.id'))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    student = db.relationship('Student', backref='status_history')
    changed_by_user = db.relationship('User', backref='status_changes_made')
    graduation = db.relationship('StudentGraduation', backref='status_history_record')
    drop = db.relationship('StudentDrop', backref='status_history_record')
    
    def get_change_type(self):
        """Determine the type of change"""
        if self.old_status != self.new_status:
            if self.new_status == 'completed':
                return 'graduation'
            elif self.new_status == 'dropped':
                return 'drop'
            elif self.new_status == 'paused':
                return 'pause'
            elif self.new_status == 'active' and self.old_status in ['paused', 'dropped']:
                return 'reactivation'
            else:
                return 'status_change'
        elif self.old_is_active != self.new_is_active:
            return 'activation_toggle'
        else:
            return 'update'
    
    def get_change_description(self):
        """Get human-readable description of the change"""
        change_type = self.get_change_type()
        
        descriptions = {
            'graduation': f"Student graduated (changed from {self.old_status} to {self.new_status})",
            'drop': f"Student dropped (changed from {self.old_status} to {self.new_status})",
            'pause': f"Student paused (changed from {self.old_status} to {self.new_status})",
            'reactivation': f"Student reactivated (changed from {self.old_status} to {self.new_status})",
            'status_change': f"Status changed from {self.old_status} to {self.new_status}",
            'activation_toggle': f"Active status changed from {self.old_is_active} to {self.new_is_active}",
            'update': "Student record updated"
        }
        
        return descriptions.get(change_type, "Status updated")
    
    def get_status_display(self, status):
        """Get display-friendly status name"""
        status_names = {
            'active': 'Active',
            'paused': 'Paused',
            'completed': 'Graduated/Completed',
            'dropped': 'Dropped',
            None: 'Not Set'
        }
        return status_names.get(status, status)
    
    def to_dict(self):
        """Convert to dictionary for JSON response"""
        return {
            'id': self.id,
            'student_id': self.student_id,
            'old_status': self.old_status,
            'new_status': self.new_status,
            'old_status_display': self.get_status_display(self.old_status),
            'new_status_display': self.get_status_display(self.new_status),
            'change_type': self.get_change_type(),
            'change_description': self.get_change_description(),
            'change_reason': self.change_reason,
            'changed_by_name': self.changed_by_user.full_name if self.changed_by_user else '',
            'change_method': self.change_method,
            'effective_date': self.effective_date.isoformat() if self.effective_date else None,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @staticmethod
    def log_status_change(student_id, old_status, new_status, old_is_active, new_is_active, 
                         reason, changed_by_user_id, change_method='manual', 
                         effective_date=None, notes=None, graduation_id=None, drop_id=None):
        """Create a status change log entry"""
        history_entry = StudentStatusHistory(
            student_id=student_id,
            old_status=old_status,
            new_status=new_status,
            old_is_active=old_is_active,
            new_is_active=new_is_active,
            change_reason=reason,
            changed_by=changed_by_user_id,
            change_method=change_method,
            effective_date=effective_date or datetime.now().date(),
            notes=notes,
            graduation_id=graduation_id,
            drop_id=drop_id
        )
        
        db.session.add(history_entry)
        db.session.commit()
        return history_entry
    
    @staticmethod
    def get_student_history(student_id, limit=None):
        """Get status change history for a student"""
        query = StudentStatusHistory.query.filter_by(student_id=student_id)\
                                         .order_by(StudentStatusHistory.created_at.desc())
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    @staticmethod
    def get_recent_changes(limit=50):
        """Get recent status changes across all students"""
        return StudentStatusHistory.query\
                                 .order_by(StudentStatusHistory.created_at.desc())\
                                 .limit(limit).all()
    
    @staticmethod
    def get_changes_by_user(user_id, limit=None):
        """Get status changes made by a specific user"""
        query = StudentStatusHistory.query.filter_by(changed_by=user_id)\
                                         .order_by(StudentStatusHistory.created_at.desc())
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    def __repr__(self):
        return f'<StudentStatusHistory {self.student.full_name if self.student else "Unknown"} - {self.old_status} -> {self.new_status}>'