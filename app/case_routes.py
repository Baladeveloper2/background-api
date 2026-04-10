from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from . import models, schemas
from .database import get_db
import uuid
from datetime import datetime
from fastapi.responses import StreamingResponse
import requests
from pypdf import PdfWriter, PdfReader
from io import BytesIO

from .auth_routes import check_module_permission

router = APIRouter(
    prefix="/cases",
    tags=["cases"]
)

@router.post("", response_model=schemas.Case, dependencies=[Depends(check_module_permission("bvs", "verification", action="write"))])
def create_case(case: schemas.CaseCreate, db: Session = Depends(get_db)):
    if not case.case_ref_no:
        customer = db.query(models.Customer).filter(models.Customer.id == case.customer_id).first()
        customer_name = customer.name if customer and customer.name else "BGV"
        prefix = customer_name[:3].upper()
        count = db.query(models.Case).filter(models.Case.customer_id == case.customer_id).count()
        case.case_ref_no = f"{prefix}{str(count + 1).zfill(3)}"
        
    db_case = models.Case(**case.dict())
    db.add(db_case)
    db.commit()
    db.refresh(db_case)
    return db_case

@router.post("/create-full", response_model=schemas.Case, dependencies=[Depends(check_module_permission("bvs", "verification", action="write"))])
def create_case_full(case_data: schemas.CaseCreateExtended, db: Session = Depends(get_db)):
    # 1. Create/Get Candidate
    candidate_dict = case_data.candidate.dict()
    db_candidate = models.Candidate(**candidate_dict)
    db.add(db_candidate)
    db.flush() # Get candidate ID

    # 2. Create Case
    if not case_data.case_ref_no:
        customer = db.query(models.Customer).filter(models.Customer.id == case_data.customer_id).first()
        customer_name = customer.name if customer and customer.name else "BGV"
        prefix = customer_name[:3].upper()
        count = db.query(models.Case).filter(models.Case.customer_id == case_data.customer_id).count()
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
    db.flush()

    # 3. Create Verification Checks
    for service in case_data.services:
        db_check = models.VerificationCheck(
            case_id=db_case.id,
            check_type=service,
            status=models.CheckStatus.INTERIM
        )
        db.add(db_check)
    
    db.commit()
    db.refresh(db_case)
    return db_case

from sqlalchemy.orm import joinedload, selectinload

@router.get("", response_model=List[schemas.CaseRead], dependencies=[Depends(check_module_permission("bvs", "verification", action="read"))])
def read_cases(status: Optional[models.CaseStatus] = None, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    # 1. Base query for cases with their relationships
    query = db.query(models.Case).options(
        joinedload(models.Case.candidate),
        joinedload(models.Case.customer),
        selectinload(models.Case.checks),
        joinedload(models.Case.batch),
        joinedload(models.Case.assigned_user)
    )
    
    if status:
        query = query.filter(models.Case.status == status)
    
    # 2. Results
    cases_models = query.offset(skip).limit(limit).all()
    
    # 3. Transform to CaseRead format
    cases_read = []
    for case in cases_models:
        case_data = schemas.CaseRead.model_validate(case)
        # Ensure candidate name is always populated separately for the registry
        if case.candidate:
            case_data.candidate_name = case.candidate.name
        else:
            case_data.candidate_name = "UNNAMED"
            
        if case.customer:
            case_data.customer_name = case.customer.name
        
        # Populate Batch Metadata
        if case.batch:
            if not case_data.tat_days:
                case_data.tat_days = case.batch.tat_days
            case_data.batch_date = case.batch.upload_date
            case_data.batch_no = case.batch.batch_no
        
        if case.assigned_user:
            case_data.assigned_user_name = case.assigned_user.full_name
            
        cases_read.append(case_data)
    
    return cases_read

@router.get("/{case_id}", response_model=schemas.CaseRead, dependencies=[Depends(check_module_permission("bvs", "verification", action="read"))])
def read_case(case_id: str, db: Session = Depends(get_db)):
    db_case = db.query(models.Case).options(
        joinedload(models.Case.candidate),
        joinedload(models.Case.customer),
        selectinload(models.Case.checks),
        joinedload(models.Case.batch)
    ).filter(models.Case.id == case_id).first()
    
    if db_case is None:
        raise HTTPException(status_code=404, detail="Case not found")
        
    case_data = schemas.CaseRead.model_validate(db_case)
    if db_case.candidate:
        case_data.candidate_name = db_case.candidate.name
    if db_case.customer:
        case_data.customer_name = db_case.customer.name
    if db_case.batch:
        case_data.batch_no = db_case.batch.batch_no
        case_data.batch_date = db_case.batch.upload_date
        
    return case_data

@router.patch("/{case_id}", response_model=schemas.Case, dependencies=[Depends(check_module_permission("bvs", "verification", action="write"))])
def update_case(case_id: str, case_update: schemas.CaseUpdate, db: Session = Depends(get_db)):
    db_case = db.query(models.Case).filter(models.Case.id == case_id).first()
    if db_case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    
    update_data = case_update.dict(exclude_unset=True)
    
    # Auto-set completed_date (Out Date) when status moves to COMPLETED
    if update_data.get("status") == models.CaseStatus.COMPLETED and db_case.status != models.CaseStatus.COMPLETED:
        db_case.completed_date = datetime.utcnow()
    elif update_data.get("status") and update_data.get("status") != models.CaseStatus.COMPLETED:
        db_case.completed_date = None # Reset if moved back from COMPLETED
        
    for key, value in update_data.items():
        setattr(db_case, key, value)
    
    db.commit()
    db.refresh(db_case)
    return db_case

@router.patch("/{case_id}/full", response_model=schemas.Case, dependencies=[Depends(check_module_permission("bvs", "verification", action="write"))])
def update_case_full(case_id: str, case_data: schemas.CaseCreateExtended, db: Session = Depends(get_db)):
    db_case = db.query(models.Case).filter(models.Case.id == case_id).first()
    if db_case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    
    # 1. Update Candidate
    db_candidate = db.query(models.Candidate).filter(models.Candidate.id == db_case.candidate_id).first()
    if db_candidate:
        candidate_data = case_data.candidate.dict(exclude_unset=True)
        for key, value in candidate_data.items():
            setattr(db_candidate, key, value)
    
    # 2. Update Case Metadata
    db_case.case_ref_no = case_data.case_ref_no
    db_case.customer_id = case_data.customer_id
    db_case.batch_id = case_data.batch_id
    
    # 3. Update Verification Checks
    current_checks = {c.check_type: c for c in db_case.checks}
    new_services = set(case_data.services)
    
    # Remove checks that are no longer selected (only if they are still interim/pending)
    for check_type, check in current_checks.items():
        if check_type not in new_services:
            db.delete(check)
            
    # Add newly selected checks
    for service in new_services:
        if service not in current_checks:
            db_check = models.VerificationCheck(
                case_id=db_case.id,
                check_type=service,
                status=models.CheckStatus.INTERIM
            )
            db.add(db_check)
    
    db.commit()
    db.refresh(db_case)
    return db_case

@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(check_module_permission("bvs", "verification", action="write"))])
def delete_case(case_id: str, db: Session = Depends(get_db)):
    db_case = db.query(models.Case).filter(models.Case.id == case_id).first()
    if db_case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    
    # Delete linked checks first
    db.query(models.VerificationCheck).filter(models.VerificationCheck.case_id == case_id).delete()
    db.delete(db_case)
    db.commit()
    return None

@router.post("/{case_id}/merge-pdfs", dependencies=[Depends(check_module_permission("bvs", "verification", action="write"))])
def merge_pdfs(case_id: str, db: Session = Depends(get_db)):
    db_case = db.query(models.Case).filter(models.Case.id == case_id).first()
    if not db_case or not db_case.candidate:
        raise HTTPException(status_code=404, detail="Case or Candidate not found")
    
    docs = db_case.candidate.documents or []
    if not docs:
        raise HTTPException(status_code=400, detail="No documents available to merge")
    
    merger = PdfWriter()
    try:
        from PIL import Image
    except ImportError:
        pass
        
    for doc in docs:
        url = doc.get('url')
        if not url: continue
        
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                if url.lower().endswith('.pdf') or 'application/pdf' in response.headers.get('content-type', ''):
                    pdf_reader = PdfReader(BytesIO(response.content))
                    merger.append(pdf_reader)
                else:
                    try:
                        image = Image.open(BytesIO(response.content))
                        if image.mode != 'RGB':
                            image = image.convert('RGB')
                        img_pdf = BytesIO()
                        image.save(img_pdf, format='PDF')
                        img_pdf.seek(0)
                        merger.append(PdfReader(img_pdf))
                    except Exception as e:
                        import logging
                        logging.warning(f"Skipping non-pdf file {url}: {e}")
        except Exception as e:
            import logging
            logging.error(f"Failed to fetch {url}: {e}")
            
    output = BytesIO()
    merger.write(output)
    output.seek(0)
    
    return StreamingResponse(
        output, 
        media_type="application/pdf", 
        headers={"Content-Disposition": f"attachment; filename=merged_case_{case_id}.pdf"}
    )

@router.post("/bulk-allocate")
def bulk_allocate(data: Dict[str, Any], db: Session = Depends(get_db)):
    case_ids = data.get("case_ids", [])
    user_id = data.get("user_id")
    
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID is required")
    
    db.query(models.Case).filter(models.Case.id.in_(case_ids)).update({
        "assigned_to": user_id
    }, synchronize_session=False)
    
    db.commit()
    return {"message": f"Successfully allocated {len(case_ids)} cases"}
