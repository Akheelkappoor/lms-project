# app/routes/notice.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, send_file
from flask_login import login_required, current_user
from datetime import datetime
from app import db
from app.models.notice import Notice, NoticeAttachment, NoticeDistribution
from app.models.user import User
from app.models.department import Department
from app.forms.notice_forms import NoticeForm, NoticeSearchForm, UserNoticeSearchForm, BulkNoticeActionForm
from app.services.notice_service import NoticeService
from app.routes.admin import admin_required
from functools import wraps
import boto3
from botocore.exceptions import ClientError
from app.utils.advanced_permissions import require_permission

bp = Blueprint('notice', __name__)

def notice_management_required(f):
    """Decorator to check notice management permissions"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role not in ['superadmin', 'admin', 'coordinator']:
            flash('Access denied. You do not have permission to manage notices.', 'error')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated_function


# ============ ADMIN NOTICE MANAGEMENT ROUTES ============

@bp.route('/admin/notices')
@login_required
@require_permission('notice_management')
def admin_notices():
    """Admin notice management dashboard"""
    form = NoticeSearchForm()
    
    # Build query
    query = Notice.query
    
    # Apply filters
    if request.args.get('search'):
        search_term = request.args.get('search')
        query = query.filter(Notice.title.contains(search_term))
    
    if request.args.get('category'):
        query = query.filter(Notice.category == request.args.get('category'))
    
    if request.args.get('priority'):
        query = query.filter(Notice.priority == request.args.get('priority'))
    
    if request.args.get('status'):
        status = request.args.get('status')
        if status == 'draft':
            query = query.filter(Notice.is_published == False)
        elif status == 'published':
            query = query.filter(Notice.is_published == True)
        elif status == 'expired':
            query = query.filter(
                Notice.is_published == True,
                Notice.expiry_date < datetime.utcnow()
            )
    
    # Department filter (if coordinator, only show notices they can manage)
    if current_user.role == 'coordinator' and request.args.get('department'):
        dept_id = int(request.args.get('department'))
        if dept_id != current_user.department_id:
            flash('Access denied. You can only view notices for your department.', 'error')
            return redirect(url_for('notice.admin_notices'))
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    notices = query.order_by(Notice.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    # Get statistics
    stats = {
        'total': Notice.query.count(),
        'published': Notice.query.filter_by(is_published=True).count(),
        'draft': Notice.query.filter_by(is_published=False).count(),
        'urgent': Notice.query.filter_by(priority='urgent').count()
    }
    
    return render_template('admin/notices/index.html', 
                         notices=notices, form=form, stats=stats)


@bp.route('/admin/notices/create', methods=['GET', 'POST'])
@login_required
@require_permission('notice_management')
def create_notice():
    """Create new notice"""
    form = NoticeForm()
    
    if form.validate_on_submit():
        try:
            # Determine target audiences based on form data
            target_departments = None
            target_users = None
            
            if form.target_type.data == 'department':
                target_departments = form.target_departments.data
            elif form.target_type.data == 'individual':
                target_users = form.target_users.data
            
            # Create notice
            notice = NoticeService.create_notice(
                title=form.title.data,
                content=form.content.data,
                category=form.category.data,
                priority=form.priority.data,
                target_type=form.target_type.data,
                created_by=current_user.id,
                target_departments=target_departments,
                target_users=target_users,
                requires_acknowledgment=form.requires_acknowledgment.data,
                publish_date=form.publish_date.data,
                expiry_date=form.expiry_date.data,
                attachments=form.attachments.data
            )
            
            # Check if should publish immediately
            if form.publish.data:
                NoticeService.publish_notice(notice.id)
                flash(f'Notice "{notice.title}" created and published successfully!', 'success')
            else:
                flash(f'Notice "{notice.title}" saved as draft!', 'success')
            
            return redirect(url_for('notice.admin_notices'))
            
        except Exception as e:
            flash(f'Error creating notice: {str(e)}', 'error')
    
    return render_template('admin/notices/create.html', form=form)


@bp.route('/admin/notices/<int:notice_id>')
@login_required
@require_permission('notice_management')
def view_notice(notice_id):
    """View notice details and analytics"""
    notice = Notice.query.get_or_404(notice_id)
    
    # Check permissions for coordinators
    if current_user.role == 'coordinator':
        if notice.target_type == 'department':
            target_depts = notice.get_target_departments()
            if current_user.department_id not in target_depts:
                flash('Access denied.', 'error')
                return redirect(url_for('notice.admin_notices'))
    
    # Get analytics
    analytics = NoticeService.get_notice_analytics(notice_id)
    
    return render_template('admin/notices/view.html', 
                         notice=notice, analytics=analytics)


@bp.route('/admin/notices/<int:notice_id>/edit', methods=['GET', 'POST'])
@login_required
@require_permission('notice_management')
def edit_notice(notice_id):
    """Edit notice"""
    notice = Notice.query.get_or_404(notice_id)
    
    # Check permissions
    if current_user.role == 'coordinator' and notice.created_by != current_user.id:
        flash('Access denied. You can only edit notices you created.', 'error')
        return redirect(url_for('notice.admin_notices'))
    
    form = NoticeForm(obj=notice)
    
    if form.validate_on_submit():
        try:
            # Prepare update data
            update_data = {
                'title': form.title.data,
                'content': form.content.data,
                'category': form.category.data,
                'priority': form.priority.data,
                'target_type': form.target_type.data,
                'requires_acknowledgment': form.requires_acknowledgment.data,
                'publish_date': form.publish_date.data,
                'expiry_date': form.expiry_date.data
            }
            
            # Handle target audiences
            if form.target_type.data == 'department':
                update_data['target_departments'] = form.target_departments.data
            elif form.target_type.data == 'individual':
                update_data['target_users'] = form.target_users.data
            
            # Update notice
            updated_notice = NoticeService.update_notice(notice_id, **update_data)
            
            if updated_notice:
                flash(f'Notice "{updated_notice.title}" updated successfully!', 'success')
                return redirect(url_for('notice.view_notice', notice_id=notice_id))
            else:
                flash('Error updating notice.', 'error')
                
        except Exception as e:
            flash(f'Error updating notice: {str(e)}', 'error')
    
    # Pre-populate form fields
    if notice.target_type == 'department':
        form.target_departments.data = notice.get_target_departments()
    elif notice.target_type == 'individual':
        form.target_users.data = notice.get_target_users()
    
    return render_template('admin/notices/edit.html', form=form, notice=notice)


@bp.route('/admin/notices/<int:notice_id>/publish', methods=['POST'])
@login_required
@require_permission('notice_management')
def publish_notice(notice_id):
    """Publish a notice"""
    notice = Notice.query.get_or_404(notice_id)
    
    # Check permissions
    if current_user.role == 'coordinator' and notice.created_by != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        NoticeService.publish_notice(notice_id)
        return jsonify({'success': True, 'message': 'Notice published successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/admin/notices/<int:notice_id>/delete', methods=['POST'])
@login_required
@require_permission('notice_management')
def delete_notice(notice_id):
    """Delete a notice"""
    notice = Notice.query.get_or_404(notice_id)
    
    # Check permissions
    if current_user.role == 'coordinator' and notice.created_by != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        if NoticeService.delete_notice(notice_id):
            flash('Notice deleted successfully.', 'success')
        else:
            flash('Error deleting notice.', 'error')
    except Exception as e:
        flash(f'Error deleting notice: {str(e)}', 'error')
    
    return redirect(url_for('notice.admin_notices'))


# ============ USER NOTICE INBOX ROUTES ============

@bp.route('/notices')
@login_required
def user_notices():
    """User notice inbox"""
    form = UserNoticeSearchForm()
    
    # Get user's notices with filtering
    category = request.args.get('category')
    read_status = request.args.get('read_status')
    acknowledgment_status = request.args.get('acknowledgment_status')
    search = request.args.get('search')
    
    notices_query = NoticeService.get_user_notices(
        user_id=current_user.id,
        category=category,
        read_status=read_status,
        acknowledgment_status=acknowledgment_status,
        search=search
    )
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    notices = notices_query.paginate(page=page, per_page=20, error_out=False)
    
    # Get user's notice statistics
    stats = {
        'total': NoticeDistribution.query.filter_by(user_id=current_user.id).join(Notice).filter(Notice.is_published == True).count(),
        'unread': NoticeService.get_unread_count(current_user.id),
        'pending_acknowledgment': NoticeService.get_pending_acknowledgments_count(current_user.id)
    }
    
    return render_template('notices/inbox.html', 
                         notices=notices, form=form, stats=stats)


@bp.route('/notices/<int:notice_id>')
@login_required
def view_user_notice(notice_id):
    """View specific notice for user"""
    notice = Notice.query.get_or_404(notice_id)
    
    # Check if user can view this notice
    if not notice.can_be_viewed_by(current_user):
        flash('Notice not found or you do not have permission to view it.', 'error')
        return redirect(url_for('notice.user_notices'))
    
    # Get user's distribution record
    distribution = NoticeDistribution.query.filter_by(
        notice_id=notice_id,
        user_id=current_user.id
    ).first()
    
    if not distribution:
        flash('Notice distribution record not found.', 'error')
        return redirect(url_for('notice.user_notices'))
    
    # Mark as read if not already read
    if not distribution.is_read:
        NoticeService.mark_notice_read(notice_id, current_user.id)
        distribution = NoticeDistribution.query.filter_by(
            notice_id=notice_id,
            user_id=current_user.id
        ).first()  # Refresh the record
    
    return render_template('notices/view.html', 
                         notice=notice, distribution=distribution)


@bp.route('/api/notices/<int:notice_id>/acknowledge', methods=['POST'])
@login_required
def acknowledge_notice(notice_id):
    """Acknowledge a notice"""
    try:
        success = NoticeService.acknowledge_notice(notice_id, current_user.id)
        if success:
            return jsonify({'success': True, 'message': 'Notice acknowledged successfully'})
        else:
            return jsonify({'error': 'Error acknowledging notice'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/api/notices/<int:notice_id>/read', methods=['POST'])
@login_required
def mark_notice_read(notice_id):
    """Mark notice as read"""
    try:
        success = NoticeService.mark_notice_read(notice_id, current_user.id)
        if success:
            return jsonify({'success': True, 'message': 'Notice marked as read'})
        else:
            return jsonify({'error': 'Error marking notice as read'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============ FILE DOWNLOAD ROUTES ============

@bp.route('/notices/attachments/<int:attachment_id>/download')
@login_required
def download_attachment(attachment_id):
    """Download notice attachment"""
    attachment = NoticeAttachment.query.get_or_404(attachment_id)
    notice = attachment.notice
    
    # Check if user can access this notice
    if not notice.can_be_viewed_by(current_user):
        flash('Access denied.', 'error')
        return redirect(url_for('notice.user_notices'))
    
    try:
        # Generate S3 presigned URL for download
        s3_client = boto3.client(
            's3',
            aws_access_key_id=current_app.config['AWS_ACCESS_KEY_ID'],
            aws_secret_access_key=current_app.config['AWS_SECRET_ACCESS_KEY'],
            region_name=current_app.config.get('AWS_DEFAULT_REGION', 'us-east-1')
        )
        
        download_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': attachment.s3_bucket,
                'Key': attachment.s3_key,
                'ResponseContentDisposition': f'attachment; filename="{attachment.original_filename}"'
            },
            ExpiresIn=3600  # 1 hour
        )
        
        return redirect(download_url)
        
    except ClientError as e:
        current_app.logger.error(f"Error generating download URL: {str(e)}")
        flash('Error downloading file.', 'error')
        return redirect(url_for('notice.view_user_notice', notice_id=notice.id))


# ============ API ENDPOINTS ============

@bp.route('/api/notices/unread-count')
@login_required
def api_unread_count():
    """Get unread notice count for current user"""
    count = NoticeService.get_unread_count(current_user.id)
    return jsonify({'unread_count': count})


@bp.route('/api/notices/pending-acknowledgments-count')
@login_required
def api_pending_acknowledgments_count():
    """Get pending acknowledgments count for current user"""
    count = NoticeService.get_pending_acknowledgments_count(current_user.id)
    return jsonify({'pending_count': count})


@bp.route('/api/admin/notices/bulk-action', methods=['POST'])
@login_required
@require_permission('notice_management')
def bulk_notice_action():
    """Handle bulk actions on notices"""
    form = BulkNoticeActionForm()
    
    if form.validate_on_submit():
        try:
            action = form.action.data
            notice_ids = [int(x) for x in form.notice_ids.data.split(',') if x.strip()]
            
            if not notice_ids:
                return jsonify({'error': 'No notices selected'}), 400
            
            success_count = 0
            
            for notice_id in notice_ids:
                notice = Notice.query.get(notice_id)
                if not notice:
                    continue
                
                # Check permissions for coordinators
                if current_user.role == 'coordinator' and notice.created_by != current_user.id:
                    continue
                
                if action == 'publish' and not notice.is_published:
                    NoticeService.publish_notice(notice_id)
                    success_count += 1
                elif action == 'unpublish' and notice.is_published:
                    notice.is_published = False
                    db.session.commit()
                    success_count += 1
                elif action == 'delete':
                    if NoticeService.delete_notice(notice_id):
                        success_count += 1
            
            return jsonify({
                'success': True, 
                'message': f'{action.title()} action completed for {success_count} notices'
            })
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    return jsonify({'error': 'Invalid form data'}), 400