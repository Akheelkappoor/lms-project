import os
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from app import db
from app.models.student import Student
from app.models.class_model import Class
from app.models.attendance import Attendance
from app.models.tutor import Tutor
from functools import wraps
from app.models.department import Department
from app.models.user import User
from app.routes.admin import admin_required
from sqlalchemy import or_
from app.utils.advanced_permissions import require_permission
from app.utils.input_sanitizer import InputSanitizer
from app.utils.error_handler import handle_json_errors, ErrorHandler
from sqlalchemy.orm import joinedload
# Import new services
from app.services.database_service import DatabaseService
from app.services.validation_service import ValidationService
from app.services.error_service import handle_errors, error_service

bp = Blueprint('student', __name__)


@bp.route('/students')
@login_required
@require_permission('student_management')
def list_students():
    """List all students (alias for admin.students)"""
    return redirect(url_for('admin.students'))

@bp.route('/students/<int:student_id>')
@login_required
@require_permission('student_management')
@handle_errors
def student_profile(student_id):
    """View student profile with optimized queries"""
    # Use optimized query with eager loading
    student = DatabaseService.get_optimized_query(
        Student,
        includes=['department'],
        filters={'id': student_id, 'is_active': True}
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
        joinedload(Class.tutor).joinedload(Tutor.user)
    ).order_by(Class.scheduled_date.desc()).limit(20).all()
    
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
@require_permission('student_management')
def edit_student(student_id):
    """Edit student information"""
    student = Student.query.get_or_404(student_id)
    
    # Check department access
    if current_user.role == 'coordinator' and current_user.department_id != student.department_id:
        flash('Access denied. You can only edit students from your department.', 'error')
        return redirect(url_for('admin.students'))
    
    if request.method == 'POST':
        try:
            # Update basic information with sanitization
            student.full_name = InputSanitizer.sanitize_name(request.form.get('full_name'))
            student.email = InputSanitizer.sanitize_email(request.form.get('email'))
            student.phone = InputSanitizer.sanitize_phone(request.form.get('phone'))
            student.grade = InputSanitizer.sanitize_grade(request.form.get('grade'))
            student.board = InputSanitizer.sanitize_text(request.form.get('board'), max_length=100)
            student.school_name = InputSanitizer.sanitize_text(request.form.get('school_name'), max_length=200)
            
            # Update parent details with sanitization
            parent_details = {
                'father': {
                    'name': InputSanitizer.sanitize_name(request.form.get('father_name')),
                    'phone': InputSanitizer.sanitize_phone(request.form.get('father_phone')),
                    'email': InputSanitizer.sanitize_email(request.form.get('father_email')),
                    'profession': InputSanitizer.sanitize_text(request.form.get('father_profession'), max_length=100),
                    'workplace': InputSanitizer.sanitize_text(request.form.get('father_workplace'), max_length=200)
                },
                'mother': {
                    'name': InputSanitizer.sanitize_name(request.form.get('mother_name')),
                    'phone': InputSanitizer.sanitize_phone(request.form.get('mother_phone')),
                    'email': InputSanitizer.sanitize_email(request.form.get('mother_email')),
                    'profession': InputSanitizer.sanitize_text(request.form.get('mother_profession'), max_length=100),
                    'workplace': InputSanitizer.sanitize_text(request.form.get('mother_workplace'), max_length=200)
                }
            }
            student.set_parent_details(parent_details)
            
            # Update subjects with sanitization
            subjects_raw = InputSanitizer.sanitize_subject_list(request.form.get('subjects_enrolled', ''))
            subjects = [s.strip() for s in subjects_raw.split(',') if s.strip()]
            student.set_subjects_enrolled(subjects)
            
            # Update fee structure with sanitization
            fee_structure = student.get_fee_structure()
            total_fee = InputSanitizer.sanitize_numeric(request.form.get('total_fee', 0), min_val=0, max_val=1000000)
            amount_paid = InputSanitizer.sanitize_numeric(request.form.get('amount_paid', 0), min_val=0, max_val=1000000)
            fee_structure['total_fee'] = total_fee or 0
            fee_structure['amount_paid'] = amount_paid or 0
            fee_structure['balance_amount'] = fee_structure['total_fee'] - fee_structure['amount_paid']
            fee_structure['payment_mode'] = InputSanitizer.sanitize_text(request.form.get('payment_mode'), max_length=50)
            fee_structure['payment_schedule'] = InputSanitizer.sanitize_text(request.form.get('payment_schedule'), max_length=50)
            student.set_fee_structure(fee_structure)
            
            # Update status with validation
            enrollment_status = InputSanitizer.sanitize_text(request.form.get('enrollment_status'), max_length=50)
            # Validate enrollment status against allowed values
            allowed_statuses = ['active', 'paused', 'completed', 'dropped']
            student.enrollment_status = enrollment_status if enrollment_status in allowed_statuses else 'active'
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
@require_permission('student_management')
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
@require_permission('student_management')
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
@require_permission('student_management')
def student_fees(student_id):
    """View student's fee information"""
    student = Student.query.get_or_404(student_id)
    
    # Check department access
    if current_user.role == 'coordinator' and current_user.department_id != student.department_id:
        flash('Access denied.', 'error')
        return redirect(url_for('admin.students'))
    
    fee_structure = student.get_fee_structure()
    payment_history = student.get_fee_payment_history()
    upcoming_installments = student.get_upcoming_installments(5)  # Get next 5 upcoming payments
    next_payment_info = student.get_next_payment_info()
    
    return render_template('student/fees.html',
                         student=student,
                         fee_structure=fee_structure,
                         payment_history=payment_history,
                         upcoming_installments=upcoming_installments,
                         next_payment_info=next_payment_info)

@bp.route('/students/<int:student_id>/fees/payment', methods=['POST'])
@login_required
@require_permission('student_management')
@handle_json_errors
def record_payment(student_id):
    """Record a fee payment"""
    student = Student.query.get_or_404(student_id)
    
    # Check department access
    if current_user.role == 'coordinator' and current_user.department_id != student.department_id:
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        # Better JSON handling
        if not request.is_json:
            return jsonify({'error': 'Content-Type must be application/json'}), 400
        
        try:
            data = request.get_json(force=False, silent=False, cache=False)
        except Exception as json_err:
            return jsonify({'error': 'Failed to decode JSON object: Invalid JSON format'}), 400
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Sanitize payment input
        amount = InputSanitizer.sanitize_numeric(data.get('amount', 0), min_val=0, max_val=1000000)
        if amount is None or amount <= 0:
            return jsonify({'error': 'Invalid payment amount'}), 400
        
        payment_mode = InputSanitizer.sanitize_text(data.get('payment_mode', 'cash'), max_length=50)
        # Validate payment mode
        allowed_payment_modes = ['cash', 'online', 'bank_transfer', 'cheque', 'upi', 'card']
        if payment_mode not in allowed_payment_modes:
            payment_mode = 'cash'
        
        payment_date_str = InputSanitizer.sanitize_text(data.get('payment_date', datetime.now().date().isoformat()), max_length=20)
        try:
            # Validate date format
            datetime.fromisoformat(payment_date_str)
            payment_date = payment_date_str
        except ValueError:
            payment_date = datetime.now().date().isoformat()
        
        notes = InputSanitizer.sanitize_text(data.get('notes', ''), max_length=500)
        
        # Parse payment date
        payment_date_obj = None
        if payment_date:
            try:
                payment_date_obj = datetime.fromisoformat(payment_date).date()
            except ValueError:
                payment_date_obj = datetime.now().date()
        
        # Record payment using the model method
        payment_record = student.add_fee_payment(
            amount=amount,
            payment_mode=payment_mode,
            payment_date=payment_date_obj,
            notes=notes,
            recorded_by=current_user.full_name if hasattr(current_user, 'full_name') else current_user.email
        )
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Payment of ₹{amount:,.2f} recorded successfully',
            'payment_record': payment_record,
            'new_balance': student.calculate_outstanding_fees()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Error recording payment'}), 500

@bp.route('/students/<int:student_id>/deactivate', methods=['POST'])
@login_required
@require_permission('student_management')
def deactivate_student(student_id):
    """Deactivate a student"""
    student = Student.query.get_or_404(student_id)
    
    # Check department access
    if current_user.role == 'coordinator' and current_user.department_id != student.department_id:
        return jsonify({'error': 'Access denied'}), 403
    
    # Better JSON handling
    if request.is_json:
        try:
            data = request.get_json(force=False, silent=False, cache=False)
            reason = data.get('reason', '') if data else ''
        except Exception:
            reason = ''
    else:
        reason = request.form.get('reason', '')
    
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
@require_permission('student_management')
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
@require_permission('student_management')
def search_students():
    """Search students API endpoint"""
    query = request.args.get('q', '')
    department_id = request.args.get('department_id', type=int)
    grade = request.args.get('grade', '')
    
    # Build search query
    search_query = Student.query.filter_by(is_active=True)
    
    if query:
        search_term = f"%{query}%"
        search_query = search_query.filter(Student.full_name.ilike(search_term))
    
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
    




@bp.route('/api/students/search-enhanced')
@login_required
@require_permission('student_management')
def search_students_enhanced():
    """Enhanced student search with pagination and advanced filters"""
    try:
        # Get parameters
        query = request.args.get('q', '').strip()
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        grade = request.args.get('grade', '').strip()
        board = request.args.get('board', '').strip()
        subject = request.args.get('subject', '').strip()
        department_id = request.args.get('department_id', type=int)
        enrollment_status = request.args.get('enrollment_status', '').strip()
        
        # Build base query
        search_query = Student.query.filter_by(is_active=True)
        
        # Department access check for coordinators
        if current_user.role == 'coordinator':
            search_query = search_query.filter_by(department_id=current_user.department_id)
        
        # Apply filters
        if query:
            search_term = f"%{query}%"
            search_query = search_query.filter(
                db.or_(
                    Student.full_name.ilike(search_term),
                    Student.email.ilike(search_term),
                    Student.phone.ilike(search_term)
                )
            )
        
        if grade:
            search_query = search_query.filter_by(grade=grade)
        
        if board:
            search_query = search_query.filter_by(board=board)
        
        if department_id:
            search_query = search_query.filter_by(department_id=department_id)
        
        if enrollment_status:
            search_query = search_query.filter_by(enrollment_status=enrollment_status)
        
        if subject:
            # Filter by subjects enrolled (assuming you have a method for this)
            subject_students = []
            all_students = search_query.all()
            for student in all_students:
                try:
                    student_subjects = student.get_subjects_enrolled() if hasattr(student, 'get_subjects_enrolled') else []
                    if any(subject.lower() in subj.lower() for subj in student_subjects):
                        subject_students.append(student.id)
                except:
                    pass
            
            if subject_students:
                search_query = search_query.filter(Student.id.in_(subject_students))
            else:
                search_query = search_query.filter(Student.id == -1)  # No results
        
        # Get paginated results
        paginated = search_query.order_by(Student.full_name).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # Format results
        students = []
        for student in paginated.items:
            try:
                # Get subjects enrolled
                subjects_enrolled = []
                if hasattr(student, 'get_subjects_enrolled'):
                    subjects_enrolled = student.get_subjects_enrolled() or []
                
                students.append({
                    'id': student.id,
                    'name': student.full_name,
                    'email': student.email,
                    'phone': student.phone or '',
                    'grade': student.grade,
                    'board': student.board,
                    'department': student.department.name if student.department else '',
                    'enrollment_status': student.enrollment_status,
                    'subjects_enrolled': subjects_enrolled
                })
            except Exception as e:
                # Log error but continue with basic data
                students.append({
                    'id': student.id,
                    'name': student.full_name,
                    'email': student.email,
                    'phone': student.phone or '',
                    'grade': student.grade,
                    'board': student.board,
                    'department': student.department.name if student.department else '',
                    'enrollment_status': student.enrollment_status,
                    'subjects_enrolled': []
                })
        
        return jsonify({
            'success': True,
            'students': students,
            'pagination': {
                'page': paginated.page,
                'pages': paginated.pages,
                'per_page': paginated.per_page,
                'total': paginated.total,
                'has_next': paginated.has_next,
                'has_prev': paginated.has_prev
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/students/filter-options')
@login_required
@require_permission('student_management')
def get_student_filter_options():
    """Get available filter options for students"""
    
    # Base query with department restrictions
    base_query = Student.query.filter_by(is_active=True)
    if current_user.role == 'coordinator':
        base_query = base_query.filter_by(department_id=current_user.department_id)
    
    # Get unique grades
    grades = db.session.query(Student.grade).distinct().filter(
        Student.is_active == True
    )
    if current_user.role == 'coordinator':
        grades = grades.filter(Student.department_id == current_user.department_id)
    grades = [g[0] for g in grades.all() if g[0]]
    grades.sort(key=lambda x: int(x) if x.isdigit() else float('inf'))
    
    # Get unique boards
    boards = db.session.query(Student.board).distinct().filter(
        Student.is_active == True
    )
    if current_user.role == 'coordinator':
        boards = boards.filter(Student.department_id == current_user.department_id)
    boards = [b[0] for b in boards.all() if b[0]]
    boards.sort()
    
    # Get departments (if user has access)
    departments = []
    if current_user.role != 'coordinator':
        from app.models.department import Department
        departments = [{'id': d.id, 'name': d.name} for d in Department.query.filter_by(is_active=True).all()]
    
    # Get common subjects
    all_students = base_query.all()
    all_subjects = set()
    for student in all_students:
        subjects = student.get_subjects_enrolled()
        all_subjects.update(subjects)
    subjects = sorted(list(all_subjects))
    
    # Enrollment statuses
    enrollment_statuses = ['active', 'paused', 'completed', 'dropped']
    
    return jsonify({
        'success': True,
        'options': {
            'grades': grades,
            'boards': boards,
            'departments': departments,
            'subjects': subjects,
            'enrollment_statuses': enrollment_statuses
        }
    })