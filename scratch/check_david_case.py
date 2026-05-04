import asyncio
import sys

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app.database import AsyncSessionLocal
from app import models, enums
from sqlalchemy import select

async def check():
    async with AsyncSessionLocal() as db:
        # Find David's case
        stmt = select(models.Case).join(models.Candidate).filter(models.Candidate.name.ilike("%David%"))
        res = await db.execute(stmt)
        case = res.scalar_one_or_none()
        if case:
            print(f"Case ID: {case.id}")
            print(f"Customer ID: {case.customer_id}")
            print(f"Status: {case.status}")
            
            if case.customer_id:
                # Find users for this customer
                u_stmt = select(models.User).filter(models.User.customer_id == case.customer_id)
                u_res = await db.execute(u_stmt)
                users = u_res.scalars().all()
                print(f"Users for customer {case.customer_id}:")
                for u in users:
                    print(f"  - {u.email} | Role: {u.role} | Status: {u.status}")
            else:
                print("No Customer ID assigned to this case!")
        else:
            print("Case not found for David")

if __name__ == "__main__":
    asyncio.run(check())
