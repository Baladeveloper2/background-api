import boto3
import os
from dotenv import load_dotenv

# Load env from backend folder
env_path = r"d:\project\backend\.env"
load_dotenv(env_path)

def test_upload():
    aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    aws_region = os.getenv('AWS_REGION', 'us-east-1')
    aws_bucket = os.getenv('AWS_S3_BUCKET')
    
    image_path = r"d:\project\frontend\public\17973908.jpg"
    
    print(f"Testing upload... Bucket: {aws_bucket}, Region: {aws_region}")
    
    s3_client = boto3.client(
        's3',
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key,
        region_name=aws_region
    )
    
    try:
        with open(image_path, 'rb') as f:
            s3_client.upload_fileobj(
                f,
                aws_bucket,
                "test_uploads/17973908.jpg",
                ExtraArgs={'ContentType': 'image/jpeg'}
            )
        
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': aws_bucket, 'Key': "test_uploads/17973908.jpg"},
            ExpiresIn=3600
        )
        print("URL=" + str(url))
        print("STATUS=SUCCESS")
        
    except Exception as e:
        print("STATUS=ERROR")
        print("MESSAGE=" + str(e))

if __name__ == "__main__":
    test_upload()
