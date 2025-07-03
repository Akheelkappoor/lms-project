from flask import Blueprint, render_template, request, jsonify, make_response
from flask_login import login_required, current_user
from datetime import datetime, date
import csv
import io
from app import db
from app.models.tutor import Tutor
from app.models.student import Student
from app.routes.admin import admin_required

bp = Blueprint('finance', __name__)

# Salary endpoints
@bp.route('/api/v1/finance/salary/tutor/<int:tutor_id>')
@login_required
@admin_required
def get_tutor_salary(tutor_id):
    """Get tutor salary details"""
    tutor = Tutor.query.get_or_404(tutor_id)
    month = request.args.get('month', datetime.now().month, type=int)
    year = request.args.get('year', datetime.now().year, type=int)
    
    salary_data = tutor.calculate_monthly_salary(month, year)
    salary_history = tutor.get_salary_history()
    
    return jsonify({
        'tutor_id': tutor_id,
        'salary_calculation': salary_data,
        'outstanding_amount': tutor.get_outstanding_salary(),
        'payment_history': salary_history
    })

@bp.route('/api/v1/finance/salary/calculate', methods=['POST'])
@login_required
@admin_required
def calculate_salary():
    """Calculate monthly salary for tutors"""
    data = request.get_json()
    tutor_id = data.get('tutor_id')
    month = data.get('month', datetime.now().month)
    year = data.get('year', datetime.now().year)
    
    tutor = Tutor.query.get_or_404(tutor_id)
    salary_data = tutor.calculate_monthly_salary(month, year)
    
    return jsonify(salary_data)

@bp.route('/api/v1/finance/salary/generate', methods=['POST'])
@login_required
@admin_required
def generate_salary():
    """Generate salary payment"""
    data = request.get_json()
    tutor_id = data.get('tutor_id')
    month = data.get('month')
    year = data.get('year')
    amount = data.get('amount')
    
    tutor = Tutor.query.get_or_404(tutor_id)
    payment_record = tutor.add_salary_payment(amount, month, year, 'pending')
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'payment_record': payment_record
    })

@bp.route('/api/v1/finance/salary/export')
@login_required
@admin_required
def export_salary():
    """Export salary data to CSV"""
    month = request.args.get('month', datetime.now().month, type=int)
    year = request.args.get('year', datetime.now().year, type=int)
    
    tutors = Tutor.query.filter_by(status='active').all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Tutor Name', 'Base Salary', 'Calculated Salary', 'Classes', 'Attendance', 'Outstanding'])
    
    for tutor in tutors:
        salary_data = tutor.calculate_monthly_salary(month, year)
        writer.writerow([
            tutor.user.full_name if tutor.user else '',
            salary_data['base_salary'],
            salary_data['calculated_salary'],
            salary_data['total_classes'],
            salary_data['attended_classes'],
            tutor.get_outstanding_salary()
        ])
    
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = f'attachment; filename=salary_report_{month}_{year}.csv'
    
    return response

# Fee endpoints
@bp.route('/api/v1/finance/fees/student/<int:student_id>')
@login_required
@admin_required
def get_student_fees(student_id):
    """Get student fee details"""
    student = Student.query.get_or_404(student_id)
    
    return jsonify({
        'student_id': student_id,
        'fee_structure': student.get_fee_structure(),
        'outstanding_amount': student.calculate_outstanding_fees(),
        'payment_history': student.get_fee_payment_history(),
        'fee_status': student.get_fee_status()
    })

@bp.route('/api/v1/finance/fees/payment', methods=['POST'])
@login_required
@admin_required
def record_fee_payment():
    """Record fee payment"""
    data = request.get_json()
    student_id = data.get('student_id')
    amount = data.get('amount')
    payment_mode = data.get('payment_mode', 'cash')
    notes = data.get('notes', '')
    
    student = Student.query.get_or_404(student_id)
    payment_record = student.add_fee_payment(amount, payment_mode, notes=notes)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'payment_record': payment_record,
        'new_balance': student.calculate_outstanding_fees()
    })

@bp.route('/api/v1/finance/fees/pending')
@login_required
@admin_required
def get_pending_fees():
    """Get students with pending fees"""
    students = Student.query.filter_by(is_active=True).all()
    pending_students = []
    
    for student in students:
        outstanding = student.calculate_outstanding_fees()
        if outstanding > 0:
            pending_students.append({
                'student_id': student.id,
                'student_name': student.full_name,
                'outstanding_amount': outstanding,
                'fee_status': student.get_fee_status()
            })
    
    return jsonify(pending_students)

@bp.route('/api/v1/finance/fees/export')
@login_required
@admin_required
def export_fees():
    """Export fee data to CSV"""
    students = Student.query.filter_by(is_active=True).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Student Name', 'Total Fee', 'Amount Paid', 'Outstanding', 'Status'])
    
    for student in students:
        fee_structure = student.get_fee_structure()
        writer.writerow([
            student.full_name,
            fee_structure.get('total_fee', 0),
            fee_structure.get('amount_paid', 0),
            student.calculate_outstanding_fees(),
            student.get_fee_status()
        ])
    
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=fee_report.csv'
    
    return response