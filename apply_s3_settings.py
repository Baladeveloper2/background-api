import boto3
import json
import os
from dotenv import load_dotenv

load_dotenv()

s3 = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_REGION')
)
bucket_name = os.getenv('AWS_S3_BUCKET')

try:
    print(f"Removing Public Access Block for {bucket_name}...")
    s3.delete_public_access_block(Bucket=bucket_name)
    print("Public access block removed.")
except Exception as e:
    print("Warning removing public access block:", e)

try:
    print(f"Applying Bucket Policy to {bucket_name}...")
    bucket_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "PublicReadGetObject",
                "Effect": "Allow",
                "Principal": "*",
                "Action": "s3:GetObject",
                "Resource": f"arn:aws:s3:::{bucket_name}/*"
            }
        ]
    }
    s3.put_bucket_policy(Bucket=bucket_name, Policy=json.dumps(bucket_policy))
    print("Bucket Policy applied successfully.")
except Exception as e:
    print("Error applying bucket policy:", e)

try:
    print(f"Applying CORS configuration to {bucket_name}...")
    cors_configuration = {
        'CORSRules': [{
            'AllowedHeaders': ['*'],
            'AllowedMethods': ['GET', 'HEAD', 'PUT', 'POST'],
            'AllowedOrigins': ['*'],
            'ExposeHeaders': []
        }]
    }
    s3.put_bucket_cors(Bucket=bucket_name, CORSConfiguration=cors_configuration)
    print("CORS configuration applied successfully.")
except Exception as e:
    print("Error applying CORS:", e)

print("Finished applying S3 settings.")
