from datetime import datetime
from app import db
import json
import uuid

class StudentGraduation(db.Model):
    __tablename__ = 'student_graduations'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    graduation_date = db.Column(db.Date, nullable=False, index=True)
    final_grade = db.Column(db.String(5))
    overall_performance_rating = db.Column(db.String(20))  # excellent, good, satisfactory, needs_improvement
    
    # Certificate Information
    certificate_number = db.Column(db.String(50), unique=True)
    certificate_issued = db.Column(db.Boolean, default=False)
    certificate_issued_date = db.Column(db.Date)
    certificate_issued_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Performance Metrics
    completion_percentage = db.Column(db.Numeric(5,2))  # Overall completion rate
    total_classes_attended = db.Column(db.Integer, default=0)
    total_classes_scheduled = db.Column(db.Integer, default=0)
    attendance_percentage = db.Column(db.Numeric(5,2))
    
    # Feedback and Notes
    feedback = db.Column(db.Text)  # Graduation feedback/comments
    achievements = db.Column(db.Text)  # JSON array of achievements
    
    # Process Information
    graduated_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # Who performed graduation
    graduation_notes = db.Column(db.Text)  # Internal graduation process notes
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    student = db.relationship('Student', backref=db.backref('graduation_record', uselist=False))
    graduated_by_user = db.relationship('User', foreign_keys=[graduated_by], 
                                       backref='students_graduated')
    certificate_issuer = db.relationship('User', foreign_keys=[certificate_issued_by])
    
    def __init__(self, **kwargs):
        super(StudentGraduation, self).__init__(**kwargs)
        if not self.certificate_number:
            self.certificate_number = self.generate_certificate_number()
    
    def generate_certificate_number(self):
        """Generate unique certificate number"""
        year = self.graduation_date.year if self.graduation_date else datetime.now().year
        # Format: CERT-YYYY-XXXXXX (e.g., CERT-2024-001234)
        unique_id = str(uuid.uuid4().int)[-6:]  # Last 6 digits of UUID
        return f"CERT-{year}-{unique_id}"
    
    def get_achievements(self):
        """Get achievements as list"""
        if self.achievements:
            try:
                return json.loads(self.achievements)
            except:
                return []
        return []
    
    def set_achievements(self, achievements_list):
        """Set achievements from list"""
        self.achievements = json.dumps(achievements_list) if achievements_list else None
    
    def get_attendance_rate(self):
        """Calculate attendance rate"""
        if self.total_classes_scheduled and self.total_classes_scheduled > 0:
            return round((self.total_classes_attended / self.total_classes_scheduled) * 100, 2)
        return 0.0
    
    def issue_certificate(self, issued_by_user_id):
        """Mark certificate as issued"""
        self.certificate_issued = True
        self.certificate_issued_date = datetime.now().date()
        self.certificate_issued_by = issued_by_user_id
        db.session.commit()
    
    def get_performance_summary(self):
        """Get performance summary for display"""
        return {
            'final_grade': self.final_grade,
            'performance_rating': self.overall_performance_rating,
            'attendance_rate': self.get_attendance_rate(),
            'completion_rate': float(self.completion_percentage) if self.completion_percentage else 0,
            'total_classes': self.total_classes_scheduled,
            'attended_classes': self.total_classes_attended
        }
    
    def to_dict(self):
        """Convert to dictionary for JSON response"""
        return {
            'id': self.id,
            'student_id': self.student_id,
            'student_name': self.student.full_name if self.student else '',
            'graduation_date': self.graduation_date.isoformat() if self.graduation_date else None,
            'final_grade': self.final_grade,
            'performance_rating': self.overall_performance_rating,
            'certificate_number': self.certificate_number,
            'certificate_issued': self.certificate_issued,
            'attendance_percentage': float(self.attendance_percentage) if self.attendance_percentage else 0,
            'feedback': self.feedback,
            'achievements': self.get_achievements(),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @staticmethod
    def get_graduation_statistics(year=None):
        """Get graduation statistics for a specific year"""
        query = StudentGraduation.query
        if year:
            query = query.filter(db.extract('year', StudentGraduation.graduation_date) == year)
        
        graduations = query.all()
        
        stats = {
            'total_graduations': len(graduations),
            'certificates_issued': sum(1 for g in graduations if g.certificate_issued),
            'grade_distribution': {},
            'performance_distribution': {
                'excellent': 0,
                'good': 0, 
                'satisfactory': 0,
                'needs_improvement': 0
            },
            'average_attendance': 0
        }
        
        # Calculate grade distribution
        for graduation in graduations:
            if graduation.final_grade:
                grade = graduation.final_grade
                stats['grade_distribution'][grade] = stats['grade_distribution'].get(grade, 0) + 1
            
            if graduation.overall_performance_rating:
                rating = graduation.overall_performance_rating
                if rating in stats['performance_distribution']:
                    stats['performance_distribution'][rating] += 1
        
        # Calculate average attendance
        if graduations:
            total_attendance = sum(float(g.attendance_percentage or 0) for g in graduations)
            stats['average_attendance'] = round(total_attendance / len(graduations), 2)
        
        return stats
    
    def __repr__(self):
        return f'<StudentGraduation {self.student.full_name if self.student else "Unknown"} - {self.graduation_date}>'