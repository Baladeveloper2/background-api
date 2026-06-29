import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'app')))

from app.database import AsyncSessionLocal
from app.models import User
from app.auth import get_password_hash
from sqlalchemy import select

async def get_test_accounts():
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(User))
        users = res.scalars().all()
        
        seen_roles = set()
        roles_found = []
        for user in users:
            role_name = user.role.value if hasattr(user.role, 'value') else user.role
            if role_name not in seen_roles:
                seen_roles.add(role_name)
                user.hashed_password = get_password_hash("password123")
                session.add(user)
                roles_found.append({"role": role_name, "email": user.email, "name": user.full_name})
                
        await session.commit()
        
        print("CREDENTIALS:")
        for r in roles_found:
            print(f"Role: {r['role']} | Email: {r['email']} | Pass: password123")

if __name__ == "__main__":
    asyncio.run(get_test_accounts())
