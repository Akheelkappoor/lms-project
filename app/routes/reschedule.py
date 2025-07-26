# app/routes/reschedule.py

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from datetime import datetime, date
from app import db
from app.models.reschedule_request import RescheduleRequest
from app.models.class_model import Class
from app.models.tutor import Tutor
from app.models.user import User
from app.forms.reschedule_forms import (
    CreateRescheduleRequestForm, ReviewRescheduleRequestForm, 
    BulkRescheduleRequestForm, RescheduleRequestSearchForm, QuickRescheduleForm
)
from functools import wraps

bp = Blueprint('reschedule', __name__)

def tutor_required(f):
    """Decorator to require tutor access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role not in ['tutor']:
            flash('Access denied. Tutor access required.', 'error')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin/coordinator access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role not in ['superadmin', 'admin', 'coordinator']:
            flash('Access denied. Admin access required.', 'error')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated_function

# ============ TUTOR ROUTES ============

@bp.route('/tutor/reschedule-requests')
@login_required
@tutor_required
def tutor_reschedule_requests():
    """View tutor's reschedule requests"""
    tutor = Tutor.query.filter_by(user_id=current_user.id).first()
    if not tutor:
        flash('Tutor profile not found.', 'error')
        return redirect(url_for('dashboard.index'))
    
    requests = RescheduleRequest.get_requests_for_tutor(tutor.id)
    
    return render_template('tutor/reschedule_requests.html', 
                         requests=requests, tutor=tutor)

@bp.route('/tutor/request-reschedule/<int:class_id>', methods=['GET', 'POST'])
@login_required
@tutor_required
def create_reschedule_request(class_id):
    """Create a new reschedule request"""
    class_item = Class.query.get_or_404(class_id)
    
    # Check if this tutor owns the class
    tutor = Tutor.query.filter_by(user_id=current_user.id).first()
    if not tutor or class_item.tutor_id != tutor.id:
        flash('Access denied. You can only reschedule your own classes.', 'error')
        return redirect(url_for('tutor.my_classes'))
    
    # Check if class can be rescheduled
    if not class_item.can_be_rescheduled():
        flash('This class cannot be rescheduled.', 'error')
        return redirect(url_for('tutor.my_classes'))
    
    # Check for existing pending request
    existing_request = RescheduleRequest.query.filter_by(
        class_id=class_id,
        status='pending'
    ).first()
    
    if existing_request:
        flash('There is already a pending reschedule request for this class.', 'warning')
        return redirect(url_for('reschedule.tutor_reschedule_requests'))
    
    form = CreateRescheduleRequestForm()
    form.class_id.data = class_id
    
    if form.validate_on_submit():
        try:
            # Create reschedule request
            reschedule_request = RescheduleRequest(
                class_id=class_id,
                requested_date=form.requested_date.data,
                requested_time=form.requested_time.data,
                reason=form.reason.data,
                requested_by=current_user.id
            )
            
            # Check for conflicts
            conflicts = reschedule_request.check_conflicts()
            
            db.session.add(reschedule_request)
            db.session.commit()
            
            from app.services.reschedule_notifications import RescheduleNotificationService
            RescheduleNotificationService.send_reschedule_request_notification(reschedule_request)
            
            if conflicts:
                flash('Reschedule request submitted with conflicts detected. Admin review required.', 'warning')
            else:
                flash('Reschedule request submitted successfully!', 'success')
            
            return redirect(url_for('reschedule.tutor_reschedule_requests'))
            
        except Exception as e:
            db.session.rollback()
            flash('Error creating reschedule request. Please try again.', 'error')
            current_app.logger.error(f"Error creating reschedule request: {str(e)}")
    
    return render_template('tutor/create_reschedule_request.html', 
                         form=form, class_item=class_item)

# ============ ADMIN/COORDINATOR ROUTES ============

@bp.route('/admin/reschedule-requests')
@login_required
@admin_required
def admin_reschedule_requests():
    """Admin view of all reschedule requests"""
    form = RescheduleRequestSearchForm(department_id=current_user.department_id)
    
    # Base query
    query = RescheduleRequest.query
    
    # Department filter for coordinators
    if current_user.role == 'coordinator':
        from app.models.tutor import Tutor
        from app.models.user import User
        query = query.join(Class).join(Tutor).join(User).filter(
            User.department_id == current_user.department_id
        )
    
    # Apply filters
    if request.args.get('status'):
        query = query.filter(RescheduleRequest.status == request.args.get('status'))
    
    if request.args.get('tutor'):
        tutor_id = int(request.args.get('tutor'))
        query = query.join(Class).filter(Class.tutor_id == tutor_id)
    
    if request.args.get('date_from'):
        date_from = datetime.strptime(request.args.get('date_from'), '%Y-%m-%d').date()
        query = query.filter(RescheduleRequest.requested_date >= date_from)
    
    if request.args.get('date_to'):
        date_to = datetime.strptime(request.args.get('date_to'), '%Y-%m-%d').date()
        query = query.filter(RescheduleRequest.requested_date <= date_to)
    
    if request.args.get('search'):
        search_term = f"%{request.args.get('search')}%"
        query = query.filter(RescheduleRequest.reason.ilike(search_term))
    
    # Order by request date (newest first)
    requests = query.order_by(RescheduleRequest.request_date.desc()).all()
    
    # Get pending count for dashboard
    pending_count = RescheduleRequest.query.filter_by(status='pending').count()
    
    return render_template('admin/reschedule_requests.html', 
                         requests=requests, form=form, pending_count=pending_count)

@bp.route('/admin/reschedule-request/<int:request_id>')
@login_required
@admin_required
def view_reschedule_request(request_id):
    """View detailed reschedule request"""
    reschedule_request = RescheduleRequest.query.get_or_404(request_id)
    
    # Check department access for coordinators
    if current_user.role == 'coordinator':
        if reschedule_request.class_item.tutor.user.department_id != current_user.department_id:
            flash('Access denied. You can only view requests from your department.', 'error')
            return redirect(url_for('reschedule.admin_reschedule_requests'))
    
    # Refresh conflict check
    conflicts = reschedule_request.check_conflicts()
    db.session.commit()
    
    form = ReviewRescheduleRequestForm()
    form.request_id.data = request_id
    
    return render_template('admin/reschedule_request_detail.html', 
                         request=reschedule_request, form=form, conflicts=conflicts)

@bp.route('/admin/reschedule-request/<int:request_id>/review', methods=['POST'])
@login_required
@admin_required
def review_reschedule_request(request_id):
    """Review (approve/reject) a reschedule request"""
    reschedule_request = RescheduleRequest.query.get_or_404(request_id)
    form = ReviewRescheduleRequestForm()
    
    # Check department access for coordinators
    if current_user.role == 'coordinator':
        if reschedule_request.class_item.tutor.user.department_id != current_user.department_id:
            flash('Access denied. You can only review requests from your department.', 'error')
            return redirect(url_for('reschedule.admin_reschedule_requests'))
    
    if form.validate_on_submit():
        try:
            action = form.action.data
            notes = form.review_notes.data
            
            if action == 'approve':
                # Check conflicts unless force approve is checked
                if reschedule_request.has_conflicts and not form.force_approve.data:
                    flash('Cannot approve request with conflicts. Use force approve if necessary.', 'error')
                    return redirect(url_for('reschedule.view_reschedule_request', request_id=request_id))
                
                reschedule_request.approve(current_user, notes)
                flash('Reschedule request approved successfully!', 'success')
                
            elif action == 'reject':
                reschedule_request.reject(current_user, notes)
                flash('Reschedule request rejected.', 'info')
            
            return redirect(url_for('reschedule.admin_reschedule_requests'))
            
        except Exception as e:
            db.session.rollback()
            flash('Error processing request. Please try again.', 'error')
            current_app.logger.error(f"Error reviewing reschedule request: {str(e)}")
    
    flash('Invalid form data. Please check your input.', 'error')
    return redirect(url_for('reschedule.view_reschedule_request', request_id=request_id))

@bp.route('/admin/reschedule-request/<int:request_id>/quick-approve', methods=['POST'])
@login_required
@admin_required
def quick_approve_reschedule(request_id):
    """Quick approve reschedule request via AJAX"""
    reschedule_request = RescheduleRequest.query.get_or_404(request_id)
    
    # Check department access for coordinators
    if current_user.role == 'coordinator':
        if reschedule_request.class_item.tutor.user.department_id != current_user.department_id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403
    
    try:
        # Check for conflicts
        conflicts = reschedule_request.check_conflicts()
        
        if conflicts:
            return jsonify({
                'success': False, 
                'error': 'Cannot approve due to conflicts',
                'conflicts': conflicts
            })
        
        reschedule_request.approve(current_user, "Quick approved")
        
        return jsonify({
            'success': True,
            'message': 'Reschedule request approved successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# ============ API ROUTES ============

@bp.route('/api/reschedule-request/<int:request_id>/conflicts')
@login_required
@admin_required
def api_check_conflicts(request_id):
    """API endpoint to check conflicts for a reschedule request"""
    reschedule_request = RescheduleRequest.query.get_or_404(request_id)
    
    try:
        conflicts = reschedule_request.check_conflicts()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'has_conflicts': reschedule_request.has_conflicts,
            'conflicts': conflicts
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/reschedule-requests/pending-count')
@login_required
@admin_required
def api_pending_count():
    """Get count of pending reschedule requests"""
    try:
        query = RescheduleRequest.query.filter_by(status='pending')
        
        # Filter by department for coordinators
        if current_user.role == 'coordinator':
            from app.models.tutor import Tutor
            from app.models.user import User
            query = query.join(Class).join(Tutor).join(User).filter(
                User.department_id == current_user.department_id
            )
        
        count = query.count()
        
        return jsonify({
            'success': True,
            'pending_count': count
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ============ QUICK RESCHEDULE (ADMIN ONLY) ============

@bp.route('/admin/class/<int:class_id>/quick-reschedule', methods=['GET', 'POST'])
@login_required
@admin_required
def quick_reschedule_class(class_id):
    """Quick reschedule class without request workflow"""
    class_item = Class.query.get_or_404(class_id)
    
    # Check department access for coordinators
    if current_user.role == 'coordinator':
        if class_item.tutor.user.department_id != current_user.department_id:
            flash('Access denied. You can only reschedule classes from your department.', 'error')
            return redirect(url_for('admin.classes'))
    
    form = QuickRescheduleForm()
    form.class_id.data = class_id
    
    if form.validate_on_submit():
        try:
            # Check for conflicts
            conflict_exists, conflicting_class = Class.check_time_conflict(
                class_item.tutor_id,
                form.new_date.data,
                form.new_time.data,
                class_item.duration,
                exclude_class_id=class_id
            )
            
            if conflict_exists:
                flash(f'Time conflict detected with another class at {conflicting_class.scheduled_time}.', 'error')
                return render_template('admin/quick_reschedule.html', form=form, class_item=class_item)
            
            # Update class
            class_item.scheduled_date = form.new_date.data
            class_item.scheduled_time = form.new_time.data
            class_item.calculate_end_time()
            class_item.updated_at = datetime.utcnow()
            
            # Add admin note
            note = f"Rescheduled by {current_user.full_name}: {form.reason.data}"
            if class_item.admin_notes:
                class_item.admin_notes += f"\n{note}"
            else:
                class_item.admin_notes = note
            
            db.session.commit()
            
            flash('Class rescheduled successfully!', 'success')
            return redirect(url_for('admin.class_details', class_id=class_id))
            
        except Exception as e:
            db.session.rollback()
            flash('Error rescheduling class. Please try again.', 'error')
            current_app.logger.error(f"Error in quick reschedule: {str(e)}")
    
    return render_template('admin/quick_reschedule.html', form=form, class_item=class_item)

# ADD THESE ENDPOINTS TO app/routes/reschedule.py

@bp.route('/api/reschedule-requests/recent')
@login_required
@admin_required
def api_recent_reschedule_requests():
    """Get recent reschedule requests for dashboard"""
    try:
        limit = request.args.get('limit', 5, type=int)
        
        query = RescheduleRequest.query
        
        # Filter by department for coordinators
        if current_user.role == 'coordinator':
            from app.models.tutor import Tutor
            from app.models.user import User
            query = query.join(Class).join(Tutor).join(User).filter(
                User.department_id == current_user.department_id
            )
        
        requests = query.order_by(RescheduleRequest.request_date.desc()).limit(limit).all()
        
        request_data = []
        for req in requests:
            request_data.append({
                'id': req.id,
                'class_subject': req.class_item.subject,
                'tutor_name': req.class_item.tutor.user.full_name,
                'original_date': req.original_date.strftime('%d %b'),
                'requested_date': req.requested_date.strftime('%d %b'),
                'status': req.status,
                'has_conflicts': req.has_conflicts,
                'request_date': req.request_date.strftime('%d %b %Y')
            })
        
        return jsonify({
            'success': True,
            'requests': request_data
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/tutor/reschedule-stats')
@login_required
@tutor_required
def api_tutor_reschedule_stats():
    """Get tutor's reschedule request statistics"""
    try:
        tutor = Tutor.query.filter_by(user_id=current_user.id).first()
        if not tutor:
            return jsonify({'success': False, 'error': 'Tutor profile not found'}), 404
        
        requests = RescheduleRequest.get_requests_for_tutor(tutor.id)
        
        stats = {
            'total': len(requests),
            'pending': len([r for r in requests if r.status == 'pending']),
            'approved': len([r for r in requests if r.status == 'approved']),
            'rejected': len([r for r in requests if r.status == 'rejected'])
        }
        
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/tutor/recent-requests')
@login_required
@tutor_required
def api_tutor_recent_requests():
    """Get tutor's recent reschedule requests"""
    try:
        limit = request.args.get('limit', 3, type=int)
        
        tutor = Tutor.query.filter_by(user_id=current_user.id).first()
        if not tutor:
            return jsonify({'success': False, 'error': 'Tutor profile not found'}), 404
        
        requests = RescheduleRequest.get_requests_for_tutor(tutor.id)[:limit]
        
        request_data = []
        for req in requests:
            request_data.append({
                'id': req.id,
                'class_subject': req.class_item.subject,
                'original_date': req.original_date.strftime('%d %b'),
                'requested_date': req.requested_date.strftime('%d %b'),
                'status': req.status,
                'has_conflicts': req.has_conflicts,
                'request_date': req.request_date.strftime('%d %b %Y')
            })
        
        return jsonify({
            'success': True,
            'requests': request_data
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/reschedule-request/<int:request_id>/notification-status')
@login_required
@admin_required
def api_reschedule_notification_status(request_id):
    """Check if notifications were sent for a reschedule request"""
    try:
        reschedule_request = RescheduleRequest.query.get_or_404(request_id)
        
        # This would integrate with your notification system
        # For now, return mock data
        return jsonify({
            'success': True,
            'notifications': {
                'tutor_notified': True,
                'students_notified': True,
                'admin_notified': True,
                'last_notification_sent': datetime.utcnow().isoformat()
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# BULK OPERATIONS ENDPOINTS

@bp.route('/api/reschedule-requests/bulk-approve', methods=['POST'])
@login_required
@admin_required
def api_bulk_approve_reschedule_requests():
    """Bulk approve reschedule requests"""
    try:
        data = request.get_json()
        request_ids = data.get('request_ids', [])
        notes = data.get('notes', 'Bulk approved')
        force_approve = data.get('force_approve', False)
        
        if not request_ids:
            return jsonify({'success': False, 'error': 'No requests selected'}), 400
        
        approved_count = 0
        failed_count = 0
        conflicts = []
        
        for request_id in request_ids:
            reschedule_request = RescheduleRequest.query.get(request_id)
            if not reschedule_request:
                failed_count += 1
                continue
            
            # Check department access for coordinators
            if current_user.role == 'coordinator':
                if reschedule_request.class_item.tutor.user.department_id != current_user.department_id:
                    failed_count += 1
                    continue
            
            # Check conflicts unless force approve
            if reschedule_request.has_conflicts and not force_approve:
                conflicts.append({
                    'request_id': request_id,
                    'conflicts': reschedule_request.get_conflicts()
                })
                failed_count += 1
                continue
            
            try:
                reschedule_request.approve(current_user, notes)
                approved_count += 1
            except Exception as e:
                failed_count += 1
        
        return jsonify({
            'success': True,
            'approved_count': approved_count,
            'failed_count': failed_count,
            'conflicts': conflicts
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/reschedule-requests/bulk-reject', methods=['POST'])
@login_required
@admin_required
def api_bulk_reject_reschedule_requests():
    """Bulk reject reschedule requests"""
    try:
        data = request.get_json()
        request_ids = data.get('request_ids', [])
        notes = data.get('notes', 'Bulk rejected')
        
        if not request_ids:
            return jsonify({'success': False, 'error': 'No requests selected'}), 400
        
        rejected_count = 0
        failed_count = 0
        
        for request_id in request_ids:
            reschedule_request = RescheduleRequest.query.get(request_id)
            if not reschedule_request:
                failed_count += 1
                continue
            
            # Check department access for coordinators
            if current_user.role == 'coordinator':
                if reschedule_request.class_item.tutor.user.department_id != current_user.department_id:
                    failed_count += 1
                    continue
            
            try:
                reschedule_request.reject(current_user, notes)
                rejected_count += 1
            except Exception as e:
                failed_count += 1
        
        return jsonify({
            'success': True,
            'rejected_count': rejected_count,
            'failed_count': failed_count
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# SEARCH AND FILTER ENDPOINTS

@bp.route('/api/reschedule-requests/search')
@login_required
@admin_required
def api_search_reschedule_requests():
    """Search reschedule requests with filters"""
    try:
        # Get search parameters
        status = request.args.get('status')
        tutor_id = request.args.get('tutor_id', type=int)
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        search_term = request.args.get('search')
        has_conflicts = request.args.get('has_conflicts')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        # Build query
        query = RescheduleRequest.query
        
        # Department filter for coordinators
        if current_user.role == 'coordinator':
            from app.models.tutor import Tutor
            from app.models.user import User
            query = query.join(Class).join(Tutor).join(User).filter(
                User.department_id == current_user.department_id
            )
        
        # Apply filters
        if status:
            query = query.filter(RescheduleRequest.status == status)
        
        if tutor_id:
            query = query.join(Class).filter(Class.tutor_id == tutor_id)
        
        if date_from:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            query = query.filter(RescheduleRequest.requested_date >= date_from_obj)
        
        if date_to:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            query = query.filter(RescheduleRequest.requested_date <= date_to_obj)
        
        if search_term:
            search_pattern = f"%{search_term}%"
            query = query.filter(RescheduleRequest.reason.ilike(search_pattern))
        
        if has_conflicts is not None:
            query = query.filter(RescheduleRequest.has_conflicts == (has_conflicts.lower() == 'true'))
        
        # Paginate results
        pagination = query.order_by(RescheduleRequest.request_date.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        requests_data = [req.to_dict() for req in pagination.items]
        
        return jsonify({
            'success': True,
            'requests': requests_data,
            'pagination': {
                'page': pagination.page,
                'pages': pagination.pages,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'has_next': pagination.has_next,
                'has_prev': pagination.has_prev
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500