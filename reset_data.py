#!/usr/bin/env python3
"""
Database Reset Script for LMS Project
Usage: python reset_database.py
"""

import os
import sys
from app import create_app, db
from app.models.user import User
from app.models.department import Department
from app.models.tutor import Tutor
from app.models.student import Student
from app.models.class_model import Class
from app.models.attendance import Attendance

def reset_database():
    """Reset the entire database"""
    app = create_app()
    
    with app.app_context():
        print("🔄 Starting database reset...")
        
        try:
            # Drop all tables
# Drop all tables, even with circular dependencies
            print("📋 Reflecting and dropping all tables (even with circular FKs)...")
            from sqlalchemy import MetaData
            meta = MetaData()
            meta.reflect(bind=db.engine)
            meta.drop_all(bind=db.engine)
            print("✅ All tables dropped successfully")

            
            # Create all tables
            print("🏗️  Creating tables...")
            db.create_all()
            print("✅ All tables created successfully")
            
            # Create default departments
            print("🏢 Creating default departments...")
            Department.create_default_departments()
            print("✅ Default departments created")
            
            # Create default admin
            print("👤 Creating default superadmin...")
            admin = User.create_default_admin()
            print(f"✅ Default superadmin created: {admin.email}")
            
            print("\n🎉 Database reset completed successfully!")
            print("=" * 50)
            print("Default Login Credentials:")
            print(f"Email: {admin.email}")
            print(f"Password: {admin.password}")
            print("=" * 50)
            
        except Exception as e:
            print(f"❌ Error during database reset: {str(e)}")
            sys.exit(1)

def confirm_reset():
    """Confirm reset with user"""
    print("⚠️  WARNING: This will delete ALL data in the database!")
    print("This action cannot be undone.")
    
    response = input("\nAre you sure you want to continue? (type 'YES' to confirm): ")
    
    if response != 'YES':
        print("❌ Database reset cancelled.")
        sys.exit(0)
    
    return True

if __name__ == '__main__':
    confirm_reset()
    reset_database()