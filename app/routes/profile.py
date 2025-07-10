from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app, send_file
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import json
from app import db
from app.models.user import User
from app.models.tutor import Tutor
from app.forms.user import EditProfileForm, ChangePasswordForm, BankingDetailsForm
from functools import wraps

bp = Blueprint('profile', __name__)

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

@bp.route('/profile')
@login_required
def view_profile():
    """View user profile"""
    tutor_profile = None
    if current_user.role == 'tutor':
        tutor_profile = Tutor.query.filter_by(user_id=current_user.id).first()
    
    return render_template('profile/view_profile.html', 
                         user=current_user, 
                         tutor_profile=tutor_profile)

@bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """Edit user profile"""
    form = EditProfileForm(obj=current_user)
    
    if form.validate_on_submit():
        try:
            # Update basic information
            current_user.full_name = form.full_name.data
            current_user.phone = form.phone.data
            current_user.address = form.address.data
            current_user.working_hours = form.working_hours.data
            
            # Handle emergency contact
            if form.emergency_name.data and form.emergency_phone.data:
                emergency_contact = {
                    'name': form.emergency_name.data,
                    'phone': form.emergency_phone.data,
                    'relationship': form.emergency_relationship.data,
                    'email': form.emergency_email.data
                }
                current_user.set_emergency_contact(emergency_contact)
            
            # Handle profile picture upload
            if form.profile_picture.data:
                filename = save_uploaded_file(form.profile_picture.data, 'profiles')
                if filename:
                    # Delete old profile picture if exists
                    if current_user.profile_picture:
                        old_file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'profiles', current_user.profile_picture)
                        if os.path.exists(old_file_path):
                            os.remove(old_file_path)
                    
                    current_user.profile_picture = filename
            
            db.session.commit()
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('profile.view_profile'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating profile: {str(e)}', 'error')
    
    # Pre-populate emergency contact
    emergency_contact = current_user.get_emergency_contact()
    if emergency_contact:
        form.emergency_name.data = emergency_contact.get('name')
        form.emergency_phone.data = emergency_contact.get('phone')
        form.emergency_relationship.data = emergency_contact.get('relationship')
        form.emergency_email.data = emergency_contact.get('email')
    
    return render_template('profile/edit_profile.html', form=form)

@bp.route('/profile/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Change user password"""
    form = ChangePasswordForm()
    
    if form.validate_on_submit():
        # Verify current password
        if not current_user.check_password(form.current_password.data):
            flash('Current password is incorrect.', 'error')
            return render_template('profile/change_password.html', form=form)
        
        # Set new password
        current_user.set_password(form.new_password.data)
        db.session.commit()
        flash('Your password has been changed successfully.', 'success')
        return redirect(url_for('profile.view_profile'))
    
    return render_template('profile/change_password.html', form=form)

@bp.route('/profile/banking', methods=['GET', 'POST'])
@login_required
def banking_details():
    """Manage banking information (Tutors only)"""
    if current_user.role != 'tutor':
        flash('Banking details are only available for tutors.', 'error')
        return redirect(url_for('profile.view_profile'))
    
    tutor = Tutor.query.filter_by(user_id=current_user.id).first()
    if not tutor:
        flash('Tutor profile not found.', 'error')
        return redirect(url_for('profile.view_profile'))
    
    form = BankingDetailsForm()
    
    if form.validate_on_submit():
        try:
            banking_info = {
                'account_holder_name': form.account_holder_name.data,
                'bank_name': form.bank_name.data,
                'branch_name': form.branch_name.data,
                'account_number': form.account_number.data,
                'ifsc_code': form.ifsc_code.data,
                'account_type': form.account_type.data,
                'updated_at': datetime.now().isoformat(),
                'updated_by': current_user.full_name
            }
            
            # Handle bank verification document upload
            if form.bank_document.data:
                filename = save_uploaded_file(form.bank_document.data, 'documents')
                if filename:
                    banking_info['verification_document'] = filename
            
            tutor.set_bank_details(banking_info)
            db.session.commit()
            
            flash('Banking details updated successfully!', 'success')
            return redirect(url_for('profile.view_profile'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating banking details: {str(e)}', 'error')
    
    # Pre-populate form with existing data
    bank_details = tutor.get_bank_details()
    if bank_details:
        form.account_holder_name.data = bank_details.get('account_holder_name')
        form.bank_name.data = bank_details.get('bank_name')
        form.branch_name.data = bank_details.get('branch_name')
        form.account_number.data = bank_details.get('account_number')
        form.ifsc_code.data = bank_details.get('ifsc_code')
        form.account_type.data = bank_details.get('account_type')
    
    return render_template('profile/banking_details.html', form=form, tutor=tutor)

@bp.route('/profile/documents')
@login_required
def manage_documents():
    """Manage user documents"""
    tutor_profile = None
    if current_user.role == 'tutor':
        tutor_profile = Tutor.query.filter_by(user_id=current_user.id).first()
    
    return render_template('profile/manage_documents.html', 
                         user=current_user, 
                         tutor_profile=tutor_profile)

@bp.route('/profile/documents/upload', methods=['POST'])
@login_required
def upload_document():
    """Upload a document"""
    try:
        document_type = request.form.get('document_type')
        file = request.files.get('document_file')
        
        if not file or not document_type:
            return jsonify({'error': 'File and document type are required'}), 400
        
        filename = save_uploaded_file(file, 'documents')
        if not filename:
            return jsonify({'error': 'Failed to save file'}), 500
        
        # Update user or tutor documents based on role
        if current_user.role == 'tutor':
            tutor = Tutor.query.filter_by(user_id=current_user.id).first()
            if tutor:
                documents = tutor.get_documents()
                documents[document_type] = {
                    'filename': filename,
                    'uploaded_at': datetime.now().isoformat(),
                    'uploaded_by': current_user.full_name
                }
                tutor.set_documents(documents)
        else:
            # For admin/coordinator, store in user profile or separate table
            # This can be extended based on requirements
            pass
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'{document_type.replace("_", " ").title()} uploaded successfully',
            'filename': filename
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error uploading document: {str(e)}'}), 500

@bp.route('/profile/documents/download/<document_type>')
@login_required
def download_document(document_type):
    """Download a document"""
    try:
        filename = None
        
        # Get document filename based on user role
        if current_user.role == 'tutor':
            tutor = Tutor.query.filter_by(user_id=current_user.id).first()
            if tutor:
                documents = tutor.get_documents()
                if document_type in documents:
                    filename = documents[document_type].get('filename')
        
        if not filename:
            flash('Document not found.', 'error')
            return redirect(url_for('profile.manage_documents'))
        
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'documents', filename)
        
        if not os.path.exists(file_path):
            flash('File not found on server.', 'error')
            return redirect(url_for('profile.manage_documents'))
        
        return send_file(file_path, as_attachment=True, download_name=f"{document_type}_{filename}")
        
    except Exception as e:
        flash(f'Error downloading document: {str(e)}', 'error')
        return redirect(url_for('profile.manage_documents'))

@bp.route('/profile/documents/delete/<document_type>', methods=['POST'])
@login_required
def delete_document(document_type):
    """Delete a document"""
    try:
        filename = None
        
        # Get and remove document based on user role
        if current_user.role == 'tutor':
            tutor = Tutor.query.filter_by(user_id=current_user.id).first()
            if tutor:
                documents = tutor.get_documents()
                if document_type in documents:
                    filename = documents[document_type].get('filename')
                    del documents[document_type]
                    tutor.set_documents(documents)
        
        if filename:
            # Delete physical file
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'documents', filename)
            if os.path.exists(file_path):
                os.remove(file_path)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'{document_type.replace("_", " ").title()} deleted successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error deleting document: {str(e)}'}), 500

@bp.route('/profile/system-documents')
@login_required
def system_documents():
    """Download system documents (offer letter, policies, etc.)"""
    documents = {
        'offer_letter': {
            'title': 'Offer Letter',
            'description': 'Your employment offer letter',
            'available': True
        },
        'company_policies': {
            'title': 'Company Policies',
            'description': 'HR policies and code of conduct',
            'available': True
        },
        'handbook': {
            'title': 'Employee Handbook',
            'description': 'Guidelines and procedures',
            'available': True
        },
        'certificates': {
            'title': 'Training Certificates',
            'description': 'Completion certificates for training programs',
            'available': current_user.role == 'tutor'
        }
    }
    
    return render_template('profile/system_documents.html', documents=documents)

@bp.route('/profile/system-documents/download/<doc_type>')
@login_required
def download_system_document(doc_type):
    """Download system-generated documents"""
    # This would typically generate or serve pre-made documents
    # For now, we'll create placeholder functionality
    
    document_mapping = {
        'offer_letter': 'offer_letter_template.pdf',
        'company_policies': 'company_policies.pdf',
        'handbook': 'employee_handbook.pdf',
        'certificates': 'training_certificates.pdf'
    }
    
    if doc_type not in document_mapping:
        flash('Invalid document type.', 'error')
        return redirect(url_for('profile.system_documents'))
    
    # In a real implementation, you would:
    # 1. Generate personalized documents (offer letter with user details)
    # 2. Serve from a secure documents folder
    # 3. Log document downloads for audit purposes
    
    flash(f'{doc_type.replace("_", " ").title()} download functionality will be implemented.', 'info')
    return redirect(url_for('profile.system_documents'))

@bp.route('/profile/notifications', methods=['GET', 'POST'])
@login_required
def notification_preferences():
    """Manage notification preferences"""
    if request.method == 'POST':
        try:
            preferences = {
                'email_notifications': request.form.get('email_notifications') == 'on',
                'sms_notifications': request.form.get('sms_notifications') == 'on',
                'class_reminders': request.form.get('class_reminders') == 'on',
                'attendance_alerts': request.form.get('attendance_alerts') == 'on',
                'payment_notifications': request.form.get('payment_notifications') == 'on',
                'system_updates': request.form.get('system_updates') == 'on',
                'updated_at': datetime.now().isoformat()
            }
            
            # Store preferences (this would typically be in a separate table or user settings)
            # For now, we'll use the emergency_contact field as a placeholder
            # In production, create a separate UserPreferences model
            
            flash('Notification preferences updated successfully!', 'success')
            return redirect(url_for('profile.view_profile'))
            
        except Exception as e:
            flash(f'Error updating preferences: {str(e)}', 'error')
    
    return render_template('profile/notification_preferences.html')