from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
import logging
import cloudinary
import cloudinary.uploader
import cloudinary.utils
import boto3
from botocore.exceptions import ClientError
from .auth_routes import get_current_user
from .models import User
import os
import uuid
from dotenv import load_dotenv

router = APIRouter(prefix="/media", tags=["media"])
print("--- MEDIA ROUTES RELOADED (CLEAN VERSION) ---")

# Load environment variables
load_dotenv(override=True)

from .aws_utils import s3_client, aws_bucket, aws_region


# Initializing Cloudinary as fallback
cloudinary_url = os.getenv('CLOUDINARY_URL')
if cloudinary_url:
    cloudinary.config(cloudinary_url=cloudinary_url, secure=True)
else:
    cloudinary.config(
        cloud_name="dfrfq0ch8",
        api_key="257176576991427",
        api_secret="L0Dsbb-q8rIUV-nAznSlVTpy5DY",
        secure=True
    )

@router.post("/upload")
def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    try:
        # Validate file extension
        ext = os.path.splitext(file.filename)[1].lower()
        allowed_exts = ['.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png', '.webp', '.gif']
        if ext not in allowed_exts:
            raise HTTPException(status_code=400, detail=f"Unsupported file format ({ext})")

        # Determine resource type
        if ext in ['.pdf', '.jpg', '.jpeg', '.png']:
            resource_type = "image"
        else:
            resource_type = "raw"
        
        file.file.seek(0)
        base_filename = "".join([c if c.isalnum() or c in ['-', '_'] else '_' for c in os.path.splitext(file.filename)[0]])
        
        # S3 Upload logic
        if s3_client and aws_bucket:
            unique_filename = f"bgv_documents/{uuid.uuid4()}_{file.filename}"
            s3_client.upload_fileobj(
                file.file,
                aws_bucket,
                unique_filename,
                ExtraArgs={'ContentType': file.content_type}
            )
            return {
                "url": f"https://{aws_bucket}.s3.{aws_region}.amazonaws.com/{unique_filename}",
                "public_id": unique_filename,
                "resource_type": resource_type,
                "storage_provider": "s3",
                "original_filename": file.filename
            }

        # Cloudinary Fallback
        upload_result = cloudinary.uploader.upload(
            file.file,
            resource_type=resource_type,
            folder="bgv_documents",
            public_id=f"{base_filename}_{os.urandom(2).hex()}"
        )

        return {
            "url": upload_result.get("secure_url"),
            "public_id": upload_result.get("public_id"),
            "resource_type": upload_result.get("resource_type"),
            "storage_provider": "cloudinary",
            "original_filename": file.filename
        }
    except Exception as e:
        provider = "S3" if (s3_client and aws_bucket) else "Cloudinary"
        logging.error(f"{provider} upload error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload file to {provider}: {str(e)}"
        )

@router.get("/get-url")
def get_signed_url(
    public_id: str,
    resource_type: str = "image",
    current_user: User = Depends(get_current_user)
):
    try:
        # S3 Presigned URL
        if s3_client and aws_bucket and public_id.startswith('bgv_documents/'):
            url = s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': aws_bucket, 'Key': public_id},
                ExpiresIn=3600
            )
            print(f"DEBUG: Generated Signed URL: {url}")
            return {"url": url}

        # Cloudinary Signed URL
        effective_resource_type = resource_type
        if public_id.lower().endswith(('.doc', '.docx')):
             effective_resource_type = "raw"
        elif public_id.lower().endswith(('.pdf', '.jpg', '.png')):
             effective_resource_type = "image"
             
        url, _ = cloudinary.utils.cloudinary_url(
            public_id,
            resource_type=effective_resource_type,
            secure=True,
            sign_url=True
        )
        return {"url": url}
    except Exception as e:
        logging.error(f"Error generating URL: {str(e)}")
        # Simple fallback
        return {"url": f"https://res.cloudinary.com/dfrfq0ch8/{resource_type}/upload/{public_id}"}
