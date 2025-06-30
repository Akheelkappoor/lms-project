from app import create_app, db
from app.models import User, Department, Tutor, Student, Class, Attendance
from config import Config
from flask import url_for, redirect

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
    with app.app_context():
        # Check if system needs setup
        if not User.query.filter_by(role='superadmin').first():
            return redirect(url_for('setup.initial_setup'))
        else:
            return redirect(url_for('auth.login'))

def check_database():
    """Check if database exists and create if not"""
    with app.app_context():
        try:
            # Try to query users table
            User.query.first()
            return True
        except Exception:
            # Database doesn't exist or is corrupted
            print("📋 Database not found. Creating tables...")
            db.create_all()
            return False

def create_default_data():
    """Create default admin user and departments on first run"""
    with app.app_context():
        print("🔄 Checking database status...")
        
        # Create tables if they don't exist
        if not check_database():
            print("✅ Database tables created")
        
        # Check if superadmin exists
        superadmin = User.query.filter_by(role='superadmin').first()
        
        if not superadmin:
            print("⚠️  No superadmin found. Please visit /setup to complete initial setup.")
            return
        
        # Create default departments if they don't exist
        if not Department.query.first():
            Department.create_default_departments()
            print("✅ Default departments created")
        
        print(f"✅ System ready! Superadmin: {superadmin.email}")

if __name__ == '__main__':
    # Check and create default data
    create_default_data()
    
    # Run the application
    print("🚀 Starting I2Global LMS...")
    print("📊 Access the application at: http://localhost:5001")
    print("=" * 50)
    
    app.run(debug=True, host='0.0.0.0', port=5001)