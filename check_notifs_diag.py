import asyncio
import os
import sys

# Add project root to sys.path
sys.path.append(os.getcwd())

from sqlalchemy import select
from app.database import AsyncSessionLocal
from app import models

async def check_notifs():
    async with AsyncSessionLocal() as db:
        try:
            # Check last 10 notifications
            stmt = select(models.Notification).order_by(models.Notification.created_at.desc()).limit(10)
            res = await db.execute(stmt)
            print("--- LAST 10 NOTIFICATIONS ---")
            for n in res.scalars().all():
                print(f"ID: {n.id} | User: {n.user_id} | Title: {n.title} | Extra: {n.extra_data}")
                
            print("\n--- USERS ---")
            # Check users
            stmt = select(models.User).limit(20)
            res = await db.execute(stmt)
            for u in res.scalars().all():
                 print(f"User ID: {u.id} | Full Name: {u.full_name}")
                 
        finally:
            await db.close()

if __name__ == "__main__":
    asyncio.run(check_notifs())
