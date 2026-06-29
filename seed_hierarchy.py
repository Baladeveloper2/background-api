import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'app')))
from app.database import AsyncSessionLocal
from app.models import Zone, Customer, Branch, User, Role
from app.enums import UserRole
from sqlalchemy import select, update

async def main():
    async with AsyncSessionLocal() as db:
        # 1. Handle Zones
        zones = (await db.execute(select(Zone))).scalars().all()
        tcs_zone = next((z for z in zones if z.zone_name == "TCS"), None)
        
        if tcs_zone:
            tcs_zone.zone_name = "South India"
            tcs_zone.zone_code = "SOUTH"
            db.add(tcs_zone)
        else:
            tcs_zone = Zone(zone_name="South India", zone_code="SOUTH")
            db.add(tcs_zone)
            
        await db.flush()

        # Create missing zones
        existing_zone_names = [z.zone_name for z in zones]
        for zname, zcode in [("North India", "NORTH"), ("East India", "EAST"), ("West India", "WEST")]:
            if zname not in existing_zone_names:
                db.add(Zone(zone_name=zname, zone_code=zcode))

        # Ensure all existing customers belong to South India
        customers = (await db.execute(select(Customer))).scalars().all()
        for cust in customers:
            if not cust.zone_id or cust.zone_id != tcs_zone.id:
                cust.zone_id = tcs_zone.id
                db.add(cust)

        # 2. Handle Roles
        role_definitions = {
            "Super Admin": {"bvs.verification": True, "admin.zones": True, "admin.customers": True, "admin.users": True},
            "Zone Admin": {"admin.customers": True, "admin.users": True},
            "Customer Head": {"admin.branches": True, "admin.users": True, "bvs.reports": True},
            "Branch Admin": {"admin.users": True, "bvs.verification": True},
            "HR": {"bvs.verification": True},
            "Recruiter": {"bvs.verification": True},
            "Verifier": {"bvs.verification": True, "bvs.data_entry": True},
            "Data Entry": {"bvs.data_entry": True},
            "Viewer": {"bvs.reports": True}
        }
        
        roles = (await db.execute(select(Role))).scalars().all()
        role_map = {r.name: r for r in roles}
        
        for role_name, perms in role_definitions.items():
            if role_name not in role_map:
                r = Role(name=role_name, permissions=perms)
                db.add(r)
                role_map[role_name] = r
            else:
                r = role_map[role_name]
                r.permissions = perms
                db.add(r)
        
        await db.flush()

        # 3. Fix Users to map to new Enum strings and Role Table records
        users = (await db.execute(select(User))).scalars().all()
        for u in users:
            if u.role == "CUSTOMER":
                u.role = UserRole.CUSTOMER_HEAD
                u.role_id = role_map["Customer Head"].id
            elif u.role == "SUPER_ADMIN" or u.role == "SUPER ADMIN":
                u.role = UserRole.SUPER_ADMIN
                u.role_id = role_map["Super Admin"].id
            elif u.role == "VERIFIER":
                u.role = UserRole.VERIFIER
                u.role_id = role_map["Verifier"].id
            elif u.role == "DATA ENTRY":
                u.role = UserRole.DATA_ENTRY
                u.role_id = role_map["Data Entry"].id
            db.add(u)

        await db.commit()
        print("Database Hierarchy Seeding Complete.")

if __name__ == "__main__":
    asyncio.run(main())
