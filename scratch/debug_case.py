import asyncio
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app import models

async def debug():
    db = AsyncSessionLocal()
    try:
        stmt = select(models.Case).filter(models.Case.case_ref_no == 'CL-ITC-006')
        res = await db.execute(stmt)
        case_obj = res.scalar_one_or_none()
        if not case_obj:
            print("Case CL-ITC-006 not found!")
            return
        print(f"Case ID: {case_obj.id}")
        print(f"Status: {case_obj.status}")
        
        # Check checks
        stmt_checks = select(models.VerificationCheck).filter(models.VerificationCheck.case_id == case_obj.id)
        res_checks = await db.execute(stmt_checks)
        checks = res_checks.scalars().all()
        print(f"Number of checks: {len(checks)}")
        for chk in checks:
            print(f"Check ID: {chk.id}, Type: {chk.check_type}, Status: {chk.status}")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await db.close()

if __name__ == '__main__':
    asyncio.run(debug())
