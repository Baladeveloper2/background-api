import asyncio
from app.database import AsyncSessionLocal
from app import models, enums
from sqlalchemy import select, update
from datetime import datetime

async def test_auto_allocate():
    async with AsyncSessionLocal() as db:
        # 1. Get an unallocated case
        stmt = select(models.Case).filter(models.Case.assigned_to == None).limit(1)
        res = await db.execute(stmt)
        case = res.scalar_one_or_none()
        if not case:
            print("No unallocated cases found")
            return
        
        print(f"Testing auto-allocate for Case: {case.case_ref_no} (ID: {case.id})")
        
        # 2. Re-run backend logic manually
        res_users = await db.execute(select(models.User).filter(models.User.role == enums.UserRole.VERIFIER, models.User.status == "ACTIVE"))
        verifiers = res_users.scalars().all()
        if not verifiers:
            print("No active verifiers")
            return
        
        workloads = {}
        for v in verifiers:
            count_res = await db.execute(select(func.count(models.Case.id)).filter(models.Case.assigned_to == v.id, models.Case.status != models.CaseStatus.COMPLETED))
            workloads[v.id] = count_res.scalar() or 0
        
        target_v_id = min(workloads, key=workloads.get)
        print(f"Target Verifier ID: {target_v_id}")

        # Update
        await db.execute(
            update(models.Case).where(models.Case.id == case.id).values(
                assigned_to=target_v_id,
                assigned_at=datetime.utcnow()
            )
        )
        await db.commit()
        print("Success!")

if __name__ == "__main__":
    from sqlalchemy import func
    asyncio.run(test_auto_allocate())
