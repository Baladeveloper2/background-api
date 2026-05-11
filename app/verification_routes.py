from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from sqlalchemy.orm import selectinload
from typing import List, Optional, Dict, Any
from . import models, schemas, aws_utils
from .database import get_async_db
from .auth_routes import check_module_permission, get_current_user
from . import notification_utils
import uuid
from datetime import datetime


router = APIRouter(
    prefix="/verifications",
    tags=["verifications"]
)

def enrich_check(check: models.VerificationCheck) -> models.VerificationCheck:
    """Populates virtual fields for response schemas."""
    case_obj = check.case
    if case_obj:
        check.case_ref = case_obj.case_ref_no
        if case_obj.candidate:
            check.candidate_name = case_obj.candidate.name
            # Handle given_address enrichment
            addr_data = ""
            if case_obj.candidate.address_details:
                if "address" in case_obj.candidate.address_details:
                    addr_data = str(case_obj.candidate.address_details["address"])
                elif "addresses" in case_obj.candidate.address_details and case_obj.candidate.address_details["addresses"]:
                    first = case_obj.candidate.address_details["addresses"][0]
                    addr_data = str(first.get("address", first))
            check.given_address = addr_data or (case_obj.candidate.address or "")
            
        if case_obj.customer:
            check.customer_name = case_obj.customer.name
            

    return check

@router.post("/checks", response_model=schemas.VerificationCheck, dependencies=[Depends(check_module_permission("bvs", "verification", action="write"))])
async def create_verification_check(check: schemas.VerificationCheckCreate, db: AsyncSession = Depends(get_async_db)):
    db_check = models.VerificationCheck(**check.dict())
    db.add(db_check)
    await db.commit()
    await db.refresh(db_check)
    
    # Reload with relations for enrichment
    stmt = select(models.VerificationCheck).options(
        selectinload(models.VerificationCheck.case).selectinload(models.Case.candidate),
        selectinload(models.VerificationCheck.case).selectinload(models.Case.customer),
        selectinload(models.VerificationCheck.documents).selectinload(models.VerificationDocument.uploader),
        selectinload(models.VerificationCheck.logs).selectinload(models.VerificationLog.performer),
        selectinload(models.VerificationCheck.assigned_verifier),
        selectinload(models.VerificationCheck.qc_verifier)
    ).filter(models.VerificationCheck.id == db_check.id)
    res = await db.execute(stmt)
    db_check = res.scalar_one()
    
    return enrich_check(db_check)

@router.get("/checks", response_model=List[schemas.VerificationCheck], dependencies=[Depends(check_module_permission("bvs", "verification", action="read"))])
async def read_verification_checks(case_id: Optional[str] = None, type: Optional[str] = None, db: AsyncSession = Depends(get_async_db)):
    stmt = select(models.VerificationCheck).options(
        selectinload(models.VerificationCheck.case).selectinload(models.Case.candidate),
        selectinload(models.VerificationCheck.case).selectinload(models.Case.customer),
        selectinload(models.VerificationCheck.documents).selectinload(models.VerificationDocument.uploader),
        selectinload(models.VerificationCheck.logs).selectinload(models.VerificationLog.performer),
        selectinload(models.VerificationCheck.assigned_verifier),
        selectinload(models.VerificationCheck.qc_verifier)
    )
    if case_id:
        stmt = stmt.filter(models.VerificationCheck.case_id == case_id)
    if type:
        stmt = stmt.filter(models.VerificationCheck.check_type.ilike(f"%{type}%"))
    
    res = await db.execute(stmt)
    results = res.scalars().all()
    
    return [enrich_check(c) for c in results]

@router.patch("/checks/{check_id}", response_model=schemas.VerificationCheck, dependencies=[Depends(check_module_permission("bvs", "verification", action="write"))])
async def update_verification_check(check_id: str, check_update: schemas.VerificationCheckUpdate, db: AsyncSession = Depends(get_async_db)):
    stmt = select(models.VerificationCheck).options(
        selectinload(models.VerificationCheck.case).selectinload(models.Case.candidate),
        selectinload(models.VerificationCheck.case).selectinload(models.Case.customer),
        selectinload(models.VerificationCheck.documents).selectinload(models.VerificationDocument.uploader),
        selectinload(models.VerificationCheck.logs).selectinload(models.VerificationLog.performer),
        selectinload(models.VerificationCheck.assigned_verifier),
        selectinload(models.VerificationCheck.qc_verifier)
    ).filter(models.VerificationCheck.id == check_id)
    res = await db.execute(stmt)
    db_check = res.scalar_one_or_none()
    
    if db_check is None:
        raise HTTPException(status_code=404, detail="Check not found")
    
    update_data = check_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_check, key, value)
    
    await db.commit()
    
    # Reload with relations for enrichment (avoids MissingGreenlet after refresh)
    stmt = select(models.VerificationCheck).options(
        selectinload(models.VerificationCheck.case).selectinload(models.Case.candidate),
        selectinload(models.VerificationCheck.case).selectinload(models.Case.customer),
        selectinload(models.VerificationCheck.documents).selectinload(models.VerificationDocument.uploader),
        selectinload(models.VerificationCheck.logs).selectinload(models.VerificationLog.performer),
        selectinload(models.VerificationCheck.assigned_verifier),
        selectinload(models.VerificationCheck.qc_verifier)
    ).filter(models.VerificationCheck.id == check_id)
    res = await db.execute(stmt)
    db_check = res.scalar_one()
    
    return enrich_check(db_check)

@router.patch("/checks/{check_id}/generate-link", response_model=schemas.VerificationCheck, dependencies=[Depends(check_module_permission("bvs", "verification", action="write"))])
async def generate_verification_link(check_id: str, db: AsyncSession = Depends(get_async_db)):
    stmt = select(models.VerificationCheck).options(
        selectinload(models.VerificationCheck.case).selectinload(models.Case.candidate),
        selectinload(models.VerificationCheck.case).selectinload(models.Case.customer),
        selectinload(models.VerificationCheck.documents).selectinload(models.VerificationDocument.uploader),
        selectinload(models.VerificationCheck.logs).selectinload(models.VerificationLog.performer),
        selectinload(models.VerificationCheck.assigned_verifier),
        selectinload(models.VerificationCheck.qc_verifier)
    ).filter(models.VerificationCheck.id == check_id)
    res = await db.execute(stmt)
    db_check = res.scalar_one_or_none()
    
    if db_check is None:
        raise HTTPException(status_code=404, detail="Check not found")
    
    db_check.digital_token = str(uuid.uuid4())
    await db.commit()
    
    # Reload with relations for enrichment
    stmt = select(models.VerificationCheck).options(
        selectinload(models.VerificationCheck.case).selectinload(models.Case.candidate),
        selectinload(models.VerificationCheck.case).selectinload(models.Case.customer),
        selectinload(models.VerificationCheck.documents).selectinload(models.VerificationDocument.uploader),
        selectinload(models.VerificationCheck.logs).selectinload(models.VerificationLog.performer),
        selectinload(models.VerificationCheck.assigned_verifier),
        selectinload(models.VerificationCheck.qc_verifier)
    ).filter(models.VerificationCheck.id == check_id)
    res = await db.execute(stmt)
    db_check = res.scalar_one()
    
    return enrich_check(db_check)

@router.get("/public/{token}", response_model=Dict[str, Any])
async def get_public_verification(token: str, db: AsyncSession = Depends(get_async_db)):
    stmt = select(models.VerificationCheck).options(
        selectinload(models.VerificationCheck.case).selectinload(models.Case.candidate)
    ).filter(models.VerificationCheck.digital_token == token)
    res = await db.execute(stmt)
    db_check = res.scalar_one_or_none()
    
    if db_check is None:
        raise HTTPException(status_code=404, detail="Invalid or expired link")
    
    case_obj = db_check.case
    candidate = case_obj.candidate
    
    # Resolve given address with fallbacks
    given_addr = {}
    if candidate.address_details:
        if "address" in candidate.address_details:
            given_addr = candidate.address_details["address"]
        elif "addresses" in candidate.address_details and candidate.address_details["addresses"]:
            # Often stored as a list, take the first/primary
            first = candidate.address_details["addresses"][0]
            given_addr = first.get("address", first) # handle nested address object or flat member
    
    # Format fallback if still empty but flat address string exists
    if not given_addr and candidate.address:
        given_addr = {"line1": candidate.address}

    return {
        "check_id": db_check.id,
        "candidate_name": candidate.name,
        "check_type": db_check.check_type,
        "given_address": given_addr
    }

@router.post("/public/{token}")
async def submit_public_verification(token: str, submission: Dict[str, Any], background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_async_db)):
    stmt = select(models.VerificationCheck).options(
        selectinload(models.VerificationCheck.case)
    ).filter(models.VerificationCheck.digital_token == token)
    res = await db.execute(stmt)
    db_check = res.scalar_one_or_none()
    
    if db_check is None:
        raise HTTPException(status_code=404, detail="Invalid or expired link")
    
    # Update check data
    if not db_check.data:
        db_check.data = {}
    
    db_check.data["digital_data"] = submission
    db_check.status = models.CheckStatus.VERIFICATION
    db_check.verifier_remarks = "Digital Address submitted by candidate."
    
    # Notify verifier if assigned
    if db_check.case and db_check.case.assigned_to:
        await notification_utils.create_notification(
            db, db_check.case.assigned_to,
            "Form Submitted",
            f"Candidate has submitted form for Case {db_check.case.case_ref_no}.",
            models.NotificationCategory.FORM_SUBMITTED,
            case_id=db_check.case_id,
            background_tasks=background_tasks
        )

    await db.commit()
    
@router.post("/checks/{check_id}/upload")
async def upload_verification_document(
    check_id: str, 
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    """Uploads evidence to S3 and registers it in the database."""
    stmt = select(models.VerificationCheck).filter(models.VerificationCheck.id == check_id)
    res = await db.execute(stmt)
    check = res.scalar_one_or_none()
    if not check:
        raise HTTPException(404, detail="Verification check not found")

    # Upload to S3
    ext = file.filename.split('.')[-1]
    s3_path = f"evidence/{check_id}/{uuid.uuid4()}.{ext}"
    uploaded_path = await aws_utils.upload_to_s3(file, s3_path)
    
    # Get Public/Presigned URL
    file_url = await aws_utils.generate_presigned_url(uploaded_path)
    
    # Save to DB
    doc = models.VerificationDocument(
        check_id=check_id,
        file_name=file.filename,
        file_url=file_url,
        file_type=file.content_type,
        s3_key=uploaded_path,
        uploaded_by_id=current_user.id
    )
    db.add(doc)
    
    # Log Action
    log = models.VerificationLog(
        case_id=check.case_id,
        check_id=check_id,
        action="DOCUMENT_UPLOADED",
        performed_by_id=current_user.id,
        remarks=f"Evidence document '{file.filename}' uploaded."
    )
    db.add(log)
    
    await db.commit()
    await db.refresh(doc)
    
    return doc

@router.patch("/checks/{check_id}/status-ops")
async def update_check_status_ops(
    check_id: str,
    data: Dict[str, Any],
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    """Updates status with granular logging and remarks."""
    stmt = select(models.VerificationCheck).filter(models.VerificationCheck.id == check_id)
    res = await db.execute(stmt)
    check = res.scalar_one_or_none()
    if not check:
        raise HTTPException(404, detail="Verification check not found")

    old_status = check.status
    new_status = data.get("status")
    remarks = data.get("remarks")
    confidence = data.get("confidence_score")
    
    if new_status: check.status = new_status
    if remarks: check.verifier_remarks = remarks
    if confidence is not None: check.confidence_score = confidence
    
    if new_status and new_status != old_status:
        check.verified_date = datetime.utcnow()
        
    # Log the operation
    log = models.VerificationLog(
        case_id=check.case_id,
        check_id=check_id,
        action="STATUS_UPDATED",
        performed_by_id=current_user.id,
        old_status=old_status,
        new_status=new_status,
        remarks=remarks or f"Status changed from {old_status} to {new_status}"
    )
    db.add(log)
    
    await db.commit()
    return {"status": "success", "new_status": new_status}

@router.post("/checks/{check_id}/qc-issues", response_model=schemas.QCFieldIssueRead)
async def raise_qc_issue(
    check_id: str,
    issue: schemas.QCFieldIssueCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    """Raise a granular QC discrepancy on a specific field."""
    stmt = select(models.VerificationCheck).options(
        selectinload(models.VerificationCheck.case)
    ).filter(models.VerificationCheck.id == check_id)
    res = await db.execute(stmt)
    check = res.scalar_one_or_none()
    if not check:
        raise HTTPException(404, detail="Check not found")

    # If assignee not provided, default to the verifier who worked on the check
    assignee_id = issue.assigned_to or check.assigned_verifier_id or check.case.assigned_to

    db_issue = models.QCFieldIssue(
        case_id=check.case_id,
        check_id=check_id,
        field_name=issue.field_name,
        issue_type=issue.issue_type,
        comment=issue.comment,
        raised_by=current_user.id,
        assigned_to=assignee_id,
        status=models.QCIssueStatus.OPEN
    )
    db.add(db_issue)
    
    # Update check status to signify it has open issues
    check.qc_status = "REJECTED" # Or similar
    
    # Log the operation
    log = models.VerificationLog(
        case_id=check.case_id,
        check_id=check_id,
        action="QC_ISSUE_RAISED",
        performed_by_id=current_user.id,
        remarks=f"QC Query raised on field '{issue.field_name}': {issue.issue_type}"
    )
    db.add(log)
    
    # Notify the assignee
    if assignee_id:
        await notification_utils.create_notification(
            db, assignee_id,
            "QC Query Raised",
            f"QC has raised a query on {check.check_type} - {issue.field_name}.",
            models.NotificationCategory.SYSTEM_ALERT,
            case_id=check.case_id,
            background_tasks=background_tasks
        )

    await db.commit()
    await db.refresh(db_issue)
        
    return db_issue

@router.get("/checks/{check_id}/qc-issues", response_model=List[schemas.QCFieldIssueRead])
async def get_check_qc_issues(check_id: str, db: AsyncSession = Depends(get_async_db)):
    """Fetch all QC issues for a specific check."""
    stmt = select(models.QCFieldIssue).options(
        selectinload(models.QCFieldIssue.raiser),
        selectinload(models.QCFieldIssue.assignee)
    ).filter(models.QCFieldIssue.check_id == check_id)
    res = await db.execute(stmt)
    issues = res.scalars().all()
    
    # Map names for response
    for issue in issues:
        issue.raised_by_name = issue.raiser.full_name if issue.raiser else "Unknown"
        issue.assigned_to_name = issue.assignee.full_name if issue.assignee else "Unassigned"
        
    return issues

@router.patch("/qc-issues/{issue_id}/resolve")
async def resolve_qc_issue(
    issue_id: str,
    resolve_data: schemas.QCFieldIssueResolve,
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    """Mark a QC issue as resolved."""
    stmt = select(models.QCFieldIssue).filter(models.QCFieldIssue.id == issue_id)
    res = await db.execute(stmt)
    issue = res.scalar_one_or_none()
    if not issue:
        raise HTTPException(404, detail="Issue not found")
        
    issue.status = models.QCIssueStatus.RESOLVED
    issue.resolved_at = datetime.utcnow()
    if resolve_data.comment:
        issue.comment = (issue.comment or "") + f"\n\nResolution: {resolve_data.comment}"
        
    # Log the resolution
    log = models.VerificationLog(
        case_id=issue.case_id,
        check_id=issue.check_id,
        action="QC_ISSUE_RESOLVED",
        performed_by_id=current_user.id,
        remarks=f"QC Query for field '{issue.field_name}' marked as resolved."
    )
    db.add(log)
    
    await db.commit()
    return {"status": "success", "message": "Issue resolved"}

