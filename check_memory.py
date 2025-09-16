#!/usr/bin/env python3
"""
Memory Usage Monitor for LMS
Run this to check what's consuming memory
"""

import psutil
import time
import os

def check_system_resources():
    """Check current system resource usage"""
    
    print("=" * 60)
    print("LMS SYSTEM RESOURCE MONITOR")
    print("=" * 60)
    
    # System Memory
    memory = psutil.virtual_memory()
    print(f"💾 MEMORY USAGE:")
    print(f"   Total: {memory.total / 1024 / 1024 / 1024:.1f} GB")
    print(f"   Available: {memory.available / 1024 / 1024 / 1024:.1f} GB")
    print(f"   Used: {memory.used / 1024 / 1024 / 1024:.1f} GB ({memory.percent:.1f}%)")
    print()
    
    # CPU Usage
    cpu_percent = psutil.cpu_percent(interval=1)
    print(f"🔥 CPU USAGE: {cpu_percent:.1f}%")
    print()
    
    # Disk Usage
    disk = psutil.disk_usage('/')
    print(f"💿 DISK USAGE:")
    print(f"   Total: {disk.total / 1024 / 1024 / 1024:.1f} GB")
    print(f"   Used: {disk.used / 1024 / 1024 / 1024:.1f} GB ({disk.used/disk.total*100:.1f}%)")
    print(f"   Free: {disk.free / 1024 / 1024 / 1024:.1f} GB")
    print()
    
    # Top Memory Consumers
    print("🔍 TOP 15 MEMORY CONSUMERS:")
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'cpu_percent']):
        try:
            memory_mb = proc.info['memory_info'].rss / 1024 / 1024
            if memory_mb > 10:  # Only show processes using more than 10MB
                processes.append((memory_mb, proc.info['pid'], proc.info['name'], proc.info['cpu_percent']))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    # Sort by memory usage
    processes.sort(reverse=True)
    for i, (memory_mb, pid, name, cpu) in enumerate(processes[:15]):
        print(f"   {i+1:2d}. {memory_mb:>8.1f} MB - {name:<20} (PID {pid}) - {cpu:>5.1f}% CPU")
    
    print()
    
    # Network Connections
    try:
        connections = psutil.net_connections(kind='tcp')
        listening = [c for c in connections if c.status == 'LISTEN']
        established = [c for c in connections if c.status == 'ESTABLISHED']
        
        print(f"🌐 NETWORK CONNECTIONS:")
        print(f"   Listening: {len(listening)}")
        print(f"   Established: {len(established)}")
        print()
    except psutil.AccessDenied:
        print("🌐 NETWORK: Access denied (run as administrator for details)")
        print()

def check_lms_specific():
    """Check LMS-specific processes and files"""
    
    print("🚀 LMS-SPECIFIC CHECKS:")
    
    # Check for Python/Flask processes
    python_procs = []
    for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'cmdline']):
        try:
            if 'python' in proc.info['name'].lower():
                memory_mb = proc.info['memory_info'].rss / 1024 / 1024
                cmdline = ' '.join(proc.info['cmdline'][:3]) if proc.info['cmdline'] else 'N/A'
                python_procs.append((memory_mb, proc.info['pid'], cmdline))
        except:
            pass
    
    if python_procs:
        print("   Python Processes:")
        for memory_mb, pid, cmdline in sorted(python_procs, reverse=True):
            print(f"     {memory_mb:>6.1f} MB - PID {pid} - {cmdline}")
    else:
        print("   No Python processes found")
    
    print()
    
    # Check database file size
    db_path = os.path.join(os.getcwd(), 'app.db')
    if os.path.exists(db_path):
        db_size_mb = os.path.getsize(db_path) / 1024 / 1024
        print(f"   Database Size: {db_size_mb:.1f} MB")
    else:
        print("   Database: Not found (using external DB?)")
    
    print()

def suggest_optimizations(memory_percent):
    """Suggest optimizations based on memory usage"""
    
    print("💡 OPTIMIZATION SUGGESTIONS:")
    
    if memory_percent > 85:
        print("   ⚠️  CRITICAL: Very high memory usage!")
        print("   - Close unnecessary applications")
        print("   - Restart the system if possible")
        print("   - Consider adding more RAM")
    elif memory_percent > 70:
        print("   ⚠️  WARNING: High memory usage")
        print("   - Close browser tabs you don't need")
        print("   - Close VS Code if not actively coding")
        print("   - Stop Docker containers if not needed")
    else:
        print("   ✅ Memory usage is acceptable")
    
    print("   - For LMS optimization:")
    print("     * Database connection pooling enabled")
    print("     * Limit error log queries")
    print("     * Clear browser cache")
    print("     * Use pagination for large data sets")
    print()

if __name__ == "__main__":
    try:
        check_system_resources()
        check_lms_specific()
        
        memory_percent = psutil.virtual_memory().percent
        suggest_optimizations(memory_percent)
        
        print("=" * 60)
        print("Monitor completed. Run again to track changes.")
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\nMonitoring cancelled by user")
    except Exception as e:
        print(f"Error during monitoring: {e}")