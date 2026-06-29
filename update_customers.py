import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'app')))
from app.database import AsyncSessionLocal
from app.models import Customer
from sqlalchemy import select, update

async def main():
    async with AsyncSessionLocal() as session:
        # Update Test Customer
        await session.execute(update(Customer).where(Customer.name == 'Test Customer').values(industry='Technology', head_office='Bangalore, India'))
        
        # Update MAHINDRA
        await session.execute(update(Customer).where(Customer.name == 'MAHINDRA').values(industry='Automotive', head_office='Mumbai, India'))
        
        # Update Zappy Hire
        await session.execute(update(Customer).where(Customer.name == 'Zappy Hire').values(industry='HR Tech', head_office='Kerala, India'))
        
        # Update ABC corp
        await session.execute(update(Customer).where(Customer.name == 'ABC corp').values(industry='Retail', head_office='New Delhi, India'))
        
        # Update TCS
        await session.execute(update(Customer).where(Customer.name == 'TCS').values(industry='IT Services', head_office='Mumbai, India'))
        
        await session.commit()
        print("Customers updated successfully!")

if __name__ == '__main__':
    asyncio.run(main())
