import asyncio
import sys
import os

# Set encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app.database import AsyncSessionLocal
from app import models, enums
from sqlalchemy import select

async def check():
    async with AsyncSessionLocal() as db:
        # Find David's notifications
        # Join Case and Candidate
        stmt = select(models.Notification).join(models.Case).join(models.Candidate).filter(models.Candidate.name.ilike("%David%")).order_by(models.Notification.created_at.desc())
        res = await db.execute(stmt)
        notifs = res.scalars().all()
        
        print(f"--- Notifications for David ---")
        if not notifs:
            print("None found")
        for n in notifs:
            # Strip emojis for printing if needed, but utf-8 should handle it
            print(f"ID: {n.id} | UserID: {n.user_id} | Title: {n.title} | Category: {n.category} | Created: {n.created_at}")

        # Let's see who are the internal users
        roles = [enums.UserRole.SUPER_ADMIN, enums.UserRole.ADMIN, enums.UserRole.MANAGER]
        u_stmt = select(models.User).filter(models.User.role.in_(roles))
        u_res = await db.execute(u_stmt)
        users = u_res.scalars().all()
        print(f"\n--- Internal Users ---")
        for u in users:
            print(f"ID: {u.id} | Email: {u.email} | Role: {u.role} | Status: {u.status}")

if __name__ == "__main__":
    asyncio.run(check())
