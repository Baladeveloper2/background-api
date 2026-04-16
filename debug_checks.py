import asyncio
from app.database import SessionLocal, engine
from app import models
from sqlalchemy import select

async def main():
    async with SessionLocal() as db:
        stmt = select(models.VerificationCheck)
        res = await db.execute(stmt)
        checks = res.scalars().all()
        for check in checks:
            print(f"ID: {check.id}, Type: {check.check_type}, CaseID: {check.case_id}")

if __name__ == "__main__":
    asyncio.run(main())
