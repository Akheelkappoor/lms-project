from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from sqlalchemy import or_, and_
import json
import traceback
from app import db
from app.models.user import User
from app.models.department import Department
from app.models.student import Student
from app.models.tutor import Tutor
from app.models.escalation import Escalation
from functools import wraps
from flask_wtf.csrf import generate_csrf

bp = Blueprint('escalation', __name__, url_prefix='/escalations')

def admin_required(f):
    """Decorator to require admin access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role not in ['superadmin', 'admin', 'coordinator']:
            flash('Access denied. Insufficient permissions.', 'error')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated_function

@bp.route('/')
@login_required
def list_escalations():
    """List all escalations - accessible to all authenticated users"""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    category_filter = request.args.get('category', '')
    priority_filter = request.args.get('priority', '')
    assigned_filter = request.args.get('assigned', '')
    search = request.args.get('search', '')
    
    # Base query
    query = Escalation.query
    
    # Department filter for coordinators
    if current_user.role == 'coordinator':
        query = query.filter_by(department_id=current_user.department_id)
    
    # Apply filters
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    if category_filter:
        query = query.filter_by(category=category_filter)
    
    if priority_filter:
        query = query.filter_by(priority=priority_filter)
    
    if assigned_filter == 'mine':
        query = query.filter_by(assigned_to=current_user.id)
    elif assigned_filter == 'unassigned':
        query = query.filter_by(assigned_to=None)
    
    if search:
        query = query.filter(
            or_(
                Escalation.title.contains(search),
                Escalation.description.contains(search)
            )
        )
    
    # Order by priority and creation date
    escalations = query.order_by(
        Escalation.priority.desc(),
        Escalation.created_at.desc()
    ).paginate(
        page=page, per_page=20, error_out=False
    )
    
    # Get statistics
    dept_id = current_user.department_id if current_user.role == 'coordinator' else None
    stats = Escalation.get_stats(dept_id)
    
    # Get filter options
    categories = Escalation.get_categories()
    priorities = Escalation.get_priorities()
    statuses = Escalation.get_statuses()
    
    # Get users for assignment dropdown
    users_query = User.query.filter_by(is_active=True)
    if current_user.role == 'coordinator':
        users_query = users_query.filter_by(department_id=current_user.department_id)
    users = users_query.all()
    
    print(f"DEBUG: User {current_user.full_name} ({current_user.role}) viewing {escalations.total} escalations")
    
    return render_template('escalation/list.html',
                         escalations=escalations,
                         stats=stats,
                         categories=categories,
                         priorities=priorities,
                         statuses=statuses,
                         users=users,
                         filters={
                             'status': status_filter,
                             'category': category_filter,
                             'priority': priority_filter,
                             'assigned': assigned_filter,
                             'search': search
                         })

@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_escalation():
    """Create new escalation - accessible to all authenticated users"""
    if request.method == 'POST':
        try:
            # Get form data
            title = request.form.get('title', '').strip()
            description = request.form.get('description', '').strip()
            category = request.form.get('category')
            priority = request.form.get('priority', 'medium')
            
            # Validation
            if not title or not description or not category:
                flash('Title, description, and category are required.', 'error')
                return redirect(url_for('escalation.create_escalation'))
            
            # Related records
            related_data = {}
            if request.form.get('student_id'):
                related_data['student_id'] = int(request.form.get('student_id'))
            if request.form.get('tutor_id'):
                related_data['tutor_id'] = int(request.form.get('tutor_id'))
            
            # Create escalation
            escalation = Escalation(
                title=title,
                description=description,
                category=category,
                priority=priority,
                created_by=current_user.id,
                department_id=current_user.department_id
            )
            
            # Set related records
            if related_data:
                escalation.set_related_records(related_data)
            
            # Calculate due date
            escalation.calculate_due_date()
            
            # Auto-assign based on category and department (if rules exist)
            auto_assignee = get_auto_assignee(category, current_user.department_id)
            if auto_assignee:
                escalation.assign_to_user(auto_assignee.id, current_user.id)
            
            db.session.add(escalation)
            db.session.commit()
            
            flash(f'Escalation "{title}" created successfully!', 'success')
            return redirect(url_for('escalation.view_escalation', id=escalation.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating escalation: {str(e)}', 'error')
            import traceback
            print(f"Error creating escalation: {traceback.format_exc()}")
    
    # GET request - show form
    categories = Escalation.get_categories()
    priorities = Escalation.get_priorities()
    
    # Get students and tutors based on user role and department
    students = []
    tutors = []
    
    try:
        # Superadmin and Admin can see all
        if current_user.role in ['superadmin', 'admin']:
            print(f"DEBUG: Loading all students/tutors for {current_user.role}")
            students = Student.query.filter_by(is_active=True).limit(100).all()
            tutors = Tutor.query.filter_by(status='active').limit(100).all()
            
        # Coordinator can see only their department
        elif current_user.role == 'coordinator' and current_user.department_id:
            print(f"DEBUG: Loading dept {current_user.department_id} students/tutors for coordinator")
            students = Student.query.filter_by(
                department_id=current_user.department_id, 
                is_active=True
            ).all()
            
            # Get tutors from coordinator's department
            tutors = db.session.query(Tutor).join(User).filter(
                User.department_id == current_user.department_id,
                Tutor.status == 'active'
            ).all()
            
        # Regular users (like tutors) can see their department
        elif current_user.department_id:
            print(f"DEBUG: Loading dept {current_user.department_id} students/tutors for {current_user.role}")
            students = Student.query.filter_by(
                department_id=current_user.department_id, 
                is_active=True
            ).all()
            
            tutors = db.session.query(Tutor).join(User).filter(
                User.department_id == current_user.department_id,
                Tutor.status == 'active'
            ).all()
        
        print(f"DEBUG: User {current_user.full_name} ({current_user.role}) found {len(students)} students and {len(tutors)} tutors")
        
        # Debug first few items
        if students:
            print(f"DEBUG: First student: {students[0].full_name} (Dept: {students[0].department_id})")
        if tutors:
            tutor_name = tutors[0].user.full_name if tutors[0].user else 'No User'
            tutor_dept = tutors[0].user.department_id if tutors[0].user else 'No Dept'
            print(f"DEBUG: First tutor: {tutor_name} (Dept: {tutor_dept})")
        
    except Exception as e:
        print(f"DEBUG: Error loading students/tutors: {str(e)}")
        import traceback
        print(f"DEBUG: Traceback: {traceback.format_exc()}")
        students = []
        tutors = []
    
    return render_template('escalation/create.html',
                         categories=categories,
                         priorities=priorities,
                         students=students,
                         tutors=tutors)

@bp.route('/<int:id>')
@login_required
def view_escalation(id):
    """View escalation details"""
    escalation = Escalation.query.get_or_404(id)
    
    # Check access
    if current_user.role == 'coordinator' and escalation.department_id != current_user.department_id:
        flash('Access denied. You can only view escalations from your department.', 'error')
        return redirect(url_for('escalation.list_escalations'))
    
    # Get related records
    related_records = escalation.get_related_records()
    student = None
    tutor = None
    
    if 'student_id' in related_records:
        student = Student.query.get(related_records['student_id'])
    if 'tutor_id' in related_records:
        tutor = Tutor.query.get(related_records['tutor_id'])
    
    # Get comments
    comments = escalation.get_comments()
    
    # Add user info to comments
    for comment in comments:
        user = User.query.get(comment['user_id'])
        comment['user_name'] = user.full_name if user else 'Unknown User'
    
    # Get users for assignment
    users_query = User.query.filter_by(is_active=True)
    if current_user.role == 'coordinator':
        users_query = users_query.filter_by(department_id=current_user.department_id)
    users = users_query.all()
    
    return render_template('escalation/view.html',
                         escalation=escalation,
                         student=student,
                         tutor=tutor,
                         comments=comments,
                         users=users,
                         priorities=Escalation.get_priorities(),
                         statuses=Escalation.get_statuses(),
                         csrf_token=generate_csrf)

@bp.route('/<int:id>/assign', methods=['POST'])
@login_required
@admin_required
def assign_escalation(id):
    """Assign escalation to user"""
    escalation = Escalation.query.get_or_404(id)
    
    # Check access
    if current_user.role == 'coordinator' and escalation.department_id != current_user.department_id:
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        user_id = request.json.get('user_id')
        if not user_id:
            return jsonify({'error': 'User ID is required'}), 400
        
        # Verify user exists and is in same department (for coordinators)
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        if current_user.role == 'coordinator' and user.department_id != current_user.department_id:
            return jsonify({'error': 'Can only assign to users in your department'}), 403
        
        escalation.assign_to_user(user_id, current_user.id)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Escalation assigned to {user.full_name}',
            'assigned_to': user.full_name,
            'status': escalation.status
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error assigning escalation: {str(e)}'}), 500

@bp.route('/<int:id>/update-status', methods=['POST'])
@login_required
def update_status(id):
    """Update escalation status"""
    escalation = Escalation.query.get_or_404(id)
    
    # Check access - only assigned user or admin can update
    if (escalation.assigned_to != current_user.id and 
        current_user.role not in ['superadmin', 'admin'] and
        (current_user.role == 'coordinator' and escalation.department_id != current_user.department_id)):
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        new_status = request.json.get('status')
        if new_status not in [s[0] for s in Escalation.get_statuses()]:
            return jsonify({'error': 'Invalid status'}), 400
        
        escalation.status = new_status
        escalation.updated_at = datetime.utcnow()
        escalation.add_comment(current_user.id, f"Status changed to {new_status}")
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Status updated to {new_status}',
            'status': new_status
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error updating status: {str(e)}'}), 500

@bp.route('/<int:id>/add-comment', methods=['POST'])
@login_required
def add_comment(id):
    """Add comment to escalation"""
    escalation = Escalation.query.get_or_404(id)
    
    # Check access
    if (current_user.role == 'coordinator' and 
        escalation.department_id != current_user.department_id):
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        comment = request.json.get('comment', '').strip()
        if not comment:
            return jsonify({'error': 'Comment cannot be empty'}), 400
        
        escalation.add_comment(current_user.id, comment)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Comment added successfully',
            'comment': {
                'user_name': current_user.full_name,
                'comment': comment,
                'timestamp': datetime.utcnow().isoformat()
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error adding comment: {str(e)}'}), 500

@bp.route('/<int:id>/resolve', methods=['POST'])
@login_required
def resolve_escalation(id):
    """Resolve escalation"""
    escalation = Escalation.query.get_or_404(id)
    
    # Check access - only assigned user or admin
    if (escalation.assigned_to != current_user.id and 
        current_user.role not in ['superadmin', 'admin'] and
        (current_user.role == 'coordinator' and escalation.department_id != current_user.department_id)):
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        resolution = request.json.get('resolution', '').strip()
        if not resolution:
            return jsonify({'error': 'Resolution description is required'}), 400
        
        escalation.resolve(resolution, current_user.id)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Escalation resolved successfully',
            'status': escalation.status,
            'resolution_date': escalation.resolution_date.isoformat() if escalation.resolution_date else None
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error resolving escalation: {str(e)}'}), 500

@bp.route('/<int:id>/close', methods=['POST'])
@login_required
@admin_required
def close_escalation(id):
    """Close escalation"""
    escalation = Escalation.query.get_or_404(id)
    
    # Check access
    if current_user.role == 'coordinator' and escalation.department_id != current_user.department_id:
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        escalation.close(current_user.id)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Escalation closed successfully',
            'status': escalation.status
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error closing escalation: {str(e)}'}), 500

@bp.route('/dashboard-stats')
@login_required
def dashboard_stats():
    """Get escalation stats for dashboard widget"""
    dept_id = current_user.department_id if current_user.role == 'coordinator' else None
    stats = Escalation.get_stats(dept_id)
    
    # Get recent escalations
    query = Escalation.query
    if dept_id:
        query = query.filter_by(department_id=dept_id)
    
    recent = query.order_by(Escalation.created_at.desc()).limit(5).all()
    
    # Get overdue escalations
    overdue = Escalation.get_overdue()
    if dept_id:
        overdue = [e for e in overdue if e.department_id == dept_id]
    
    return jsonify({
        'stats': stats,
        'recent': [{
            'id': e.id,
            'title': e.title,
            'category': e.category,
            'priority': e.priority,
            'status': e.status,
            'created_at': e.created_at.isoformat(),
            'is_overdue': e.is_overdue()
        } for e in recent],
        'overdue': [{
            'id': e.id,
            'title': e.title,
            'priority': e.priority,
            'due_date': e.due_date.isoformat() if e.due_date else None
        } for e in overdue[:5]]
    })

def get_auto_assignee(category, department_id):
    """Get auto-assignee based on category and department"""
    # You can implement auto-assignment rules here
    # For now, assign to department coordinator
    if category == 'technical':
        # Assign technical issues to admin
        return User.query.filter_by(role='admin', is_active=True).first()
    elif category == 'academic':
        # Assign to department coordinator
        return User.query.filter_by(role='coordinator', department_id=department_id, is_active=True).first()
    elif category == 'payment':
        # Assign to admin for payment issues
        return User.query.filter_by(role='admin', is_active=True).first()
    
    return None

@bp.route('/test-data')
@login_required
def test_data():
    """Simple test to show available data"""
    try:
        students = Student.query.filter_by(is_active=True).limit(5).all()
        tutors = Tutor.query.filter_by(status='active').limit(5).all()
        
        output = f"""
        <h2>Test Data Available</h2>
        <h3>Current User:</h3>
        <p>Name: {current_user.full_name}</p>
        <p>Role: {current_user.role}</p>
        <p>Department ID: {current_user.department_id}</p>
        
        <h3>Students Found: {len(students)}</h3>
        <ul>
        """
        
        for student in students:
            output += f"<li>ID: {student.id}, Name: {student.full_name}, Dept: {student.department_id}</li>"
        
        output += f"""
        </ul>
        
        <h3>Tutors Found: {len(tutors)}</h3>
        <ul>
        """
        
        for tutor in tutors:
            dept_id = tutor.user.department_id if tutor.user else 'None'
            output += f"<li>ID: {tutor.id}, Name: {tutor.user.full_name if tutor.user else 'No User'}, Dept: {dept_id}, Status: {tutor.status}</li>"
        
        output += "</ul>"
        
        return output
        
    except Exception as e:
        return f"<h2>Error:</h2><pre>{str(e)}</pre>"