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
        # Find ANY notification for this case ID
        case_id = '34dfa821-1a7a-4d22-98f6-0014450a9783'
        stmt = select(models.Notification).filter(models.Notification.case_id == case_id).order_by(models.Notification.created_at.desc())
        res = await db.execute(stmt)
        notifs = res.scalars().all()
        
        print(f"--- Notifications for Case {case_id} ---")
        if not notifs:
            print("None found")
        for n in notifs:
            print(f"ID: {n.id} | UserID: {n.user_id} | Title: {n.title} | Created: {n.created_at}")

if __name__ == "__main__":
    asyncio.run(check())
