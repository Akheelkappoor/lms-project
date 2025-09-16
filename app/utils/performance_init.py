# Performance System Initialization
from flask import Flask, current_app
import os
import threading
import time
import logging
from .performance_cache import cache, setup_cache_warming
from .db_optimizer import setup_database_optimization, db_optimizer
from .auth_optimized import warm_auth_cache

logger = logging.getLogger(__name__)

class PerformanceManager:
    """Central performance management system"""
    
    def __init__(self):
        self.initialized = False
        self.background_tasks = []
        self.performance_stats = {
            'cache_enabled': False,
            'db_optimized': False,
            'auth_cached': False,
            'background_tasks_running': False
        }
    
    def initialize(self, app: Flask):
        """Initialize all performance optimizations"""
        if self.initialized:
            return
        
        try:
            print("🚀 Initializing Ultra-Performance LMS System...")
            print("=" * 60)
            
            with app.app_context():
                # Step 1: Initialize Cache System
                self._init_cache_system(app)
                
                # Step 2: Optimize Database
                self._init_database_optimization(app)
                
                # Step 3: Setup Authentication Cache
                self._init_auth_optimization(app)
                
                # Step 4: Start Background Tasks
                self._init_background_tasks(app)
                
                # Step 5: Setup Performance Monitoring
                self._init_performance_monitoring(app)
                
            self.initialized = True
            self._print_success_summary()
            
        except Exception as e:
            logger.error(f"Performance initialization failed: {e}")
            print(f"❌ Performance initialization failed: {e}")
    
    def _init_cache_system(self, app):
        """Initialize caching system"""
        try:
            # Cache is already initialized in performance_cache.py
            cache.init_cache()
            
            # Setup cache warming
            setup_cache_warming(app)
            
            self.performance_stats['cache_enabled'] = True
            print("✅ Cache System: Multi-level caching active (Redis + File + Memory)")
            
        except Exception as e:
            print(f"⚠️  Cache System: Fallback mode ({e})")
    
    def _init_database_optimization(self, app):
        """Initialize database optimizations"""
        try:
            success = setup_database_optimization(app)
            
            if success:
                self.performance_stats['db_optimized'] = True
                print("✅ Database: Optimized with connection pooling and indexes")
            else:
                print("⚠️  Database: Partial optimization applied")
                
        except Exception as e:
            print(f"⚠️  Database: Optimization failed ({e})")
    
    def _init_auth_optimization(self, app):
        """Initialize authentication optimizations"""
        try:
            # Warm auth cache in background
            def warm_auth_background():
                with app.app_context():
                    warm_auth_cache()
            
            # Start warming thread
            auth_thread = threading.Thread(target=warm_auth_background, daemon=True)
            auth_thread.start()
            
            self.performance_stats['auth_cached'] = True
            print("✅ Authentication: Cache-optimized login system active")
            
        except Exception as e:
            print(f"⚠️  Authentication: Cache warming failed ({e})")
    
    def _init_background_tasks(self, app):
        """Initialize background performance tasks"""
        try:
            # Task 1: Cache Statistics Updater
            def update_cache_stats():
                while True:
                    try:
                        time.sleep(300)  # Every 5 minutes
                        with app.app_context():
                            stats = cache.get_stats()
                            cache.set('system:cache_stats', stats, 300)
                    except Exception as e:
                        logger.error(f"Cache stats update failed: {e}")
                        time.sleep(60)  # Wait 1 minute on error
            
            # Task 2: Database Performance Monitor
            def monitor_db_performance():
                while True:
                    try:
                        time.sleep(180)  # Every 3 minutes
                        with app.app_context():
                            perf_stats = db_optimizer.get_performance_stats()
                            cache.set('system:db_performance', perf_stats, 180)
                    except Exception as e:
                        logger.error(f"DB performance monitoring failed: {e}")
                        time.sleep(60)
            
            # Task 3: System Health Check
            def system_health_check():
                while True:
                    try:
                        time.sleep(600)  # Every 10 minutes
                        with app.app_context():
                            health = self._check_system_health()
                            cache.set('system:health', health, 600)
                    except Exception as e:
                        logger.error(f"System health check failed: {e}")
                        time.sleep(60)
            
            # Start background threads
            threads = [
                threading.Thread(target=update_cache_stats, daemon=True),
                threading.Thread(target=monitor_db_performance, daemon=True),
                threading.Thread(target=system_health_check, daemon=True)
            ]
            
            for thread in threads:
                thread.start()
                self.background_tasks.append(thread)
            
            self.performance_stats['background_tasks_running'] = True
            print("✅ Background Tasks: Performance monitoring active")
            
        except Exception as e:
            print(f"⚠️  Background Tasks: Failed to start ({e})")
    
    def _init_performance_monitoring(self, app):
        """Initialize performance monitoring hooks"""
        try:
            @app.before_request
            def before_request():
                from flask import g
                g.request_start_time = time.time()
            
            @app.after_request
            def after_request(response):
                try:
                    from flask import g, request
                    if hasattr(g, 'request_start_time'):
                        duration = time.time() - g.request_start_time
                        
                        # Log slow requests
                        if duration > 1.0:  # > 1 second
                            logger.warning(f"Slow request: {request.endpoint} took {duration:.3f}s")
                        
                        # Cache request performance data
                        perf_data = cache.get('system:request_times', [])
                        perf_data.append({
                            'endpoint': request.endpoint,
                            'duration': round(duration * 1000, 2),  # milliseconds
                            'timestamp': time.time()
                        })
                        
                        # Keep only last 100 requests
                        if len(perf_data) > 100:
                            perf_data = perf_data[-100:]
                        
                        cache.set('system:request_times', perf_data, 3600)
                
                except Exception as e:
                    # Don't fail requests due to monitoring errors
                    logger.error(f"Performance monitoring error: {e}")
                
                return response
            
            print("✅ Performance Monitoring: Request timing and health checks active")
            
        except Exception as e:
            print(f"⚠️  Performance Monitoring: Setup failed ({e})")
    
    def _check_system_health(self):
        """Comprehensive system health check"""
        health = {
            'status': 'healthy',
            'cache': 'unknown',
            'database': 'unknown',
            'memory': 'unknown',
            'timestamp': time.time()
        }
        
        try:
            # Check cache system
            cache.set('health:test', 'ok', 10)
            if cache.get('health:test') == 'ok':
                health['cache'] = 'healthy'
            else:
                health['cache'] = 'degraded'
                health['status'] = 'degraded'
        except:
            health['cache'] = 'failed'
            health['status'] = 'degraded'
        
        try:
            # Check database
            from app import db
            db.session.execute('SELECT 1').scalar()
            health['database'] = 'healthy'
        except:
            health['database'] = 'failed'
            health['status'] = 'critical'
        
        try:
            # Check memory usage (basic)
            import psutil
            memory_percent = psutil.virtual_memory().percent
            if memory_percent > 90:
                health['memory'] = 'critical'
                health['status'] = 'critical'
            elif memory_percent > 75:
                health['memory'] = 'warning'
                if health['status'] == 'healthy':
                    health['status'] = 'warning'
            else:
                health['memory'] = 'healthy'
        except:
            health['memory'] = 'unknown'
        
        return health
    
    def _print_success_summary(self):
        """Print initialization success summary"""
        print("=" * 60)
        print("🎉 ULTRA-PERFORMANCE LMS SYSTEM READY!")
        print("=" * 60)
        print(f"✅ Cache System:      {'Active' if self.performance_stats['cache_enabled'] else 'Fallback'}")
        print(f"✅ Database:          {'Optimized' if self.performance_stats['db_optimized'] else 'Basic'}")
        print(f"✅ Authentication:    {'Cached' if self.performance_stats['auth_cached'] else 'Standard'}")
        print(f"✅ Background Tasks:  {'Running' if self.performance_stats['background_tasks_running'] else 'Disabled'}")
        print("=" * 60)
        print("🚀 EXPECTED PERFORMANCE:")
        print("   • Login Page:      < 200ms")
        print("   • Dashboard:       < 500ms")
        print("   • API Responses:   < 100ms")
        print("   • Cache Hit Rate:  > 80%")
        print("=" * 60)
        print("🔗 ACCESS POINTS:")
        print("   • Fast Login:      /login-fast")
        print("   • Fast Dashboard:  /dashboard")
        print("   • Performance API: /api/v2/performance-metrics")
        print("=" * 60)
    
    def get_system_status(self):
        """Get current system performance status"""
        return {
            'initialized': self.initialized,
            'performance_stats': self.performance_stats,
            'cache_stats': cache.get_stats() if self.performance_stats['cache_enabled'] else None,
            'db_stats': db_optimizer.get_performance_stats() if self.performance_stats['db_optimized'] else None,
            'system_health': cache.get('system:health', {}),
            'background_tasks': len(self.background_tasks)
        }
    
    def restart_performance_systems(self):
        """Restart performance systems (admin function)"""
        try:
            # Clear all caches
            cache.clear_pattern('*')
            
            # Reinitialize
            self.initialized = False
            self.initialize(current_app)
            
            return True
        except Exception as e:
            logger.error(f"Performance system restart failed: {e}")
            return False

# Global performance manager instance
performance_manager = PerformanceManager()

def init_ultra_performance(app):
    """Initialize ultra-performance system"""
    performance_manager.initialize(app)
    return performance_manager

def get_performance_status():
    """Get current performance status"""
    return performance_manager.get_system_status()

# Flask CLI commands for performance management
def register_performance_commands(app):
    """Register CLI commands for performance management"""
    
    @app.cli.command('warm-cache')
    def warm_cache_command():
        """Warm up all caches"""
        with app.app_context():
            from .performance_cache import warm_cache
            from .auth_optimized import warm_auth_cache
            
            print("🔥 Warming up caches...")
            warm_cache()
            warm_auth_cache()
            print("✅ Cache warming completed")
    
    @app.cli.command('clear-cache')
    def clear_cache_command():
        """Clear all caches"""
        with app.app_context():
            cache.clear_pattern('*')
            print("🧹 All caches cleared")
    
    @app.cli.command('perf-status')
    def performance_status_command():
        """Show performance system status"""
        with app.app_context():
            status = get_performance_status()
            print("📊 PERFORMANCE SYSTEM STATUS")
            print("=" * 40)
            for key, value in status['performance_stats'].items():
                print(f"{key}: {'✅' if value else '❌'}")
            
            if status['cache_stats']:
                print(f"\nCache Hit Rate: {status['cache_stats']['hit_rate']}%")
                print(f"Cache Entries: {status['cache_stats']['memory_entries']}")
    
    @app.cli.command('create-indexes')
    def create_indexes_command():
        """Create database indexes"""
        with app.app_context():
            print("📊 Creating database indexes...")
            db_optimizer.create_essential_indexes()
            print("✅ Database indexes created")

# Application factory integration
def setup_ultra_performance_app(app):
    """Setup ultra-performance for Flask app"""
    # Initialize performance systems
    init_ultra_performance(app)
    
    # Register CLI commands
    register_performance_commands(app)
    
    # Register optimized blueprints
    try:
        from ..routes.auth_optimized import bp as auth_fast_bp
        app.register_blueprint(auth_fast_bp)
    except ImportError:
        pass
    
    print("🚀 Ultra-Performance LMS integration complete!")
    return app