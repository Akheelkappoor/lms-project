import boto3
import uuid
from werkzeug.utils import secure_filename
from flask import current_app

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def upload_file_to_s3(file, folder='uploads'):
    print(f"=== S3 UPLOAD DEBUG ===")
    print(f"File: {file}")
    print(f"File type: {type(file)}")
    print(f"Filename: {file.filename if file else 'No file'}")

    print(f"=== CONFIG VALUES IN HELPER ===")
    print(f"S3_BUCKET from config: {current_app.config.get('S3_BUCKET')}")
    print(f"S3_REGION from config: {current_app.config.get('S3_REGION')}")
    print(f"S3_ACCESS_KEY from config: {current_app.config.get('S3_ACCESS_KEY')}")
    print(f"S3_SECRET_KEY from config: {current_app.config.get('S3_SECRET_KEY')}")
    print(f"All S3 keys in config: {[k for k in current_app.config.keys() if 'S3' in k]}")
    print("================================")
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        print(f"Secure filename: {filename}")
        print(f"Unique filename: {unique_filename}")

        try:
            # Reset file pointer to beginning
            file.seek(0)
            print("File pointer reset to beginning")
            
            # Check if file has content
            file_content = file.read()
            print(f"File content length: {len(file_content) if file_content else 'No content'}")
            
            # Reset pointer again after reading
            file.seek(0)
            print("File pointer reset again")
            
            print("Creating S3 client...")
            s3 = boto3.client(
                "s3",
                region_name=current_app.config['S3_REGION'],
                aws_access_key_id=current_app.config['S3_ACCESS_KEY'],
                aws_secret_access_key=current_app.config['S3_SECRET_KEY']
            )
            print("S3 client created successfully")
            
            print(f"Uploading to bucket: {current_app.config['S3_BUCKET']}")
            print(f"Upload path: {folder}/{unique_filename}")
            
            s3.upload_fileobj(
                file,
                current_app.config['S3_BUCKET'],
                f"{folder}/{unique_filename}"
            )
            print("Upload successful!")

            file_url = f"{current_app.config['S3_URL']}/{folder}/{unique_filename}"
            print(f"File URL: {file_url}")
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