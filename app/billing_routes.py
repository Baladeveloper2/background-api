from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.orm import joinedload
from . import models, schemas
from .database import get_async_db
from .auth_routes import check_module_permission, get_current_user
from datetime import datetime
from typing import Optional, List

router = APIRouter(
    prefix="/billing",
    tags=["Billing"]
)

@router.get("/invoices", dependencies=[Depends(check_module_permission("bvs", "billing", action="read"))])
async def get_billing_summary(
    customer_id: Optional[str] = None,
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None, ge=2000),
    db: AsyncSession = Depends(get_async_db)
):
    # Default to current month/year if not provided
    now = datetime.now()
    month = month or now.month
    year = year or now.year
    
    # Logic: Sum up 'rate' of all checks in 'COMPLETED' cases for that month/customer
    # Since checks have their own rates, we sum VerificationCheck.rate
    
    stmt = (
        select(
            models.Customer.name.label("customer_name"),
            models.Customer.id.label("customer_id"),
            func.count(models.Case.id).label("total_cases"),
            func.sum(models.VerificationCheck.rate).label("total_billing")
        )
        .join(models.Case, models.Customer.id == models.Case.customer_id)
        .join(models.VerificationCheck, models.Case.id == models.VerificationCheck.case_id)
        .filter(models.Case.status == "COMPLETED")
        # For simplicity, filter by Case.completed_date
        .filter(func.extract('month', models.Case.completed_date) == month)
        .filter(func.extract('year', models.Case.completed_date) == year)
    )
    
    if customer_id:
        stmt = stmt.filter(models.Customer.id == customer_id)
        
    stmt = stmt.group_by(models.Customer.id, models.Customer.name)
    
    res = await db.execute(stmt)
    results = res.all()
    
    return [
        {
            "customer_name": r.customer_name,
            "customer_id": r.customer_id,
            "total_cases": r.total_cases,
            "total_billing": float(r.total_billing or 0),
            "period": f"{month}/{year}"
        } for r in results
    ]

@router.get("/case-ledger/{customer_id}", dependencies=[Depends(check_module_permission("bvs", "billing", action="read"))])
async def get_customer_ledger(customer_id: str, db: AsyncSession = Depends(get_async_db)):
    stmt = (
        select(models.Case)
        .options(joinedload(models.Case.candidate), joinedload(models.Case.checks))
        .filter(models.Case.customer_id == customer_id)
        .filter(models.Case.status == "COMPLETED")
        .order_by(models.Case.completed_date.desc())
        .limit(100)
    )
    
    res = await db.execute(stmt)
    cases = res.unique().scalars().all()
    
    ledger = []
    for c in cases:
        case_total = sum(chk.rate or 0 for chk in c.checks)
        ledger.append({
            "case_ref": c.case_ref_no,
            "candidate": c.candidate.name if c.candidate else "Unknown",
            "completed_at": c.completed_date,
            "checks": [chk.check_type for chk in c.checks],
            "billing_amount": float(case_total)
        })
        
    return ledger
