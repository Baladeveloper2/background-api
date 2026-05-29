from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_
from sqlalchemy.orm import selectinload
from typing import List, Optional, Dict, Any
from .database import get_async_db
from . import models, auth_routes
from .enums import UserRole, CaseStatus

router = APIRouter(prefix="/search", tags=["search"])

@router.get("")
async def search_all(
    q: str,
    category: Optional[str] = "all",
    limit: Optional[int] = 5,
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(auth_routes.get_current_user)
):
    if not q or len(q) < 2:
        return {
            "candidates": [],
            "cases": [],
            "clients": [],
            "documents": [],
            "invoices": [],
            "tasks": [],
            "verifiers": [],
            "reports": []
        }

    q_filter = f"%{q}%"
    results = {}
    category = (category or "all").lower()

    # 1. Candidates
    if category in ["all", "candidates"]:
        cand_stmt = select(models.Candidate).filter(
            or_(
                models.Candidate.name.ilike(q_filter),
                models.Candidate.email.ilike(q_filter),
                models.Candidate.phone.ilike(q_filter),
                models.Candidate.client_emp_code.ilike(q_filter)
            )
        ).limit(limit)
        cand_res = await db.execute(cand_stmt)
        candidates = cand_res.scalars().all()
        results["candidates"] = [
            {
                "id": c.id,
                "name": c.name,
                "email": c.email,
                "phone": c.phone,
                "client_emp_code": c.client_emp_code
            } for c in candidates
        ]

    # 2. Cases
    if category in ["all", "cases"]:
        case_stmt = select(models.Case).join(
            models.Candidate, models.Case.candidate_id == models.Candidate.id
        ).options(
            selectinload(models.Case.candidate)
        ).filter(
            or_(
                models.Case.case_ref_no.ilike(q_filter),
                models.Case.file_no.ilike(q_filter),
                models.Candidate.name.ilike(q_filter),
                models.Candidate.client_emp_code.ilike(q_filter)
            )
        ).limit(limit)
        case_res = await db.execute(case_stmt)
        cases = case_res.scalars().all()
        
        results["cases"] = []
        for case in cases:
            cand = case.candidate
            results["cases"].append({
                "id": case.id,
                "case_ref_no": case.case_ref_no,
                "candidate_name": cand.name if cand else "Unknown",
                "client_emp_code": cand.client_emp_code if cand else None,
                "status": case.status
            })

    # 3. Clients
    if category in ["all", "clients"]:
        cust_stmt = select(models.Customer).filter(
            or_(
                models.Customer.name.ilike(q_filter),
                models.Customer.email.ilike(q_filter),
                models.Customer.short_code.ilike(q_filter),
                models.Customer.contact_person.ilike(q_filter)
            )
        ).limit(limit)
        cust_res = await db.execute(cust_stmt)
        customers = cust_res.scalars().all()
        results["clients"] = [
            {
                "id": cust.id,
                "name": cust.name,
                "short_code": cust.short_code,
                "email": cust.email,
                "city": cust.city
            } for cust in customers
        ]

    # 4. Documents
    if category in ["all", "documents"]:
        # Search ClientDocument
        cd_stmt = select(models.ClientDocument).filter(
            models.ClientDocument.name.ilike(q_filter)
        ).limit(limit)
        cd_res = await db.execute(cd_stmt)
        client_docs = cd_res.scalars().all()
        
        # Search VerificationDocument
        vd_stmt = select(models.VerificationDocument).filter(
            models.VerificationDocument.file_name.ilike(q_filter)
        ).limit(limit)
        vd_res = await db.execute(vd_stmt)
        verification_docs = vd_res.scalars().all()
        
        docs = []
        for doc in client_docs:
            docs.append({
                "id": doc.id,
                "name": doc.name,
                "type": "client_document",
                "file_type": doc.file_type
            })
        for doc in verification_docs:
            docs.append({
                "id": doc.id,
                "name": doc.file_name,
                "type": "verification_document",
                "file_type": doc.file_type
            })
        results["documents"] = docs[:limit]

    # 5. Invoices
    if category in ["all", "invoices"]:
        inv_stmt = select(models.Invoice).join(
            models.Customer, models.Invoice.client_id == models.Customer.id
        ).options(
            selectinload(models.Invoice.client)
        ).filter(
            or_(
                models.Invoice.invoice_number.ilike(q_filter),
                models.Customer.name.ilike(q_filter)
            )
        ).limit(limit)
        inv_res = await db.execute(inv_stmt)
        invoices = inv_res.scalars().all()
        
        results["invoices"] = []
        for inv in invoices:
            client = inv.client
            results["invoices"].append({
                "id": inv.id,
                "invoice_number": inv.invoice_number,
                "client_name": client.name if client else "Unknown",
                "total_amount": inv.total_amount,
                "status": inv.status
            })

    # 6. Tasks (Verification Checks)
    if category in ["all", "tasks"]:
        check_stmt = select(models.VerificationCheck).options(
            selectinload(models.VerificationCheck.case).selectinload(models.Case.candidate)
        ).filter(
            or_(
                models.VerificationCheck.check_type.ilike(q_filter),
                models.VerificationCheck.verifier_remarks.ilike(q_filter)
            )
        ).limit(limit)
        check_res = await db.execute(check_stmt)
        checks = check_res.scalars().all()
        
        results["tasks"] = []
        for check in checks:
            case = check.case
            cand = case.candidate if case else None
            results["tasks"].append({
                "id": check.id,
                "check_type": check.check_type,
                "case_id": check.case_id,
                "candidate_name": cand.name if cand else "Unknown",
                "status": check.status
            })

    # 7. Verifiers
    if category in ["all", "verifiers"]:
        user_stmt = select(models.User).filter(
            and_(
                models.User.role == UserRole.VERIFIER,
                or_(
                    models.User.full_name.ilike(q_filter),
                    models.User.email.ilike(q_filter)
                )
            )
        ).limit(limit)
        user_res = await db.execute(user_stmt)
        users = user_res.scalars().all()
        results["verifiers"] = [
            {
                "id": u.id,
                "full_name": u.full_name,
                "email": u.email,
                "role": u.role
            } for u in users
        ]

    # 8. Reports (Finalized/Completed Cases)
    if category in ["all", "reports"]:
        report_stmt = select(models.Case).join(
            models.Candidate, models.Case.candidate_id == models.Candidate.id
        ).options(
            selectinload(models.Case.candidate)
        ).filter(
            and_(
                or_(
                    models.Case.status == CaseStatus.FINALIZED,
                    models.Case.completed_date.isnot(None)
                ),
                or_(
                    models.Case.case_ref_no.ilike(q_filter),
                    models.Candidate.name.ilike(q_filter)
                )
            )
        ).limit(limit)
        report_res = await db.execute(report_stmt)
        reports = report_res.scalars().all()
        
        results["reports"] = []
        for r in reports:
            cand = r.candidate
            results["reports"].append({
                "id": r.id,
                "case_ref_no": r.case_ref_no,
                "candidate_name": cand.name if cand else "Unknown",
                "final_result": r.final_result
            })

    # Ensure all categories exist in results
    all_categories = ["candidates", "cases", "clients", "documents", "invoices", "tasks", "verifiers", "reports"]
    for cat in all_categories:
        if cat not in results:
            results[cat] = []

    return results
