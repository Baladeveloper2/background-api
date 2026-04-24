
import asyncio
import sys
import os

# Add the current directory to path
sys.path.append(os.getcwd())

from app.database import SessionLocal
from app.models import Notification
from sqlalchemy import select, func

async def check_notifs():
    async with SessionLocal() as db:
        stmt = select(func.count(Notification.id))
        res = await db.execute(stmt)
        count = res.scalar()
        print(f"DEBUG_COUNT: {count}")
        
        # Get last 5
        stmt2 = select(Notification).order_by(Notification.created_at.desc()).limit(5)
        res2 = await db.execute(stmt2)
        notifs = res2.scalars().all()
        for n in notifs:
            print(f"NOTIF: ID={n.id}, User={n.user_id}, Title={n.title}, Created={n.created_at}")

if __name__ == "__main__":
    asyncio.run(check_notifs())
