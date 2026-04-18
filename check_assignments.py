import asyncio
from app.database import AsyncSessionLocal
from app.models import Case, User
from sqlalchemy import select

async def check():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Case))
        cases = res.scalars().all()
        for c in cases:
            print(f"ID: {c.id}, Assigned: {c.assigned_to}")

if __name__ == "__main__":
    asyncio.run(check())
