
import asyncio
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import models
from backend.app.database import AsyncSessionLocal
from sqlalchemy import select

async def check():
    async with AsyncSessionLocal() as db:
        try:
            stmt = select(models.Case).filter(models.Case.assigned_to != None)
            res = await db.execute(stmt)
            cases = res.scalars().all()
            print(f"Total Assigned Cases: {len(cases)}")
            for i, c in enumerate(cases):
                print(f"Index {i}: Ref={c.case_ref_no}, Status='{c.status}', Type={type(c.status)}")
                if i > 100: break
        except Exception as e:
            print(f"Error: {e}")
        finally:
            await db.close()

if __name__ == "__main__":
    asyncio.run(check())
