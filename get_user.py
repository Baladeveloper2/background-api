import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'app')))
from app.database import AsyncSessionLocal
from app.models import User, Customer
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as session:
        r = await session.execute(select(User).filter(User.email=='zoneadmin@test.com'))
        u = r.scalar_one_or_none()
        if u:
            print(f"User customer_id: {u.customer_id}")
            r2 = await session.execute(select(Customer).limit(1))
            c = r2.scalar_one_or_none()
            if c:
                print(f"First Customer ID: {c.id}")
                if u.customer_id is None:
                    u.customer_id = c.id
                    await session.commit()
                    print(f"Updated user with customer_id: {c.id}")
        else:
            print("Not found")

if __name__ == '__main__':
    asyncio.run(main())
