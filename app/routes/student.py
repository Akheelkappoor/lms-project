from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from app import db
from app.models.student import Student
from app.models.class_model import Class
from app.models.attendance import Attendance
from app.models.tutor import Tutor

bp = Blueprint('student', __name__)

def admin_required(f):
    """Decorator to require admin access"""
    def decorated_function(*args, **kwargs):
        if current_user.role not in ['superadmin', 'admin', 'coordinator']:
            flash('Access denied. Insufficient permissions.', 'error')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated_function

@bp.route('/students')
@login_required
@admin_required
def list_students():
    """List all students (alias for admin.students)"""
    return redirect(url_for('admin.students'))

@bp.route('/students/<int:student_id>')
@login_required
@admin_required
def student_profile(student_id):
    """View student profile"""
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
    
    return render_template('student/profile.html',
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
    
    if request.method == 'POST':
        try:
            # Update basic information
            student.full_name = request.form.get('full_name')
            student.email = request.form.get('email')
            student.phone = request.form.get('phone')
            student.grade = request.form.get('grade')
            student.board = request.form.get('board')
            student.school_name = request.form.get('school_name')
            
            # Update parent details
            parent_details = {
                'father': {
                    'name': request.form.get('father_name'),
                    'phone': request.form.get('father_phone'),
                    'email': request.form.get('father_email'),
                    'profession': request.form.get('father_profession'),
                    'workplace': request.form.get('father_workplace')
                },
                'mother': {
                    'name': request.form.get('mother_name'),
                    'phone': request.form.get('mother_phone'),
                    'email': request.form.get('mother_email'),
                    'profession': request.form.get('mother_profession'),
                    'workplace': request.form.get('mother_workplace')
                }
            }
            student.set_parent_details(parent_details)
            
            # Update subjects
            subjects = request.form.get('subjects_enrolled', '').split(',')
            student.set_subjects_enrolled([s.strip() for s in subjects if s.strip()])
            
            # Update fee structure
            fee_structure = student.get_fee_structure()
            fee_structure['total_fee'] = float(request.form.get('total_fee', 0))
            fee_structure['amount_paid'] = float(request.form.get('amount_paid', 0))
            fee_structure['balance_amount'] = fee_structure['total_fee'] - fee_structure['amount_paid']
            fee_structure['payment_mode'] = request.form.get('payment_mode')
            fee_structure['payment_schedule'] = request.form.get('payment_schedule')
            student.set_fee_structure(fee_structure)
            
            # Update status
            student.enrollment_status = request.form.get('enrollment_status')
            student.is_active = request.form.get('is_active') == 'on'
            
            db.session.commit()
            flash(f'Student {student.full_name} updated successfully!', 'success')
            return redirect(url_for('student.student_profile', student_id=student.id))
            
        except Exception as e:
            db.session.rollback()
            flash('Error updating student. Please try again.', 'error')
    
    return render_template('student/edit.html', student=student)

@bp.route('/students/<int:student_id>/classes')
@login_required
@admin_required
def student_classes(student_id):
    """View student's classes"""
    student = Student.query.get_or_404(student_id)
    
    # Check department access
    if current_user.role == 'coordinator' and current_user.department_id != student.department_id:
        flash('Access denied.', 'error')
        return redirect(url_for('admin.students'))
    
    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    
    # Get all classes for this student
    student_classes = []
    query = Class.query.order_by(Class.scheduled_date.desc(), Class.scheduled_time.desc())
    
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    all_classes = query.all()
    
    for cls in all_classes:
        if student.id in cls.get_students():
            student_classes.append(cls)
    
    # Manual pagination
    per_page = 20
    total = len(student_classes)
    start = (page - 1) * per_page
    end = start + per_page
    paginated_classes = student_classes[start:end]
    
    # Create pagination object
    class Pagination:
        def __init__(self, page, per_page, total, items):
            self.page = page
            self.per_page = per_page
            self.total = total
            self.items = items
            self.pages = (total + per_page - 1) // per_page
            self.has_prev = page > 1
            self.has_next = page < self.pages
            self.prev_num = page - 1 if self.has_prev else None
            self.next_num = page + 1 if self.has_next else None
    
    pagination = Pagination(page, per_page, total, paginated_classes)
    
    return render_template('student/classes.html', 
                         student=student, 
                         classes=pagination)

@bp.route('/students/<int:student_id>/attendance')
@login_required
@admin_required
def student_attendance(student_id):
    """View student's attendance"""
    student = Student.query.get_or_404(student_id)
    
    # Check department access
    if current_user.role == 'coordinator' and current_user.department_id != student.department_id:
        flash('Access denied.', 'error')
        return redirect(url_for('admin.students'))
    
    # Get date range filters
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    page = request.args.get('page', 1, type=int)
    
    # Build query
    query = Attendance.query.filter_by(student_id=student.id)
    
    if start_date:
        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            query = query.filter(Attendance.class_date >= start_date_obj)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            query = query.filter(Attendance.class_date <= end_date_obj)
        except ValueError:
            pass
    
    # Get paginated results
    attendance_records = query.order_by(Attendance.class_date.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    # Get summary statistics
    summary = Attendance.get_attendance_summary(student_id=student.id)
    
    return render_template('student/attendance.html',
                         student=student,
                         attendance_records=attendance_records,
                         summary=summary)

@bp.route('/students/<int:student_id>/fees')
@login_required
@admin_required
def student_fees(student_id):
    """View student's fee information"""
    student = Student.query.get_or_404(student_id)
    
    # Check department access
    if current_user.role == 'coordinator' and current_user.department_id != student.department_id:
        flash('Access denied.', 'error')
        return redirect(url_for('admin.students'))
    
    fee_structure = student.get_fee_structure()
    
    return render_template('student/fees.html',
                         student=student,
                         fee_structure=fee_structure)

@bp.route('/students/<int:student_id>/fees/payment', methods=['POST'])
@login_required
@admin_required
def record_payment(student_id):
    """Record a fee payment"""
    student = Student.query.get_or_404(student_id)
    
    # Check department access
    if current_user.role == 'coordinator' and current_user.department_id != student.department_id:
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        amount = float(request.json.get('amount', 0))
        payment_mode = request.json.get('payment_mode', 'cash')
        payment_date = request.json.get('payment_date', datetime.now().date().isoformat())
        notes = request.json.get('notes', '')
        
        # Update fee structure
        fee_structure = student.get_fee_structure()
        current_paid = fee_structure.get('amount_paid', 0)
        fee_structure['amount_paid'] = current_paid + amount
        fee_structure['balance_amount'] = fee_structure.get('total_fee', 0) - fee_structure['amount_paid']
        
        # Add payment record to history
        if 'payment_history' not in fee_structure:
            fee_structure['payment_history'] = []
        
        fee_structure['payment_history'].append({
            'amount': amount,
            'payment_mode': payment_mode,
            'payment_date': payment_date,
            'notes': notes,
            'recorded_by': current_user.full_name,
            'recorded_at': datetime.now().isoformat()
        })
        
        student.set_fee_structure(fee_structure)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Payment of ₹{amount:,.2f} recorded successfully',
            'new_balance': fee_structure['balance_amount']
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Error recording payment'}), 500

@bp.route('/students/<int:student_id>/deactivate', methods=['POST'])
@login_required
@admin_required
def deactivate_student(student_id):
    """Deactivate a student"""
    student = Student.query.get_or_404(student_id)
    
    # Check department access
    if current_user.role == 'coordinator' and current_user.department_id != student.department_id:
        return jsonify({'error': 'Access denied'}), 403
    
    reason = request.json.get('reason', '')
    
    student.is_active = False
    student.enrollment_status = 'dropped'
    
    # Add note to academic profile
    academic_profile = student.get_academic_profile()
    if 'admin_notes' not in academic_profile:
        academic_profile['admin_notes'] = []
    
    academic_profile['admin_notes'].append({
        'type': 'deactivation',
        'reason': reason,
        'date': datetime.now().isoformat(),
        'admin': current_user.full_name
    })
    
    student.set_academic_profile(academic_profile)
    db.session.commit()
    
    flash(f'Student {student.full_name} has been deactivated.', 'success')
    return jsonify({'success': True})

@bp.route('/students/<int:student_id>/reactivate', methods=['POST'])
@login_required
@admin_required
def reactivate_student(student_id):
    """Reactivate a student"""
    student = Student.query.get_or_404(student_id)
    
    # Check department access
    if current_user.role == 'coordinator' and current_user.department_id != student.department_id:
        return jsonify({'error': 'Access denied'}), 403
    
    student.is_active = True
    student.enrollment_status = 'active'
    
    # Add note to academic profile
    academic_profile = student.get_academic_profile()
    if 'admin_notes' not in academic_profile:
        academic_profile['admin_notes'] = []
    
    academic_profile['admin_notes'].append({
        'type': 'reactivation',
        'date': datetime.now().isoformat(),
        'admin': current_user.full_name
    })
    
    student.set_academic_profile(academic_profile)
    db.session.commit()
    
    flash(f'Student {student.full_name} has been reactivated.', 'success')
    return jsonify({'success': True})

@bp.route('/api/students/search')
@login_required
@admin_required
def search_students():
    """Search students API endpoint"""
    query = request.args.get('q', '')
    department_id = request.args.get('department_id', type=int)
    grade = request.args.get('grade', '')
    
    # Build search query
    search_query = Student.query.filter_by(is_active=True)
    
    if query:
        search_query = search_query.filter(Student.full_name.contains(query))
    
    if department_id:
        search_query = search_query.filter_by(department_id=department_id)
    
    if grade:
        search_query = search_query.filter_by(grade=grade)
    
    # Department access check
    if current_user.role == 'coordinator':
        search_query = search_query.filter_by(department_id=current_user.department_id)
    
    students = search_query.limit(20).all()
    
    results = []
    for student in students:
        results.append({
            'id': student.id,
            'name': student.full_name,
            'email': student.email,
            'grade': student.grade,
            'board': student.board,
            'department': student.department.name if student.department else '',
            'enrollment_status': student.enrollment_status
        })
    
    return jsonify(results)