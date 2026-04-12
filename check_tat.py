
from app.database import SessionLocal
from app.models import Case
db = SessionLocal()
c = db.query(Case).filter(Case.case_ref_no == 'BGV-2026-182027').first()
if c:
    print(f"TAT: {c.tat_days}")
    if c.batch:
        print(f"Batch TAT: {c.batch.tat_days}")
db.close()
