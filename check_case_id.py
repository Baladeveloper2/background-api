import asyncio
from sqlalchemy import select
from app.database import SessionLocal, get_async_db
from app import models
import json

async def check_case():
    case_id = "48e6fa09-76d2-414f-8115-3baeea11179e"
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        stmt = select(models.Case).filter(models.Case.id == case_id)
        res = await db.execute(stmt)
        case = res.scalar_one_or_none()
        
        if case:
            print(f"✅ Case found: {case.case_ref_no}, status={case.status}")
        else:
            print(f"❌ Case NOT found: {case_id}")

if __name__ == "__main__":
    asyncio.run(check_case())
