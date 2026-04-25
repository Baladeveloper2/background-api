import asyncio
from app.database import AsyncSessionLocal
from app import models
from sqlalchemy import select

async def check():
    async with AsyncSessionLocal() as db:
        stmt = select(models.Case).order_by(models.Case.received_date.desc())
        res = await db.execute(stmt)
        cases = res.scalars().all()
        for c in cases:
            print(f"{c.case_ref_no}, {c.status}, {c.received_date}")

if __name__ == "__main__":
    asyncio.run(check())
