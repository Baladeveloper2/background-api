import asyncio
from app.database import AsyncSessionLocal
from app import models
from sqlalchemy import select

async def check():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(models.Case.id, models.Case.status, models.Case.case_ref_no))
        cases = res.all()
        print(f"Total Cases in Table: {len(cases)}")
        status_counts = {}
        for c in cases:
            s = str(c.status).upper()
            status_counts[s] = status_counts.get(s, 0) + 1
        print(f"Status Breakdown: {status_counts}")

if __name__ == "__main__":
    asyncio.run(check())
