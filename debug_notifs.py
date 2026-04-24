import asyncio
import os
import sys
from sqlalchemy import select

# Add current directory to path
sys.path.append(os.getcwd())

from app.database import AsyncSessionLocal, async_engine
from app import models

async def debug():
    try:
        async with AsyncSessionLocal() as session:
            # Check Users
            res_users = await session.execute(select(models.User))
            users = res_users.scalars().all()
            print("--- USERS ---")
            for u in users:
                print(f"ID: {u.id} | Name: {u.full_name} | Role: {u.role}")
            
            # Check Notifications
            res_notifs = await session.execute(select(models.Notification).order_by(models.Notification.created_at.desc()).limit(20))
            notifs = res_notifs.scalars().all()
            print("\n--- NOTIFICATIONS ---")
            if not notifs:
                print("No notifications found in DB.")
            for n in notifs:
                print(f"ID: {n.id} | To User ID: {n.user_id} | Title: {n.title} | Read: {n.is_read} | Created: {n.created_at}")
    except Exception as e:
        print(f"Error in debug script: {e}")
    finally:
        await async_engine.dispose()

if __name__ == "__main__":
    asyncio.run(debug())
