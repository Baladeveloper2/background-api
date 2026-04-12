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
            endpoint_url=f"https://s3.{aws_region}.amazonaws.com",
            config=Config(signature_version='s3v4')
        )
        return client
    except Exception:
        return None

s3_client = get_s3_client()
