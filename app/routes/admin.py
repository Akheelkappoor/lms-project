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


bp = Blueprint('admin', __name__)

matching_engine = TutorMatchingEngine()

def admin_required(f):
    """Decorator to require admin access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role not in ['superadmin', 'admin', 'coordinator']:
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
@admin_required
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
        query = query.filter(
            (User.full_name.contains(search)) |
            (User.username.contains(search)) |
            (User.email.contains(search))
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
@admin_required
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
@admin_required
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
@admin_required
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
@admin_required
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
@admin_required
def departments():
    """Department management page"""
    departments = Department.query.order_by(Department.created_at.desc()).all()
    return render_template('admin/departments.html', departments=departments)

@bp.route('/departments/create', methods=['POST'])
@login_required
@admin_required
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
@admin_required
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
@admin_required
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
@admin_required
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
@admin_required
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

# ============ TUTOR MANAGEMENT ROUTES ============

@bp.route('/tutors')
@login_required
@admin_required
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
        query = query.filter(User.full_name.contains(search))
    
    tutors = query.order_by(Tutor.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    departments = Department.query.filter_by(is_active=True).all()

    filtered_args = request.args.to_dict()
    filtered_args.pop('page', None)  
    
    return render_template('admin/tutors.html', tutors=tutors, departments=departments, filtered_args=filtered_args )


@bp.route('/tutors/register', methods=['GET', 'POST'])
@login_required
@admin_required
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
@admin_required
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
@admin_required
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
@admin_required
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

# ============ STUDENT MANAGEMENT ROUTES ============

# Replace the students route in app/routes/admin.py

@bp.route('/students')
@login_required
@admin_required
def students():
    """Student management page"""
    from sqlalchemy import or_
    
    page = request.args.get('page', 1, type=int)
    grade_filter = request.args.get('grade', '').strip()
    dept_filter_raw = request.args.get('department', '').strip()
    search = request.args.get('search', '').strip()
    
    # Convert department filter to int only if it's a valid number
    dept_filter = None
    if dept_filter_raw and dept_filter_raw.isdigit():
        dept_filter = int(dept_filter_raw)
    
    # Build base query
    query = Student.query
    
    # Apply department access check for coordinators FIRST
    if current_user.role == 'coordinator':
        query = query.filter_by(department_id=current_user.department_id)
    
    # Apply filters only if they have valid values
    if grade_filter:
        query = query.filter_by(grade=grade_filter)
    
    # Only apply department filter if user selected a specific department AND user is not a coordinator
    if dept_filter and dept_filter > 0 and current_user.role != 'coordinator':
        query = query.filter_by(department_id=dept_filter)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Student.full_name.ilike(search_term),
                Student.email.ilike(search_term)
            )
        )
    
    # Get paginated results
    students = query.order_by(Student.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    # Calculate stats from the filtered query
    stats = {
        'total_students': query.count(),
        'active_students': query.filter_by(enrollment_status='active').count(),
        'paused_students': query.filter_by(enrollment_status='paused').count(),
        'completed_students': query.filter_by(enrollment_status='completed').count(),
        'dropped_students': query.filter_by(enrollment_status='dropped').count()
    }
    
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
@admin_required
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
            
            # Fee structure
            fee_structure = {
                'total_fee': float(getattr(form, 'total_fee', None) and form.total_fee.data or 0),
                'amount_paid': float(getattr(form, 'amount_paid', None) and form.amount_paid.data or 0),
                'payment_mode': getattr(form, 'payment_mode', None) and form.payment_mode.data or '',
                'payment_schedule': getattr(form, 'payment_schedule', None) and form.payment_schedule.data or ''
            }
            fee_structure['balance_amount'] = fee_structure['total_fee'] - fee_structure['amount_paid']
            student.set_fee_structure(fee_structure)
            
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
@admin_required
def student_details(student_id):
    """View student details"""
    student = Student.query.get_or_404(student_id)
    
    # Check department access
    if current_user.role == 'coordinator' and current_user.department_id != student.department_id:
        flash('Access denied. You can only view students from your department.', 'error')
        return redirect(url_for('admin.students'))
    
    # Get student's classes
    student_classes = []
    all_classes = Class.query.order_by(Class.scheduled_date.desc()).all()
    
    for cls in all_classes:
        if student.id in cls.get_students():
            student_classes.append(cls)
    
    student_classes = student_classes[:20]  # Limit to recent 20 classes
    
    # Get attendance summary
    attendance_summary = Attendance.get_attendance_summary(student_id=student.id)
    
    # Get upcoming classes
    upcoming_classes = []
    for cls in Class.query.filter(
        Class.scheduled_date >= date.today(),
        Class.status == 'scheduled'
    ).order_by(Class.scheduled_date, Class.scheduled_time).all():
        if student.id in cls.get_students():
            upcoming_classes.append(cls)
    
    upcoming_classes = upcoming_classes[:5]  # Next 5 classes
    
    return render_template('admin/student_details.html',
                         student=student,
                         classes=student_classes,
                         upcoming_classes=upcoming_classes,
                         attendance_summary=attendance_summary)

# COMPLETE REPLACEMENT for edit_student route in app/routes/admin.py

@bp.route('/students/<int:student_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
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
@admin_required
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
@admin_required
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
@admin_required
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

@bp.route('/students/<int:student_id>/delete', methods=['DELETE'])
@login_required
@admin_required
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
@admin_required
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
    
    classes = query.order_by(Class.scheduled_date.desc(), Class.scheduled_time.desc()).paginate(
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
@admin_required
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
@admin_required
def bulk_create_classes():
    """Create multiple classes in bulk with availability validation"""
    try:
        from datetime import timedelta
        
        # Get form data with validation
        subject = request.form.get('subject', '').strip()
        grade = request.form.get('grade', '').strip()
        duration = request.form.get('duration', '')
        tutor_id = request.form.get('tutor_id', '')
        class_type = request.form.get('class_type', '')
        
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
@admin_required
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



@bp.route('/classes/<int:class_id>')
@login_required
@admin_required
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


@bp.route('/api/v1/check-class-conflict')
@login_required
@admin_required
def api_check_class_conflict():
    """Check for scheduling conflicts"""
    try:
        tutor_id = request.args.get('tutor_id', type=int)
        date_str = request.args.get('date')
        time_str = request.args.get('time')
        
        if not all([tutor_id, date_str, time_str]):
            return jsonify({'error': 'Missing required parameters'}), 400
        
        tutor = Tutor.query.get_or_404(tutor_id)
        scheduled_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        scheduled_time = datetime.strptime(time_str, '%H:%M').time()
        
        # Check tutor availability
        day_of_week = scheduled_date.strftime('%A').lower()
        is_available = tutor.is_available_at(day_of_week, time_str)
        
        # Check for existing classes
        existing_class = Class.query.filter_by(
            tutor_id=tutor_id,
            scheduled_date=scheduled_date,
            scheduled_time=scheduled_time,
            status='scheduled'
        ).first()
        
        return jsonify({
            'available': is_available,
            'has_conflict': bool(existing_class),
            'can_schedule': is_available and not existing_class,
            'message': 'Available' if (is_available and not existing_class) else 
                      'Tutor not available at this time' if not is_available else 
                      'Tutor already has a class at this time'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
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
@admin_required
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

# ============ TIMETABLE MANAGEMENT ============

@bp.route('/timetable')
@login_required
@admin_required
def timetable():
    """Timetable management page"""
    try:
        departments = Department.query.filter_by(is_active=True).all()
        tutors = Tutor.query.filter(Tutor.status == 'active').all()
        students = Student.query.filter(Student.is_active == True).limit(100).all()
        
        return render_template('admin/timetable.html', 
                             departments=departments,
                             tutors=tutors,
                             students=students)
                             
    except Exception as e:
        flash('Error loading timetable page', 'error')
        return redirect(url_for('dashboard.index'))

# ============ API ROUTES FOR DASHBOARD/TIMETABLE ============

@bp.route('/api/v1/timetable/week')
@login_required
@admin_required
def api_timetable_week():
    """Get weekly timetable data"""
    try:
        date_param = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
        target_date = datetime.strptime(date_param, '%Y-%m-%d').date()
        
        # Get start of week (Monday)
        start_of_week = target_date - timedelta(days=target_date.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        
        classes = Class.query.filter(
            Class.scheduled_date >= start_of_week,
            Class.scheduled_date <= end_of_week
        ).order_by(Class.scheduled_date, Class.scheduled_time).all()
        
        classes_data = []
        for cls in classes:
            try:
                class_item = {
                    'id': cls.id,
                    'subject': cls.subject,
                    'class_type': cls.class_type,
                    'scheduled_date': cls.scheduled_date.strftime('%Y-%m-%d'),
                    'scheduled_time': cls.scheduled_time.strftime('%H:%M'),
                    'duration': cls.duration,
                    'status': cls.status,
                    'tutor_name': 'No Tutor Assigned',
                    'student_count': 0
                }
                
                # Get tutor name safely
                if cls.tutor and hasattr(cls.tutor, 'user') and cls.tutor.user:
                    class_item['tutor_name'] = cls.tutor.user.full_name
                
                # Get student count safely
                try:
                    if hasattr(cls, 'get_students'):
                        student_ids = cls.get_students()
                        class_item['student_count'] = len(student_ids) if student_ids else 0
                except:
                    pass
                
                classes_data.append(class_item)
            except:
                continue
        
        # Simple stats
        total_classes = len(classes_data)
        scheduled_classes = len([c for c in classes_data if c['status'] == 'scheduled'])
        completed_classes = len([c for c in classes_data if c['status'] == 'completed'])
        
        stats = {
            'total_classes': total_classes,
            'scheduled_classes': scheduled_classes,
            'completed_classes': completed_classes,
            'completion_rate': round((completed_classes / total_classes * 100) if total_classes > 0 else 0, 1)
        }
        
        return jsonify({
            'success': True,
            'classes': classes_data,
            'stats': stats,
            'week_start': start_of_week.strftime('%Y-%m-%d'),
            'week_end': end_of_week.strftime('%Y-%m-%d')
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/api/v1/timetable/today')
@login_required
@admin_required
def api_timetable_today():
    """Get today's timetable data"""
    try:
        today = date.today()
        
        classes = Class.query.filter(Class.scheduled_date == today)\
                           .order_by(Class.scheduled_time).all()
        
        classes_data = []
        for cls in classes:
            try:
                class_item = {
                    'id': cls.id,
                    'subject': cls.subject,
                    'scheduled_time': cls.scheduled_time.strftime('%H:%M'),
                    'duration': cls.duration,
                    'status': cls.status,
                    'tutor_name': 'No Tutor Assigned',
                    'student_name': 'No Students'
                }
                
                # Get tutor name
                if cls.tutor and hasattr(cls.tutor, 'user') and cls.tutor.user:
                    class_item['tutor_name'] = cls.tutor.user.full_name
                
                # Get first student name
                try:
                    if hasattr(cls, 'get_students'):
                        student_ids = cls.get_students()
                        if student_ids:
                            students = Student.query.filter(Student.id.in_(student_ids)).all()
                            if students:
                                class_item['student_name'] = students[0].full_name
                                if len(students) > 1:
                                    class_item['student_name'] += f' +{len(students)-1} more'
                except:
                    pass
                
                classes_data.append(class_item)
            except:
                continue
        
        return jsonify({
            'success': True,
            'classes': classes_data,
            'date': today.strftime('%Y-%m-%d')
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

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
@admin_required
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
@admin_required
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
        tutor_salary_data.append({
            'tutor': tutor,
            'calculation': salary_calc,
            'outstanding': tutor.get_outstanding_salary()
        })
    
    return render_template('admin/salary_generation.html',
                         tutors=tutor_salary_data,
                         current_month=current_month,
                         current_year=current_year)

@bp.route('/fee-collection')
@login_required
@admin_required
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
@admin_required
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
@admin_required
def course_batches():
    """Course batch management page - groups classes intelligently"""
    from collections import defaultdict
    from datetime import datetime, timedelta, date
    import time
    import json
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

    student_ids = set()
    for cls in classes:
        try:
            ids = cls.get_students() or []
            student_ids.update(ids)
        except Exception:
            continue

    students_by_id = {}
    if student_ids:
        students = Student.query.filter(Student.id.in_(student_ids)).all()
        students_by_id = {s.id: s for s in students}

    batches = defaultdict(lambda: {
        'classes': [],
        'students': set(),
        'tutor': None,
        'subject': '',
        'date_range': {'start': None, 'end': None},
        'total_classes': 0,
        'completed_classes': 0,
        'scheduled_classes': 0,
        'active_students': set(),
        'completed_students': set()
    })

    for cls in classes:
        if not cls.tutor or not cls.scheduled_date:
            continue

        month_year_key = cls.scheduled_date.strftime('%Y-%m')
        batch_key = f"{cls.subject}_{cls.tutor_id}_{month_year_key}"

        batch = batches[batch_key]
        batch['classes'].append(cls)
        batch['tutor'] = cls.tutor
        batch['subject'] = cls.subject
        batch['total_classes'] += 1

        if cls.status == 'completed':
            batch['completed_classes'] += 1
        elif cls.status == 'scheduled':
            batch['scheduled_classes'] += 1

        dr = batch['date_range']
        dr['start'] = min(dr['start'], cls.scheduled_date) if dr['start'] else cls.scheduled_date
        dr['end']   = max(dr['end'],   cls.scheduled_date) if dr['end']   else cls.scheduled_date

        try:
            ids = cls.get_students() or []
            for sid in ids:
                batch['students'].add(sid)
                st = students_by_id.get(sid)
                if st:
                    if hasattr(st, "is_course_active") and st.is_course_active(cls.scheduled_date):
                        batch['active_students'].add(sid)
                    elif st.enrollment_status == 'completed':
                        batch['completed_students'].add(sid)
        except Exception:
            pass

    batch_list = []
    for key, b in batches.items():
        b['batch_id'] = key
        b['student_count']            = len(b['students'])
        b['active_student_count']     = len(b['active_students'])
        b['completed_student_count']  = len(b['completed_students'])
        b['progress_percentage'] = round(
            (b['completed_classes'] / b['total_classes']) * 100, 1
        ) if b['total_classes'] else 0

        ids_slice = list(b['students'])[:5]
        b['student_objects'] = [students_by_id[i] for i in ids_slice if i in students_by_id]

        batch_list.append(b)

    batch_list.sort(key=lambda x: x['date_range']['end'] or date.min, reverse=True)

    activate_param = request.args.get('activate')  
    if activate_param in ('0', '1'):
        want_active = (activate_param == '1')
        filtered = []
        for b in batch_list:
            has_any = b['active_student_count'] > 0
            if has_any is want_active:
                filtered.append(b)
        batch_list = filtered
    batch_list.sort(key=lambda x: x['date_range']['end'] or date.min, reverse=True)

    months = sorted(
        {cls.scheduled_date.strftime('%Y-%m') for cls in classes if cls.scheduled_date},
        reverse=True
    )
    tutors = Tutor.query.filter_by(status='active').all()
    
    from math import ceil

    class SimplePagination:
        def __init__(self, page, per_page, total):
            self.page       = page
            self.per_page   = per_page
            self.total      = total
            self.pages      = ceil(total / per_page) if per_page else 0
            self.has_prev   = page > 1
            self.has_next   = page < self.pages
            self.prev_num   = page - 1 if self.has_prev else None
            self.next_num   = page + 1 if self.has_next else None
            
        def iter_pages(self, left_edge=1, right_edge=1,
                    left_current=1, right_current=2):
            """
            Only yield pages 1 through 10 (and an ellipsis + last page if total > 10).
            Signature matches what your template calls.
            """
            max_shown = 10
            for num in range(1, min(self.pages, max_shown) + 1):
                yield num


            if self.pages > max_shown:
                yield None
                yield self.pages


    page      = request.args.get('page', 1, type=int)
    per_page  = 6
    total     = len(batch_list)

    start     = (page - 1) * per_page
    end       = start + per_page
    page_items = batch_list[start:end]

    filtered_args = request.args.to_dict()
    filtered_args.pop('page', None)

    pagination = SimplePagination(page, per_page, total)

    return render_template(
        'admin/course_batches.html',
        batches=page_items,
        pagination=pagination,
        filtered_args=filtered_args,
        tutors=tutors,
        months=months,
        total_batches=total
    )


@bp.route('/course-batches/<batch_id>')
@login_required
@admin_required
def course_batch_details(batch_id):
    """View detailed information about a specific course batch."""
    from datetime import datetime, date
    from sqlalchemy.orm import selectinload
    import traceback

    try:
        parts = batch_id.split('_', 2) 
        if len(parts) != 3:
            raise ValueError("Bad batch_id parts count")

        raw_subject, raw_tutor_id, month_year = parts
        subject = raw_subject.replace('-', ' ')  
        tutor_id = int(raw_tutor_id)

        month_dt = datetime.strptime(month_year, '%Y-%m').date()
        start_date = month_dt.replace(day=1)
        # first day of next month
        if month_dt.month == 12:
            end_date = month_dt.replace(year=month_dt.year + 1, month=1, day=1)
        else:
            end_date = month_dt.replace(month=month_dt.month + 1, day=1)

    except Exception as e:
        traceback.print_exc()
        flash('Invalid batch ID', 'error')
        return redirect(url_for('admin.course_batches'))

    classes = (
        Class.query
        .options(selectinload(Class.tutor))
        .filter(
            Class.subject == subject,            
            Class.tutor_id == tutor_id,
            Class.scheduled_date >= start_date,
            Class.scheduled_date < end_date
        )
        .order_by(Class.scheduled_date.desc(), Class.scheduled_time.desc())
        .all()
    )

    if not classes:
        flash('No classes found for this batch', 'error')
        return redirect(url_for('admin.course_batches'))


    all_student_ids = set()
    for c in classes:
        try:
            ids = c.get_students() or []
            all_student_ids.update(ids)
        except Exception:
            # Log but continue
            traceback.print_exc()

    students_by_id = {}
    students = []
    if all_student_ids:
        students = Student.query.filter(Student.id.in_(all_student_ids)).all()
        students_by_id = {s.id: s for s in students}

    total_classes     = len(classes)
    completed_classes = sum(1 for c in classes if c.status == 'completed')
    scheduled_classes = sum(1 for c in classes if c.status == 'scheduled')
    cancelled_classes = sum(1 for c in classes if c.status == 'cancelled')

    total_students    = len(students)
    active_students   = sum(1 for s in students if s.enrollment_status == 'active')
    completed_students= sum(1 for s in students if s.enrollment_status == 'completed')

    stats = {
        'total_classes': total_classes,
        'completed_classes': completed_classes,
        'scheduled_classes': scheduled_classes,
        'cancelled_classes': cancelled_classes,
        'total_students': total_students,
        'active_students': active_students,
        'completed_students': completed_students
    }

    tutor = classes[0].tutor if classes else Tutor.query.get(tutor_id)

    return render_template(
        'admin/course_batch_details.html',
        classes=classes,
        students=students,
        tutor=tutor,
        batch_id=batch_id,
        subject=subject,
        stats=stats
    )
