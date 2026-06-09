from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List, Dict, Any, Optional
import os
import uuid
import logging
from datetime import datetime, date

from .database import get_async_db, AsyncSessionLocal
from . import models, schemas
from .auth_routes import get_current_user, check_module_permission
from . import aws_utils
from .worker import process_ocr_document_task

logger = logging.getLogger("ocr_routes")
router = APIRouter(prefix="/ocr", tags=["OCR / Document Intelligence"])

def parse_date_string(date_str: str) -> Optional[date]:
    
    if not date_str:
        return None
    cleaned = date_str.strip().replace("/", "-")
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d-%b-%Y", "%d-%m-%y"):
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None

@router.get("/settings", response_model=List[schemas.SystemSettingRead])
async def get_ocr_settings(
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    stmt = select(models.SystemSetting)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("/settings", response_model=List[schemas.SystemSettingRead])
async def update_ocr_settings(
    payload: Dict[str, str],
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    # Check permissions (must be admin/super admin)
    user_role = str(current_user.role.value if hasattr(current_user.role, 'value') else current_user.role).upper()
    if user_role not in ["ADMIN", "SUPER_ADMIN", "SUPER_ADMINISTRATOR", "SUPER_ADMIN", "SUPER ADMIN"]:
        raise HTTPException(status_code=403, detail="Only administrators can adjust System OCR configurations.")

    for key, val in payload.items():
        stmt = select(models.SystemSetting).filter(models.SystemSetting.key == key)
        res = await db.execute(stmt)
        setting = res.scalar_one_or_none()
        if setting:
            setting.value = val
        else:
            new_setting = models.SystemSetting(key=key, value=val)
            db.add(new_setting)
            
    await db.commit()
    stmt = select(models.SystemSetting)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("/upload", response_model=schemas.OcrExtractionRead)
async def upload_ocr_document(
    file: UploadFile = File(...),
    candidate_id: Optional[str] = None,
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    if not aws_utils.s3_client:
        raise HTTPException(status_code=503, detail="S3 Storage service unavailable")

    try:
        ext = os.path.splitext(file.filename)[1].lower()
        allowed_exts = ['.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.heic']
        if ext not in allowed_exts:
            raise HTTPException(status_code=400, detail=f"Unsupported file format ({ext})")

        # Validate maximum size of 20MB
        file_data = await file.read()
        file_size_mb = len(file_data) / (1024 * 1024)
        if file_size_mb > 20.0:
            raise HTTPException(status_code=400, detail="File size exceeds the 20MB limits.")

        # Upload file to S3
        unique_filename = f"ocr_documents/{uuid.uuid4()}_{file.filename}"
        await db.run_sync(
            lambda session: aws_utils.s3_client.put_object(
                Bucket=aws_utils.aws_bucket,
                Key=unique_filename,
                Body=file_data,
                ContentType=file.content_type
            )
        )
        
        file_url = f"https://{aws_utils.aws_bucket}.s3.{aws_utils.aws_region}.amazonaws.com/{unique_filename}"
        
        # Create OCR Processing Job record
        job = models.OcrExtraction(
            file_name=file.filename,
            file_url=file_url,
            s3_key=unique_filename,
            status="QUEUED",
            progress=0,
            candidate_id=candidate_id
        )
        
        # Save uploader metadata as DocumentMetadata to keep duplicate audits working
        import hashlib
        file_hash = hashlib.sha256(file_data).hexdigest()
        meta = models.DocumentMetadata(
            file_hash=file_hash,
            file_name=file.filename,
            mime_type=file.content_type,
            size=len(file_data),
            uploader_id=current_user.id,
            candidate_id=candidate_id
        )
        
        db.add(job)
        db.add(meta)
        await db.commit()
        await db.refresh(job)

        # Trigger background Celery Task (using delay or threadpool since celery is configured)
        try:
            process_ocr_document_task.delay(job.id)
        except Exception:
            pass
        
        import threading
        threading.Thread(target=process_ocr_document_task, args=(job.id,), daemon=True).start()
        
        return job
    except Exception as e:
        logger.error(f"OCR document upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to upload document for OCR: {str(e)}")

@router.post("/bulk-process", response_model=List[schemas.OcrExtractionRead])
async def bulk_upload_ocr_documents(
    files: List[UploadFile] = File(...),
    candidate_id: Optional[str] = None,
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    if not aws_utils.s3_client:
        raise HTTPException(status_code=503, detail="S3 Storage service unavailable")

    batch_id = str(uuid.uuid4())
    created_jobs = []

    for file in files:
        try:
            ext = os.path.splitext(file.filename)[1].lower()
            allowed_exts = ['.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.heic', '.zip', '.rar']
            if ext not in allowed_exts:
                continue

            file_data = await file.read()
            file_size_mb = len(file_data) / (1024 * 1024)
            if file_size_mb > 20.0:
                continue

            unique_filename = f"ocr_documents/{uuid.uuid4()}_{file.filename}"
            await db.run_sync(
                lambda session: aws_utils.s3_client.put_object(
                    Bucket=aws_utils.aws_bucket,
                    Key=unique_filename,
                    Body=file_data,
                    ContentType=file.content_type
                )
            )
            
            file_url = f"https://{aws_utils.aws_bucket}.s3.{aws_utils.aws_region}.amazonaws.com/{unique_filename}"
            
            job = models.OcrExtraction(
                file_name=file.filename,
                file_url=file_url,
                s3_key=unique_filename,
                status="QUEUED",
                progress=0,
                candidate_id=candidate_id,
                batch_id=batch_id
            )
            
            import hashlib
            file_hash = hashlib.sha256(file_data).hexdigest()
            meta = models.DocumentMetadata(
                file_hash=file_hash,
                file_name=file.filename,
                mime_type=file.content_type,
                size=len(file_data),
                uploader_id=current_user.id,
                candidate_id=candidate_id
            )
            
            db.add(job)
            db.add(meta)
            created_jobs.append(job)
            
        except Exception as e:
            logger.error(f"Bulk OCR document upload failed for {file.filename}: {e}", exc_info=True)
            continue
            
    await db.commit()
    
    import threading
    for job in created_jobs:
        await db.refresh(job)
        try:
            process_ocr_document_task.delay(job.id)
        except Exception:
            pass
        threading.Thread(target=process_ocr_document_task, args=(job.id,), daemon=True).start()
        
    return created_jobs

@router.get("/jobs", response_model=List[schemas.OcrExtractionRead])
async def list_ocr_jobs(
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    stmt = select(models.OcrExtraction).order_by(models.OcrExtraction.created_at.desc())
    res = await db.execute(stmt)
    return res.scalars().all()

@router.get("/jobs/{job_id}", response_model=schemas.OcrExtractionRead)
async def get_ocr_job(
    job_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    stmt = select(models.OcrExtraction).filter(models.OcrExtraction.id == job_id)
    res = await db.execute(stmt)
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="OCR job not found.")
    return job

@router.post("/jobs/{job_id}/action", response_model=schemas.OcrExtractionRead)
async def execute_ocr_action(
    job_id: str,
    payload: schemas.OcrExtractionAction,
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    stmt = select(models.OcrExtraction).filter(models.OcrExtraction.id == job_id)
    res = await db.execute(stmt)
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="OCR job not found.")

    act = payload.action.upper()
    if act == "APPROVE":
        job.review_status = "APPROVED"
        job.is_verified = True
    elif act == "REJECT":
        job.review_status = "REJECTED"
        job.is_verified = False
    elif act == "REPROCESS":
        job.status = "QUEUED"
        job.progress = 0
        job.review_status = "PENDING"
        job.is_verified = False
        try:
            process_ocr_document_task.delay(job.id)
        except Exception:
            pass
        import threading
        threading.Thread(target=process_ocr_document_task, args=(job.id,), daemon=True).start()
    else:
        raise HTTPException(status_code=400, detail=f"Invalid action: {act}")

    await db.commit()
    await db.refresh(job)
    return job

@router.post("/jobs/{job_id}/save", response_model=schemas.OcrExtractionRead)
async def save_ocr_job_results(
    job_id: str,
    payload: schemas.OcrExtractionUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    stmt = select(models.OcrExtraction).filter(models.OcrExtraction.id == job_id)
    res = await db.execute(stmt)
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="OCR Job not found.")

    if payload.extracted_data is not None:
        # Merge edits
        job.extracted_data = {**(job.extracted_data or {}), **payload.extracted_data}
    if payload.review_status is not None:
        job.review_status = payload.review_status
    if payload.is_verified is not None:
        job.is_verified = payload.is_verified

    # Handle Smart Auto Mapping if enabled & candidate_id exists
    settings_stmt = select(models.SystemSetting).filter(models.SystemSetting.key == "enable_auto_mapping")
    settings_res = await db.execute(settings_stmt)
    auto_mapping_setting = settings_res.scalar_one_or_none()
    enable_mapping = auto_mapping_setting.value.lower() == "true" if auto_mapping_setting else True

    if enable_mapping and job.candidate_id:
        cand_stmt = select(models.Candidate).filter(models.Candidate.id == job.candidate_id)
        cand_res = await db.execute(cand_stmt)
        candidate = cand_res.scalar_one_or_none()
        
        if candidate:
            fields = job.extracted_data
            doc_type = job.document_type

            # Candidate basic profile mapping
            if doc_type == "Aadhaar Card":
                candidate.gender = fields.get("gender") or candidate.gender
                candidate.address = fields.get("address_on_id") or candidate.address
                candidate.phone = fields.get("mobile") or candidate.phone
                if fields.get("name_on_id"):
                    candidate.name = fields.get("name_on_id")
                dob_val = parse_date_string(fields.get("dob_on_id"))
                if dob_val:
                    candidate.dob = dob_val
                
                # Append card metadata to Candidate.documents list
                doc_entry = {
                    "original_filename": job.file_name,
                    "name": "Aadhaar Card",
                    "url": job.file_url,
                    "path": job.s3_key,
                    "mimetype": "image/png" if not job.file_name.lower().endswith('.pdf') else "application/pdf",
                    "check_type": "Identity Verification",
                    "uploaded_at": datetime.utcnow().isoformat() + "Z"
                }
                curr = list(candidate.documents) if candidate.documents else []
                curr.append(doc_entry)
                candidate.documents = curr

            elif doc_type == "PAN Card":
                candidate.pan_no = fields.get("id_number") or candidate.pan_no
                if fields.get("name_on_id") and not candidate.name:
                    candidate.name = fields.get("name_on_id")
                dob_val = parse_date_string(fields.get("dob_on_id"))
                if dob_val and not candidate.dob:
                    candidate.dob = dob_val

                doc_entry = {
                    "original_filename": job.file_name,
                    "name": "PAN Card",
                    "url": job.file_url,
                    "path": job.s3_key,
                    "mimetype": "image/png" if not job.file_name.lower().endswith('.pdf') else "application/pdf",
                    "check_type": "Identity Verification",
                    "uploaded_at": datetime.utcnow().isoformat() + "Z"
                }
                curr = list(candidate.documents) if candidate.documents else []
                curr.append(doc_entry)
                candidate.documents = curr

            elif doc_type == "Passport":
                candidate.passport_no = fields.get("id_number") or candidate.passport_no
                candidate.nationality = fields.get("nationality") or candidate.nationality
                if fields.get("name_on_id") and not candidate.name:
                    candidate.name = fields.get("name_on_id")
                dob_val = parse_date_string(fields.get("dob_on_id"))
                if dob_val and not candidate.dob:
                    candidate.dob = dob_val

                doc_entry = {
                    "original_filename": job.file_name,
                    "name": "Passport",
                    "url": job.file_url,
                    "path": job.s3_key,
                    "mimetype": "image/png" if not job.file_name.lower().endswith('.pdf') else "application/pdf",
                    "check_type": "Identity Verification",
                    "uploaded_at": datetime.utcnow().isoformat() + "Z"
                }
                curr = list(candidate.documents) if candidate.documents else []
                curr.append(doc_entry)
                candidate.documents = curr

            elif doc_type == "Employment Document":
                # Employment fields mapping - we can inject into a standard check or logs
                doc_entry = {
                    "original_filename": job.file_name,
                    "name": f"Employment Letter - {fields.get('employer_name')}",
                    "url": job.file_url,
                    "path": job.s3_key,
                    "mimetype": "image/png" if not job.file_name.lower().endswith('.pdf') else "application/pdf",
                    "check_type": "Employment Verification",
                    "uploaded_at": datetime.utcnow().isoformat() + "Z"
                }
                curr = list(candidate.documents) if candidate.documents else []
                curr.append(doc_entry)
                candidate.documents = curr

            elif doc_type == "Education Document":
                # Education fields mapping
                doc_entry = {
                    "original_filename": job.file_name,
                    "name": f"Education Certificate - {fields.get('university')}",
                    "url": job.file_url,
                    "path": job.s3_key,
                    "mimetype": "image/png" if not job.file_name.lower().endswith('.pdf') else "application/pdf",
                    "check_type": "Education Verification",
                    "uploaded_at": datetime.utcnow().isoformat() + "Z"
                }
                curr = list(candidate.documents) if candidate.documents else []
                curr.append(doc_entry)
                candidate.documents = curr

            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(candidate, "documents")
            db.add(candidate)

    await db.commit()
    await db.refresh(job)
    return job

@router.post("/process-existing", response_model=schemas.OcrExtractionRead)
async def process_existing_file(
    payload: dict,
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    try:
        file_url = payload.get("file_url")
        file_name = payload.get("file_name", "document")
        candidate_id = payload.get("candidate_id")

        if not file_url:
            raise HTTPException(status_code=400, detail="file_url is required")

        job = models.OcrExtraction(
            file_name=file_name,
            file_url=file_url,
            s3_key=file_url.split(".com/")[-1] if ".com/" in file_url else file_url,
            status="QUEUED",
            progress=0,
            candidate_id=candidate_id,
            batch_id=str(uuid.uuid4())
        )
        
        db.add(job)
        await db.commit()
        await db.refresh(job)

        try:
            process_ocr_document_task.delay(job.id)
        except Exception:
            pass
        import threading
        threading.Thread(target=process_ocr_document_task, args=(job.id,), daemon=True).start()
        
        return job
    except Exception as e:
        logger.error(f"Failed to process existing document for OCR: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to trigger OCR: {str(e)}")
