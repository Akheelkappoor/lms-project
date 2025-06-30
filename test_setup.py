# test_setup.py - FIXED VERSION
# Place this in your project root directory

from app import create_app, db
from app.models.user import User
from app.models.department import Department
from app.models.tutor import Tutor
from app.models.student import Student
from app.models.class_model import Class
from datetime import datetime, date, time, timedelta
import json

def test_database_connections():
    """Test all database models"""
    print("Testing database connections...")
    
    try:
        # Test each model
        print(f"Departments: {Department.query.count()}")
        print(f"Users: {User.query.count()}")
        print(f"Tutors: {Tutor.query.count()}")
        print(f"Students: {Student.query.count()}")
        print(f"Classes: {Class.query.count()}")
        print("✅ Database connections working!")
        return True
    except Exception as e:
        print(f"❌ Database error: {str(e)}")
        return False

def create_sample_department():
    """Create a sample department if none exists"""
    if Department.query.count() == 0:
        print("Creating sample department...")
        dept = Department(
            name="Mathematics Department",
            code="MATH",
            description="Mathematics and Science courses",
            is_active=True,
            created_at=datetime.now()  # Fixed: Use datetime.now() instead of utcnow()
        )
        db.session.add(dept)
        db.session.commit()
        print("✅ Sample department created!")
        return dept
    else:
        return Department.query.first()

def create_sample_user_and_tutor():
    """Create a sample tutor if none exists"""
    if Tutor.query.count() == 0:
        print("Creating sample tutor...")
        
        # Create user first
        user = User(
            username="tutor1",
            email="tutor1@example.com",
            full_name="John Smith",
            phone="9876543210",
            role="tutor",
            is_active=True,
            is_verified=True,
            created_at=datetime.now()  # Fixed: Use datetime.now() instead of utcnow()
        )
        user.set_password("password123")
        
        # Get department
        dept = Department.query.first()
        if dept:
            user.department_id = dept.id
        
        db.session.add(user)
        db.session.flush()  # Get the ID
        
        # Create tutor with ALL required fields
        tutor = Tutor(
            user_id=user.id,
            qualification="M.Sc Mathematics",
            experience="5 years teaching experience in high school mathematics",
            salary_type="monthly",  # FIXED: Added required salary_type
            monthly_salary=25000.0,  # FIXED: Added salary amount
            status="approved",  # Set to approved so they show up in lists
            verification_status="verified",  # Set to verified
            created_at=datetime.now()  # Fixed: Use datetime.now() instead of utcnow()
        )
        
        # Set subjects, grades, and boards using the model methods
        tutor.set_subjects(["Mathematics", "Physics"])
        tutor.set_grades(["9", "10", "11", "12"])
        tutor.set_boards(["CBSE", "ICSE"])
        
        db.session.add(tutor)
        db.session.commit()
        print("✅ Sample tutor created!")
        return tutor
    else:
        return Tutor.query.first()

def create_sample_student():
    """Create a sample student if none exists"""
    if Student.query.count() == 0:
        print("Creating sample student...")
        
        dept = Department.query.first()
        
        student = Student(
            full_name="Alice Johnson",
            email="alice@example.com",
            phone="9876543210",
            grade="10",
            board="CBSE",
            school_name="ABC High School",
            department_id=dept.id if dept else None,
            is_active=True,
            enrollment_status="active",  # Fixed: Use 'active' instead of 'enrolled'
            created_at=datetime.now()  # Fixed: Use datetime.now() instead of utcnow()
        )
        
        # Set parent details
        parent_details = {
            "father": {
                "name": "Robert Johnson",
                "phone": "9876543211",
                "email": "robert@example.com",
                "profession": "Engineer",
                "workplace": "Tech Corp"
            },
            "mother": {
                "name": "Mary Johnson", 
                "phone": "9876543212",
                "email": "mary@example.com",
                "profession": "Teacher",
                "workplace": "ABC School"
            }
        }
        student.set_parent_details(parent_details)
        
        # Set subjects enrolled
        student.set_subjects_enrolled(["Mathematics", "Physics", "Chemistry"])
        
        db.session.add(student)
        db.session.commit()
        print("✅ Sample student created!")
        return student
    else:
        return Student.query.first()

def create_sample_classes():
    """Create sample classes for testing"""
    if Class.query.count() == 0:
        print("Creating sample classes...")
        
        tutor = Tutor.query.first()
        student = Student.query.first()
        
        if tutor and student:
            # Create multiple classes for different days/times
            classes_to_create = [
                {
                    'subject': 'Mathematics',
                    'date': date.today(),
                    'time': time(10, 0),  # 10:00 AM
                    'status': 'scheduled'
                },
                {
                    'subject': 'Physics', 
                    'date': date.today(),
                    'time': time(14, 0),  # 2:00 PM
                    'status': 'ongoing'
                },
                {
                    'subject': 'Mathematics',
                    'date': date.today() + timedelta(days=1),
                    'time': time(11, 0),  # 11:00 AM tomorrow
                    'status': 'scheduled'
                },
                {
                    'subject': 'Chemistry',
                    'date': date.today() - timedelta(days=1),
                    'time': time(15, 0),  # 3:00 PM yesterday
                    'status': 'completed'
                }
            ]
            
            created_count = 0
            for class_data in classes_to_create:
                cls = Class(
                    subject=class_data['subject'],
                    class_type="one_on_one",
                    grade="10",
                    board="CBSE",
                    scheduled_date=class_data['date'],
                    scheduled_time=class_data['time'],
                    duration=60,
                    tutor_id=tutor.id,
                    primary_student_id=student.id,
                    platform="zoom",
                    meeting_link="https://zoom.us/j/123456789",
                    status=class_data['status'],
                    class_notes="Sample class notes",
                    created_at=datetime.now()
                )
                
                db.session.add(cls)
                created_count += 1
            
            db.session.commit()
            print(f"✅ {created_count} sample classes created!")
            return True
        else:
            print("❌ Cannot create classes - missing tutor or student")
            return False
    else:
        print("Classes already exist, skipping...")
        return True

def create_additional_sample_data():
    """Create additional tutors and students for testing"""
    print("Creating additional sample data...")
    
    dept = Department.query.first()
    
    # Create another tutor
    if Tutor.query.count() < 2:
        print("Creating second tutor...")
        user2 = User(
            username="tutor2",
            email="tutor2@example.com", 
            full_name="Sarah Wilson",
            phone="9876543211",
            role="tutor",
            department_id=dept.id if dept else None,
            is_active=True,
            is_verified=True,
            created_at=datetime.now()
        )
        user2.set_password("password123")
        db.session.add(user2)
        db.session.flush()
        
        tutor2 = Tutor(
            user_id=user2.id,
            qualification="M.Sc Physics",
            experience="3 years teaching physics and chemistry",
            salary_type="hourly",
            hourly_rate=500.0,
            status="approved",
            verification_status="verified",
            created_at=datetime.now()
        )
        tutor2.set_subjects(["Physics", "Chemistry"])
        tutor2.set_grades(["11", "12"])
        tutor2.set_boards(["CBSE"])
        
        db.session.add(tutor2)
    
    # Create another student
    if Student.query.count() < 2:
        print("Creating second student...")
        student2 = Student(
            full_name="Bob Smith",
            email="bob@example.com",
            phone="9876543213",
            grade="11",
            board="CBSE",
            school_name="XYZ High School",
            department_id=dept.id if dept else None,
            is_active=True,
            enrollment_status="active",
            created_at=datetime.now()
        )
        student2.set_subjects_enrolled(["Physics", "Chemistry", "Mathematics"])
        db.session.add(student2)
    
    try:
        db.session.commit()
        print("✅ Additional sample data created!")
    except Exception as e:
        print(f"❌ Error creating additional data: {str(e)}")
        db.session.rollback()

def setup_sample_data():
    """Set up all sample data"""
    print("Setting up sample data...")
    
    # Create in order due to dependencies
    dept = create_sample_department()
    tutor = create_sample_user_and_tutor() 
    student = create_sample_student()
    create_sample_classes()
    create_additional_sample_data()
    
    print("✅ Sample data setup complete!")

def verify_setup():
    """Verify that everything was created correctly"""
    print("\n🔍 Verifying setup...")
    
    try:
        dept_count = Department.query.count()
        user_count = User.query.count()
        tutor_count = Tutor.query.count()
        student_count = Student.query.count()
        class_count = Class.query.count()
        
        print(f"📊 Final counts:")
        print(f"  Departments: {dept_count}")
        print(f"  Users: {user_count}")
        print(f"  Tutors: {tutor_count}")
        print(f"  Students: {student_count}")
        print(f"  Classes: {class_count}")
        
        # Test relationships
        if tutor_count > 0:
            tutor = Tutor.query.first()
            print(f"  First tutor: {tutor.user.full_name if tutor.user else 'No user'}")
            print(f"  Tutor subjects: {tutor.get_subjects()}")
            print(f"  Tutor salary: {tutor.salary_type} - {tutor.monthly_salary or tutor.hourly_rate}")
        
        if student_count > 0:
            student = Student.query.first()
            print(f"  First student: {student.full_name}")
            print(f"  Student subjects: {student.get_subjects_enrolled()}")
        
        print("✅ Verification complete!")
        return True
        
    except Exception as e:
        print(f"❌ Verification failed: {str(e)}")
        return False

def main():
    app = create_app()
    
    with app.app_context():
        print("🚀 Starting database test and setup...")
        
        # Test connections
        if not test_database_connections():
            print("❌ Fix database issues first!")
            return
        
        # Check if we need sample data
        total_records = (Department.query.count() + 
                        Tutor.query.count() + 
                        Student.query.count() + 
                        Class.query.count())
        
        if total_records < 10:  # If very little data
            create_sample = input("Create sample data? (y/n): ").lower().strip()
            if create_sample == 'y':
                setup_sample_data()
                verify_setup()
        else:
            print("📊 Sufficient data exists, skipping sample creation")
            verify_setup()
        
        print("\n🎉 Setup complete! You can now:")
        print("1. Visit /admin/debug-timetable")
        print("2. Visit /admin/timetable")
        print("3. Test the API at /admin/test-timetable")
        print("4. Try creating classes")
        print("\n💡 Test credentials:")
        print("   Username: tutor1")
        print("   Password: password123")

if __name__ == "__main__":
    main()