import requests
import json

try:
    # We need to bypass auth or use a token. 
    # Since I'm locally I might be able to call it if depends are mocked? 
    # Actually, I'll just use the DB session directly to simulate the route logic.
    pass
except:
    pass

from app.database import SessionLocal
from app import models, schemas
from datetime import datetime, timezone

def test_logic():
    db = SessionLocal()
    from sqlalchemy import select
    res = db.execute(select(models.Case).filter(models.Case.case_ref_no.in_(['BSS002', 'IBM002', 'IBM001', 'TAT002'])))
    cases = res.scalars().all()
    
    now_dt = datetime.now(timezone.utc)
    
    for case in cases:
        case_data = schemas.CaseRead.model_validate(case)
        if case.received_date:
            r_date = case.received_date
            if r_date.tzinfo is None: r_date = r_date.replace(tzinfo=timezone.utc)
            e_date = case.completed_date or now_dt
            if e_date.tzinfo is None: e_date = e_date.replace(tzinfo=timezone.utc)
            
            total_days = (e_date.date() - r_date.date()).days + 1
            total_days = max(1, total_days)
            
            allowed = case.tat_days or 10
            if total_days <= allowed:
                case_data.in_tat = total_days
                case_data.out_tat = 0
            else:
                case_data.in_tat = allowed
                case_data.out_tat = total_days - allowed
                
        print(f"Ref: {case.case_ref_no} | In-TAT Calc: {case_data.in_tat}")
    db.close()

if __name__ == "__main__":
    test_logic()
