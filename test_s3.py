import boto3
import os
from dotenv import load_dotenv

load_dotenv()

def test_s3():
    ak = os.getenv('AWS_ACCESS_KEY_ID')
    sk = os.getenv('AWS_SECRET_ACCESS_KEY')
    reg = os.getenv('AWS_REGION', 'ap-south-1')
    buck = os.getenv('AWS_S3_BUCKET')
    
    print(f"Testing S3: {buck} in {reg}")
    try:
        s3 = boto3.client(
            's3',
            aws_access_key_id=ak,
            aws_secret_access_key=sk,
            region_name=reg
        )
        # Try to list objects (head bucket is better but list is more common check)
        s3.list_objects_v2(Bucket=buck, MaxKeys=1)
        print("S3 CONNECTION SUCCESSFUL!")
    except Exception as e:
        print(f"S3 CONNECTION FAILED: {str(e)}")

if __name__ == "__main__":
    test_s3()
