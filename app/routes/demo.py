# app/routes/demo.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from app import db
from app.models.demo_student import DemoStudent
from app.models.class_model import Class
from app.models.tutor import Tutor
from app.models.student import Student
from app.forms.demo_forms import DemoStudentForm, DemoClassForm, DemoFeedbackForm, ConvertDemoForm
from app.routes.admin import admin_required
from app.utils.meeting_utils import generate_meeting_link, create_zoom_meeting
from app.utils.email_utils import send_demo_confirmation_email

bp = Blueprint('demo', __name__)

# ============ DEMO STUDENT ROUTES ============

@bp.route('/demo/students')
@login_required
@admin_required
def demo_students():
    """List all demo students"""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    search = request.args.get('search', '')
    
    query = DemoStudent.query
    
    if status_filter:
        query = query.filter_by(demo_status=status_filter)
    
    if search:
        query = query.filter(DemoStudent.full_name.contains(search))
    
    demo_students = query.order_by(DemoStudent.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('demo/demo_students.html', demo_students=demo_students)

@bp.route('/demo/students/register', methods=['GET', 'POST'])
@login_required 
@admin_required
def register_demo_student():
    """Register new demo student with basic details"""
    form = DemoStudentForm()
    
    if form.validate_on_submit():
        try:
            # Create demo student record
            demo_student = DemoStudent(
                full_name=form.full_name.data,
                grade=form.grade.data,
                board=form.board.data,
                subject=form.subject.data,
                parent_name=form.parent_name.data,
                phone=form.phone.data,
                email=form.email.data,
                preferred_time=form.preferred_time.data,
                demo_status='registered'
            )
            
            db.session.add(demo_student)
            db.session.commit()
            
            flash(f'Demo student {demo_student.full_name} registered successfully!', 'success')
            return redirect(url_for('demo.schedule_demo_class', demo_student_id=demo_student.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error registering demo student: {str(e)}', 'error')
    
    return render_template('demo/register_demo_student.html', form=form)

@bp.route('/demo/students/<int:demo_student_id>')
@login_required
@admin_required
def demo_student_details(demo_student_id):
    """View demo student details"""
    demo_student = DemoStudent.query.get_or_404(demo_student_id)
    demo_classes = demo_student.get_demo_classes()
    
    return render_template('demo/demo_student_details.html', 
                         demo_student=demo_student, demo_classes=demo_classes)

# ============ DEMO CLASS ROUTES ============

@bp.route('/demo/classes')
@login_required
@admin_required
def demo_classes():
    """List all demo classes"""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    tutor_filter = request.args.get('tutor', '', type=int)
    date_filter = request.args.get('date', '')
    
    query = Class.query.filter_by(class_type='demo')
    
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    if tutor_filter:
        query = query.filter_by(tutor_id=tutor_filter)
    
    if date_filter:
        filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
        query = query.filter_by(scheduled_date=filter_date)
    
    demo_classes = query.order_by(Class.scheduled_date.desc(), Class.scheduled_time.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    tutors = Tutor.query.filter_by(status='active').all()
    
    return render_template('demo/demo_classes.html', demo_classes=demo_classes, tutors=tutors)

@bp.route('/demo/classes/schedule', methods=['GET', 'POST'])
@bp.route('/demo/classes/schedule/<int:demo_student_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def schedule_demo_class(demo_student_id=None):
    """Schedule demo class for a demo student"""
    form = DemoClassForm()
    demo_student = None
    
    if demo_student_id:
        demo_student = DemoStudent.query.get_or_404(demo_student_id)
        # Pre-fill form with demo student details
        form.demo_student_id.data = demo_student.id
        form.subject.data = demo_student.subject
    
    if form.validate_on_submit():
        try:
            demo_student = DemoStudent.query.get_or_404(form.demo_student_id.data)
            tutor = Tutor.query.get_or_404(form.tutor_id.data)
            
            scheduled_date = form.scheduled_date.data
            scheduled_time = form.scheduled_time.data
            
            # Check tutor availability using existing function
            day_of_week = scheduled_date.strftime('%A').lower()
            time_str = scheduled_time.strftime('%H:%M')
            
            if not tutor.is_available_at(day_of_week, time_str):
                flash(f'Tutor {tutor.user.full_name} is not available on {day_of_week.title()} at {time_str}', 'error')
                return render_template('demo/schedule_demo_class.html', form=form, demo_student=demo_student)
            
            # Check for scheduling conflicts using existing function
            existing_class = Class.query.filter_by(
                tutor_id=form.tutor_id.data,
                scheduled_date=scheduled_date,
                scheduled_time=scheduled_time,
                status='scheduled'
            ).first()
            
            if existing_class:
                flash(f'Tutor already has a class scheduled at this time', 'error')
                return render_template('demo/schedule_demo_class.html', form=form, demo_student=demo_student)
            
            # Generate meeting link
            meeting_data = generate_meeting_link(form.platform.data)
            
            # Create demo class
            demo_class = Class(
                subject=form.subject.data,
                class_type='demo',
                scheduled_date=scheduled_date,
                scheduled_time=scheduled_time,
                duration=int(form.duration.data),
                tutor_id=form.tutor_id.data,
                demo_student_id=demo_student.id,
                meeting_link=meeting_data.get('join_url'),
                meeting_id=meeting_data.get('meeting_id'),
                meeting_password=meeting_data.get('password'),
                class_notes=form.class_notes.data,
                status='scheduled',
                created_by=current_user.id
            )
            
            # Update demo student status and meeting details
            demo_student.demo_status = 'scheduled'
            demo_student.set_meeting_details(meeting_data)
            
            db.session.add(demo_class)
            db.session.commit()
            
            # Send confirmation email
            send_demo_confirmation_email(demo_student, demo_class)
            
            flash(f'Demo class scheduled successfully for {demo_student.full_name}!', 'success')
            return redirect(url_for('demo.demo_classes'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error scheduling demo class: {str(e)}', 'error')
    
    return render_template('demo/schedule_demo_class.html', form=form, demo_student=demo_student)

@bp.route('/demo/classes/<int:class_id>')
@login_required
@admin_required
def demo_class_details(class_id):
    """View demo class details"""
    demo_class = Class.query.filter_by(id=class_id, class_type='demo').first_or_404()
    demo_student = DemoStudent.query.get(demo_class.demo_student_id)
    
    return render_template('demo/demo_class_details.html', 
                         demo_class=demo_class, demo_student=demo_student)

@bp.route('/demo/classes/<int:class_id>/feedback', methods=['GET', 'POST'])
@login_required
@admin_required
def demo_class_feedback(class_id):
    """Submit feedback for demo class"""
    demo_class = Class.query.filter_by(id=class_id, class_type='demo').first_or_404()
    demo_student = DemoStudent.query.get(demo_class.demo_student_id)
    form = DemoFeedbackForm()
    
    if form.validate_on_submit():
        try:
            # Prepare feedback data
            feedback_data = {
                'student_level': form.student_level.data,
                'student_engagement': form.student_engagement.data,
                'topics_covered': form.topics_covered.data,
                'student_strengths': form.student_strengths.data,
                'areas_for_improvement': form.areas_for_improvement.data,
                'recommendation': form.recommendation.data,
                'suggested_frequency': form.suggested_frequency.data,
                'tutor_comments': form.tutor_comments.data,
                'feedback_date': datetime.utcnow().isoformat(),
                'feedback_by': current_user.full_name
            }
            
            # Save feedback
            demo_student.set_demo_feedback(feedback_data)
            demo_student.demo_status = 'completed'
            demo_class.status = 'completed'
            
            db.session.commit()
            
            flash('Demo class feedback submitted successfully!', 'success')
            return redirect(url_for('demo.demo_class_details', class_id=class_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error submitting feedback: {str(e)}', 'error')
    
    return render_template('demo/demo_class_feedback.html', 
                         form=form, demo_class=demo_class, demo_student=demo_student)

# ============ CONVERSION ROUTES ============

@bp.route('/demo/students/<int:demo_student_id>/convert', methods=['GET', 'POST'])
@login_required
@admin_required
def convert_to_regular(demo_student_id):
    """Convert demo student to regular student"""
    demo_student = DemoStudent.query.get_or_404(demo_student_id)
    
    if demo_student.demo_status != 'completed':
        flash('Demo class must be completed before conversion', 'error')
        return redirect(url_for('demo.demo_student_details', demo_student_id=demo_student_id))
    
    form = ConvertDemoForm()
    form.demo_student_id.data = demo_student_id
    
    if form.validate_on_submit():
        try:
            # Create regular student record
            regular_student = Student(
                full_name=demo_student.full_name,
                email=demo_student.email,
                phone=demo_student.phone,
                date_of_birth=form.date_of_birth.data,
                address=form.address.data,
                state=form.state.data,
                pin_code=form.pin_code.data,
                grade=demo_student.grade,
                board=demo_student.board,
                school_name=form.school_name.data,
                academic_year=form.academic_year.data,
                department_id=current_user.department_id,
                status='active'
            )
            
            # Set subjects enrolled
            regular_student.set_subjects_enrolled([demo_student.subject])
            
            # Set parent details
            parent_details = {
                'father_name': form.father_name.data,
                'mother_name': form.mother_name.data,
                'parent_phone': demo_student.phone,
                'parent_email': demo_student.email,
                'occupation': form.parent_occupation.data
            }
            regular_student.set_parent_details(parent_details)
            
            # Set fee structure
            fee_structure = {
                'total_fee': int(form.total_fee.data),
                'payment_mode': form.payment_mode.data,
                'payment_schedule': form.payment_mode.data,
                'amount_paid': 0,
                'balance_amount': int(form.total_fee.data)
            }
            regular_student.set_fee_structure(fee_structure)
            
            db.session.add(regular_student)
            db.session.flush()  # Get student ID
            
            # Mark demo student as converted
            demo_student.mark_as_converted(regular_student.id, form.conversion_notes.data)
            
            db.session.commit()
            
            flash(f'Demo student {demo_student.full_name} converted to regular student successfully!', 'success')
            return redirect(url_for('admin.student_details', student_id=regular_student.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error converting student: {str(e)}', 'error')
    
    return render_template('demo/convert_to_regular.html', 
                         form=form, demo_student=demo_student)

# ============ API ROUTES ============

@bp.route('/api/v1/demo/check-availability')
@login_required
@admin_required
def api_check_demo_availability():
    """Check tutor availability for demo class (same as regular class)"""
    try:
        tutor_id = request.args.get('tutor_id', type=int)
        date_str = request.args.get('date')
        time_str = request.args.get('time')
        
        if not all([tutor_id, date_str, time_str]):
            return jsonify({'error': 'Missing required parameters'}), 400
        
        tutor = Tutor.query.get_or_404(tutor_id)
        scheduled_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        scheduled_time = datetime.strptime(time_str, '%H:%M').time()
        
        # Check tutor availability (reuse existing function)
        day_of_week = scheduled_date.strftime('%A').lower()
        is_available = tutor.is_available_at(day_of_week, time_str)
        
        # Check for existing classes (regular OR demo)
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
            'message': 'Available for demo class' if (is_available and not existing_class) else 
                      'Tutor not available at this time' if not is_available else 
                      f'Tutor already has a {existing_class.class_type} class at this time'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/v1/demo/compatible-tutors')
@login_required
@admin_required
def api_compatible_demo_tutors():
    """Get tutors compatible with demo student requirements"""
    try:
        demo_student_id = request.args.get('demo_student_id', type=int)
        
        if demo_student_id:
            demo_student = DemoStudent.query.get_or_404(demo_student_id)
            subject = demo_student.subject.lower()
            grade = demo_student.grade
            board = demo_student.board
        else:
            subject = request.args.get('subject', '').lower()
            grade = request.args.get('grade', '')
            board = request.args.get('board', '')
        
        # Get all active tutors with availability (reuse existing logic)
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
                'user_name': tutor.user.full_name if tutor.user else 'Unknown',
                'email': tutor.user.email if tutor.user else '',
                'subjects': tutor.get_subjects(),
                'grades': tutor.get_grades(),
                'boards': tutor.get_boards(),
                'availability': tutor.get_availability()
            })
        
        return jsonify({
            'success': True,
            'compatible_tutors': compatible_tutors,
            'total_count': len(compatible_tutors)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/v1/demo/statistics')
@login_required
@admin_required  
def api_demo_statistics():
    """Get demo class statistics and conversion rates"""
    try:
        # Demo statistics
        total_demos = DemoStudent.query.count()
        scheduled_demos = DemoStudent.query.filter_by(demo_status='scheduled').count()
        completed_demos = DemoStudent.query.filter_by(demo_status='completed').count()
        converted_demos = DemoStudent.query.filter_by(demo_status='converted').count()
        
        # Conversion rate
        conversion_rate = (converted_demos / completed_demos * 100) if completed_demos > 0 else 0
        
        # Monthly trends
        from sqlalchemy import func, extract
        monthly_demos = db.session.query(
            extract('month', DemoStudent.created_at).label('month'),
            func.count(DemoStudent.id).label('count')
        ).group_by(extract('month', DemoStudent.created_at)).all()
        
        return jsonify({
            'success': True,
            'statistics': {
                'total_demos': total_demos,
                'scheduled_demos': scheduled_demos,
                'completed_demos': completed_demos,
                'converted_demos': converted_demos,
                'conversion_rate': round(conversion_rate, 2),
                'monthly_trends': [{'month': m, 'count': c} for m, c in monthly_demos]
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500