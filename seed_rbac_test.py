import asyncio
import os
import sys

# Add the backend app directory to the path so we can import from it
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'app')))

from app.database import AsyncSessionLocal
from app.models import User, Role, Customer, Branch, Zone, UserRole
from app.auth import get_password_hash
from sqlalchemy import select

async def seed_test_data():
    async with AsyncSessionLocal() as session:
        # Create a Zone
        res = await session.execute(select(Zone).filter_by(zone_name="Test Zone"))
        zone = res.scalar_one_or_none()
        if not zone:
            zone = Zone(zone_name="Test Zone", zone_code="TZ-01")
            session.add(zone)
            await session.flush()

        # Create a Customer in the Zone
        res = await session.execute(select(Customer).filter_by(company_code="TEST-CUST"))
        customer = res.scalar_one_or_none()
        if not customer:
            customer = Customer(
                name="Test Customer",
                company_name="Test Customer Inc.",
                company_code="TEST-CUST",
                zone_id=zone.id
            )
            session.add(customer)
            await session.flush()

        # Create a Branch in the Customer
        res = await session.execute(select(Branch).filter_by(branch_code="TEST-BR-01"))
        branch = res.scalar_one_or_none()
        if not branch:
            branch = Branch(
                branch_name="Test Branch 01",
                branch_code="TEST-BR-01",
                customer_id=customer.id
            )
            session.add(branch)
            await session.flush()

        # Define users to create
        users_to_create = [
            {
                "email": "superadmin@test.com",
                "full_name": "Test Super Admin",
                "role": "SUPER_ADMIN",
                "customer_id": None,
                "branch_id": None,
                "zone_id": None
            },
            {
                "email": "zoneadmin@test.com",
                "full_name": "Test Zone Admin",
                "role": "ZONE_ADMIN",
                "customer_id": None,
                "branch_id": None,
                "zone_id": zone.id
            },
            {
                "email": "customeradmin@test.com",
                "full_name": "Test Customer Admin",
                "role": "CUSTOMER",
                "customer_id": customer.id,
                "branch_id": None,
                "zone_id": zone.id
            },
            {
                "email": "branchadmin@test.com",
                "full_name": "Test Branch Admin",
                "role": "CUSTOMER",
                "customer_id": customer.id,
                "branch_id": branch.id,
                "zone_id": zone.id
            }
        ]

        created_users = []
        for u in users_to_create:
            res = await session.execute(select(User).filter_by(email=u["email"]))
            user = res.scalar_one_or_none()
            if not user:
                # Find role relation (we will just use string roles for now or assign a dummy role_id if needed)
                # But for now, setting the Enum role is enough for basic scoping
                role_enum = UserRole.SUPER_ADMIN if u["role"] == "SUPER_ADMIN" else UserRole.CUSTOMER
                
                user = User(
                    email=u["email"],
                    hashed_password=get_password_hash("password123"),
                    full_name=u["full_name"],
                    role=role_enum,
                    customer_id=u["customer_id"],
                    branch_id=u["branch_id"],
                    zone_id=u["zone_id"],
                    status="ACTIVE"
                )
                session.add(user)
                created_users.append(u["email"])
        
        await session.commit()
        print(f"Seed complete. Created users: {', '.join(created_users)}")
        print("\nTest Credentials (Password for all is 'password123'):")
        for u in users_to_create:
            print(f"- {u['full_name']}: {u['email']}")

if __name__ == "__main__":
    asyncio.run(seed_test_data())
