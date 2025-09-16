"""
Performance Migration Script
Run this to apply all database optimizations and create indexes
"""
from app import db
from sqlalchemy import text, Index


class PerformanceMigration:
    """Apply performance optimizations to the database"""
    
    @staticmethod
    def create_indexes():
        """Create database indexes for better query performance"""
        try:
            # Student indexes
            indexes_to_create = [
                # Student table indexes
                "CREATE INDEX IF NOT EXISTS idx_students_active ON students(is_active)",
                "CREATE INDEX IF NOT EXISTS idx_students_enrollment_status ON students(enrollment_status)",
                "CREATE INDEX IF NOT EXISTS idx_students_created_at ON students(created_at)",
                "CREATE INDEX IF NOT EXISTS idx_students_department_id ON students(department_id)",
                "CREATE INDEX IF NOT EXISTS idx_students_grade ON students(grade)",
                "CREATE INDEX IF NOT EXISTS idx_students_board ON students(board)",
                "CREATE INDEX IF NOT EXISTS idx_students_email ON students(email)",
                
                # Class table indexes
                "CREATE INDEX IF NOT EXISTS idx_classes_scheduled_date ON classes(scheduled_date)",
                "CREATE INDEX IF NOT EXISTS idx_classes_scheduled_time ON classes(scheduled_time)",
                "CREATE INDEX IF NOT EXISTS idx_classes_tutor_id ON classes(tutor_id)",
                "CREATE INDEX IF NOT EXISTS idx_classes_status ON classes(status)",
                "CREATE INDEX IF NOT EXISTS idx_classes_completion_status ON classes(completion_status)",
                "CREATE INDEX IF NOT EXISTS idx_classes_primary_student_id ON classes(primary_student_id)",
                "CREATE INDEX IF NOT EXISTS idx_classes_tutor_date ON classes(tutor_id, scheduled_date)",
                "CREATE INDEX IF NOT EXISTS idx_classes_date_status ON classes(scheduled_date, status)",
                
                # User table indexes
                "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)",
                "CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)",
                "CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active)",
                "CREATE INDEX IF NOT EXISTS idx_users_department_id ON users(department_id)",
                
                # Tutor table indexes
                "CREATE INDEX IF NOT EXISTS idx_tutors_status ON tutors(status)",
                "CREATE INDEX IF NOT EXISTS idx_tutors_user_id ON tutors(user_id)",
                
                # Attendance table indexes
                "CREATE INDEX IF NOT EXISTS idx_attendance_class_id ON attendance(class_id)",
                "CREATE INDEX IF NOT EXISTS idx_attendance_student_id ON attendance(student_id)",
                "CREATE INDEX IF NOT EXISTS idx_attendance_tutor_id ON attendance(tutor_id)",
                "CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(class_date)",
                "CREATE INDEX IF NOT EXISTS idx_attendance_status ON attendance(status)",
                
                # Department table indexes
                "CREATE INDEX IF NOT EXISTS idx_departments_active ON departments(is_active)",
                "CREATE INDEX IF NOT EXISTS idx_departments_name ON departments(name)"
            ]
            
            for index_sql in indexes_to_create:
                try:
                    db.session.execute(text(index_sql))
                    print(f"✓ Created index: {index_sql.split()[-1]}")
                except Exception as e:
                    print(f"✗ Failed to create index: {e}")
            
            db.session.commit()
            print("✓ All indexes created successfully")
            
        except Exception as e:
            db.session.rollback()
            print(f"✗ Error creating indexes: {e}")
    
    @staticmethod
    def analyze_tables():
        """Analyze tables for query optimization (PostgreSQL/MySQL)"""
        try:
            # Get database engine type
            engine = db.engine.name
            
            tables = ['students', 'classes', 'users', 'tutors', 'attendance', 'departments']
            
            if engine == 'postgresql':
                # PostgreSQL ANALYZE
                for table in tables:
                    db.session.execute(text(f"ANALYZE {table}"))
                    print(f"✓ Analyzed table: {table}")
            
            elif engine == 'mysql':
                # MySQL ANALYZE
                for table in tables:
                    db.session.execute(text(f"ANALYZE TABLE {table}"))
                    print(f"✓ Analyzed table: {table}")
            
            else:
                print(f"Table analysis not supported for {engine}")
            
            db.session.commit()
            print("✓ Table analysis completed")
            
        except Exception as e:
            db.session.rollback()
            print(f"✗ Error analyzing tables: {e}")
    
    @staticmethod
    def optimize_json_queries():
        """Create indexes for JSON field queries (PostgreSQL)"""
        try:
            engine = db.engine.name
            
            if engine == 'postgresql':
                # PostgreSQL JSON indexes
                json_indexes = [
                    "CREATE INDEX IF NOT EXISTS idx_students_subjects_gin ON students USING gin ((subjects_enrolled::jsonb))",
                    "CREATE INDEX IF NOT EXISTS idx_tutors_subjects_gin ON tutors USING gin ((subjects_taught::jsonb))",
                    "CREATE INDEX IF NOT EXISTS idx_tutors_availability_gin ON tutors USING gin ((availability::jsonb))"
                ]
                
                for index_sql in json_indexes:
                    try:
                        db.session.execute(text(index_sql))
                        print(f"✓ Created JSON index")
                    except Exception as e:
                        print(f"✗ Failed to create JSON index: {e}")
                
                db.session.commit()
                print("✓ JSON indexes created successfully")
            
            else:
                print(f"JSON indexes not supported for {engine}")
                
        except Exception as e:
            db.session.rollback()
            print(f"✗ Error creating JSON indexes: {e}")
    
    @staticmethod
    def check_query_performance():
        """Check slow queries and provide optimization suggestions"""
        try:
            print("\n=== Query Performance Analysis ===")
            
            # Test common queries
            queries = [
                {
                    'name': 'Active Students Count',
                    'sql': "SELECT COUNT(*) FROM students WHERE is_active = true"
                },
                {
                    'name': 'Today\'s Classes',
                    'sql': "SELECT COUNT(*) FROM classes WHERE scheduled_date = CURRENT_DATE"
                },
                {
                    'name': 'Active Tutors with Users',
                    'sql': "SELECT COUNT(*) FROM tutors t JOIN users u ON t.user_id = u.id WHERE t.status = 'active'"
                },
                {
                    'name': 'Recent Classes with Tutors',
                    'sql': "SELECT COUNT(*) FROM classes c JOIN tutors t ON c.tutor_id = t.id WHERE c.scheduled_date >= CURRENT_DATE - INTERVAL '7' DAY"
                }
            ]
            
            for query in queries:
                try:
                    import time
                    start_time = time.time()
                    
                    result = db.session.execute(text(query['sql']))
                    count = result.scalar()
                    
                    end_time = time.time()
                    duration = round((end_time - start_time) * 1000, 2)
                    
                    status = "✓" if duration < 100 else "⚠️" if duration < 500 else "✗"
                    print(f"{status} {query['name']}: {count} records in {duration}ms")
                    
                    if duration > 500:
                        print(f"  └─ Warning: Query is slow (>{duration}ms)")
                    
                except Exception as e:
                    print(f"✗ {query['name']}: Error - {e}")
            
            print("\n=== Performance Recommendations ===")
            print("✓ Queries under 100ms: Excellent performance")
            print("⚠️ Queries 100-500ms: Good performance, monitor usage")
            print("✗ Queries over 500ms: Needs optimization")
            
        except Exception as e:
            print(f"✗ Error checking query performance: {e}")
    
    @staticmethod
    def run_full_optimization():
        """Run complete performance optimization"""
        print("🚀 Starting LMS Performance Optimization...")
        print("=" * 50)
        
        print("\n1. Creating database indexes...")
        PerformanceMigration.create_indexes()
        
        print("\n2. Optimizing JSON queries...")
        PerformanceMigration.optimize_json_queries()
        
        print("\n3. Analyzing tables...")
        PerformanceMigration.analyze_tables()
        
        print("\n4. Checking query performance...")
        PerformanceMigration.check_query_performance()
        
        print("\n" + "=" * 50)
        print("🎉 Performance optimization completed!")
        print("\nNext steps:")
        print("- Monitor query performance in production")
        print("- Use DatabaseService for new queries")
        print("- Apply ValidationService to forms")
        print("- Implement ErrorService in routes")


# CLI commands for easy execution
def create_performance_indexes():
    """CLI command to create performance indexes"""
    PerformanceMigration.create_indexes()


def check_performance():
    """CLI command to check performance"""
    PerformanceMigration.check_query_performance()


def optimize_database():
    """CLI command to run full optimization"""
    PerformanceMigration.run_full_optimization()


if __name__ == "__main__":
    # Run when executed directly
    from app import create_app
    
    app = create_app()
    with app.app_context():
        PerformanceMigration.run_full_optimization()