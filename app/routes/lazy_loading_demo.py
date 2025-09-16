# app/routes/lazy_loading_demo.py

from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
import json
from datetime import datetime
import time

lazy_demo_bp = Blueprint('lazy_demo', __name__, url_prefix='/lazy-demo')

@lazy_demo_bp.route('/')
@login_required
def index():
    """Lazy loading demo page"""
    return render_template('examples/lazy-loading-examples.html')

# API endpoints for lazy loading demos
@lazy_demo_bp.route('/api/students/list')
@login_required
def api_students_list():
    """Demo API for lazy table loading"""
    # Simulate loading delay
    time.sleep(1)
    
    return jsonify({
        'html': '''
        <table class="table table-hover">
            <thead>
                <tr>
                    <th>Name</th>
                    <th>Grade</th>
                    <th>Subject</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>John Doe</td>
                    <td>Grade 10</td>
                    <td>Mathematics</td>
                    <td><span class="badge bg-success">Active</span></td>
                </tr>
                <tr>
                    <td>Jane Smith</td>
                    <td>Grade 9</td>
                    <td>Science</td>
                    <td><span class="badge bg-success">Active</span></td>
                </tr>
                <tr>
                    <td>Mike Johnson</td>
                    <td>Grade 11</td>
                    <td>English</td>
                    <td><span class="badge bg-warning">Pending</span></td>
                </tr>
            </tbody>
        </table>
        '''
    })

@lazy_demo_bp.route('/api/classes/schedule')
@login_required
def api_classes_schedule():
    """Demo API for lazy table loading"""
    time.sleep(0.8)
    
    return jsonify({
        'html': '''
        <table class="table table-striped">
            <thead>
                <tr>
                    <th>Time</th>
                    <th>Subject</th>
                    <th>Tutor</th>
                    <th>Students</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>09:00 AM</td>
                    <td>Mathematics</td>
                    <td>Dr. Smith</td>
                    <td>5 students</td>
                </tr>
                <tr>
                    <td>10:30 AM</td>
                    <td>Physics</td>
                    <td>Prof. Johnson</td>
                    <td>3 students</td>
                </tr>
                <tr>
                    <td>02:00 PM</td>
                    <td>Chemistry</td>
                    <td>Dr. Brown</td>
                    <td>4 students</td>
                </tr>
            </tbody>
        </table>
        '''
    })

@lazy_demo_bp.route('/api/dashboard/stats')
@login_required
def api_dashboard_stats():
    """Demo API for lazy content loading"""
    time.sleep(1.2)
    
    return jsonify({
        'html': '''
        <div class="dashboard-stats">
            <div class="row">
                <div class="col-6">
                    <div class="stat-item">
                        <h6>Total Classes</h6>
                        <span class="stat-number">147</span>
                    </div>
                </div>
                <div class="col-6">
                    <div class="stat-item">
                        <h6>This Week</h6>
                        <span class="stat-number">23</span>
                    </div>
                </div>
                <div class="col-6">
                    <div class="stat-item">
                        <h6>Completed</h6>
                        <span class="stat-number text-success">134</span>
                    </div>
                </div>
                <div class="col-6">
                    <div class="stat-item">
                        <h6>Scheduled</h6>
                        <span class="stat-number text-primary">13</span>
                    </div>
                </div>
            </div>
        </div>
        <style>
        .stat-item { text-align: center; padding: 0.5rem; }
        .stat-number { font-size: 1.5rem; font-weight: 600; }
        </style>
        '''
    })

@lazy_demo_bp.route('/api/notices/recent')
@login_required
def api_notices_recent():
    """Demo API for lazy content loading"""
    time.sleep(0.9)
    
    return jsonify({
        'html': '''
        <div class="notices-list">
            <div class="notice-item">
                <div class="notice-title">Holiday Notice</div>
                <div class="notice-date">Aug 12, 2025</div>
                <div class="notice-excerpt">Classes will be suspended...</div>
            </div>
            <div class="notice-item">
                <div class="notice-title">New Course Available</div>
                <div class="notice-date">Aug 10, 2025</div>
                <div class="notice-excerpt">Advanced Mathematics course...</div>
            </div>
            <div class="notice-item">
                <div class="notice-title">System Maintenance</div>
                <div class="notice-date">Aug 8, 2025</div>
                <div class="notice-excerpt">Scheduled maintenance window...</div>
            </div>
        </div>
        <style>
        .notice-item { 
            padding: 0.75rem; 
            border-bottom: 1px solid #e9ecef; 
            margin-bottom: 0.5rem; 
        }
        .notice-title { 
            font-weight: 600; 
            color: var(--primary-color); 
        }
        .notice-date { 
            font-size: 0.8rem; 
            color: #6c757d; 
            margin: 0.25rem 0; 
        }
        .notice-excerpt { 
            font-size: 0.9rem; 
        }
        </style>
        '''
    })

@lazy_demo_bp.route('/api/classes/upcoming')
@login_required
def api_classes_upcoming():
    """Demo API for lazy content loading"""
    time.sleep(1.1)
    
    return jsonify({
        'html': '''
        <div class="upcoming-classes">
            <div class="class-item">
                <div class="class-time">
                    <i class="fas fa-clock"></i>
                    Today, 3:00 PM
                </div>
                <div class="class-subject">Mathematics - Grade 10</div>
                <div class="class-tutor">with Dr. Smith</div>
            </div>
            <div class="class-item">
                <div class="class-time">
                    <i class="fas fa-clock"></i>
                    Tomorrow, 10:00 AM
                </div>
                <div class="class-subject">Physics - Grade 11</div>
                <div class="class-tutor">with Prof. Johnson</div>
            </div>
            <div class="class-item">
                <div class="class-time">
                    <i class="fas fa-clock"></i>
                    Tomorrow, 2:00 PM
                </div>
                <div class="class-subject">Chemistry - Grade 9</div>
                <div class="class-tutor">with Dr. Brown</div>
            </div>
        </div>
        <style>
        .class-item { 
            padding: 0.75rem; 
            background: #f8f9fa; 
            border-radius: 6px; 
            margin-bottom: 0.5rem; 
        }
        .class-time { 
            color: var(--primary-color); 
            font-size: 0.9rem; 
            margin-bottom: 0.25rem; 
        }
        .class-subject { 
            font-weight: 600; 
            margin-bottom: 0.25rem; 
        }
        .class-tutor { 
            font-size: 0.85rem; 
            color: #6c757d; 
        }
        </style>
        '''
    })

# API Data endpoints
@lazy_demo_bp.route('/api/stats/students/count')
@login_required
def api_stats_students_count():
    """Demo API for count data"""
    time.sleep(0.5)
    return jsonify({'count': 247})

@lazy_demo_bp.route('/api/stats/classes/active')
@login_required
def api_stats_classes_active():
    """Demo API for count data"""
    time.sleep(0.6)
    return jsonify({'count': 18})

@lazy_demo_bp.route('/api/stats/tutors/online')
@login_required
def api_stats_tutors_online():
    """Demo API for count data"""
    time.sleep(0.4)
    return jsonify({'count': 12})

@lazy_demo_bp.route('/api/stats/requests/pending')
@login_required
def api_stats_requests_pending():
    """Demo API for count data"""
    time.sleep(0.7)
    return jsonify({'count': 5})

# Auto-refresh endpoints
@lazy_demo_bp.route('/api/time/current')
@login_required
def api_time_current():
    """Demo API for auto-refresh data"""
    return jsonify({'text': datetime.now().strftime('%H:%M:%S')})

@lazy_demo_bp.route('/api/system/status')
@login_required
def api_system_status():
    """Demo API for auto-refresh data"""
    import random
    statuses = ['🟢 Online', '🟡 Maintenance', '🔴 Offline']
    return jsonify({'text': random.choice(statuses)})

@lazy_demo_bp.route('/api/users/active')
@login_required
def api_users_active():
    """Demo API for auto-refresh data"""
    import random
    count = random.randint(50, 150)
    return jsonify({'text': f'{count} users'})

# Form submission endpoint
@lazy_demo_bp.route('/api/test/form', methods=['POST'])
@login_required
def api_test_form():
    """Demo API for form submission"""
    # Simulate processing time
    time.sleep(2)
    
    # Get form data
    name = request.form.get('name')
    email = request.form.get('email')
    message = request.form.get('message')
    
    # Simulate validation
    if not name or not email or not message:
        return jsonify({
            'success': False,
            'message': 'All fields are required'
        }), 400
    
    return jsonify({
        'success': True,
        'message': f'Form submitted successfully! Thank you, {name}.',
        'redirect': None  # Could redirect somewhere if needed
    })