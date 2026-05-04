import asyncio
import sys

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app.database import AsyncSessionLocal
from app import models, enums
from sqlalchemy import select

async def check():
    async with AsyncSessionLocal() as db:
        stmt = select(models.User).filter(models.User.email.in_(["hr@ITCglobal.com", "itc@gmail.com"]))
        res = await db.execute(stmt)
        users = res.scalars().all()
        user_ids = [u.id for u in users]
        
        print(f"User IDs: {user_ids}")
        
        # Check notifications for these users
        n_stmt = select(models.Notification).filter(models.Notification.user_id.in_(user_ids)).order_by(models.Notification.created_at.desc())
        n_res = await db.execute(n_stmt)
        notifs = n_res.scalars().all()
        
        print("\n--- Notifications for Customer Users ---")
        if not notifs:
            print("None found")
        for n in notifs:
            print(f"ID: {n.id} | UserID: {n.user_id} | Title: {n.title} | Created: {n.created_at}")

if __name__ == "__main__":
    asyncio.run(check())
