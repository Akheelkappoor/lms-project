# app/services/notice_service.py

from datetime import datetime
from flask import current_app
from app import db
from app.models.notice import Notice, NoticeAttachment, NoticeDistribution
from app.models.user import User
from app.models.department import Department
from app.utils.helper import upload_file_to_s3
import os
import secrets
from werkzeug.utils import secure_filename

class NoticeService:
    """Service class for notice operations"""
    
    @staticmethod
    def create_notice(title, content, category, priority, target_type, 
                     created_by, target_departments=None, target_users=None,
                     requires_acknowledgment=False, publish_date=None, 
                     expiry_date=None, attachments=None):
        """Create a new notice"""
        try:
            notice = Notice(
                title=title,
                content=content,
                category=category,
                priority=priority,
                target_type=target_type,
                created_by=created_by,
                requires_acknowledgment=requires_acknowledgment,
                publish_date=publish_date,
                expiry_date=expiry_date
            )
            
            # Set target audiences
            if target_type == 'department' and target_departments:
                notice.set_target_departments(target_departments)
            elif target_type == 'individual' and target_users:
                notice.set_target_users(target_users)
            
            db.session.add(notice)
            db.session.flush()  # Get the notice ID
            
            # Handle file attachments
            if attachments:
                NoticeService._handle_attachments(notice.id, attachments, created_by)
            
            db.session.commit()
            return notice
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating notice: {str(e)}")
            raise e
    
    @staticmethod
    def publish_notice(notice_id, publish_immediately=True):
        """Publish a notice and create distributions"""
        try:
            notice = Notice.query.get(notice_id)
            if not notice:
                raise ValueError("Notice not found")
            
            notice.is_published = True
            if publish_immediately:
                notice.publish_date = datetime.utcnow()
            
            # Create distributions for target audience
            target_users = NoticeService._get_target_users(notice)
            
            for user_id in target_users:
                # Check if distribution already exists
                existing = NoticeDistribution.query.filter_by(
                    notice_id=notice.id, 
                    user_id=user_id
                ).first()
                
                if not existing:
                    distribution = NoticeDistribution(
                        notice_id=notice.id,
                        user_id=user_id
                    )
                    db.session.add(distribution)
            
            db.session.commit()
            return notice
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error publishing notice: {str(e)}")
            raise e
    
    @staticmethod
    def _get_target_users(notice):
        """Get list of target user IDs for a notice"""
        target_users = set()
        
        if notice.target_type == 'all':
            # Get all active users
            users = User.query.filter_by(is_active=True).all()
            target_users.update([u.id for u in users])
            
        elif notice.target_type == 'department':
            # Get users from target departments
            target_depts = notice.get_target_departments()
            if target_depts:
                users = User.query.filter(
                    User.is_active == True,
                    User.department_id.in_(target_depts)
                ).all()
                target_users.update([u.id for u in users])
                
        elif notice.target_type == 'individual':
            # Get specific users
            target_user_ids = notice.get_target_users()
            if target_user_ids:
                # Verify users are active
                users = User.query.filter(
                    User.is_active == True,
                    User.id.in_(target_user_ids)
                ).all()
                target_users.update([u.id for u in users])
        
        return list(target_users)
    
    @staticmethod
    def _handle_attachments(notice_id, attachments, uploaded_by):
        """Handle file attachments for notice"""
        for file in attachments:
            if file and file.filename:
                try:
                    # Generate secure filename
                    original_filename = secure_filename(file.filename)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    random_string = secrets.token_hex(8)
                    file_extension = original_filename.rsplit('.', 1)[1].lower()
                    filename = f"notice_{notice_id}_{timestamp}_{random_string}.{file_extension}"
                    
                    # Upload to S3
                    s3_key = f"notices/attachments/{filename}"
                    s3_url = upload_file_to_s3(file, s3_key)
                    
                    if s3_url:
                        # Create attachment record
                        attachment = NoticeAttachment(
                            notice_id=notice_id,
                            filename=filename,
                            original_filename=original_filename,
                            file_size=NoticeService._get_file_size(file),
                            file_type=file.mimetype or 'application/octet-stream',
                            s3_key=s3_key,
                            s3_bucket=current_app.config.get('S3_BUCKET_NAME'),
                            uploaded_by=uploaded_by
                        )
                        db.session.add(attachment)
                        
                except Exception as e:
                    current_app.logger.error(f"Error uploading attachment: {str(e)}")
                    continue
    
    @staticmethod
    def _get_file_size(file):
        """Get file size in bytes"""
        try:
            file.seek(0, 2)  # Seek to end
            size = file.tell()
            file.seek(0)  # Reset to beginning
            return size
        except:
            return None
    
    @staticmethod
    def get_user_notices(user_id, category=None, read_status=None, 
                        acknowledgment_status=None, search=None):
        """Get notices for a specific user with filtering"""
        query = db.session.query(Notice).join(NoticeDistribution).filter(
            NoticeDistribution.user_id == user_id,
            Notice.is_published == True
        )
        
        # Apply filters
        if category:
            query = query.filter(Notice.category == category)
        
        if search:
            query = query.filter(Notice.title.contains(search))
        
        if read_status == 'unread':
            query = query.filter(NoticeDistribution.is_read == False)
        elif read_status == 'read':
            query = query.filter(NoticeDistribution.is_read == True)
        
        if acknowledgment_status == 'pending':
            query = query.filter(
                Notice.requires_acknowledgment == True,
                NoticeDistribution.is_acknowledged == False
            )
        elif acknowledgment_status == 'acknowledged':
            query = query.filter(NoticeDistribution.is_acknowledged == True)
        
        return query.order_by(Notice.created_at.desc())
    
    @staticmethod
    def mark_notice_read(notice_id, user_id):
        """Mark notice as read for a user"""
        try:
            distribution = NoticeDistribution.query.filter_by(
                notice_id=notice_id,
                user_id=user_id
            ).first()
            
            if distribution:
                distribution.mark_as_read()
                return True
            return False
            
        except Exception as e:
            current_app.logger.error(f"Error marking notice as read: {str(e)}")
            return False
    
    @staticmethod
    def acknowledge_notice(notice_id, user_id):
        """Acknowledge notice for a user"""
        try:
            distribution = NoticeDistribution.query.filter_by(
                notice_id=notice_id,
                user_id=user_id
            ).first()
            
            if distribution:
                distribution.mark_as_acknowledged()
                return True
            return False
            
        except Exception as e:
            current_app.logger.error(f"Error acknowledging notice: {str(e)}")
            return False
    
    @staticmethod
    def get_notice_analytics(notice_id):
        """Get detailed analytics for a notice"""
        notice = Notice.query.get(notice_id)
        if not notice:
            return None
        
        distributions = notice.distributions.all()
        
        analytics = {
            'notice': {
                'id': notice.id,
                'title': notice.title,
                'content': notice.content,
                'category': notice.category,
                'priority': notice.priority,
                'target_type': notice.target_type,
                'requires_acknowledgment': notice.requires_acknowledgment,
                'is_published': notice.is_published,
                'publish_date': notice.publish_date,  # Keep as datetime object
                'expiry_date': notice.expiry_date,  # Keep as datetime object
                'created_at': notice.created_at,  # Keep as datetime object
                'author': notice.author.full_name if notice.author else '',
                'attachments_count': notice.attachments.count(),
                'delivery_stats': notice.get_delivery_stats()
            },
            'total_recipients': len(distributions),
            'delivery_stats': notice.get_delivery_stats(),
            'recipients': []
        }
        
        for dist in distributions:
            recipient_data = {
                'user_id': dist.user_id,
                'user_name': dist.user.full_name if dist.user else 'Unknown',
                'user_role': dist.user.role if dist.user else 'Unknown',
                'department': dist.user.department.name if dist.user and dist.user.department else 'None',
                'delivered_at': dist.delivered_at,  # Keep as datetime object
                'read_at': dist.read_at,  # Keep as datetime object
                'acknowledged_at': dist.acknowledged_at,  # Keep as datetime object
                'is_read': dist.is_read,
                'is_acknowledged': dist.is_acknowledged
            }
            analytics['recipients'].append(recipient_data)
        
        return analytics
    
    @staticmethod
    def get_unread_count(user_id):
        """Get count of unread notices for a user"""
        count = NoticeDistribution.query.filter_by(
            user_id=user_id,
            is_read=False
        ).join(Notice).filter(Notice.is_published == True).count()
        
        return count
    
    @staticmethod
    def get_pending_acknowledgments_count(user_id):
        """Get count of notices requiring acknowledgment for a user"""
        count = NoticeDistribution.query.filter_by(
            user_id=user_id,
            is_acknowledged=False
        ).join(Notice).filter(
            Notice.is_published == True,
            Notice.requires_acknowledgment == True
        ).count()
        
        return count
    
    @staticmethod
    def delete_notice(notice_id):
        """Delete a notice and all related data"""
        try:
            notice = Notice.query.get(notice_id)
            if not notice:
                return False
            
            # Delete from S3 first
            for attachment in notice.attachments:
                try:
                    # Here you would delete from S3
                    # s3_client.delete_object(Bucket=attachment.s3_bucket, Key=attachment.s3_key)
                    pass
                except Exception as e:
                    current_app.logger.error(f"Error deleting S3 file: {str(e)}")
            
            # Delete from database (cascading will handle related records)
            db.session.delete(notice)
            db.session.commit()
            return True
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error deleting notice: {str(e)}")
            return False
    
    @staticmethod
    def update_notice(notice_id, **kwargs):
        """Update notice details"""
        try:
            notice = Notice.query.get(notice_id)
            if not notice:
                return None
            
            # Update allowed fields
            allowed_fields = ['title', 'content', 'category', 'priority', 
                            'target_type', 'requires_acknowledgment', 
                            'publish_date', 'expiry_date']
            
            for field, value in kwargs.items():
                if field in allowed_fields and hasattr(notice, field):
                    setattr(notice, field, value)
            
            # Handle target audiences
            if 'target_departments' in kwargs:
                notice.set_target_departments(kwargs['target_departments'])
            if 'target_users' in kwargs:
                notice.set_target_users(kwargs['target_users'])
            
            notice.updated_at = datetime.utcnow()
            db.session.commit()
            return notice
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating notice: {str(e)}")
            return None