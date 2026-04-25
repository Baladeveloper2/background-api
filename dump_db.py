import asyncio
import os
import sys
import json

# Add current directory to path
sys.path.append(os.getcwd())

from app.database import AsyncSessionLocal
from app.models import Case, VerificationCheck
from sqlalchemy import select

async def check_case():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Case).filter(Case.case_ref_no == 'TAT003'))
        case = res.scalar_one_or_none()
        if not case:
            print('Case TAT003 not found')
            return
        
        res = await db.execute(select(VerificationCheck).filter(VerificationCheck.case_id == case.id))
        checks = res.scalars().all()
        
        results = []
        for c in checks:
            results.append({
                "check_type": c.check_type,
                "status": c.status,
                "data": c.data
            })
            
        with open("db_dump.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=4)

if __name__ == "__main__":
    asyncio.run(check_case())
