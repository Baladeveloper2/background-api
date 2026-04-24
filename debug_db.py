import asyncio
import os
import sys

# Add current directory to path
sys.path.append(os.getcwd())

from app.database import AsyncSessionLocal
from app import models
from sqlalchemy import select, func

async def check():
    async with AsyncSessionLocal() as session:
        count = await session.scalar(select(func.count(models.Case.id)))
        print(f"Total Cases: {count}")
        
        users = await session.execute(select(models.User.email, models.User.role))
        print("Users in system:")
        for email, role in users.all():
            print(f" - {email}: {role}")

if __name__ == "__main__":
    asyncio.run(check())
