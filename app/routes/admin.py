from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from datetime import datetime, date, timedelta
import os
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

bp = Blueprint('admin', __name__)

from functools import wraps

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
        # Add timestamp to prevent conflicts
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
        filename = timestamp + filename
        
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], subfolder, filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        file.save(file_path)
        return filename
    return None

# User Management Routes
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
    
    # Apply filters
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
    """Create new user"""
    form = CreateUserForm()
    
    if form.validate_on_submit():
        user = User()
        form.populate_obj(user)
        
        # Set password
        user.set_password(form.password.data)
        
        # Handle profile picture upload
        if form.profile_picture.data:
            filename = save_uploaded_file(form.profile_picture.data, 'profiles')
            user.profile_picture = filename
        
        # Set emergency contact if provided
        emergency_contact = {
            'name': request.form.get('emergency_name', ''),
            'phone': request.form.get('emergency_phone', ''),
            'relation': request.form.get('emergency_relation', '')
        }
        if emergency_contact['name']:
            user.set_emergency_contact(emergency_contact)
        
        user.created_at = datetime.utcnow()
        user.is_verified = True
        
        try:
            db.session.add(user)
            db.session.commit()
            flash(f'User {user.full_name} created successfully!', 'success')
            return redirect(url_for('admin.users'))
        except Exception as e:
            db.session.rollback()
            flash('Error creating user. Please try again.', 'error')
    
    return render_template('admin/create_user.html', form=form)

@bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    """Edit user"""
    user = User.query.get_or_404(user_id)
    form = EditUserForm(user_id=user.id, obj=user)
    
    if form.validate_on_submit():
        form.populate_obj(user)
        
        # Handle profile picture upload
        if form.profile_picture.data:
            filename = save_uploaded_file(form.profile_picture.data, 'profiles')
            user.profile_picture = filename
        
        try:
            db.session.commit()
            flash(f'User {user.full_name} updated successfully!', 'success')
            return redirect(url_for('admin.users'))
        except Exception as e:
            db.session.rollback()
            flash('Error updating user. Please try again.', 'error')
    
    return render_template('admin/edit_user.html', form=form, user=user)

@bp.route('/users/<int:user_id>/toggle-status', methods=['POST'])
@login_required
@admin_required
def toggle_user_status(user_id):
    """Toggle user active status"""
    user = User.query.get_or_404(user_id)
    
    if user.role == 'superadmin' and current_user.role != 'superadmin':
        return jsonify({'error': 'Cannot modify superadmin account'}), 403
    
    user.is_active = not user.is_active
    db.session.commit()
    
    status = 'activated' if user.is_active else 'deactivated'
    flash(f'User {user.full_name} has been {status}.', 'success')
    
    return jsonify({'success': True, 'status': user.is_active})

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
        # Check if user has associated data
        if user.role == 'tutor' and user.tutor_profile:
            # Check if tutor has classes
            if Class.query.filter_by(tutor_id=user.tutor_profile.id).first():
                return jsonify({'error': 'Cannot delete tutor with existing classes'}), 400
        
        db.session.delete(user)
        db.session.commit()
        flash(f'User {user.full_name} deleted successfully.', 'success')
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Error deleting user'}), 500

# Department Management Routes
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
    
    department = Department(
        name=data['name'],
        code=data['code'],
        description=data.get('description', ''),
        created_by=current_user.id
    )
    
    try:
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

# Tutor Management Routes
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
    
    # Apply filters
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
    """Register new tutor"""
    form = TutorRegistrationForm()
    print("Form fields:", [field.name for field in form])
    
    if form.validate_on_submit():
        try:
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
            user.set_password(form.password.data) # Set password
            
            db.session.add(user)
            db.session.flush()  # Get user ID
            
            # Create tutor profile
            tutor = Tutor(
                user_id=user.id,
                qualification=form.qualification.data,
                experience=form.experience.data,
                salary_type=form.salary_type.data,
                monthly_salary=form.monthly_salary.data,
                hourly_rate=form.hourly_rate.data,
                status='pending',
                verification_status='pending'
            )
            
            # Set subjects, grades, and boards
            tutor.set_subjects([s.strip() for s in form.subjects.data.split(',')])
            tutor.set_grades([g.strip() for g in form.grades.data.split(',')])
            tutor.set_boards([b.strip() for b in form.boards.data.split(',')])
            
            # Handle document uploads
            documents = {}
            if form.aadhaar_card.data:
                documents['aadhaar'] = save_uploaded_file(form.aadhaar_card.data, 'documents')
            if form.pan_card.data:
                documents['pan'] = save_uploaded_file(form.pan_card.data, 'documents')
            if form.resume.data:
                documents['resume'] = save_uploaded_file(form.resume.data, 'documents')
            if form.degree_certificate.data:
                documents['degree'] = save_uploaded_file(form.degree_certificate.data, 'documents')
            
            tutor.set_documents(documents)
            
            # Handle video uploads
            if form.demo_video.data:
                tutor.demo_video = save_uploaded_file(form.demo_video.data, 'videos')
            if form.interview_video.data:
                tutor.interview_video = save_uploaded_file(form.interview_video.data, 'videos')
            
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
            
            flash(f'Tutor {user.full_name} registered successfully!', 'success')
            return redirect(url_for('admin.tutors'))
            
        except Exception as e:
            db.session.rollback()
            flash('Error registering tutor. Please try again.', 'error')
    
    return render_template('admin/register_tutor.html', form=form)

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

# Student Management Routes
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
    
    # Apply filters
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
            student = Student()
            
            # Basic information
            student.full_name = form.full_name.data
            student.email = form.email.data
            student.phone = form.phone.data
            student.date_of_birth = form.date_of_birth.data
            student.address = form.address.data
            student.state = form.state.data
            student.pin_code = form.pin_code.data
            
            # Academic information
            student.grade = form.grade.data
            student.board = form.board.data
            student.school_name = form.school_name.data
            student.academic_year = form.academic_year.data
            student.course_start_date = form.course_start_date.data
            student.department_id = form.department_id.data
            student.relationship_manager = form.relationship_manager.data
            
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
            if form.marksheet.data:
                documents['marksheet'] = save_uploaded_file(form.marksheet.data, 'documents')
            if form.student_aadhaar.data:
                documents['aadhaar'] = save_uploaded_file(form.student_aadhaar.data, 'documents')
            if form.school_id.data:
                documents['school_id'] = save_uploaded_file(form.school_id.data, 'documents')
            
            student.set_documents(documents)
            
            db.session.add(student)
            db.session.commit()
            
            flash(f'Student {student.full_name} registered successfully!', 'success')
            return redirect(url_for('admin.students'))
            
        except Exception as e:
            db.session.rollback()
            flash('Error registering student. Please try again.', 'error')
    
    return render_template('admin/register_student.html', form=form)

# Class Management Routes
@bp.route('/classes')
@login_required
@admin_required
def classes():
    """Class management page"""
    page = request.args.get('page', 1, type=int)
    date_filter = request.args.get('date', '')
    tutor_filter = request.args.get('tutor', '', type=int)
    status_filter = request.args.get('status', '')
    
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
    
    classes = query.order_by(Class.scheduled_date.desc(), Class.scheduled_time.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    tutors = Tutor.query.join(User).filter(User.is_active==True).all()
    students = Student.query.filter(Student.is_active==True).all()  # Add this line
    
    # Create students dictionary for quick lookup
    students_dict = {s.id: s for s in students}
    
    return render_template('admin/classes.html', 
                         classes=classes, 
                         tutors=tutors, 
                         students=students,
                         students_dict=students_dict,
                         today=date.today(),
                         csrf_token=generate_csrf)

@bp.route('/classes/create', methods=['POST'])
@login_required
@admin_required
def create_class():
    """Create a new class"""
    try:
        class_data = {
            'subject': request.form['subject'],
            'class_type': request.form['class_type'],
            'scheduled_date': datetime.strptime(request.form['scheduled_date'], '%Y-%m-%d').date(),
            'scheduled_time': datetime.strptime(request.form['scheduled_time'], '%H:%M').time(),
            'duration': int(request.form['duration']),
            'tutor_id': int(request.form['tutor_id']),
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
        flash(f'Class created successfully for {class_data["scheduled_date"]}', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash('Error creating class. Please try again.', 'error')
    
    return redirect(url_for('admin.classes'))

@bp.route('/classes/bulk-create', methods=['POST'])
@login_required
@admin_required
def bulk_create_classes():
    """Create multiple classes in bulk"""
    try:
        from datetime import timedelta
        
        # Get form data
        subject = request.form['subject']
        grade = request.form['grade']
        duration = int(request.form['duration'])
        tutor_id = int(request.form['tutor_id'])
        class_type = request.form['class_type']
        students = [int(s) for s in request.form.getlist('students')]
        
        start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d').date()
        end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d').date()
        start_time = datetime.strptime(request.form['start_time'], '%H:%M').time()
        
        days_of_week = [int(d) for d in request.form.getlist('days_of_week')]
        
        created_count = 0
        current_date = start_date
        
        while current_date <= end_date:
            # Check if current day is in selected days of week
            if current_date.weekday() in days_of_week:
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
            
            current_date += timedelta(days=1)
        
        db.session.commit()
        flash(f'{created_count} classes created successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash('Error creating bulk classes. Please try again.', 'error')
    
    return redirect(url_for('admin.classes'))

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
            # Update student information
            student.full_name = form.full_name.data
            student.email = form.email.data
            student.phone = form.phone.data
            student.date_of_birth = form.date_of_birth.data
            student.address = form.address.data
            student.state = form.state.data
            student.pin_code = form.pin_code.data
            student.grade = form.grade.data
            student.board = form.board.data
            student.subjects = form.subjects.data
            
            # Update parent information
            parent_info = student.get_parent_info()
            parent_info.update({
                'parent_name': form.parent_name.data,
                'parent_phone': form.parent_phone.data,
                'parent_email': form.parent_email.data
            })
            student.set_parent_info(parent_info)
            
            # Update fee structure if changed
            fee_structure = student.get_fee_structure()
            fee_structure.update({
                'total_fee': form.total_fee.data,
                'payment_type': form.payment_type.data
            })
            student.set_fee_structure(fee_structure)
            
            # Update additional info
            additional_info = student.get_additional_info()
            additional_info.update({
                'medical_conditions': form.medical_conditions.data,
                'special_requirements': form.special_requirements.data
            })
            student.set_additional_info(additional_info)
            
            db.session.commit()
            flash(f'Student {student.full_name} updated successfully!', 'success')
            return redirect(url_for('admin.students'))
            
        except Exception as e:
            db.session.rollback()
            flash('Error updating student. Please try again.', 'error')
    
    return render_template('admin/edit_student.html', form=form, student=student)

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
    
# Add this route to your app/routes/admin.py file

@bp.route('/timetable')
@login_required
@admin_required
def timetable():
    """Timetable management page"""
    try:
        # Get all departments for filter
        departments = []
        try:
            departments = Department.query.filter_by(is_active=True).all()
        except Exception as e:
            print(f"Error loading departments: {str(e)}")
            departments = []
        
        # Get tutors - No join needed since Tutor has relationship to User
        tutors = []
        try:
            tutors_query = Tutor.query.filter(Tutor.status == 'approved').all()
            tutors = [t for t in tutors_query if hasattr(t, 'user') and t.user and t.user.is_active]
        except Exception as e:
            print(f"Error loading tutors: {str(e)}")
            tutors = []
        
        # Get students - Direct query since Student has its own fields
        students = []
        try:
            students = Student.query.filter(
                Student.is_active == True,
                Student.enrollment_status == 'active'
            ).limit(100).all()
        except Exception as e:
            print(f"Error loading students: {str(e)}")
            # Fallback - get all students
            try:
                students = Student.query.limit(50).all()
            except:
                students = []
        
        return render_template('admin/timetable.html', 
                             departments=departments,
                             tutors=tutors,
                             students=students)
                             
    except Exception as e:
        print(f"Error loading timetable page: {str(e)}")
        flash('Error loading timetable page', 'error')
        return redirect(url_for('dashboard.index'))

# ALSO ADD THESE HELPER ROUTES FOR BETTER FUNCTIONALITY

@bp.route('/api/v1/tutors/available')
@login_required 
@admin_required
def api_available_tutors():
    """Get available tutors"""
    try:
        available_tutors = []
        
        # Get all approved tutors
        tutors = Tutor.query.filter(Tutor.status == 'approved').all()
        
        for tutor in tutors:
            if hasattr(tutor, 'user') and tutor.user and tutor.user.is_active:
                available_tutors.append({
                    'id': tutor.id,
                    'name': tutor.user.full_name,
                    'subjects': getattr(tutor, 'subjects', 'Not specified'),
                    'avatar': getattr(tutor.user, 'profile_picture', None)
                })
        
        return jsonify({
            'success': True,
            'tutors': available_tutors
        })
        
    except Exception as e:
        print(f"Error getting available tutors: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/api/v1/students/search')
@login_required
@admin_required  
def api_search_students():
    """Search students"""
    try:
        query = request.args.get('q', '')
        grade = request.args.get('grade', '')
        
        # Build student query - no User join needed
        student_query = Student.query.filter(Student.is_active == True)
        
        if query:
            student_query = student_query.filter(
                Student.full_name.contains(query)
            )
        
        if grade:
            student_query = student_query.filter(
                Student.grade == grade
            )
        
        students = student_query.limit(20).all()
        
        student_list = []
        for student in students:
            student_list.append({
                'id': student.id,
                'name': student.full_name,
                'grade': getattr(student, 'grade', 'Not specified'),
                'subjects': 'Not specified'  # Since students don't have direct subjects
            })
        
        return jsonify({
            'success': True,
            'students': student_list
        })
        
    except Exception as e:
        print(f"Error searching students: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/api/v1/classes/<int:class_id>/reschedule', methods=['POST'])
@login_required
@admin_required
def api_reschedule_class(class_id):
    """Reschedule a class"""
    try:
        data = request.get_json()
        cls = Class.query.get_or_404(class_id)
        
        if cls.status == 'completed':
            return jsonify({'error': "Cannot reschedule a completed class"}), 400
        
        # Parse new date and time
        new_date = datetime.strptime(data['scheduled_date'], '%Y-%m-%d').date()
        new_time = datetime.strptime(data['scheduled_time'], '%H:%M').time()
        
        # Check for conflicts
        conflict = Class.query.filter(
            Class.tutor_id == cls.tutor_id,
            Class.scheduled_date == new_date,
            Class.scheduled_time == new_time,
            Class.status.in_(['scheduled', 'ongoing']),
            Class.id != class_id
        ).first()
        
        if conflict:
            return jsonify({'error': "Tutor has another class at this time"}), 400
        
        # Update the class
        cls.scheduled_date = new_date
        cls.scheduled_time = new_time
        cls.class_notes = data.get('notes', cls.class_notes)
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': "Class rescheduled successfully"})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f"Error rescheduling class: {str(e)}"}), 500

@bp.route('/api/v1/dashboard/stats')
@login_required
@admin_required
def api_dashboard_stats():
    """Get dashboard statistics"""
    try:
        today = date.today()
        
        # Today's stats
        today_classes = Class.query.filter(Class.scheduled_date == today).all()
        
        # This week's stats
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        
        week_classes = Class.query.filter(
            Class.scheduled_date >= start_of_week,
            Class.scheduled_date <= end_of_week
        ).all()
        
        # Active counts
        active_tutors = Tutor.query.join(User).filter(
            User.is_active == True,
            Tutor.status == 'approved'
        ).count()
        
        active_students = Student.query.join(User).filter(
            User.is_active == True,
            Student.enrollment_status == 'enrolled'
        ).count()
        
        stats = {
            'today': {
                'total': len(today_classes),
                'scheduled': len([c for c in today_classes if c.status == 'scheduled']),
                'ongoing': len([c for c in today_classes if c.status == 'ongoing']),
                'completed': len([c for c in today_classes if c.status == 'completed']),
                'cancelled': len([c for c in today_classes if c.status == 'cancelled'])
            },
            'week': {
                'total': len(week_classes),
                'scheduled': len([c for c in week_classes if c.status == 'scheduled']),
                'ongoing': len([c for c in week_classes if c.status == 'ongoing']),
                'completed': len([c for c in week_classes if c.status == 'completed']),
                'cancelled': len([c for c in week_classes if c.status == 'cancelled'])
            },
            'active_tutors': active_tutors,
            'active_students': active_students
        }
        
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f"Error getting dashboard stats: {str(e)}"
        }), 500
    

@bp.route('/dashboard') 
@login_required
@admin_required
def admin_dashboard():
    """Admin dashboard - redirect to main dashboard"""
    return redirect(url_for('dashboard.index'))

@bp.route('/debug-timetable')
@login_required
@admin_required
def debug_timetable():
    """Debug timetable functionality"""
    try:
        # Get sample data for debugging
        total_classes = Class.query.count()
        total_tutors = Tutor.query.count()
        total_students = Student.query.count()
        
        # Get recent classes
        recent_classes = Class.query.order_by(Class.created_at.desc()).limit(10).all()
        
        debug_info = {
            'total_classes': total_classes,
            'total_tutors': total_tutors,
            'total_students': total_students,
            'recent_classes': [
                {
                    'id': c.id,
                    'subject': c.subject,
                    'date': c.scheduled_date.strftime('%Y-%m-%d'),
                    'time': c.scheduled_time.strftime('%H:%M'),
                    'tutor': c.tutor.full_name if c.tutor else 'No Tutor',
                    'status': c.status
                } for c in recent_classes
            ]
        }
        
        return jsonify(debug_info)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    

# REPLACE THE EXISTING /api/v1/timetable/week route with this SIMPLE VERSION

@bp.route('/api/v1/timetable/week')
@login_required
@admin_required
def api_timetable_week():
    """Get weekly timetable data - SIMPLE VERSION"""
    try:
        # Get basic parameters
        date_param = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
        target_date = datetime.strptime(date_param, '%Y-%m-%d').date()
        
        # Get start of week (Monday)
        start_of_week = target_date - timedelta(days=target_date.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        
        # Get classes for the week
        try:
            classes = Class.query.filter(
                Class.scheduled_date >= start_of_week,
                Class.scheduled_date <= end_of_week
            ).order_by(Class.scheduled_date, Class.scheduled_time).all()
        except Exception as e:
            # If there's an error, return empty data
            classes = []
        
        # Format classes data safely
        classes_data = []
        for cls in classes:
            try:
                # Get basic class info safely
                class_item = {
                    'id': cls.id,
                    'subject': getattr(cls, 'subject', 'Unknown Subject'),
                    'class_type': getattr(cls, 'class_type', 'regular'),
                    'scheduled_date': cls.scheduled_date.strftime('%Y-%m-%d'),
                    'scheduled_time': cls.scheduled_time.strftime('%H:%M'),
                    'duration': getattr(cls, 'duration', 60),
                    'status': getattr(cls, 'status', 'scheduled'),
                    'tutor_name': 'No Tutor Assigned',
                    'tutor_id': getattr(cls, 'tutor_id', None),
                    'grade': getattr(cls, 'grade', ''),
                    'students': [],
                    'student_count': 0,
                    'class_notes': getattr(cls, 'class_notes', '')
                }
                
                # Try to get tutor name safely
                try:
                    if cls.tutor:
                        if hasattr(cls.tutor, 'full_name'):
                            class_item['tutor_name'] = cls.tutor.full_name
                        elif hasattr(cls.tutor, 'user') and cls.tutor.user:
                            class_item['tutor_name'] = cls.tutor.user.full_name
                except:
                    pass  # Keep default "No Tutor Assigned"
                
                # Try to get students safely
                try:
                    if hasattr(cls, 'get_students'):
                        student_ids = cls.get_students()
                        if student_ids:
                            students = Student.query.filter(Student.id.in_(student_ids)).all()
                            class_item['students'] = [{'id': s.id, 'name': s.full_name} for s in students]
                            class_item['student_count'] = len(students)
                except:
                    pass  # Keep empty students list
                
                classes_data.append(class_item)
                
            except Exception as e:
                # Skip problematic classes but continue
                continue
        
        # Calculate simple stats
        total_classes = len(classes_data)
        scheduled_classes = len([c for c in classes_data if c['status'] == 'scheduled'])
        completed_classes = len([c for c in classes_data if c['status'] == 'completed'])
        cancelled_classes = len([c for c in classes_data if c['status'] == 'cancelled'])
        
        stats = {
            'total_classes': total_classes,
            'scheduled_classes': scheduled_classes,
            'completed_classes': completed_classes,
            'cancelled_classes': cancelled_classes,
            'completion_rate': round((completed_classes / total_classes * 100) if total_classes > 0 else 0, 1)
        }
        
        return jsonify({
            'success': True,
            'classes': classes_data,
            'stats': stats,
            'week_start': start_of_week.strftime('%Y-%m-%d'),
            'week_end': end_of_week.strftime('%Y-%m-%d'),
            'debug_info': {
                'date_param': date_param,
                'classes_found': len(classes),
                'classes_processed': len(classes_data)
            }
        })
        
    except Exception as e:
        # Return error details for debugging
        return jsonify({
            'success': False,
            'error': str(e),
            'error_type': type(e).__name__,
            'debug_info': {
                'date_param': request.args.get('date', 'not provided'),
                'filter_type': request.args.get('filter_type', 'not provided')
            }
        }), 500

# ALSO ADD/REPLACE THE TODAY API ROUTE

@bp.route('/api/v1/timetable/today')
@login_required
@admin_required
def api_timetable_today():
    """Get today's timetable data - SIMPLE VERSION"""
    try:
        today = date.today()
        
        # Get today's classes safely
        try:
            classes = Class.query.filter(Class.scheduled_date == today)\
                               .order_by(Class.scheduled_time).all()
        except Exception as e:
            classes = []
        
        classes_data = []
        for cls in classes:
            try:
                class_item = {
                    'id': cls.id,
                    'subject': getattr(cls, 'subject', 'Unknown Subject'),
                    'class_type': getattr(cls, 'class_type', 'regular'),
                    'scheduled_time': cls.scheduled_time.strftime('%H:%M'),
                    'duration': getattr(cls, 'duration', 60),
                    'status': getattr(cls, 'status', 'scheduled'),
                    'tutor_name': 'No Tutor Assigned',
                    'student_name': 'No Students',
                    'students': []
                }
                
                # Get tutor name safely
                try:
                    if cls.tutor:
                        if hasattr(cls.tutor, 'full_name'):
                            class_item['tutor_name'] = cls.tutor.full_name
                        elif hasattr(cls.tutor, 'user') and cls.tutor.user:
                            class_item['tutor_name'] = cls.tutor.user.full_name
                except:
                    pass
                
                # Get first student name for display
                try:
                    if hasattr(cls, 'get_students'):
                        student_ids = cls.get_students()
                        if student_ids:
                            students = Student.query.filter(Student.id.in_(student_ids)).all()
                            class_item['students'] = [{'id': s.id, 'name': s.full_name} for s in students]
                            if students:
                                class_item['student_name'] = students[0].full_name
                                if len(students) > 1:
                                    class_item['student_name'] += f' +{len(students)-1} more'
                except:
                    pass
                
                classes_data.append(class_item)
                
            except Exception as e:
                continue
        
        return jsonify({
            'success': True,
            'classes': classes_data,
            'date': today.strftime('%Y-%m-%d'),
            'debug_info': {
                'classes_found': len(classes),
                'classes_processed': len(classes_data)
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'error_type': type(e).__name__
        }), 500
    
@bp.route('/api/v1/timetable/month')
@login_required
@admin_required
def api_timetable_month():
    """Get monthly timetable data"""
    try:
        date_param = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
        target_date = datetime.strptime(date_param, '%Y-%m-%d').date()
        
        # Get start and end of month
        start_of_month = target_date.replace(day=1)
        if target_date.month == 12:
            end_of_month = target_date.replace(year=target_date.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_of_month = target_date.replace(month=target_date.month + 1, day=1) - timedelta(days=1)
        
        classes = Class.query.filter(
            Class.scheduled_date >= start_of_month,
            Class.scheduled_date <= end_of_month
        ).order_by(Class.scheduled_date, Class.scheduled_time).all()
        
        classes_data = []
        for cls in classes:
            try:
                class_item = {
                    'id': cls.id,
                    'subject': getattr(cls, 'subject', 'Unknown Subject'),
                    'scheduled_date': cls.scheduled_date.strftime('%Y-%m-%d'),
                    'scheduled_time': cls.scheduled_time.strftime('%H:%M'),
                    'status': getattr(cls, 'status', 'scheduled'),
                    'tutor_name': 'No Tutor Assigned',
                    'student_count': 0
                }
                
                # Get tutor name safely
                try:
                    if cls.tutor:
                        if hasattr(cls.tutor, 'full_name'):
                            class_item['tutor_name'] = cls.tutor.full_name
                        elif hasattr(cls.tutor, 'user') and cls.tutor.user:
                            class_item['tutor_name'] = cls.tutor.user.full_name
                except:
                    pass
                
                classes_data.append(class_item)
            except:
                continue
        
        return jsonify({
            'success': True,
            'classes': classes_data,
            'month_start': start_of_month.strftime('%Y-%m-%d'),
            'month_end': end_of_month.strftime('%Y-%m-%d')
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    
# ADD THIS SIMPLE TEST ROUTE TO app/routes/admin.py

@bp.route('/test-timetable-api')
@login_required
@admin_required
def test_timetable_api():
    """Test what data we have for timetable"""
    try:
        # Get simple counts first
        total_classes = Class.query.count()
        total_tutors = Tutor.query.count() 
        total_students = Student.query.count()
        
        # Get a few recent classes to see structure
        recent_classes = Class.query.limit(5).all()
        
        test_data = {
            'database_counts': {
                'classes': total_classes,
                'tutors': total_tutors,
                'students': total_students
            },
            'sample_classes': []
        }
        
        # Add sample class data
        for cls in recent_classes:
            class_info = {
                'id': cls.id,
                'subject': cls.subject if hasattr(cls, 'subject') else 'No Subject',
                'scheduled_date': str(cls.scheduled_date) if hasattr(cls, 'scheduled_date') else 'No Date',
                'scheduled_time': str(cls.scheduled_time) if hasattr(cls, 'scheduled_time') else 'No Time',
                'status': cls.status if hasattr(cls, 'status') else 'No Status',
                'tutor_id': cls.tutor_id if hasattr(cls, 'tutor_id') else None,
                'tutor_name': 'No Tutor',
                'has_tutor_relation': False,
                'class_type': cls.class_type if hasattr(cls, 'class_type') else 'No Type',
                'duration': cls.duration if hasattr(cls, 'duration') else 0
            }
            
            # Try to get tutor info safely
            try:
                if cls.tutor and hasattr(cls.tutor, 'full_name'):
                    class_info['tutor_name'] = cls.tutor.full_name
                    class_info['has_tutor_relation'] = True
                elif cls.tutor and hasattr(cls.tutor, 'user') and cls.tutor.user:
                    class_info['tutor_name'] = cls.tutor.user.full_name
                    class_info['has_tutor_relation'] = True
            except Exception as e:
                class_info['tutor_error'] = str(e)
            
            # Try to get student info safely
            try:
                if hasattr(cls, 'get_students'):
                    student_ids = cls.get_students()
                    class_info['student_ids'] = student_ids
                    class_info['student_count'] = len(student_ids) if student_ids else 0
                else:
                    class_info['has_get_students_method'] = False
            except Exception as e:
                class_info['student_error'] = str(e)
            
            test_data['sample_classes'].append(class_info)
        
        return jsonify(test_data)
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'error_type': type(e).__name__
        }), 500
    
# ADD THIS ROUTE TO CREATE SAMPLE DATA FOR TESTING

@bp.route('/add-sample-timetable-data')
@login_required
@admin_required
def add_sample_timetable_data():
    """Add sample timetable data for testing"""
    try:
        # Check if we already have classes
        existing_classes = Class.query.count()
        
        if existing_classes > 0:
            return jsonify({
                'message': f'Already have {existing_classes} classes in database',
                'action': 'No sample data added'
            })
        
        # Get first available tutor
        tutor = Tutor.query.first()
        if not tutor:
            return jsonify({
                'error': 'No tutors found. Please create a tutor first.',
                'suggestion': 'Go to Admin > Tutors > Register Tutor'
            })
        
        # Create sample classes for this week
        today = date.today()
        sample_classes = []
        
        for i in range(5):  # Create 5 sample classes
            class_date = today + timedelta(days=i)
            class_time = datetime.strptime('10:00', '%H:%M').time()
            
            sample_class = Class(
                subject=f'Sample Subject {i+1}',
                class_type='regular',
                scheduled_date=class_date,
                scheduled_time=class_time,
                duration=60,
                status='scheduled',
                tutor_id=tutor.id,
                grade='10',
                class_notes=f'Sample class {i+1} for testing',
                created_at=datetime.utcnow()
            )
            
            db.session.add(sample_class)
            sample_classes.append(sample_class)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Created {len(sample_classes)} sample classes',
            'classes': [
                {
                    'id': cls.id,
                    'subject': cls.subject,
                    'date': cls.scheduled_date.strftime('%Y-%m-%d'),
                    'time': cls.scheduled_time.strftime('%H:%M')
                } for cls in sample_classes
            ]
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'error': str(e),
            'error_type': type(e).__name__
        }), 500
    
@bp.route('/api/v1/classes/<int:class_id>')
@login_required
@admin_required
def api_get_class(class_id):
    """Get single class details"""
    try:
        cls = Class.query.get_or_404(class_id)
        
        class_data = {
            'id': cls.id,
            'subject': getattr(cls, 'subject', 'Unknown Subject'),
            'class_type': getattr(cls, 'class_type', 'regular'),
            'scheduled_date': cls.scheduled_date.strftime('%Y-%m-%d'),
            'scheduled_time': cls.scheduled_time.strftime('%H:%M'),
            'duration': getattr(cls, 'duration', 60),
            'status': getattr(cls, 'status', 'scheduled'),
            'tutor_name': 'No Tutor Assigned',
            'tutor_id': getattr(cls, 'tutor_id', None),
            'class_notes': getattr(cls, 'class_notes', '')
        }
        
        # Get tutor name safely
        try:
            if cls.tutor:
                if hasattr(cls.tutor, 'full_name'):
                    class_data['tutor_name'] = cls.tutor.full_name
                elif hasattr(cls.tutor, 'user') and cls.tutor.user:
                    class_data['tutor_name'] = cls.tutor.user.full_name
        except:
            pass
        
        return jsonify({
            'success': True,
            'data': class_data
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    
@bp.route('/api/v1/classes/create', methods=['POST'])
@login_required
@admin_required
def api_create_class():
    """Create a new class via API"""
    try:
        data = request.get_json()
        
        # Parse date and time
        scheduled_date = datetime.strptime(data['scheduled_date'], '%Y-%m-%d').date()
        scheduled_time = datetime.strptime(data['scheduled_time'], '%H:%M').time()
        
        # Create new class
        new_class = Class(
            subject=data.get('subject', 'New Class'),
            class_type=data.get('class_type', 'regular'),
            scheduled_date=scheduled_date,
            scheduled_time=scheduled_time,
            duration=int(data.get('duration', 60)),
            tutor_id=int(data['tutor_id']) if data.get('tutor_id') else None,
            grade=data.get('grade', ''),
            class_notes=data.get('notes', ''),
            status='scheduled',
            created_at=datetime.utcnow()
        )
        
        db.session.add(new_class)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Class created successfully',
            'class_id': new_class.id
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    
@bp.route('/api/v1/classes/<int:class_id>/cancel', methods=['POST'])
@login_required
@admin_required
def api_cancel_class(class_id):
    """Cancel a class"""
    try:
        cls = Class.query.get_or_404(class_id)
        
        if cls.status == 'completed':
            return jsonify({'success': False, 'error': 'Cannot cancel a completed class'}), 400
        
        cls.status = 'cancelled'
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Class cancelled successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    

@bp.route('/api/v1/classes/<int:class_id>/start', methods=['POST'])
@login_required
@admin_required
def api_start_class(class_id):
    """Start a class"""
    try:
        cls = Class.query.get_or_404(class_id)
        
        if cls.status != 'scheduled':
            return jsonify({'success': False, 'error': 'Class is not in scheduled status'}), 400
        
        cls.status = 'ongoing'
        cls.actual_start_time = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Class started successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    
@bp.route('/api/v1/classes/<int:class_id>/complete', methods=['POST'])
@login_required
@admin_required
def api_complete_class(class_id):
    """Mark a class as completed"""
    try:
        cls = Class.query.get_or_404(class_id)
        
        if cls.status not in ['scheduled', 'ongoing']:
            return jsonify({'success': False, 'error': 'Class cannot be completed'}), 400
        
        cls.status = 'completed'
        cls.actual_end_time = datetime.utcnow()
        
        # If it was never started, set start time too
        if not cls.actual_start_time:
            cls.actual_start_time = datetime.utcnow() - timedelta(minutes=cls.duration)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Class marked as completed'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500   
    
@bp.route('/api/v1/classes/<int:class_id>', methods=['DELETE'])
@login_required
@admin_required
def api_delete_class(class_id):
    """Delete a class"""
    try:
        cls = Class.query.get_or_404(class_id)
        
        # Check if class can be deleted
        if cls.status == 'ongoing':
            return jsonify({'success': False, 'error': 'Cannot delete an ongoing class'}), 400
        
        # If class is completed, check if user has permission
        if cls.status == 'completed' and current_user.role not in ['superadmin', 'admin']:
            return jsonify({'success': False, 'error': 'Cannot delete completed classes'}), 403
        
        # Check for associated attendance records
        attendance_count = Attendance.query.filter_by(class_id=class_id).count()
        if attendance_count > 0 and current_user.role not in ['superadmin', 'admin']:
            return jsonify({'success': False, 'error': 'Cannot delete class with attendance records'}), 403
        
        # Delete associated attendance records first
        Attendance.query.filter_by(class_id=class_id).delete()
        
        # Delete the class
        db.session.delete(cls)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Class deleted successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500