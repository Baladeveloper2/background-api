import asyncio
import os
import sys

# Add current directory to path
sys.path.append(os.getcwd())

from app.database import AsyncSessionLocal
from app import models
from sqlalchemy import select

async def check():
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(models.Notification).limit(10).order_by(models.Notification.created_at.desc()))
        notifs = res.all()
        for n in notifs:
            print(f"[{n[0].created_at}] {n[0].category:15} | {n[0].title}")

if __name__ == "__main__":
    asyncio.run(check())
