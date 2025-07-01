from app import create_app, db
from app.models import User, Department, Tutor, Student, Class, Attendance
from flask import url_for, redirect

# Create Flask application instance
app = create_app()

@app.shell_context_processor
def make_shell_context():
    return {
        'db': db, 
        'User': User, 
        'Department': Department, 
        'Tutor': Tutor, 
        'Student': Student, 
        'Class': Class, 
        'Attendance': Attendance
    }

@app.route('/')
def index():
    """Main index route - redirect based on setup status"""
    try:
        # Check if system needs setup
        if not User.query.filter_by(role='superadmin').first():
            return redirect(url_for('setup.initial_setup'))
        else:
            return redirect(url_for('auth.login'))
    except Exception:
        # Database tables don't exist, redirect to setup
        return redirect(url_for('setup.initial_setup'))

# Initialize database on import (for production)
with app.app_context():
    try:
        # Test if tables exist
        User.query.first()
    except Exception:
        # Create all tables
        db.create_all()

if __name__ == '__main__':
    print("🚀 Starting I2Global LMS...")
    app.run(debug=True, host='0.0.0.0', port=5001)