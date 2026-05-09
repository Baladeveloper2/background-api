import asyncio
from app.database import AsyncSessionLocal
from app import models
from sqlalchemy import select

async def check():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(models.Case.status))
        statuses = [r[0] for r in res.all()]
        counts = {}
        for s in statuses:
            counts[s] = counts.get(s, 0) + 1
        print(f"RAW Status Breakdown: {counts}")

if __name__ == "__main__":
    asyncio.run(check())
