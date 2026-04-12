
from app.database import SessionLocal
from app.models import Case
from sqlalchemy.orm import joinedload
db = SessionLocal()
query = db.query(Case).options(joinedload(Case.candidate))
cases = query.all()
print(f"LEN: {len(cases)}")
for c in cases:
    print(f"CASE: {c.case_ref_no} | ID: {c.id}")
db.close()
