
import asyncio
from app.database import async_engine
from app import models
from sqlalchemy import update

async def fix():
    # Manish ID: 2d002335-c4b3-4419-8e5b-e3188d0e54d9
    manish_id = "2d002335-c4b3-4419-8e5b-e3188d0e54d9"
    case_refs = ["TAT001", "IBM002", "TAT002"]
    
    async with async_engine.connect() as conn:
        stmt = update(models.Case).where(models.Case.case_ref_no.in_(case_refs)).values(qa_id=manish_id)
        await conn.execute(stmt)
        await conn.commit()
    print("Fixed 3 cases for Manish.")
    await async_engine.dispose()

if __name__ == "__main__":
    asyncio.run(fix())
