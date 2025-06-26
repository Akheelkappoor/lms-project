import boto3
from botocore.exceptions import ClientError
import os
import uuid
from werkzeug.utils import secure_filename

class FileService:
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
            region_name=os.environ.get('AWS_REGION', 'us-east-1')
        )
        self.bucket_name = os.environ.get('S3_BUCKET')
    
    def upload_file(self, file, folder, user_id):
        """Upload file to S3 and return the URL"""
        try:
            # Generate unique filename
            file_extension = file.filename.rsplit('.', 1)[1].lower()
            unique_filename = f"{str(uuid.uuid4())}.{file_extension}"
            
            # Create S3 key
            s3_key = f"{folder}/{user_id}/{unique_filename}"
            
            # Upload to S3
            self.s3_client.upload_fileobj(
                file,
                self.bucket_name,
                s3_key,
                ExtraArgs={'ContentType': file.content_type}
            )
            
            # Return the S3 URL
            return f"https://{self.bucket_name}.s3.{os.environ.get('AWS_REGION', 'us-east-1')}.amazonaws.com/{s3_key}"
        
        except ClientError as e:
            print(f"File upload failed: {e}")
            return None
    
    def delete_file(self, file_url):
        """Delete file from S3"""
        try:
            # Extract S3 key from URL
            s3_key = file_url.split(f"{self.bucket_name}.s3.")[1].split('.amazonaws.com/')[1]
            
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except ClientError as e:
            print(f"File deletion failed: {e}")
            return False
    
    def generate_presigned_url(self, s3_key, expiration=3600):
        """Generate a presigned URL for file access"""
        try:
            response = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': s3_key},
                ExpiresIn=expiration
            )
            return response
        except ClientError as e:
            print(f"Presigned URL generation failed: {e}")
            return None