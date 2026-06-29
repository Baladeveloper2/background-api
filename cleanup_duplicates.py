import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'app')))
from app.database import AsyncSessionLocal
from app.models import Case, VerificationCheck
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as session:
        # Fetch all cases
        r = await session.execute(select(Case).order_by(Case.id.desc()))
        cases = r.scalars().all()
        
        seen = set()
        deleted = 0
        for case in cases:
            key = (case.candidate_id, case.customer_id)
            if key in seen:
                # Delete related checks
                r2 = await session.execute(select(VerificationCheck).filter(VerificationCheck.case_id == case.id))
                checks = r2.scalars().all()
                for c in checks:
                    await session.delete(c)
                
                await session.delete(case)
                deleted += 1
                print(f"Deleted duplicate case: {case.id}")
            else:
                seen.add(key)
        
        await session.commit()
        print(f"Total deleted duplicates: {deleted}")

if __name__ == "__main__":
    asyncio.run(main())
