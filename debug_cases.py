from app.database import SessionLocal
from app import models
from datetime import datetime, timezone
import asyncio

async def debug_cases():
    db = SessionLocal()
    from sqlalchemy import select
    # Target cases from screenshot: KARTHIKA (BSS002), RAJESWARI (TAT002), BALAMURUGAN (TAT001)
    refs = ["BSS002", "TAT002", "TAT001", "IBM002", "IBM003"]
    res = db.execute(select(models.Case).filter(models.Case.case_ref_no.in_(refs)))
    cases = res.scalars().all()
    
    now_dt = datetime.now(timezone.utc)
    print(f"Server Now (UTC): {now_dt}")
    
    for c in cases:
        print("-" * 40)
        print(f"Ref: {c.case_ref_no} | Status: {c.status}")
        print(f"Received: {c.received_date}")
        print(f"Completed: {c.completed_date}")
        
        r_date = c.received_date
        if r_date and r_date.tzinfo is None:
            r_date = r_date.replace(tzinfo=timezone.utc)
            
        e_date = c.completed_date or now_dt
        if e_date and e_date.tzinfo is None:
            e_date = e_date.replace(tzinfo=timezone.utc)
            
        if r_date and e_date:
            diff = e_date - r_date
            print(f"Diff Seconds: {diff.total_seconds()}")
            print(f"Diff Days (floor): {int(diff.total_seconds() / 86400)}")

    db.close()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(debug_cases())
