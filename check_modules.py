import asyncio
from app.database import AsyncSessionLocal
from app.models import Module, Role
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Module))
        modules = res.scalars().all()
        print("\n--- Available Modules ---")
        for m in modules:
            print(f"Code: {m.code}, Name: {m.name}, Category: {m.category}")
            
        res_roles = await db.execute(select(Role))
        roles = res_roles.scalars().all()
        print("\n--- Existing Roles ---")
        for r in roles:
            print(f"Role: {r.name}")

if __name__ == "__main__":
    asyncio.run(main())
