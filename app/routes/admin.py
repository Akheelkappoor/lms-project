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
from functools import wraps
from app.utils.email import send_password_reset_email, send_onboarding_email
bp = Blueprint('admin', __name__)

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
    
    return render_template('admin/users.html', users=users, departments=departments)

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
    
    return render_template('admin/tutors.html', tutors=tutors, departments=departments)


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
                else:
                    raise ValueError(f"{video_name.replace('_', ' ').title()} is required")
            
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
    action = request.json.get('action')  # 'approve' or 'reject'
    
    try:
        if action == 'approve':
            tutor.verification_status = 'verified'
            tutor.status = 'active'
            tutor.user.is_verified = True
            message = f'Tutor {tutor.user.full_name} has been verified and activated.'
        elif action == 'reject':
            tutor.verification_status = 'rejected'
            tutor.status = 'inactive'
            message = f'Tutor {tutor.user.full_name} verification has been rejected.'
        else:
            return jsonify({'error': 'Invalid action'}), 400
        
        db.session.commit()
        flash(message, 'success')
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Error verifying tutor'}), 500

# ============ STUDENT MANAGEMENT ROUTES ============

@bp.route('/students')
@login_required
@admin_required
def students():
    """Student management page"""
    page = request.args.get('page', 1, type=int)
    grade_filter = request.args.get('grade', '')
    dept_filter = request.args.get('department', '', type=int)
    search = request.args.get('search', '')
    
    query = Student.query
    
    if grade_filter:
        query = query.filter_by(grade=grade_filter)
    
    if dept_filter:
        query = query.filter_by(department_id=dept_filter)
    
    if search:
        query = query.filter(Student.full_name.contains(search))
    
    students = query.order_by(Student.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    departments = Department.query.filter_by(is_active=True).all()
    
    return render_template('admin/students.html', students=students, departments=departments)

@bp.route('/students/register', methods=['GET', 'POST'])
@login_required
@admin_required
def register_student():
    """Register new student"""
    form = StudentRegistrationForm()
    
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
                    'name': form.father_name.data,
                    'phone': form.father_phone.data,
                    'email': form.father_email.data,
                    'profession': form.father_profession.data,
                    'workplace': form.father_workplace.data
                },
                'mother': {
                    'name': form.mother_name.data,
                    'phone': form.mother_phone.data,
                    'email': form.mother_email.data,
                    'profession': form.mother_profession.data,
                    'workplace': form.mother_workplace.data
                }
            }
            student.set_parent_details(parent_details)
            
            # Academic profile
            academic_profile = {
                'siblings': form.siblings.data,
                'hobbies': [h.strip() for h in (form.hobbies.data or '').split(',') if h.strip()],
                'learning_styles': [l.strip() for l in (form.learning_styles.data or '').split(',') if l.strip()],
                'learning_patterns': [p.strip() for p in (form.learning_patterns.data or '').split(',') if p.strip()],
                'parent_feedback': form.parent_feedback.data
            }
            student.set_academic_profile(academic_profile)
            
            # Subjects
            student.set_subjects_enrolled([s.strip() for s in form.subjects_enrolled.data.split(',')])
            if form.favorite_subjects.data:
                student.set_favorite_subjects([s.strip() for s in form.favorite_subjects.data.split(',')])
            if form.difficult_subjects.data:
                student.set_difficult_subjects([s.strip() for s in form.difficult_subjects.data.split(',')])
            
            # Fee structure
            fee_structure = {
                'total_fee': form.total_fee.data,
                'amount_paid': form.amount_paid.data or 0,
                'balance_amount': form.total_fee.data - (form.amount_paid.data or 0),
                'payment_mode': form.payment_mode.data,
                'payment_schedule': form.payment_schedule.data
            }
            student.set_fee_structure(fee_structure)
            
            # Handle document uploads
            documents = {}
            s3_url = None
            if form.marksheet.data:
                s3_url = upload_file_to_s3(form.marksheet.data, folder=f"{current_app.config['UPLOAD_FOLDER']}/documents")
            if s3_url:
                documents['marksheet'] = s3_url
            s3_url = None    
            if form.student_aadhaar.data:
                s3_url = upload_file_to_s3(form.student_aadhaar.data, folder=f"{current_app.config['UPLOAD_FOLDER']}/documents")
            if s3_url:
                documents['aadhaar'] = s3_url
            s3_url = None
            if form.school_id.data:
                s3_url = upload_file_to_s3(form.school_id.data, folder=f"{current_app.config['UPLOAD_FOLDER']}/documents")
            if s3_url:
                documents['school_id'] = s3_url

            
            student.set_documents(documents)
            
            db.session.add(student)
            db.session.commit()
            
            flash(f'Student {student.full_name} registered successfully!', 'success')
            return redirect(url_for('admin.students'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error registering student: {str(e)}', 'error')
    
    return render_template('admin/register_student.html', form=form)

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

@bp.route('/students/<int:student_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_student(student_id):
    """Edit student information"""
    student = Student.query.get_or_404(student_id)
    
    # Check department access
    if current_user.role == 'coordinator' and current_user.department_id != student.department_id:
        flash('Access denied. You can only edit students from your department.', 'error')
        return redirect(url_for('admin.students'))
    
    form = StudentRegistrationForm(obj=student)
    
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
            
            # Update parent details
            parent_details = {
                'father': {
                    'name': form.father_name.data,
                    'phone': form.father_phone.data,
                    'email': form.father_email.data,
                    'profession': form.father_profession.data,
                    'workplace': form.father_workplace.data
                },
                'mother': {
                    'name': form.mother_name.data,
                    'phone': form.mother_phone.data,
                    'email': form.mother_email.data,
                    'profession': form.mother_profession.data,
                    'workplace': form.mother_workplace.data
                }
            }
            student.set_parent_details(parent_details)
            
            # Update fee structure
            fee_structure = student.get_fee_structure()
            fee_structure.update({
                'total_fee': form.total_fee.data,
                'payment_mode': form.payment_mode.data,
                'payment_schedule': form.payment_schedule.data
            })
            student.set_fee_structure(fee_structure)
            
            db.session.commit()
            flash(f'Student {student.full_name} updated successfully!', 'success')
            return redirect(url_for('admin.students'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating student: {str(e)}', 'error')
    
    return render_template('admin/edit_student.html', form=form, student=student)

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

@bp.route('/classes/bulk-create', methods=['POST'])
@login_required
@admin_required
def bulk_create_classes():
    """Create multiple classes in bulk with availability validation"""
    try:
        from datetime import timedelta
        
        # Get form data
        subject = request.form['subject']
        grade = request.form['grade']
        duration = int(request.form['duration'])
        tutor_id = int(request.form['tutor_id'])
        class_type = request.form['class_type']
        students = [int(s) for s in request.form.getlist('students')]
        
        # Validate tutor
        tutor = Tutor.query.get_or_404(tutor_id)
        availability = tutor.get_availability()
        
        if not availability:
            flash(f'Cannot create classes: {tutor.user.full_name} has not set their availability yet.', 'error')
            return redirect(url_for('admin.classes'))
        
        if tutor.status != 'active':
            flash(f'Cannot create classes: {tutor.user.full_name} is not in active status.', 'error')
            return redirect(url_for('admin.classes'))
        
        start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d').date()
        end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d').date()
        start_time = datetime.strptime(request.form['start_time'], '%H:%M').time()
        
        days_of_week = [int(d) for d in request.form.getlist('days_of_week')]
        
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
                        class_data = {
                            'subject': subject,
                            'class_type': class_type,
                            'scheduled_date': current_date,
                            'scheduled_time': start_time,
                            'duration': duration,
                            'tutor_id': tutor_id,
                            'grade': grade,
                            'status': 'scheduled',
                            'created_by': current_user.id
                        }
                        
                        new_class = Class(**class_data)
                        new_class.set_students(students)
                        
                        db.session.add(new_class)
                        created_count += 1
                    else:
                        skipped_count += 1
                else:
                    skipped_count += 1
            
            current_date += timedelta(days=1)
        
        db.session.commit()
        
        message = f'{created_count} classes created successfully!'
        if skipped_count > 0:
            message += f' {skipped_count} classes were skipped due to availability conflicts or existing bookings.'
        
        flash(message, 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating bulk classes: {str(e)}', 'error')
    
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