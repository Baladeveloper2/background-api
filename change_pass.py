import asyncio
from sqlalchemy import update
from app.database import AsyncSessionLocal
from app.models import User
from app.auth import get_password_hash

async def change_password():
    async with AsyncSessionLocal() as session:
        new_hash = get_password_hash("admin123")
        stmt = update(User).where(User.email == "admin@bgvms.com").values(hashed_password=new_hash)
        await session.execute(stmt)
        await session.commit()
        print("Password for admin@bgvms.com has been updated to 'admin123'")

if __name__ == "__main__":
    asyncio.run(change_password())
