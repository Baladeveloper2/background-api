import asyncio, sys
sys.path.insert(0, '.')
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

async def check():
    from app.database import async_engine
    from app import models
    async with AsyncSession(async_engine) as db:
        # Find the ITC customer
        cust_res = await db.execute(select(models.Customer).filter(models.Customer.name.ilike('%ITC%')))
        cust = cust_res.scalars().first()
        if not cust:
            print("No ITC customer found")
            return
        print(f"Customer: {cust.name} (id={cust.id})")
        
        stmt = (
            select(models.Case)
            .options(joinedload(models.Case.candidate), joinedload(models.Case.checks))
            .filter(models.Case.customer_id == cust.id)
            .filter(models.Case.status == "COMPLETED")
        )
        res = await db.execute(stmt)
        cases = res.unique().scalars().all()
        
        for c in cases:
            print(f"\nCase: {c.case_ref_no}, completed_date={c.completed_date}")
            for chk in c.checks:
                print(f"  check_type={chk.check_type}, rate={chk.rate}")
            
            # Simulate what billing_routes returns
            check_items = [
                {"check_type": chk.check_type, "rate": float(chk.rate or 0)}
                for chk in c.checks
            ]
            case_total = sum(item["rate"] for item in check_items)
            print(f"  => check_items = {check_items}")
            print(f"  => billing_amount = {case_total}")

asyncio.run(check())
