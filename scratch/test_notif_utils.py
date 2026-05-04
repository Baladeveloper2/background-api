import asyncio
from app.database import AsyncSessionLocal
from app import models, enums, notification_utils
from sqlalchemy import select

async def check():
    async with AsyncSessionLocal() as db:
        roles = [enums.UserRole.SUPER_ADMIN, enums.UserRole.ADMIN, enums.UserRole.MANAGER]
        users = await notification_utils.get_users_by_role(db, roles)
        print(f"Internal Users found: {[u.email for u in users]}")
        
        # Test create_notification
        # Using a dummy user ID (the super admin one)
        if users:
            admin_id = users[0].id
            print(f"Testing create_notification for {users[0].email} (ID: {admin_id})")
            notif = await notification_utils.create_notification(
                db, admin_id, "Test Notification", "This is a test", enums.NotificationCategory.SYSTEM_ALERT
            )
            if notif:
                print(f"Notification created: {notif.id}")
                await db.commit()
                print("Committed successfully")
            else:
                print("Failed to create notification")

if __name__ == "__main__":
    asyncio.run(check())
