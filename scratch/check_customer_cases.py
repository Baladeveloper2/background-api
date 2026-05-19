import asyncio
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app import models, database, enums

async def main():
    async with database.AsyncSessionLocal() as session:
        # Get customer user Rabi
        stmt = select(models.User).filter(models.User.email == 'Rabi.panda@apexgroup.com')
        res = await session.execute(stmt)
        user = res.scalar()
        
        print(f"User: {user.email}, Role: {user.role}, CustID: {user.customer_id}")
        
        stmt = select(models.Case).options(
            selectinload(models.Case.candidate),
            selectinload(models.Case.customer),
            selectinload(models.Case.checks),
            selectinload(models.Case.assigned_user)
        ).filter(
            models.Case.customer_id == user.customer_id,
            ~models.Case.status.in_([enums.CaseStatus.PENDING, enums.CaseStatus.LINK_SHARED, enums.CaseStatus.DOCUMENTS_SUBMITTED])
        )
        
        res = await session.execute(stmt)
        cases = res.unique().scalars().all()
        print(f"\nStrategic MIS Query returned {len(cases)} cases:")
        for c in cases:
            print(f"Case ID={c.id}, Ref={c.case_ref_no}, Candidate={c.candidate.name if c.candidate else 'N/A'}, Status={c.status}")

if __name__ == "__main__":
    asyncio.run(main())
