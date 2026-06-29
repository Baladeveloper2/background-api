from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
from sqlalchemy.orm import Session
from typing import List, Optional
from . import models, schemas, database, auth_routes
import os
import uuid
import io
from .aws_utils import s3_client, aws_bucket, aws_region
from anyio import to_thread
from datetime import datetime
from .visibility import get_tenant_filters

router = APIRouter(prefix="/customers", tags=["customers"])

# ─── IMPORTANT: Static routes MUST come before /{customer_id} dynamic route ───

from sqlalchemy import or_, func
from fastapi.responses import JSONResponse

def derive_case_final_result(case, db):
    """Derive business verification outcome from check results when case.final_result is NULL.
    Priority: case.final_result > case.final_report_status > derived from checks.
    NEVER returns workflow status like FINALIZED/COMPLETED as a business result."""
    stored = (case.final_result or case.final_report_status or "").upper().strip()
    
    # If stored result is a real business outcome, use it
    business_outcomes = ['POSITIVE', 'CLEAR', 'GREEN', 'CLEAR/VERIFIED', 'NEGATIVE', 'RED',
                         'AMBER', 'DISCREPANCY', 'STOPCHECK', 'STOP CHECK', 'CLIENT HOLD',
                         'HOLD', 'STOP', 'INTERIM', 'PARTIAL COMPLETION', 'INSUFFICIENT', 'INSUFFICIENCY']
    if stored in business_outcomes:
        return stored
    
    # Stored value is empty or a workflow status (FINALIZED/COMPLETED) — derive from checks
    workflow_status = (case.status or "").upper().strip()
    is_finalized = workflow_status in ['FINALIZED', 'COMPLETED']
    
    if not is_finalized:
        return None  # Case not yet finalized, genuinely WIP
    
    # Case is finalized but final_result not set — derive from verification checks
    checks = db.query(models.VerificationCheck).filter(
        models.VerificationCheck.case_id == case.id
    ).all()
    
    if not checks:
        return None
    
    check_results = [(chk.final_result or chk.status or "").upper().strip() for chk in checks]
    
    # Business rules: any NEGATIVE → NEGATIVE, any AMBER → AMBER, all POSITIVE → POSITIVE
    for r in check_results:
        if r in ['NEGATIVE', 'RED']:
            return 'NEGATIVE'
    for r in check_results:
        if r in ['STOPCHECK', 'STOP CHECK', 'CLIENT HOLD']:
            return 'STOP CHECK'
    for r in check_results:
        if r in ['INSUFFICIENT', 'INSUFFICIENCY']:
            return 'INSUFFICIENT'
    for r in check_results:
        if r in ['AMBER', 'DISCREPANCY']:
            return 'AMBER'
    for r in check_results:
        if r in ['INTERIM', 'PARTIAL COMPLETION']:
            return 'INTERIM'
    
    # All checks positive or clear
    positive_set = ['POSITIVE', 'CLEAR', 'GREEN', 'CLEAR/VERIFIED', 'QC_VERIFIED', 'VERIFIED']
    if all(r in positive_set for r in check_results if r):
        return 'POSITIVE'
    
    return None


@router.get("/dashboard-summary")
def get_customer_dashboard_summary(
    search: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_routes.get_current_user)
):
    if not current_user.customer_id:
        raise HTTPException(status_code=403, detail="Not associated with any customer")
        
    client_id = current_user.customer_id
    
    query = db.query(models.Case).filter(models.Case.customer_id == client_id)
    
    if search:
        query = query.join(models.Candidate, models.Case.candidate_id == models.Candidate.id, isouter=True).filter(
            or_(
                models.Candidate.name.ilike(f"%{search}%"),
                models.Case.case_ref_no.ilike(f"%{search}%")
            )
        )

    if from_date:
        try:
            from_dt = datetime.strptime(from_date, "%Y-%m-%d")
            query = query.filter(models.Case.received_date >= from_dt)
        except ValueError:
            query = query.filter(models.Case.received_date >= from_date)
    if to_date:
        try:
            to_dt = datetime.strptime(to_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            query = query.filter(models.Case.received_date <= to_dt)
        except ValueError:
            query = query.filter(models.Case.received_date <= to_date)

    cases = query.all()
    
    overall = len(cases)
    positive = 0
    negative = 0
    amber = 0
    in_progress = 0
    stop_check = 0
    interim = 0
    insufficiency = 0
    
    for c in cases:
        # Derive the REAL business result (never workflow status)
        val_to_eval = (derive_case_final_result(c, db) or "").upper().strip()

        if val_to_eval in ['POSITIVE', 'CLEAR', 'GREEN', 'CLEAR/VERIFIED']:
            positive += 1
        elif val_to_eval in ['NEGATIVE', 'RED']:
            negative += 1
        elif val_to_eval in ['AMBER', 'DISCREPANCY']:
            amber += 1
        elif val_to_eval in ['STOPCHECK', 'STOP CHECK', 'CLIENT HOLD', 'HOLD', 'STOP']:
            stop_check += 1
        elif val_to_eval in ['INTERIM', 'PARTIAL COMPLETION']:
            interim += 1
        elif val_to_eval in ['INSUFFICIENT', 'INSUFFICIENCY']:
            insufficiency += 1
        else:
            in_progress += 1


    return {
        "overallCases": overall,
        "positive": positive,
        "negative": negative,
        "amber": amber,
        "inProgress": in_progress,
        "stopCheck": stop_check,
        "interim": interim,
        "insufficiency": insufficiency
    }


@router.get("/candidates-list")
def get_customer_candidates(
    status: Optional[str] = None,
    search: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    page: int = 1,
    limit: int = 10,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_routes.get_current_user)
):
    if not current_user.customer_id:
        raise HTTPException(status_code=403, detail="Not associated with any customer")

    from sqlalchemy.orm import joinedload
    query = (
        db.query(models.Case)
        .options(joinedload(models.Case.candidate), joinedload(models.Case.customer))
        .filter(models.Case.customer_id == current_user.customer_id)
    )

    if search:
        query = query.join(models.Candidate, models.Case.candidate_id == models.Candidate.id, isouter=True).filter(
            or_(
                models.Candidate.name.ilike(f"%{search}%"),
                models.Case.case_ref_no.ilike(f"%{search}%")
            )
        )

    if from_date:
        try:
            from_dt = datetime.strptime(from_date, "%Y-%m-%d")
            query = query.filter(models.Case.received_date >= from_dt)
        except ValueError:
            query = query.filter(models.Case.received_date >= from_date)
    if to_date:
        try:
            to_dt = datetime.strptime(to_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            query = query.filter(models.Case.received_date <= to_dt)
        except ValueError:
            query = query.filter(models.Case.received_date <= to_date)

    # If status filter is applied, perform pagination in Python after status derivation
    if status and status.upper() not in ('ALL', ''):
        cases = query.order_by(models.Case.received_date.desc()).all()
        results = []
        for c in cases:
            cand = c.candidate
            results.append({
                "id": c.id,
                "candidate_name": cand.name if cand else "N/A",
                "case_ref_no": c.case_ref_no,
                "client_emp_code": cand.client_emp_code if cand else None,
                "received_date": c.received_date.isoformat() if c.received_date else None,
                "completed_date": c.completed_date.isoformat() if c.completed_date else None,
                "status": c.status,
                "final_result": derive_case_final_result(c, db),
                "is_in_tat": c.is_in_tat
            })

        filter_upper = status.upper().strip()
        def outcome_matches(res):
            val = (res.get('final_result') or '').upper().strip()
            if filter_upper == 'POSITIVE':
                return val in ['POSITIVE', 'CLEAR', 'GREEN', 'CLEAR/VERIFIED']
            if filter_upper == 'NEGATIVE':
                return val in ['NEGATIVE', 'RED']
            if filter_upper == 'AMBER':
                return val in ['AMBER', 'DISCREPANCY']
            if filter_upper in ['IN PROGRESS (WIP)', 'INPROGRESS', 'IN PROGRESS', 'WIP']:
                return not val or val == 'WIP'
            if filter_upper == 'STOP CHECK':
                return val in ['STOPCHECK', 'STOP CHECK', 'CLIENT HOLD']
            if filter_upper == 'INTERIM':
                return val in ['INTERIM', 'PARTIAL COMPLETION']
            if filter_upper in ('INSUFFICIENT', 'INSUFFICIENCY'):
                return val in ['INSUFFICIENT', 'INSUFFICIENCY']
            return False

        filtered = [r for r in results if outcome_matches(r)]
        total = len(filtered)
        results = filtered[(page - 1) * limit : page * limit]
    else:
        total = query.count()
        cases = query.order_by(models.Case.received_date.desc()).offset((page - 1) * limit).limit(limit).all()
        results = []
        for c in cases:
            cand = c.candidate
            results.append({
                "id": c.id,
                "candidate_name": cand.name if cand else "N/A",
                "case_ref_no": c.case_ref_no,
                "client_emp_code": cand.client_emp_code if cand else None,
                "received_date": c.received_date.isoformat() if c.received_date else None,
                "completed_date": c.completed_date.isoformat() if c.completed_date else None,
                "status": c.status,
                "final_result": derive_case_final_result(c, db),
                "is_in_tat": c.is_in_tat
            })

    return JSONResponse(
        content=results,
        headers={"x-total-count": str(total), "access-control-expose-headers": "x-total-count"}
    )


@router.get("/candidate/{case_id}/summary")
def get_candidate_summary(
    case_id: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_routes.get_current_user)
):
    if not current_user.customer_id:
        raise HTTPException(status_code=403, detail="Not associated with any customer")

    from sqlalchemy.orm import joinedload
    case = (
        db.query(models.Case)
        .options(joinedload(models.Case.candidate), joinedload(models.Case.customer))
        .filter(models.Case.id == case_id, models.Case.customer_id == current_user.customer_id)
        .first()
    )
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Use VerificationCheck (the actual model name)
    checks = db.query(models.VerificationCheck).filter(models.VerificationCheck.case_id == case_id).all()

    check_list = []
    for chk in checks:
        check_list.append({
            "module": chk.check_type,
            "status": chk.status,
            "result": chk.final_result,
            "completed_date": chk.verified_date.isoformat() if chk.verified_date else None
        })

    cand = case.candidate
    cust = case.customer
    return {
        "case": {
            "candidate_name": cand.name if cand else "N/A",
            "case_ref_no": case.case_ref_no,
            "client_emp_code": cand.client_emp_code if cand else None,
            "status": case.status,
            "sla": case.is_in_tat,
            "received_date": case.received_date.isoformat() if case.received_date else None,
            "completed_date": case.completed_date.isoformat() if case.completed_date else None,
            "overall_result": derive_case_final_result(case, db),
            "report_status": case.status,
            "id": case.id,
            "customer_name": cust.name if cust else "N/A"
        },
        "checks": check_list
    }


# ─── Dynamic / parameterized routes below ────────────────────────────────────

@router.post("", response_model=schemas.Customer)
async def create_customer(
    name: str = Form(...),
    short_code: Optional[str] = Form(None),
    city: Optional[str] = Form(None),
    contact_person: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    status: str = Form("ACTIVE"),
    zone_id: Optional[str] = Form(None),
    company_name: Optional[str] = Form(None),
    company_code: Optional[str] = Form(None),
    head_office: Optional[str] = Form(None),
    industry: Optional[str] = Form(None),
    agreement_file: Optional[UploadFile] = File(None),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_routes.check_module_permission("bms", "customer", action="write"))
):
    file_path = None
    if agreement_file and s3_client and aws_bucket:
        file_ext = os.path.splitext(agreement_file.filename)[1]
        file_name = f"bgv_documents/{uuid.uuid4()}{file_ext}"
        file_data = await agreement_file.read()
        
        await to_thread.run_sync(
            s3_client.upload_fileobj,
            io.BytesIO(file_data),
            aws_bucket,
            file_name,
            {'ContentType': agreement_file.content_type}
        )
        file_path = file_name

    # Check short_code uniqueness
    if short_code:
        existing = db.query(models.Customer).filter(models.Customer.short_code == short_code).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"Shortcode '{short_code}' is already assigned to another client.")

    db_customer = models.Customer(
        name=name,
        short_code=short_code,
        city=city,
        contact_person=contact_person,
        phone=phone,
        email=email,
        address=address,
        status=status,
        zone_id=zone_id,
        company_name=company_name,
        company_code=company_code,
        head_office=head_office,
        industry=industry,
        customer_agreement=file_path
    )
    db.add(db_customer)
    db.commit()
    db.refresh(db_customer)
    return db_customer

@router.get("", response_model=List[schemas.Customer])
def list_customers(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_routes.check_module_permission("bms", "customer", action="read"))
):
    user_role_str = str(current_user.role.value if hasattr(current_user.role, 'value') else current_user.role).upper()
    role_name = (current_user.role_rel.name.upper() if current_user.role_rel else "").upper()
    is_customer = "CUSTOMER" in user_role_str or "CUSTOMER" in role_name

    from sqlalchemy import func
    
    # Subquery to count batches per customer
    batch_counts_subq = db.query(
        models.Batch.customer_id, 
        func.count(models.Batch.id).label("total_batches")
    ).group_by(models.Batch.customer_id).subquery()

    # Optimized joined query
    query = db.query(
        models.Customer, 
        batch_counts_subq.c.total_batches
    ).outerjoin(batch_counts_subq, models.Customer.id == batch_counts_subq.c.customer_id).order_by(models.Customer.created_at.desc())
    
    tenant_filter = get_tenant_filters(current_user, models.Customer)
    if tenant_filter is not None:
        if tenant_filter is False:
            return [] # No access
        elif tenant_filter is not True:
            query = query.filter(tenant_filter)
    
    res = query.all()
    
    # Map results and attach counts
    results = []
    for customer, count in res:
        customer.batches_count = int(count or 0)
        results.append(customer)
        
    return results

@router.get("/{customer_id}", response_model=schemas.Customer)
def get_customer(
    customer_id: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_routes.check_module_permission("bms", "customer", action="read"))
):
    db_customer = db.query(models.Customer).filter(models.Customer.id == customer_id).first()
    if not db_customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Add count
    from sqlalchemy import func
    count = db.query(func.count(models.Batch.id)).filter(models.Batch.customer_id == customer_id).scalar()
    db_customer.batches_count = count
    
    return db_customer

@router.patch("/{customer_id}", response_model=schemas.Customer)
async def update_customer(
    customer_id: str,
    name: Optional[str] = Form(None),
    short_code: Optional[str] = Form(None),
    city: Optional[str] = Form(None),
    contact_person: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    status: Optional[str] = Form(None),
    zone_id: Optional[str] = Form(None),
    company_name: Optional[str] = Form(None),
    company_code: Optional[str] = Form(None),
    head_office: Optional[str] = Form(None),
    industry: Optional[str] = Form(None),
    agreement_file: Optional[UploadFile] = File(None),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_routes.check_module_permission("bms", "customer", action="write"))
):
    db_customer = db.query(models.Customer).filter(models.Customer.id == customer_id).first()
    if not db_customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    if name is not None: db_customer.name = name
    if city is not None: db_customer.city = city
    if contact_person is not None: db_customer.contact_person = contact_person
    if phone is not None: db_customer.phone = phone
    if email is not None: db_customer.email = email
    if address is not None: db_customer.address = address
    if status is not None: db_customer.status = status
    if zone_id is not None: db_customer.zone_id = zone_id
    if company_name is not None: db_customer.company_name = company_name
    if company_code is not None: db_customer.company_code = company_code
    if head_office is not None: db_customer.head_office = head_office
    if industry is not None: db_customer.industry = industry

    if short_code is not None:
        # Check uniqueness if changed
        if short_code != db_customer.short_code:
            existing = db.query(models.Customer).filter(models.Customer.short_code == short_code).first()
            if existing:
                raise HTTPException(status_code=400, detail=f"Shortcode '{short_code}' is already assigned to another client.")
        db_customer.short_code = short_code

    if agreement_file and s3_client and aws_bucket:
        file_ext = os.path.splitext(agreement_file.filename)[1]
        file_name = f"bgv_documents/{uuid.uuid4()}{file_ext}"
        file_data = await agreement_file.read()
        
        await to_thread.run_sync(
            s3_client.upload_fileobj,
            io.BytesIO(file_data),
            aws_bucket,
            file_name,
            {'ContentType': agreement_file.content_type}
        )
        db_customer.customer_agreement = file_name
    
    db.commit()
    db.refresh(db_customer)
    return db_customer

@router.post("/{customer_id}/documents", response_model=schemas.Customer)
async def upload_customer_document(
    customer_id: str,
    file: UploadFile = File(...),
    folder: str = "General",
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_routes.get_current_user)
):
    # Check if user belongs to this customer or is admin
    if current_user.role != models.UserRole.SUPER_ADMIN and current_user.customer_id != customer_id:
        raise HTTPException(status_code=403, detail="Not authorized to upload for this client")

    db_customer = db.query(models.Customer).filter(models.Customer.id == customer_id).first()
    if not db_customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    if not s3_client or not aws_bucket:
        raise HTTPException(status_code=500, detail="S3 storage is not configured. Please check your AWS credentials.")

    try:
        file_ext = os.path.splitext(file.filename)[1]
        file_key = f"bgv_documents/{uuid.uuid4()}{file_ext}"
        file_data = await file.read()
        
        await to_thread.run_sync(
            s3_client.upload_fileobj,
            io.BytesIO(file_data),
            aws_bucket,
            file_key,
            {'ContentType': file.content_type}
        )
        file_info = {
            "url": f"https://{aws_bucket}.s3.{aws_region}.amazonaws.com/{file_key}",
            "path": file_key,
            "original_filename": file.filename,
            "uploaded_at": datetime.utcnow().isoformat(),
            "uploaded_by": current_user.full_name,
            "folder": folder
        }
        
        docs = list(db_customer.documents or [])
        docs.append(file_info)
        db_customer.documents = docs
        db.commit()
        db.refresh(db_customer)
        return db_customer

    except Exception as e:
        print(f"S3 Upload Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to upload to S3: {str(e)}")

from fastapi.responses import RedirectResponse
@router.get("/{customer_id}/agreement")
async def get_customer_agreement(
    customer_id: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_routes.get_current_user)
):
    db_customer = db.query(models.Customer).filter(models.Customer.id == customer_id).first()
    if not db_customer or not db_customer.customer_agreement:
        raise HTTPException(status_code=404, detail="Agreement not found")
    
    if s3_client and aws_bucket:
        try:
            url = await to_thread.run_sync(
                s3_client.generate_presigned_url,
                'get_object',
                {'Bucket': aws_bucket, 'Key': db_customer.customer_agreement},
                3600
            )
            return {"url": url}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"S3 Error: {str(e)}")
    
    raise HTTPException(status_code=500, detail="S3 storage not configured")

@router.delete("/{customer_id}")
def delete_customer(
    customer_id: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_routes.check_module_permission("bms", "customer", action="delete"))
):
    db_customer = db.query(models.Customer).filter(models.Customer.id == customer_id).first()
    if not db_customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    db.delete(db_customer)
    db.commit()
    return {"message": "Customer deleted successfully"}

