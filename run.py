from app import create_app, db
from app.models import User, Department, Tutor, Student, Class, Attendance
from config import Config

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


def create_default_data():
    """Create default admin user and departments on first run"""
    with app.app_context():
        # Create all database tables
        db.create_all()
        
        # Create default departments
        Department.create_default_departments()
        
        # Create default admin user
        User.create_default_admin()
        
        print("Default data created successfully!")

if __name__ == '__main__':
    # Create default data on first run
    create_default_data()
    app.run(debug=True, host='0.0.0.0', port=5000)