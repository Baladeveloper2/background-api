
import asyncio
import sys
import os
from sqlalchemy import select, func
from datetime import datetime

# Add the current directory to path
sys.path.append(os.getcwd())

from app.database import AsyncSessionLocal
from app.models import Notification, User

async def diag():
    async with AsyncSessionLocal() as db:
        # Check total
        n_count = await db.execute(select(func.count(Notification.id)))
        print(f"Total Notifications: {n_count.scalar()}")
        
        # Check users
        u_res = await db.execute(select(User))
        users = u_res.scalars().all()
        for u in users:
            notif_res = await db.execute(select(func.count(Notification.id)).filter(Notification.user_id == u.id))
            n_count_val = notif_res.scalar()
            print(f"User {u.email} (ID={u.id}, Role={u.role}) has {n_count_val} notifications")
            
            if n_count_val > 0:
                # Show last one for each
                last_res = await db.execute(select(Notification).filter(Notification.user_id == u.id).order_by(Notification.created_at.desc()).limit(1))
                last_n = last_res.scalar_one_or_none()
                if last_n:
                    print(f"  Last: [{last_n.category}] {last_n.title} - {last_n.message} ({last_n.created_at})")

if __name__ == "__main__":
    asyncio.run(diag())
