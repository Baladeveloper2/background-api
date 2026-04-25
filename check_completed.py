import asyncio
from app.database import AsyncSessionLocal
from app import models
from sqlalchemy import select

async def check():
    async with AsyncSessionLocal() as db:
        try:
            stmt = select(models.Case).order_by(models.Case.received_date.desc())
            res = await db.execute(stmt)
            cases = res.scalars().all()
            print(f"{'Ref':<10} | {'Status':<15} | {'Received':<25}")
            print("-" * 50)
            for c in cases:
                print(f"{c.case_ref_no:<10} | {str(c.status):<15} | {str(c.received_date):<25}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check())
