import asyncio
from app.database import AsyncSessionLocal
from app.models import Case, Candidate, Customer
from sqlalchemy import select
from sqlalchemy.orm import joinedload

async def check():
    async with AsyncSessionLocal() as db:
        stmt = select(Case).options(joinedload(Case.candidate), joinedload(Case.customer))
        res = await db.execute(stmt)
        cases = res.unique().scalars().all()
        print(f"DEBUG: Found {len(cases)} cases")
        for c in cases:
            print(f"CASE: {c.case_ref_no}, Candidate: {c.candidate.name if c.candidate else 'None'}, Customer: {c.customer.name if c.customer else 'None'}, Assigned: {c.assigned_to}")

if __name__ == "__main__":
    asyncio.run(check())
