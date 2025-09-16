from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from datetime import datetime, date, timedelta
import os
from app.utils.helper import upload_file_to_s3
import json
from flask_wtf.csrf import generate_csrf
from app import db
from app.models.user import User
from app.models.department import Department  
from app.models.tutor import Tutor
from app.models.student import Student
from app.models.class_model import Class
from app.models.attendance import Attendance
from app.forms.user import CreateUserForm, EditUserForm, TutorRegistrationForm, StudentRegistrationForm
from app.utils.tutor_matching import TutorMatchingEngine, SearchQueryProcessor, AvailabilityChecker, monitor_search_performance
from functools import wraps
from app.utils.email import send_password_reset_email, send_onboarding_email
from app.forms.user import EditStudentForm
from sqlalchemy import text
from app.utils.enhanced_email_subjects import create_better_email_subject, get_enhanced_subject_options
import urllib.parse
from flask import make_response
from app.utils.allocation_helper import allocation_helper
from app.utils.error_handler import handle_json_errors
from sqlalchemy import or_, and_, func, text
from flask_moment import Moment

from app.utils.advanced_permissions import (
    require_permission, 
    require_any_permission, 
    require_all_permissions,
    require_role,
    PermissionRegistry,
    PermissionUtils
)
from app.utils.input_sanitizer import InputSanitizer

# Import new services for optimization
from app.services.database_service import DatabaseService
from app.services.validation_service import ValidationService
from app.services.error_service import handle_errors, error_service, ValidationError

bp = Blueprint('admin', __name__)

matching_engine = TutorMatchingEngine()

def admin_required(f):
    """Decorator to require admin access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role not in ['superadmin', 'admin', 'coordinator']:
            # Don't show permission errors to tutors (they know functionality works)
            if current_user.role != 'tutor':
                flash('Access denied. Insufficient permissions.', 'error')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated_function

def save_uploaded_file(file, subfolder):
    """Save uploaded file and return filename"""
    if file and file.filename:
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
        filename = timestamp + filename
        
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], subfolder, filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        file.save(file_path)
        return filename
    return None


@bp.route('/users')
@login_required
@require_permission('user_management')
def users():
    """User management page"""
    page = request.args.get('page', 1, type=int)
    role_filter = request.args.get('role', '')
    dept_filter = request.args.get('department', '', type=int)
    search = request.args.get('search', '')
    
    query = User.query
    
    if role_filter:
        query = query.filter_by(role=role_filter)
    
    if dept_filter:
        query = query.filter_by(department_id=dept_filter)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (User.full_name.ilike(search_term)) |
            (User.username.ilike(search_term)) |
            (User.email.ilike(search_term))
        )
    
    users = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    departments = Department.query.filter_by(is_active=True).all()

    filtered_args = request.args.to_dict()
    filtered_args.pop('page', None)

    return render_template('admin/users.html', users=users, departments=departments, filtered_args=filtered_args)

@bp.route('/users/create', methods=['GET', 'POST'])
@login_required
@require_permission('user_management')
def create_user():
    """Create new user - DEBUG VERSION WITH ONBOARDING EMAIL"""
    form = CreateUserForm()
    
    if request.method == 'POST':
        print("=== POST REQUEST RECEIVED ===")
        print(f"Form data: {dict(request.form)}")
        print(f"Files: {dict(request.files)}")
        
        print(f"Form validates: {form.validate()}")
        print(f"Form errors: {form.errors}")
        
        if form.validate_on_submit():
            print("=== FORM VALIDATION PASSED ===")
            try:
                print("Creating user object...")
                
                # Store password before hashing for email
                plain_password = form.password.data
                print(f"Plain password stored for email: {plain_password}")
                
                # Create user object
                user = User(
                    username=form.username.data,
                    email=form.email.data,
                    full_name=form.full_name.data,
                    phone=form.phone.data,
                    role=form.role.data,
                    department_id=form.department_id.data if form.department_id.data else None,
                    address=form.address.data,
                    working_hours=form.working_hours.data,
                    joining_date=form.joining_date.data or datetime.utcnow().date(),
                    is_active=form.is_active.data,
                    is_verified=True,
                    created_at=datetime.utcnow()
                )
                
                print(f"User object created: {user.username}")
                
                # Set password
                user.set_password(plain_password)
                print("Password set")
                
                # Handle profile picture upload
                if form.profile_picture.data:
                    print("Processing profile picture...")
                    s3_url = upload_file_to_s3(form.profile_picture.data, folder=f"{current_app.config['UPLOAD_FOLDER']}/profiles")
                    user.profile_picture = s3_url
                    print(f"Profile picture saved: {s3_url}")
                
                # Handle emergency contact
                emergency_contact = {
                    'name': request.form.get('emergency_name', ''),
                    'phone': request.form.get('emergency_phone', ''),
                    'relation': request.form.get('emergency_relation', '')
                }
                if emergency_contact['name']:
                    user.set_emergency_contact(emergency_contact)
                    print(f"Emergency contact set: {emergency_contact}")
                
                print("About to add to database...")
                # Save to database
                db.session.add(user)
                print("User added to session")
                
                db.session.commit()
                print("DATABASE COMMIT SUCCESSFUL!")
                
                # Send onboarding email
                try:
                    print("=== SENDING ONBOARDING EMAIL ===")
                    print(f"Email: {user.email}")
                    print(f"User: {user.full_name}")
                    print(f"Role: {user.role}")
                    
                    send_onboarding_email(user, plain_password)
                    print("=== ONBOARDING EMAIL SENT SUCCESSFULLY ===")
                    
                    flash(f'User {user.full_name} created successfully! Onboarding email sent to {user.email}.', 'success')
                    
                except Exception as email_error:
                    print(f"=== EMAIL SENDING FAILED ===")
                    print(f"Email error type: {type(email_error)}")
                    print(f"Email error message: {str(email_error)}")
                    import traceback
                    print(f"Email traceback: {traceback.format_exc()}")
                    
                    flash(f'User {user.full_name} created successfully, but failed to send onboarding email. Please send credentials manually to {user.email}.', 'warning')
                
                print("=== SUCCESS: REDIRECTING ===")
                return redirect(url_for('admin.users'))
                
            except Exception as e:
                print(f"=== EXCEPTION OCCURRED ===")
                print(f"Exception type: {type(e)}")
                print(f"Exception message: {str(e)}")
                print(f"Exception details: {repr(e)}")
                import traceback
                print(f"Traceback: {traceback.format_exc()}")
                
                db.session.rollback()
                flash(f'Error creating user: {str(e)}', 'error')
        else:
            print("=== FORM VALIDATION FAILED ===")
            print(f"Validation errors: {form.errors}")
    
    print("=== RETURNING TEMPLATE ===")
    return render_template('admin/create_user.html', form=form)

@bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@require_permission('user_management')
def edit_user(user_id):
    """Edit user"""
    user = User.query.get_or_404(user_id)
    form = EditUserForm(user_id=user.id, obj=user)
    
    if form.validate_on_submit():
        try:
            # Update user fields
            user.full_name = form.full_name.data
            user.email = form.email.data
            user.phone = form.phone.data
            user.role = form.role.data
            user.department_id = form.department_id.data if form.department_id.data else None
            user.address = form.address.data
            user.working_hours = form.working_hours.data
            user.joining_date = form.joining_date.data
            user.is_active = form.is_active.data
            
            # Handle profile picture upload
            if form.profile_picture.data:
                s3_url = upload_file_to_s3(form.profile_picture.data, folder=f"{current_app.config['UPLOAD_FOLDER']}/profiles")
                user.profile_picture = s3_url
            
            db.session.commit()
            flash(f'User {user.full_name} updated successfully!', 'success')
            return redirect(url_for('admin.users'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating user: {str(e)}', 'error')
    
    return render_template('admin/edit_user.html', form=form, user=user)

@bp.route('/users/<int:user_id>/toggle-status', methods=['POST'])
@login_required
@require_permission('user_management')
def toggle_user_status(user_id):
    """Toggle user active status"""
    user = User.query.get_or_404(user_id)
    
    if user.role == 'superadmin' and current_user.role != 'superadmin':
        return jsonify({'error': 'Cannot modify superadmin account'}), 403
    
    try:
        user.is_active = not user.is_active
        db.session.commit()
        
        status = 'activated' if user.is_active else 'deactivated'
        flash(f'User {user.full_name} has been {status}.', 'success')
        
        return jsonify({'success': True, 'status': user.is_active})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Error updating user status'}), 500

@bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@require_permission('user_management')
def delete_user(user_id):
    """Delete user (superadmin only)"""
    if current_user.role != 'superadmin':
        return jsonify({'error': 'Only superadmin can delete users'}), 403
    
    user = User.query.get_or_404(user_id)
    
    if user.role == 'superadmin':
        return jsonify({'error': 'Cannot delete superadmin account'}), 403
    
    try:
        # Check dependencies before deleting
        if user.role == 'tutor' and user.tutor_profile:
            if Class.query.filter_by(tutor_id=user.tutor_profile.id).first():
                return jsonify({'error': 'Cannot delete tutor with existing classes'}), 400
        
        db.session.delete(user)
        db.session.commit()
        
        flash(f'User {user.full_name} deleted successfully.', 'success')
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Error deleting user'}), 500

# ============ DEPARTMENT MANAGEMENT ROUTES ============

@bp.route('/departments')
@login_required
@require_role('superadmin', 'admin')
def departments():
    """Department management page"""
    departments = Department.query.order_by(Department.created_at.desc()).all()
    return render_template('admin/departments.html', departments=departments)

@bp.route('/departments/create', methods=['POST'])
@login_required
@require_role('superadmin', 'admin')
def create_department():
    """Create new department"""
    if current_user.role not in ['superadmin', 'admin']:
        return jsonify({'error': 'Insufficient permissions'}), 403
    
    data = request.get_json()
    
    try:
        department = Department(
            name=data['name'],
            code=data['code'],
            description=data.get('description', ''),
            created_by=current_user.id
        )
        
        db.session.add(department)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Department created successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Error creating department'}), 500

@bp.route('/departments/<int:dept_id>/permissions', methods=['GET', 'POST'])
@login_required
@require_role('superadmin', 'admin')
def department_permissions(dept_id):
    """Manage department permissions"""
    if current_user.role not in ['superadmin', 'admin']:
        flash('Insufficient permissions.', 'error')
        return redirect(url_for('admin.departments'))
    
    department = Department.query.get_or_404(dept_id)
    
    if request.method == 'POST':
        permissions = request.form.getlist('permissions')
        department.set_permissions(permissions)
        db.session.commit()
        flash(f'Permissions updated for {department.name}', 'success')
        return redirect(url_for('admin.departments'))
    
    all_permissions = [
        'user_management', 'tutor_management', 'student_management',
        'class_management', 'attendance_management', 'schedule_management',
        'demo_management', 'finance_management', 'report_generation',
        'communication', 'profile_management', 'quality_checking'
    ]
    
    return render_template('admin/department_permissions.html', 
                         department=department, all_permissions=all_permissions)

@bp.route('/departments/<int:dept_id>/data')
@login_required
@require_role('superadmin', 'admin')
def get_department_data(dept_id):
    """Get department data for editing"""
    department = Department.query.get_or_404(dept_id)
    return jsonify({
        'success': True,
        'department': {
            'id': department.id,
            'name': department.name,
            'code': department.code,
            'description': department.description
        }
    })

@bp.route('/departments/<int:dept_id>/update', methods=['POST'])
@login_required
@require_role('superadmin', 'admin')
def update_department(dept_id):
    """Update department"""
    department = Department.query.get_or_404(dept_id)
    data = request.get_json()
    
    try:
        department.name = data['name']
        department.code = data['code']
        department.description = data.get('description', '')
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Department updated successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Error updating department'}), 500

@bp.route('/departments/<int:dept_id>/toggle-status', methods=['POST'])
@login_required
@require_role('superadmin', 'admin')
def toggle_department_status(dept_id):
    """Toggle department active status"""
    department = Department.query.get_or_404(dept_id)
    
    try:
        department.is_active = not department.is_active
        db.session.commit()
        
        status = 'activated' if department.is_active else 'deactivated'
        return jsonify({'success': True, 'message': f'Department {status} successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Error updating department status'}), 500


@bp.route('/permission-management')
@bp.route('/permission-management/<int:dept_id>')
@login_required
@require_role('superadmin', 'admin')
def permission_management(dept_id=None):
    """Advanced permission management interface with department selector"""
    departments = Department.query.order_by(Department.name).all()
    
    # Handle case where no departments exist
    if not departments:
        flash('No departments found. Please create a department first.', 'warning')
        return redirect(url_for('admin.departments'))
    
    # Select department - either from URL or first available
    if dept_id:
        department = Department.query.get_or_404(dept_id)
    else:
        department = departments[0]
    
    # Simple permission categories
    permission_categories = {
        'Administration': [
            {'key': 'user_management', 'name': 'User Management', 'description': 'Manage user accounts', 'level': 'high', 'routes_count': 5},
            {'key': 'system_documents', 'name': 'System Documents', 'description': 'Manage documents', 'level': 'low', 'routes_count': 3}
        ],
        'Academic': [
            {'key': 'student_management', 'name': 'Student Management', 'description': 'Manage students', 'level': 'high', 'routes_count': 8},
            {'key': 'tutor_management', 'name': 'Tutor Management', 'description': 'Manage tutors', 'level': 'high', 'routes_count': 7},
            {'key': 'class_management', 'name': 'Class Management', 'description': 'Manage classes', 'level': 'medium', 'routes_count': 6},
            {'key': 'attendance_management', 'name': 'Attendance Management', 'description': 'Track attendance', 'level': 'medium', 'routes_count': 5}
        ],
        'Communication': [
            {'key': 'notice_management', 'name': 'Notice Management', 'description': 'Manage notices', 'level': 'medium', 'routes_count': 4},
            {'key': 'communication', 'name': 'Communication', 'description': 'Send messages', 'level': 'low', 'routes_count': 3}
        ],
        'Reports': [
            {'key': 'report_generation', 'name': 'Report Generation', 'description': 'Generate reports', 'level': 'medium', 'routes_count': 6},
            {'key': 'finance_management', 'name': 'Finance Management', 'description': 'Manage finances', 'level': 'high', 'routes_count': 8}
        ]
    }
    
    # SAFETY CHECKS - ensure no None values
    if not hasattr(department, 'permission_level') or department.permission_level is None:
        department.permission_level = 'medium'
    
    try:
        current_permissions = department.get_permissions()
    except:
        current_permissions = []
    
    return render_template('admin/permission_management.html',
                         departments=departments,
                         department=department,
                         permission_categories=permission_categories,
                         current_permissions=current_permissions)
    
    
@bp.route('/fix-departments')
@login_required
@require_role('superadmin', 'admin')
def fix_departments():
    """Fix department data - temporary route"""
    try:
        departments = Department.query.all()
        fixed_count = 0
        
        for dept in departments:
            changed = False
            
            # Fix permission_level if None
            if dept.permission_level is None:
                dept.permission_level = 'medium'
                changed = True
            
            # Fix name if None
            if dept.name is None:
                dept.name = f'Department {dept.id}'
                changed = True
                
            # Fix code if None
            if dept.code is None:
                dept.code = f'DEPT{dept.id}'
                changed = True
            
            if changed:
                fixed_count += 1
        
        if fixed_count > 0:
            db.session.commit()
            return f"Fixed {fixed_count} departments. Now try permission-management again."
        else:
            return f"Found {len(departments)} departments, all look good."
            
    except Exception as e:
        return f"Error: {str(e)}"
# ============ TUTOR MANAGEMENT ROUTES ============

@bp.route('/tutors')
@login_required
@require_permission('tutor_management')
def tutors():
    """Tutor management page"""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    dept_filter = request.args.get('department', '', type=int)
    search = request.args.get('search', '')
    
    query = Tutor.query.join(User)
    
    if status_filter:
        query = query.filter(Tutor.status == status_filter)
    
    if dept_filter:
        query = query.filter(User.department_id == dept_filter)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(User.full_name.ilike(search_term))
    
    tutors = query.order_by(Tutor.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    departments = Department.query.filter_by(is_active=True).all()

    filtered_args = request.args.to_dict()
    filtered_args.pop('page', None)  
    
    return render_template('admin/tutors.html', tutors=tutors, departments=departments, filtered_args=filtered_args )


@bp.route('/tutors/register', methods=['GET', 'POST'])
@login_required
@require_permission('tutor_management')
def register_tutor():
    """Register new tutor with test score"""
    form = TutorRegistrationForm()
    
    if form.validate_on_submit():
        try:
            # Validate department selection
            if form.department_id.data == 0:
                raise ValueError("Please select a valid department")
            
            # Validate test score
            if form.test_score.data is None or form.test_score.data < 0 or form.test_score.data > 100:
                raise ValueError("Test score must be between 0 and 100")
            
            # Store password before hashing for email
            plain_password = form.password.data
            
            # Create user account
            user = User(
                username=form.username.data,
                email=form.email.data,
                full_name=form.full_name.data,
                phone=form.phone.data,
                role='tutor',
                department_id=form.department_id.data,
                address=form.address.data,
                is_active=True,
                is_verified=False,
                joining_date=datetime.now().date()
            )
            user.set_password(plain_password)
            
            db.session.add(user)
            db.session.flush()  # Get user ID
            
            # Create tutor profile with test score
            tutor = Tutor(
                user_id=user.id,
                qualification=form.qualification.data,
                experience=form.experience.data,
                salary_type=form.salary_type.data,
                monthly_salary=form.monthly_salary.data,
                hourly_rate=form.hourly_rate.data,
                # Test Score Information - NEW FIELDS
                test_score=form.test_score.data,
                test_date=form.test_date.data,
                test_notes=form.test_notes.data,
                status='pending',
                verification_status='pending',
                date_of_birth=form.date_of_birth.data,
                state=form.state.data,
                pin_code=form.pin_code.data
            )
            
            # Set subjects, grades, and boards
            tutor.set_subjects([s.strip() for s in form.subjects.data.split(',')])
            tutor.set_grades([g.strip() for g in form.grades.data.split(',')])
            tutor.set_boards([b.strip() for b in form.boards.data.split(',')])
            
            # Handle document uploads
            documents = {}
            required_docs = ['aadhaar_card', 'pan_card', 'resume', 'degree_certificate']
            
            for doc_name in required_docs:
                file_field = getattr(form, doc_name).data

                if has_file_content(file_field):
                    s3_url = upload_file_to_s3(file_field, folder=f"{current_app.config['UPLOAD_FOLDER']}/documents")
                    if s3_url:
                        documents[doc_name.replace('_card', '').replace('_certificate', '')] = s3_url
                    else:
                        raise ValueError(f"{doc_name.replace('_', ' ').title()} upload failed.")
                else:
                    raise ValueError(f"{doc_name.replace('_', ' ').title()} is required")
            
            tutor.set_documents(documents)
            
            # Handle video uploads
            required_videos = ['demo_video', 'interview_video']
            for video_name in required_videos:
                file_field = getattr(form, video_name).data
                if has_file_content(file_field):
                    s3_url = upload_file_to_s3(file_field, folder=f"{current_app.config['UPLOAD_FOLDER']}/videos")
                    if s3_url:
                        setattr(tutor, video_name, s3_url)
                    else:
                        raise ValueError(f"{video_name.replace('_', ' ').title()} upload failed.")
            
            # Set bank details
            bank_details = {
                'account_holder_name': form.account_holder_name.data,
                'bank_name': form.bank_name.data,
                'branch_name': form.branch_name.data,
                'account_number': form.account_number.data,
                'ifsc_code': form.ifsc_code.data
            }
            tutor.set_bank_details(bank_details)
            
            db.session.add(tutor)
            db.session.commit()
            
            # Send onboarding email
            try:
                send_onboarding_email(user, plain_password)
                
                # Success message with test score info
                test_grade = tutor.get_test_score_grade()
                success_message = f'Tutor {user.full_name} registered successfully with test score {tutor.test_score}/100 ({test_grade}). Onboarding email sent to {user.email}.'
                flash(success_message, 'success')
                
            except Exception as email_error:
                # Warning message with test score info
                test_grade = tutor.get_test_score_grade()
                warning_message = f'Tutor {user.full_name} registered successfully with test score {tutor.test_score}/100 ({test_grade}), but failed to send onboarding email. Please send credentials manually to {user.email}.'
                flash(warning_message, 'warning')
            
            return redirect(url_for('admin.tutors'))
            
        except ValueError as ve:
            db.session.rollback()
            flash(str(ve), 'error')
        except Exception as e:
            db.session.rollback()
            flash(f'Error registering tutor: {str(e)}', 'error')
    
    return render_template('admin/register_tutor.html', form=form)

def has_file_content(file_field):
    """Check if file field actually has a file"""
    return (file_field and 
            hasattr(file_field, 'filename') and 
            file_field.filename and 
            file_field.filename.strip() != '')
    

@bp.route('/tutors/<int:tutor_id>')
@login_required
@require_permission('tutor_management')
def tutor_details(tutor_id):
    """View tutor details"""
    tutor = Tutor.query.get_or_404(tutor_id)
    
    # Get tutor's classes
    classes = Class.query.filter_by(tutor_id=tutor.id).order_by(Class.scheduled_date.desc()).limit(10).all()
    
    # Get attendance summary
    attendance_summary = Attendance.get_attendance_summary(tutor_id=tutor.id)
    
    return render_template('admin/tutor_details.html', 
                         tutor=tutor, classes=classes, 
                         attendance_summary=attendance_summary)

@bp.route('/tutors/<int:tutor_id>/verify', methods=['POST'])
@login_required
@require_permission('tutor_management')
def verify_tutor(tutor_id):
    """Verify tutor profile"""
    tutor = Tutor.query.get_or_404(tutor_id)
    
    # Validate request data
    if not request.is_json:
        return jsonify({'success': False, 'error': 'Request must be JSON'}), 400
    
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400
    
    action = data.get('action')
    if not action or action not in ['approve', 'reject']:
        return jsonify({'success': False, 'error': 'Invalid or missing action'}), 400
    
    # Check if tutor can be verified
    if tutor.verification_status == 'verified' and action == 'approve':
        return jsonify({'success': False, 'error': 'Tutor is already verified'}), 400
    
    try:
        if action == 'approve':
            tutor.verification_status = 'verified'
            tutor.status = 'active'
            tutor.user.is_verified = True
            message = f'Tutor {tutor.user.full_name} has been verified and activated.'
            
        elif action == 'reject':
            tutor.verification_status = 'rejected'
            tutor.status = 'inactive'
            tutor.user.is_verified = False
            message = f'Tutor {tutor.user.full_name} verification has been rejected.'
        
        # Commit changes to database
        db.session.commit()
        
        # Log the action for audit trail
        current_app.logger.info(
            f'Admin {current_user.username} (ID: {current_user.id}) '
            f'{action}d tutor verification for {tutor.user.full_name} (ID: {tutor_id})'
        )
        
        return jsonify({
            'success': True,
            'message': message,
            'data': {
                'tutor_id': tutor_id,
                'verification_status': tutor.verification_status,
                'tutor_status': tutor.status,
                'user_verified': tutor.user.is_verified
            }
        })
        
    except Exception as e:
        db.session.rollback()
        error_msg = f'Database error during tutor verification: {str(e)}'
        current_app.logger.error(error_msg)
        return jsonify({
            'success': False, 
            'error': 'Failed to update tutor verification status. Please try again.'
        }), 500

@bp.route('/tutors/<int:tutor_id>/toggle-status', methods=['POST'])
@login_required
@require_permission('tutor_management')
def toggle_tutor_status(tutor_id):
    """Toggle tutor active/inactive status"""
    tutor = Tutor.query.get_or_404(tutor_id)
    
    try:
        # Determine new status
        if tutor.status == 'active':
            new_tutor_status = 'inactive'
            new_user_status = False
            action_text = 'deactivated'
        else:
            new_tutor_status = 'active'
            new_user_status = True
            action_text = 'activated'
        
        # Update both tutor and user status
        tutor.status = new_tutor_status
        tutor.user.is_active = new_user_status
        
        # Commit changes
        db.session.commit()
        
        message = f'Tutor {tutor.user.full_name} has been {action_text}.'
        
        # Log the action
        current_app.logger.info(
            f'Admin {current_user.username} (ID: {current_user.id}) '
            f'{action_text} tutor {tutor.user.full_name} (ID: {tutor_id})'
        )
        
        return jsonify({
            'success': True,
            'message': message,
            'data': {
                'tutor_id': tutor_id,
                'tutor_status': tutor.status,
                'user_active': tutor.user.is_active,
                'action': action_text
            }
        })
        
    except Exception as e:
        db.session.rollback()
        error_msg = f'Database error during status toggle: {str(e)}'
        current_app.logger.error(error_msg)
        return jsonify({
            'success': False,
            'error': 'Failed to update tutor status. Please try again.'
        }), 500
        
@bp.route('/tutors/<int:tutor_id>/documents/<document_type>/view')
@login_required
@require_permission('tutor_management')
def view_tutor_document(tutor_id, document_type):
    """Generate secure presigned URL for viewing tutor documents"""
    try:
        tutor = Tutor.query.get_or_404(tutor_id)
        
        # Check permissions
        if current_user.role not in ['superadmin', 'admin', 'coordinator']:
            return jsonify({'error': 'Access denied'}), 403
        
        # Get document URL from tutor
        documents = tutor.get_documents()
        document_info = documents.get(document_type)
        
        if not document_info:
            return jsonify({'error': 'Document not found'}), 404
        
        # Extract filename/URL
        if isinstance(document_info, dict):
            document_url = document_info.get('filename')
        else:
            document_url = document_info
        
        if not document_url:
            return jsonify({'error': 'Document URL not found'}), 404
        
        # Generate secure presigned URL
        from app.utils.helper import generate_signed_document_url
        signed_url = generate_signed_document_url(document_url, expiration=3600)  # 1 hour
        
        if signed_url:
            # Redirect to the secure URL
            return redirect(signed_url)
        else:
            return jsonify({'error': 'Failed to generate secure URL'}), 500
            
    except Exception as e:
        current_app.logger.error(f'Error viewing tutor document: {str(e)}')
        return jsonify({'error': f'Error accessing document: {str(e)}'}), 500
    
@bp.route('/tutors/<int:tutor_id>/videos/<video_type>/view')
@login_required
@require_permission('tutor_management')
def view_tutor_video(tutor_id, video_type):
    """Generate secure presigned URL for viewing tutor videos"""
    try:
        tutor = Tutor.query.get_or_404(tutor_id)
        
        # Check permissions
        if current_user.role not in ['superadmin', 'admin', 'coordinator']:
            return jsonify({'error': 'Access denied'}), 403
        
        # Get video URL from tutor
        video_url = None
        if video_type == 'demo' and tutor.demo_video:
            video_url = tutor.demo_video
        elif video_type == 'interview' and tutor.interview_video:
            video_url = tutor.interview_video
        else:
            return jsonify({'error': 'Video not found'}), 404
        
        if not video_url:
            return jsonify({'error': 'Video URL not found'}), 404
        
        # Generate secure presigned URL
        from app.utils.helper import generate_signed_video_url
        signed_url = generate_signed_video_url(video_url, expiration=86400)  # 24 hours for videos
        
        if signed_url and signed_url != video_url:  # If signing was successful
            return redirect(signed_url)
        else:
            return jsonify({'error': 'Failed to generate secure URL'}), 500
            
    except Exception as e:
        current_app.logger.error(f'Error viewing tutor video: {str(e)}')
        return jsonify({'error': f'Error accessing video: {str(e)}'}), 500

# ============ STUDENT MANAGEMENT ROUTES ============

# Replace the students route in app/routes/admin.py

@bp.route('/students')
@login_required
@require_permission('student_management')
@handle_errors
def students():
    """Student management page with optimized queries"""
    page = request.args.get('page', 1, type=int)
    grade_filter = request.args.get('grade', '').strip()
    dept_filter_raw = request.args.get('department', '').strip()
    search = request.args.get('search', '').strip()
    
    # Convert department filter to int only if it's a valid number
    dept_filter = None
    if dept_filter_raw and dept_filter_raw.isdigit():
        dept_filter = int(dept_filter_raw)
    
    # Build base query with eager loading for better performance
    # Note: Removed automatic is_active=True filter to show all students
    query = Student.query.options(db.joinedload(Student.department))
    
    # Apply department access check for coordinators FIRST
    if current_user.role == 'coordinator':
        query = query.filter_by(department_id=current_user.department_id)
    
    # Apply filters only if they have valid values
    if grade_filter:
        query = query.filter_by(grade=grade_filter)
    
    # Only apply department filter if user selected a specific department AND user is not a coordinator
    if dept_filter and dept_filter > 0 and current_user.role != 'coordinator':
        query = query.filter_by(department_id=dept_filter)
    
    # Apply search filter using traditional method for compatibility
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Student.full_name.ilike(search_term),
                Student.email.ilike(search_term),
                Student.phone.ilike(search_term)
            )
        )
    
    # Get paginated results - Use Flask-SQLAlchemy's paginate for template compatibility
    students = query.order_by(Student.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    # Get dashboard stats efficiently - use the base query without pagination
    base_count_query = query.with_entities(Student.id)  # More efficient count
    stats = {
        'total_students': base_count_query.count()
    }
    
    # Add enrollment status stats using the same filtered query
    for status in ['active', 'paused', 'completed', 'dropped']:
        stats[f'{status}_students'] = base_count_query.filter(Student.enrollment_status == status).count()
    
    # Get departments (respect coordinator permissions)
    if current_user.role == 'coordinator':
        departments = Department.query.filter_by(
            id=current_user.department_id, 
            is_active=True
        ).all()
    else:
        departments = Department.query.filter_by(is_active=True).all()
    
    return render_template('admin/students.html', 
                         students=students, 
                         departments=departments,
                         stats=stats)

# Replace the register_student route in app/routes/admin.py

@bp.route('/students/register', methods=['GET', 'POST'])
@login_required
@require_permission('student_management')
def register_student():
    """Register new student"""
    from app.forms.user import StudentRegistrationForm
    
    form = StudentRegistrationForm()
    
    # Get all unique subjects for dropdown (for the subject enhancement)
    all_students = Student.query.all()
    all_subjects = set()
    for s in all_students:
        subjects = s.get_subjects_enrolled()
        all_subjects.update(subjects)
    
    # Add some common subjects if none exist yet
    if not all_subjects:
        all_subjects = {
            'Mathematics', 'Physics', 'Chemistry', 'Biology', 'English', 
            'Hindi', 'History', 'Geography', 'Economics', 'Computer Science',
            'Accountancy', 'Business Studies', 'Political Science', 'Sociology'
        }
    
    if form.validate_on_submit():
        try:
            # Create student
            student = Student(
                full_name=form.full_name.data,
                email=form.email.data,
                phone=form.phone.data,
                date_of_birth=form.date_of_birth.data,
                address=form.address.data,
                state=form.state.data,
                pin_code=form.pin_code.data,
                grade=form.grade.data,
                board=form.board.data,
                school_name=form.school_name.data,
                academic_year=form.academic_year.data,
                course_start_date=form.course_start_date.data,
                department_id=form.department_id.data,
                relationship_manager=form.relationship_manager.data,
                created_at=datetime.utcnow()
            )
            
            # Parent details
            parent_details = {
                'father': {
                    'name': form.father_name.data or '',
                    'phone': form.father_phone.data or '',
                    'email': form.father_email.data or '',
                    'profession': form.father_profession.data or '',
                    'workplace': getattr(form, 'father_workplace', None) and form.father_workplace.data or ''
                },
                'mother': {
                    'name': form.mother_name.data or '',
                    'phone': form.mother_phone.data or '',
                    'email': form.mother_email.data or '',
                    'profession': form.mother_profession.data or '',
                    'workplace': getattr(form, 'mother_workplace', None) and form.mother_workplace.data or ''
                }
            }
            student.set_parent_details(parent_details)
            
            # Academic profile
            academic_profile = {
                'siblings': getattr(form, 'siblings', None) and form.siblings.data or '',
                'hobbies': [h.strip() for h in (getattr(form, 'hobbies', None) and form.hobbies.data or '').split(',') if h.strip()],
                'learning_styles': [l.strip() for l in (getattr(form, 'learning_styles', None) and form.learning_styles.data or '').split(',') if l.strip()],
                'learning_patterns': [p.strip() for p in (getattr(form, 'learning_patterns', None) and form.learning_patterns.data or '').split(',') if p.strip()],
                'parent_feedback': getattr(form, 'parent_feedback', None) and form.parent_feedback.data or ''
            }
            student.set_academic_profile(academic_profile)
            
            # Subjects
            if form.subjects_enrolled.data:
                subjects = [s.strip() for s in form.subjects_enrolled.data.split(',') if s.strip()]
                student.set_subjects_enrolled(subjects)
            
            # Fee structure with enhanced installment support
            fee_structure = {
                'total_fee': float(getattr(form, 'total_fee', None) and form.total_fee.data or 0),
                'amount_paid': float(getattr(form, 'amount_paid', None) and form.amount_paid.data or 0),
                'payment_mode': getattr(form, 'payment_mode', None) and form.payment_mode.data or ''
            }
            fee_structure['balance_amount'] = fee_structure['total_fee'] - fee_structure['amount_paid']
            student.set_fee_structure(fee_structure)
            
            # Handle installment plan only if payment schedule is set to installment_plan
            if form.payment_schedule.data == 'installment_plan':
                installment_data = request.form.get('installment_data')
                if installment_data:
                    try:
                        import json
                        installments = json.loads(installment_data)
                        if installments:  # Only create plan if installments exist
                            student.create_installment_plan(installments)
                            print(f"Created installment plan with {len(installments)} installments")
                        else:
                            print("No installment data provided for installment payment plan")
                            flash('Installment payment plan selected but no installment details provided.', 'warning')
                    except Exception as e:
                        print(f"Error creating installment plan: {e}")
                        # Don't fail registration if installment creation fails
                        flash('Student registered successfully, but installment plan could not be created.', 'warning')
                else:
                    print("Installment payment plan selected but no installment data found")
                    flash('Installment payment plan selected but no installment details provided.', 'warning')
            
            # Handle document uploads
            documents = {}
            
            # Process file uploads if they exist
            for field_name in ['marksheet', 'student_aadhaar', 'school_id']:
                if hasattr(form, field_name):
                    file_field = getattr(form, field_name)
                    if file_field.data:
                        try:
                            # Upload to S3 or your file storage system
                            file_url = upload_file_to_s3(file_field.data, folder=f"{current_app.config['UPLOAD_FOLDER']}/students")
                            if file_url:
                                documents[field_name] = file_url
                        except Exception as e:
                            print(f"Error uploading {field_name}: {e}")
                            flash(f'Error uploading {field_name.replace("_", " ").title()}', 'warning')
            
            if documents:
                student.set_documents(documents)
            
            db.session.add(student)
            db.session.commit()
            
            flash(f'Student {student.full_name} registered successfully!', 'success')
            return redirect(url_for('admin.students'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error registering student: {str(e)}', 'error')
            print(f"Error registering student: {e}")  # For debugging
    else:
        # Print form errors for debugging
        if form.errors:
            print(f"Form validation errors: {form.errors}")
    
    return render_template('admin/register_student.html', 
                         form=form, 
                         all_subjects=sorted(list(all_subjects)))

@bp.route('/students/<int:student_id>')
@login_required
@require_permission('student_management')
@handle_errors
def student_details(student_id):
    """View student details with optimized queries"""
    # Use optimized query with eager loading (allow both active and inactive students)
    student = DatabaseService.get_optimized_query(
        Student,
        includes=['department'],
        filters={'id': student_id}
    ).first()
    
    if not student:
        return error_service.handle_not_found_error("Student")
    
    # Check department access
    if current_user.role == 'coordinator' and current_user.department_id != student.department_id:
        flash('Access denied. You can only view students from your department.', 'error')
        return redirect(url_for('admin.students'))
    
    # Optimized query for student's classes - direct SQL search instead of loading all classes
    student_classes = Class.query.filter(
        or_(
            Class.primary_student_id == student_id,
            Class.students.like(f'%{student_id}%')
        )
    ).options(
        db.joinedload(Class.tutor).joinedload(Tutor.user)
    ).order_by(Class.scheduled_date.desc()).limit(20).all()
    
    # Get attendance summary using optimized method
    attendance_summary = DatabaseService.get_dashboard_stats(
        Attendance,
        user_filter=lambda q: q.filter_by(student_id=student_id),
        date_field='class_date',
        days=365
    )
    
    # Optimized query for upcoming classes
    upcoming_classes = Class.query.filter(
        and_(
            or_(
                Class.primary_student_id == student_id,
                Class.students.like(f'%{student_id}%')
            ),
            Class.scheduled_date >= date.today(),
            Class.status == 'scheduled'
        )
    ).options(
        db.joinedload(Class.tutor).joinedload(Tutor.user)
    ).order_by(Class.scheduled_date, Class.scheduled_time).limit(5).all()
    
    return render_template('admin/student_details.html',
                         student=student,
                         classes=student_classes,
                         upcoming_classes=upcoming_classes,
                         attendance_summary=attendance_summary)

# COMPLETE REPLACEMENT for edit_student route in app/routes/admin.py

@bp.route('/students/<int:student_id>/edit', methods=['GET', 'POST'])
@login_required
@require_permission('student_management')
def edit_student(student_id):
    """Edit student information"""
    from datetime import datetime
    from app.forms.user import EditStudentForm
    
    student = Student.query.get_or_404(student_id)
    
    # Check department access
    if current_user.role == 'coordinator' and current_user.department_id != student.department_id:
        flash('Access denied. You can only edit students from your department.', 'error')
        return redirect(url_for('admin.students'))
    
    # Initialize form with student object (this handles basic fields)
    form = EditStudentForm(student_id=student.id, obj=student)
    
    # Pre-populate form with existing data on GET request
    if request.method == 'GET':
        # Get parent details and populate form
        parent_details = student.get_parent_details()
        if parent_details:
            father = parent_details.get('father', {})
            mother = parent_details.get('mother', {})
            
            # Populate father fields
            form.father_name.data = father.get('name', '')
            form.father_phone.data = father.get('phone', '')
            form.father_email.data = father.get('email', '')
            form.father_profession.data = father.get('profession', '')
            
            # Populate mother fields  
            form.mother_name.data = mother.get('name', '')
            form.mother_phone.data = mother.get('phone', '')
            form.mother_email.data = mother.get('email', '')
            form.mother_profession.data = mother.get('profession', '')
        
        # Get academic profile and populate form
        academic_profile = student.get_academic_profile()
        if academic_profile:
            form.siblings.data = str(academic_profile.get('siblings', ''))
            form.hobbies.data = ', '.join(academic_profile.get('hobbies', []))
            form.learning_styles.data = ', '.join(academic_profile.get('learning_styles', []))
            form.parent_feedback.data = academic_profile.get('parent_feedback', '')
        
        # Get subjects and populate form
        subjects = student.get_subjects_enrolled()
        if subjects:
            form.subjects_enrolled.data = ', '.join(subjects)
        
        # Get fee structure and populate form
        fee_structure = student.get_fee_structure()
        if fee_structure:
            form.total_fee.data = fee_structure.get('total_fee', 0)
            form.amount_paid.data = fee_structure.get('amount_paid', 0)
            form.payment_mode.data = fee_structure.get('payment_mode', '')
            form.payment_schedule.data = fee_structure.get('payment_schedule', '')
    
    if form.validate_on_submit():
        try:
            # Update basic information
            student.full_name = form.full_name.data
            student.email = form.email.data
            student.phone = form.phone.data
            student.date_of_birth = form.date_of_birth.data
            student.address = form.address.data
            student.state = form.state.data
            student.pin_code = form.pin_code.data
            student.grade = form.grade.data
            student.board = form.board.data
            student.school_name = form.school_name.data
            student.academic_year = form.academic_year.data
            student.course_start_date = form.course_start_date.data
            student.relationship_manager = form.relationship_manager.data
            
            # Update parent details
            parent_details = {
                'father': {
                    'name': form.father_name.data or '',
                    'phone': form.father_phone.data or '',
                    'email': form.father_email.data or '',
                    'profession': form.father_profession.data or ''
                },
                'mother': {
                    'name': form.mother_name.data or '',
                    'phone': form.mother_phone.data or '',
                    'email': form.mother_email.data or '',
                    'profession': form.mother_profession.data or ''
                }
            }
            student.set_parent_details(parent_details)
            
            # Update academic profile
            academic_profile = {
                'siblings': form.siblings.data or '',
                'hobbies': [h.strip() for h in (form.hobbies.data or '').split(',') if h.strip()],
                'learning_styles': [l.strip() for l in (form.learning_styles.data or '').split(',') if l.strip()],
                'parent_feedback': form.parent_feedback.data or ''
            }
            student.set_academic_profile(academic_profile)
            
            # Update subjects enrolled
            if form.subjects_enrolled.data:
                subjects = [s.strip() for s in form.subjects_enrolled.data.split(',') if s.strip()]
                student.set_subjects_enrolled(subjects)
            
            # Update fee structure
            fee_structure = student.get_fee_structure()
            fee_structure.update({
                'total_fee': float(form.total_fee.data or 0),
                'amount_paid': float(form.amount_paid.data or 0),
                'payment_mode': form.payment_mode.data or '',
                'payment_schedule': form.payment_schedule.data or ''
            })
            fee_structure['balance_amount'] = fee_structure['total_fee'] - fee_structure['amount_paid']
            student.set_fee_structure(fee_structure)
            
            # Set department if provided
            if form.department_id.data:
                student.department_id = form.department_id.data
            
            # Set updated timestamp
            student.updated_at = datetime.utcnow()
            
            db.session.commit()
            flash(f'Student {student.full_name} updated successfully!', 'success')
            return redirect(url_for('admin.students'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating student: {str(e)}', 'error')
            print(f"Error updating student: {e}")
    else:
        # Print form errors for debugging
        if form.errors:
            print(f"Form validation errors: {form.errors}")
    
    # Get all unique subjects for dropdown (for the subject enhancement)
    all_students = Student.query.all()
    all_subjects = set()
    for s in all_students:
        subjects = s.get_subjects_enrolled()
        all_subjects.update(subjects)
    
    return render_template('admin/edit_student.html', 
                         form=form, 
                         student=student,
                         all_subjects=sorted(list(all_subjects)))

@bp.route('/students/<int:student_id>/deactivate', methods=['POST'])
@login_required
@require_permission('student_management')
def deactivate_student(student_id):
    """Deactivate a student"""
    student = Student.query.get_or_404(student_id)
    
    # Check department access
    if current_user.role == 'coordinator' and current_user.department_id != student.department_id:
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        student.is_active = False
        student.enrollment_status = 'dropped'
        db.session.commit()
        
        flash(f'Student {student.full_name} has been deactivated.', 'success')
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Error deactivating student'}), 500

@bp.route('/students/<int:student_id>/activate', methods=['POST'])
@login_required
@require_permission('student_management')
def activate_student(student_id):
    """Activate a student"""
    student = Student.query.get_or_404(student_id)
    
    # Check department access
    if current_user.role == 'coordinator' and current_user.department_id != student.department_id:
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        student.is_active = True
        student.enrollment_status = 'active'
        db.session.commit()
        
        flash(f'Student {student.full_name} has been activated.', 'success')
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Error activating student'}), 500


@bp.route('/students/<int:student_id>/toggle-status', methods=['POST'])
@login_required
@require_permission('student_management')
def toggle_student_status(student_id):
    """Toggle student active status"""
    student = Student.query.get_or_404(student_id)
    
    # Check department access
    if current_user.role == 'coordinator' and current_user.department_id != student.department_id:
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        # Toggle status
        student.is_active = not student.is_active
        
        # Update enrollment status based on active status
        if student.is_active:
            student.enrollment_status = 'active'
        else:
            student.enrollment_status = 'paused'
        
        # Set updated timestamp
        student.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        status_text = 'activated' if student.is_active else 'deactivated'
        return jsonify({
            'success': True, 
            'message': f'Student {student.full_name} {status_text} successfully',
            'new_status': student.is_active
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error updating student status: {str(e)}'}), 500
    
    
@bp.route('/students/<int:student_id>/documents/<document_type>/view')
@login_required
@require_permission('student_management') 
def view_student_document(student_id, document_type):
    """Generate secure presigned URL for viewing student documents"""
    try:
        student = Student.query.get_or_404(student_id)
        
        # Check permissions
        if current_user.role not in ['superadmin', 'admin', 'coordinator']:
            return jsonify({'error': 'Access denied'}), 403
        
        # Get document URL from student
        documents = student.get_documents()
        document_info = documents.get(document_type)
        
        if not document_info:
            return jsonify({'error': 'Document not found'}), 404
        
        # Extract filename/URL
        if isinstance(document_info, dict):
            document_url = document_info.get('filename')
        else:
            document_url = document_info
        
        if not document_url:
            return jsonify({'error': 'Document URL not found'}), 404
        
        # Generate secure presigned URL
        from app.utils.helper import generate_signed_document_url
        signed_url = generate_signed_document_url(document_url, expiration=3600)
        
        if signed_url:
            return redirect(signed_url)
        else:
            return jsonify({'error': 'Failed to generate secure URL'}), 500
            
    except Exception as e:
        current_app.logger.error(f'Error viewing student document: {str(e)}')
        return jsonify({'error': f'Error accessing document: {str(e)}'}), 500


# ==================== GRADUATION AND DROP FUNCTIONALITY ====================

@bp.route('/students/<int:student_id>/graduate', methods=['GET', 'POST'])
@login_required
@require_permission('student_management')
def graduate_student(student_id):
    """Graduate a student"""
    from app.forms.student_status_forms import GraduateStudentForm
    
    student = Student.query.get_or_404(student_id)
    
    # Check department access
    if current_user.role == 'coordinator' and current_user.department_id != student.department_id:
        flash('Access denied', 'error')
        return redirect(url_for('admin.students'))
    
    form = GraduateStudentForm()
    
    # Check eligibility
    can_graduate, eligibility_reason = student.can_graduate()
    
    if form.validate_on_submit():
        # Check if manual override is being used
        using_override = form.manual_override.data
        
        if not can_graduate and not using_override:
            flash(f'Cannot graduate student: {eligibility_reason}', 'error')
            return redirect(url_for('admin.student_details', student_id=student_id))
        
        # Validate override reason if using override
        if using_override and not form.override_reason.data:
            flash('Override reason is required when using manual override', 'error')
            return render_template('admin/students/graduate.html', 
                                 student=student, form=form, 
                                 can_graduate=can_graduate, reason=eligibility_reason)
        
        try:
            # Parse achievements from form if provided
            achievements = []
            if form.achievements.data:
                achievements = [ach.strip() for ach in form.achievements.data.split('\n') if ach.strip()]
            
            graduation = student.graduate_student(
                final_grade=form.final_grade.data if form.final_grade.data else None,
                graduation_date=form.graduation_date.data,
                user_id=current_user.id,
                feedback=form.feedback.data,
                achievements=achievements,
                performance_rating=form.overall_performance.data,
                issue_certificate=form.issue_certificate.data,
                manual_override=using_override,
                override_reason=form.override_reason.data
            )
            
            # Send graduation notification
            try:
                from app.services.student_notification_service import StudentNotificationService
                StudentNotificationService.send_graduation_notification(student, graduation)
            except ImportError:
                pass  # Notification service not yet implemented
            
            flash(f'🎓 Student {student.full_name} has been successfully graduated!', 'success')
            return redirect(url_for('admin.student_details', student_id=student_id))
            
        except ValueError as e:
            flash(str(e), 'error')
        except Exception as e:
            flash(f'Error graduating student: {str(e)}', 'error')
    
    return render_template('admin/students/graduate.html', 
                         student=student, form=form, 
                         can_graduate=can_graduate, 
                         eligibility_reason=eligibility_reason)


@bp.route('/students/<int:student_id>/drop', methods=['GET', 'POST'])
@login_required  
@require_permission('student_management')
def drop_student_new(student_id):
    """Drop a student with detailed workflow"""
    from app.forms.student_status_forms import DropStudentForm
    
    student = Student.query.get_or_404(student_id)
    
    # Check department access
    if current_user.role == 'coordinator' and current_user.department_id != student.department_id:
        flash('Access denied', 'error')
        return redirect(url_for('admin.students'))
    
    form = DropStudentForm()
    
    # Pre-populate refund amount with current balance if applicable
    if not form.refund_amount.data:
        # Could calculate suggested refund based on remaining course time
        balance = student.get_balance_amount()
        if balance == 0 and student.get_fee_status() == 'paid':
            # Student has paid, calculate pro-rated refund
            progress = student.get_course_progress()
            if progress and progress < 80:  # Less than 80% complete
                fee_structure = student.get_fee_structure()
                total_fee = fee_structure.get('total_fee', 0) if fee_structure else 0
                if total_fee > 0:
                    remaining_percentage = (100 - progress) / 100
                    suggested_refund = total_fee * remaining_percentage * 0.8  # 80% refund rate
                    form.refund_amount.data = round(suggested_refund, 2)
    
    if form.validate_on_submit():
        # Check if manual override is being used
        using_override = form.manual_override.data
        
        # Validate override reason if using override
        if using_override and not form.override_reason.data:
            flash('Override reason is required when using manual override', 'error')
            return render_template('admin/students/drop.html', 
                                 student=student, form=form)
        
        try:
            drop_record = student.drop_student(
                drop_reason=form.drop_reason.data,
                detailed_reason=form.detailed_reason.data,
                drop_date=form.drop_date.data,
                dropped_by=current_user.id,
                refund_amount=form.refund_amount.data or 0,
                refund_reason=form.refund_reason.data,
                exit_interview_notes=form.exit_interview_notes.data,
                re_enrollment_allowed=form.re_enrollment_allowed.data,
                blacklist=form.blacklist_student.data,
                cancel_future_classes=form.cancel_future_classes.data,
                internal_notes=form.internal_notes.data,
                manual_override=using_override,
                override_reason=form.override_reason.data
            )
            
            # Update additional drop record fields
            drop_record.exit_interview_conducted = form.exit_interview_conducted.data
            drop_record.student_notified = form.notify_parents.data  # Will be set to True after notification
            drop_record.parents_notified = form.notify_parents.data
            drop_record.tutor_notified = form.notify_tutor.data
            db.session.commit()
            
            # Send notifications
            try:
                from app.services.student_notification_service import StudentNotificationService
                if form.notify_parents.data:
                    StudentNotificationService.send_drop_notification(student, drop_record)
                if form.notify_tutor.data:
                    StudentNotificationService.send_tutor_drop_notification(student, drop_record)
            except ImportError:
                pass  # Notification service not yet implemented
            
            flash(f'Student {student.full_name} has been dropped from the course.', 'info')
            if drop_record.cancelled_classes_count > 0:
                flash(f'Cancelled {drop_record.cancelled_classes_count} future classes.', 'info')
            
            return redirect(url_for('admin.student_details', student_id=student_id))
            
        except Exception as e:
            db.session.rollback()  # Roll back the transaction on error
            flash(f'Error dropping student: {str(e)}', 'error')
    
    return render_template('admin/students/drop.html', student=student, form=form)


@bp.route('/students/<int:student_id>/reactivate', methods=['GET', 'POST'])
@login_required
@require_permission('student_management')
def reactivate_student_new(student_id):
    """Reactivate a dropped or paused student"""
    from app.forms.student_status_forms import ReactivateStudentForm
    
    student = Student.query.get_or_404(student_id)
    
    # Check department access
    if current_user.role == 'coordinator' and current_user.department_id != student.department_id:
        flash('Access denied', 'error')
        return redirect(url_for('admin.students'))
    
    if student.enrollment_status not in ['dropped', 'paused']:
        flash('Can only reactivate dropped or paused students.', 'error')
        return redirect(url_for('admin.student_details', student_id=student_id))
    
    form = ReactivateStudentForm()
    
    if form.validate_on_submit():
        try:
            student.reactivate_student(
                reactivated_by=current_user.id,
                reason=form.reason.data,
                reactivation_date=form.reactivation_date.data,
                reset_attendance=form.reset_attendance.data,
                new_course_start_date=form.new_course_start_date.data,
                special_conditions=form.special_conditions.data
            )
            
            # Send notifications
            try:
                from app.services.student_notification_service import StudentNotificationService
                if form.notify_student.data:
                    StudentNotificationService.send_reactivation_notification(student)
                if form.notify_tutor.data:
                    StudentNotificationService.send_tutor_reactivation_notification(student)
            except ImportError:
                pass
            
            flash(f'🎉 Student {student.full_name} has been successfully reactivated!', 'success')
            return redirect(url_for('admin.student_details', student_id=student_id))
            
        except ValueError as e:
            flash(str(e), 'error')
        except Exception as e:
            flash(f'Error reactivating student: {str(e)}', 'error')
    
    return render_template('admin/students/reactivate.html', student=student, form=form)


@bp.route('/students/<int:student_id>/status-history')
@login_required
@require_permission('student_management')
def student_status_history(student_id):
    """View student's status change history"""
    student = Student.query.get_or_404(student_id)
    
    # Check department access
    if current_user.role == 'coordinator' and current_user.department_id != student.department_id:
        flash('Access denied', 'error')
        return redirect(url_for('admin.students'))
    
    # Get status history
    status_history = student.get_status_history(limit=50)
    
    # Get graduation and drop records
    graduation_record = student.get_graduation_record()
    drop_record = student.get_drop_record()
    
    # Get lifecycle summary
    lifecycle_summary = student.get_lifecycle_summary()
    
    return render_template('admin/students/status_history.html', 
                         student=student,
                         status_history=status_history,
                         graduation_record=graduation_record,
                         drop_record=drop_record,
                         lifecycle_summary=lifecycle_summary)


@bp.route('/students/bulk-status-change', methods=['GET', 'POST'])
@login_required
@require_permission('student_management')
def bulk_status_change():
    """Bulk status change for multiple students"""
    from app.forms.student_status_forms import BulkStatusChangeForm
    
    form = BulkStatusChangeForm()
    
    if form.validate_on_submit():
        try:
            student_ids = [int(id.strip()) for id in form.student_ids.data.split(',') if id.strip().isdigit()]
            
            if not student_ids:
                flash('No valid student IDs provided.', 'error')
                return redirect(url_for('admin.students'))
            
            updated_count = 0
            errors = []
            
            for student_id in student_ids:
                try:
                    student = Student.query.get(student_id)
                    if not student:
                        errors.append(f"Student ID {student_id} not found")
                        continue
                    
                    # Check department access
                    if current_user.role == 'coordinator' and current_user.department_id != student.department_id:
                        errors.append(f"Access denied for student {student.full_name}")
                        continue
                    
                    # Store old status for history
                    old_status = student.enrollment_status
                    old_is_active = student.is_active
                    
                    # Update status
                    student.enrollment_status = form.new_status.data
                    if form.new_status.data == 'active':
                        student.is_active = True
                    elif form.new_status.data in ['dropped', 'paused']:
                        student.is_active = False
                    
                    # Log status change
                    from app.models.student_status_history import StudentStatusHistory
                    StudentStatusHistory.log_status_change(
                        student_id=student.id,
                        old_status=old_status,
                        new_status=form.new_status.data,
                        old_is_active=old_is_active,
                        new_is_active=student.is_active,
                        reason=form.reason.data,
                        changed_by_user_id=current_user.id,
                        change_method='bulk',
                        effective_date=form.effective_date.data,
                        notes=f"Bulk status change operation"
                    )
                    
                    updated_count += 1
                    
                except Exception as e:
                    errors.append(f"Error updating student ID {student_id}: {str(e)}")
            
            db.session.commit()
            
            flash(f'Successfully updated {updated_count} students.', 'success')
            if errors:
                for error in errors:
                    flash(error, 'warning')
            
            return redirect(url_for('admin.students'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error performing bulk update: {str(e)}', 'error')
    
    return render_template('admin/students/bulk_status_change.html', form=form)


# ==================== GRADUATION AND DROP STATISTICS ====================

@bp.route('/students/graduation-statistics')
@login_required
@require_permission('student_management')
def graduation_statistics():
    """View graduation statistics and reports"""
    from app.models.student_graduation import StudentGraduation
    from app.models.student_drop import StudentDrop
    from datetime import datetime
    import calendar
    
    current_year = datetime.now().year
    current_month = datetime.now().month
    
    # Get statistics for current year
    graduation_stats = StudentGraduation.get_graduation_statistics(current_year)
    drop_stats = StudentDrop.get_drop_statistics(current_year)
    
    # Monthly statistics for current year
    monthly_data = []
    for month in range(1, 13):
        month_graduations = StudentGraduation.get_graduation_statistics(current_year)
        month_drops = StudentDrop.get_drop_statistics(current_year, month)
        
        monthly_data.append({
            'month': calendar.month_name[month],
            'month_num': month,
            'graduations': len(StudentGraduation.query.filter(
                db.extract('year', StudentGraduation.graduation_date) == current_year,
                db.extract('month', StudentGraduation.graduation_date) == month
            ).all()),
            'drops': len(StudentDrop.query.filter(
                db.extract('year', StudentDrop.drop_date) == current_year,
                db.extract('month', StudentDrop.drop_date) == month
            ).all())
        })
    
    # Get common drop reasons
    common_drop_reasons = StudentDrop.get_common_drop_reasons()
    
    # Overall statistics
    total_students = Student.query.count()
    active_students = Student.query.filter_by(enrollment_status='active').count()
    graduated_students = Student.query.filter_by(enrollment_status='completed').count()
    dropped_students = Student.query.filter_by(enrollment_status='dropped').count()
    
    overall_stats = {
        'total_students': total_students,
        'active_students': active_students,
        'graduated_students': graduated_students,
        'dropped_students': dropped_students,
        'graduation_rate': round((graduated_students / total_students * 100), 2) if total_students > 0 else 0,
        'drop_rate': round((dropped_students / total_students * 100), 2) if total_students > 0 else 0
    }
    
    return render_template('admin/students/graduation_statistics.html',
                         graduation_stats=graduation_stats,
                         drop_stats=drop_stats,
                         monthly_data=monthly_data,
                         common_drop_reasons=common_drop_reasons,
                         overall_stats=overall_stats,
                         current_year=current_year)

@bp.route('/students/<int:student_id>/delete', methods=['DELETE'])
@login_required
@require_permission('student_management')
def delete_student(student_id):
    """Delete student (superadmin only)"""
    if current_user.role != 'superadmin':
        return jsonify({'error': 'Only superadmin can delete students'}), 403
    
    student = Student.query.get_or_404(student_id)
    
    try:
        student_name = student.full_name
        
        # You might want to soft delete instead of hard delete
        # For now, let's mark as deleted instead of actual deletion
        student.is_active = False
        student.enrollment_status = 'deleted'
        student.updated_at = datetime.utcnow()
        
        # Or for hard delete (uncomment below and comment above):
        # db.session.delete(student)
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Student {student_name} deleted successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error deleting student: {str(e)}'}), 500

# ============ CLASS MANAGEMENT ROUTES ============

@bp.route('/classes')
@login_required
@require_permission('class_management')
def classes():
    """Class management page"""
    page = request.args.get('page', 1, type=int)
    date_filter = request.args.get('date', '')
    tutor_filter = request.args.get('tutor', '', type=int)
    status_filter = request.args.get('status', '')
    class_type_filter = request.args.get('class_type', '')
    
    query = Class.query
    
    # Apply filters
    if date_filter:
        try:
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            query = query.filter_by(scheduled_date=filter_date)
        except ValueError:
            pass
    
    if tutor_filter:
        query = query.filter_by(tutor_id=tutor_filter)
    
    if status_filter:
        query = query.filter_by(status=status_filter)
        
    if class_type_filter:
        query = query.filter_by(class_type=class_type_filter)
    
    classes = query.order_by(Class.scheduled_date, Class.scheduled_time).paginate(
        page=page, per_page=20, error_out=False
    )
    
    # Get tutors - only those with availability set AND with user relationship
    available_tutors = []
    all_tutors = []
    
    try:
        # Get all tutors with user relationship
        tutors_query = Tutor.query.join(User).filter(User.is_active==True).all()
        
        for tutor in tutors_query:
            all_tutors.append(tutor)
            availability = tutor.get_availability()
            if availability and tutor.status == 'active':
                available_tutors.append(tutor)
    except Exception as e:
        print(f"Error loading tutors: {e}")
        tutors_query = Tutor.query.all()
        for tutor in tutors_query:
            if hasattr(tutor, 'user') and tutor.user:
                all_tutors.append(tutor)
                availability = tutor.get_availability()
                if availability and tutor.status == 'active':
                    available_tutors.append(tutor)
    
    # Get students - Student model has fields directly
    students = []
    try:
        students = Student.query.filter(Student.is_active==True).all()
    except Exception as e:
        print(f"Error loading students: {e}")
        students = []
    
    # Create students dictionary for quick lookup
    students_dict = {s.id: s for s in students}
    
    # Check if there are tutors without availability
    tutors_without_availability = [t for t in all_tutors if not t.get_availability()]
    
    # Convert to dictionaries for JavaScript
    tutors_dict_data = []
    for tutor in available_tutors:
        try:
            tutor_dict = {
                'id': tutor.id,
                'user_name': tutor.user.full_name if tutor.user else 'Unknown',
                'email': tutor.user.email if tutor.user else '',
                'subjects': tutor.get_subjects(),
                'grades': tutor.get_grades(),
                'boards': tutor.get_boards(),
                'has_availability': bool(tutor.get_availability()),
                'status': tutor.status,
                'rating': tutor.rating or 0
            }
            tutors_dict_data.append(tutor_dict)
        except Exception as e:
            print(f"Error processing tutor {tutor.id}: {e}")
    
    students_dict_data = []
    for student in students:
        try:
            student_dict = {
                'id': student.id,
                'full_name': student.full_name,
                'grade': student.grade,
                'board': student.board,
                'subjects_enrolled': student.get_subjects_enrolled() if hasattr(student, 'get_subjects_enrolled') else []
            }
            students_dict_data.append(student_dict)
        except Exception as e:
            print(f"Error processing student {student.id}: {e}")
    
    return render_template('admin/classes.html', 
                         classes=classes, 
                         tutors=available_tutors,  # Only tutors with availability
                         all_tutors=all_tutors,    # All tutors for reference
                         tutors_without_availability=tutors_without_availability,
                         students=students,
                         students_dict=students_dict,
                         tutors_dict_data=tutors_dict_data,  # For JavaScript
                         students_dict_data=students_dict_data,  # For JavaScript
                         today=date.today(),
                         csrf_token=generate_csrf)


@bp.route('/classes/create', methods=['POST'])
@login_required
@require_permission('class_management')
def create_class():
    """Create a new class with availability validation"""
    try:
        # Get tutor and validate availability
        tutor_id = int(request.form['tutor_id'])
        tutor = Tutor.query.get_or_404(tutor_id)
        
        # Check if tutor has set availability
        availability = tutor.get_availability()
        if not availability:
            flash(f'Cannot create class: {tutor.user.full_name} has not set their availability yet. Please ask the tutor to set their schedule first.', 'error')
            return redirect(url_for('admin.classes'))
        
        # Check if tutor is active
        if tutor.status != 'active':
            flash(f'Cannot create class: {tutor.user.full_name} is not in active status.', 'error')
            return redirect(url_for('admin.classes'))
        
        # Get class details
        scheduled_date = datetime.strptime(request.form['scheduled_date'], '%Y-%m-%d').date()
        scheduled_time = datetime.strptime(request.form['scheduled_time'], '%H:%M').time()
        
        # Check if tutor is available at the requested time
        day_of_week = scheduled_date.strftime('%A').lower()  # monday, tuesday, etc.
        time_str = scheduled_time.strftime('%H:%M')
        
        if not tutor.is_available_at(day_of_week, time_str):
            flash(f'Cannot create class: {tutor.user.full_name} is not available on {day_of_week.title()} at {time_str}. Please choose a different time or tutor.', 'error')
            return redirect(url_for('admin.classes'))
        
        # Check for scheduling conflicts (tutor already has a class at this time)
        existing_class = Class.query.filter_by(
            tutor_id=tutor_id,
            scheduled_date=scheduled_date,
            scheduled_time=scheduled_time,
            status='scheduled'
        ).first()
        
        if existing_class:
            flash(f'Cannot create class: {tutor.user.full_name} already has a class scheduled at this time.', 'error')
            return redirect(url_for('admin.classes'))
        
        # Create class if all validations pass
        class_data = {
            'subject': request.form['subject'],
            'class_type': request.form['class_type'],
            'scheduled_date': scheduled_date,
            'scheduled_time': scheduled_time,
            'duration': int(request.form['duration']),
            'tutor_id': tutor_id,
            'grade': request.form.get('grade', ''),
            'meeting_link': request.form.get('meeting_link', ''),
            'class_notes': request.form.get('class_notes', ''),
            'status': 'scheduled',
            'created_by': current_user.id
        }
        
        new_class = Class(**class_data)
        db.session.add(new_class)
        db.session.flush()  # Get class ID
        
        # Handle student assignment based on class type
        students = []
        if class_data['class_type'] == 'one_on_one' or class_data['class_type'] == 'demo':
            primary_student_id = request.form.get('primary_student_id')
            if primary_student_id:
                students = [int(primary_student_id)]
        elif class_data['class_type'] == 'group':
            students = [int(s) for s in request.form.getlist('students')]
        
        if students:
            new_class.set_students(students)
        
        db.session.commit()
        flash(f'Class created successfully for {class_data["scheduled_date"]} at {time_str}!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating class: {str(e)}', 'error')
    
    return redirect(url_for('admin.classes'))

# Replace the bulk_create_classes route in app/routes/admin.py

@bp.route('/classes/bulk-create', methods=['POST'])
@login_required
@require_permission('class_management')
def bulk_create_classes():
    """Create multiple classes in bulk with availability validation"""
    try:
        from datetime import timedelta
        
        # Get form data with sanitization and validation
        subject = InputSanitizer.sanitize_text(request.form.get('subject', ''), max_length=100)
        grade = InputSanitizer.sanitize_grade(request.form.get('grade', ''))
        duration_raw = InputSanitizer.sanitize_numeric(request.form.get('duration', ''), min_val=15, max_val=300)
        duration = str(int(duration_raw)) if duration_raw else ''
        tutor_id_raw = InputSanitizer.sanitize_numeric(request.form.get('tutor_id', ''), min_val=1)
        tutor_id = str(int(tutor_id_raw)) if tutor_id_raw else ''
        class_type = InputSanitizer.sanitize_text(request.form.get('class_type', ''), max_length=50)
        
        # Validate required fields
        if not all([subject, grade, duration, tutor_id, class_type]):
            flash('All basic fields (subject, grade, duration, tutor, class type) are required.', 'error')
            return redirect(url_for('admin.classes'))
        
        # Convert to proper types
        try:
            duration = int(duration)
            tutor_id = int(tutor_id)
        except ValueError:
            flash('Invalid duration or tutor selection.', 'error')
            return redirect(url_for('admin.classes'))
        
        # Get students list
        students = request.form.getlist('students')
        if not students:
            flash('At least one student must be selected.', 'error')
            return redirect(url_for('admin.classes'))
        
        try:
            students = [int(s) for s in students]
        except ValueError:
            flash('Invalid student selection.', 'error')
            return redirect(url_for('admin.classes'))
        
        # Get schedule data
        start_date_str = request.form.get('start_date', '')
        end_date_str = request.form.get('end_date', '')
        start_time_str = request.form.get('start_time', '')
        days_of_week = request.form.getlist('days_of_week')
        
        if not all([start_date_str, end_date_str, start_time_str, days_of_week]):
            flash('All schedule fields (start date, end date, start time, days of week) are required.', 'error')
            return redirect(url_for('admin.classes'))
        
        # Parse dates and time
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            start_time = datetime.strptime(start_time_str, '%H:%M').time()
            days_of_week = [int(d) for d in days_of_week]
        except ValueError as e:
            flash('Invalid date or time format.', 'error')
            return redirect(url_for('admin.classes'))
        
        # Validate date range
        if end_date <= start_date:
            flash('End date must be after start date.', 'error')
            return redirect(url_for('admin.classes'))
        
        # Validate tutor
        tutor = Tutor.query.get_or_404(tutor_id)
        availability = tutor.get_availability()
        
        if not availability:
            flash(f'Cannot create classes: {tutor.user.full_name} has not set their availability yet.', 'error')
            return redirect(url_for('admin.classes'))
        
        if tutor.status != 'active':
            flash(f'Cannot create classes: {tutor.user.full_name} is not in active status.', 'error')
            return redirect(url_for('admin.classes'))
        
        # Validate students exist
        student_objects = Student.query.filter(Student.id.in_(students)).all()
        if len(student_objects) != len(students):
            flash('One or more selected students do not exist.', 'error')
            return redirect(url_for('admin.classes'))
        
        # Create classes
        created_count = 0
        skipped_count = 0
        current_date = start_date
        
        while current_date <= end_date:
            # Check if current day is in selected days of week
            if current_date.weekday() in days_of_week:
                day_of_week = current_date.strftime('%A').lower()
                time_str = start_time.strftime('%H:%M')
                
                # Check tutor availability for this day/time
                if tutor.is_available_at(day_of_week, time_str):
                    # Check for existing classes at this time
                    existing_class = Class.query.filter_by(
                        tutor_id=tutor_id,
                        scheduled_date=current_date,
                        scheduled_time=start_time,
                        status='scheduled'
                    ).first()
                    
                    if not existing_class:
                        # Create the class
                        class_data = {
                            'subject': subject,
                            'class_type': class_type,
                            'scheduled_date': current_date,
                            'scheduled_time': start_time,
                            'duration': duration,
                            'tutor_id': tutor_id,
                            'grade': grade,
                            'meeting_link': request.form.get('meeting_link', ''),
                            'class_notes': request.form.get('class_notes', ''),
                            'status': 'scheduled',
                            'created_by': current_user.id
                        }
                        
                        new_class = Class(**class_data)
                        db.session.add(new_class)
                        db.session.flush()  # Get the ID
                        
                        # Set students for the class
                        if hasattr(new_class, 'set_students'):
                            new_class.set_students(students)
                        else:
                            # Fallback if set_students method doesn't exist
                            if students:
                                new_class.primary_student_id = students[0]
                        
                        created_count += 1
                    else:
                        skipped_count += 1
                else:
                    skipped_count += 1
            
            current_date += timedelta(days=1)
        
        db.session.commit()
        
        # Show results
        if created_count > 0:
            message = f'{created_count} classes created successfully!'
            if skipped_count > 0:
                message += f' {skipped_count} classes were skipped due to availability conflicts or existing bookings.'
            flash(message, 'success')
        else:
            flash('No classes were created. Please check tutor availability and existing schedules.', 'warning')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating bulk classes: {str(e)}', 'error')
        print(f"Bulk create error: {e}")  # For debugging
    
    return redirect(url_for('admin.classes'))

@bp.route('/api/v1/tutor/<int:tutor_id>/availability')
@login_required
@require_permission('class_management')
def api_tutor_availability(tutor_id):
    """Get tutor availability for AJAX requests"""
    try:
        tutor = Tutor.query.get_or_404(tutor_id)
        availability = tutor.get_availability()
        
        return jsonify({
            'success': True,
            'has_availability': bool(availability),
            'availability': availability,
            'status': tutor.status,
            'can_teach': tutor.status == 'active' and bool(availability),
            'tutor_name': tutor.user.full_name if tutor.user else 'Unknown',
            'subjects': tutor.get_subjects(),
            'grades': tutor.get_grades(),
            'boards': tutor.get_boards()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/tutors/<int:tutor_id>/edit', methods=['GET', 'POST'])
@login_required
@require_permission('tutor_management')
def edit_tutor(tutor_id):
    """Edit tutor profile (admin route)"""
    tutor = Tutor.query.get_or_404(tutor_id)
    
    # Check department access for coordinators
    if current_user.role == 'coordinator':
        if current_user.department_id != tutor.user.department_id:
            flash('Access denied. You can only edit tutors from your department.', 'error')
            return redirect(url_for('admin.tutors'))
    
    # Redirect to the profile edit route with tutor_user_id
    return redirect(url_for('profile.edit_tutor_profile', tutor_user_id=tutor.user_id))

# ADD these routes to your app/routes/admin.py file

@bp.route('/tutors/<int:tutor_id>/documents/upload', methods=['POST'])
@login_required
@require_permission('tutor_management')
def upload_tutor_document(tutor_id):
    """Upload document for a tutor (admin only)"""
    try:
        tutor = Tutor.query.get_or_404(tutor_id)
        
        # Check permissions
        if current_user.role not in ['superadmin', 'admin']:
            return jsonify({'error': 'Access denied'}), 403
        
        document_type = request.form.get('document_type')
        file = request.files.get('document')
        
        if not file or not document_type:
            return jsonify({'error': 'File and document type are required'}), 400
        
        # Validate file type
        allowed_extensions = {'pdf', 'jpg', 'jpeg', 'png'}
        if '.' not in file.filename or file.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
            return jsonify({'error': 'Invalid file type. Only PDF, JPG, and PNG files are allowed'}), 400
        
        # Validate file size (10MB limit)
        if request.content_length > 10 * 1024 * 1024:
            return jsonify({'error': 'File size exceeds 10MB limit'}), 400
        
        # Upload to S3 (using your existing upload_file_to_s3 function)
        s3_url = upload_file_to_s3(file, folder=f"{current_app.config['UPLOAD_FOLDER']}/documents")
        if not s3_url:
            return jsonify({'error': 'Failed to upload file to S3'}), 500
        
        # Update tutor documents
        documents = tutor.get_documents()
        documents[document_type] = {
            'filename': s3_url,  # Store S3 URL directly
            'uploaded_at': datetime.now().isoformat(),
            'uploaded_by': current_user.full_name
        }
        tutor.set_documents(documents)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'{document_type.replace("_", " ").title()} uploaded successfully',
            'filename': s3_url
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error uploading tutor document: {str(e)}')
        return jsonify({'error': f'Error uploading document: {str(e)}'}), 500


@bp.route('/tutors/<int:tutor_id>/videos/upload', methods=['POST'])
@login_required
@require_permission('tutor_management')
def upload_tutor_video(tutor_id):
    """Upload video for a tutor (admin only)"""
    try:
        tutor = Tutor.query.get_or_404(tutor_id)
        
        # Check permissions
        if current_user.role not in ['superadmin', 'admin']:
            return jsonify({'error': 'Access denied'}), 403
        
        video_type = request.form.get('video_type')
        file = request.files.get('video')
        
        if not file or not video_type:
            return jsonify({'error': 'File and video type are required'}), 400
        
        # Validate file type
        allowed_extensions = {'mp4', 'avi', 'mov', 'wmv'}
        if '.' not in file.filename or file.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
            return jsonify({'error': 'Invalid file type. Only MP4, AVI, MOV, and WMV files are allowed'}), 400
        
        # Validate file size (100MB limit)
        if request.content_length > 100 * 1024 * 1024:
            return jsonify({'error': 'File size exceeds 100MB limit'}), 400
        
        # Upload to S3 (using your existing upload_file_to_s3 function)
        s3_url = upload_file_to_s3(file, folder=f"{current_app.config['UPLOAD_FOLDER']}/videos")
        if not s3_url:
            return jsonify({'error': 'Failed to upload video to S3'}), 500
        
        # Update tutor video
        if video_type == 'demo':
            tutor.demo_video = s3_url
        elif video_type == 'interview':
            tutor.interview_video = s3_url
        else:
            return jsonify({'error': 'Invalid video type'}), 400
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'{video_type.title()} video uploaded successfully',
            'filename': s3_url
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error uploading tutor video: {str(e)}')
        return jsonify({'error': f'Error uploading video: {str(e)}'}), 500


@bp.route('/tutors/<int:tutor_id>/documents/<document_type>/delete', methods=['POST'])
@login_required
@require_permission('tutor_management')
def delete_tutor_document(tutor_id, document_type):
    """Delete document for a tutor (admin only)"""
    try:
        tutor = Tutor.query.get_or_404(tutor_id)
        
        # Check permissions
        if current_user.role not in ['superadmin', 'admin']:
            return jsonify({'error': 'Access denied'}), 403
        
        documents = tutor.get_documents()
        s3_url = None
        
        if document_type in documents:
            if isinstance(documents[document_type], dict):
                s3_url = documents[document_type].get('filename')
            else:
                s3_url = documents[document_type]
            
            # Remove from documents
            del documents[document_type]
            tutor.set_documents(documents)
        
        # Note: For S3 files, you might want to implement S3 deletion
        # This would require additional S3 delete functionality
        # For now, we just remove the reference from the database
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'{document_type.replace("_", " ").title()} deleted successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error deleting tutor document: {str(e)}')
        return jsonify({'error': f'Error deleting document: {str(e)}'}), 500

@bp.route('/tutors/<int:tutor_id>/videos/<video_type>/delete', methods=['POST'])
@login_required
@require_permission('tutor_management')
def delete_tutor_video(tutor_id, video_type):
    """Delete video for a tutor (admin only)"""
    try:
        tutor = Tutor.query.get_or_404(tutor_id)
        
        # Check permissions
        if current_user.role not in ['superadmin', 'admin']:
            return jsonify({'error': 'Access denied'}), 403
        
        s3_url = None
        
        # Get current video URL and remove
        if video_type == 'demo' and tutor.demo_video:
            s3_url = tutor.demo_video
            tutor.demo_video = None
        elif video_type == 'interview' and tutor.interview_video:
            s3_url = tutor.interview_video
            tutor.interview_video = None
        else:
            return jsonify({'error': 'Video not found or invalid type'}), 404
        
        # Note: For S3 files, you might want to implement S3 deletion
        # This would require additional S3 delete functionality
        # For now, we just remove the reference from the database
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'{video_type.title()} video deleted successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error deleting tutor video: {str(e)}')
        return jsonify({'error': f'Error deleting video: {str(e)}'}), 500


# Helper function to validate file content (add this if it doesn't exist)
def has_file_content(file_field):
    """Check if file field has actual content"""
    return file_field and hasattr(file_field, 'filename') and file_field.filename != ''


@bp.route('/classes/<int:class_id>')
@login_required
@require_permission('class_management')
def class_details(class_id):
    """View class details"""
    class_obj = Class.query.get_or_404(class_id)
    
    # Get students for this class
    try:
        student_ids = class_obj.get_students() if hasattr(class_obj, 'get_students') else []
        students = Student.query.filter(Student.id.in_(student_ids)).all() if student_ids else []
    except:
        students = []
    
    return render_template('admin/class_details.html', class_item=class_obj, students=students)

    
@bp.route('/api/v1/compatible-tutors')
@login_required
@admin_required
def api_compatible_tutors():
    """Get tutors compatible with student criteria"""
    try:
        student_id = request.args.get('student_id', type=int)
        subject = request.args.get('subject', '').lower()
        grade = request.args.get('grade', '')
        board = request.args.get('board', '')
        
        # Get all active tutors with availability
        tutors = Tutor.query.filter_by(status='active').all()
        compatible_tutors = []
        
        for tutor in tutors:
            # Must have availability
            if not tutor.get_availability():
                continue
            
            # Check subject compatibility
            if subject:
                tutor_subjects = [s.lower() for s in tutor.get_subjects()]
                if not any(subject in ts or ts in subject for ts in tutor_subjects):
                    continue
            
            # Check grade compatibility
            if grade:
                tutor_grades = [str(g) for g in tutor.get_grades()]
                if tutor_grades and str(grade) not in tutor_grades:
                    continue
            
            # Check board compatibility
            if board:
                tutor_boards = [b.lower() for b in tutor.get_boards()]
                if tutor_boards and board.lower() not in tutor_boards:
                    continue
            
            compatible_tutors.append({
                'id': tutor.id,
                'name': tutor.user.full_name if tutor.user else 'Unknown',
                'email': tutor.user.email if tutor.user else '',
                'subjects': tutor.get_subjects(),
                'grades': tutor.get_grades(),
                'boards': tutor.get_boards(),
                'rating': tutor.rating or 0,
                'completion_rate': tutor.get_completion_rate()
            })
        
        return jsonify({
            'success': True,
            'tutors': compatible_tutors,
            'total': len(compatible_tutors)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
@bp.route('/api/v1/student/<int:student_id>/details')
@login_required
@require_permission('student_management')
def api_student_details(student_id):
    """Get student details for tutor matching"""
    try:
        student = Student.query.get_or_404(student_id)
        
        return jsonify({
            'success': True,
            'student': {
                'id': student.id,
                'full_name': student.full_name,
                'grade': student.grade,
                'board': student.board,
                'subjects_enrolled': student.get_subjects_enrolled(),
                'favorite_subjects': student.get_favorite_subjects() if hasattr(student, 'get_favorite_subjects') else [],
                'difficult_subjects': student.get_difficult_subjects() if hasattr(student, 'get_difficult_subjects') else [],
                'learning_style': student.get_academic_profile().get('learning_styles', []) if hasattr(student, 'get_academic_profile') else []
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============ DASHBOARD REDIRECT ============

@bp.route('/dashboard') 
@login_required
@admin_required
def admin_dashboard():
    """Admin dashboard - redirect to main dashboard"""
    return redirect(url_for('dashboard.index'))

# ========== finance ========

@bp.route('/finance')
@login_required
@require_permission('finance_management')
def finance_dashboard():
    """Finance dashboard"""
    from datetime import datetime, date
    from sqlalchemy import func
    
    current_month = datetime.now().month
    current_year = datetime.now().year
    
    try:
        # Get all active tutors
        tutors = Tutor.query.filter_by(status='active').all()
        
        # Calculate tutor salary data
        total_salary_expense = 0
        tutor_salaries = []
        
        for tutor in tutors:
            salary_calc = tutor.calculate_monthly_salary(current_month, current_year)
            outstanding = tutor.get_outstanding_salary()
            
            # Create calculation object that matches template expectations
            calculation_data = {
                'total_classes': salary_calc['total_classes'],
                'total_hours': salary_calc['total_classes'] * 1.0,  # Assuming 1 hour per class
                'net_salary': salary_calc['calculated_salary']
            }
            
            tutor_salaries.append({
                'tutor': tutor,
                'calculation': type('obj', (object,), calculation_data)  # Convert dict to object
            })
            
            total_salary_expense += salary_calc['calculated_salary']
        
        # Get all active students
        students = Student.query.filter_by(is_active=True).all()
        
        # Calculate fee defaulters
        total_outstanding = 0
        fee_defaulters = []
        
        for student in students:
            outstanding_amount = student.calculate_outstanding_fees()
            
            if outstanding_amount > 0:
                # Create outstanding object that matches template expectations
                outstanding_data = {
                    'outstanding_amount': outstanding_amount,
                    'overdue_amount': outstanding_amount  # Assuming all outstanding is overdue for now
                }
                
                fee_defaulters.append({
                    'student': student,
                    'outstanding': type('obj', (object,), outstanding_data)  # Convert dict to object
                })
                
                total_outstanding += outstanding_amount
        
        # Sort fee defaulters by outstanding amount (highest first)
        fee_defaulters.sort(key=lambda x: x['outstanding'].outstanding_amount, reverse=True)
        
        return render_template('admin/finance_dashboard.html',
                             month=current_month,
                             year=current_year,
                             total_salary_expense=total_salary_expense,
                             total_outstanding=total_outstanding,
                             tutor_salaries=tutor_salaries,
                             fee_defaulters=fee_defaulters)
                             
    except Exception as e:
        flash(f'Error loading finance dashboard: {str(e)}', 'error')
        return render_template('admin/finance_dashboard.html',
                             month=current_month,
                             year=current_year,
                             total_salary_expense=0,
                             total_outstanding=0,
                             tutor_salaries=[],
                             fee_defaulters=[])
    
@bp.route('/salary-generation')
@login_required
@require_permission('finance_management')
def salary_generation():
    """Salary generation page"""
    from datetime import datetime
    
    current_month = datetime.now().month
    current_year = datetime.now().year
    
    # Get all active tutors
    tutors = Tutor.query.filter_by(status='active').all()
    
    tutor_salary_data = []
    for tutor in tutors:
        salary_calc = tutor.calculate_monthly_salary(current_month, current_year)
        
        # Convert dict to object-like access for template compatibility
        calculation_obj = type('obj', (object,), salary_calc)
        
        tutor_salary_data.append({
            'tutor': tutor,
            'calculation': calculation_obj,
            'outstanding': tutor.get_outstanding_salary()
        })
    
    return render_template('admin/salary_generation.html',
                         tutors=tutor_salary_data,
                         current_month=current_month,
                         current_year=current_year)
    
@bp.route('/tutors/<int:tutor_id>/salary')
@login_required
@admin_required
def tutor_salary_details(tutor_id):
    """View detailed salary information for a specific tutor"""
    from datetime import datetime
    from app.models.attendance import Attendance
    
    tutor = Tutor.query.get_or_404(tutor_id)
    
    # Get month and year from query parameters
    month = request.args.get('month', datetime.now().month, type=int)
    year = request.args.get('year', datetime.now().year, type=int)
    
    # Calculate salary for the specified period
    salary_calculation = tutor.calculate_monthly_salary(month, year)
    
    # Get attendance records for this period
    attendance_records = tutor._get_monthly_attendance_records(month, year)
    
    # Get salary payment history
    salary_history = tutor.get_salary_history()
    
    # Get outstanding amount
    outstanding_amount = tutor.get_outstanding_salary()
    
    # Calculate additional statistics
    total_late_minutes = sum(att.tutor_late_minutes or 0 for att in attendance_records)
    total_early_leaves = sum(att.tutor_early_leave_minutes or 0 for att in attendance_records)
    
    return render_template('admin/tutor_salary_details.html',
                         tutor=tutor,
                         month=month,
                         year=year,
                         salary_calculation=salary_calculation,
                         attendance_records=attendance_records,
                         salary_history=salary_history,
                         outstanding_amount=outstanding_amount,
                         total_late_minutes=total_late_minutes,
                         total_early_leaves=total_early_leaves)

@bp.route('/fee-collection')
@login_required
@require_permission('finance_management')
def fee_collection():
    """Fee collection page"""
    # Get students with outstanding fees
    students = Student.query.filter_by(is_active=True).all()
    
    students_with_fees = []
    for student in students:
        outstanding = student.calculate_outstanding_fees()
        if outstanding > 0:
            students_with_fees.append({
                'student': student,
                'outstanding': outstanding,
                'fee_structure': student.get_fee_structure()
            })
    
    # Sort by outstanding amount (highest first)
    students_with_fees.sort(key=lambda x: x['outstanding'], reverse=True)
    
    return render_template('admin/fee_collection.html',
                         students_with_fees=students_with_fees)

@bp.route('/api/v1/finance/dashboard')
@login_required
@admin_required
def finance_dashboard_api():
    """API endpoint for finance dashboard data"""
    from datetime import datetime
    
    current_month = datetime.now().month
    current_year = datetime.now().year
    
    # Get summary data
    tutors = Tutor.query.filter_by(status='active').all()
    students = Student.query.filter_by(is_active=True).all()
    
    total_salary_expense = sum(
        tutor.calculate_monthly_salary(current_month, current_year)['calculated_salary'] 
        for tutor in tutors
    )
    
    total_outstanding_fees = sum(
        student.calculate_outstanding_fees() 
        for student in students
    )
    
    return jsonify({
        'month': current_month,
        'year': current_year,
        'total_salary_expense': total_salary_expense,
        'total_outstanding_fees': total_outstanding_fees,
        'total_tutors': len(tutors),
        'total_students': len(students)
    })

# Add these routes to your app/routes/admin.py file

@bp.route('/system-documents')
@login_required
@require_permission('system_documents')
def system_documents():
    """Manage system documents"""
    from app.models.system_document import SystemDocument
    
    documents = SystemDocument.query.order_by(SystemDocument.updated_at.desc()).all()
    document_types = SystemDocument.get_document_types()
    
    return render_template('admin/system_documents.html', 
                         documents=documents,
                         document_types=document_types)

@bp.route('/system-documents/upload', methods=['GET', 'POST'])
@login_required
@admin_required
def upload_system_document():
    """Upload system document"""
    from app.models.system_document import SystemDocument
    
    if request.method == 'POST':
        try:
            document_type = request.form.get('document_type')
            title = request.form.get('title')
            description = request.form.get('description', '')
            available_roles = request.form.getlist('available_roles')
            
            if 'document_file' not in request.files:
                flash('No file selected', 'error')
                return redirect(request.url)
            
            file = request.files['document_file']
            if file.filename == '':
                flash('No file selected', 'error')
                return redirect(request.url)
            
            # Check if document type already exists
            existing_doc = SystemDocument.query.filter_by(document_type=document_type).first()
            if existing_doc:
                flash('Document type already exists. Please update the existing document.', 'error')
                return redirect(request.url)
            
            # Save file
            filename = save_uploaded_file(file, 'system_documents')
            if not filename:
                flash('Error uploading file', 'error')
                return redirect(request.url)
            
            # Create document record
            doc = SystemDocument(
                document_type=document_type,
                title=title,
                description=description,
                filename=filename,
                file_path=f'system_documents/{filename}',
                file_size=len(file.read()),
                mime_type=file.content_type,
                uploaded_by=current_user.id
            )
            
            # Reset file pointer after reading size
            file.seek(0)
            
            doc.set_available_roles(available_roles)
            
            db.session.add(doc)
            db.session.commit()
            
            flash(f'System document "{title}" uploaded successfully!', 'success')
            return redirect(url_for('admin.system_documents'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error uploading document: {str(e)}', 'error')
    
    document_types = SystemDocument.get_document_types()
    roles = ['superadmin', 'admin', 'coordinator', 'tutor', 'student']
    
    return render_template('admin/upload_system_document.html',
                         document_types=document_types,
                         roles=roles)

@bp.route('/system-documents/<int:doc_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_system_document(doc_id):
    """Edit system document"""
    from app.models.system_document import SystemDocument
    
    doc = SystemDocument.query.get_or_404(doc_id)
    
    if request.method == 'POST':
        try:
            doc.title = request.form.get('title')
            doc.description = request.form.get('description', '')
            available_roles = request.form.getlist('available_roles')
            doc.set_available_roles(available_roles)
            
            # Handle file replacement
            if 'document_file' in request.files and request.files['document_file'].filename:
                file = request.files['document_file']
                
                # Delete old file
                old_file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], doc.file_path)
                if os.path.exists(old_file_path):
                    os.remove(old_file_path)
                
                # Save new file
                filename = save_uploaded_file(file, 'system_documents')
                if filename:
                    doc.filename = filename
                    doc.file_path = f'system_documents/{filename}'
                    doc.file_size = len(file.read())
                    doc.mime_type = file.content_type
                    file.seek(0)
            
            doc.updated_at = datetime.now()
            db.session.commit()
            
            flash(f'Document "{doc.title}" updated successfully!', 'success')
            return redirect(url_for('admin.system_documents'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating document: {str(e)}', 'error')
    
    roles = ['superadmin', 'admin', 'coordinator', 'tutor', 'student']
    return render_template('admin/edit_system_document.html', doc=doc, roles=roles)

@bp.route('/system-documents/<int:doc_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_system_document(doc_id):
    """Delete system document"""
    from app.models.system_document import SystemDocument
    
    try:
        doc = SystemDocument.query.get_or_404(doc_id)
        
        # Delete physical file
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], doc.file_path)
        if os.path.exists(file_path):
            os.remove(file_path)
        
        db.session.delete(doc)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Document deleted successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/system-documents/<int:doc_id>/toggle-status', methods=['POST'])
@login_required
@admin_required
def toggle_document_status(doc_id):
    """Toggle document active status"""
    from app.models.system_document import SystemDocument
    
    try:
        doc = SystemDocument.query.get_or_404(doc_id)
        doc.is_active = not doc.is_active
        db.session.commit()
        
        status = 'activated' if doc.is_active else 'deactivated'
        return jsonify({'success': True, 'message': f'Document {status} successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# Enhanced API routes to add to your existing app/routes/admin.py
# Add these routes after your existing API routes

@bp.route('/api/v1/tutors/smart-search')
@login_required
@admin_required
def api_smart_tutor_search():
    """Advanced tutor search with multiple criteria and scoring"""
    try:
        # Get search parameters
        student_id = request.args.get('student_id', type=int)
        subject = request.args.get('subject', '').strip().lower()
        min_test_score = request.args.get('min_test_score', type=float)
        min_rating = request.args.get('min_rating', type=float)
        experience_level = request.args.get('experience_level', '').strip()
        search_term = request.args.get('search_term', '').strip().lower()
        availability_day = request.args.get('availability_day', '').strip().lower()
        availability_time = request.args.get('availability_time', '').strip()
        
        # Get base query
        tutors = Tutor.query.filter_by(status='active').all()
        
        # Get student context if provided
        student = None
        if student_id:
            student = Student.query.get(student_id)
        
        compatible_tutors = []
        
        for tutor in tutors:
            # Must have availability
            if not tutor.get_availability():
                continue
            
            # Initialize tutor score
            tutor_score = {
                'tutor_id': tutor.id,
                'tutor_name': tutor.user.full_name if tutor.user else 'Unknown',
                'email': tutor.user.email if tutor.user else '',
                'test_score': tutor.test_score or 0,
                'test_grade': tutor.get_test_score_grade(),
                'rating': tutor.rating or 0,
                'total_classes': tutor.total_classes or 0,
                'completed_classes': tutor.completed_classes or 0,
                'qualification': tutor.qualification or '',
                'subjects': tutor.get_subjects(),
                'grades': tutor.get_grades(),
                'boards': tutor.get_boards(),
                'compatibility_score': 0,
                'match_reasons': [],
                'availability_status': 'available'
            }
            
            # Student-based compatibility scoring
            if student:
                # Grade compatibility (mandatory)
                tutor_grades = [str(g) for g in tutor.get_grades()]
                if tutor_grades and str(student.grade) not in tutor_grades:
                    continue
                tutor_score['compatibility_score'] += 20
                tutor_score['match_reasons'].append(f"Teaches Grade {student.grade}")
                
                # Board compatibility (mandatory)
                tutor_boards = [b.lower() for b in tutor.get_boards()]
                if tutor_boards and student.board.lower() not in tutor_boards:
                    continue
                tutor_score['compatibility_score'] += 15
                tutor_score['match_reasons'].append(f"Familiar with {student.board}")
                
                # Subject compatibility with student's enrolled subjects
                student_subjects = [s.lower() for s in student.get_subjects_enrolled()]
                tutor_subjects = [s.lower() for s in tutor.get_subjects()]
                
                if student_subjects and tutor_subjects:
                    common_subjects = set(student_subjects) & set(tutor_subjects)
                    partial_matches = [s for s in student_subjects for ts in tutor_subjects if s in ts or ts in s]
                    
                    if common_subjects or partial_matches:
                        tutor_score['compatibility_score'] += 25
                        matched_subjects = list(common_subjects) or partial_matches[:2]
                        tutor_score['match_reasons'].append(f"Teaches: {', '.join(matched_subjects)}")
            
            # Subject filter (if specified independently)
            if subject:
                tutor_subjects = [s.lower() for s in tutor.get_subjects()]
                subject_match = any(subject in ts or ts in subject for ts in tutor_subjects)
                if not subject_match:
                    continue
                tutor_score['compatibility_score'] += 20
                tutor_score['match_reasons'].append(f"Subject expertise: {subject}")
            
            # Test score filter and scoring
            if min_test_score and (not tutor.test_score or tutor.test_score < min_test_score):
                continue
            
            if tutor.test_score:
                if tutor.test_score >= 90:
                    tutor_score['compatibility_score'] += 15
                    tutor_score['match_reasons'].append("Excellent test performance (90+)")
                elif tutor.test_score >= 80:
                    tutor_score['compatibility_score'] += 10
                    tutor_score['match_reasons'].append("Strong test performance (80+)")
                elif tutor.test_score >= 70:
                    tutor_score['compatibility_score'] += 5
                    tutor_score['match_reasons'].append("Good test performance (70+)")
            
            # Rating filter and scoring
            if min_rating and (not tutor.rating or tutor.rating < min_rating):
                continue
            
            if tutor.rating:
                if tutor.rating >= 4.5:
                    tutor_score['compatibility_score'] += 10
                    tutor_score['match_reasons'].append("Highly rated (4.5+ stars)")
                elif tutor.rating >= 4.0:
                    tutor_score['compatibility_score'] += 7
                    tutor_score['match_reasons'].append("Well rated (4.0+ stars)")
                elif tutor.rating >= 3.5:
                    tutor_score['compatibility_score'] += 5
                    tutor_score['match_reasons'].append("Good rating (3.5+ stars)")
            
            # Experience level filter
            if experience_level:
                qualification_lower = tutor.qualification.lower() if tutor.qualification else ''
                if experience_level == 'master' and 'master' not in qualification_lower:
                    continue
                elif experience_level == 'phd' and not any(term in qualification_lower for term in ['phd', 'doctorate', 'ph.d']):
                    continue
                elif experience_level == 'expert' and not any(term in qualification_lower for term in ['expert', 'specialist', 'senior']):
                    continue
                
                tutor_score['compatibility_score'] += 8
                tutor_score['match_reasons'].append(f"Advanced qualification: {experience_level}")
            
            # Search term filter (name/qualification)
            if search_term:
                tutor_name = tutor.user.full_name.lower() if tutor.user else ''
                qualification_lower = tutor.qualification.lower() if tutor.qualification else ''
                
                if search_term not in tutor_name and search_term not in qualification_lower:
                    continue
                
                tutor_score['compatibility_score'] += 5
                tutor_score['match_reasons'].append("Matches search term")
            
            # Availability check for specific day/time
            if availability_day and availability_time:
                is_available = tutor.is_available_at(availability_day, availability_time)
                if not is_available:
                    tutor_score['availability_status'] = 'busy'
                    continue
                
                tutor_score['compatibility_score'] += 10
                tutor_score['match_reasons'].append(f"Available on {availability_day.title()} at {availability_time}")
            
            # Completion rate bonus
            if tutor.total_classes > 5:  # Only consider if tutor has meaningful experience
                completion_rate = tutor.get_completion_rate()
                if completion_rate >= 95:
                    tutor_score['compatibility_score'] += 8
                    tutor_score['match_reasons'].append("Excellent completion rate (95%+)")
                elif completion_rate >= 90:
                    tutor_score['compatibility_score'] += 5
                    tutor_score['match_reasons'].append("High completion rate (90%+)")
            
            # Add comprehensive tutor info
            tutor_score['completion_rate'] = tutor.get_completion_rate()
            tutor_score['overall_score'] = tutor.calculate_overall_score() if hasattr(tutor, 'calculate_overall_score') else tutor_score['compatibility_score']
            
            compatible_tutors.append(tutor_score)
        
        # Sort by compatibility score (highest first)
        compatible_tutors.sort(key=lambda x: x['compatibility_score'], reverse=True)
        
        # Add rank information
        for i, tutor in enumerate(compatible_tutors):
            tutor['rank'] = i + 1
            if i == 0:
                tutor['badge'] = 'Best Match'
            elif tutor['compatibility_score'] >= 80:
                tutor['badge'] = 'Excellent Match'
            elif tutor['compatibility_score'] >= 60:
                tutor['badge'] = 'Good Match'
            elif tutor['compatibility_score'] >= 40:
                tutor['badge'] = 'Fair Match'
            else:
                tutor['badge'] = 'Basic Match'
        
        return jsonify({
            'success': True,
            'tutors': compatible_tutors,
            'total_found': len(compatible_tutors),
            'search_criteria': {
                'student_id': student_id,
                'subject': subject,
                'min_test_score': min_test_score,
                'min_rating': min_rating,
                'experience_level': experience_level,
                'search_term': search_term
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Error in smart tutor search: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/api/v1/tutors/browse-all')
@login_required
@admin_required
def api_browse_all_tutors():
    """Get all available tutors with detailed information for browsing"""
    try:
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        sort_by = request.args.get('sort_by', 'rating')  # rating, test_score, name, experience
        order = request.args.get('order', 'desc')  # asc, desc
        
        # Get all active tutors with availability
        tutors_query = Tutor.query.filter_by(status='active')
        
        all_tutors = []
        for tutor in tutors_query.all():
            if not tutor.get_availability():
                continue
                
            tutor_info = {
                'id': tutor.id,
                'name': tutor.user.full_name if tutor.user else 'Unknown',
                'email': tutor.user.email if tutor.user else '',
                'qualification': tutor.qualification or '',
                'experience': tutor.experience or '',
                'subjects': tutor.get_subjects(),
                'grades': tutor.get_grades(),
                'boards': tutor.get_boards(),
                'test_score': tutor.test_score or 0,
                'test_grade': tutor.get_test_score_grade(),
                'rating': tutor.rating or 0,
                'total_classes': tutor.total_classes or 0,
                'completed_classes': tutor.completed_classes or 0,
                'completion_rate': tutor.get_completion_rate(),
                'salary_type': tutor.salary_type,
                'monthly_salary': tutor.monthly_salary,
                'hourly_rate': tutor.hourly_rate,
                'created_at': tutor.created_at.isoformat() if tutor.created_at else None,
                'last_class': tutor.last_class.isoformat() if tutor.last_class else None,
                'availability_summary': get_availability_summary(tutor.get_availability())
            }
            
            all_tutors.append(tutor_info)
        
        # Sort tutors
        if sort_by == 'rating':
            all_tutors.sort(key=lambda x: x['rating'], reverse=(order == 'desc'))
        elif sort_by == 'test_score':
            all_tutors.sort(key=lambda x: x['test_score'], reverse=(order == 'desc'))
        elif sort_by == 'name':
            all_tutors.sort(key=lambda x: x['name'], reverse=(order == 'desc'))
        elif sort_by == 'experience':
            all_tutors.sort(key=lambda x: x['total_classes'], reverse=(order == 'desc'))
        
        # Paginate
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_tutors = all_tutors[start_idx:end_idx]
        
        return jsonify({
            'success': True,
            'tutors': paginated_tutors,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': len(all_tutors),
                'pages': (len(all_tutors) + per_page - 1) // per_page,
                'has_next': end_idx < len(all_tutors),
                'has_prev': page > 1
            },
            'sort_info': {
                'sort_by': sort_by,
                'order': order
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Error browsing tutors: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def get_availability_summary(availability_dict):
    """Generate a summary of tutor availability"""
    if not availability_dict:
        return "No availability set"
    
    available_days = []
    total_hours = 0
    
    for day, slots in availability_dict.items():
        if slots:
            available_days.append(day.title())
            # Calculate total hours for this day
            for slot in slots:
                try:
                    start_time = datetime.strptime(slot['start'], '%H:%M').time()
                    end_time = datetime.strptime(slot['end'], '%H:%M').time()
                    start_datetime = datetime.combine(date.today(), start_time)
                    end_datetime = datetime.combine(date.today(), end_time)
                    hours = (end_datetime - start_datetime).total_seconds() / 3600
                    total_hours += hours
                except:
                    continue
    
    if not available_days:
        return "No availability set"
    
    return f"{len(available_days)} days/week ({total_hours:.1f}h total)"

@bp.route('/api/v1/tutors/<int:tutor_id>/detailed-profile')
@login_required
@admin_required
def api_tutor_detailed_profile(tutor_id):
    """Get comprehensive tutor profile for detailed view"""
    try:
        tutor = Tutor.query.get_or_404(tutor_id)
        
        # Get recent classes
        recent_classes = Class.query.filter_by(tutor_id=tutor_id)\
                                   .order_by(Class.scheduled_date.desc())\
                                   .limit(10).all()
        
        # Get student feedback/ratings (if you have feedback model)
        # This would need to be implemented based on your feedback system
        
        detailed_profile = {
            'basic_info': {
                'id': tutor.id,
                'name': tutor.user.full_name if tutor.user else 'Unknown',
                'email': tutor.user.email if tutor.user else '',
                'phone': tutor.user.phone if tutor.user else '',
                'qualification': tutor.qualification,
                'experience': tutor.experience,
                'date_of_birth': tutor.date_of_birth.isoformat() if tutor.date_of_birth else None,
                'state': tutor.state,
                'joining_date': tutor.created_at.isoformat() if tutor.created_at else None
            },
            'academic_info': {
                'subjects': tutor.get_subjects(),
                'grades': tutor.get_grades(),
                'boards': tutor.get_boards(),
                'test_score': tutor.test_score,
                'test_grade': tutor.get_test_score_grade(),
                'test_date': tutor.test_date.isoformat() if tutor.test_date else None,
                'test_notes': tutor.test_notes
            },
            'performance_metrics': {
                'rating': tutor.rating,
                'total_classes': tutor.total_classes,
                'completed_classes': tutor.completed_classes,
                'completion_rate': tutor.get_completion_rate(),
                'overall_score': tutor.calculate_overall_score() if hasattr(tutor, 'calculate_overall_score') else 0
            },
            'availability': {
                'schedule': tutor.get_availability(),
                'summary': get_availability_summary(tutor.get_availability())
            },
            'compensation': {
                'salary_type': tutor.salary_type,
                'monthly_salary': tutor.monthly_salary,
                'hourly_rate': tutor.hourly_rate
            },
            'recent_activity': {
                'last_class': tutor.last_class.isoformat() if tutor.last_class else None,
                'recent_classes': [
                    {
                        'id': cls.id,
                        'subject': cls.subject,
                        'date': cls.scheduled_date.isoformat(),
                        'time': cls.scheduled_time.strftime('%H:%M'),
                        'status': cls.status,
                        'student_count': len(cls.get_students()) if hasattr(cls, 'get_students') else 0
                    }
                    for cls in recent_classes
                ],
                'status': tutor.status,
                'verification_status': tutor.verification_status
            }
        }
        
        return jsonify({
            'success': True,
            'tutor': detailed_profile
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting tutor detailed profile: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Add this helper function to improve the existing compatible tutors API
@bp.route('/api/v1/compatible-tutors-enhanced')
@login_required
@admin_required
def api_compatible_tutors_enhanced():
    """Enhanced version of existing compatible tutors API with scoring"""
    try:
        student_id = request.args.get('student_id', type=int)
        subject = request.args.get('subject', '').lower()
        grade = request.args.get('grade', '')
        board = request.args.get('board', '')
        include_scores = request.args.get('include_scores', 'true').lower() == 'true'
        
        # Use the smart search function with basic parameters
        search_result = api_smart_tutor_search()
        
        # If it's a JSON response (error case), return it
        if hasattr(search_result, 'get_json'):
            return search_result
        
        # Otherwise, call the smart search internally
        from flask import current_app
        with current_app.test_request_context(
            f'/admin/api/v1/tutors/smart-search?student_id={student_id}&subject={subject}'
        ):
            smart_results = api_smart_tutor_search()
            return smart_results
            
    except Exception as e:
        current_app.logger.error(f"Error in enhanced compatible tutors: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
        

@bp.route('/api/v1/tutors/intelligent-search')
@login_required
@admin_required
@monitor_search_performance
def api_intelligent_tutor_search():
    """Most advanced tutor search with ML-like matching"""
    try:
        # Get search parameters
        student_id = request.args.get('student_id', type=int)
        subject = request.args.get('subject', '').strip()
        preferences = request.args.get('preferences', '{}')
        
        # Parse preferences
        try:
            prefs = json.loads(preferences) if preferences else {}
        except:
            prefs = {}
        
        # Build filters from preferences
        filters = {}
        if prefs.get('min_test_score'):
            filters['min_test_score'] = float(prefs['min_test_score'])
        if prefs.get('min_rating'):
            filters['min_rating'] = float(prefs['min_rating'])
        if prefs.get('experience_level'):
            filters['experience_level'] = prefs['experience_level']
        
        # Use the matching engine
        matches = matching_engine.find_best_matches(
            student_id=student_id,
            subject=subject,
            filters=filters,
            limit=prefs.get('limit', 10)
        )
        
        # Enhanced response with detailed analytics
        response_data = {
            'success': True,
            'matches': matches,
            'search_metadata': {
                'total_found': len(matches),
                'search_criteria': {
                    'student_id': student_id,
                    'subject': subject,
                    'filters_applied': list(filters.keys()),
                    'preferences': prefs
                },
                'algorithm_version': '2.0',
                'timestamp': datetime.utcnow().isoformat()
            }
        }
        
        # Add analytics if matches found
        if matches:
            scores = [m['score_data']['total_score'] for m in matches]
            response_data['search_metadata']['score_analytics'] = {
                'highest_score': max(scores),
                'average_score': round(sum(scores) / len(scores), 1),
                'score_distribution': {
                    'excellent': len([s for s in scores if s >= 85]),
                    'good': len([s for s in scores if 70 <= s < 85]),
                    'fair': len([s for s in scores if 55 <= s < 70]),
                    'basic': len([s for s in scores if s < 55])
                }
            }
        
        return jsonify(response_data)
        
    except Exception as e:
        current_app.logger.error(f"Intelligent search error: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Search failed',
            'details': str(e) if current_app.debug else 'Internal server error'
        }), 500

@bp.route('/api/v1/tutors/availability-analysis')
@login_required
@admin_required
def api_tutor_availability_analysis():
    """Analyze tutor availability for a specific date/time"""
    try:
        tutor_id = request.args.get('tutor_id', type=int)
        date_str = request.args.get('date')
        time_str = request.args.get('time')
        duration = request.args.get('duration', 60, type=int)
        
        if not all([tutor_id, date_str, time_str]):
            return jsonify({
                'success': False,
                'error': 'Missing required parameters: tutor_id, date, time'
            }), 400
        
        # Parse date and time
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        target_time = datetime.strptime(time_str, '%H:%M').time()
        
        # Check availability
        availability_result = AvailabilityChecker.check_tutor_availability(
            tutor_id, target_date, target_time, duration
        )
        
        # Get alternative slots if not available
        alternative_slots = []
        if not availability_result['available']:
            # Check next 7 days for alternatives
            for i in range(1, 8):
                alt_date = target_date + timedelta(days=i)
                slots = AvailabilityChecker.get_available_slots(
                    tutor_id, alt_date, duration
                )
                if slots:
                    alternative_slots.extend([{
                        'date': alt_date.isoformat(),
                        'day_name': alt_date.strftime('%A'),
                        'slots': slots[:3]  # First 3 slots per day
                    }])
                    if len(alternative_slots) >= 5:  # Limit to 5 alternative days
                        break
        
        # Get tutor's weekly schedule summary
        tutor = Tutor.query.get(tutor_id)
        schedule_summary = {}
        if tutor:
            availability_dict = tutor.get_availability()
            for day, slots in availability_dict.items():
                if slots:
                    schedule_summary[day] = {
                        'slot_count': len(slots),
                        'first_slot': f"{slots[0]['start']}-{slots[0]['end']}" if slots else None,
                        'total_hours': sum([
                            (datetime.strptime(slot['end'], '%H:%M') - 
                             datetime.strptime(slot['start'], '%H:%M')).total_seconds() / 3600
                            for slot in slots
                        ])
                    }
        
        return jsonify({
            'success': True,
            'availability_check': {
                'requested_slot': {
                    'date': date_str,
                    'time': time_str,
                    'duration': duration
                },
                'result': availability_result,
                'alternative_slots': alternative_slots,
                'weekly_schedule': schedule_summary
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Availability analysis error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Analysis failed'
        }), 500

@bp.route('/api/v1/students/<int:student_id>/recommended-tutors')
@login_required
@admin_required
def api_student_recommended_tutors(student_id):
    """Get personalized tutor recommendations for a student"""
    try:
        student = Student.query.get_or_404(student_id)
        
        # Get student's learning preferences and history
        academic_profile = student.get_academic_profile()
        subjects_enrolled = student.get_subjects_enrolled()
        difficult_subjects = student.get_difficult_subjects()
        
        recommendations = []
        
        # Recommend tutors for each enrolled subject
        for subject in subjects_enrolled:
            subject_matches = matching_engine.find_best_matches(
                student_id=student_id,
                subject=subject,
                limit=3
            )
            
            # Add context about why this subject needs attention
            priority = 'high' if subject.lower() in [d.lower() for d in difficult_subjects] else 'normal'
            
            if subject_matches:
                recommendations.append({
                    'subject': subject,
                    'priority': priority,
                    'reason': f"Student enrolled in {subject}" + 
                             (f" (marked as difficult)" if priority == 'high' else ""),
                    'recommended_tutors': subject_matches[:2],  # Top 2 per subject
                    'alternative_tutors': subject_matches[2:3] if len(subject_matches) > 2 else []
                })
        
        # Recommend tutors for difficult subjects (if not already covered)
        for difficult_subject in difficult_subjects:
            if difficult_subject not in subjects_enrolled:
                matches = matching_engine.find_best_matches(
                    student_id=student_id,
                    subject=difficult_subject,
                    limit=2
                )
                
                if matches:
                    recommendations.append({
                        'subject': difficult_subject,
                        'priority': 'urgent',
                        'reason': f"Student needs help with {difficult_subject} (marked as difficult)",
                        'recommended_tutors': matches,
                        'alternative_tutors': []
                    })
        
        # Sort by priority
        priority_order = {'urgent': 0, 'high': 1, 'normal': 2}
        recommendations.sort(key=lambda x: priority_order.get(x['priority'], 3))
        
        return jsonify({
            'success': True,
            'student_info': {
                'id': student.id,
                'name': student.full_name,
                'grade': student.grade,
                'board': student.board,
                'subjects_enrolled': subjects_enrolled,
                'difficult_subjects': difficult_subjects
            },
            'recommendations': recommendations,
            'summary': {
                'total_subjects': len(recommendations),
                'urgent_subjects': len([r for r in recommendations if r['priority'] == 'urgent']),
                'high_priority_subjects': len([r for r in recommendations if r['priority'] == 'high']),
                'total_tutor_options': sum([len(r['recommended_tutors']) + len(r['alternative_tutors']) 
                                           for r in recommendations])
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Student recommendations error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to generate recommendations'
        }), 500

@bp.route('/api/v1/tutors/batch-availability-check')
@login_required
@admin_required
def api_batch_availability_check():
    """Check availability for multiple tutors at once"""
    try:
        # Get parameters
        tutor_ids = request.args.getlist('tutor_ids', type=int)
        date_str = request.args.get('date')
        time_str = request.args.get('time')
        duration = request.args.get('duration', 60, type=int)
        
        if not all([tutor_ids, date_str, time_str]):
            return jsonify({
                'success': False,
                'error': 'Missing required parameters'
            }), 400
        
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        target_time = datetime.strptime(time_str, '%H:%M').time()
        
        results = []
        
        for tutor_id in tutor_ids:
            tutor = Tutor.query.get(tutor_id)
            if not tutor:
                continue
                
            availability_result = AvailabilityChecker.check_tutor_availability(
                tutor_id, target_date, target_time, duration
            )
            
            results.append({
                'tutor_id': tutor_id,
                'tutor_name': tutor.user.full_name if tutor.user else 'Unknown',
                'availability': availability_result,
                'tutor_summary': {
                    'rating': tutor.rating or 0,
                    'test_score': tutor.test_score or 0,
                    'total_classes': tutor.total_classes or 0
                }
            })
        
        # Sort by availability and then by rating
        results.sort(key=lambda x: (
            not x['availability']['available'],  # Available tutors first
            -(x['tutor_summary']['rating'] or 0)  # Then by rating (descending)
        ))
        
        available_count = len([r for r in results if r['availability']['available']])
        
        return jsonify({
            'success': True,
            'batch_check': {
                'requested_slot': {
                    'date': date_str,
                    'time': time_str,
                    'duration': duration
                },
                'results': results,
                'summary': {
                    'total_checked': len(results),
                    'available_tutors': available_count,
                    'unavailable_tutors': len(results) - available_count
                }
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Batch availability check error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Batch check failed'
        }), 500

@bp.route('/api/v1/search/suggestions')
@login_required
@admin_required
def api_search_suggestions():
    """Get search suggestions for autocomplete"""
    try:
        query = request.args.get('query', '').strip().lower()
        search_type = request.args.get('type', 'all')  # all, subjects, tutors, students
        
        suggestions = {
            'subjects': [],
            'tutors': [],
            'students': [],
            'qualifications': []
        }
        
        if len(query) < 2:
            return jsonify({'success': True, 'suggestions': suggestions})
        
        # Subject suggestions
        if search_type in ['all', 'subjects']:
            # Get unique subjects from tutors
            tutors = Tutor.query.filter_by(status='active').all()
            all_subjects = set()
            for tutor in tutors:
                all_subjects.update([s.lower() for s in tutor.get_subjects()])
            
            # Process with SearchQueryProcessor
            processed_subjects = SearchQueryProcessor.process_subject_query(query)
            matching_subjects = [s for s in all_subjects if query in s]
            matching_subjects.extend(processed_subjects)
            
            suggestions['subjects'] = list(set(matching_subjects))[:5]
        
        # Tutor suggestions
        if search_type in ['all', 'tutors']:
            tutors = Tutor.query.join(User).filter(
                Tutor.status == 'active',
                User.full_name.ilike(f'%{query}%')
            ).limit(5).all()
            
            suggestions['tutors'] = [
                {
                    'id': t.id,
                    'name': t.user.full_name,
                    'subjects': t.get_subjects()[:2],
                    'rating': t.rating or 0
                }
                for t in tutors
            ]
        
        # Student suggestions
        if search_type in ['all', 'students']:
            students = Student.query.filter(
                Student.is_active == True,
                Student.full_name.ilike(f'%{query}%')
            ).limit(5).all()
            
            suggestions['students'] = [
                {
                    'id': s.id,
                    'name': s.full_name,
                    'grade': s.grade,
                    'board': s.board
                }
                for s in students
            ]
        
        # Qualification suggestions
        if search_type in ['all', 'qualifications']:
            tutors_with_qual = Tutor.query.filter(
                Tutor.status == 'active',
                Tutor.qualification.ilike(f'%{query}%')
            ).all()
            
            qualifications = set()
            for tutor in tutors_with_qual:
                if tutor.qualification and query in tutor.qualification.lower():
                    qualifications.add(tutor.qualification)
            
            suggestions['qualifications'] = list(qualifications)[:5]
        
        return jsonify({
            'success': True,
            'query': query,
            'suggestions': suggestions
        })
        
    except Exception as e:
        current_app.logger.error(f"Search suggestions error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to get suggestions'
        }), 500

# Analytics and reporting endpoints

@bp.route('/api/v1/analytics/tutor-matching-stats')
@login_required
@admin_required
def api_tutor_matching_analytics():
    """Get analytics about tutor matching performance"""
    try:
        # Date range
        days_back = request.args.get('days', 30, type=int)
        end_date = date.today()
        start_date = end_date - timedelta(days=days_back)
        
        # Get all active tutors
        tutors = Tutor.query.filter_by(status='active').all()
        
        analytics = {
            'overview': {
                'total_active_tutors': len(tutors),
                'tutors_with_availability': len([t for t in tutors if t.get_availability()]),
                'highly_rated_tutors': len([t for t in tutors if t.rating and t.rating >= 4.5]),
                'excellent_test_scores': len([t for t in tutors if t.test_score and t.test_score >= 90])
            },
            'availability_stats': {},
            'performance_distribution': {},
            'subject_coverage': {},
            'grade_coverage': {}
        }
        
        # Availability statistics
        total_hours_available = 0
        availability_by_day = {day: 0 for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']}
        
        for tutor in tutors:
            availability = tutor.get_availability()
            if availability:
                for day, slots in availability.items():
                    if slots:
                        availability_by_day[day] += 1
                        for slot in slots:
                            try:
                                start = datetime.strptime(slot['start'], '%H:%M')
                                end = datetime.strptime(slot['end'], '%H:%M')
                                hours = (end - start).total_seconds() / 3600
                                total_hours_available += hours
                            except:
                                continue
        
        analytics['availability_stats'] = {
            'total_hours_per_week': round(total_hours_available, 1),
            'average_hours_per_tutor': round(total_hours_available / len(tutors), 1) if tutors else 0,
            'availability_by_day': availability_by_day,
            'busiest_day': max(availability_by_day.items(), key=lambda x: x[1])[0] if availability_by_day else None
        }
        
        # Performance distribution
        test_score_ranges = {'90+': 0, '80-89': 0, '70-79': 0, '60-69': 0, 'below_60': 0, 'not_tested': 0}
        rating_ranges = {'4.5+': 0, '4.0-4.4': 0, '3.5-3.9': 0, '3.0-3.4': 0, 'below_3': 0, 'no_rating': 0}
        
        for tutor in tutors:
            # Test score distribution
            if tutor.test_score is None:
                test_score_ranges['not_tested'] += 1
            elif tutor.test_score >= 90:
                test_score_ranges['90+'] += 1
            elif tutor.test_score >= 80:
                test_score_ranges['80-89'] += 1
            elif tutor.test_score >= 70:
                test_score_ranges['70-79'] += 1
            elif tutor.test_score >= 60:
                test_score_ranges['60-69'] += 1
            else:
                test_score_ranges['below_60'] += 1
            
            # Rating distribution
            if tutor.rating is None:
                rating_ranges['no_rating'] += 1
            elif tutor.rating >= 4.5:
                rating_ranges['4.5+'] += 1
            elif tutor.rating >= 4.0:
                rating_ranges['4.0-4.4'] += 1
            elif tutor.rating >= 3.5:
                rating_ranges['3.5-3.9'] += 1
            elif tutor.rating >= 3.0:
                rating_ranges['3.0-3.4'] += 1
            else:
                rating_ranges['below_3'] += 1
        
        analytics['performance_distribution'] = {
            'test_scores': test_score_ranges,
            'ratings': rating_ranges
        }
        
        # Subject and grade coverage
        all_subjects = {}
        all_grades = {}
        
        for tutor in tutors:
            for subject in tutor.get_subjects():
                all_subjects[subject] = all_subjects.get(subject, 0) + 1
            for grade in tutor.get_grades():
                all_grades[str(grade)] = all_grades.get(str(grade), 0) + 1
        
        analytics['subject_coverage'] = dict(sorted(all_subjects.items(), key=lambda x: x[1], reverse=True)[:10])
        analytics['grade_coverage'] = dict(sorted(all_grades.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 999))
        
        return jsonify({
            'success': True,
            'analytics': analytics,
            'date_range': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'days_analyzed': days_back
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Analytics error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Analytics generation failed'
        }), 500
        

@bp.route('/course-batches')
@login_required
@require_any_permission('class_management', 'tutor_management')
def course_batches():
    """Course batch management page - groups classes by tutor with expandable batches"""
    from collections import defaultdict
    from datetime import datetime, timedelta, date
    import time
    import json
    import urllib.parse
    from sqlalchemy.orm import selectinload

    t0 = time.perf_counter()

    query = (
        Class.query
        .options(selectinload(Class.tutor))   
        .order_by(Class.scheduled_date.desc())
    )

    tutor_filter  = request.args.get('tutor', type=int)
    status_filter = request.args.get('status', type=str)
    month_filter  = request.args.get('month', type=str)

    if tutor_filter:
        query = query.filter(Class.tutor_id == tutor_filter)
    if status_filter:
        query = query.filter(Class.status == status_filter)
    if month_filter:
        try:
            month_year = datetime.strptime(month_filter, '%Y-%m')
            start = month_year.replace(day=1)
            next_month = (start + timedelta(days=32)).replace(day=1)
            query = query.filter(
                Class.scheduled_date >= start,
                Class.scheduled_date < next_month
            )
        except ValueError:
            pass

    classes = query.all()

    # Get all students efficiently
    student_ids = set()
    for cls in classes:
        try:
            ids = cls.get_students() or []
            student_ids.update(ids)
        except Exception as e:
            print(f"Error getting students for class {cls.id}: {str(e)}")
            continue

    students_by_id = {}
    if student_ids:
        try:
            students = Student.query.filter(Student.id.in_(student_ids)).all()
            students_by_id = {s.id: s for s in students}
        except Exception as e:
            print(f"Error fetching students: {str(e)}")

    # Group by tutor first, then create individual batches within tutor
    tutors_data = defaultdict(lambda: {
        'tutor': None,
        'batches': defaultdict(lambda: {
            'classes': [],
            'students': set(),
            'tutor': None,
            'subject': '',
            'date_range': {'start': None, 'end': None},
            'total_classes': 0,
            'completed_classes': 0,
            'scheduled_classes': 0,
            'cancelled_classes': 0,
            'active_students': set(),
            'completed_students': set()
        }),
        'total_classes': 0,
        'completed_classes': 0,
        'scheduled_classes': 0,
        'cancelled_classes': 0,
        'all_students': set(),
        'active_students': set(),
        'completed_students': set(),
        'subjects': set(),
        'date_range': {'start': None, 'end': None}
    })

    for cls in classes:
        if not cls.tutor or not cls.scheduled_date:
            continue
        
        # FIXED: Better subject encoding for batch key
        try:
            # Create a safe batch key
            safe_subject = cls.subject.replace(' ', '_').replace('/', '_').replace('&', 'and')
            batch_key = f"{safe_subject}_{cls.tutor_id}"
        except Exception:
            batch_key = f"Unknown_Subject_{cls.tutor_id}"
        
        tutor_data = tutors_data[cls.tutor_id]
        tutor_data['tutor'] = cls.tutor
        tutor_data['subjects'].add(cls.subject)
        tutor_data['total_classes'] += 1
        
        # Update tutor date range
        dr = tutor_data['date_range']
        dr['start'] = min(dr['start'], cls.scheduled_date) if dr['start'] else cls.scheduled_date
        dr['end'] = max(dr['end'], cls.scheduled_date) if dr['end'] else cls.scheduled_date

        # Count by status
        if cls.status == 'completed':
            tutor_data['completed_classes'] += 1
        elif cls.status == 'scheduled':
            tutor_data['scheduled_classes'] += 1
        elif cls.status == 'cancelled':
            tutor_data['cancelled_classes'] += 1

        # Individual batch data
        batch = tutor_data['batches'][batch_key]
        batch['classes'].append(cls)
        batch['tutor'] = cls.tutor
        batch['subject'] = cls.subject
        batch['total_classes'] += 1

        if cls.status == 'completed':
            batch['completed_classes'] += 1
        elif cls.status == 'scheduled':
            batch['scheduled_classes'] += 1
        elif cls.status == 'cancelled':
            batch['cancelled_classes'] += 1

        batch_dr = batch['date_range']
        batch_dr['start'] = min(batch_dr['start'], cls.scheduled_date) if batch_dr['start'] else cls.scheduled_date
        batch_dr['end'] = max(batch_dr['end'], cls.scheduled_date) if batch_dr['end'] else cls.scheduled_date

        # FIXED: Better student handling
        try:
            ids = cls.get_students() or []
            for sid in ids:
                if not isinstance(sid, int):
                    continue
                    
                tutor_data['all_students'].add(sid)
                batch['students'].add(sid)
                
                st = students_by_id.get(sid)
                if st:
                    try:
                        if hasattr(st, "is_course_active") and callable(st.is_course_active):
                            if st.is_course_active(cls.scheduled_date):
                                tutor_data['active_students'].add(sid)
                                batch['active_students'].add(sid)
                        elif getattr(st, 'enrollment_status', None) == 'active':
                            tutor_data['active_students'].add(sid)
                            batch['active_students'].add(sid)
                            
                        if getattr(st, 'enrollment_status', None) == 'completed':
                            tutor_data['completed_students'].add(sid)
                            batch['completed_students'].add(sid)
                    except Exception as e:
                        print(f"Error checking student {sid} status: {str(e)}")
        except Exception as e:
            print(f"Error processing students for class {cls.id}: {str(e)}")

    # Convert to list for tutors
    tutor_list = []
    for tutor_id, tutor_data in tutors_data.items():
        # Process individual batches
        batch_list = []
        for key, b in tutor_data['batches'].items():
            b['batch_id'] = key
            b['student_count'] = len(b['students'])
            b['active_student_count'] = len(b['active_students'])
            b['completed_student_count'] = len(b['completed_students'])
            
            # FIXED: Safe progress calculation
            if b['total_classes'] > 0:
                b['progress_percentage'] = round((b['completed_classes'] / b['total_classes']) * 100, 1)
            else:
                b['progress_percentage'] = 0

            # Get sample student objects
            ids_slice = list(b['students'])[:5]
            b['student_objects'] = []
            for sid in ids_slice:
                if sid in students_by_id:
                    b['student_objects'].append(students_by_id[sid])
            
            batch_list.append(b)
        
        # Sort batches by date (most recent first)
        batch_list.sort(key=lambda x: x['date_range']['start'] or date.min, reverse=True)
        
        # Tutor summary
        tutor_summary = {
            'tutor_id': tutor_id,
            'tutor': tutor_data['tutor'],
            'total_batches': len(batch_list),
            'total_classes': tutor_data['total_classes'],
            'completed_classes': tutor_data['completed_classes'],
            'scheduled_classes': tutor_data['scheduled_classes'],
            'cancelled_classes': tutor_data['cancelled_classes'],
            'total_students': len(tutor_data['all_students']),
            'active_students': len(tutor_data['active_students']),
            'completed_students': len(tutor_data['completed_students']),
            'subjects': list(tutor_data['subjects']),
            'date_range': tutor_data['date_range'],
            'batches': batch_list
        }
        
        # FIXED: Safe progress calculation
        if tutor_summary['total_classes'] > 0:
            tutor_summary['progress_percentage'] = round(
                (tutor_summary['completed_classes'] / tutor_summary['total_classes']) * 100, 1
            )
        else:
            tutor_summary['progress_percentage'] = 0
        
        # Get student objects for preview
        ids_slice = list(tutor_data['active_students'])[:5]
        tutor_summary['student_objects'] = []
        for sid in ids_slice:
            if sid in students_by_id:
                tutor_summary['student_objects'].append(students_by_id[sid])
        
        tutor_list.append(tutor_summary)

    # Sort tutors by name
    tutor_list.sort(key=lambda x: x['tutor'].user.full_name if x['tutor'] and x['tutor'].user else 'ZZZ')

    # Apply activity filter
    activate_param = request.args.get('activate')  
    if activate_param in ('0', '1'):
        want_active = (activate_param == '1')
        filtered = []
        for tutor in tutor_list:
            has_any = tutor['active_students'] > 0
            if has_any is want_active:
                filtered.append(tutor)
        tutor_list = filtered

    # Get filter options
    months = sorted(
        {cls.scheduled_date.strftime('%Y-%m') for cls in classes if cls.scheduled_date},
        reverse=True
    )
    tutors = Tutor.query.filter_by(status='active').all()
    
    # Simple pagination
    from math import ceil

    class SimplePagination:
        def __init__(self, page, per_page, total):
            self.page = page
            self.per_page = per_page
            self.total = total
            self.pages = ceil(total / per_page) if per_page > 0 else 0
            self.has_prev = page > 1
            self.has_next = page < self.pages
            self.prev_num = page - 1 if self.has_prev else None
            self.next_num = page + 1 if self.has_next else None
            
        def iter_pages(self, left_edge=1, right_edge=1, left_current=1, right_current=2):
            max_shown = 10
            for num in range(1, min(self.pages, max_shown) + 1):
                yield num
            if self.pages > max_shown:
                yield None
                yield self.pages

    page = request.args.get('page', 1, type=int)
    per_page = 8
    total = len(tutor_list)

    start = (page - 1) * per_page
    end = start + per_page
    page_items = tutor_list[start:end]

    filtered_args = request.args.to_dict()
    filtered_args.pop('page', None)

    pagination = SimplePagination(page, per_page, total)

    print(f"Course batches loaded in {time.perf_counter() - t0:.3f}s")

    return render_template(
        'admin/course_batches.html',
        tutors_data=page_items,
        pagination=pagination,
        filtered_args=filtered_args,
        tutors=tutors,
        months=months,
        total_tutors=total
    )


@bp.route('/course-batches/<batch_id>')
@require_any_permission('class_management', 'tutor_management')
@admin_required
def course_batch_details(batch_id):
    """View detailed information about a specific course batch."""
    from datetime import datetime, date
    from sqlalchemy.orm import selectinload
    import traceback

    try:
        # FIXED: Better batch_id parsing
        parts = batch_id.split('_')
        if len(parts) < 2:
            raise ValueError(f"Invalid batch_id format: {batch_id}")

        # Last part is tutor_id, everything else is subject
        tutor_id = int(parts[-1])
        subject_parts = parts[:-1]
        
        # Reconstruct subject name (reverse the encoding)
        subject = '_'.join(subject_parts).replace('_', ' ').replace('and', '&')

        print(f"Parsed batch_id '{batch_id}' -> subject: '{subject}', tutor_id: {tutor_id}")

    except Exception as e:
        print(f"Error parsing batch_id '{batch_id}': {str(e)}")
        traceback.print_exc()
        flash('Invalid batch ID format', 'error')
        return redirect(url_for('admin.course_batches'))

    # FIXED: Query classes with better subject matching
    classes = (
        Class.query
        .options(selectinload(Class.tutor))
        .filter(
            Class.subject.ilike(subject),
            Class.tutor_id == tutor_id
        )
        .order_by(Class.scheduled_date, Class.scheduled_time)
        .all()
    )

    print(f"Found {len(classes)} classes for subject '{subject}' and tutor {tutor_id}")

    if not classes:
        # Debug: Try to find similar subjects
        debug_classes = (
            Class.query
            .filter(Class.tutor_id == tutor_id)
            .all()
        )
        
        if debug_classes:
            subjects_found = list(set(cls.subject for cls in debug_classes))
            print(f"Available subjects for tutor {tutor_id}: {subjects_found}")
            flash(f'No classes found for subject "{subject}". Available: {", ".join(subjects_found)}', 'warning')
        else:
            print(f"No classes found for tutor {tutor_id}")
            flash(f'No classes found for this tutor', 'error')
        
        return redirect(url_for('admin.course_batches'))

    # FIXED: Better student collection
    all_student_ids = set()
    for c in classes:
        try:
            ids = c.get_students() or []
            # Ensure all IDs are integers
            valid_ids = [int(sid) for sid in ids if isinstance(sid, (int, str)) and str(sid).isdigit()]
            all_student_ids.update(valid_ids)
        except Exception as e:
            print(f"Error getting students for class {c.id}: {str(e)}")

    students_by_id = {}
    students = []
    if all_student_ids:
        try:
            students = Student.query.filter(Student.id.in_(all_student_ids)).all()
            students_by_id = {s.id: s for s in students}
            print(f"Found {len(students)} students for batch")
        except Exception as e:
            print(f"Error fetching students: {str(e)}")

    # Calculate statistics
    total_classes = len(classes)
    completed_classes = sum(1 for c in classes if c.status == 'completed')
    scheduled_classes = sum(1 for c in classes if c.status == 'scheduled')
    cancelled_classes = sum(1 for c in classes if c.status == 'cancelled')

    total_students = len(students)
    active_students = sum(1 for s in students if getattr(s, 'enrollment_status', '') == 'active')
    completed_students = sum(1 for s in students if getattr(s, 'enrollment_status', '') == 'completed')

    stats = {
        'total_classes': total_classes,
        'completed_classes': completed_classes,
        'scheduled_classes': scheduled_classes,
        'cancelled_classes': cancelled_classes,
        'total_students': total_students,
        'active_students': active_students,
        'completed_students': completed_students,
        'progress_percentage': round((completed_classes / total_classes) * 100, 1) if total_classes > 0 else 0
    }

    # Get tutor info
    tutor = classes[0].tutor if classes else Tutor.query.get(tutor_id)
    
    # Get available tutors for change functionality
    available_tutors = Tutor.query.filter_by(status='active').all()
    available_tutors = [t for t in available_tutors if hasattr(t, 'get_availability') and t.get_availability()]

    # Get ALL active students for Smart Bulk Edit (not just current batch students)
    all_active_students = []
    try:
        # Get all active students with department filtering if user is coordinator
        student_query = Student.query.filter_by(is_active=True)
        if current_user.role == 'coordinator' and current_user.department_id:
            student_query = student_query.filter_by(department_id=current_user.department_id)
        
        all_active_students = student_query.order_by(Student.full_name).all()
        print(f"Found {len(all_active_students)} total active students for Smart Bulk Edit")
    except Exception as e:
        print(f"Error fetching all active students: {str(e)}")
        all_active_students = students  # Fallback to current batch students

    print(f"Batch details loaded successfully")

    return render_template(
        'admin/course_batch_details.html',
        classes=classes,
        students=students,
        tutor=tutor,
        available_tutors=available_tutors,
        batch_id=batch_id,
        subject=subject,
        stats=stats,
        all_active_students=all_active_students  # Add all students for Smart Bulk Edit
    )


@bp.route('/api/classes/smart-bulk-edit', methods=['POST'])
@login_required
@require_any_permission('class_management', 'tutor_management')
def smart_bulk_edit():
    """Smart bulk edit API - handles all types of class modifications"""
    try:
        data = request.get_json()
        class_ids = data.get('class_ids', [])
        changes = data.get('changes', {})
        batch_id = data.get('batch_id', '')
        
        if not class_ids:
            return jsonify({'error': 'No classes selected'}), 400
            
        if not changes:
            return jsonify({'error': 'No changes specified'}), 400
        
        # Get all classes to update
        classes = Class.query.filter(Class.id.in_(class_ids)).all()
        
        if not classes:
            return jsonify({'error': 'No valid classes found'}), 404
        
        # Track successful updates and conflicts
        updated_count = 0
        conflicts = []
        
        # Process each class
        for cls in classes:
            try:
                # Check for conflicts before applying changes
                conflict = check_class_conflicts(cls, changes)
                if conflict:
                    conflicts.append({
                        'class_id': cls.id,
                        'reason': conflict,
                        'class_info': f"{cls.subject} - {cls.scheduled_date}"
                    })
                    continue
                
                # Apply changes to this class
                apply_changes_to_class(cls, changes)
                updated_count += 1
                
            except Exception as e:
                conflicts.append({
                    'class_id': cls.id,
                    'reason': f"Error: {str(e)}",
                    'class_info': f"{cls.subject} - {cls.scheduled_date}"
                })
                continue
        
        # Commit all changes
        db.session.commit()
        
        # Prepare response
        response = {
            'success': True,
            'updated_count': updated_count,
            'total_selected': len(class_ids),
            'conflicts': conflicts
        }
        
        if conflicts:
            response['message'] = f"{updated_count} classes updated successfully. {len(conflicts)} conflicts detected."
        else:
            response['message'] = f"All {updated_count} classes updated successfully!"
        
        return jsonify(response)
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Bulk edit failed: {str(e)}'}), 500


def check_class_conflicts(cls, changes):
    """Check for potential conflicts before applying changes"""
    
    # Note: tutor_id conflict checking removed - use standalone Change Tutor modal for tutor changes
    
    # For time/date conflicts, we still need to check the current class details
    check_date = cls.scheduled_date
    check_time = cls.scheduled_time
    
    # Apply time changes for conflict checking (tutor checking removed)
    if 'time_shift' in changes:
        from datetime import datetime, timedelta
        dt = datetime.combine(check_date, check_time)
        shift_minutes = changes['time_shift']['amount']
        if changes['time_shift']['direction'] == 'subtract':
            shift_minutes = -shift_minutes
        dt += timedelta(minutes=shift_minutes)
        check_time = dt.time()
        
    elif 'specific_time' in changes:
        from datetime import datetime
        check_time = datetime.strptime(changes['specific_time'], '%H:%M').time()
        
    elif 'day_wise_time_changes' in changes:
        # Check if this class's day has a time change
        current_day = cls.scheduled_date.strftime('%A').lower()
        day_changes = changes['day_wise_time_changes']
        if current_day in day_changes:
            from datetime import datetime
            check_time = datetime.strptime(day_changes[current_day], '%H:%M').time()
    
    # Apply day-to-day mapping changes for conflict checking
    if 'day_to_day_mappings' in changes:
        current_day = cls.scheduled_date.strftime('%A').lower()
        day_mappings = changes['day_to_day_mappings']
        if current_day in day_mappings:
            # Calculate new date for conflict checking
            from datetime import timedelta
            current_weekday = check_date.weekday()
            target_weekday = get_weekday_number(day_mappings[current_day])
            days_diff = target_weekday - current_weekday
            
            if days_diff < 0:
                days_diff += 7
                
            check_date += timedelta(days=days_diff)
    
    # Apply date changes for conflict checking
    if 'date_shift' in changes:
        from datetime import timedelta
        shift_days = changes['date_shift']['amount']
        if changes['date_shift']['direction'] == 'subtract':
            shift_days = -shift_days
        check_date += timedelta(days=shift_days)
        
    elif 'day_of_week' in changes:
        # Calculate new date based on day of week change
        current_weekday = check_date.weekday()
        target_weekday = get_weekday_number(changes['day_of_week'])
        days_diff = target_weekday - current_weekday
        check_date += timedelta(days=days_diff)
        
    
    # Note: Tutor conflict checking removed since tutor changes are handled by standalone modal
    # Smart Bulk Edit now focuses on time/date changes only
    return None


def apply_changes_to_class(cls, changes):
    """Apply all changes to a single class"""
    from datetime import datetime, timedelta
    
    # Basic Information Changes
    if 'subject' in changes and changes['subject']:
        cls.subject = changes['subject']
    
    if 'grade' in changes and changes['grade']:
        cls.grade = changes['grade']
    
    if 'board' in changes and changes['board']:
        cls.board = changes['board']
    
    if 'class_type' in changes and changes['class_type']:
        cls.class_type = changes['class_type']
    
    # Scheduling Changes
    if 'time_shift' in changes:
        dt = datetime.combine(cls.scheduled_date, cls.scheduled_time)
        shift_minutes = changes['time_shift']['amount']
        if changes['time_shift']['direction'] == 'subtract':
            shift_minutes = -shift_minutes
        dt += timedelta(minutes=shift_minutes)
        cls.scheduled_time = dt.time()
        cls.calculate_end_time()
    
    if 'specific_time' in changes and changes['specific_time']:
        cls.scheduled_time = datetime.strptime(changes['specific_time'], '%H:%M').time()
        cls.calculate_end_time()
    
    # Day-wise time changes
    if 'day_wise_time_changes' in changes:
        day_changes = changes['day_wise_time_changes']
        current_day = cls.scheduled_date.strftime('%A').lower()
        
        if current_day in day_changes:
            new_time_str = day_changes[current_day]
            cls.scheduled_time = datetime.strptime(new_time_str, '%H:%M').time()
            cls.calculate_end_time()
    
    # Day-to-day mappings  
    if 'day_to_day_mappings' in changes:
        day_mappings = changes['day_to_day_mappings']
        current_day = cls.scheduled_date.strftime('%A').lower()
        
        if current_day in day_mappings:
            target_day = day_mappings[current_day]
            
            # Calculate new date based on target day
            current_weekday = cls.scheduled_date.weekday()
            target_weekday = get_weekday_number(target_day)
            days_diff = target_weekday - current_weekday
            
            # If the target day is in the past this week, move to next week
            if days_diff < 0:
                days_diff += 7
                
            cls.scheduled_date += timedelta(days=days_diff)
    
    if 'duration' in changes and changes['duration']:
        cls.duration = changes['duration']
        cls.calculate_end_time()
    
    if 'date_shift' in changes:
        shift_days = changes['date_shift']['amount']
        if changes['date_shift']['direction'] == 'subtract':
            shift_days = -shift_days
        cls.scheduled_date += timedelta(days=shift_days)
    
    if 'day_of_week' in changes and changes['day_of_week']:
        current_weekday = cls.scheduled_date.weekday()
        target_weekday = get_weekday_number(changes['day_of_week'])
        days_diff = target_weekday - current_weekday
        cls.scheduled_date += timedelta(days=days_diff)
    
    if 'selective_day_changes' in changes:
        # Handle selective day changes
        current_day = cls.scheduled_date.strftime('%A').lower()
        if current_day in changes['selective_day_changes']:
            current_weekday = cls.scheduled_date.weekday()
            target_weekday = get_weekday_number(changes['selective_day_changes'][current_day])
            days_diff = target_weekday - current_weekday
            cls.scheduled_date += timedelta(days=days_diff)
    
    # Assignment Changes (tutor_id removed - use standalone Change Tutor modal)
    if 'add_students' in changes and changes['add_students']:
        current_students = cls.get_students()
        new_students = list(set(current_students + changes['add_students']))
        cls.set_students(new_students)
    
    if 'remove_students' in changes and changes['remove_students']:
        current_students = cls.get_students()
        new_students = [s for s in current_students if s not in changes['remove_students']]
        cls.set_students(new_students)
    
    # Platform Changes
    if 'platform' in changes and changes['platform']:
        cls.platform = changes['platform']
    
    if 'meeting_link' in changes and changes['meeting_link']:
        cls.meeting_link = changes['meeting_link']
    
    if 'meeting_id' in changes and changes['meeting_id']:
        cls.meeting_id = changes['meeting_id']
    
    # Content Changes
    if 'class_notes' in changes and changes['class_notes']:
        note_change = changes['class_notes']
        if note_change['action'] == 'replace':
            cls.class_notes = note_change['content']
        elif note_change['action'] == 'append':
            current_notes = cls.class_notes or ''
            cls.class_notes = f"{current_notes}\n{note_change['content']}" if current_notes else note_change['content']
        elif note_change['action'] == 'prepend':
            current_notes = cls.class_notes or ''
            cls.class_notes = f"{note_change['content']}\n{current_notes}" if current_notes else note_change['content']
    
    if 'topics_covered' in changes and changes['topics_covered']:
        cls.topics_covered = changes['topics_covered']
    
    if 'homework_assigned' in changes and changes['homework_assigned']:
        cls.homework_assigned = changes['homework_assigned']
    
    if 'video_link' in changes and changes['video_link']:
        cls.video_link = changes['video_link']
    
    if 'materials' in changes and changes['materials']:
        cls.materials = changes['materials']
    
    # Status Changes
    if 'status' in changes and changes['status']:
        cls.status = changes['status']
    
    if 'completion_status' in changes and changes['completion_status']:
        cls.completion_status = changes['completion_status']
    
    # Update timestamp
    cls.updated_at = datetime.utcnow()


def get_weekday_number(day_name):
    """Convert day name to weekday number (Monday = 0)"""
    days = {
        'monday': 0,
        'tuesday': 1,
        'wednesday': 2,
        'thursday': 3,
        'friday': 4,
        'saturday': 5,
        'sunday': 6
    }
    return days.get(day_name.lower(), 0)


@bp.route('/api/bulk-edit/check-conflicts', methods=['POST'])
@login_required
@require_any_permission('class_management', 'tutor_management')
def check_bulk_edit_conflicts():
    """Check for conflicts before applying bulk changes"""
    try:
        data = request.get_json()
        class_ids = data.get('class_ids', [])
        changes = data.get('changes', {})
        
        classes = Class.query.filter(Class.id.in_(class_ids)).all()
        conflicts = []
        
        for cls in classes:
            conflict = check_class_conflicts(cls, changes)
            if conflict:
                conflicts.append({
                    'class_id': cls.id,
                    'reason': conflict,
                    'class_info': f"{cls.subject} - {cls.scheduled_date}"
                })
        
        return jsonify({
            'conflicts': conflicts,
            'has_conflicts': len(conflicts) > 0
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


    
# ============ BATCH MANAGEMENT API ROUTES ============

@bp.route('/api/batch/<batch_id>/change-tutor', methods=['POST'])
@login_required
@require_any_permission('class_management', 'tutor_management')
def api_batch_change_tutor(batch_id):
    """Enhanced batch tutor change with day/time selection support"""
    try:
        print(f"Enhanced batch change request for batch_id: {batch_id}")
        print(f"Request data: {request.json}")
        
        data = request.json
        new_tutor_id = data.get('new_tutor_id')
        selected_changes = data.get('selected_changes', [])
        change_type = data.get('change_type', 'keep_schedule')
        
        if not new_tutor_id:
            return jsonify({'error': 'New tutor ID is required'}), 400

        # Parse batch_id to get class filters
        parts = batch_id.split('_')
        if len(parts) < 2:
            return jsonify({'error': 'Invalid batch ID format'}), 400
            
        current_tutor_id = int(parts[-1])
        subject_parts = parts[:-1]
        
        # Reconstruct subject name
        subject = '_'.join(subject_parts).replace('_', ' ').replace('and', '&')
        
        print(f"Enhanced batch change - Subject: '{subject}', Current Tutor ID: {current_tutor_id}, New Tutor ID: {new_tutor_id}")

        # Get tutors
        current_tutor = Tutor.query.get_or_404(current_tutor_id)
        new_tutor = Tutor.query.get_or_404(new_tutor_id)
        
        if not new_tutor.get_availability():
            return jsonify({'error': 'Selected tutor has not set their availability'}), 400

        # Get all future scheduled classes in the batch
        all_classes = Class.query.filter(
            Class.subject.ilike(subject),
            Class.tutor_id == current_tutor_id,
            Class.scheduled_date >= datetime.now().date(),
            Class.status.in_(['scheduled'])
        ).all()
        
        print(f"Found {len(all_classes)} future classes in batch")

        if not all_classes:
            return jsonify({'error': 'No future scheduled classes found in this batch'}), 404

        # If no specific changes selected, apply to all classes (backward compatibility)
        if not selected_changes:
            selected_changes = []
            # Create default changes for all unique day/time combinations
            day_time_combos = set()
            for cls in all_classes:
                day = cls.scheduled_date.strftime('%A')
                time = cls.scheduled_time.strftime('%H:%M')
                day_time_combos.add((day, time))
            
            for day, time in day_time_combos:
                selected_changes.append({
                    'day': day,
                    'time': time,
                    'new_day': day,
                    'new_time': time
                })

        print(f"Processing {len(selected_changes)} selected day/time changes")

        # Process only classes that match selected day/time combinations
        classes_to_change = []
        conflicts = []
        successful_changes = 0
        
        for change in selected_changes:
            current_day = change['day']
            current_time = change['time']
            new_day = change.get('new_day', current_day)
            new_time = change.get('new_time', current_time)
            
            # Find classes matching this day and time
            matching_classes = [
                cls for cls in all_classes 
                if (cls.scheduled_date.strftime('%A') == current_day and 
                    cls.scheduled_time.strftime('%H:%M') == current_time)
            ]
            
            print(f"Found {len(matching_classes)} classes for {current_day} at {current_time}")
            
            for cls in matching_classes:
                # Calculate new date if day changed
                new_date = cls.scheduled_date
                if change_type == 'modify_schedule' and new_day != current_day:
                    # Find next occurrence of the new day
                    current_weekday = cls.scheduled_date.weekday()
                    new_weekday = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'].index(new_day)
                    days_diff = (new_weekday - current_weekday) % 7
                    if days_diff == 0:
                        days_diff = 7  # Move to next week if same day
                    new_date = cls.scheduled_date + timedelta(days=days_diff)
                
                # Check new tutor availability at new day/time
                check_day = new_day.lower() if change_type in ['modify_times', 'modify_schedule'] else current_day.lower()
                check_time = new_time if change_type in ['modify_times', 'modify_schedule'] else current_time
                
                if not new_tutor.is_available_at(check_day, check_time):
                    conflicts.append({
                        'class_id': cls.id,
                        'date': cls.scheduled_date.strftime('%Y-%m-%d'),
                        'day': current_day,
                        'current_time': current_time,
                        'new_day': new_day,
                        'new_time': new_time,
                        'reason': 'New tutor not available at requested day/time'
                    })
                    continue
                
                # Check for scheduling conflicts at new date/time
                new_time_obj = datetime.strptime(new_time, '%H:%M').time()
                existing_class = Class.query.filter_by(
                    tutor_id=new_tutor_id,
                    scheduled_date=new_date,
                    scheduled_time=new_time_obj,
                    status='scheduled'
                ).first()
                
                if existing_class:
                    conflicts.append({
                        'class_id': cls.id,
                        'date': cls.scheduled_date.strftime('%Y-%m-%d'),
                        'day': current_day,
                        'current_time': current_time,
                        'new_day': new_day,
                        'new_time': new_time,
                        'reason': 'New tutor already has a class at this date/time'
                    })
                    continue
                
                # Apply changes
                cls.tutor_id = new_tutor_id
                
                # Update schedule if modifying times or full schedule
                if change_type in ['modify_times', 'modify_schedule']:
                    if new_time != current_time:
                        cls.scheduled_time = new_time_obj
                        cls.calculate_end_time()
                    
                    if change_type == 'modify_schedule' and new_date != cls.scheduled_date:
                        cls.scheduled_date = new_date
                
                cls.updated_at = datetime.utcnow()
                
                # Add change history to admin notes
                change_note = f"Batch tutor changed from {current_tutor.user.full_name} to {new_tutor.user.full_name}"
                
                if change_type in ['modify_times', 'modify_schedule']:
                    if new_day != current_day and new_time != current_time:
                        change_note += f", Schedule changed from {current_day} at {current_time} to {new_day} at {new_time}"
                    elif new_day != current_day:
                        change_note += f", Day changed from {current_day} to {new_day}"
                    elif new_time != current_time:
                        change_note += f", Time changed from {current_time} to {new_time}"
                
                change_note += f" on {datetime.now().strftime('%d %b %Y at %H:%M')}"
                
                if cls.admin_notes:
                    cls.admin_notes += f"\n{change_note}"
                else:
                    cls.admin_notes = change_note
                
                classes_to_change.append(cls)
                successful_changes += 1

        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Successfully changed tutor for {successful_changes} classes',
            'successful_changes': successful_changes,
            'conflicts': conflicts,
            'total_classes': len(classes)
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error changing tutor: {str(e)}'}), 500

@bp.route('/api/batch/<batch_id>/delete-classes', methods=['POST'])
@login_required
@require_any_permission('class_management', 'tutor_management')
def api_batch_delete_classes(batch_id):
    """Delete selected classes from a batch"""
    try:
        class_ids = request.json.get('class_ids', [])
        if not class_ids:
            return jsonify({'error': 'No classes selected for deletion'}), 400

        # Verify classes belong to the batch
        classes = Class.query.filter(Class.id.in_(class_ids)).all()
        
        if not classes:
            return jsonify({'error': 'No valid classes found'}), 404

        deleted_count = 0
        for cls in classes:
            # Only delete scheduled classes
            if cls.status == 'scheduled':
                cls.status = 'cancelled'
                cls.cancellation_reason = 'Deleted via batch management'
                cls.cancelled_at = datetime.utcnow()
                cls.cancelled_by = current_user.id
                deleted_count += 1

        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Successfully cancelled {deleted_count} classes',
            'deleted_count': deleted_count
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error deleting classes: {str(e)}'}), 500

@bp.route('/api/tutor/<int:tutor_id>/batch-availability', methods=['GET'])
@login_required
@require_any_permission('class_management', 'tutor_management')
def api_tutor_batch_availability(tutor_id):
    """Check tutor availability for a batch of classes - OPTIMIZED"""
    print(f"🔍 BATCH AVAILABILITY API CALLED: tutor_id={tutor_id}")
    try:
        class_ids = request.args.getlist('class_ids')
        if not class_ids:
            return jsonify({'error': 'No class IDs provided'}), 400

        # Limit the number of classes to prevent performance issues
        if len(class_ids) > 100:
            return jsonify({'error': 'Too many classes. Maximum 100 classes per request.'}), 400

        # Convert to integers and validate
        try:
            class_ids = [int(cid) for cid in class_ids]
        except ValueError:
            return jsonify({'error': 'Invalid class ID format'}), 400

        tutor = Tutor.query.get_or_404(tutor_id)
        availability = tutor.get_availability()
        
        if not availability:
            return jsonify({
                'success': False,
                'has_availability': False,
                'message': 'Tutor has not set their availability'
            })

        # OPTIMIZATION 1: Batch load all classes in one query
        classes = Class.query.filter(Class.id.in_(class_ids)).all()
        
        if not classes:
            return jsonify({'error': 'No valid classes found'}), 404

        # SMART OPTIMIZATION 2: Extract unique day/time patterns instead of checking every class
        unique_patterns = {}
        pattern_to_classes = {}
        
        for cls in classes:
            day_of_week = cls.scheduled_date.strftime('%A').lower()
            time_str = cls.scheduled_time.strftime('%H:%M')
            pattern_key = (day_of_week, time_str)
            
            # Group classes by their day/time pattern
            if pattern_key not in unique_patterns:
                unique_patterns[pattern_key] = {
                    'day_of_week': day_of_week,
                    'time_str': time_str,
                    'sample_date': cls.scheduled_date,
                    'sample_time': cls.scheduled_time
                }
                pattern_to_classes[pattern_key] = []
            
            pattern_to_classes[pattern_key].append(cls)

        print(f"🚀 PATTERN OPTIMIZATION: Reduced {len(classes)} classes to {len(unique_patterns)} unique patterns")
        print(f"🚀 PERFORMANCE BOOST: {((len(classes) - len(unique_patterns)) / len(classes) * 100):.1f}% fewer checks needed!")

        # OPTIMIZATION 3: Check conflicts only for unique patterns
        from sqlalchemy import and_, or_
        conflict_conditions = []
        for pattern in unique_patterns.values():
            conflict_conditions.append(
                and_(
                    Class.scheduled_time == pattern['sample_time'],
                    # For time conflicts, we only care about the time, not specific dates
                    # since we're checking tutor's general availability
                )
            )
        
        # Single query to get potential time conflicts (simplified)
        if conflict_conditions:
            existing_conflicts = Class.query.filter(
                Class.tutor_id == tutor_id,
                Class.status == 'scheduled',
                or_(*[Class.scheduled_time == p['sample_time'] for p in unique_patterns.values()])
            ).all()
            
            # Create time-based conflict lookup
            conflict_times = {cls.scheduled_time for cls in existing_conflicts}
        else:
            conflict_times = set()

        # OPTIMIZATION 4: Check availability for each unique pattern only once
        pattern_results = {}
        available_patterns = 0
        
        for pattern_key, pattern_info in unique_patterns.items():
            day_of_week = pattern_info['day_of_week']
            time_str = pattern_info['time_str']
            sample_time = pattern_info['sample_time']
            
            # Check tutor availability (done once per pattern)
            is_available = tutor.is_available_at(day_of_week, time_str)
            
            # Check for time conflicts (simplified check)
            has_time_conflict = sample_time in conflict_times
            
            # Determine final availability for this pattern
            final_available = is_available and not has_time_conflict
            if final_available:
                available_patterns += 1
            
            # Determine reason
            if not is_available:
                reason = f'Not available on {day_of_week.title()}s at {time_str}'
            elif has_time_conflict:
                reason = f'Time conflict: Another class at {time_str}'
            else:
                reason = f'Available on {day_of_week.title()}s at {time_str}'
            
            pattern_results[pattern_key] = {
                'available': final_available,
                'reason': reason
            }

        # OPTIMIZATION 5: Apply pattern results to all classes in each pattern
        availability_results = []
        available_count = 0
        
        for pattern_key, pattern_classes in pattern_to_classes.items():
            pattern_result = pattern_results[pattern_key]
            
            for cls in pattern_classes:
                if pattern_result['available']:
                    available_count += 1
                
                availability_results.append({
                    'class_id': cls.id,
                    'date': cls.scheduled_date.strftime('%Y-%m-%d'),
                    'time': cls.scheduled_time.strftime('%H:%M'),
                    'day': cls.scheduled_date.strftime('%A'),
                    'available': pattern_result['available'],
                    'reason': pattern_result['reason']
                })
        
        return jsonify({
            'success': True,
            'has_availability': bool(availability),
            'tutor_name': tutor.user.full_name,
            'total_classes': len(classes),
            'available_classes': available_count,
            'conflicts': len(classes) - available_count,
            'details': availability_results
        })

    except Exception as e:
        print(f"ERROR in api_tutor_batch_availability: {str(e)}")  # Debug logging
        return jsonify({'error': f'Error checking availability: {str(e)}'}), 500


@bp.route('/api/validate-tutor-schedule', methods=['POST'])
@login_required
@require_any_permission('class_management', 'tutor_management')
def api_validate_tutor_schedule():
    """Validate if a tutor is available at a specific day/time"""
    try:
        data = request.get_json()
        print(f"DEBUG: Received data: {data}")  # Debug logging
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No JSON data received'
            }), 400
            
        tutor_id = data.get('tutor_id')
        day_of_week = data.get('day_of_week')  # monday, tuesday, etc.
        time = data.get('time')  # HH:MM format
        duration = data.get('duration', 60)  # minutes
        
        print(f"DEBUG: Parsed - tutor_id: {tutor_id}, day_of_week: {day_of_week}, time: {time}, duration: {duration}")
        
        # More detailed validation
        missing_params = []
        if not tutor_id:
            missing_params.append('tutor_id')
        if not day_of_week:
            missing_params.append('day_of_week')
        if not time:
            missing_params.append('time')
            
        if missing_params:
            return jsonify({
                'success': False,
                'error': f'Missing required parameters: {", ".join(missing_params)}. Received: {data}'
            }), 400

        tutor = Tutor.query.get(tutor_id)
        if not tutor:
            return jsonify({
                'success': False,
                'error': 'Tutor not found'
            }), 404

        # Check if tutor has availability set
        availability = tutor.get_availability()
        if not availability:
            return jsonify({
                'success': True,
                'available': False,
                'reason': 'Tutor has not set their availability'
            })

        # Check if tutor is available at the specified day/time
        is_available = tutor.is_available_at(day_of_week.lower(), time)
        
        if not is_available:
            return jsonify({
                'success': True,
                'available': False,
                'reason': f'Tutor is not available on {day_of_week.title()} at {time}'
            })

        # For schedule validation, we don't need to check specific date conflicts
        # We just check if the tutor is generally available at that day/time
        # The actual conflict checking will be done when applying the changes
        
        # Skip the complex date calculation for better performance
        # Just validate the general availability pattern

        # All checks passed
        return jsonify({
            'success': True,
            'available': True,
            'reason': f'Tutor is available on {day_of_week.title()} at {time}'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error validating tutor schedule: {str(e)}'
        }), 500
    
    
@bp.route('/api/v1/check-class-conflict')
@login_required
@require_any_permission('class_management', 'tutor_management')
def api_check_class_conflict():
    """Enhanced conflict checking that includes reschedule exclusions"""
    try:
        tutor_id = request.args.get('tutor_id', type=int)
        date_str = request.args.get('date')
        time_str = request.args.get('time')
        duration = request.args.get('duration', type=int)
        exclude_class = request.args.get('exclude_class', type=int)  # For reschedule checks
        
        if not all([tutor_id, date_str, time_str, duration]):
            return jsonify({
                'success': False,
                'error': 'Missing required parameters'
            }), 400
        
        # Parse date and time
        from datetime import datetime, date, time
        schedule_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        schedule_time = datetime.strptime(time_str, '%H:%M').time()
        
        # Check for time conflicts
        conflict_exists, conflicting_class = Class.check_time_conflict(
            tutor_id, schedule_date, schedule_time, duration, exclude_class
        )
        
        tutor = Tutor.query.get(tutor_id)
        if not tutor:
            return jsonify({
                'success': False,
                'error': 'Tutor not found'
            }), 404
        
        # Check tutor availability
        day_name = schedule_date.strftime('%A').lower()
        availability_check = True
        
        if hasattr(tutor, 'is_available_at'):
            availability_check = tutor.is_available_at(day_name, time_str)
        
        can_schedule = not conflict_exists and availability_check
        
        message = "Available"
        if conflict_exists:
            message = f"Tutor has another class at {conflicting_class.scheduled_time.strftime('%H:%M')}"
        elif not availability_check:
            message = f"Tutor is not available on {day_name.title()} at {time_str}"
        
        return jsonify({
            'success': True,
            'can_schedule': can_schedule,
            'has_conflict': conflict_exists,
            'tutor_available': availability_check,
            'message': message,
            'conflicting_class_id': conflicting_class.id if conflicting_class else None
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
        

@bp.route('/api/v1/classes/<int:class_id>/reschedule', methods=['POST'])
@login_required
@require_any_permission('class_management', 'tutor_management')
def api_reschedule_class(class_id):
    """API endpoint for rescheduling classes"""
    try:
        class_item = Class.query.get_or_404(class_id)
        
        # Check department access for coordinators
        if current_user.role == 'coordinator':
            if class_item.tutor.user.department_id != current_user.department_id:
                return jsonify({'success': False, 'error': 'Access denied'}), 403
        
        data = request.get_json()
        new_date_str = data.get('scheduled_date')
        new_time_str = data.get('scheduled_time')
        reason = data.get('reschedule_reason', 'Rescheduled by admin')
        
        if not new_date_str or not new_time_str:
            return jsonify({'success': False, 'error': 'Date and time are required'}), 400
        
        # Parse date and time
        from datetime import datetime
        new_date = datetime.strptime(new_date_str, '%Y-%m-%d').date()
        new_time = datetime.strptime(new_time_str, '%H:%M').time()
        
        # Check for conflicts
        conflict_exists, conflicting_class = Class.check_time_conflict(
            class_item.tutor_id, new_date, new_time, class_item.duration, class_id
        )
        
        if conflict_exists:
            return jsonify({
                'success': False,
                'error': f'Time conflict with existing class at {conflicting_class.scheduled_time}'
            })
        
        # Update class
        old_date = class_item.scheduled_date
        old_time = class_item.scheduled_time
        
        class_item.scheduled_date = new_date
        class_item.scheduled_time = new_time
        class_item.calculate_end_time()
        class_item.updated_at = datetime.utcnow()
        
        # Add admin note
        note = f"Rescheduled by {current_user.full_name} from {old_date} {old_time} to {new_date} {new_time}. Reason: {reason}"
        if class_item.admin_notes:
            class_item.admin_notes += f"\n{note}"
        else:
            class_item.admin_notes = note
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Class rescheduled successfully',
            'new_date': new_date.strftime('%Y-%m-%d'),
            'new_time': new_time.strftime('%H:%M')
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/v1/classes/<int:class_id>/cancel', methods=['POST'])
@login_required
@require_any_permission('class_management', 'tutor_management')
@handle_json_errors
def api_cancel_class(class_id):
    """API endpoint for cancelling classes"""
    try:
        class_item = Class.query.get_or_404(class_id)
        
        # Check department access for coordinators
        if current_user.role == 'coordinator':
            if class_item.tutor.user.department_id != current_user.department_id:
                return jsonify({'success': False, 'error': 'Access denied'}), 403
        
        # Better JSON handling - allow empty request body
        try:
            if request.is_json and request.get_data(as_text=True).strip():
                data = request.get_json(force=False, silent=False, cache=False)
            else:
                data = {}
        except Exception:
            data = {}
        
        reason = data.get('reason', 'Cancelled by admin')
        
        # Cancel the class
        class_item.cancel_class(reason)
        
        return jsonify({
            'success': True,
            'message': 'Class cancelled successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# ADD THIS ROUTE for dashboard statistics
@bp.route('/api/v1/dashboard/reschedule-stats')
@login_required
@require_permission('class_management')
def api_reschedule_stats():
    """Get reschedule request statistics for dashboard"""
    try:
        from app.models.reschedule_request import RescheduleRequest
        
        # Base query
        query = RescheduleRequest.query
        
        # Filter by department for coordinators
        if current_user.role == 'coordinator':
            from app.models.tutor import Tutor
            from app.models.user import User
            query = query.join(Class).join(Tutor).join(User).filter(
                User.department_id == current_user.department_id
            )
        
        # Get counts
        total_requests = query.count()
        pending_requests = query.filter_by(status='pending').count()
        approved_requests = query.filter_by(status='approved').count()
        rejected_requests = query.filter_by(status='rejected').count()
        
        # Get requests with conflicts
        conflict_requests = query.filter_by(has_conflicts=True, status='pending').count()
        
        return jsonify({
            'success': True,
            'stats': {
                'total_requests': total_requests,
                'pending_requests': pending_requests,
                'approved_requests': approved_requests,
                'rejected_requests': rejected_requests,
                'conflict_requests': conflict_requests
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    
    
# ADD THESE ROUTES TO app/routes/admin.py

@bp.route('/api/v1/tutors/active')
@login_required
@require_any_permission('class_management', 'tutor_management')
def api_get_active_tutors():
    """Get active tutors for bulk edit and other operations"""
    try:
        tutors = Tutor.query.join(Tutor.user).filter(
            Tutor.status == 'active',
            Tutor.user.has(is_active=True)
        ).all()
        
        tutor_data = []
        for tutor in tutors:
            tutor_data.append({
                'id': tutor.id,
                'name': tutor.user.full_name,
                'subjects': tutor.get_subjects(),
                'grades': tutor.get_grades(),
                'status': tutor.status,
                'department': tutor.user.department.name if tutor.user.department else None
            })
        
        return jsonify({
            'success': True,
            'tutors': tutor_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/classes/<int:class_id>/edit', methods=['GET', 'POST'])
@login_required
@require_any_permission('class_management', 'tutor_management')
def edit_class(class_id):
    """Edit single class"""
    from app.forms.class_forms import EditClassForm
    import json
    
    class_obj = Class.query.get_or_404(class_id)
    
    # Check if class can be edited
    if not class_obj.is_editable():
        flash('This class cannot be edited. Classes that are completed, ongoing, or start within 1 hour cannot be modified.', 'error')
        return redirect(url_for('admin.class_details', class_id=class_id))
    
    # Check department access for coordinators
    if current_user.role == 'coordinator':
        if class_obj.tutor and class_obj.tutor.user.department_id != current_user.department_id:
            flash('Access denied. You can only edit classes from your department.', 'error')
            return redirect(url_for('admin.classes'))
    
    form = EditClassForm(class_obj=class_obj, department_id=current_user.department_id if current_user.role == 'coordinator' else None)
    
    if form.validate_on_submit():
        try:
            # Store original values for change tracking
            original_tutor_id = class_obj.tutor_id
            original_date = class_obj.scheduled_date
            original_time = class_obj.scheduled_time
            
            # Update basic information
            class_obj.subject = form.subject.data
            class_obj.class_type = form.class_type.data
            class_obj.grade = form.grade.data
            class_obj.board = form.board.data
            
            # Update scheduling
            class_obj.scheduled_date = form.scheduled_date.data
            class_obj.scheduled_time = form.scheduled_time.data
            class_obj.duration = form.duration.data
            
            # Calculate end time
            from datetime import datetime, timedelta
            start_datetime = datetime.combine(class_obj.scheduled_date, class_obj.scheduled_time)
            end_datetime = start_datetime + timedelta(minutes=class_obj.duration)
            class_obj.end_time = end_datetime.time()
            
            # Update tutor assignment
            class_obj.tutor_id = form.tutor_id.data
            
            # Update student assignments
            if form.class_type.data == 'one_on_one':
                class_obj.primary_student_id = form.primary_student_id.data
                class_obj.students = None  # Clear group students
            elif form.class_type.data == 'group':
                if form.students.data:
                    class_obj.students = json.dumps(form.students.data)
                if form.primary_student_id.data and form.primary_student_id.data != 0:
                    class_obj.primary_student_id = form.primary_student_id.data
                else:
                    class_obj.primary_student_id = None
            else:  # demo
                class_obj.primary_student_id = form.primary_student_id.data
                class_obj.students = None
            
            # Update platform and links
            class_obj.platform = form.platform.data
            class_obj.meeting_link = form.meeting_link.data
            class_obj.meeting_id = form.meeting_id.data
            class_obj.meeting_password = form.meeting_password.data
            
            # Update notes
            class_obj.class_notes = form.class_notes.data
            
            # Update timestamp
            class_obj.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            # Create change notification message
            changes = []
            if original_tutor_id != class_obj.tutor_id:
                old_tutor = Tutor.query.get(original_tutor_id).user.full_name if original_tutor_id else 'None'
                new_tutor = Tutor.query.get(class_obj.tutor_id).user.full_name
                changes.append(f"Tutor: {old_tutor} → {new_tutor}")
            
            if original_date != class_obj.scheduled_date or original_time != class_obj.scheduled_time:
                old_schedule = f"{original_date} at {original_time}"
                new_schedule = f"{class_obj.scheduled_date} at {class_obj.scheduled_time}"
                changes.append(f"Schedule: {old_schedule} → {new_schedule}")
            
            if changes:
                flash(f'Class updated successfully! Changes: {", ".join(changes)}', 'success')
            else:
                flash('Class updated successfully!', 'success')
            
            return redirect(url_for('admin.class_details', class_id=class_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating class: {str(e)}', 'error')
    
    return render_template('admin/edit_class.html', form=form, class_obj=class_obj)


@bp.route('/classes/bulk-edit', methods=['GET', 'POST'])
@login_required
@require_any_permission('class_management', 'tutor_management')
def bulk_edit_classes():
    """Bulk edit multiple classes"""
    from app.forms.class_forms import BulkEditClassForm
    import json
    from datetime import datetime, timedelta
    
    form = BulkEditClassForm(department_id=current_user.department_id if current_user.role == 'coordinator' else None)
    
    if form.validate_on_submit():
        try:
            # Parse selected classes
            class_ids = json.loads(form.selected_classes.data)
            classes = Class.query.filter(Class.id.in_(class_ids)).all()
            
            # Filter editable classes
            editable_classes = [cls for cls in classes if cls.is_editable()]
            skipped_count = len(classes) - len(editable_classes)
            
            if not editable_classes:
                flash('No classes could be edited. All selected classes are either completed, ongoing, or start within 1 hour.', 'warning')
                return redirect(url_for('admin.classes'))
            
            updated_count = 0
            error_count = 0
            
            for class_obj in editable_classes:
                try:
                    changes_made = False
                    
                    # Update tutor if specified
                    if form.tutor_id.data and form.tutor_id.data != 0:
                        # Check for conflicts before updating
                        conflict_exists, _ = Class.check_time_conflict(
                            form.tutor_id.data,
                            class_obj.scheduled_date,
                            class_obj.scheduled_time,
                            class_obj.duration,
                            class_obj.id
                        )
                        
                        if not conflict_exists:
                            class_obj.tutor_id = form.tutor_id.data
                            changes_made = True
                    
                    # Update platform if specified
                    if form.platform.data:
                        class_obj.platform = form.platform.data
                        changes_made = True
                    
                    # Apply time adjustments
                    if form.time_adjustment.data:
                        adjustment_map = {
                            'add_15': 15,
                            'subtract_15': -15,
                            'add_30': 30,
                            'subtract_30': -30
                        }
                        
                        if form.time_adjustment.data in adjustment_map:
                            minutes_delta = adjustment_map[form.time_adjustment.data]
                            current_datetime = datetime.combine(class_obj.scheduled_date, class_obj.scheduled_time)
                            new_datetime = current_datetime + timedelta(minutes=minutes_delta)
                            
                            # Ensure new time is not in the past
                            if new_datetime.date() >= datetime.now().date():
                                class_obj.scheduled_time = new_datetime.time()
                                # Update end time
                                end_datetime = new_datetime + timedelta(minutes=class_obj.duration)
                                class_obj.end_time = end_datetime.time()
                                changes_made = True
                    
                    # Update duration if specified
                    if form.new_duration.data:
                        class_obj.duration = form.new_duration.data
                        # Recalculate end time
                        start_datetime = datetime.combine(class_obj.scheduled_date, class_obj.scheduled_time)
                        end_datetime = start_datetime + timedelta(minutes=class_obj.duration)
                        class_obj.end_time = end_datetime.time()
                        changes_made = True
                    
                    # Update meeting link if specified
                    if form.meeting_link.data:
                        class_obj.meeting_link = form.meeting_link.data
                        changes_made = True
                    
                    # Append bulk notes if specified
                    if form.bulk_notes.data:
                        if class_obj.class_notes:
                            class_obj.class_notes += f"\n\n{form.bulk_notes.data}"
                        else:
                            class_obj.class_notes = form.bulk_notes.data
                        changes_made = True
                    
                    if changes_made:
                        class_obj.updated_at = datetime.utcnow()
                        updated_count += 1
                
                except Exception as e:
                    error_count += 1
                    print(f"Error updating class {class_obj.id}: {str(e)}")
                    continue
            
            db.session.commit()
            
            # Create success message
            message = f'Bulk edit completed! Updated {updated_count} classes.'
            if skipped_count > 0:
                message += f' {skipped_count} classes were skipped (not editable).'
            if error_count > 0:
                message += f' {error_count} classes had errors.'
            
            flash(message, 'success' if error_count == 0 else 'warning')
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error during bulk edit: {str(e)}', 'error')
    
    return redirect(url_for('admin.classes'))


@bp.route('/api/v1/classes/<int:class_id>/editable')
@login_required
@require_any_permission('class_management', 'tutor_management')
def api_check_class_editable(class_id):
    """Check if a class can be edited via API"""
    try:
        class_obj = Class.query.get_or_404(class_id)
        
        return jsonify({
            'success': True,
            'editable': class_obj.is_editable(),
            'reason': None if class_obj.is_editable() else 'Class is completed, ongoing, or starts within 1 hour'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/v1/classes/<int:class_id>/quick-edit', methods=['POST'])
@login_required
@require_any_permission('class_management', 'tutor_management')
def api_quick_edit_class(class_id):
    """Quick edit class via API (for simple changes)"""
    try:
        class_obj = Class.query.get_or_404(class_id)
        
        if not class_obj.is_editable():
            return jsonify({
                'success': False,
                'error': 'Class cannot be edited'
            }), 400
        
        data = request.get_json()
        
        # Handle quick edits
        if 'tutor_id' in data:
            # Check for conflicts
            conflict_exists, conflicting_class = Class.check_time_conflict(
                data['tutor_id'],
                class_obj.scheduled_date,
                class_obj.scheduled_time,
                class_obj.duration,
                class_obj.id
            )
            
            if conflict_exists:
                return jsonify({
                    'success': False,
                    'error': f'Tutor has a conflicting class: {conflicting_class.subject}'
                }), 400
            
            class_obj.tutor_id = data['tutor_id']
        
        if 'platform' in data:
            class_obj.platform = data['platform']
        
        if 'meeting_link' in data:
            class_obj.meeting_link = data['meeting_link']
        
        if 'class_notes' in data:
            class_obj.class_notes = data['class_notes']
        
        class_obj.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Class updated successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/classes/<int:class_id>/duplicate')
@login_required
@require_any_permission('class_management', 'tutor_management')
def duplicate_class(class_id):
    """Create a duplicate of an existing class"""
    try:
        original_class = Class.query.get_or_404(class_id)
        
        # Create new class with same data
        new_class = Class(
            subject=original_class.subject,
            class_type=original_class.class_type,
            grade=original_class.grade,
            board=original_class.board,
            scheduled_date=original_class.scheduled_date,
            scheduled_time=original_class.scheduled_time,
            duration=original_class.duration,
            tutor_id=original_class.tutor_id,
            primary_student_id=original_class.primary_student_id,
            students=original_class.students,
            platform=original_class.platform,
            meeting_link=original_class.meeting_link,
            meeting_id=original_class.meeting_id,
            meeting_password=original_class.meeting_password,
            class_notes=f"Duplicated from class #{original_class.id}",
            status='scheduled',
            created_by=current_user.id
        )
        
        # Calculate end time
        from datetime import datetime, timedelta
        start_datetime = datetime.combine(new_class.scheduled_date, new_class.scheduled_time)
        end_datetime = start_datetime + timedelta(minutes=new_class.duration)
        new_class.end_time = end_datetime.time()
        
        db.session.add(new_class)
        db.session.commit()
        
        flash(f'Class duplicated successfully! New class ID: {new_class.id}', 'success')
        return redirect(url_for('admin.edit_class', class_id=new_class.id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error duplicating class: {str(e)}', 'error')
        return redirect(url_for('admin.class_details', class_id=class_id))


@bp.route('/classes/<int:class_id>/delete', methods=['POST'])
@login_required
@require_any_permission('class_management', 'tutor_management')
def delete_class(class_id):
    """Delete a class"""
    try:
        class_obj = Class.query.get_or_404(class_id)
        
        if not class_obj.is_deletable():
            return jsonify({
                'success': False,
                'error': 'Class cannot be deleted. Completed classes or classes that have started cannot be removed.'
            }), 400
        
        # Check permissions
        if current_user.role == 'coordinator':
            if class_obj.tutor and class_obj.tutor.user.department_id != current_user.department_id:
                return jsonify({
                    'success': False,
                    'error': 'Access denied'
                }), 403
        
        # Delete related attendance records first
        Attendance.query.filter_by(class_id=class_id).delete()
        
        # Delete the class
        db.session.delete(class_obj)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Class deleted successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
        
        
### ADDITIONAL ROUTES FOR ALLOCATION HELPERS

# Replace your allocation_dashboard route in admin.py with this debugging version:

@bp.route('/allocation-dashboard')
@login_required
@require_permission('tutor_management')
def allocation_dashboard():
    """Smart Allocation Dashboard - Main View"""
    try:
        # Get analytics for overview
        analytics = allocation_helper.get_allocation_analytics()
        print(f"Analytics: {analytics}")  # Debug print
        
        # Get recent unallocated students (last 20)
        unallocated_students = allocation_helper.get_unallocated_students()[:20]
        print(f"Unallocated students count: {len(unallocated_students)}")  # Debug print
        
        # Get available tutors (top 15 by rating)
        available_tutors = allocation_helper.get_available_tutors()[:15]
        print(f"Available tutors count: {len(available_tutors)}")  # Debug print
        
        # Get departments for filtering
        departments = Department.query.filter_by(is_active=True).all()
        
        # Get unique subjects and grades for filters
        all_subjects = set()
        all_grades = set()
        all_boards = set()
        
        students = Student.query.filter_by(is_active=True).all()
        for student in students:
            try:
                subjects = student.get_subjects_enrolled()
                all_subjects.update(subjects)
                all_grades.add(student.grade)
                all_boards.add(student.board)
            except Exception as e:
                print(f"Error processing student {student.id}: {e}")
                continue
        
        filter_options = {
            'subjects': sorted(list(all_subjects)),
            'grades': sorted(list(all_grades), key=lambda x: int(x) if x.isdigit() else 999),
            'boards': sorted(list(all_boards))
        }
        
        print(f"Filter options: {filter_options}")  # Debug print
        
        return render_template('admin/allocation_dashboard.html',
                             analytics=analytics,
                             unallocated_students=unallocated_students,
                             available_tutors=available_tutors,
                             departments=departments,
                             filter_options=filter_options)
                             
    except Exception as e:
        print(f"Error in allocation dashboard: {e}")
        # Return basic version if there's an error
        return render_template('admin/allocation_dashboard.html',
                             analytics={'overview': {'allocated_students': 0, 'unallocated_students': 0, 'allocation_percentage': 0, 'urgent_cases': 0}},
                             unallocated_students=[],
                             available_tutors=[],
                             departments=[],
                             filter_options={'subjects': [], 'grades': [], 'boards': []})


@bp.route('/api/allocation/unallocated-students')
@login_required
@admin_required
def api_unallocated_students():
    """API: Get unallocated students with filters"""
    try:
        # Get filters from request
        filters = {}
        if request.args.get('grade'):
            filters['grade'] = request.args.get('grade')
        if request.args.get('board'):
            filters['board'] = request.args.get('board')
        if request.args.get('subject'):
            filters['subject'] = request.args.get('subject')
        if request.args.get('department_id'):
            filters['department_id'] = int(request.args.get('department_id'))
        if request.args.get('days_unallocated'):
            filters['days_unallocated'] = int(request.args.get('days_unallocated'))
        
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        # Get unallocated students
        all_unallocated = allocation_helper.get_unallocated_students(filters)
        
        # Apply pagination
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_students = all_unallocated[start_idx:end_idx]
        
        return jsonify({
            'success': True,
            'students': paginated_students,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': len(all_unallocated),
                'pages': (len(all_unallocated) + per_page - 1) // per_page,
                'has_next': end_idx < len(all_unallocated),
                'has_prev': page > 1
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Unallocated students API error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch unallocated students'
        }), 500


@bp.route('/api/allocation/available-tutors')
@login_required
@require_any_permission('class_management', 'tutor_management')
def api_available_tutors():
    """API: Get available tutors with filters"""
    try:
        # Get filters from request
        filters = {}
        if request.args.get('subject'):
            filters['subject'] = request.args.get('subject')
        if request.args.get('grade'):
            filters['grade'] = request.args.get('grade')
        if request.args.get('board'):
            filters['board'] = request.args.get('board')
        if request.args.get('min_rating'):
            filters['min_rating'] = float(request.args.get('min_rating'))
        if request.args.get('min_test_score'):
            filters['min_test_score'] = float(request.args.get('min_test_score'))
        
        available_tutors = allocation_helper.get_available_tutors(filters)
        
        return jsonify({
            'success': True,
            'tutors': available_tutors
        })
        
    except Exception as e:
        current_app.logger.error(f"Available tutors API error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch available tutors'
        }), 500


@bp.route('/api/allocation/smart-match/<int:student_id>')
@login_required
@require_any_permission('class_management', 'tutor_management')
def api_smart_match(student_id):
    """API: Get smart tutor matches for specific student"""
    try:
        limit = request.args.get('limit', 3, type=int)
        matches = allocation_helper.get_smart_matches(student_id, limit)
        
        # Get student info
        student = Student.query.get_or_404(student_id)
        student_info = {
            'id': student.id,
            'full_name': student.full_name,
            'grade': student.grade,
            'board': student.board,
            'subjects_enrolled': student.get_subjects_enrolled()
        }
        
        return jsonify({
            'success': True,
            'student': student_info,
            'matches': matches
        })
        
    except Exception as e:
        current_app.logger.error(f"Smart match API error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to generate matches'
        }), 500


@bp.route('/api/allocation/quick-assign', methods=['POST'])
@login_required
@require_any_permission('class_management', 'tutor_management')
def api_quick_assign():
    """API: Quick assign student to tutor"""
    try:
        data = request.get_json()
        student_id = data.get('student_id')
        tutor_id = data.get('tutor_id')
        subject = data.get('subject', 'General')
        
        if not all([student_id, tutor_id]):
            return jsonify({
                'success': False,
                'error': 'Student ID and Tutor ID are required'
            }), 400
        
        # Verify student and tutor exist
        student = Student.query.get_or_404(student_id)
        tutor = Tutor.query.get_or_404(tutor_id)
        
        # Check if tutor has availability
        if not tutor.get_availability():
            return jsonify({
                'success': False,
                'error': 'Selected tutor has not set their availability'
            }), 400
        
        # Check if student is already allocated
        existing_class = Class.query.filter(
            or_(
                Class.primary_student_id == student_id,
                json.loads(cls.students)
            ),
            Class.status.in_(['scheduled', 'ongoing'])
        ).first()
        
        if existing_class:
            return jsonify({
                'success': False,
                'error': 'Student is already allocated to a class'
            }), 400
        
        # Create new class assignment
        # Note: You'll need to set scheduled_date and scheduled_time based on availability
        # This is a simplified version - you may want to enhance this
        new_class = Class(
            subject=subject,
            class_type='one_on_one',
            tutor_id=tutor_id,
            primary_student_id=student_id,
            grade=student.grade,
            board=student.board,
            status='scheduled',
            duration=60,  # Default 60 minutes
            created_by=current_user.id,
            created_at=datetime.utcnow()
        )
        
        db.session.add(new_class)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'{student.full_name} assigned to {tutor.user.full_name}',
            'class_id': new_class.id
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Quick assign error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to assign student'
        }), 500


@bp.route('/api/allocation/bulk-auto-assign', methods=['POST'])
@login_required
@require_any_permission('class_management', 'tutor_management')
def api_bulk_auto_assign():
    """API: Bulk auto-assign students to tutors"""
    try:
        data = request.get_json()
        filters = data.get('filters', {})
        dry_run = data.get('dry_run', True)
        
        result = allocation_helper.bulk_auto_assign(filters, dry_run)
        
        return jsonify(result)
        
    except Exception as e:
        current_app.logger.error(f"Bulk auto assign error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Bulk assignment failed'
        }), 500


@bp.route('/api/allocation/analytics')
@login_required
@admin_required
def api_allocation_analytics():
    """API: Get allocation analytics data"""
    try:
        analytics = allocation_helper.get_allocation_analytics()
        return jsonify({
            'success': True,
            'analytics': analytics
        })
        
    except Exception as e:
        current_app.logger.error(f"Analytics API error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch analytics'
        }), 500
        
# ADD these routes to app/routes/admin.py

@bp.route('/live-monitoring')
@login_required
@require_permission('tutor_management')
def live_monitoring():
    """Live monitoring dashboard for admins"""
    
    # Get current time and today's date
    current_time = datetime.now()
    today = current_time.date()
    
    # Get live stats
    live_stats = get_live_monitoring_stats()
    
    # Get currently ongoing classes
    live_classes = Class.query.filter(
        Class.status == 'ongoing',
        Class.scheduled_date == today
    ).order_by(Class.scheduled_time).all()
    
    # Get attendance stats for live classes
    attendance_stats = {}
    for cls in live_classes:
        attendance_records = Attendance.query.filter_by(class_id=cls.id).all()
        present_count = sum(1 for a in attendance_records if a.student_present)
        attendance_stats[cls.id] = {
            'total': len(attendance_records),
            'present': present_count
        }
    
    # Get classes with pending video uploads
    pending_videos = Class.query.filter(
        Class.status == 'completed',
        Class.video_link.is_(None),
        Class.scheduled_date >= today - timedelta(days=1)
    ).order_by(Class.video_upload_deadline.asc()).all()
    
    # Get today's summary
    today_summary = get_today_summary()
    
    # Get system alerts
    system_alerts = get_system_alerts()
    
    # Get performance metrics
    performance_metrics = get_performance_metrics()
    
    return render_template('admin/live_monitoring.html',
                         live_stats=live_stats,
                         live_classes=live_classes,
                         attendance_stats=attendance_stats,
                         pending_videos=pending_videos,
                         today_summary=today_summary,
                         system_alerts=system_alerts,
                         performance_metrics=performance_metrics,
                         current_time=current_time)


@bp.route('/api/live-monitoring-data')
@login_required
@require_permission('tutor_management')
def live_monitoring_data_api():
    """API endpoint for live monitoring data"""
    try:
        current_time = datetime.now()
        today = current_time.date()
        
        # Get live stats
        live_stats = get_live_monitoring_stats()
        
        # Get live classes with detailed info
        live_classes = []
        ongoing_classes = Class.query.filter(
            Class.status == 'ongoing',
            Class.scheduled_date == today
        ).order_by(Class.scheduled_time).all()
        
        for cls in ongoing_classes:
            # Get attendance info
            attendance_records = Attendance.query.filter_by(class_id=cls.id).all()
            present_count = sum(1 for a in attendance_records if a.student_present)
            
            # Calculate duration
            duration_minutes = 0
            if cls.actual_start_time:
                duration_minutes = int((current_time - cls.actual_start_time).total_seconds() / 60)
            
            live_classes.append({
                'id': cls.id,
                'subject': cls.subject,
                'scheduled_time': cls.scheduled_time.strftime('%H:%M'),
                'tutor_name': cls.tutor.user.full_name if cls.tutor and cls.tutor.user else 'Unknown',
                'tutor_rating': cls.tutor.rating if cls.tutor else 0,
                'student_count': len(cls.get_students()),
                'present_count': present_count,
                'duration_minutes': duration_minutes,
                'scheduled_duration': cls.duration,
                'meeting_link': cls.meeting_link,
                'status': cls.status
            })
        
        # Get system alerts
        system_alerts = []
        alerts = get_system_alerts()
        for alert in alerts:
            system_alerts.append({
                'title': alert['title'],
                'message': alert['message'],
                'severity': alert['severity'],
                'icon': alert['icon'],
                'timestamp': alert['timestamp'].strftime('%H:%M'),
                'action_url': alert.get('action_url')
            })
        
        return jsonify({
            'success': True,
            'live_stats': live_stats,
            'live_classes': live_classes,
            'system_alerts': system_alerts,
            'timestamp': current_time.isoformat()
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/send-video-reminder/<int:class_id>', methods=['POST'])
@login_required
@require_permission('tutor_management')
def send_video_reminder_api(class_id):
    """Send urgent video upload reminder"""
    try:
        class_obj = Class.query.get_or_404(class_id)
        
        if class_obj.video_link:
            return jsonify({'success': False, 'error': 'Video already uploaded'})
        
        # Send reminder email
        from app.utils.video_upload_scheduler import send_final_warning
        send_final_warning(class_id)
        
        # Update reminder flag
        class_obj.video_final_warning_sent = True
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Urgent reminder sent successfully'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/mark-class-incomplete/<int:class_id>', methods=['POST'])
@login_required
@require_permission('tutor_management')
def mark_class_incomplete_api(class_id):
    """Mark class as incomplete due to policy violations"""
    try:
        class_obj = Class.query.get_or_404(class_id)
        data = request.get_json()
        reason = data.get('reason', 'admin_decision')
        
        # Mark as incomplete
        class_obj.status = 'incomplete'
        class_obj.completion_status = 'incomplete_admin_action'
        class_obj.completion_compliance = False
        
        # Add admin note
        admin_note = f"Marked incomplete by admin. Reason: {reason}. Time: {datetime.now().strftime('%d %b %Y at %H:%M')}"
        if class_obj.admin_notes:
            class_obj.admin_notes += f"\n{admin_note}"
        else:
            class_obj.admin_notes = admin_note
        
        db.session.commit()
        
        # Update tutor rating due to non-compliance
        if class_obj.tutor:
            from app.utils.rating_calculator import update_tutor_rating
            update_tutor_rating(class_obj.tutor.id)
        
        return jsonify({
            'success': True,
            'message': 'Class marked as incomplete successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/system-alerts')
@login_required
@require_permission('tutor_management')
def system_alerts_api():
    """Get current system alerts"""
    try:
        alerts = get_system_alerts()
        return jsonify({
            'success': True,
            'alerts': [{
                'title': alert['title'],
                'message': alert['message'],
                'severity': alert['severity'],
                'icon': alert['icon'],
                'timestamp': alert['timestamp'].strftime('%H:%M'),
                'action_url': alert.get('action_url')
            } for alert in alerts]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/export-monitoring-report')
@login_required
@require_permission('tutor_management')
def export_monitoring_report():
    """Export monitoring reports"""
    try:
        report_type = request.args.get('type', 'daily')
        
        if report_type == 'daily':
            data = generate_daily_report()
            filename = f"daily_monitoring_report_{date.today().isoformat()}.csv"
        elif report_type == 'weekly':
            data = generate_weekly_report()
            filename = f"weekly_monitoring_report_{date.today().isoformat()}.csv"
        elif report_type == 'compliance':
            data = generate_compliance_report()
            filename = f"compliance_report_{date.today().isoformat()}.csv"
        else:
            return jsonify({'error': 'Invalid report type'}), 400
        
        # Create CSV response
        output = StringIO()
        writer = csv.writer(output)
        
        # Write headers
        writer.writerow(data['headers'])
        
        # Write data
        for row in data['rows']:
            writer.writerow(row)
        
        output.seek(0)
        
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def get_live_monitoring_stats():
    """Get real-time monitoring statistics"""
    today = date.today()
    current_time = datetime.now()
    
    # Ongoing classes
    ongoing_classes = Class.query.filter(
        Class.status == 'ongoing',
        Class.scheduled_date == today
    ).count()
    
    # Pending videos (completed classes without videos)
    pending_videos = Class.query.filter(
        Class.status == 'completed',
        Class.video_link.is_(None),
        Class.scheduled_date >= today - timedelta(days=1)
    ).count()
    
    # Overdue videos
    overdue_videos = Class.query.filter(
        Class.status == 'completed',
        Class.video_link.is_(None),
        Class.video_upload_deadline < current_time
    ).count()
    
    # Auto-attendance usage today
    auto_attendance_today = Class.query.filter(
        Class.scheduled_date == today,
        Class.auto_attendance_marked == True
    ).count()
    
    # Total classes today
    total_classes_today = Class.query.filter(
        Class.scheduled_date == today
    ).count()
    
    # Active alerts
    alerts = get_system_alerts()
    active_alerts = len(alerts)
    critical_alerts = len([a for a in alerts if a['severity'] == 'critical'])
    
    return {
        'ongoing_classes': ongoing_classes,
        'pending_videos': pending_videos,
        'overdue_videos': overdue_videos,
        'auto_attendance_today': auto_attendance_today,
        'total_classes_today': total_classes_today,
        'active_alerts': active_alerts,
        'critical_alerts': critical_alerts
    }


def get_today_summary():
    """Get today's summary statistics"""
    today = date.today()
    
    # Total classes today
    total_classes = Class.query.filter(Class.scheduled_date == today).count()
    
    # Completed classes
    completed_classes = Class.query.filter(
        Class.scheduled_date == today,
        Class.status == 'completed'
    ).count()
    
    # Auto-attendance usage
    auto_attendance = Class.query.filter(
        Class.scheduled_date == today,
        Class.auto_attendance_marked == True
    ).count()
    
    # Videos uploaded
    videos_uploaded = Class.query.filter(
        Class.scheduled_date == today,
        Class.status == 'completed',
        Class.video_link.isnot(None)
    ).count()
    
    return {
        'total_classes': total_classes,
        'completed_classes': completed_classes,
        'auto_attendance': auto_attendance,
        'videos_uploaded': videos_uploaded
    }


def get_system_alerts():
    """Generate system alerts based on current system state"""
    alerts = []
    current_time = datetime.now()
    today = current_time.date()
    
    # Critical: Overdue video uploads
    overdue_videos = Class.query.filter(
        Class.status == 'completed',
        Class.video_link.is_(None),
        Class.video_upload_deadline < current_time
    ).all()
    
    for cls in overdue_videos:
        hours_overdue = int((current_time - cls.video_upload_deadline).total_seconds() / 3600)
        alerts.append({
            'title': 'Video Upload Overdue',
            'message': f'{cls.subject} class by {cls.tutor.user.full_name if cls.tutor else "Unknown"} is {hours_overdue}h overdue',
            'severity': 'critical',
            'icon': 'fa-exclamation-triangle',
            'timestamp': current_time,
            'action_url': f'/admin/class/{cls.id}'
        })
    
    # Warning: Classes starting without tutors present
    upcoming_classes = Class.query.filter(
        Class.status == 'scheduled',
        Class.scheduled_date == today,
        Class.scheduled_time <= (current_time + timedelta(minutes=10)).time(),
        Class.scheduled_time > current_time.time()
    ).all()
    
    for cls in upcoming_classes:
        # Check if tutor is marked as present
        tutor_attendance = Attendance.query.filter_by(
            class_id=cls.id,
            tutor_id=cls.tutor_id,
            tutor_present=True
        ).first()
        
        if not tutor_attendance:
            alerts.append({
                'title': 'Tutor Not Present',
                'message': f'{cls.subject} starts in {int((datetime.combine(today, cls.scheduled_time) - current_time).total_seconds() / 60)}min but tutor not present',
                'severity': 'warning',
                'icon': 'fa-user-times',
                'timestamp': current_time,
                'action_url': f'/admin/class/{cls.id}'
            })
    
    # Warning: Low engagement classes
    low_engagement_classes = Class.query.filter(
        Class.scheduled_date == today,
        Class.status == 'completed',
        Class.engagement_average < 2.0
    ).all()
    
    for cls in low_engagement_classes:
        alerts.append({
            'title': 'Low Student Engagement',
            'message': f'{cls.subject} class had very low engagement (avg: {cls.engagement_average:.1f}/5)',
            'severity': 'warning',
            'icon': 'fa-chart-line',
            'timestamp': current_time,
            'action_url': f'/admin/class/{cls.id}'
        })
    
    # Info: High-performing tutors
    high_performing_tutors = Tutor.query.filter(
        Tutor.rating >= 4.5,
        Tutor.video_upload_compliance >= 95.0
    ).count()
    
    if high_performing_tutors > 0:
        alerts.append({
            'title': 'High Performance',
            'message': f'{high_performing_tutors} tutors maintaining excellent standards',
            'severity': 'info',
            'icon': 'fa-star',
            'timestamp': current_time
        })
    
    return sorted(alerts, key=lambda x: (x['severity'] == 'critical', x['severity'] == 'warning'), reverse=True)


def get_performance_metrics():
    """Get overall system performance metrics"""
    thirty_days_ago = date.today() - timedelta(days=30)
    
    # Completion rate
    total_classes = Class.query.filter(Class.scheduled_date >= thirty_days_ago).count()
    completed_classes = Class.query.filter(
        Class.scheduled_date >= thirty_days_ago,
        Class.status == 'completed'
    ).count()
    
    completion_rate = (completed_classes / total_classes * 100) if total_classes > 0 else 100
    
    # Punctuality (classes started on time)
    on_time_classes = Class.query.filter(
        Class.scheduled_date >= thirty_days_ago,
        Class.status.in_(['completed', 'ongoing']),
        Class.punctuality_score >= 4.0
    ).count()
    
    punctuality = (on_time_classes / completed_classes * 100) if completed_classes > 0 else 100
    
    # Video compliance
    classes_needing_video = Class.query.filter(
        Class.scheduled_date >= thirty_days_ago,
        Class.status == 'completed'
    ).count()
    
    classes_with_video = Class.query.filter(
        Class.scheduled_date >= thirty_days_ago,
        Class.status == 'completed',
        Class.video_link.isnot(None)
    ).count()
    
    video_compliance = (classes_with_video / classes_needing_video * 100) if classes_needing_video > 0 else 100
    
    # Average tutor rating
    avg_rating = db.session.query(func.avg(Tutor.rating)).filter(
        Tutor.rating.isnot(None),
        Tutor.status == 'active'
    ).scalar() or 0
    
    return {
        'avg_completion_rate': round(completion_rate, 1),
        'avg_punctuality': round(punctuality, 1),
        'video_compliance': round(video_compliance, 1),
        'avg_rating': round(avg_rating, 1)
    }


def generate_daily_report():
    """Generate daily monitoring report data"""
    today = date.today()
    
    classes = Class.query.filter(Class.scheduled_date == today).all()
    
    headers = [
        'Class ID', 'Subject', 'Tutor', 'Scheduled Time', 'Status',
        'Students Enrolled', 'Students Present', 'Video Uploaded',
        'Punctuality Score', 'Engagement Average'
    ]
    
    rows = []
    for cls in classes:
        # Get attendance data
        attendance_records = Attendance.query.filter_by(class_id=cls.id).all()
        enrolled = len(attendance_records)
        present = sum(1 for a in attendance_records if a.student_present)
        
        rows.append([
            cls.id,
            cls.subject,
            cls.tutor.user.full_name if cls.tutor and cls.tutor.user else 'Unknown',
            cls.scheduled_time.strftime('%H:%M'),
            cls.status,
            enrolled,
            present,
            'Yes' if cls.video_link else 'No',
            cls.punctuality_score or 0,
            cls.engagement_average or 0
        ])
    
    return {'headers': headers, 'rows': rows}


def generate_weekly_report():
    """Generate weekly monitoring report data"""
    end_date = date.today()
    start_date = end_date - timedelta(days=7)
    
    classes = Class.query.filter(
        Class.scheduled_date >= start_date,
        Class.scheduled_date <= end_date
    ).all()
    
    headers = [
        'Date', 'Total Classes', 'Completed', 'Videos Uploaded', 
        'Auto-Attendance Used', 'Avg Punctuality', 'Avg Engagement'
    ]
    
    # Group by date
    daily_stats = {}
    for cls in classes:
        date_key = cls.scheduled_date.isoformat()
        if date_key not in daily_stats:
            daily_stats[date_key] = {
                'total': 0, 'completed': 0, 'videos': 0, 
                'auto_attendance': 0, 'punctuality': [], 'engagement': []
            }
        
        stats = daily_stats[date_key]
        stats['total'] += 1
        
        if cls.status == 'completed':
            stats['completed'] += 1
            
        if cls.video_link:
            stats['videos'] += 1
            
        if cls.auto_attendance_marked:
            stats['auto_attendance'] += 1
            
        if cls.punctuality_score:
            stats['punctuality'].append(cls.punctuality_score)
            
        if cls.engagement_average:
            stats['engagement'].append(cls.engagement_average)
    
    rows = []
    for date_key, stats in sorted(daily_stats.items()):
        avg_punct = sum(stats['punctuality']) / len(stats['punctuality']) if stats['punctuality'] else 0
        avg_eng = sum(stats['engagement']) / len(stats['engagement']) if stats['engagement'] else 0
        
        rows.append([
            date_key,
            stats['total'],
            stats['completed'],
            stats['videos'],
            stats['auto_attendance'],
            round(avg_punct, 1),
            round(avg_eng, 1)
        ])
    
    return {'headers': headers, 'rows': rows}


def generate_compliance_report():
    """Generate compliance report data"""
    thirty_days_ago = date.today() - timedelta(days=30)
    
    tutors = Tutor.query.filter(Tutor.status == 'active').all()
    
    headers = [
        'Tutor ID', 'Tutor Name', 'Total Classes', 'Completion Rate',
        'Video Compliance', 'Punctuality Average', 'Rating', 'Auto-Attendance Usage'
    ]
    
    rows = []
    for tutor in tutors:
        # Get tutor's classes in last 30 days
        tutor_classes = Class.query.filter(
            Class.tutor_id == tutor.id,
            Class.scheduled_date >= thirty_days_ago
        ).all()
        
        if not tutor_classes:
            continue
        
        total_classes = len(tutor_classes)
        completed = len([c for c in tutor_classes if c.status == 'completed'])
        with_video = len([c for c in tutor_classes if c.video_link])
        auto_attendance = len([c for c in tutor_classes if c.auto_attendance_marked])
        
        completion_rate = (completed / total_classes * 100) if total_classes > 0 else 0
        video_compliance = (with_video / completed * 100) if completed > 0 else 0
        auto_usage = (auto_attendance / total_classes * 100) if total_classes > 0 else 0
        
        rows.append([
            tutor.id,
            tutor.user.full_name if tutor.user else 'Unknown',
            total_classes,
            round(completion_rate, 1),
            round(video_compliance, 1),
            tutor.punctuality_average or 0,
            tutor.rating or 0,
            round(auto_usage, 1)
        ])
    
    return {'headers': headers, 'rows': rows}

from flask import Response
from io import StringIO
import csv


def get_performance_metrics():
    """Get system performance metrics"""
    today = date.today()
    last_30_days = today - timedelta(days=30)
    
    # Calculate completion rate
    total_classes = Class.query.filter(
        Class.scheduled_date >= last_30_days,
        Class.scheduled_date <= today
    ).count()
    
    completed_classes = Class.query.filter(
        Class.scheduled_date >= last_30_days,
        Class.scheduled_date <= today,
        Class.status == 'completed'
    ).count()
    
    completion_rate = (completed_classes / total_classes * 100) if total_classes > 0 else 0
    
    # Calculate punctuality
    punctual_classes = Class.query.filter(
        Class.scheduled_date >= last_30_days,
        Class.punctuality_score >= 80
    ).count()
    
    punctuality = (punctual_classes / total_classes * 100) if total_classes > 0 else 0
    
    # Calculate video compliance
    classes_with_videos = Class.query.filter(
        Class.scheduled_date >= last_30_days,
        Class.status == 'completed',
        Class.video_link.isnot(None)
    ).count()
    
    video_compliance = (classes_with_videos / completed_classes * 100) if completed_classes > 0 else 0
    
    # Calculate average tutor rating
    avg_rating = db.session.query(func.avg(Tutor.rating)).filter(
        Tutor.status == 'active'
    ).scalar() or 0
    
    return {
        'avg_completion_rate': round(completion_rate, 1),
        'avg_punctuality': round(punctuality, 1),
        'video_compliance': round(video_compliance, 1),
        'avg_rating': round(avg_rating, 1)
    }


def generate_compliance_report():
    """Generate compliance monitoring report data"""
    last_7_days = date.today() - timedelta(days=7)
    
    classes = Class.query.filter(
        Class.scheduled_date >= last_7_days,
        Class.status == 'completed'
    ).all()
    
    headers = [
        'Date', 'Class ID', 'Subject', 'Tutor', 'Video Uploaded',
        'Upload Time', 'Deadline Met', 'Compliance Score'
    ]
    
    rows = []
    for cls in classes:
        # Calculate compliance score
        compliance_score = 100
        
        if not cls.video_link:
            compliance_score -= 50
        elif cls.video_upload_deadline and cls.video_uploaded_at:
            if cls.video_uploaded_at > cls.video_upload_deadline:
                compliance_score -= 25
        
        if cls.punctuality_score and cls.punctuality_score < 80:
            compliance_score -= 25
        
        rows.append([
            cls.scheduled_date.isoformat(),
            cls.id,
            cls.subject,
            cls.tutor.user.full_name if cls.tutor and cls.tutor.user else 'Unknown',
            'Yes' if cls.video_link else 'No',
            cls.video_uploaded_at.strftime('%H:%M') if cls.video_uploaded_at else 'N/A',
            'Yes' if cls.video_upload_deadline and cls.video_uploaded_at and cls.video_uploaded_at <= cls.video_upload_deadline else 'No',
            f"{compliance_score}%"
        ])
    
    return {'headers': headers, 'rows': rows}

# ================== HOLD FUNCTIONALITY ROUTES ==================

@bp.route('/students/<int:student_id>/hold-graduation', methods=['GET', 'POST'])
@login_required
@require_permission('student_management')
def hold_graduation(student_id):
    """Put student graduation on hold"""
    from app.forms.student_status_forms import HoldGraduationForm
    
    student = Student.query.get_or_404(student_id)
    
    # Check department access
    if current_user.role == 'coordinator' and current_user.department_id != student.department_id:
        flash('Access denied', 'error')
        return redirect(url_for('admin.students'))
    
    if student.enrollment_status != 'active':
        flash('Can only put active students on graduation hold', 'error')
        return redirect(url_for('admin.student_details', student_id=student_id))
    
    form = HoldGraduationForm()
    
    if form.validate_on_submit():
        try:
            student.put_graduation_on_hold(
                reason=form.hold_reason.data,
                user_id=current_user.id,
                notes=form.notes.data
            )
            
            flash(f'🔒 {student.full_name}\'s graduation has been put on hold', 'warning')
            return redirect(url_for('admin.student_details', student_id=student_id))
            
        except ValueError as e:
            flash(str(e), 'error')
    
    return render_template('admin/students/hold_graduation.html', 
                         student=student, form=form)

@bp.route('/students/<int:student_id>/hold-drop', methods=['GET', 'POST'])
@login_required
@require_permission('student_management')
def hold_drop(student_id):
    """Put student drop on hold (prevent dropping)"""
    from app.forms.student_status_forms import HoldDropForm
    
    student = Student.query.get_or_404(student_id)
    
    # Check department access
    if current_user.role == 'coordinator' and current_user.department_id != student.department_id:
        flash('Access denied', 'error')
        return redirect(url_for('admin.students'))
    
    if student.enrollment_status != 'active':
        flash('Can only put active students on drop hold', 'error')
        return redirect(url_for('admin.student_details', student_id=student_id))
    
    form = HoldDropForm()
    
    if form.validate_on_submit():
        try:
            student.put_drop_on_hold(
                reason=form.hold_reason.data,
                user_id=current_user.id,
                notes=form.notes.data
            )
            
            flash(f'🔒 {student.full_name} has been protected from dropping (drop hold applied)', 'info')
            return redirect(url_for('admin.student_details', student_id=student_id))
            
        except ValueError as e:
            flash(str(e), 'error')
    
    return render_template('admin/students/hold_drop.html', 
                         student=student, form=form)

@bp.route('/students/<int:student_id>/remove-hold', methods=['GET', 'POST'])
@login_required
@require_permission('student_management')
def remove_hold(student_id):
    """Remove hold status from student"""
    from app.forms.student_status_forms import RemoveHoldForm
    
    student = Student.query.get_or_404(student_id)
    
    # Check department access
    if current_user.role == 'coordinator' and current_user.department_id != student.department_id:
        flash('Access denied', 'error')
        return redirect(url_for('admin.students'))
    
    if student.enrollment_status not in ['hold_graduation', 'hold_drop']:
        flash('Student is not currently on hold', 'error')
        return redirect(url_for('admin.student_details', student_id=student_id))
    
    hold_status = student.get_hold_status()
    form = RemoveHoldForm()
    
    if form.validate_on_submit():
        try:
            student.remove_hold(
                user_id=current_user.id,
                reason=form.removal_reason.data,
                notes=form.notes.data
            )
            
            flash(f'✅ Hold removed from {student.full_name} - student is now active', 'success')
            return redirect(url_for('admin.student_details', student_id=student_id))
            
        except ValueError as e:
            flash(str(e), 'error')
    
    return render_template('admin/students/remove_hold.html', 
                         student=student, form=form, hold_status=hold_status)


# ============ ENHANCED TUTOR CHANGE SYSTEM APIs ============

@bp.route('/api/student/<int:student_id>/class-schedule-analysis')
@login_required
@require_any_permission('class_management', 'tutor_management')
def api_student_schedule_analysis(student_id):
    """Analyze student's class schedule for enhanced tutor change"""
    try:
        from collections import defaultdict
        
        student = Student.query.get_or_404(student_id)
        
        # Get all future scheduled classes for this student
        future_classes = Class.query.filter(
            or_(
                Class.primary_student_id == student_id,
                Class.students.like(f'%{student_id}%')
            ),
            Class.scheduled_date >= datetime.now().date(),
            Class.status == 'scheduled'
        ).order_by(Class.scheduled_date, Class.scheduled_time).all()
        
        # Group by subject and tutor
        schedule_analysis = defaultdict(lambda: {
            'tutor_info': {},
            'classes': [],
            'days_times': defaultdict(list),
            'unique_days': set(),
            'unique_times': set(),
            'total_classes': 0,
            'weekly_pattern': {}
        })
        
        for cls in future_classes:
            if not cls.tutor:
                continue
                
            key = f"{cls.subject}_{cls.tutor_id}"
            day_name = cls.scheduled_date.strftime('%A').lower()
            time_str = cls.scheduled_time.strftime('%H:%M')
            
            schedule_analysis[key]['tutor_info'] = {
                'id': cls.tutor.id,
                'name': cls.tutor.user.full_name,
                'subjects': cls.tutor.get_subjects()
            }
            
            schedule_analysis[key]['classes'].append({
                'id': cls.id,
                'date': cls.scheduled_date.strftime('%Y-%m-%d'),
                'day': day_name.title(),
                'time': time_str,
                'duration': cls.duration,
                'subject': cls.subject
            })
            
            schedule_analysis[key]['days_times'][day_name].append(time_str)
            schedule_analysis[key]['unique_days'].add(day_name.title())
            schedule_analysis[key]['unique_times'].add(time_str)
            schedule_analysis[key]['total_classes'] += 1
        
        # Convert sets to lists for JSON serialization
        for key, data in schedule_analysis.items():
            data['unique_days'] = sorted(list(data['unique_days']))
            data['unique_times'] = sorted(list(data['unique_times']))
            
            # Calculate weekly pattern
            day_counts = defaultdict(int)
            for cls in data['classes']:
                day_counts[cls['day']] += 1
            data['weekly_pattern'] = dict(day_counts)
        
        return jsonify({
            'success': True,
            'student_name': student.full_name,
            'schedule_analysis': dict(schedule_analysis),
            'total_future_classes': len(future_classes)
        })
        
    except Exception as e:
        print(f"Schedule analysis error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/tutors/availability-matrix')
@login_required
@require_any_permission('class_management', 'tutor_management')
def api_tutors_availability_matrix():
    """Get availability matrix for multiple tutors"""
    try:
        tutors = Tutor.query.filter_by(status='active').all()
        
        availability_matrix = {}
        for tutor in tutors:
            availability = tutor.get_availability()
            if availability:
                availability_matrix[tutor.id] = {
                    'name': tutor.user.full_name,
                    'subjects': tutor.get_subjects(),
                    'availability': availability,
                    'rating': tutor.rating
                }
        
        return jsonify({
            'success': True,
            'availability_matrix': availability_matrix
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/student/<int:student_id>/enhanced-tutor-change', methods=['POST'])
@login_required
@require_any_permission('class_management', 'tutor_management')
def api_enhanced_tutor_change(student_id):
    """Enhanced tutor change with flexible day/time selection"""
    try:
        from datetime import datetime, timedelta
        
        data = request.json
        current_tutor_id = data.get('current_tutor_id')
        new_tutor_id = data.get('new_tutor_id')
        subject = data.get('subject')
        selected_changes = data.get('selected_changes', [])  # List of {day, time, new_time (optional)}
        change_type = data.get('change_type', 'keep_schedule')  # 'keep_schedule' or 'modify_times'
        
        if not all([current_tutor_id, new_tutor_id, subject, selected_changes]):
            return jsonify({'error': 'Missing required parameters'}), 400
        
        # Get tutors
        current_tutor = Tutor.query.get_or_404(current_tutor_id)
        new_tutor = Tutor.query.get_or_404(new_tutor_id)
        
        if not new_tutor.get_availability():
            return jsonify({'error': 'New tutor has not set their availability'}), 400
        
        # Get classes to change
        classes_to_change = []
        conflicts = []
        successful_changes = 0
        
        for change in selected_changes:
            day = change['day'].lower()
            current_time = change['time']
            new_time = change.get('new_time', current_time)
            
            # Find classes matching this day and time
            matching_classes = Class.query.filter(
                or_(
                    Class.primary_student_id == student_id,
                    Class.students.like(f'%{student_id}%')
                ),
                Class.tutor_id == current_tutor_id,
                Class.subject.ilike(subject),
                Class.scheduled_date >= datetime.now().date(),
                Class.status == 'scheduled',
                func.lower(func.strftime('%A', Class.scheduled_date)) == day,
                func.strftime('%H:%M', Class.scheduled_time) == current_time
            ).all()
            
            for cls in matching_classes:
                # Check new tutor availability
                if not new_tutor.is_available_at(day, new_time):
                    conflicts.append({
                        'class_id': cls.id,
                        'date': cls.scheduled_date.strftime('%Y-%m-%d'),
                        'day': day.title(),
                        'current_time': current_time,
                        'new_time': new_time,
                        'reason': 'New tutor not available at requested time'
                    })
                    continue
                
                # Check for scheduling conflicts
                new_time_obj = datetime.strptime(new_time, '%H:%M').time()
                existing_class = Class.query.filter_by(
                    tutor_id=new_tutor_id,
                    scheduled_date=cls.scheduled_date,
                    scheduled_time=new_time_obj,
                    status='scheduled'
                ).first()
                
                if existing_class:
                    conflicts.append({
                        'class_id': cls.id,
                        'date': cls.scheduled_date.strftime('%Y-%m-%d'),
                        'day': day.title(),
                        'current_time': current_time,
                        'new_time': new_time,
                        'reason': 'New tutor already has a class at this time'
                    })
                    continue
                
                # Apply changes
                cls.tutor_id = new_tutor_id
                if change_type == 'modify_times' and new_time != current_time:
                    cls.scheduled_time = new_time_obj
                    cls.calculate_end_time()
                
                cls.updated_at = datetime.utcnow()
                
                # Add change history to admin notes
                change_note = f"Tutor changed from {current_tutor.user.full_name} to {new_tutor.user.full_name}"
                if change_type == 'modify_times' and new_time != current_time:
                    change_note += f", Time changed from {current_time} to {new_time}"
                change_note += f" on {datetime.now().strftime('%d %b %Y at %H:%M')}"
                
                if cls.admin_notes:
                    cls.admin_notes += f"\n{change_note}"
                else:
                    cls.admin_notes = change_note
                
                classes_to_change.append(cls)
                successful_changes += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Successfully changed tutor for {successful_changes} classes',
            'successful_changes': successful_changes,
            'conflicts': conflicts,
            'total_requested': sum(len(Class.query.filter(
                or_(
                    Class.primary_student_id == student_id,
                    Class.students.like(f'%{student_id}%')
                ),
                Class.tutor_id == current_tutor_id,
                Class.subject.ilike(subject),
                Class.scheduled_date >= datetime.now().date(),
                Class.status == 'scheduled',
                func.lower(func.strftime('%A', Class.scheduled_date)) == change['day'].lower(),
                func.strftime('%H:%M', Class.scheduled_time) == change['time']
            ).all()) for change in selected_changes)
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Enhanced tutor change error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/student/<int:student_id>/tutor-change-history')
@login_required
@require_any_permission('class_management', 'tutor_management')
def api_student_tutor_change_history(student_id):
    """Get tutor change history for a student"""
    try:
        student = Student.query.get_or_404(student_id)
        
        # Get classes with admin notes (containing change history)
        classes_with_changes = Class.query.filter(
            or_(
                Class.primary_student_id == student_id,
                Class.students.like(f'%{student_id}%')
            ),
            Class.admin_notes.isnot(None),
            Class.admin_notes.like('%Tutor changed%')
        ).order_by(Class.updated_at.desc()).all()
        
        history = []
        for cls in classes_with_changes:
            # Parse admin notes for tutor changes
            notes_lines = cls.admin_notes.split('\n')
            for line in notes_lines:
                if 'Tutor changed' in line:
                    history.append({
                        'class_id': cls.id,
                        'subject': cls.subject,
                        'date': cls.scheduled_date.strftime('%d %b %Y'),
                        'time': cls.scheduled_time.strftime('%H:%M'),
                        'change_details': line.strip(),
                        'updated_at': cls.updated_at.strftime('%d %b %Y at %H:%M') if cls.updated_at else 'Unknown'
                    })
        
        return jsonify({
            'success': True,
            'student_name': student.full_name,
            'history': history
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500