import asyncio
from app.database import AsyncSessionLocal
from app.models import Customer
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Customer))
        customers = res.scalars().all()
        print(f"Total Customers: {len(customers)}")
        for c in customers:
            print(f"ID: {c.id}, Name: {c.name}")

if __name__ == "__main__":
    asyncio.run(main())
