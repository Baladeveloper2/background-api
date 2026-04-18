
import asyncio
from app.database import async_engine, get_async_db
from app import models
from sqlalchemy import select

async def check():
    async with async_engine.connect() as conn:
        res = await conn.execute(select(models.Case).filter(models.Case.status == 'COMPLETED'))
        cases = res.all()
        print(f"Total Completed Cases: {len(cases)}")
        for c in cases:
            print(f"Ref: {c.case_ref_no}, Assigned: {c.assigned_to}, QC: {c.qc_id}, QA: {c.qa_id}")
            
    await async_engine.dispose()

if __name__ == "__main__":
    asyncio.run(check())
