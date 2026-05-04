import asyncio
import sys

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app.database import AsyncSessionLocal
from app import models, enums
from sqlalchemy import select
from datetime import datetime, timedelta

async def check():
    async with AsyncSessionLocal() as db:
        # Find ANY notification created in the last 24 hours
        yesterday = datetime.now() - timedelta(days=1)
        stmt = select(models.Notification).filter(models.Notification.created_at >= yesterday).order_by(models.Notification.created_at.desc())
        res = await db.execute(stmt)
        notifs = res.scalars().all()
        
        print(f"--- Notifications in the last 24 hours ---")
        if not notifs:
            print("None found")
        for n in notifs:
            print(f"ID: {n.id} | UserID: {n.user_id} | Title: {n.title} | Category: {n.category} | Created: {n.created_at}")

if __name__ == "__main__":
    asyncio.run(check())
