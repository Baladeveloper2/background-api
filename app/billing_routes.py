from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, update
from sqlalchemy.orm import joinedload
from . import models, database
from .database import get_async_db
from .auth_routes import check_module_permission, get_current_user
from datetime import datetime, timedelta
import uuid
import json
from typing import Optional, List, Dict, Any

router = APIRouter(
    prefix="/billing",
    tags=["Billing"]
)

# All terminal case statuses that are considered completed/billable
FINAL_STATUSES = [
    'FINALIZED', 'COMPLETED', 'POSITIVE', 'NEGATIVE',
    'DISCREPANCY', 'UNABLE TO VERIFY', 'QC_VERIFIED', 'CLOSED'
]

@router.get("/dashboard-stats")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Fetch Enterprise Billing Summary stats.
    Calculates active clients, billable cases, pending invoices, paid invoices, monthly revenue, outstanding amount.
    """
    # 1. Active Clients Count
    clients_stmt = select(func.count(models.Customer.id)).filter(models.Customer.status == "ACTIVE")
    clients_res = await db.execute(clients_stmt)
    active_clients = clients_res.scalar() or 0

    # 2. Billable Cases (Cases completed but not invoiced)
    # Only completed/finalized cases become billable
    billable_stmt = (
        select(func.count(models.Case.id))
        .filter(models.Case.status.in_(FINAL_STATUSES))
        .filter(models.Case.is_invoiced == 0)
        .filter(models.Case.is_billable == 1)
    )
    billable_res = await db.execute(billable_stmt)
    billable_cases = billable_res.scalar() or 0

    # 3. Pending Invoices (Draft, Generated, Sent)
    pending_stmt = (
        select(func.count(models.Invoice.id))
        .filter(models.Invoice.status.in_(["DRAFT", "GENERATED", "SENT"]))
    )
    pending_res = await db.execute(pending_stmt)
    pending_invoices = pending_res.scalar() or 0

    # 4. Paid Invoices Count
    paid_stmt = select(func.count(models.Invoice.id)).filter(models.Invoice.status == "PAID")
    paid_res = await db.execute(paid_stmt)
    paid_invoices = paid_res.scalar() or 0

    # 5. Monthly Revenue (total amount of invoices generated or paid this month)
    now = datetime.now()
    start_of_month = datetime(now.year, now.month, 1)
    revenue_stmt = (
        select(func.sum(models.Invoice.total_amount))
        .filter(models.Invoice.generated_at >= start_of_month)
        .filter(models.Invoice.status != "DRAFT")
    )
    revenue_res = await db.execute(revenue_stmt)
    monthly_revenue = float(revenue_res.scalar() or 0)

    # 6. Outstanding Amount (invoices not paid, excluding DRAFT)
    outstanding_stmt = (
        select(func.sum(models.Invoice.total_amount))
        .filter(models.Invoice.status.in_(["GENERATED", "SENT", "OVERDUE"]))
    )
    outstanding_res = await db.execute(outstanding_stmt)
    outstanding_amount = float(outstanding_res.scalar() or 0)

    return {
        "active_clients": active_clients,
        "billable_cases": billable_cases,
        "pending_invoices": pending_invoices,
        "paid_invoices": paid_invoices,
        "monthly_revenue": monthly_revenue,
        "outstanding_amount": outstanding_amount
    }


@router.get("/clients")
async def get_billing_clients(
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Get a list of all active clients with their billing configurations,
    active billable cases count, and pending invoice totals.
    """
    # Fetch all active clients
    stmt = select(models.Customer).filter(models.Customer.status == "ACTIVE").order_by(models.Customer.name.asc())
    res = await db.execute(stmt)
    clients = res.scalars().all()

    results = []
    for client in clients:
        # Get count of completed, non-invoiced cases
        billable_stmt = (
            select(func.count(models.Case.id))
            .filter(models.Case.customer_id == client.id)
            .filter(models.Case.status.in_(FINAL_STATUSES))
            .filter(models.Case.is_invoiced == 0)
            .filter(models.Case.is_billable == 1)
        )
        billable_res = await db.execute(billable_stmt)
        billable_count = billable_res.scalar() or 0

        # Get outstanding invoices sum
        outstanding_stmt = (
            select(func.sum(models.Invoice.total_amount))
            .filter(models.Invoice.client_id == client.id)
            .filter(models.Invoice.status.in_(["GENERATED", "SENT", "OVERDUE"]))
        )
        outstanding_res = await db.execute(outstanding_stmt)
        outstanding_sum = float(outstanding_res.scalar() or 0)

        # Default configuration
        default_config = {
            "billingCycle": "MONTHLY",
            "delayDays": 0,
            "dueDays": 15,
            "gstPercentage": 18.0,
            "currency": "INR",
            "autoGenerateInvoice": False,
            "invoiceGenerationDay": 30,
            "invoicePrefix": "INV",
            "rateCardId": "STANDARD",
            "stateName": "",
            "stateCode": ""
        }
        
        cfg = client.billing_config or {}
        merged_cfg = {**default_config, **cfg}

        results.append({
            "id": client.id,
            "name": client.name,
            "short_code": client.short_code,
            "contact_person": client.contact_person,
            "email": client.email,
            "phone": client.phone,
            "address": client.address,
            "gst_number": client.gst_number,
            "billing_config": merged_cfg,
            "billable_cases_count": billable_count,
            "outstanding_amount": outstanding_sum
        })
    return results


@router.post("/clients/{customer_id}/config")
async def update_client_billing_config(
    customer_id: str,
    payload: Dict[str, Any] = Body(...),
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Update a client's billing configuration and GST number.
    """
    stmt = select(models.Customer).filter(models.Customer.id == customer_id)
    res = await db.execute(stmt)
    client = res.scalar()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    if "gst_number" in payload:
        client.gst_number = payload["gst_number"]
    
    if "billing_config" in payload:
        current_cfg = client.billing_config or {}
        client.billing_config = {**current_cfg, **payload["billing_config"]}

    await db.commit()
    return {"status": "success", "message": "Client billing configuration updated successfully"}


@router.get("/eligible-cases")
async def get_eligible_cases(
    client_id: str,
    billing_cycle: Optional[str] = None,
    start_date: Optional[str] = None, # YYYY-MM-DD
    end_date: Optional[str] = None,   # YYYY-MM-DD
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Fetch all completed, non-invoiced cases for a client that are eligible for invoicing.
    Filters:
    - completed/finalized (status == 'COMPLETED')
    - is_invoiced == 0
    - completed_date inside the specified billing period (if provided)
    """
    stmt = (
        select(models.Case)
        .options(joinedload(models.Case.candidate), joinedload(models.Case.checks))
        .filter(models.Case.customer_id == client_id)
        .filter(models.Case.status.in_(FINAL_STATUSES))
        .filter(models.Case.is_invoiced == 0)
        .filter(models.Case.is_billable == 1)
    )

    if start_date:
        s_date = datetime.strptime(start_date, "%Y-%m-%d")
        stmt = stmt.filter(models.Case.completed_date >= s_date)
    if end_date:
        e_date = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        stmt = stmt.filter(models.Case.completed_date < e_date)

    stmt = stmt.order_by(models.Case.completed_date.asc())
    res = await db.execute(stmt)
    cases = res.unique().scalars().all()

    results = []
    for case in cases:
        # Calculate dynamic billing amount:
        # Sum of check rates, falling back to batch.case_rate, falling back to a standard default
        check_rates_sum = sum(float(chk.rate or 0) for chk in case.checks)
        
        # Resolve case rate: if direct billing_amount is set, use it.
        # Otherwise, if check rates sum > 0, use checks rate sum.
        # Otherwise, fall back to case batch rate.
        rate = float(case.billing_amount or 0)
        if rate <= 0:
            if check_rates_sum > 0:
                rate = check_rates_sum
            elif case.batch and case.batch.case_rate:
                rate = float(case.batch.case_rate)
            else:
                rate = 300.0 # Default fallback rate

        checks_summary = ", ".join([chk.check_type for chk in case.checks]) if case.checks else "Basic Verification"

        results.append({
            "id": case.id,
            "candidate_name": case.candidate.name if case.candidate else "Unknown Candidate",
            "case_ref": case.case_ref_no,
            "check_type": checks_summary,
            "completed_at": case.completed_date.isoformat() if case.completed_date else None,
            "rate": rate,
            "amount": rate
        })
    return results


@router.post("/generate-invoice")
async def generate_invoice(
    client_id: str = Body(...),
    billing_cycle: str = Body(...),
    billing_period_from: str = Body(...), # YYYY-MM-DD
    billing_period_to: str = Body(...),   # YYYY-MM-DD
    case_ids: Optional[List[str]] = Body(None),
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Generate a single consolidated invoice grouping multiple finalized cases.
    Prevent duplicate invoicing strictly by checking and locking is_invoiced = 1.
    """
    # 1. Fetch Client info
    client_stmt = select(models.Customer).filter(models.Customer.id == client_id)
    client_res = await db.execute(client_stmt)
    client = client_res.scalar()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # 2. Fetch Cases to invoice
    # If case_ids list is not provided, fetch all eligible cases in the period
    stmt = (
        select(models.Case)
        .options(joinedload(models.Case.checks), joinedload(models.Case.candidate))
        .filter(models.Case.customer_id == client_id)
        .filter(models.Case.status.in_(FINAL_STATUSES))
        .filter(models.Case.is_invoiced == 0)
        .filter(models.Case.is_billable == 1)
    )

    if case_ids:
        stmt = stmt.filter(models.Case.id.in_(case_ids))
    else:
        s_date = datetime.strptime(billing_period_from, "%Y-%m-%d")
        e_date = datetime.strptime(billing_period_to, "%Y-%m-%d") + timedelta(days=1)
        stmt = stmt.filter(models.Case.completed_date >= s_date).filter(models.Case.completed_date < e_date)

    res = await db.execute(stmt)
    cases = res.unique().scalars().all()

    if not cases:
        raise HTTPException(status_code=400, detail="No eligible non-invoiced cases found for this period.")

    # 3. Calculate Totals
    subtotal = 0.0
    case_rate_mappings = []

    for case in cases:
        # Prevent double invoicing checks
        if case.is_invoiced == 1 or case.invoice_id is not None:
            raise HTTPException(status_code=400, detail=f"Case {case.case_ref_no} is already invoiced!")

        # Rates resolution
        check_rates_sum = sum(float(chk.rate or 0) for chk in case.checks)
        rate = float(case.billing_amount or 0)
        if rate <= 0:
            if check_rates_sum > 0:
                rate = check_rates_sum
            elif case.batch and case.batch.case_rate:
                rate = float(case.batch.case_rate)
            else:
                rate = 300.0 # Default standard fallback

        subtotal += rate
        case_rate_mappings.append((case, rate))

    # 4. Resolve GST and final invoice numbers
    cfg = client.billing_config or {}
    gst_percent = float(cfg.get("gstPercentage", 18.0))
    prefix = str(cfg.get("invoicePrefix", "INV"))
    due_days = int(cfg.get("dueDays", 15))

    gst_amount = round((subtotal * gst_percent / 100.0), 2)
    total_amount = round((subtotal + gst_amount), 2)

    # Generate sequential or unique invoice number
    now = datetime.now()
    month_str = now.strftime("%Y%m")
    
    # Count existing invoices this month to generate sequence
    invoice_count_stmt = select(func.count(models.Invoice.id)).filter(models.Invoice.invoice_number.like(f"{prefix}-{month_str}-%"))
    invoice_count_res = await db.execute(invoice_count_stmt)
    seq = (invoice_count_res.scalar() or 0) + 1
    invoice_no = f"{prefix}-{month_str}-{seq:04d}"

    invoice_id = str(uuid.uuid4())
    due_date = now + timedelta(days=due_days)

    # 5. Create Invoice record
    invoice = models.Invoice(
        id=invoice_id,
        invoice_number=invoice_no,
        client_id=client_id,
        billing_cycle=billing_cycle,
        billing_period_from=datetime.strptime(billing_period_from, "%Y-%m-%d"),
        billing_period_to=datetime.strptime(billing_period_to, "%Y-%m-%d"),
        subtotal=subtotal,
        gst_amount=gst_amount,
        total_amount=total_amount,
        generated_at=now,
        due_date=due_date,
        status="GENERATED",
        generated_by=current_user.id
    )
    db.add(invoice)

    # 6. Lock and Update cases
    for case, rate in case_rate_mappings:
        case.is_invoiced = 1
        case.invoice_id = invoice_id
        case.billed_at = now
        case.billing_amount = rate

    await db.commit()

    return {
        "status": "success",
        "message": "Invoice generated successfully",
        "invoice": {
            "id": invoice_id,
            "invoice_number": invoice_no,
            "subtotal": subtotal,
            "gst_amount": gst_amount,
            "total_amount": total_amount,
            "due_date": due_date.isoformat(),
            "linked_cases_count": len(cases)
        }
    }


@router.get("/invoices")
async def list_invoices(
    client_id: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    List all generated invoices with paginated, filtered, and search support.
    """
    stmt = (
        select(models.Invoice)
        .options(joinedload(models.Invoice.client), joinedload(models.Invoice.creator))
        .order_by(desc(models.Invoice.generated_at))
    )

    if client_id:
        stmt = stmt.filter(models.Invoice.client_id == client_id)
    if status:
        stmt = stmt.filter(models.Invoice.status == status)

    # Total Count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    count_res = await db.execute(count_stmt)
    total_count = count_res.scalar() or 0

    # Pagination
    stmt = stmt.offset((page - 1) * limit).limit(limit)
    res = await db.execute(stmt)
    invoices = res.unique().scalars().all()

    results = []
    for inv in invoices:
        # Get count of linked cases
        cases_count_stmt = select(func.count(models.Case.id)).filter(models.Case.invoice_id == inv.id)
        cases_count_res = await db.execute(cases_count_stmt)
        cases_count = cases_count_res.scalar() or 0

        results.append({
            "id": inv.id,
            "invoice_number": inv.invoice_number,
            "client_name": inv.client.name if inv.client else "Unknown Client",
            "billing_cycle": inv.billing_cycle,
            "billing_period_from": inv.billing_period_from.isoformat() if inv.billing_period_from else None,
            "billing_period_to": inv.billing_period_to.isoformat() if inv.billing_period_to else None,
            "subtotal": inv.subtotal,
            "gst_amount": inv.gst_amount,
            "total_amount": inv.total_amount,
            "status": inv.status,
            "generated_at": inv.generated_at.isoformat() if inv.generated_at else None,
            "due_date": inv.due_date.isoformat() if inv.due_date else None,
            "generated_by_name": inv.creator.full_name if inv.creator else "System",
            "cases_count": cases_count
        })

    return {
        "total": total_count,
        "page": page,
        "limit": limit,
        "data": results
    }


@router.get("/invoices/{invoice_id}")
async def get_invoice_details(
    invoice_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Get full details of a specific invoice, including the list of linked verification cases.
    """
    stmt = (
        select(models.Invoice)
        .options(joinedload(models.Invoice.client), joinedload(models.Invoice.creator))
        .filter(models.Invoice.id == invoice_id)
    )
    res = await db.execute(stmt)
    inv = res.scalar()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # Fetch all linked cases
    cases_stmt = (
        select(models.Case)
        .options(joinedload(models.Case.candidate), joinedload(models.Case.checks))
        .filter(models.Case.invoice_id == invoice_id)
        .order_by(models.Case.completed_date.asc())
    )
    cases_res = await db.execute(cases_stmt)
    cases = cases_res.unique().scalars().all()

    cases_list = []
    for c in cases:
        checks_summary = ", ".join([chk.check_type for chk in c.checks]) if c.checks else "Basic Verification"
        cases_list.append({
            "id": c.id,
            "candidate_name": c.candidate.name if c.candidate else "Unknown Candidate",
            "case_ref": c.case_ref_no,
            "check_type": checks_summary,
            "completed_at": c.completed_date.isoformat() if c.completed_date else None,
            "amount": c.billing_amount
        })

    return {
        "id": inv.id,
        "invoice_number": inv.invoice_number,
        "client_id": inv.client_id,
        "client_name": inv.client.name if inv.client else "Unknown Client",
        "client_gst": inv.client.gst_number if inv.client else None,
        "client_address": inv.client.address if inv.client else None,
        "client_state": inv.client.billing_config.get("stateName") if (inv.client and inv.client.billing_config) else None,
        "client_state_code": inv.client.billing_config.get("stateCode") if (inv.client and inv.client.billing_config) else None,
        "billing_cycle": inv.billing_cycle,
        "billing_period_from": inv.billing_period_from.isoformat() if inv.billing_period_from else None,
        "billing_period_to": inv.billing_period_to.isoformat() if inv.billing_period_to else None,
        "subtotal": inv.subtotal,
        "gst_amount": inv.gst_amount,
        "total_amount": inv.total_amount,
        "status": inv.status,
        "generated_at": inv.generated_at.isoformat() if inv.generated_at else None,
        "due_date": inv.due_date.isoformat() if inv.due_date else None,
        "generated_by_name": inv.creator.full_name if inv.creator else "System",
        "paid_at": inv.paid_at.isoformat() if inv.paid_at else None,
        "cases": cases_list
    }


@router.post("/invoices/{invoice_id}/mark-paid")
async def mark_invoice_paid(
    invoice_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Mark an invoice as PAID. Invoice records must always remain immutable after payment.
    """
    stmt = select(models.Invoice).filter(models.Invoice.id == invoice_id)
    res = await db.execute(stmt)
    inv = res.scalar()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if inv.status == "PAID":
        raise HTTPException(status_code=400, detail="Invoice is already paid and locked!")

    inv.status = "PAID"
    inv.paid_at = datetime.utcnow()
    inv.modified_by = current_user.id

    await db.commit()
    return {"status": "success", "message": "Invoice marked as Paid successfully. Record is now locked."}


@router.delete("/invoices/{invoice_id}")
async def delete_invoice(
    invoice_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Delete a DRAFT or GENERATED invoice, resetting the linked cases is_invoiced and invoice_id fields.
    Paid invoices are immutable and cannot be deleted.
    """
    stmt = select(models.Invoice).filter(models.Invoice.id == invoice_id)
    res = await db.execute(stmt)
    inv = res.scalar()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if inv.status == "PAID":
        raise HTTPException(status_code=400, detail="Cannot delete a PAID invoice. Financial records are locked.")

    # 1. Reset all linked cases
    reset_cases_stmt = (
        update(models.Case)
        .where(models.Case.invoice_id == invoice_id)
        .values(is_invoiced=0, invoice_id=None, billed_at=None)
    )
    await db.execute(reset_cases_stmt)

    # 2. Delete invoice
    await db.delete(inv)
    await db.commit()

    return {"status": "success", "message": "Invoice deleted and linked cases returned to billable pool successfully."}


@router.post("/auto-generate")
async def trigger_auto_billing(
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Automated Billing Scheduler simulation.
    Finds active clients that have autoGenerateInvoice = True, determines eligible cases,
    and consolidates them into single grouped invoices automatically.
    """
    # Fetch active clients with billing configuration
    stmt = select(models.Customer).filter(models.Customer.status == "ACTIVE")
    res = await db.execute(stmt)
    clients = res.scalars().all()

    generated_invoices = []
    now = datetime.now()

    for client in clients:
        cfg = client.billing_config or {}
        is_auto = cfg.get("autoGenerateInvoice", False)
        if not is_auto:
            continue

        # Fetch eligible cases
        cases_stmt = (
            select(models.Case)
            .options(joinedload(models.Case.checks), joinedload(models.Case.candidate))
            .filter(models.Case.customer_id == client.id)
            .filter(models.Case.status.in_(FINAL_STATUSES))
            .filter(models.Case.is_invoiced == 0)
            .filter(models.Case.is_billable == 1)
        )
        cases_res = await db.execute(cases_stmt)
        cases = cases_res.unique().scalars().all()

        if not cases:
            continue

        # Invoicing logic
        subtotal = 0.0
        case_rate_mappings = []

        for case in cases:
            check_rates_sum = sum(float(chk.rate or 0) for chk in case.checks)
            rate = float(case.billing_amount or 0)
            if rate <= 0:
                if check_rates_sum > 0:
                    rate = check_rates_sum
                elif case.batch and case.batch.case_rate:
                    rate = float(case.batch.case_rate)
                else:
                    rate = 300.0

            subtotal += rate
            case_rate_mappings.append((case, rate))

        gst_percent = float(cfg.get("gstPercentage", 18.0))
        prefix = str(cfg.get("invoicePrefix", "AUTO"))
        due_days = int(cfg.get("dueDays", 15))

        gst_amount = round((subtotal * gst_percent / 100.0), 2)
        total_amount = round((subtotal + gst_amount), 2)

        month_str = now.strftime("%Y%m")
        invoice_no = f"{prefix}-{month_str}-{str(uuid.uuid4())[:6].upper()}"
        invoice_id = str(uuid.uuid4())
        due_date = now + timedelta(days=due_days)

        # Create Invoice
        invoice = models.Invoice(
            id=invoice_id,
            invoice_number=invoice_no,
            client_id=client.id,
            billing_cycle=cfg.get("billingCycle", "MONTHLY"),
            billing_period_from=now - timedelta(days=30),
            billing_period_to=now,
            subtotal=subtotal,
            gst_amount=gst_amount,
            total_amount=total_amount,
            generated_at=now,
            due_date=due_date,
            status="GENERATED",
            generated_by=current_user.id
        )
        db.add(invoice)

        # Lock cases
        for case, rate in case_rate_mappings:
            case.is_invoiced = 1
            case.invoice_id = invoice_id
            case.billed_at = now
            case.billing_amount = rate

        generated_invoices.append({
            "client_name": client.name,
            "invoice_number": invoice_no,
            "amount": total_amount,
            "cases_count": len(cases)
        })

    if generated_invoices:
        await db.commit()

    return {
        "status": "success",
        "generated_count": len(generated_invoices),
        "invoices": generated_invoices
    }


# --- BACKWARD COMPATIBILITY ENDPOINT ---
@router.get("/case-ledger/{customer_id}")
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
        check_items = [
            {"check_type": chk.check_type, "rate": float(chk.rate or 0)}
            for chk in c.checks
        ]
        case_total = sum(item["rate"] for item in check_items)
        ledger.append({
            "case_ref": c.case_ref_no,
            "candidate": c.candidate.name if c.candidate else "Unknown",
            "completed_at": c.completed_date,
            "checks": [chk.check_type for chk in c.checks],
            "check_items": check_items,
            "billing_amount": float(case_total)
        })
        
    return ledger
