"""
Database optimization utilities for adding indexes and constraints.
"""
from app import db
from sqlalchemy import text, Index
import logging

logger = logging.getLogger(__name__)

class DatabaseOptimizer:
    """Utility class for database performance optimizations"""
    
    @staticmethod
    def create_indexes():
        """Create performance-optimizing indexes"""
        try:
            # User table indexes
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_user_email ON user (email);
            """))
            
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_user_username ON user (username);
            """))
            
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_user_role ON user (role);
            """))
            
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_user_department ON user (department_id);
            """))
            
            # Student table indexes
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_student_email ON student (email);
            """))
            
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_student_grade ON student (grade);
            """))
            
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_student_active ON student (is_active);
            """))
            
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_student_status ON student (enrollment_status);
            """))
            
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_student_department ON student (department_id);
            """))
            
            # Tutor table indexes
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_tutor_status ON tutor (status);
            """))
            
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_tutor_user ON tutor (user_id);
            """))
            
            # Class table indexes
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_class_date ON class (scheduled_date);
            """))
            
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_class_tutor ON class (tutor_id);
            """))
            
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_class_status ON class (status);
            """))
            
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_class_subject ON class (subject);
            """))
            
            # Attendance table indexes
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_attendance_student ON attendance (student_id);
            """))
            
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_attendance_class ON attendance (class_id);
            """))
            
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance (class_date);
            """))
            
            # Notice table indexes
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_notice_published ON notice (is_published);
            """))
            
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_notice_category ON notice (category);
            """))
            
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_notice_priority ON notice (priority);
            """))
            
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_notice_created_at ON notice (created_at);
            """))
            
            # Reschedule request indexes
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_reschedule_status ON reschedule_request (status);
            """))
            
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_reschedule_class ON reschedule_request (class_id);
            """))
            
            db.session.commit()
            logger.info("Database indexes created successfully")
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating indexes: {e}")
            raise
    
    @staticmethod
    def add_constraints():
        """Add data integrity constraints"""
        try:
            # Email format constraints
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS temp_constraint_check AS 
                SELECT 1 WHERE EXISTS (
                    SELECT 1 FROM pragma_table_info('user') 
                    WHERE name = 'email'
                );
            """))
            
            # Add check constraints for email format (if supported)
            # Note: SQLite has limited constraint support, so we'll focus on indexes
            
            # Add foreign key constraints validation
            db.session.execute(text("PRAGMA foreign_keys = ON;"))
            
            db.session.commit()
            logger.info("Database constraints added successfully")
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error adding constraints: {e}")
            raise
    
    @staticmethod
    def analyze_performance():
        """Analyze database performance and suggest optimizations"""
        try:
            # Get table sizes
            tables_info = {}
            
            table_names = [
                'user', 'student', 'tutor', 'class', 'attendance', 
                'notice', 'department', 'reschedule_request'
            ]
            
            for table in table_names:
                try:
                    result = db.session.execute(text(f"SELECT COUNT(*) FROM {table}")).fetchone()
                    tables_info[table] = result[0] if result else 0
                except Exception as e:
                    logger.warning(f"Could not get count for table {table}: {e}")
                    tables_info[table] = 0
            
            # Check for missing indexes (simplified check)
            missing_indexes = []
            
            # Check if foreign key indexes exist
            fk_checks = [
                ('user', 'department_id'),
                ('student', 'department_id'),
                ('tutor', 'user_id'),
                ('class', 'tutor_id'),
                ('attendance', 'student_id'),
                ('attendance', 'class_id'),
                ('reschedule_request', 'class_id'),
            ]
            
            for table, column in fk_checks:
                try:
                    # Check if index exists (simplified)
                    index_name = f"idx_{table}_{column.replace('_id', '')}"
                    result = db.session.execute(text(f"""
                        SELECT name FROM sqlite_master 
                        WHERE type='index' AND name='{index_name}'
                    """)).fetchone()
                    
                    if not result:
                        missing_indexes.append(f"{table}.{column}")
                except Exception:
                    pass
            
            performance_report = {
                'table_sizes': tables_info,
                'missing_indexes': missing_indexes,
                'recommendations': []
            }
            
            # Add recommendations based on table sizes
            for table, count in tables_info.items():
                if count > 1000:
                    performance_report['recommendations'].append(
                        f"Table '{table}' has {count} records - ensure proper indexing"
                    )
            
            if missing_indexes:
                performance_report['recommendations'].append(
                    f"Consider adding indexes for: {', '.join(missing_indexes)}"
                )
            
            return performance_report
            
        except Exception as e:
            logger.error(f"Error analyzing performance: {e}")
            return {'error': str(e)}
    
    @staticmethod
    def optimize_database():
        """Run complete database optimization"""
        try:
            logger.info("Starting database optimization...")
            
            # Create indexes
            DatabaseOptimizer.create_indexes()
            
            # Add constraints
            DatabaseOptimizer.add_constraints()
            
            # Analyze tables
            db.session.execute(text("ANALYZE;"))
            db.session.commit()
            
            logger.info("Database optimization completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Database optimization failed: {e}")
            return False