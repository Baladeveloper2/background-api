import asyncio
from app.database import AsyncSessionLocal
from app import models
from sqlalchemy import select, or_

async def check():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(models.User).filter(models.User.full_name == 'Manish'))
        manish = res.scalar_one_or_none()
        if manish:
            res = await db.execute(select(models.Case).filter(
                or_(
                    models.Case.assigned_to == manish.id,
                    models.Case.qc_id == manish.id,
                    models.Case.qa_id == manish.id
                )
            ))
            cases = res.scalars().all()
            print(f"Manish Total Assignments: {len(cases)}")
            for c in cases:
                print(f"ID: {c.id}, Status: {c.status}")

if __name__ == "__main__":
    asyncio.run(check())
