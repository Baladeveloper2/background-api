import asyncio
import os
import sys

# Add current directory to path
sys.path.append(os.getcwd())

from app.database import AsyncSessionLocal
from app import models
from sqlalchemy import select, func

async def check():
    async with AsyncSessionLocal() as session:
        users = await session.execute(select(models.User).limit(1))
        current_user = users.scalar_one()
        
        print(f"User: {current_user.email}")
        print(f"User Role Object: {current_user.role} (Type: {type(current_user.role)})")
        
        # Exact logic from stats_routes.py
        user_role = str(current_user.role.value if hasattr(current_user.role, 'value') else current_user.role).upper()
        role_name = (current_user.role_rel.name.upper() if current_user.role_rel else "").upper()
        
        print(f"Computed user_role: '{user_role}'")
        print(f"Computed role_name: '{role_name}'")
        
        is_customer = user_role == "CUSTOMER" or role_name == "CUSTOMER"
        is_admin = user_role in ["SUPER_ADMIN", "ADMIN", "MANAGER", "QA", "QC"] or role_name in ["SUPER ADMIN", "QC VERIFIER"]
        
        print(f"is_customer: {is_customer}")
        print(f"is_admin: {is_admin}")
        
        filter_verifier = not (is_admin or is_customer)
        print(f"filter_verifier: {filter_verifier}")

if __name__ == "__main__":
    asyncio.run(check())
