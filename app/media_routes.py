from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from fastapi.responses import StreamingResponse
from typing import Optional
import io
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
from fastapi import Request
from .auth_routes import limiter
from anyio import to_thread
from .ocr_utils import get_scanner

router = APIRouter(prefix="/media", tags=["media"])
print("--- MEDIA ROUTES RELOADED (ASYNC VERSION) ---")

load_dotenv(override=True)

from .aws_utils import s3_client, aws_bucket, aws_region

# Cloudinary fallback
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
@limiter.limit("100/minute")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    try:
        ext = os.path.splitext(file.filename)[1].lower()
        allowed_exts = ['.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png', '.webp', '.gif']
        if ext not in allowed_exts:
            raise HTTPException(status_code=400, detail=f"Unsupported file format ({ext})")

        resource_type = "image" if ext in ['.pdf', '.jpg', '.jpeg', '.png'] else "raw"
        
        file_data = await file.read()
        file_size = len(file_data)
        base_filename = "".join([c if c.isalnum() or c in ['-', '_'] else '_' for c in os.path.splitext(file.filename)[0]])
        
        # S3 Upload logic
        if s3_client and aws_bucket:
            unique_filename = f"bgv_documents/{uuid.uuid4()}_{file.filename}"
            from io import BytesIO
            
            print(f"DEBUG: Starting S3 upload to {aws_bucket}/{unique_filename}")
            await to_thread.run_sync(
                s3_client.upload_fileobj,
                BytesIO(file_data),
                aws_bucket,
                unique_filename,
                {'ContentType': file.content_type}
            )
            print(f"DEBUG: S3 upload successful: {unique_filename}")
            
            return {
                "url": f"https://{aws_bucket}.s3.{aws_region}.amazonaws.com/{unique_filename}",
                "public_id": unique_filename,
                "path": unique_filename,
                "resource_type": resource_type,
                "storage_provider": "s3",
                "original_filename": file.filename,
                "mimetype": file.content_type,
                "size": file_size
            }

        # Cloudinary Fallback
        upload_result = await to_thread.run_sync(
            cloudinary.uploader.upload,
            file_data,
            resource_type=resource_type,
            folder="bgv_documents",
            public_id=f"{base_filename}_{os.urandom(2).hex()}"
        )

        return {
            "url": upload_result.get("secure_url"),
            "public_id": upload_result.get("public_id"),
            "path": upload_result.get("public_id"),
            "resource_type": upload_result.get("resource_type"),
            "storage_provider": "cloudinary",
            "original_filename": file.filename,
            "mimetype": file.content_type,
            "size": file_size
        }
    except Exception as e:
        provider = "S3" if (s3_client and aws_bucket) else "Cloudinary"
        logging.error(f"{provider} upload error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload file to {provider}: {str(e)}"
        )

@router.get("/get-url")
async def get_signed_url(
    public_id: str,
    resource_type: str = "image",
    original_filename: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    try:
        # S3 Presigned URL
        is_s3_path = public_id.startswith('bgv_documents/') or public_id.startswith('bqv_documents/')
        if s3_client and aws_bucket and is_s3_path:
            params = {'Bucket': aws_bucket, 'Key': public_id}
            if original_filename:
                # Sanitize filename
                safe_name = "".join([c if c.isalnum() or c in ['-', '_', '.'] else '_' for c in original_filename])
                params['ResponseContentDisposition'] = f'inline; filename="{safe_name}"'
            
            url = await to_thread.run_sync(
                s3_client.generate_presigned_url,
                'get_object',
                params,
                3600
            )
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
        return {"url": f"https://res.cloudinary.com/dfrfq0ch8/{resource_type}/upload/{public_id}"}

@router.get("/proxy")
async def proxy_media(
    public_id: str,
    current_user: User = Depends(get_current_user)
):
    try:
        if s3_client and aws_bucket:
            # Run both get_object and read() in the thread pool to avoid blocking
            def fetch_s3_data():
                resp = s3_client.get_object(Bucket=aws_bucket, Key=public_id)
                return resp['Body'].read(), resp.get('ContentType', 'image/png')
            
            data, content_type = await to_thread.run_sync(fetch_s3_data)
            
            return StreamingResponse(
                io.BytesIO(data),
                media_type=content_type,
                headers={
                    "Cache-Control": "max-age=3600",
                    "Access-Control-Allow-Origin": "*"
                }
            )
        
        # Fallback for Cloudinary (usually doesn't need proxying, but for consistency)
        import requests
        url = f"https://res.cloudinary.com/dfrfq0ch8/image/upload/{public_id}"
        resp = requests.get(url)
        return StreamingResponse(io.BytesIO(resp.content), media_type="image/png")

    except Exception as e:
        logging.error(f"Proxy error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to proxy media")

@router.post("/extract")
async def extract_ocr_data(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    try:
        scanner = get_scanner()
        file_data = await file.read()
        
        # 1. Extract raw text
        text = await to_thread.run_sync(scanner.extract_text, file_data)
        
        # 2. Parse into structured data
        parsed = await to_thread.run_sync(scanner.parse_id, text)
        
        return {
            "success": True,
            "raw_text": text,
            "extracted_data": parsed
        }
    except Exception as e:
        logging.error(f"OCR Extraction Error: {str(e)}")
        return {
            "success": False, 
            "message": f"Failed to extract text: {str(e)}"
        }
