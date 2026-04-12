
from app.database import SessionLocal
from app.models import Case, Candidate
db = SessionLocal()
search_ref = "BGV-2026-182027"
c = db.query(Case).filter(Case.case_ref_no == search_ref).first()
if c:
    print(f"FOUND: ID={c.id}, CustomerID={c.customer_id}, CandidateID={c.candidate_id}, Status={c.status}")
else:
    print("NOT FOUND")
db.close()
