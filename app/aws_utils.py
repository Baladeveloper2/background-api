import os
import boto3
from botocore.config import Config
from dotenv import load_dotenv

load_dotenv(override=True)

# AWS Configuration
aws_access_key = os.getenv('AWS_ACCESS_KEY_ID', '').strip()
aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY', '').strip()
aws_region = os.getenv('AWS_REGION', 'us-east-1').strip()
aws_bucket = os.getenv('AWS_S3_BUCKET', '').strip()

def get_s3_client():
    if not (aws_access_key and aws_secret_key):
        return None
    try:
        client = boto3.client(
            's3',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name=aws_region,
            config=Config(signature_version='s3v4', retries={'max_attempts': 3})
        )
        return client
    except Exception:
        return None

s3_client = get_s3_client()

async def upload_to_s3(file, path):
    if not s3_client:
        # Fallback to local storage if needed, but here we assume S3 is required
        os.makedirs(os.path.dirname(f"uploads/{path}"), exist_ok=True)
        with open(f"uploads/{path}", "wb") as f:
            content = await file.read()
            f.write(content)
        return f"uploads/{path}"
        
    content = await file.read()
    s3_client.put_object(
        Bucket=aws_bucket,
        Key=path,
        Body=content,
        ContentType=file.content_type
    )
    return path

async def generate_presigned_url(path, as_attachment=False, filename=None):
    if not s3_client:
        return f"/api/v1/media/local/{path}" # Fallback
        
    params = {'Bucket': aws_bucket, 'Key': path}
    if as_attachment:
        final_filename = filename or os.path.basename(path)
        # Ensure filename is properly quoted for Content-Disposition
        from urllib.parse import quote
        safe_filename = quote(final_filename)
        params['ResponseContentDisposition'] = f"attachment; filename*=UTF-8''{safe_filename}"
        
    return s3_client.generate_presigned_url(
        'get_object',
        Params=params,
        ExpiresIn=3600
    )
