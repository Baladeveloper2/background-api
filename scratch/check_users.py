import asyncio
from app.database import AsyncSessionLocal
from app import models, enums
from sqlalchemy import select

async def check():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(models.User.email, models.User.role, models.User.customer_id))
        users = res.all()
        print("--- All Users ---")
        for u in users:
            print(u)
        
        # Check specific case customer
        # Let's find David D's case
        stmt = select(models.Case).join(models.Candidate).filter(models.Candidate.name.ilike("%David%"))
        res = await db.execute(stmt)
        case = res.scalar_one_or_none()
        if case:
            print(f"\n--- Case for David (ID: {case.id}) ---")
            print(f"Customer ID: {case.customer_id}")
            
            # Find users for this customer
            u_stmt = select(models.User).filter(models.User.customer_id == case.customer_id)
            u_res = await db.execute(u_stmt)
            c_users = u_res.scalars().all()
            print(f"Users for this customer: {[u.email + ' (' + u.role + ')' for u in c_users]}")
        else:
            print("\nCase for David not found")

if __name__ == "__main__":
    asyncio.run(check())
