from app.database import SessionLocal
from app import models
from datetime import datetime
import asyncio

async def debug_tat():
    db = SessionLocal()
    from sqlalchemy import select
    res = db.execute(select(models.Case).limit(5))
    cases = res.scalars().all()
    
    print(f"Current Time: {datetime.now()}")
    for c in cases:
        print(f"Case ID: {c.id}")
        print(f"Received Date: {c.received_date}")
        print(f"Completed Date: {c.completed_date}")
        
        end_dt = c.completed_date or datetime.now() # naive for now
        if c.received_date:
            # Match tzinfo
            if c.received_date.tzinfo:
                now_aware = datetime.now(c.received_date.tzinfo)
                diff = now_aware - c.received_date
            else:
                diff = datetime.now() - c.received_date
            
            print(f"Diff: {diff}")
            print(f"Diff Days: {diff.days}")
    db.close()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(debug_tat())
