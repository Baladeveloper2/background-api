import asyncio
import os
import sys
from datetime import datetime, timedelta
sys.path.append(os.getcwd())

from app.database import AsyncSessionLocal
from app.models import Case
from sqlalchemy import select, func, or_, and_, text

async def check():
    async with AsyncSessionLocal() as db:
        risk_threshold = datetime.utcnow() - timedelta(days=7)
        # Query 1: The filter logic in read_cases
        q1 = select(func.count(Case.id)).filter(
            Case.status.notin_(['COMPLETED', 'QC_VERIFIED']),
            or_(
                Case.is_in_tat == 0,
                Case.received_date < risk_threshold
            )
        )
        res1 = await db.execute(q1)
        count1 = res1.scalar()
        
        print(f"Filter count (Logic 1): {count1}")
        
        # Query 2: All cases to see what's happening
        q2 = select(Case.id, Case.status, Case.received_date, Case.is_in_tat)
        res2 = await db.execute(q2)
        rows = res2.all()
        for r in rows:
            is_old = r.received_date < risk_threshold
            is_active = r.status not in ['COMPLETED', 'QC_VERIFIED']
            matches = is_active and (r.is_in_tat == 0 or is_old)
            print(f"ID: {r.id}, Status: {r.status}, Received: {r.received_date}, InTAT: {r.is_in_tat}, Old: {is_old}, Active: {is_active}, Match: {matches}")

if __name__ == "__main__":
    asyncio.run(check())
