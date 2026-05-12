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
from .models import User, DocumentMetadata
from . import aws_utils
from .database import get_async_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import hashlib

router = APIRouter(prefix="/media", tags=["media"])

@router.post("/public-upload")
@limiter.limit("50/minute")
async def public_upload_file(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_db)
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
        
        # Calculate Hash for Fraud Detection
        file_hash = hashlib.sha256(file_data).hexdigest()
        
        # Check for cross-candidate duplication (Fraud Indicator)
        stmt = select(DocumentMetadata).filter(DocumentMetadata.file_hash == file_hash)
        existing = await db.execute(stmt)
        duplicate = existing.scalar_one_or_none()
        
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

        # Store Metadata
        new_meta = DocumentMetadata(
            file_hash=file_hash,
            file_name=file.filename,
            mime_type=file.content_type,
            size=len(file_data)
        )
        db.add(new_meta)
        await db.commit()
        
        return {
            "url": f"https://{aws_utils.aws_bucket}.s3.{aws_utils.aws_region}.amazonaws.com/{unique_filename}",
            "public_id": unique_filename,
            "path": unique_filename,
            "original_filename": file.filename,
            "mimetype": file.content_type,
            "size": len(file_data),
            "storage_provider": "s3",
            "is_duplicate": duplicate is not None,
            "duplicate_info": f"Previously uploaded on {duplicate.created_at.date()}" if duplicate else None
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

class PresignedRequest(BaseModel):
    file_name: str
    content_type: str
    category: Optional[str] = "bgv_documents" # or "public_documents"

@router.post("/request-presigned-upload")
async def get_presigned_upload_url(
    req: PresignedRequest,
    current_user: User = Depends(get_current_user)
):
    """Generates a direct S3 upload signature."""
    if not aws_utils.s3_client:
        raise HTTPException(status_code=503, detail="S3 service offline")
    
    ext = os.path.splitext(req.file_name)[1].lower()
    allowed = ['.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png', '.webp', '.gif']
    if ext not in allowed:
        raise HTTPException(status_code=400, detail="File type not allowed")

    folder = "bgv_documents" if req.category != "public_documents" else "public_documents"
    s3_key = f"{folder}/{uuid.uuid4()}_{req.file_name}"
    
    url = aws_utils.generate_presigned_put_url(s3_key, req.content_type)
    if not url:
        raise HTTPException(status_code=500, detail="Failed to sign URL")
        
    return {
        "upload_url": url,
        "public_id": s3_key,
        "predicted_url": f"https://{aws_utils.aws_bucket}.s3.{aws_utils.aws_region}.amazonaws.com/{s3_key}",
        "headers": {"Content-Type": req.content_type}
    }

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

@router.get("/proxy")
async def proxy_media(
    public_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Enterprise Proxy: Streams S3 objects directly to the frontend.
    Essential for CORS-compliant report rendering (html2pdf/html2canvas).
    """
    if not aws_utils.s3_client:
        raise HTTPException(status_code=503, detail="S3 Storage unavailable")
        
    try:
        response = await to_thread.run_sync(
            partial(
                aws_utils.s3_client.get_object,
                Bucket=aws_utils.aws_bucket,
                Key=public_id
            )
        )
        
        return StreamingResponse(
            io.BytesIO(response['Body'].read()),
            media_type=response.get('ContentType', 'application/octet-stream')
        )
    except aws_utils.s3_client.exceptions.NoSuchKey:
        raise HTTPException(status_code=404, detail="Media asset not found in storage")
    except Exception as e:
        logging.error(f"Media Proxy Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Protocol Error: Failed to retrieve media stream")
