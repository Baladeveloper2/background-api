import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'app')))
from app.database import AsyncSessionLocal
from app.models import Zone, Customer, Branch, User, Role, Candidate, Case
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as db:
        zones = (await db.execute(select(Zone))).scalars().all()
        customers = (await db.execute(select(Customer))).scalars().all()
        users = (await db.execute(select(User))).scalars().all()
        roles = (await db.execute(select(Role))).scalars().all()
        
        print('--- ZONES ---')
        for z in zones: print(f'{z.id}: {z.zone_name}')
        
        print('\n--- CUSTOMERS ---')
        for c in customers: print(f'{c.id}: {c.name} (Zone: {c.zone_id})')
        
        print('\n--- USERS ---')
        for u in users: print(f'{u.id}: {u.email} (Role: {u.role}, Customer: {u.customer_id}, Branch: {u.branch_id})')
        
        print('\n--- ROLES ---')
        for r in roles: print(f'{r.id}: {r.name}')

asyncio.run(main())
