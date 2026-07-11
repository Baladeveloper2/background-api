import sys
sys.path.insert(0, 'D:/project/backend')
import asyncio
from app.database import AsyncSessionLocal
from app.models import User
from sqlalchemy import select

async def main():
    session = AsyncSessionLocal()
    res = await session.execute(select(User))
    users = res.scalars().all()
    for u in users:
        print(f"User: {u.email} | Role: {u.role} | CustomerID: {u.customer_id}")
    await session.close()

if __name__ == '__main__':
    asyncio.run(main())
