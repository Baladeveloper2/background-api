import os
import sys
import asyncio

# Add the parent directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import AsyncSessionLocal
from app import models
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(models.User.email, models.User.role))
        users = res.all()
        for u in users:
            print(f"Email: {u[0]}, Role: {u[1]}")

if __name__ == "__main__":
    asyncio.run(main())
