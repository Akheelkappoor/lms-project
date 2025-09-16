# CREATE: upgrade_auto_attendance_system.py (in project root)

import os
import sys

# Add the project root to Python path
sys.path.insert(0, os.path.abspath('.'))

def upgrade_database():
    """
    Database upgrade script for auto-attendance system
    Run this after adding the new fields to models
    """
    
    try:
        from app import create_app, db
        from sqlalchemy import text
        
        # Create Flask app context
        app = create_app()
        
        with app.app_context():
            print("🔄 Starting database upgrade for auto-attendance system...")
            
            try:
                # Test database connection
                db.session.execute(text("SELECT 1"))
                print("✅ Database connection successful")
                
                # Add new columns to classes table
                print("📋 Adding new columns to classes table...")
                
                db.session.execute(text("""
                    ALTER TABLE classes 
                    ADD COLUMN IF NOT EXISTS video_uploaded_at TIMESTAMP;
                """))
                
                db.session.execute(text("""
                    ALTER TABLE classes 
                    ADD COLUMN IF NOT EXISTS video_upload_deadline TIMESTAMP;
                """))
                
                db.session.execute(text("""
                    ALTER TABLE classes 
                    ADD COLUMN IF NOT EXISTS video_reminder_sent BOOLEAN DEFAULT FALSE;
                """))
                
                db.session.execute(text("""
                    ALTER TABLE classes 
                    ADD COLUMN IF NOT EXISTS video_final_warning_sent BOOLEAN DEFAULT FALSE;
                """))
                
                db.session.execute(text("""
                    ALTER TABLE classes 
                    ADD COLUMN IF NOT EXISTS auto_attendance_marked BOOLEAN DEFAULT FALSE;
                """))
                
                db.session.execute(text("""
                    ALTER TABLE classes 
                    ADD COLUMN IF NOT EXISTS attendance_review_completed BOOLEAN DEFAULT FALSE;
                """))
                
                db.session.execute(text("""
                    ALTER TABLE classes 
                    ADD COLUMN IF NOT EXISTS attendance_verified_by INTEGER;
                """))
                
                db.session.execute(text("""
                    ALTER TABLE classes 
                    ADD COLUMN IF NOT EXISTS attendance_verified_at TIMESTAMP;
                """))
                
                db.session.execute(text("""
                    ALTER TABLE classes 
                    ADD COLUMN IF NOT EXISTS completion_method VARCHAR(20);
                """))
                
                db.session.execute(text("""
                    ALTER TABLE classes 
                    ADD COLUMN IF NOT EXISTS quality_review_status VARCHAR(20);
                """))
                
                db.session.execute(text("""
                    ALTER TABLE classes 
                    ADD COLUMN IF NOT EXISTS quality_reviewed_by INTEGER;
                """))
                
                db.session.execute(text("""
                    ALTER TABLE classes 
                    ADD COLUMN IF NOT EXISTS quality_reviewed_at TIMESTAMP;
                """))
                
                db.session.execute(text("""
                    ALTER TABLE classes 
                    ADD COLUMN IF NOT EXISTS quality_feedback TEXT;
                """))
                
                db.session.execute(text("""
                    ALTER TABLE classes 
                    ADD COLUMN IF NOT EXISTS punctuality_score FLOAT;
                """))
                
                db.session.execute(text("""
                    ALTER TABLE classes 
                    ADD COLUMN IF NOT EXISTS engagement_average FLOAT;
                """))
                
                db.session.execute(text("""
                    ALTER TABLE classes 
                    ADD COLUMN IF NOT EXISTS completion_compliance BOOLEAN DEFAULT TRUE;
                """))
                
                print("✅ Classes table updated successfully")
                
                # Add new columns to attendance table
                print("📋 Adding new columns to attendance table...")
                
                db.session.execute(text("""
                    ALTER TABLE attendance 
                    ADD COLUMN IF NOT EXISTS auto_marked BOOLEAN DEFAULT FALSE;
                """))
                
                db.session.execute(text("""
                    ALTER TABLE attendance 
                    ADD COLUMN IF NOT EXISTS manually_reviewed BOOLEAN DEFAULT FALSE;
                """))
                
                db.session.execute(text("""
                    ALTER TABLE attendance 
                    ADD COLUMN IF NOT EXISTS review_timestamp TIMESTAMP;
                """))
                
                db.session.execute(text("""
                    ALTER TABLE attendance 
                    ADD COLUMN IF NOT EXISTS original_status VARCHAR(20);
                """))
                
                db.session.execute(text("""
                    ALTER TABLE attendance 
                    ADD COLUMN IF NOT EXISTS final_status VARCHAR(20);
                """))
                
                db.session.execute(text("""
                    ALTER TABLE attendance 
                    ADD COLUMN IF NOT EXISTS status_change_reason VARCHAR(200);
                """))
                
                db.session.execute(text("""
                    ALTER TABLE attendance 
                    ADD COLUMN IF NOT EXISTS engagement_score FLOAT;
                """))
                
                db.session.execute(text("""
                    ALTER TABLE attendance 
                    ADD COLUMN IF NOT EXISTS participation_notes TEXT;
                """))
                
                db.session.execute(text("""
                    ALTER TABLE attendance 
                    ADD COLUMN IF NOT EXISTS tutor_satisfaction INTEGER;
                """))
                
                print("✅ Attendance table updated successfully")
                
                # Add new columns to tutors table
                print("📋 Adding new columns to tutors table...")
                
                db.session.execute(text("""
                    ALTER TABLE tutors 
                    ADD COLUMN IF NOT EXISTS rating_history TEXT;
                """))
                
                db.session.execute(text("""
                    ALTER TABLE tutors 
                    ADD COLUMN IF NOT EXISTS last_rating_update TIMESTAMP;
                """))
                
                db.session.execute(text("""
                    ALTER TABLE tutors 
                    ADD COLUMN IF NOT EXISTS rating_calculation_method VARCHAR(50) DEFAULT 'performance_based';
                """))
                
                db.session.execute(text("""
                    ALTER TABLE tutors 
                    ADD COLUMN IF NOT EXISTS video_upload_compliance FLOAT DEFAULT 100.0;
                """))
                
                db.session.execute(text("""
                    ALTER TABLE tutors 
                    ADD COLUMN IF NOT EXISTS punctuality_average FLOAT DEFAULT 5.0;
                """))
                
                db.session.execute(text("""
                    ALTER TABLE tutors 
                    ADD COLUMN IF NOT EXISTS engagement_average FLOAT DEFAULT 3.0;
                """))
                
                db.session.execute(text("""
                    ALTER TABLE tutors 
                    ADD COLUMN IF NOT EXISTS completion_rate_30d FLOAT DEFAULT 100.0;
                """))
                
                db.session.execute(text("""
                    ALTER TABLE tutors 
                    ADD COLUMN IF NOT EXISTS auto_attendance_usage INTEGER DEFAULT 0;
                """))
                
                db.session.execute(text("""
                    ALTER TABLE tutors 
                    ADD COLUMN IF NOT EXISTS manual_review_rate FLOAT DEFAULT 0.0;
                """))
                
                print("✅ Tutors table updated successfully")
                
                # Commit all changes
                db.session.commit()
                
                print("\n🎉 Database upgrade completed successfully!")
                print("=" * 60)
                print("✅ Auto-attendance system database schema updated")
                print("✅ All new fields added successfully")
                print("✅ System ready for auto-attendance functionality")
                print("=" * 60)
                
                # Show summary of changes
                print("\n📊 SUMMARY OF CHANGES:")
                print("Classes table: +16 new columns")
                print("Attendance table: +9 new columns") 
                print("Tutors table: +9 new columns")
                print("\n🚀 You can now start using the auto-attendance system!")
                
            except Exception as e:
                db.session.rollback()
                print(f"❌ Error during database upgrade: {str(e)}")
                print("\n🔧 TROUBLESHOOTING:")
                print("1. Make sure your database is running")
                print("2. Check your database connection string in .env")
                print("3. Ensure you have proper permissions")
                print("4. Try running: flask db upgrade")
                return False
                
    except ImportError as e:
        print(f"❌ Import error: {str(e)}")
        print("\n🔧 TROUBLESHOOTING:")
        print("1. Make sure you're in the project root directory")
        print("2. Check that your virtual environment is activated")
        print("3. Run: pip install -r requirements.txt")
        print("4. Ensure app/__init__.py exists")
        return False
    
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return False
    
    return True

def confirm_upgrade():
    """Confirm upgrade with user"""
    print("⚠️  AUTO-ATTENDANCE SYSTEM DATABASE UPGRADE")
    print("=" * 60)
    print("This will add new columns to your database tables:")
    print("• Classes table: Video tracking, auto-attendance flags")
    print("• Attendance table: Auto-marking, review tracking")  
    print("• Tutors table: Rating history, compliance metrics")
    print("\n⚠️  BACKUP RECOMMENDED: Please backup your database first!")
    print("=" * 60)
    
    response = input("\nProceed with upgrade? (type 'YES' to confirm): ")
    
    if response != 'YES':
        print("❌ Database upgrade cancelled.")
        return False
    
    return True

if __name__ == '__main__':
    print("🚀 LMS Auto-Attendance System Database Upgrade")
    print("=" * 60)
    
    if confirm_upgrade():
        success = upgrade_database()
        if success:
            print("\n✅ Upgrade completed successfully!")
            print("You can now restart your application and use the auto-attendance system.")
        else:
            print("\n❌ Upgrade failed. Please check the errors above.")
            sys.exit(1)
    else:
        print("Upgrade cancelled by user.")
        sys.exit(0)