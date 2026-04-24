
import asyncio
from backend.app import models
from backend.app.database import SessionLocal
from sqlalchemy import select

async def check():
    db = SessionLocal()
    try:
        stmt = select(models.Case).filter(models.Case.assigned_to != None)
        res = await db.execute(stmt)
        cases = res.scalars().all()
        print(f"Total Assigned Cases: {len(cases)}")
        for i, c in enumerate(cases):
            print(f"Index {i}: Ref={c.case_ref_no}, Status='{c.status}'")
            if i > 100: break
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(check())
