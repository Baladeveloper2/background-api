import asyncio
import os
import sys

sys.path.append("d:\\project\\backend")

from app.database import AsyncSessionLocal
from app import models
from sqlalchemy import select

async def check():
    async with AsyncSessionLocal() as db:
        stmt = select(models.Case).options(
            select(models.Case).outerjoin(models.Case.candidate).outerjoin(models.Case.customer)
        ).order_by(models.Case.received_date.desc()).limit(20)
        
        res = await db.execute(stmt)
        cases = res.scalars().all()
        print(f"Found {len(cases)} cases:")
        for c in cases:
            cand_name = c.candidate.name if c.candidate else "None"
            cand_email = c.candidate.email if c.candidate else "None"
            print(f"ID: {c.id} | Ref: {c.case_ref_no} | Name: {cand_name} | Email: {cand_email} | Status: {c.status} | Submitted At: {c.submitted_at}")

if __name__ == "__main__":
    asyncio.run(check())
