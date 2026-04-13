import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from app.database import AsyncSessionLocal
from app import models
from sqlalchemy import select, func

async def check():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(func.count(models.Case.id)))
        case_count = res.scalar()
        
        res = await db.execute(select(func.count(models.Candidate.id)))
        cand_count = res.scalar()
        
        print(f"Cases in DB: {case_count}")
        print(f"Candidates in DB: {cand_count}")
        
        if case_count > 0:
            res = await db.execute(select(models.Case).limit(5))
            cases = res.scalars().all()
            for c in cases:
                print(f"Case ID: {c.id}, Ref: {c.case_ref_no}, Candidate: {c.candidate_id}")

if __name__ == "__main__":
    asyncio.run(check())
