import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'app')))
from app.database import AsyncSessionLocal
from app.models import User
from sqlalchemy import select
from app.auth import verify_password

async def main():
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(User).filter_by(email='zoneadmin@test.com'))
        u = res.scalar_one_or_none()
        if u:
            print(f"Email: {u.email}")
            print(f"Status: {u.status}")
            print(f"Hash: {u.hashed_password}")
            print(f"Verify 'password123': {verify_password('password123', u.hashed_password)}")
        else:
            print("User not found")

if __name__ == '__main__':
    asyncio.run(main())
