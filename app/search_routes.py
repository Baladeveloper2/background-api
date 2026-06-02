from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_
from sqlalchemy.orm import selectinload
from typing import List, Optional, Dict, Any
from datetime import datetime
from .database import get_async_db
from . import models, auth_routes
from .enums import UserRole, CaseStatus

router = APIRouter(prefix="/search", tags=["search"])

@router.get("")
async def search_all(
    q: str,
    category: Optional[str] = "all",
    limit: Optional[int] = 5,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    search_type: Optional[str] = "all",
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
    search_type = (search_type or "all").lower()

    user_role = str(current_user.role.value if hasattr(current_user.role, 'value') else current_user.role).upper()
    is_customer = "CUSTOMER" in user_role or (current_user.role_rel and current_user.role_rel.name.upper() == "CUSTOMER")

    # 1. Candidates
    if category in ["all", "candidates"]:
        cand_filters = []
        needs_case_join = True

        if search_type == "case_ref":
            cand_filters.append(models.Case.case_ref_no.ilike(q_filter))
        else:
            cand_or_conditions = []
            if search_type == "all" or search_type == "name":
                cand_or_conditions.append(models.Candidate.name.ilike(q_filter))
            if search_type == "all" or search_type == "emp_code":
                cand_or_conditions.append(models.Candidate.client_emp_code.ilike(q_filter))
            if not cand_or_conditions:
                cand_or_conditions.append(models.Candidate.name.ilike(q_filter))
            cand_filters.append(or_(*cand_or_conditions))

        if is_customer:
            cand_filters.append(models.Case.customer_id == current_user.customer_id)

        if from_date:
            try:
                from_dt = datetime.strptime(from_date, "%Y-%m-%d")
                cand_filters.append(models.Case.received_date >= from_dt)
            except ValueError:
                cand_filters.append(models.Case.received_date >= from_date)
        if to_date:
            try:
                to_dt = datetime.strptime(to_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
                cand_filters.append(models.Case.received_date <= to_dt)
            except ValueError:
                cand_filters.append(models.Case.received_date <= to_date)

        if needs_case_join:
            cand_stmt = select(models.Candidate, models.Case.case_ref_no, models.Case.id.label("case_id")).join(
                models.Case, models.Case.candidate_id == models.Candidate.id
            ).filter(and_(*cand_filters)).distinct().limit(limit)
            
            cand_res = await db.execute(cand_stmt)
            candidates_tuples = cand_res.all()
            results["candidates"] = [
                {
                    "id": c.id,
                    "name": c.name,
                    "email": c.email,
                    "phone": c.phone,
                    "client_emp_code": c.client_emp_code,
                    "case_ref_no": case_ref_no,
                    "case_id": case_id
                } for c, case_ref_no, case_id in candidates_tuples
            ]
        else:
            cand_stmt = select(models.Candidate).filter(and_(*cand_filters)).limit(limit)
            cand_res = await db.execute(cand_stmt)
            candidates = cand_res.scalars().all()
            results["candidates"] = [
                {
                    "id": c.id,
                    "name": c.name,
                    "email": c.email,
                    "phone": c.phone,
                    "client_emp_code": c.client_emp_code,
                    "case_ref_no": "N/A",
                    "case_id": None
                } for c in candidates
            ]

    # 2. Cases
    if category in ["all", "cases"]:
        case_filters = [
            or_(
                models.Case.case_ref_no.ilike(q_filter),
                models.Case.file_no.ilike(q_filter),
                models.Candidate.name.ilike(q_filter),
                models.Candidate.client_emp_code.ilike(q_filter)
            )
        ]
        if is_customer:
            case_filters.append(models.Case.customer_id == current_user.customer_id)
        if from_date:
            try:
                from_dt = datetime.strptime(from_date, "%Y-%m-%d")
                case_filters.append(models.Case.received_date >= from_dt)
            except ValueError:
                case_filters.append(models.Case.received_date >= from_date)
        if to_date:
            try:
                to_dt = datetime.strptime(to_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
                case_filters.append(models.Case.received_date <= to_dt)
            except ValueError:
                case_filters.append(models.Case.received_date <= to_date)

        case_stmt = select(models.Case).join(
            models.Candidate, models.Case.candidate_id == models.Candidate.id
        ).options(
            selectinload(models.Case.candidate)
        ).filter(and_(*case_filters)).limit(limit)
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

    # 3. Clients (Internal Only)
    if category in ["all", "clients"] and not is_customer:
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
        cd_filters = [models.ClientDocument.name.ilike(q_filter)]
        if is_customer:
            cd_filters.append(models.ClientDocument.customer_id == current_user.customer_id)
        if from_date:
            try:
                from_dt = datetime.strptime(from_date, "%Y-%m-%d")
                cd_filters.append(models.ClientDocument.created_at >= from_dt)
            except ValueError:
                cd_filters.append(models.ClientDocument.created_at >= from_date)
        if to_date:
            try:
                to_dt = datetime.strptime(to_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
                cd_filters.append(models.ClientDocument.created_at <= to_dt)
            except ValueError:
                cd_filters.append(models.ClientDocument.created_at <= to_date)
        cd_stmt = select(models.ClientDocument).filter(and_(*cd_filters)).limit(limit)
        cd_res = await db.execute(cd_stmt)
        client_docs = cd_res.scalars().all()
        
        # Search VerificationDocument
        vd_stmt = select(
            models.VerificationDocument,
            models.Case.id.label("case_id"),
            models.Case.case_ref_no,
            models.Candidate.name.label("candidate_name")
        ).join(
            models.VerificationCheck, models.VerificationDocument.check_id == models.VerificationCheck.id
        ).join(
            models.Case, models.VerificationCheck.case_id == models.Case.id
        ).join(
            models.Candidate, models.Case.candidate_id == models.Candidate.id
        )
        vd_filters = [models.VerificationDocument.file_name.ilike(q_filter)]
        if is_customer:
            vd_filters.append(models.Case.customer_id == current_user.customer_id)
        if from_date:
            try:
                from_dt = datetime.strptime(from_date, "%Y-%m-%d")
                vd_filters.append(models.Case.received_date >= from_dt)
            except ValueError:
                vd_filters.append(models.Case.received_date >= from_date)
        if to_date:
            try:
                to_dt = datetime.strptime(to_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
                vd_filters.append(models.Case.received_date <= to_dt)
            except ValueError:
                vd_filters.append(models.Case.received_date <= to_date)
        vd_stmt = vd_stmt.filter(and_(*vd_filters)).limit(limit)
        vd_res = await db.execute(vd_stmt)
        verification_docs_tuples = vd_res.all()
        
        docs = []
        for doc in client_docs:
            docs.append({
                "id": doc.id,
                "name": doc.name,
                "type": "client_document",
                "file_type": doc.file_type,
                "case_id": None,
                "case_ref_no": None,
                "candidate_name": None
            })
        for doc, case_id, case_ref_no, candidate_name in verification_docs_tuples:
            docs.append({
                "id": doc.id,
                "name": doc.file_name,
                "type": "verification_document",
                "file_type": doc.file_type,
                "case_id": case_id,
                "case_ref_no": case_ref_no,
                "candidate_name": candidate_name
            })
        results["documents"] = docs[:limit]

    # 5. Invoices (Internal Only)
    if category in ["all", "invoices"] and not is_customer:
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

    # 6. Tasks (Internal Only)
    if category in ["all", "tasks"] and not is_customer:
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

    # 7. Verifiers (Internal Only)
    if category in ["all", "verifiers"] and not is_customer:
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

    # 8. Reports (Internal Only)
    if category in ["all", "reports"] and not is_customer:
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

    # 9. Insufficiencies
    if category in ["all", "insufficiencies"]:
        ins_filters = []
        if is_customer:
            ins_filters.append(models.Case.customer_id == current_user.customer_id)
        
        ins_filters.append(
            or_(
                models.Case.case_ref_no.ilike(q_filter),
                models.Candidate.name.ilike(q_filter),
                models.Insufficiency.message.ilike(q_filter)
            )
        )
        
        ins_stmt = select(models.Insufficiency).join(
            models.Case, models.Insufficiency.case_id == models.Case.id
        ).join(
            models.Candidate, models.Case.candidate_id == models.Candidate.id
        ).options(
            selectinload(models.Insufficiency.case).selectinload(models.Case.candidate)
        ).filter(and_(*ins_filters)).distinct().limit(limit)
        
        ins_res = await db.execute(ins_stmt)
        insufficiencies = ins_res.scalars().all()
        
        results["insufficiencies"] = [
            {
                "id": ins.id,
                "case_ref_no": ins.case.case_ref_no,
                "candidate_name": ins.case.candidate.name if ins.case.candidate else "Unknown",
                "message": ins.message,
                "status": ins.status,
                "is_resolved": ins.is_resolved,
                "case_id": ins.case_id
            } for ins in insufficiencies
        ]

    # Ensure all categories exist in results
    all_categories = ["candidates", "cases", "clients", "documents", "invoices", "tasks", "verifiers", "reports", "insufficiencies"]
    for cat in all_categories:
        if cat not in results:
            results[cat] = []

    return results
