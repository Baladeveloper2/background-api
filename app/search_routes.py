from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_, case, desc
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
    limit: Optional[int] = 10,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    search_type: Optional[str] = "all",
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(auth_routes.get_current_user)
):
    if not q or len(q) < 2:
        return { cat: [] for cat in ["candidates", "cases", "clients", "documents", "invoices", "verifiers", "reports", "insufficiencies", "executives", "users"] }

    q_exact = q
    q_starts = f"{q}%"
    q_filter = f"%{q}%"
    
    results = {}
    category = (category or "all").lower()
    search_type = (search_type or "all").lower()

    user_role = str(current_user.role.value if hasattr(current_user.role, 'value') else current_user.role).upper()
    is_customer = "CUSTOMER" in user_role or (current_user.role_rel and current_user.role_rel.name.upper() == "CUSTOMER")
    is_admin = user_role in ["SUPER_ADMIN", "ADMIN"]
    is_verifier = user_role == "VERIFIER"
    is_executive = user_role in ["MANAGER", "QA", "QC", "QC VERIFIER"]

    # Date filters helper
    def apply_dates(filters, date_field):
        if from_date:
            try:
                from_dt = datetime.strptime(from_date, "%Y-%m-%d")
                filters.append(date_field >= from_dt)
            except ValueError:
                filters.append(date_field >= from_date)
        if to_date:
            try:
                to_dt = datetime.strptime(to_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
                filters.append(date_field <= to_dt)
            except ValueError:
                filters.append(date_field <= to_date)

    # 1. Candidates
    if category in ["all", "candidates"]:
        cand_filters = []
        if is_customer:
            cand_filters.append(models.Case.customer_id == current_user.customer_id)
        elif is_executive:
            cand_filters.append(or_(models.Case.assigned_to == current_user.id, models.Case.finalized_by == current_user.id))
        elif is_verifier:
            cand_filters.append(models.Case.id.in_(select(models.VerificationCheck.case_id).where(models.VerificationCheck.assigned_verifier_id == current_user.id)))
        
        apply_dates(cand_filters, models.Case.received_date)

        score_expr = case(
            (models.Candidate.name.ilike(q_exact), 100),
            (models.Candidate.name.ilike(q_starts), 80),
            (models.Candidate.name.ilike(q_filter), 60),
            (models.Candidate.email.ilike(q_filter), 30),
            (models.Candidate.client_emp_code.ilike(q_filter), 20),
            (models.Candidate.phone.ilike(q_filter), 20),
            else_=0
        ).label('score')
        
        reason_expr = case(
            (models.Candidate.name.ilike(q_filter), "name"),
            (models.Candidate.email.ilike(q_filter), "email"),
            (models.Candidate.client_emp_code.ilike(q_filter), "code"),
            (models.Candidate.phone.ilike(q_filter), "phone"),
            else_="none"
        ).label('match_reason')

        cand_stmt = select(
            models.Candidate, models.Case.case_ref_no, models.Case.id.label("case_id"), score_expr, reason_expr
        ).join(
            models.Case, models.Case.candidate_id == models.Candidate.id
        ).filter(and_(*cand_filters, score_expr > 0)).order_by(desc(score_expr)).limit(limit)
        
        cand_res = await db.execute(cand_stmt)
        candidates_tuples = cand_res.all()
        results["candidates"] = [
            {
                "id": c.id, "name": c.name, "email": c.email, "phone": c.phone, "client_emp_code": c.client_emp_code,
                "case_ref_no": case_ref_no, "case_id": case_id, "score": score, "match_reason": reason
            } for c, case_ref_no, case_id, score, reason in candidates_tuples
        ]

    # 2. Cases
    if category in ["all", "cases"]:
        case_filters = []
        if is_customer:
            case_filters.append(models.Case.customer_id == current_user.customer_id)
        elif is_executive:
            case_filters.append(or_(models.Case.assigned_to == current_user.id, models.Case.finalized_by == current_user.id))
        elif is_verifier:
            case_filters.append(models.Case.id.in_(select(models.VerificationCheck.case_id).where(models.VerificationCheck.assigned_verifier_id == current_user.id)))
        apply_dates(case_filters, models.Case.received_date)

        score_expr = case(
            (models.Case.case_ref_no.ilike(q_exact), 100),
            (models.Case.case_ref_no.ilike(q_starts), 80),
            (models.Case.case_ref_no.ilike(q_filter), 60),
            (models.Candidate.name.ilike(q_filter), 60),
            (models.Case.file_no.ilike(q_filter), 20),
            (models.Candidate.client_emp_code.ilike(q_filter), 20),
            else_=0
        ).label('score')
        
        reason_expr = case(
            (models.Case.case_ref_no.ilike(q_filter), "name"),
            (models.Candidate.name.ilike(q_filter), "name"),
            (models.Case.file_no.ilike(q_filter), "code"),
            (models.Candidate.client_emp_code.ilike(q_filter), "code"),
            else_="none"
        ).label('match_reason')

        case_stmt = select(models.Case, score_expr, reason_expr).join(
            models.Candidate, models.Case.candidate_id == models.Candidate.id
        ).options(selectinload(models.Case.candidate)).filter(and_(*case_filters, score_expr > 0)).order_by(desc(score_expr)).limit(limit)
        
        case_res = await db.execute(case_stmt)
        cases_tuples = case_res.all()
        
        results["cases"] = []
        for case_obj, score, reason in cases_tuples:
            cand = case_obj.candidate
            results["cases"].append({
                "id": case_obj.id, "case_ref_no": case_obj.case_ref_no, "candidate_name": cand.name if cand else "Unknown",
                "client_emp_code": cand.client_emp_code if cand else None, "status": case_obj.status, "score": score, "match_reason": reason
            })

    # 3. Clients (Internal Only)
    if category in ["all", "clients"] and not is_customer:
        score_expr = case(
            (models.Customer.name.ilike(q_exact), 100),
            (models.Customer.name.ilike(q_starts), 80),
            (models.Customer.name.ilike(q_filter), 60),
            (models.Customer.email.ilike(q_filter), 30),
            (models.Customer.short_code.ilike(q_filter), 20),
            (models.Customer.contact_person.ilike(q_filter), 20),
            else_=0
        ).label('score')
        
        reason_expr = case(
            (models.Customer.name.ilike(q_filter), "name"),
            (models.Customer.email.ilike(q_filter), "email"),
            (models.Customer.short_code.ilike(q_filter), "code"),
            (models.Customer.contact_person.ilike(q_filter), "metadata"),
            else_="none"
        ).label('match_reason')

        cust_stmt = select(models.Customer, score_expr, reason_expr).filter(score_expr > 0).order_by(desc(score_expr)).limit(limit)
        cust_res = await db.execute(cust_stmt)
        customers_tuples = cust_res.all()
        results["clients"] = [
            {
                "id": cust.id, "name": cust.name, "short_code": cust.short_code,
                "email": cust.email, "city": cust.city, "score": score, "match_reason": reason
            } for cust, score, reason in customers_tuples
        ]

    # 4. Documents
    if category in ["all", "documents"]:
        docs = []
        # Client Docs
        cd_filters = []
        if is_customer: cd_filters.append(models.ClientDocument.customer_id == current_user.customer_id)
        apply_dates(cd_filters, models.ClientDocument.created_at)
        
        cd_score = case((models.ClientDocument.name.ilike(q_exact), 100), (models.ClientDocument.name.ilike(q_starts), 80), (models.ClientDocument.name.ilike(q_filter), 60), else_=0).label('score')
        cd_reason = case((models.ClientDocument.name.ilike(q_filter), "name"), else_="none").label('match_reason')
        
        cd_stmt = select(models.ClientDocument, cd_score, cd_reason).filter(and_(*cd_filters, cd_score > 0)).order_by(desc(cd_score)).limit(limit)
        cd_res = await db.execute(cd_stmt)
        for doc, score, reason in cd_res.all():
            docs.append({ "id": doc.id, "name": doc.name, "type": "client_document", "file_type": doc.file_type, "case_id": None, "case_ref_no": None, "candidate_name": None, "score": score, "match_reason": reason })
            
        # Verification Docs
        vd_filters = []
        if is_customer: vd_filters.append(models.Case.customer_id == current_user.customer_id)
        elif is_executive: vd_filters.append(or_(models.Case.assigned_to == current_user.id, models.Case.finalized_by == current_user.id))
        elif is_verifier: vd_filters.append(models.VerificationDocument.check_id.in_(select(models.VerificationCheck.id).where(models.VerificationCheck.assigned_verifier_id == current_user.id)))
        apply_dates(vd_filters, models.Case.received_date)

        vd_score = case((models.VerificationDocument.file_name.ilike(q_exact), 100), (models.VerificationDocument.file_name.ilike(q_starts), 80), (models.VerificationDocument.file_name.ilike(q_filter), 60), else_=0).label('score')
        vd_reason = case((models.VerificationDocument.file_name.ilike(q_filter), "name"), else_="none").label('match_reason')
        
        vd_stmt = select(
            models.VerificationDocument, models.Case.id.label("case_id"), models.Case.case_ref_no, models.Candidate.name.label("candidate_name"), vd_score, vd_reason
        ).join(models.VerificationCheck, models.VerificationDocument.check_id == models.VerificationCheck.id).join(models.Case, models.VerificationCheck.case_id == models.Case.id).join(models.Candidate, models.Case.candidate_id == models.Candidate.id)
        vd_stmt = vd_stmt.filter(and_(*vd_filters, vd_score > 0)).order_by(desc(vd_score)).limit(limit)
        
        vd_res = await db.execute(vd_stmt)
        for doc, case_id, case_ref_no, candidate_name, score, reason in vd_res.all():
            docs.append({ "id": doc.id, "name": doc.file_name, "type": "verification_document", "file_type": doc.file_type, "case_id": case_id, "case_ref_no": case_ref_no, "candidate_name": candidate_name, "score": score, "match_reason": reason })
            
        docs.sort(key=lambda x: x["score"], reverse=True)
        results["documents"] = docs[:limit]

    # 5. Invoices (Internal Only)
    if category in ["all", "invoices"] and not is_customer:
        score_expr = case(
            (models.Invoice.invoice_number.ilike(q_exact), 100),
            (models.Invoice.invoice_number.ilike(q_starts), 80),
            (models.Invoice.invoice_number.ilike(q_filter), 60),
            (models.Customer.name.ilike(q_filter), 60),
            else_=0
        ).label('score')
        reason_expr = case((models.Invoice.invoice_number.ilike(q_filter), "name"), (models.Customer.name.ilike(q_filter), "metadata"), else_="none").label('match_reason')

        inv_stmt = select(models.Invoice, score_expr, reason_expr).join(
            models.Customer, models.Invoice.client_id == models.Customer.id
        ).options(selectinload(models.Invoice.client)).filter(score_expr > 0).order_by(desc(score_expr)).limit(limit)
        
        inv_res = await db.execute(inv_stmt)
        results["invoices"] = []
        for inv, score, reason in inv_res.all():
            client = inv.client
            results["invoices"].append({
                "id": inv.id, "invoice_number": inv.invoice_number, "client_name": client.name if client else "Unknown",
                "total_amount": inv.total_amount, "status": inv.status, "score": score, "match_reason": reason
            })

    # 7. Verifiers
    if category in ["all", "verifiers"] and not is_customer:
        score_expr = case(
            (models.User.full_name.ilike(q_exact), 100),
            (models.User.full_name.ilike(q_starts), 80),
            (models.User.full_name.ilike(q_filter), 60),
            (models.User.email.ilike(q_filter), 30),
            else_=0
        ).label('score')
        reason_expr = case((models.User.full_name.ilike(q_filter), "name"), (models.User.email.ilike(q_filter), "email"), else_="none").label('match_reason')

        user_stmt = select(models.User, score_expr, reason_expr).filter(and_(models.User.role == UserRole.VERIFIER, score_expr > 0)).order_by(desc(score_expr)).limit(limit)
        user_res = await db.execute(user_stmt)
        results["verifiers"] = [
            { "id": u.id, "full_name": u.full_name, "email": u.email, "role": u.role, "score": score, "match_reason": reason } 
            for u, score, reason in user_res.all()
        ]

    # 8. Reports
    if category in ["all", "reports"] and not is_customer:
        score_expr = case(
            (models.Case.case_ref_no.ilike(q_exact), 100),
            (models.Case.case_ref_no.ilike(q_starts), 80),
            (models.Case.case_ref_no.ilike(q_filter), 60),
            (models.Candidate.name.ilike(q_filter), 60),
            else_=0
        ).label('score')
        reason_expr = case((models.Case.case_ref_no.ilike(q_filter), "name"), (models.Candidate.name.ilike(q_filter), "name"), else_="none").label('match_reason')

        report_stmt = select(models.Case, score_expr, reason_expr).join(models.Candidate, models.Case.candidate_id == models.Candidate.id).options(selectinload(models.Case.candidate)).filter(
            and_(or_(models.Case.status == CaseStatus.FINALIZED, models.Case.completed_date.isnot(None)), score_expr > 0)
        ).order_by(desc(score_expr)).limit(limit)
        
        report_res = await db.execute(report_stmt)
        results["reports"] = []
        for r, score, reason in report_res.all():
            cand = r.candidate
            results["reports"].append({ "id": r.id, "case_ref_no": r.case_ref_no, "candidate_name": cand.name if cand else "Unknown", "final_result": r.final_result, "score": score, "match_reason": reason })

    # 9. Insufficiencies
    if category in ["all", "insufficiencies"]:
        ins_filters = []
        if is_customer: ins_filters.append(models.Case.customer_id == current_user.customer_id)
        elif is_executive: ins_filters.append(or_(models.Case.assigned_to == current_user.id, models.Case.finalized_by == current_user.id))
        elif is_verifier: ins_filters.append(models.Case.id.in_(select(models.VerificationCheck.case_id).where(models.VerificationCheck.assigned_verifier_id == current_user.id)))
        
        score_expr = case(
            (models.Case.case_ref_no.ilike(q_exact), 100),
            (models.Candidate.name.ilike(q_starts), 80),
            (models.Candidate.name.ilike(q_filter), 60),
            (models.Insufficiency.message.ilike(q_filter), 10),
            else_=0
        ).label('score')
        reason_expr = case((models.Case.case_ref_no.ilike(q_filter), "name"), (models.Candidate.name.ilike(q_filter), "name"), (models.Insufficiency.message.ilike(q_filter), "metadata"), else_="none").label('match_reason')

        ins_stmt = select(models.Insufficiency, score_expr, reason_expr).join(models.Case, models.Insufficiency.case_id == models.Case.id).join(models.Candidate, models.Case.candidate_id == models.Candidate.id).options(
            selectinload(models.Insufficiency.case).selectinload(models.Case.candidate)
        ).filter(and_(*ins_filters, score_expr > 0)).order_by(desc(score_expr)).limit(limit)
        
        ins_res = await db.execute(ins_stmt)
        results["insufficiencies"] = [
            { "id": ins.id, "case_ref_no": ins.case.case_ref_no, "candidate_name": ins.case.candidate.name if ins.case.candidate else "Unknown", "message": ins.message, "status": ins.status, "is_resolved": ins.is_resolved, "case_id": ins.case_id, "score": score, "match_reason": reason } 
            for ins, score, reason in ins_res.all()
        ]

    # 10. Executives
    if category in ["all", "executives"] and not is_customer:
        score_expr = case(
            (models.User.full_name.ilike(q_exact), 100),
            (models.User.full_name.ilike(q_starts), 80),
            (models.User.full_name.ilike(q_filter), 60),
            (models.User.email.ilike(q_filter), 30),
            (models.User.phone.ilike(q_filter), 20),
            else_=0
        ).label('score')
        reason_expr = case((models.User.full_name.ilike(q_filter), "name"), (models.User.email.ilike(q_filter), "email"), (models.User.phone.ilike(q_filter), "phone"), else_="none").label('match_reason')

        exec_stmt = select(models.User, score_expr, reason_expr).filter(and_(models.User.role.in_([UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.MANAGER, UserRole.QC, UserRole.QA]), score_expr > 0)).order_by(desc(score_expr)).limit(limit)
        exec_res = await db.execute(exec_stmt)
        results["executives"] = [
            { "id": u.id, "full_name": u.full_name, "email": u.email, "phone": u.phone, "role": u.role, "score": score, "match_reason": reason } 
            for u, score, reason in exec_res.all()
        ]

    # 11. Users
    if category in ["all", "users"] and not is_customer:
        score_expr = case(
            (models.User.full_name.ilike(q_exact), 100),
            (models.User.full_name.ilike(q_starts), 80),
            (models.User.full_name.ilike(q_filter), 60),
            (models.User.email.ilike(q_filter), 30),
            (models.User.phone.ilike(q_filter), 20),
            else_=0
        ).label('score')
        reason_expr = case((models.User.full_name.ilike(q_filter), "name"), (models.User.email.ilike(q_filter), "email"), (models.User.phone.ilike(q_filter), "phone"), else_="none").label('match_reason')

        users_stmt = select(models.User, score_expr, reason_expr).filter(score_expr > 0).order_by(desc(score_expr)).limit(limit)
        users_res = await db.execute(users_stmt)
        results["users"] = [
            { "id": u.id, "full_name": u.full_name, "email": u.email, "phone": u.phone, "role": u.role, "score": score, "match_reason": reason } 
            for u, score, reason in users_res.all()
        ]

    all_categories = ["candidates", "cases", "clients", "documents", "invoices", "verifiers", "reports", "insufficiencies", "executives", "users"]
    for cat in all_categories:
        if cat not in results:
            results[cat] = []

    return results
