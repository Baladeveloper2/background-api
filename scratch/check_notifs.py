import asyncio
from app.database import AsyncSessionLocal
from sqlalchemy import text
from app.models import User
from app.enums import UserRole

async def check_users():
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT id, email, role, status FROM users"))
        users = result.fetchall()
        print(f"Users in DB (Total: {len(users)}):")
        for u in users:
            print(f"ID: {u.id}, Email: {u.email}, Role: {u.role}, Status: {u.status}")

if __name__ == "__main__":
    asyncio.run(check_users())
