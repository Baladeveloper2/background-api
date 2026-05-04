from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from typing import Optional, List
import io
import logging
import os
import uuid
from anyio import to_thread
from functools import partial
from .auth_routes import get_current_user, limiter
from .models import User
from . import aws_utils

router = APIRouter(prefix="/media", tags=["media"])

@router.post("/public-upload")
@limiter.limit("50/minute")
async def public_upload_file(
    request: Request,
    file: UploadFile = File(...)
):
    """Exclusively S3 public upload for candidates."""
    if not aws_utils.s3_client:
        raise HTTPException(status_code=503, detail="S3 Storage service unavailable")
    
    try:
        ext = os.path.splitext(file.filename)[1].lower()
        allowed_exts = ['.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png', '.webp', '.gif']
        if ext not in allowed_exts:
            raise HTTPException(status_code=400, detail=f"Unsupported file format ({ext})")

        file_data = await file.read()
        unique_filename = f"public_documents/{uuid.uuid4()}_{file.filename}"
        
        await to_thread.run_sync(
            partial(
                aws_utils.s3_client.put_object,
                Bucket=aws_utils.aws_bucket,
                Key=unique_filename,
                Body=file_data,
                ContentType=file.content_type
            )
        )
        
        return {
            "url": f"https://{aws_utils.aws_bucket}.s3.{aws_utils.aws_region}.amazonaws.com/{unique_filename}",
            "public_id": unique_filename,
            "path": unique_filename,
            "original_filename": file.filename,
            "mimetype": file.content_type,
            "size": len(file_data),
            "storage_provider": "s3"
        }
    except Exception as e:
        logging.error(f"S3 Public Upload error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"S3 Upload failed: {str(e)}")

@router.post("/upload")
@limiter.limit("100/minute")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """Exclusively S3 upload for authenticated users."""
    if not aws_utils.s3_client:
        raise HTTPException(status_code=503, detail="S3 Storage service unavailable")

    try:
        ext = os.path.splitext(file.filename)[1].lower()
        allowed_exts = ['.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png', '.webp', '.gif']
        if ext not in allowed_exts:
            raise HTTPException(status_code=400, detail=f"Unsupported file format ({ext})")

        file_data = await file.read()
        unique_filename = f"bgv_documents/{uuid.uuid4()}_{file.filename}"
        
        await to_thread.run_sync(
            partial(
                aws_utils.s3_client.put_object,
                Bucket=aws_utils.aws_bucket,
                Key=unique_filename,
                Body=file_data,
                ContentType=file.content_type
            )
        )
        
        return {
            "url": f"https://{aws_utils.aws_bucket}.s3.{aws_utils.aws_region}.amazonaws.com/{unique_filename}",
            "public_id": unique_filename,
            "path": unique_filename,
            "original_filename": file.filename,
            "mimetype": file.content_type,
            "size": len(file_data),
            "storage_provider": "s3"
        }
    except Exception as e:
        logging.error(f"S3 Upload error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"S3 Upload failed: {str(e)}")

@router.get("/public-get-url")
async def public_get_signed_url(
    public_id: str,
    original_filename: Optional[str] = None,
    download: bool = False
):
    """Get S3 presigned URL for public docs."""
    try:
        url = await aws_utils.generate_presigned_url(
            public_id, 
            as_attachment=download, 
            filename=original_filename
        )
        return {"url": url}
    except Exception as e:
        logging.error(f"S3 Public Get URL error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate URL")

@router.get("/get-url")
async def get_signed_url(
    public_id: str,
    original_filename: Optional[str] = None,
    download: bool = False,
    current_user: User = Depends(get_current_user)
):
    """Get S3 presigned URL for internal docs."""
    try:
        url = await aws_utils.generate_presigned_url(
            public_id, 
            as_attachment=download, 
            filename=original_filename
        )
        return {"url": url}
    except Exception as e:
        logging.error(f"S3 Get URL error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate URL")

@router.get("/local/{path:path}")
async def get_local_media(path: str):
    file_path = os.path.join("uploads", path)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Local file not found")
    import mimetypes
    mime_type, _ = mimetypes.guess_type(file_path)
    return FileResponse(file_path, media_type=mime_type or "application/octet-stream")
