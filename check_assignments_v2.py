import asyncio
from app.database import AsyncSessionLocal
from app.models import Case, User
from sqlalchemy import select

async def check():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Case))
        cases = res.scalars().all()
        print(f"DEBUG: Found {len(cases)} cases")
        for c in cases:
            print(f"CASE ID: {c.id}, ASSIGNED_TO: {c.assigned_to}")

if __name__ == "__main__":
    asyncio.run(check())
