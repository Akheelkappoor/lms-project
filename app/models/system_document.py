from app import db
from datetime import datetime

class SystemDocument(db.Model):
    """System-wide documents model"""
    __tablename__ = 'system_documents'
    
    id = db.Column(db.Integer, primary_key=True)
    document_type = db.Column(db.String(100), nullable=False, unique=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer)
    mime_type = db.Column(db.String(100))
    
    # Availability settings
    is_active = db.Column(db.Boolean, default=True)
    available_for_roles = db.Column(db.Text)  # JSON string of roles
    
    # Metadata
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Version tracking
    version = db.Column(db.String(10), default='1.0')
    
    def __repr__(self):
        return f'<SystemDocument {self.document_type}: {self.title}>'
    
    def get_available_roles(self):
        """Get list of roles that can access this document"""
        if self.available_for_roles:
            import json
            return json.loads(self.available_for_roles)
        return []
    
    def set_available_roles(self, roles):
        """Set roles that can access this document"""
        import json
        self.available_for_roles = json.dumps(roles)
    
    def is_available_for_user(self, user):
        """Check if document is available for specific user"""
        if not self.is_active:
            return False
        
        available_roles = self.get_available_roles()
        if not available_roles:  # Available for all roles
            return True
        
        return user.role in available_roles
    
    @staticmethod
    def get_document_types():
        """Get predefined document types"""
        return {
            'offer_letter': 'Offer Letter',
            'employee_handbook': 'Employee Handbook',
            'hr_policies': 'HR Policies',
            'safety_guidelines': 'Safety Guidelines',
            'company_policies': 'Company Policies',
            'form_16': 'Form 16 (TDS Certificate)',
            'salary_certificate': 'Salary Certificate',
            'experience_letter': 'Experience Letter',
            'training_certificate': 'Training Certificate',
            'code_of_conduct': 'Code of Conduct',
            'leave_policy': 'Leave Policy',
            'grievance_policy': 'Grievance Policy'
        }