import boto3
import uuid
from werkzeug.utils import secure_filename
from flask import current_app

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def upload_file_to_s3(file, folder='uploads'):
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex}_{filename}"

        try:
            s3 = boto3.client(
                "s3",
                region_name=current_app.config['S3_REGION'],
                aws_access_key_id=current_app.config['S3_ACCESS_KEY'],
                aws_secret_access_key=current_app.config['S3_SECRET_KEY']
            )

            s3.upload_fileobj(
                file,
                current_app.config['S3_BUCKET'],
                f"{folder}/{unique_filename}",
                
            )

            file_url = f"{current_app.config['S3_URL']}/{folder}/{unique_filename}"
            return file_url

        except Exception as e:
            current_app.logger.error(f"S3 Upload Failed: {e}")
            return None

    return None
