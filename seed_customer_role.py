import asyncio
from app.database import AsyncSessionLocal
from app.models import Role, Module
from sqlalchemy import select

async def seed():
    async with AsyncSessionLocal() as db:
        # Check if exists
        res = await db.execute(select(Role).filter(Role.name == "Customer"))
        existing = res.scalar_one_or_none()
        if existing:
            print("Customer role already exists.")
            return

        # New Customer Role
        new_role = Role(
            name="Customer",
            description="HR / Company login for candidate uploads and tracking",
            permissions={
                "bvs.verification": {"read": True, "write": True},
                "bvs.batch": {"read": True, "write": True},
                "bms.applicants": {"read": True, "write": True},
                "reports": {"read": True}
            }
        )
        db.add(new_role)
        await db.commit()
        print("Successfully created Customer role.")

if __name__ == "__main__":
    asyncio.run(seed())
