import asyncio
from app.database import AsyncSessionLocal
from app import models
from sqlalchemy import select

async def check():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(models.Case).filter(models.Case.assigned_to.isnot(None)))
        cases = res.scalars().all()
        print(f"Total Assigned Cases (Any Status): {len(cases)}")
        for c in cases:
            print(f"ID: {c.id}, Status: {c.status}")

if __name__ == "__main__":
    asyncio.run(check())
