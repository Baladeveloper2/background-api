import asyncio
import os
import sys
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

# Add parent dir to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import models, database, enums, notification_utils

async def create_test_notif():
    engine = database.engine
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    async with async_session() as db:
        # Get first user
        res = await db.execute(select(models.User).limit(1))
        user = res.scalar_one_or_none()
        if not user:
            print("No user found")
            return
        
        print(f"Creating unread notification for {user.email}")
        
        await notification_utils.create_notification(
            db, 
            user.id, 
            "🚀 Test Notification", 
            "This is a test notification to verify the feed is working.",
            enums.NotificationCategory.SYSTEM_ALERT
        )
        await db.commit()
        print("Done.")

if __name__ == "__main__":
    asyncio.run(create_test_notif())
