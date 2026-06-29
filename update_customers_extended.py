import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'app')))
from app.database import AsyncSessionLocal
from app.models import Customer, Zone
from sqlalchemy import select, update

async def main():
    async with AsyncSessionLocal() as session:
        # Get a valid zone if available
        zone_res = await session.execute(select(Zone.id).limit(1))
        zone = zone_res.scalars().first()
        
        # MAHINDRA
        await session.execute(update(Customer).where(Customer.name == 'MAHINDRA').values(
            company_name='Mahindra & Mahindra Ltd',
            company_code='MAHINDRA123',
            gst_number='27AAACM0007E1Z1',
            short_code='MAH',
            zone_id=zone
        ))
        
        # Test Customer
        await session.execute(update(Customer).where(Customer.name == 'Test Customer').values(
            company_name='Test Customer Pvt Ltd',
            company_code='TEST-CUST',
            gst_number='27AAAAA0000A1Z5',
            short_code='TC',
            zone_id=zone
        ))
        
        # Zappy Hire
        await session.execute(update(Customer).where(Customer.name == 'Zappy Hire').values(
            company_name='Zappy Hire Solutions',
            company_code='ZH-001',
            gst_number='32AAACZ0000Z1Z5',
            short_code='ZH',
            zone_id=zone
        ))
        
        # ABC corp
        await session.execute(update(Customer).where(Customer.name == 'ABC corp').values(
            company_name='ABC Corporation',
            company_code='ABC-001',
            gst_number='27AAACA0000A1Z5',
            short_code='ABC',
            zone_id=zone
        ))
        
        # TCS
        await session.execute(update(Customer).where(Customer.name == 'TCS').values(
            company_name='Tata Consultancy Services',
            company_code='TCS-001',
            gst_number='27AAACT0000T1Z5',
            short_code='TCS',
            zone_id=zone
        ))
        
        await session.commit()
        print("Customers extended info updated successfully!")

if __name__ == '__main__':
    asyncio.run(main())
