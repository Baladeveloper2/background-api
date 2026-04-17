from fastapi import APIRouter, Depends, HTTPException, status, Response, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, update, delete
from sqlalchemy.orm import contains_eager, joinedload, selectinload
from typing import List, Optional, Dict, Any
from . import models, schemas
from .database import get_async_db, SessionLocal
import uuid
from datetime import datetime
from fastapi.responses import StreamingResponse
import requests
from pypdf import PdfWriter, PdfReader
from io import BytesIO
from .ocr_utils import get_scanner

from .auth_routes import check_module_permission, limiter, get_current_user, create_audit_log

router = APIRouter(
    prefix="/cases",
    tags=["cases"]
)

@router.post("", response_model=schemas.Case, dependencies=[Depends(check_module_permission("bvs", "verification", action="write"))])
async def create_case(case: schemas.CaseCreate, db: AsyncSession = Depends(get_async_db)):
    if not case.case_ref_no:
        customer_res = await db.execute(select(models.Customer).filter(models.Customer.id == case.customer_id))
        customer = customer_res.scalar_one_or_none()
        customer_name = customer.name if customer and customer.name else "BGV"
        prefix = customer_name[:3].upper()
        
        count_res = await db.execute(select(func.count(models.Case.id)).filter(models.Case.customer_id == case.customer_id))
        count = count_res.scalar() or 0
        case.case_ref_no = f"{prefix}{str(count + 1).zfill(3)}"
        
    db_case = models.Case(**case.dict())
    db.add(db_case)
    await db.commit()
    res = await db.execute(
        select(models.Case).options(
            joinedload(models.Case.candidate),
            joinedload(models.Case.customer),
            selectinload(models.Case.checks)
        ).filter(models.Case.id == db_case.id)
    )
    db_case = res.unique().scalar_one()

    return db_case

@router.post("/create-full", response_model=schemas.Case, dependencies=[Depends(check_module_permission("bvs", "verification", action="write"))])
async def create_case_full(case_data: schemas.CaseCreateExtended, db: AsyncSession = Depends(get_async_db)):
    # 1. Create/Get Candidate
    candidate_dict = case_data.candidate.dict()
    db_candidate = models.Candidate(**candidate_dict)
    db.add(db_candidate)
    await db.flush() # Get candidate ID

    # 2. Create Case
    if not case_data.case_ref_no:
        customer_res = await db.execute(select(models.Customer).filter(models.Customer.id == case_data.customer_id))
        customer = customer_res.scalar_one_or_none()
        customer_name = customer.name if customer and customer.name else "BGV"
        prefix = customer_name[:3].upper()
        count_res = await db.execute(select(func.count(models.Case.id)).filter(models.Case.customer_id == case_data.customer_id))
        count = count_res.scalar() or 0
        case_ref = f"{prefix}{str(count + 1).zfill(3)}"
    else:
        case_ref = case_data.case_ref_no

    db_case = models.Case(
        case_ref_no=case_ref,
        customer_id=case_data.customer_id,
        candidate_id=db_candidate.id,
        batch_id=case_data.batch_id,
        status=models.CaseStatus.PENDING,
        received_date=datetime.utcnow()
    )
    db.add(db_case)
    await db.flush()

    # 3. Create Verification Checks
    for service in case_data.services:
        rate = case_data.check_rates.get(service, 0.0) if case_data.check_rates else 0.0
        db_check = models.VerificationCheck(
            case_id=db_case.id,
            check_type=service,
            status=models.CheckStatus.INTERIM,
            rate=rate
        )
        db.add(db_check)
    
    await db.commit()
    
    # Reload with relationships for response validation
    stmt = select(models.Case).options(
        joinedload(models.Case.candidate),
        joinedload(models.Case.customer),
        selectinload(models.Case.checks)
    ).filter(models.Case.id == db_case.id)
    res = await db.execute(stmt)
    return res.unique().scalar_one()

@router.get("", response_model=List[schemas.CaseRead], dependencies=[Depends(check_module_permission("bvs", "verification", action="read"))])
async def read_cases(
    response: Response,
    status: Optional[models.CaseStatus] = None, 
    batch_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    search: Optional[str] = None,
    search_name: Optional[str] = None,
    search_ref: Optional[str] = None,
    assigned: Optional[bool] = None,
    skip: int = 0, 
    limit: int = 200, 
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    # 1. Base query for cases with their relationships
    stmt = select(models.Case).outerjoin(models.Case.candidate).options(
        contains_eager(models.Case.candidate),
        joinedload(models.Case.customer),
        joinedload(models.Case.batch),
        joinedload(models.Case.assigned_user),
        joinedload(models.Case.qa_user),
        joinedload(models.Case.qc_user),
        selectinload(models.Case.checks)
    )

    # 2. Assignment-based filtering (Data Isolation)
    if current_user.role not in [models.UserRole.SUPER_ADMIN, models.UserRole.ADMIN, models.UserRole.MANAGER, models.UserRole.QA, models.UserRole.QC]:
        stmt = stmt.filter(models.Case.assigned_to == current_user.id)
    
    if status:
        stmt = stmt.filter(models.Case.status == status)
    if batch_id:
        stmt = stmt.filter(models.Case.batch_id == batch_id)
    if customer_id:
        stmt = stmt.filter(models.Case.customer_id == customer_id)
    if search:
        stmt = stmt.filter(or_(models.Case.case_ref_no.ilike(f"%{search}%"), models.Candidate.name.ilike(f"{search}%")))
    if search_name:
        stmt = stmt.filter(models.Candidate.name.ilike(f"{search_name}%"))
    if search_ref:
        stmt = stmt.filter(models.Case.case_ref_no.ilike(f"%{search_ref}%"))
    if assigned is not None:
        if assigned:
            stmt = stmt.filter(models.Case.assigned_to != None)
        else:
            stmt = stmt.filter(models.Case.assigned_to == None)
    
    # 2. Results
    count_stmt = select(func.count(func.distinct(models.Case.id))).select_from(stmt.subquery())
    total_count_res = await db.execute(count_stmt)
    total_count = total_count_res.scalar() or 0
    response.headers["X-Total-Count"] = str(total_count)
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"

    stmt = stmt.order_by(models.Case.received_date.desc()).offset(skip).limit(limit)
    res = await db.execute(stmt)
    cases_models = res.unique().scalars().all()
    
    # 3. Transform to CaseRead format
    cases_read = []
    for case in cases_models:
        case_data = schemas.CaseRead.model_validate(case)
        if case.candidate: case_data.candidate_name = case.candidate.name
        if case.customer: case_data.customer_name = case.customer.name
        if case.batch:
            if not case_data.tat_days: case_data.tat_days = case.batch.tat_days
            case_data.batch_date = case.batch.upload_date
            case_data.batch_no = case.batch.batch_no
        if case.assigned_user: case_data.assigned_user_name = case.assigned_user.full_name
        if case.qa_user: case_data.qa_user_name = case.qa_user.full_name
        if case.qc_user: case_data.qc_user_name = case.qc_user.full_name
        cases_read.append(case_data)
    
    return cases_read

@router.get("/clients", response_model=List[str], dependencies=[Depends(check_module_permission("bvs", "verification", action="read"))])
async def read_case_clients(db: AsyncSession = Depends(get_async_db)):
    stmt = select(models.Customer.name).distinct().join(models.Case)
    res = await db.execute(stmt)
    return [r for r in res.scalars().all() if r]

@router.get("/report-stats", dependencies=[Depends(check_module_permission("bvs", "verification", action="read"))])
async def get_report_stats(customer_id: Optional[str] = None, db: AsyncSession = Depends(get_async_db)):
    # 1. Pie Data: Status distribution
    stmt = select(models.Case.status, func.count(models.Case.id)).group_by(models.Case.status)
    if customer_id: stmt = stmt.filter(models.Case.customer_id == customer_id)
    res = await db.execute(stmt)
    pie_data = [{"name": str(s), "value": count} for s, count in res.all()]

    # 2. Aggregates
    base_stmt = select(models.Case)
    if customer_id: base_stmt = base_stmt.filter(models.Case.customer_id == customer_id)
    
    total_res = await db.execute(select(func.count(models.Case.id)).select_from(base_stmt.subquery()))
    total = total_res.scalar() or 0
    
    comp_res = await db.execute(select(func.count(models.Case.id)).filter(models.Case.status == models.CaseStatus.COMPLETED).select_from(base_stmt.subquery()))
    completed = comp_res.scalar() or 0
    
    tat_res = await db.execute(select(func.avg(models.Case.tat_days)).filter(models.Case.status == models.CaseStatus.COMPLETED).select_from(base_stmt.subquery()))
    avg_tat = tat_res.scalar() or 0

    return {
        "pie_data": pie_data,
        "total_cases": total,
        "completion_rate": float(round((completed / total * 100), 1)) if total > 0 else 0.0,
        "avg_tat": float(round(float(avg_tat), 1))
    }

@router.get("/{case_id}", response_model=schemas.CaseRead, dependencies=[Depends(check_module_permission("bvs", "verification", action="read"))])
async def read_case(case_id: str, db: AsyncSession = Depends(get_async_db)):
    stmt = select(models.Case).options(
        joinedload(models.Case.candidate),
        joinedload(models.Case.customer),
        selectinload(models.Case.checks),
        joinedload(models.Case.batch),
        joinedload(models.Case.assigned_user),
        joinedload(models.Case.qa_user),
        joinedload(models.Case.qc_user)
    ).filter(models.Case.id == case_id)
    res = await db.execute(stmt)
    db_case = res.unique().scalar_one_or_none()
    
    if db_case is None:
        raise HTTPException(status_code=404, detail="Case not found")
        
    case_data = schemas.CaseRead.model_validate(db_case)
    if db_case.candidate: case_data.candidate_name = db_case.candidate.name
    if db_case.customer: case_data.customer_name = db_case.customer.name
    if db_case.batch:
        case_data.batch_no = db_case.batch.batch_no
        case_data.batch_date = db_case.batch.upload_date
    if db_case.assigned_user: case_data.assigned_user_name = db_case.assigned_user.full_name
    if db_case.qa_user: case_data.qa_user_name = db_case.qa_user.full_name
    if db_case.qc_user: case_data.qc_user_name = db_case.qc_user.full_name
    return case_data
class BulkActionRequest(schemas.BaseModel):
    case_ids: List[str]
    action: str
    target_value: Optional[str] = None

@router.post("/face-match")
async def face_match(req: dict, current_user: models.User = Depends(get_current_user)):
    url1 = req.get("url1") # ID Photo
    url2 = req.get("url2") # Profile/Selfie Photo
    
    if not url1 or not url2:
        return {"success": False, "message": "Missing URLs"}
        
    try:
        import requests
        from .ocr_utils import get_scanner
        
        scanner = get_scanner()
        
        # Download images
        r1 = requests.get(url1)
        r2 = requests.get(url2)
        
        if r1.status_code != 200 or r2.status_code != 200:
            return {"success": False, "message": "Failed to download images"}
            
        face1 = scanner.get_face(r1.content)
        face2 = scanner.get_face(r2.content)
        
        if face1 is None: return {"success": False, "message": "No face detected in Image 1"}
        if face2 is None: return {"success": False, "message": "No face detected in Image 2"}
        
        score = scanner.match_faces(face1, face2)
        
        return {
            "success": True,
            "match_score": round(score, 2),
            "is_match": score > 60, # Threshold for match
            "message": "Match successful" if score > 60 else "Potential mismatch"
        }
    except Exception as e:
        return {"success": False, "message": str(e)}

@router.post("/bulk-action", dependencies=[Depends(check_module_permission("bvs", "verification", action="write"))])
async def bulk_action(req: schemas.BulkActionRequest, db: AsyncSession = Depends(get_async_db), current_user: models.User = Depends(get_current_user)):
    if not req.case_ids:
        return {"msg": "No cases provided"}
        
    update_data: Dict[str, Any] = {}
    if req.action == "assign":
        update_data["assigned_to"] = req.target_value
        update_data["assigned_at"] = datetime.utcnow()
    elif req.action == "status":
        update_data["status"] = req.target_value
        if req.target_value == models.CaseStatus.COMPLETED:
            update_data["completed_date"] = datetime.utcnow()
            
    if not update_data:
        return {"msg": "Invalid action"}
        
    stmt = update(models.Case).where(models.Case.id.in_(req.case_ids)).values(**update_data)
    await db.execute(stmt)
    await db.commit()
    return {"msg": "Bulk action completed successfullly"}
    
    # Audit log and broadcast
@router.post("/auto-allocate")
async def auto_allocate(req: schemas.BulkActionRequest, db: AsyncSession = Depends(get_async_db), current_user: models.User = Depends(get_current_user)):
    if not req.case_ids:
        return {"msg": "No cases provided"}
        
    # 1. Fetch available verifiers
    res_users = await db.execute(select(models.User).filter(models.User.role == models.UserRole.VERIFIER, models.User.status == "ACTIVE"))
    verifiers = res_users.scalars().all()
    
    if not verifiers:
        return {"msg": "No active verifiers found", "success": False}
        
    # 2. Get current workloads
    # This counts cases with status PENDING or VERIFICATION assigned to each verifier
    workloads = {}
    for v in verifiers:
        count_res = await db.execute(select(func.count(models.Case.id)).filter(models.Case.assigned_to == v.id, models.Case.status != models.CaseStatus.COMPLETED))
        workloads[v.id] = count_res.scalar() or 0
        
    # 3. Assign cases greedily to verifier with least cases
    assigned_count = 0
    from .ws import manager
    
    for cid in req.case_ids:
        # Find verifier with minimum workload
        target_v_id = min(workloads, key=workloads.get)
        
        # Update case
        await db.execute(
            update(models.Case).where(models.Case.id == cid).values(
                assigned_to=target_v_id,
                assigned_at=datetime.utcnow()
            )
        )
        
        # Increment workload for next iteration
        workloads[target_v_id] += 1
        assigned_count += 1
        
        # Audit log and broadcast
        await create_audit_log(db, current_user.id, "AUTO_ALLOCATION", f"Case automatically assigned to verifier", resource_id=cid)
        await manager.broadcast({"type": "CASE_UPDATED", "case_id": cid, "action": "auto-assignment"})
        
    await db.commit()
    return {"msg": f"Successfully auto-allocated {assigned_count} cases", "success": True}

@router.patch("/{case_id}", response_model=schemas.Case, dependencies=[Depends(check_module_permission("bvs", "verification", action="write"))])
async def update_case(case_id: str, case_update: schemas.CaseUpdate, db: AsyncSession = Depends(get_async_db), current_user: models.User = Depends(get_current_user)):
    res = await db.execute(select(models.Case).filter(models.Case.id == case_id))
    db_case = res.scalar_one_or_none()
    if db_case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    
    update_data = case_update.dict(exclude_unset=True)
    candidate_update_data = update_data.pop("candidate", None)
    services_update = update_data.pop("services", None)
    rates_update = update_data.pop("check_rates", {})

    if update_data.get("status") == models.CaseStatus.COMPLETED and db_case.status != models.CaseStatus.COMPLETED:
        db_case.completed_date = datetime.utcnow()
    elif update_data.get("status") and update_data.get("status") != models.CaseStatus.COMPLETED:
        db_case.completed_date = None
        
    if update_data.get("assigned_to") and not db_case.assigned_at:
        db_case.assigned_at = datetime.utcnow()

    for key, value in update_data.items():
        if getattr(db_case, key) != value:
            # Simple audit log for status changes
            if key == "status":
                await create_audit_log(db, current_user.id, "STATUS_CHANGE", f"Case status updated from {db_case.status} to {value}", resource_id=case_id)
            elif key == "assigned_to":
                await create_audit_log(db, current_user.id, "CASE_ASSIGNMENT", f"Case assigned to user ID {value}", resource_id=case_id)
        setattr(db_case, key, value)
    
    # Update or Create Candidate
    if candidate_update_data:
        if db_case.candidate_id:
            res_cand = await db.execute(select(models.Candidate).filter(models.Candidate.id == db_case.candidate_id))
            db_candidate = res_cand.scalar_one_or_none()
            if db_candidate:
                for key, value in candidate_update_data.items():
                    if value is not None:
                        setattr(db_candidate, key, value)
        else:
            # Create new candidate if missing
            db_candidate = models.Candidate(**candidate_update_data)
            db.add(db_candidate)
            await db.flush()
            db_case.candidate_id = db_candidate.id

    # Sync Services/Checks
    if services_update is not None:
        # 1. Get existing checks
        existing_checks_res = await db.execute(select(models.VerificationCheck).filter(models.VerificationCheck.case_id == case_id))
        existing_checks = {c.check_type: c for c in existing_checks_res.scalars().all()}
        
        # 2. Add missing ones
        for svc in services_update:
            rate = rates_update.get(svc, 0.0)
            if svc in existing_checks:
                # Update rate if provided
                existing_checks[svc].rate = rate
            else:
                # Create new
                new_check = models.VerificationCheck(
                    case_id=case_id,
                    check_type=svc,
                    status=models.CheckStatus.INTERIM,
                    rate=rate
                )
                db.add(new_check)
        
        # 3. Optional: Remove checks not in services_update? 
        # For now, let's keep them (safer) or remove them if user specifically unselected them
        # (Decision: Unselected checks in Step 2 should be removed)
        for svc_type in list(existing_checks.keys()):
            if svc_type not in services_update:
                await db.delete(existing_checks[svc_type])
    
    await db.commit()
    res = await db.execute(
        select(models.Case).options(
            joinedload(models.Case.candidate),
            joinedload(models.Case.customer),
            selectinload(models.Case.checks)
        ).filter(models.Case.id == db_case.id)
    )
    db_case = res.unique().scalar_one()

    return db_case

@router.get("/{resource_id}/audit-logs", response_model=List[schemas.AuditLogRead], dependencies=[Depends(check_module_permission("bvs", "verification", action="read"))])
async def get_audit_logs(resource_id: str, db: AsyncSession = Depends(get_async_db)):
    # Note: I used DATABASE_get_async_db to avoid conflict with local variable if any, 
    # but the import is actually get_async_db in this file. Correcting to get_async_db.
    stmt = (
        select(models.AuditLog, models.User.full_name.label("user_full_name"))
        .outerjoin(models.User, models.AuditLog.user_id == models.User.id)
        .filter(models.AuditLog.resource_id == resource_id)
        .order_by(models.AuditLog.timestamp.desc())
    )
    res = await db.execute(stmt)
    results = []
    for log, full_name in res.all():
        log_data = schemas.AuditLogRead.model_validate(log)
        log_data.user_full_name = full_name
        results.append(log_data)
    return results

@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(check_module_permission("bvs", "verification", action="write"))])
async def delete_case(case_id: str, db: AsyncSession = Depends(get_async_db)):
    res = await db.execute(select(models.Case).filter(models.Case.id == case_id))
    db_case = res.scalar_one_or_none()
    if db_case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    
    candidate_id = db_case.candidate_id
    
    # Delete related checks first (cascade)
    await db.execute(delete(models.VerificationCheck).filter(models.VerificationCheck.case_id == case_id))
    
    # Delete the case
    await db.delete(db_case)
    
    # Check if candidate has other cases, if not, delete candidate
    if candidate_id:
        other_cases_res = await db.execute(select(func.count(models.Case.id)).filter(models.Case.candidate_id == candidate_id, models.Case.id != case_id))
        count = other_cases_res.scalar() or 0
        if count == 0:
            await db.execute(delete(models.Candidate).filter(models.Candidate.id == candidate_id))
            
    await db.commit()
    return None

from .aws_utils import s3_client, aws_bucket

def _do_merge(case_id: str, docs: list, candidate_name: str, case_ref: str):
    """Sync Background Task for PDF Merge."""
    import logging
    merger = PdfWriter()
    for doc in docs:
        url = doc.get('url')
        if not url: continue
        try:
            content = requests.get(url, timeout=15).content
            if url.lower().endswith('.pdf'):
                merger.append(PdfReader(BytesIO(content)))
            else:
                from PIL import Image
                img = Image.open(BytesIO(content)).convert('RGB')
                buf = BytesIO(); img.save(buf, format='PDF'); buf.seek(0)
                merger.append(PdfReader(buf))
        except Exception as e: logging.error(f"Merge error: {e}")
    
    if len(merger.pages) > 0:
        out = BytesIO(); merger.write(out); out.seek(0)
        filename = f"{candidate_name}_{case_ref}_merged.pdf"
        if s3_client and aws_bucket:
            s3_key = f"merged/{case_id}/{filename}"
            s3_client.put_object(Bucket=aws_bucket, Key=s3_key, Body=out.getvalue(), ContentType='application/pdf')
            db = SessionLocal()
            c = db.query(models.Case).filter(models.Case.id == case_id).first()
            if c: c.merged_pdf_key = s3_key; db.commit()
            db.close()

@router.post("/{case_id}/merge-pdfs", status_code=202, dependencies=[Depends(check_module_permission("bvs", "verification", action="write"))])
@limiter.limit("10/minute")
async def merge_pdfs(case_id: str, request: Request, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_async_db)):
    res = await db.execute(select(models.Case).options(joinedload(models.Case.candidate)).filter(models.Case.id == case_id))
    db_case = res.unique().scalar_one_or_none()
    if not db_case or not db_case.candidate:
        raise HTTPException(status_code=404, detail="Case/Candidate not found")
    
    docs = db_case.candidate.documents or []
    background_tasks.add_task(_do_merge, case_id, docs, db_case.candidate.name, db_case.case_ref_no)
    return {"message": "PDF merge queued"}

@router.post("/bulk-allocate")
async def bulk_allocate(data: Dict[str, Any], db: AsyncSession = Depends(get_async_db)):
    case_ids = data.get("case_ids", [])
    user_id = data.get("user_id")
    if not user_id and user_id is not None: raise HTTPException(400, "User ID required")
    await db.execute(update(models.Case).where(models.Case.id.in_(case_ids)).values(assigned_to=user_id))
    await db.commit()
    return {"message": "Success"}

@router.post("/ocr-extract")
async def ocr_extract(data: Dict[str, str], db: AsyncSession = Depends(get_async_db)):
    url = data.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="Document URL required")
    
    try:
        # Fetch the document
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch document")
        
        # OCR Processing
        scanner = get_scanner()
        text = scanner.reader.readtext(response.content, detail=0)
        full_text = " ".join(text)
        
        # Basic parsing
        extracted = scanner.parse_id(full_text)
        
        return {
            "success": True,
            "extracted_data": extracted,
            "raw_text_debug": str(full_text)[:500] # for debugging
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{case_id}/ai-summary")
async def generate_ai_summary(case_id: str, db: AsyncSession = Depends(get_async_db)):
    stmt = select(models.Case).options(
        joinedload(models.Case.candidate),
        selectinload(models.Case.checks)
    ).filter(models.Case.id == case_id)
    
    res = await db.execute(stmt)
    db_case = res.unique().scalar_one_or_none()
    if not db_case:
        raise HTTPException(status_code=404, detail="Case not found")
        
    checks = db_case.checks
    summary_parts = []
    
    # 1. Overall Status
    status_counts = {}
    for c in checks:
        status_counts[c.status] = status_counts.get(c.status, 0) + 1
    
    overall = "GREEN" if status_counts.get("GREEN") == len(checks) else "AMBER" if status_counts.get("RED") else "GREEN"
    if status_counts.get("RED"): overall = "RED"
    
    name = db_case.candidate.name if db_case.candidate else "The candidate"
    summary_parts.append(f"Verification Summary for {name}:")
    summary_parts.append(f"The overall verification status is {overall}.")
    
    # 2. Key Findings
    findings = []
    for c in checks:
        if c.status == "GREEN":
            findings.append(f"• {c.check_type}: Verified successfully with no discrepancies.")
        elif c.status == "RED":
            findings.append(f"• {c.check_type}: CRITICAL DISCREPANCY FOUND. {c.verifier_remarks or 'Verification failed.'}")
        elif c.status == "AMBER":
            findings.append(f"• {c.check_type}: Minor discrepancy noted. {c.verifier_remarks or 'Check results were clear with minor remarks.'}")
        else:
            findings.append(f"• {c.check_type}: Verification is currently {c.status}.")
            
    summary_parts.extend(findings)
    
    # 3. Final Conclusion
    if overall == "GREEN":
        summary_parts.append("\nConclusion: All provided credentials and background details have been verified as authentic. The candidate is cleared for further processing.")
    elif overall == "RED":
        summary_parts.append("\nConclusion: Due to critical discrepancies found in one or more verification modules, extreme caution is advised. Further internal review is recommended.")
    else:
        summary_parts.append("\nConclusion: The verification process revealed minor inconsistencies. Please review the specific notes for each module.")
        
    full_summary = "\n".join(summary_parts)
    
    # Save to DB
    db_case.ai_summary = full_summary
    await db.commit()
    
    return {"summary": full_summary}
