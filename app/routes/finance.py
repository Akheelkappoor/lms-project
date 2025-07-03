from flask import Blueprint, request, jsonify, send_file
from flask_login import login_required, current_user
from app import db
from app.models.tutor import Tutor
from app.models.student import Student
from app.models.user import User
from datetime import datetime, date
import csv
import io
from functools import wraps

bp = Blueprint('finance', __name__, url_prefix='/api/v1/finance')

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ['superadmin', 'coordinator']:
            return jsonify({'error': 'Access denied'}), 403
        return f(*args, **kwargs)
    return decorated_function

# ===== SALARY ENDPOINTS =====

@bp.route('/salary/tutor/<int:tutor_id>', methods=['GET'])
@login_required
@admin_required
def get_tutor_salary(tutor_id):
    """Get tutor salary info"""
    try:
        tutor = Tutor.query.get_or_404(tutor_id)
        
        month = request.args.get('month', datetime.now().month, type=int)
        year = request.args.get('year', datetime.now().year, type=int)
        
        # Calculate current month salary
        calculation = tutor.calculate_monthly_salary(month, year)
        
        # Get history if available
        history = tutor.get_salary_history() if hasattr(tutor, 'get_salary_history') else []
        
        # Get outstanding if available
        outstanding = tutor.get_outstanding_salary() if hasattr(tutor, 'get_outstanding_salary') else []
        
        return jsonify({
            'tutor_id': tutor.id,
            'tutor_name': tutor.user.full_name if tutor.user else 'Unknown',
            'current_calculation': calculation,
            'salary_history': history,
            'outstanding_months': outstanding,
            'bank_details': tutor.get_bank_details()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/salary/calculate', methods=['POST'])
@login_required
@admin_required
def calculate_salary():
    """Calculate salary for multiple tutors"""
    try:
        data = request.get_json()
        tutor_ids = data.get('tutor_ids', [])
        month = data.get('month', datetime.now().month)
        year = data.get('year', datetime.now().year)
        
        if not tutor_ids:
            tutors = Tutor.query.filter_by(status='active').all()
            tutor_ids = [t.id for t in tutors]
        
        results = []
        for tutor_id in tutor_ids:
            tutor = Tutor.query.get(tutor_id)
            if tutor:
                calculation = tutor.calculate_monthly_salary(month, year)
                results.append({
                    'tutor_id': tutor.id,
                    'tutor_name': tutor.user.full_name if tutor.user else 'Unknown',
                    'calculation': calculation
                })
        
        return jsonify({
            'month': month,
            'year': year,
            'calculations': results,
            'total_amount': sum(r['calculation']['net_salary'] for r in results)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/salary/generate', methods=['POST'])
@login_required
@admin_required
def generate_salary():
    """Generate salary payments"""
    try:
        data = request.get_json()
        calculations = data.get('calculations', [])
        payment_date = data.get('payment_date', datetime.now().date().isoformat())
        
        processed = []
        errors = []
        
        for calc in calculations:
            try:
                tutor = Tutor.query.get(calc['tutor_id'])
                if not tutor:
                    errors.append(f"Tutor {calc['tutor_id']} not found")
                    continue
                
                payment_data = {
                    'amount': calc['calculation']['net_salary'],
                    'month': calc['calculation']['month'],
                    'year': calc['calculation']['year'],
                    'payment_date': payment_date,
                    'status': 'paid'
                }
                
                if hasattr(tutor, 'add_salary_payment'):
                    tutor.add_salary_payment(payment_data)
                
                processed.append({
                    'tutor_id': tutor.id,
                    'tutor_name': tutor.user.full_name if tutor.user else 'Unknown',
                    'amount': calc['calculation']['net_salary']
                })
                
            except Exception as e:
                errors.append(f"Error processing tutor {calc.get('tutor_id', 'unknown')}: {str(e)}")
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'processed': processed,
            'errors': errors,
            'total_amount': sum(p['amount'] for p in processed)
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/salary/export', methods=['POST'])
@login_required
@admin_required
def export_salary():
    """Export salary data to CSV"""
    try:
        data = request.get_json()
        month = data.get('month', datetime.now().month)
        year = data.get('year', datetime.now().year)
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Headers
        writer.writerow([
            'Tutor ID', 'Name', 'Email', 'Salary Type', 'Base Salary',
            'Hours', 'Classes', 'Bonus', 'Deductions', 'Net Salary',
            'Bank Account', 'IFSC', 'Month', 'Year'
        ])
        
        tutors = Tutor.query.filter_by(status='active').all()
        
        for tutor in tutors:
            calculation = tutor.calculate_monthly_salary(month, year)
            bank = tutor.get_bank_details()
            
            writer.writerow([
                tutor.id,
                tutor.user.full_name if tutor.user else 'N/A',
                tutor.user.email if tutor.user else 'N/A',
                tutor.salary_type or 'monthly',
                calculation['base_salary'],
                calculation['total_hours'],
                calculation['total_classes'],
                calculation['bonus'],
                calculation['deductions'],
                calculation['net_salary'],
                bank.get('account_number', ''),
                bank.get('ifsc_code', ''),
                month,
                year
            ])
        
        output.seek(0)
        file_content = output.getvalue().encode('utf-8')
        file_buffer = io.BytesIO(file_content)
        
        return send_file(
            file_buffer,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'salary_report_{month}_{year}.csv'
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ===== FEE ENDPOINTS =====

@bp.route('/fees/student/<int:student_id>', methods=['GET'])
@login_required
@admin_required
def get_student_fees(student_id):
    """Get student fee information"""
    try:
        student = Student.query.get_or_404(student_id)
        
        outstanding = student.calculate_outstanding_fees()
        history = student.get_payment_history()
        fee_structure = student.get_fee_structure()
        
        return jsonify({
            'student_id': student.id,
            'student_name': student.full_name,
            'email': student.email,
            'outstanding_fees': outstanding,
            'payment_history': history,
            'fee_structure': fee_structure,
            'is_defaulter': student.is_fee_defaulter() if hasattr(student, 'is_fee_defaulter') else False
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/fees/payment', methods=['POST'])
@login_required
@admin_required
def record_fee_payment():
    """Record fee payment"""
    try:
        data = request.get_json()
        student_id = data.get('student_id')
        amount = float(data.get('amount', 0))
        payment_mode = data.get('payment_mode', 'cash')
        payment_date = data.get('payment_date', datetime.now().date().isoformat())
        notes = data.get('notes', '')
        
        if not student_id or amount <= 0:
            return jsonify({'error': 'Valid student ID and amount required'}), 400
        
        student = Student.query.get_or_404(student_id)
        
        payment_data = {
            'amount': amount,
            'payment_mode': payment_mode,
            'payment_date': payment_date,
            'notes': notes,
            'recorded_by': current_user.full_name
        }
        
        student.add_payment_record(payment_data)
        db.session.commit()
        
        outstanding = student.calculate_outstanding_fees()
        
        return jsonify({
            'success': True,
            'message': f'Payment of ₹{amount:,.2f} recorded',
            'new_outstanding': outstanding['outstanding_amount']
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/fees/pending', methods=['GET'])
@login_required
@admin_required
def get_pending_fees():
    """Get students with pending fees"""
    try:
        students = Student.query.filter_by(is_active=True).all()
        pending_students = []
        
        for student in students:
            outstanding = student.calculate_outstanding_fees()
            if outstanding['outstanding_amount'] > 0:
                pending_students.append({
                    'student_id': student.id,
                    'student_name': student.full_name,
                    'email': student.email,
                    'grade': student.grade,
                    'outstanding_amount': outstanding['outstanding_amount'],
                    'overdue_amount': outstanding['overdue_amount'],
                    'payment_status': outstanding['payment_status']
                })
        
        # Sort by outstanding amount
        pending_students.sort(key=lambda x: x['outstanding_amount'], reverse=True)
        
        return jsonify({
            'total_pending': len(pending_students),
            'total_outstanding': sum(s['outstanding_amount'] for s in pending_students),
            'students': pending_students
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/fees/export', methods=['POST'])
@login_required
@admin_required
def export_fees():
    """Export fee data to CSV"""
    try:
        data = request.get_json()
        report_type = data.get('report_type', 'outstanding')
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        if report_type == 'outstanding':
            writer.writerow([
                'Student ID', 'Name', 'Email', 'Grade', 'Total Fee',
                'Amount Paid', 'Outstanding', 'Overdue', 'Status'
            ])
            
            students = Student.query.filter_by(is_active=True).all()
            
            for student in students:
                outstanding = student.calculate_outstanding_fees()
                fee_structure = student.get_fee_structure()
                
                writer.writerow([
                    student.id,
                    student.full_name,
                    student.email,
                    student.grade,
                    fee_structure.get('total_fee', 0),
                    fee_structure.get('amount_paid', 0),
                    outstanding['outstanding_amount'],
                    outstanding['overdue_amount'],
                    outstanding['payment_status']
                ])
        
        output.seek(0)
        file_content = output.getvalue().encode('utf-8')
        file_buffer = io.BytesIO(file_content)
        
        return send_file(
            file_buffer,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'fee_{report_type}_report.csv'
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ===== DASHBOARD =====

@bp.route('/dashboard', methods=['GET'])
@login_required
@admin_required
def finance_dashboard():
    """Get finance dashboard data"""
    try:
        month = request.args.get('month', datetime.now().month, type=int)
        year = request.args.get('year', datetime.now().year, type=int)
        
        # Salary summary
        active_tutors = Tutor.query.filter_by(status='active').all()
        total_salary = 0
        for tutor in active_tutors:
            calc = tutor.calculate_monthly_salary(month, year)
            total_salary += calc['net_salary']
        
        # Fee summary
        active_students = Student.query.filter_by(is_active=True).all()
        total_fees = 0
        collected_fees = 0
        outstanding_fees = 0
        
        for student in active_students:
            fee_structure = student.get_fee_structure()
            outstanding = student.calculate_outstanding_fees()
            
            total_fees += fee_structure.get('total_fee', 0)
            collected_fees += fee_structure.get('amount_paid', 0)
            outstanding_fees += outstanding['outstanding_amount']
        
        return jsonify({
            'month': month,
            'year': year,
            'salary_summary': {
                'total_tutors': len(active_tutors),
                'total_salary_expense': total_salary
            },
            'fee_summary': {
                'total_students': len(active_students),
                'total_fees': total_fees,
                'collected_fees': collected_fees,
                'outstanding_fees': outstanding_fees,
                'collection_percentage': (collected_fees / total_fees * 100) if total_fees > 0 else 0
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500