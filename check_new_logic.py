import asyncio
from app.database import AsyncSessionLocal
from app import models
from sqlalchemy import select, func, or_, and_

async def check():
    async with AsyncSessionLocal() as db:
        # Strictly count cases that are READY for allocation
        unallocated_stmt = select(func.count(models.Case.id)).filter(
            models.Case.status == 'PENDING'
        )
        
        # Strictly count cases that are ACTIVELY in the verification pipeline
        allocated_stmt = select(func.count(models.Case.id)).filter(
            models.Case.status.in_(['VERIFICATION', 'QC', 'QC_PENDING', 'QA_PENDING'])
        )
        
        un_res = await db.execute(unallocated_stmt)
        al_res = await db.execute(allocated_stmt)
        print(f"DB Unallocated (PENDING only): {un_res.scalar()}")
        print(f"DB Allocated (Active only): {al_res.scalar()}")

if __name__ == "__main__":
    asyncio.run(check())
