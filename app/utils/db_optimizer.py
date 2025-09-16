# Database Performance Optimizer
from sqlalchemy import create_engine, text, event
from sqlalchemy.pool import QueuePool
from flask import current_app
from app import db
import time
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

class DatabaseOptimizer:
    """High-performance database connection and query optimization"""
    
    def __init__(self):
        self.query_cache = {}
        self.slow_query_threshold = 0.5  # 500ms
        self.query_stats = {'fast': 0, 'slow': 0, 'total_time': 0}
    
    def setup_connection_pool(self, app):
        """Setup optimized database connection pooling"""
        try:
            # Configure SQLAlchemy engine options directly in the app config
            app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
                'poolclass': QueuePool,
                'pool_size': 20,           # More connections for high load
                'max_overflow': 30,        # Allow burst connections
                'pool_pre_ping': True,     # Validate connections before use
                'pool_recycle': 3600,      # Recycle connections every hour
                'connect_args': {
                    "options": "-c default_transaction_isolation=read_committed"
                }
            }
            
            # Reinitialize the database with new engine options
            # This is necessary for the new engine options to take effect
            with app.app_context():
                db.create_all()
            
            print("✅ Database connection pool optimized")
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup connection pool: {e}")
            return False
    
    def create_essential_indexes(self):
        """Create database indexes for optimal performance"""
        indexes = [
            # User table indexes
            "CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active) WHERE is_active = true;",
            "CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);",
            "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);",
            "CREATE INDEX IF NOT EXISTS idx_users_department ON users(department_id);",
            
            # Student table indexes
            "CREATE INDEX IF NOT EXISTS idx_students_active ON students(is_active) WHERE is_active = true;",
            "CREATE INDEX IF NOT EXISTS idx_students_enrollment ON students(enrollment_status);",
            "CREATE INDEX IF NOT EXISTS idx_students_created ON students(created_at);",
            "CREATE INDEX IF NOT EXISTS idx_students_department ON students(department_id);",
            
            # Class table indexes
            "CREATE INDEX IF NOT EXISTS idx_classes_date ON classes(scheduled_date);",
            "CREATE INDEX IF NOT EXISTS idx_classes_tutor ON classes(tutor_id);",
            "CREATE INDEX IF NOT EXISTS idx_classes_status ON classes(status);",
            "CREATE INDEX IF NOT EXISTS idx_classes_date_status ON classes(scheduled_date, status);",
            
            # Attendance table indexes
            "CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(class_date);",
            "CREATE INDEX IF NOT EXISTS idx_attendance_student ON attendance(student_id);",
            "CREATE INDEX IF NOT EXISTS idx_attendance_tutor ON attendance(tutor_id);",
            "CREATE INDEX IF NOT EXISTS idx_attendance_present ON attendance(student_present, tutor_present);",
            
            # Tutor table indexes
            "CREATE INDEX IF NOT EXISTS idx_tutors_status ON tutors(status);",
            "CREATE INDEX IF NOT EXISTS idx_tutors_user ON tutors(user_id);",
            
            # Department table indexes
            "CREATE INDEX IF NOT EXISTS idx_departments_active ON departments(is_active) WHERE is_active = true;",
            
            # Error log indexes (if exists)
            "CREATE INDEX IF NOT EXISTS idx_error_logs_created ON error_logs(created_at);",
            "CREATE INDEX IF NOT EXISTS idx_error_logs_severity ON error_logs(severity);",
            "CREATE INDEX IF NOT EXISTS idx_error_logs_user ON error_logs(user_id);",
        ]
        
        created_count = 0
        failed_count = 0
        
        try:
            for index_sql in indexes:
                try:
                    db.session.execute(text(index_sql))
                    db.session.commit()
                    created_count += 1
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        logger.warning(f"Index creation failed: {e}")
                        failed_count += 1
                    db.session.rollback()
            
            print(f"✅ Database indexes: {created_count} created, {failed_count} failed")
            return True
            
        except Exception as e:
            logger.error(f"Index creation failed: {e}")
            db.session.rollback()
            return False
    
    def optimize_database_settings(self):
        """Apply database-level performance optimizations"""
        optimizations = [
            # PostgreSQL optimizations
            "SET shared_preload_libraries = 'pg_stat_statements';",
            "SET effective_cache_size = '256MB';",
            "SET maintenance_work_mem = '64MB';",
            "SET checkpoint_completion_target = 0.9;",
            "SET wal_buffers = '16MB';",
            "SET default_statistics_target = 100;",
            
            # Connection optimizations
            "SET tcp_keepalives_idle = 600;",
            "SET tcp_keepalives_interval = 30;",
            "SET tcp_keepalives_count = 3;",
        ]
        
        applied_count = 0
        for optimization in optimizations:
            try:
                db.session.execute(text(optimization))
                applied_count += 1
            except Exception as e:
                # Many settings might not be applicable, so we continue
                pass
        
        try:
            db.session.commit()
            print(f"✅ Database optimizations applied: {applied_count}")
        except:
            db.session.rollback()
    
    @contextmanager
    def fast_query(self, description="Query"):
        """Context manager for fast query execution with timing"""
        start_time = time.time()
        try:
            yield
        finally:
            execution_time = time.time() - start_time
            self.query_stats['total_time'] += execution_time
            
            if execution_time > self.slow_query_threshold:
                self.query_stats['slow'] += 1
                logger.warning(f"Slow query detected: {description} took {execution_time:.3f}s")
            else:
                self.query_stats['fast'] += 1
    
    def get_optimized_dashboard_stats(self):
        """Get dashboard statistics with single optimized query"""
        with self.fast_query("Dashboard statistics"):
            # Single complex query instead of multiple queries
            query = text("""
                WITH user_stats AS (
                    SELECT 
                        COUNT(*) FILTER (WHERE is_active = true) as total_users,
                        COUNT(*) FILTER (WHERE role IN ('superadmin', 'admin', 'coordinator') AND is_active = true) as total_admins,
                        COUNT(*) FILTER (WHERE role = 'tutor' AND is_active = true) as total_tutors
                    FROM users
                ),
                student_stats AS (
                    SELECT 
                        COUNT(*) FILTER (WHERE is_active = true) as total_students,
                        COUNT(*) FILTER (WHERE is_active = true AND created_at >= CURRENT_DATE - INTERVAL '1 month') as new_students_month,
                        COUNT(*) FILTER (WHERE is_active = true AND created_at >= CURRENT_DATE - INTERVAL '1 week') as new_students_week
                    FROM students
                ),
                class_stats AS (
                    SELECT 
                        COUNT(*) FILTER (WHERE scheduled_date = CURRENT_DATE) as todays_classes,
                        COUNT(*) FILTER (WHERE scheduled_date >= DATE_TRUNC('month', CURRENT_DATE) AND scheduled_date <= CURRENT_DATE) as total_classes_month,
                        COUNT(*) FILTER (WHERE scheduled_date >= DATE_TRUNC('month', CURRENT_DATE) AND scheduled_date <= CURRENT_DATE AND status = 'completed') as completed_classes_month,
                        COUNT(*) FILTER (WHERE scheduled_date > CURRENT_DATE AND status = 'scheduled') as upcoming_classes
                    FROM classes
                ),
                attendance_today AS (
                    SELECT 
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE tutor_present = true AND student_present = true) as present,
                        COUNT(*) FILTER (WHERE tutor_present = false OR student_present = false) as absent,
                        COUNT(*) FILTER (WHERE tutor_late_minutes > 5 OR student_late_minutes > 5) as late
                    FROM attendance 
                    WHERE class_date = CURRENT_DATE
                ),
                attendance_week AS (
                    SELECT 
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE tutor_present = true AND student_present = true) as present
                    FROM attendance 
                    WHERE class_date >= CURRENT_DATE - INTERVAL '1 week'
                )
                SELECT 
                    u.total_users, u.total_admins, u.total_tutors,
                    s.total_students, s.new_students_month, s.new_students_week,
                    c.todays_classes, c.total_classes_month, c.completed_classes_month, c.upcoming_classes,
                    at.total as attendance_total, at.present as attendance_present, 
                    at.absent as attendance_absent, at.late as attendance_late,
                    aw.total as week_total, aw.present as week_present
                FROM user_stats u, student_stats s, class_stats c, attendance_today at, attendance_week aw;
            """)
            
            result = db.session.execute(query).fetchone()
            
            if result:
                return {
                    'total_users': int(result.total_users or 0),
                    'total_admins': int(result.total_admins or 0),
                    'total_tutors': int(result.total_tutors or 0),
                    'total_students': int(result.total_students or 0),
                    'new_students_this_month': int(result.new_students_month or 0),
                    'new_students_this_week': int(result.new_students_week or 0),
                    'todays_classes': int(result.todays_classes or 0),
                    'total_classes_this_month': int(result.total_classes_month or 0),
                    'completed_classes_this_month': int(result.completed_classes_month or 0),
                    'upcoming_classes': int(result.upcoming_classes or 0),
                    'todays_attendance': {
                        'total': int(result.attendance_total or 0),
                        'present': int(result.attendance_present or 0),
                        'absent': int(result.attendance_absent or 0),
                        'late': int(result.attendance_late or 0)
                    },
                    'week_attendance': {
                        'total': int(result.week_total or 0),
                        'present': int(result.week_present or 0),
                        'completion_rate': round((result.week_present / result.week_total * 100) if result.week_total > 0 else 0, 1)
                    },
                    'departments': [],  # Can be loaded separately if needed
                    'performance': {},
                    'finance': {},
                    'system_health': {}
                }
            
            return self._get_fallback_stats()
    
    def _get_fallback_stats(self):
        """Fallback statistics with minimal data"""
        return {
            'total_users': 0, 'total_admins': 0, 'total_tutors': 0,
            'total_students': 0, 'new_students_this_month': 0,
            'todays_classes': 0, 'total_classes_this_month': 0,
            'todays_attendance': {'total': 0, 'present': 0, 'absent': 0, 'late': 0},
            'week_attendance': {'total': 0, 'present': 0, 'completion_rate': 0},
            'departments': [], 'performance': {}, 'finance': {}, 'system_health': {}
        }
    
    def get_performance_stats(self):
        """Get database performance statistics"""
        total_queries = self.query_stats['fast'] + self.query_stats['slow']
        avg_time = self.query_stats['total_time'] / total_queries if total_queries > 0 else 0
        
        return {
            'total_queries': total_queries,
            'fast_queries': self.query_stats['fast'],
            'slow_queries': self.query_stats['slow'],
            'average_time': round(avg_time * 1000, 2),  # in milliseconds
            'total_time': round(self.query_stats['total_time'], 3)
        }

# Global optimizer instance
db_optimizer = DatabaseOptimizer()

def setup_database_optimization(app):
    """Setup all database optimizations"""
    try:
        print("🚀 Setting up database optimizations...")
        
        with app.app_context():
            # Setup connection pooling
            db_optimizer.setup_connection_pool(app)
            
            # Create indexes
            db_optimizer.create_essential_indexes()
            
            # Apply optimizations
            db_optimizer.optimize_database_settings()
            
        print("✅ Database optimization complete")
        return True
        
    except Exception as e:
        print(f"❌ Database optimization failed: {e}")
        return False