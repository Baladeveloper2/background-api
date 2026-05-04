import asyncio
from app.database import AsyncSessionLocal
from app import models
from sqlalchemy import select

async def check():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(models.Insufficiency.id, models.Insufficiency.message, models.Insufficiency.is_resolved).filter(models.Insufficiency.case_id.ilike('%ITC-003%')))
        print(f"Insufficiencies for CL-ITC-003: {res.all()}")

if __name__ == "__main__":
    asyncio.run(check())
