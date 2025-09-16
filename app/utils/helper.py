import boto3
import uuid
from werkzeug.utils import secure_filename
from flask import current_app

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def get_organized_s3_path(file_type, category=None, user_id=None, date_obj=None):
    """
    Generate organized S3 folder paths based on file type and metadata
    
    Args:
        file_type: 'video', 'document', 'image', 'profile', etc.
        category: 'attendance', 'demo', 'certificate', 'id_card', etc.
        user_id: User/Tutor/Student ID for user-specific files
        date_obj: Date object for date-based organization
    
    Returns:
        Tuple of (folder_path, filename_prefix)
    """
    base_folder = current_app.config.get('UPLOAD_FOLDER', 'lms')
    
    if date_obj is None:
        from datetime import datetime
        date_obj = datetime.now()
    
    year = date_obj.strftime('%Y')
    month = date_obj.strftime('%m')
    
    # Organize by file type and category
    if file_type == 'video':
        if category == 'attendance':
            folder = f"{base_folder}/videos/attendance/{year}/{month}"
            prefix = f"attendance_video"
        elif category == 'demo':
            folder = f"{base_folder}/videos/demo/{year}/{month}"
            prefix = f"demo_video"
        else:
            folder = f"{base_folder}/videos/general/{year}/{month}"
            prefix = f"video"
    
    elif file_type == 'document':
        if category in ['id_card', 'certificate', 'resume']:
            folder = f"{base_folder}/documents/{category}/{year}"
            prefix = f"{category}"
        else:
            folder = f"{base_folder}/documents/general/{year}/{month}"
            prefix = f"document"
    
    elif file_type == 'profile':
        folder = f"{base_folder}/profiles/{year}"
        prefix = f"profile"
    
    elif file_type == 'notice':
        folder = f"{base_folder}/notices/attachments/{year}/{month}"
        prefix = f"notice_attachment"
    
    else:
        # Default organization
        folder = f"{base_folder}/{file_type}/{year}/{month}"
        prefix = f"{file_type}"
    
    return folder, prefix

def upload_file_to_s3(file, folder='uploads', filename=None):
    
    if file and allowed_file(file.filename):
        # Use custom filename if provided, otherwise generate unique filename
        if filename:
            final_filename = secure_filename(filename)
        else:
            original_filename = secure_filename(file.filename)
            final_filename = f"{uuid.uuid4().hex}_{original_filename}"
        

        try:
            # Reset file pointer to beginning
            file.seek(0)
            
            # Check if file has content
            file_content = file.read()
            
            # Reset pointer again after reading
            file.seek(0)
            
            s3 = boto3.client(
                "s3",
                region_name=current_app.config['S3_REGION'],
                aws_access_key_id=current_app.config['AWS_ACCESS_KEY_ID'],
                aws_secret_access_key=current_app.config['AWS_SECRET_ACCESS_KEY']
            )
            
            s3_key = f"{folder}/{final_filename}"
            
            # Upload with content type detection for videos
            extra_args = {}
            if file.filename.lower().endswith(('.mp4', '.avi', '.mov', '.wmv', '.mkv', '.webm')):
                extra_args['ContentType'] = 'video/mp4'
            
            # Configure upload with timeout and retry settings
            from botocore.config import Config
            config = Config(
                retries={"max_attempts": 3, "mode": "adaptive"},
                read_timeout=3600,  # 1 hour
                connect_timeout=300  # 5 minutes
            )
            
            # Recreate client with config
            s3 = boto3.client(
                "s3",
                region_name=current_app.config['S3_REGION'],
                aws_access_key_id=current_app.config['AWS_ACCESS_KEY_ID'],
                aws_secret_access_key=current_app.config['AWS_SECRET_ACCESS_KEY'],
                config=config
            )
            
            # Add server-side encryption and storage class for videos
            if file.filename.lower().endswith(('.mp4', '.avi', '.mov', '.wmv', '.mkv', '.webm')):
                extra_args.update({
                    'ContentType': 'video/mp4',
                    'ServerSideEncryption': 'AES256',
                    'StorageClass': 'STANDARD_IA'  # Cheaper for infrequent access
                })
            
            s3.upload_fileobj(
                file,
                current_app.config['S3_BUCKET'],
                s3_key,
                ExtraArgs=extra_args,
                # File upload progress callback removed for production
            )

            file_url = f"{current_app.config['S3_URL']}/{s3_key}"
            return file_url

        except Exception as e:
            print(f"=== S3 UPLOAD EXCEPTION ===")
            print(f"Exception type: {type(e)}")
            print(f"Exception message: {str(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            current_app.logger.error(f"S3 Upload Failed: {e}")
            return None
    else:
        print("File validation failed")
        print(f"File exists: {bool(file)}")
        if file:
            print(f"File allowed: {allowed_file(file.filename)}")
        return None

def generate_signed_video_url(video_url, expiration=3600):
    """
    Generate a signed URL for S3 video access
    
    Args:
        video_url: The original S3 URL
        expiration: URL expiration time in seconds (default 1 hour)
    
    Returns:
        Signed URL if successful, original URL if not S3 or on error
    """
    try:
        if not video_url or 's3.amazonaws.com' not in video_url:
            # Not an S3 URL, return original
            return video_url
        
        # Extract bucket and key from S3 URL
        # URL format: https://bucket.s3.region.amazonaws.com/key
        # or https://bucket.s3.amazonaws.com/key
        parts = video_url.replace('https://', '').split('/')
        if len(parts) < 2:
            return video_url
            
        bucket_part = parts[0]
        s3_key = '/'.join(parts[1:])
        
        # Extract bucket name (remove s3 domain parts)
        if '.s3.' in bucket_part:
            bucket = bucket_part.split('.s3.')[0]
        elif '.s3-' in bucket_part:
            bucket = bucket_part.split('.s3-')[0]
        else:
            bucket = bucket_part.split('.')[0]
        
        print(f"Generating signed URL for bucket: {bucket}, key: {s3_key}")
        
        # Create S3 client
        s3_client = boto3.client(
            's3',
            region_name=current_app.config['S3_REGION'],
            aws_access_key_id=current_app.config['AWS_ACCESS_KEY_ID'],
            aws_secret_access_key=current_app.config['AWS_SECRET_ACCESS_KEY']
        )
        
        # Generate signed URL
        signed_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket, 'Key': s3_key},
            ExpiresIn=expiration
        )
        
        print(f"Generated signed URL successfully")
        return signed_url
        
    except Exception as e:
        print(f"Error generating signed URL: {str(e)}")
        current_app.logger.error(f"Signed URL generation failed: {e}")
        # Return original URL as fallback
        return video_url

def generate_signed_document_url(document_url, expiration=3600):
    """
    Generate presigned URL for document access (similar to video function)
    
    Args:
        document_url: S3 URL of the document
        expiration: URL expiration time in seconds (default 1 hour)
    
    Returns:
        Presigned URL string or original URL if signing fails
    """
    if not document_url or 's3.amazonaws.com' not in document_url:
        return document_url
    
    try:
        from urllib.parse import urlparse
        
        # Parse S3 URL to extract bucket and key
        parsed_url = urlparse(document_url)
        
        # Handle different S3 URL formats
        if '.s3.amazonaws.com' in parsed_url.netloc:
            # Format: https://bucket-name.s3.amazonaws.com/path/file.pdf
            bucket = parsed_url.netloc.split('.s3.amazonaws.com')[0]
            s3_key = parsed_url.path.lstrip('/')
        elif 's3.amazonaws.com' in parsed_url.netloc:
            # Format: https://s3.amazonaws.com/bucket-name/path/file.pdf
            path_parts = parsed_url.path.lstrip('/').split('/', 1)
            bucket = path_parts[0]
            s3_key = path_parts[1] if len(path_parts) > 1 else ''
        else:
            # Regional format: https://bucket-name.s3.region.amazonaws.com/path/file.pdf
            bucket_part = parsed_url.netloc.split('.')[0]
            bucket = bucket_part
            s3_key = parsed_url.path.lstrip('/')
        
        print(f"Generating signed document URL for bucket: {bucket}, key: {s3_key}")
        
        # Create S3 client using your config variables
        s3_client = boto3.client(
            's3',
            region_name=current_app.config.get('S3_REGION', 'ap-south-1'),
            aws_access_key_id=current_app.config.get('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=current_app.config.get('AWS_SECRET_ACCESS_KEY')
        )
        
        # Generate presigned URL
        signed_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket, 
                'Key': s3_key,
                'ResponseContentDisposition': 'inline'  # View in browser, not download
            },
            ExpiresIn=expiration
        )
        
        print(f"Generated signed document URL successfully")
        return signed_url
        
    except Exception as e:
        print(f"Error generating signed document URL: {str(e)}")
        current_app.logger.error(f"Document signed URL generation failed: {e}")
        return document_url  # Return original URL as fallback

def is_s3_url(url):
    """Check if URL is an S3 URL"""
    return url and isinstance(url, str) and 's3.amazonaws.com' in url

def upload_organized_file_to_s3(file, file_type, category=None, user_id=None, class_id=None, custom_filename=None):
    """
    Upload file to S3 with organized folder structure and meaningful filenames
    
    Args:
        file: File object to upload
        file_type: 'video', 'document', 'image', 'profile', etc.
        category: 'attendance', 'demo', 'certificate', 'id_card', etc.
        user_id: User/Tutor/Student ID for user-specific files
        class_id: Class ID for class-related files
        custom_filename: Custom filename (optional)
    
    Returns:
        S3 URL if successful, None if failed
    """
    from datetime import datetime
    
    if not file or not allowed_file(file.filename):
        print(f"File validation failed for organized upload")
        return None
    
    # Get organized folder path
    folder, prefix = get_organized_s3_path(file_type, category, user_id)
    
    # Generate structured filename
    if custom_filename:
        filename = secure_filename(custom_filename)
    else:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        original_filename = secure_filename(file.filename)
        
        # Build filename with relevant IDs
        filename_parts = [prefix]
        
        if class_id:
            filename_parts.append(f"class_{class_id}")
        if user_id:
            filename_parts.append(f"user_{user_id}")
        
        filename_parts.extend([timestamp, original_filename])
        filename = "_".join(filename_parts)
    
    print(f"Organized upload: {file_type}/{category} -> {folder}/{filename}")
    
    return upload_file_to_s3(file, folder=folder, filename=filename)

def get_file_extension(filename):
    """Get file extension safely"""
    if not filename or '.' not in filename:
        return ''
    return filename.rsplit('.', 1)[1].lower()

def is_video_file(filename):
    """Check if file is a video"""
    video_extensions = {'mp4', 'avi', 'mov', 'wmv', 'mkv', 'webm', 'flv', 'm4v'}
    return get_file_extension(filename) in video_extensions

def is_document_file(filename):
    """Check if file is a document"""
    document_extensions = {'pdf', 'doc', 'docx', 'txt', 'rtf', 'odt'}
    return get_file_extension(filename) in document_extensions

def is_image_file(filename):
    """Check if file is an image"""
    image_extensions = {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'webp'}
    return get_file_extension(filename) in image_extensions

def get_file_size_mb(file_path_or_size):
    """Get file size in MB"""
    try:
        if isinstance(file_path_or_size, (int, float)):
            # Size in bytes
            return round(file_path_or_size / (1024 * 1024), 2)
        else:
            # File path
            import os
            size_bytes = os.path.getsize(file_path_or_size)
            return round(size_bytes / (1024 * 1024), 2)
    except:
        return 0

def validate_file_upload(file, max_size_mb=100, allowed_types=None):
    """
    Comprehensive file upload validation
    
    Args:
        file: File object to validate
        max_size_mb: Maximum file size in MB
        allowed_types: List of allowed file types ('video', 'document', 'image')
    
    Returns:
        Dict with 'valid' boolean and 'error' message
    """
    if not file or not file.filename:
        return {'valid': False, 'error': 'No file selected'}
    
    if not allowed_file(file.filename):
        return {'valid': False, 'error': 'File type not allowed'}
    
    # Check file size
    file.seek(0, 2)  # Seek to end
    size_bytes = file.tell()
    file.seek(0)  # Reset to beginning
    
    size_mb = size_bytes / (1024 * 1024)
    if size_mb > max_size_mb:
        return {'valid': False, 'error': f'File size ({size_mb:.1f}MB) exceeds limit ({max_size_mb}MB)'}
    
    # Check file type if specified
    if allowed_types:
        file_valid = False
        if 'video' in allowed_types and is_video_file(file.filename):
            file_valid = True
        elif 'document' in allowed_types and is_document_file(file.filename):
            file_valid = True
        elif 'image' in allowed_types and is_image_file(file.filename):
            file_valid = True
        
        if not file_valid:
            return {'valid': False, 'error': f'File must be one of: {", ".join(allowed_types)}'}
    
    return {'valid': True, 'error': None}