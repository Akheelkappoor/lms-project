from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from datetime import datetime, date
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
    student_ids = class_obj.get_students()
    students = Student.query.filter(Student.id.in_(student_ids)).all() if student_ids else []
    
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