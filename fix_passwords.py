import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'app')))

from app.database import AsyncSessionLocal
from app.models import User
from app.auth import get_password_hash
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as session:
        emails = [
            "superadmin@test.com",
            "zoneadmin@test.com",
            "customeradmin@test.com",
            "branchadmin@test.com",
            "Viktar@gmail.com"
        ]
        
        for email in emails:
            res = await session.execute(select(User).filter_by(email=email))
            user = res.scalar_one_or_none()
            if user:
                user.hashed_password = get_password_hash("password123")
                session.add(user)
                print(f"Updated password for {email}")
            else:
                print(f"User {email} NOT FOUND")
                
        await session.commit()

if __name__ == "__main__":
    asyncio.run(main())
