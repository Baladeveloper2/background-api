import asyncio
import os
import sys
from datetime import datetime, timedelta
sys.path.append(os.getcwd())

from app.database import AsyncSessionLocal
from app.models import Case, VerificationCheck
from app import tat_utils
from sqlalchemy import select, text

async def check():
    async with AsyncSessionLocal() as db:
        # Get cases and their checks
        res = await db.execute(select(Case))
        cases = res.scalars().all()
        
        at_risk_count = 0
        print(f"Total cases: {len(cases)}")
        for c in cases:
            # Get checks
            checks_res = await db.execute(select(VerificationCheck).filter(VerificationCheck.case_id == c.id))
            checks = checks_res.scalars().all()
            check_types = [chk.check_type for chk in checks]
            
            p_tat = tat_utils.calculate_predictive_tat(check_types)
            is_at_risk = tat_utils.check_is_at_risk(c.received_date, p_tat)
            
            print(f"Case: {c.case_ref_no}, Received: {c.received_date}, P-TAT: {p_tat}, Is At Risk: {is_at_risk}, In TAT: {c.is_in_tat}, Status: {c.status}")
            if is_at_risk:
                at_risk_count += 1
        
        print(f"Calculated At Risk Count: {at_risk_count}")

if __name__ == "__main__":
    asyncio.run(check())
