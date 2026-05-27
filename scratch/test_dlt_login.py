import sys
import os
import asyncio

sys.path.append(r'd:\project\backend')

from app.database import AsyncSessionLocal
from app.models import User, UserRole
from app.auth import get_password_hash
from sqlalchemy import select

async def seed_2fa_user():
    async with AsyncSessionLocal() as db:
        print("Checking if test DLT user exists...")
        stmt = select(User).filter(User.email == "test_dlt@example.com")
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()
        
        if user:
            print("DLT test user exists, updating phone and 2FA status...")
            user.phone = "9876543210"
            user.is_2fa_enabled = True
            db.add(user)
        else:
            print("Creating new DLT test user...")
            user = User(
                email="test_dlt@example.com",
                hashed_password=get_password_hash("password123"),
                full_name="DLT Test User",
                role=UserRole.USER,
                phone="9876543210",
                is_2fa_enabled=True
            )
            db.add(user)
            
        await db.commit()
        print("\nSUCCESS: Seeded 2FA Jio DLT Test Account successfully!")
        print("---------------------------------------------")
        print("Email:    test_dlt@example.com")
        print("Password: password123")
        print("Phone:    9876543210")
        print("2FA status: ENABLED")
        print("---------------------------------------------\n")

if __name__ == "__main__":
    asyncio.run(seed_2fa_user())
