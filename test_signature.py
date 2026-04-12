import boto3
import os
import requests
from dotenv import load_dotenv
from botocore.config import Config

env_path = r"d:\project\backend\.env"
load_dotenv(env_path)

def test_signed_url():
    aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    aws_region = os.getenv('AWS_REGION', 'us-east-1')
    aws_bucket = os.getenv('AWS_S3_BUCKET')
    
    if not all([aws_access_key, aws_secret_key, aws_bucket]):
        print("STATUS=ERROR")
        print("MESSAGE=Missing AWS configuration in .env")
        return
    
    # Use the public_id from the user's error
    public_id = "bgv_documents/ee3e8fad-dad3-4533-92eb-451179319c88_BGV_Report_BGV-2026-2381.pdf"
    
    s3_client = boto3.client(
        's3',
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key,
        region_name=aws_region,
        endpoint_url=f"https://s3.{aws_region}.amazonaws.com",
        config=Config(signature_version='s3v4')
    )
    
    try:
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': aws_bucket, 'Key': public_id},
            ExpiresIn=3600
        )
        print("GENERATED URL: " + url)
        
        # Test the URL
        print("Testing URL with requests...")
        r = requests.get(url)
        print(f"HTTP Status: {r.status_code}")
        if r.status_code != 200:
            print("Response Body:")
            print(r.text)
        else:
            print("✅ SUCCESS: URL is valid and accessible!")
            
    except Exception as e:
        print("ERROR: " + str(e))

if __name__ == "__main__":
    test_signed_url()
