#!/usr/bin/env python3
"""
Add finance columns to existing database
Run this after updating the models
"""

from app import create_app, db
from sqlalchemy import text

def add_finance_columns():
    """Add new finance columns to existing tables"""
    app = create_app()
    
    with app.app_context():
        print("🔄 Adding finance columns...")
        
        try:
            # Add columns to tutors table
            print("📋 Adding tutor finance columns...")
            
            # Check if columns exist before adding
            result = db.session.execute(text("PRAGMA table_info(tutors)"))
            existing_columns = [row[1] for row in result.fetchall()]
            
            if 'salary_history' not in existing_columns:
                db.session.execute(text('ALTER TABLE tutors ADD COLUMN salary_history TEXT'))
                print("✅ Added salary_history to tutors")
            
            if 'total_earnings' not in existing_columns:
                db.session.execute(text('ALTER TABLE tutors ADD COLUMN total_earnings FLOAT DEFAULT 0.0'))
                print("✅ Added total_earnings to tutors")
            
            if 'last_salary_date' not in existing_columns:
                db.session.execute(text('ALTER TABLE tutors ADD COLUMN last_salary_date DATE'))
                print("✅ Added last_salary_date to tutors")
            
            # Add columns to students table
            print("📋 Adding student finance columns...")
            
            result = db.session.execute(text("PRAGMA table_info(students)"))
            existing_columns = [row[1] for row in result.fetchall()]
            
            if 'payment_history' not in existing_columns:
                db.session.execute(text('ALTER TABLE students ADD COLUMN payment_history TEXT'))
                print("✅ Added payment_history to students")
            
            db.session.commit()
            print("\n🎉 Finance columns added successfully!")
            
        except Exception as e:
            print(f"❌ Error adding columns: {str(e)}")
            db.session.rollback()
            
            # Columns might already exist, check if we can continue
            try:
                # Test if we can query the tables normally
                from app.models.tutor import Tutor
                from app.models.student import Student
                
                tutor_count = Tutor.query.count()
                student_count = Student.query.count()
                
                print(f"✅ Tables accessible: {tutor_count} tutors, {student_count} students")
                print("💡 Columns may already exist - continuing with existing structure")
                
            except Exception as e2:
                print(f"❌ Database structure issue: {str(e2)}")
                return False
        
        return True

if __name__ == '__main__':
    add_finance_columns()