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
    with app.app_context():
        try:
            # Check if system needs setup
            if not User.query.filter_by(role='superadmin').first():
                return redirect(url_for('setup.initial_setup'))
            else:
                return redirect(url_for('auth.login'))
        except Exception as e:
            # Database tables don't exist, redirect to setup
            print(f"Database not ready: {str(e)}")
            return redirect(url_for('setup.initial_setup'))

def initialize_database():
    """Initialize database tables if needed"""
    with app.app_context():
        try:
            # Test if tables exist by making a simple query
            User.query.first()
            print("✅ Database tables already exist")
        except Exception as e:
            print(f"⚠️  Creating database tables: {str(e)}")
            try:
                db.create_all()
                print("✅ Database tables created successfully")
            except Exception as create_error:
                print(f"❌ Error creating tables: {str(create_error)}")

if __name__ == '__main__':
    print("🚀 Starting I2Global LMS...")
    print("📊 Checking database...")
    
    # Initialize database tables if needed
    initialize_database()
    
    print("🌐 Server starting on http://0.0.0.0:5001")
    app.run(debug=True, host='0.0.0.0', port=5001)