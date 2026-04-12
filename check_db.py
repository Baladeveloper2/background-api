
from app.database import SessionLocal
from app.models import Case, Candidate
db = SessionLocal()
cases = db.query(Case).all()
print(f"Total Cases: {len(cases)}")
for c in cases:
    name = c.candidate.name if c.candidate else "N/A"
    print(f"ID: {c.id} | Ref: {c.case_ref_no} | Name: {name}")
db.close()
