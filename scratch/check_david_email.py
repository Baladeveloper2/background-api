import asyncio
from app.database import AsyncSessionLocal
from app import models
from sqlalchemy import select

async def check():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(models.Candidate.email).filter(models.Candidate.name.ilike('%David%')))
        print(f"David's email: {res.scalar_one_or_none()}")

if __name__ == "__main__":
    asyncio.run(check())
